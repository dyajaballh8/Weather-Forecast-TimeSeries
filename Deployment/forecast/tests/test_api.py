"""JSON endpoints (bonus): /api/predict/, /api/sample/ and /health/."""
import json

from django.test import SimpleTestCase
from django.urls import reverse

from forecast.ml import history
from forecast.ml.predictor import forecast

PREDICT = reverse("forecast:api_predict")


def payload(**overrides):
    data = history.latest_inputs()
    data.update(overrides)
    return data


class PredictApiTests(SimpleTestCase):
    def post(self, body, raw=False):
        return self.client.post(PREDICT, body if raw else json.dumps(body), content_type="application/json")

    def test_valid_request_returns_forecast_and_intervals(self):
        response = self.post(payload(model="ridge"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertLess(body["interval_95"][0], body["interval_80"][0])
        self.assertLess(body["interval_80"][0], body["predicted_temperature_c"])
        self.assertLess(body["predicted_temperature_c"], body["interval_80"][1])
        self.assertEqual(body["model"], "ridge")

    def test_api_value_equals_python_call(self):
        data = payload(model="random_forest")
        from datetime import date
        direct = forecast("random_forest", date.fromisoformat(data["forecast_date"]),
                          {k: data[k] for k in ("temp_2d_ago", "temp_24d_ago", "temp_1y_ago", "avg_8d", "avg_30d", "avg_62d")})
        self.assertAlmostEqual(self.post(data).json()["predicted_temperature_c"], round(direct.value, 2), places=2)

    def test_repeated_request_is_cached(self):
        data = payload(model="gradient_boosting", temp_2d_ago=21.77)
        self.post(data)
        self.assertTrue(self.post(data).json()["cached"])

    def test_missing_and_invalid_fields_return_400_with_messages(self):
        bad = self.post({"forecast_date": "2026-10-12", "temp_2d_ago": "abc", "model": "ridge"})
        self.assertEqual(bad.status_code, 400)
        errors = bad.json()["errors"]
        self.assertIn("temp_2d_ago", errors)
        self.assertIn("temp_24d_ago", errors)          # missing
        self.assertFalse(bad.json()["ok"])

    def test_malformed_json_and_wrong_method(self):
        self.assertEqual(self.post("{not json", raw=True).status_code, 400)
        self.assertEqual(self.post("[1, 2]", raw=True).status_code, 400)
        self.assertEqual(self.client.get(PREDICT).status_code, 405)


class SampleAndHealthTests(SimpleTestCase):
    def test_sample_returns_real_inputs(self):
        d = history.last_date().isoformat()
        body = self.client.get(reverse("forecast:api_sample"), {"date": d}).json()
        self.assertTrue(body["ok"])
        self.assertIsNotNone(body["observed"])
        self.assertEqual(body["forecast_date"], d)

    def test_sample_for_next_forecast_date_has_no_observed_value(self):
        body = self.client.get(reverse("forecast:api_sample"), {"date": history.latest_inputs()["forecast_date"]}).json()
        self.assertIsNone(body["observed"])

    def test_sample_errors(self):
        url = reverse("forecast:api_sample")
        self.assertEqual(self.client.get(url, {"date": "oops"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"date": "2021-02-01"}).status_code, 404)   # not enough history yet

    def test_health(self):
        body = self.client.get(reverse("forecast:health")).json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["default_model"], "ridge")
