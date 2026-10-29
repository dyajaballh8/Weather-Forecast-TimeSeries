"""HTML page: rendering, validation messages for bad / missing input, warnings and caching."""
from django.test import SimpleTestCase
from django.urls import reverse

from forecast.ml import history

URL = reverse("forecast:index")


def valid_post(**overrides):
    data = history.latest_inputs()
    data["model"] = "ridge"
    data.update(overrides)
    return data


class PageTests(SimpleTestCase):
    def test_get_renders_form_prefilled_with_latest_real_data(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cairo Temperature Forecast")
        self.assertContains(response, 'name="forecast_date"')
        self.assertContains(response, history.latest_inputs()["forecast_date"])
        self.assertNotContains(response, 'class="card result-card')

    def test_valid_post_shows_forecast_panel(self):
        response = self.client.post(URL, valid_post())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "result-card")
        self.assertContains(response, "Likely range (80%)")
        self.assertContains(response, "<svg")
        self.assertIn("forecast", response.context)
        self.assertGreater(response.context["forecast"].value, 5)

    def test_second_identical_post_is_flagged_as_cached(self):
        data = valid_post(temp_2d_ago="23.37")
        self.client.post(URL, data)
        self.assertContains(self.client.post(URL, data), "served from cache")


class ValidationTests(SimpleTestCase):
    def test_empty_form_lists_every_missing_field(self):
        response = self.client.post(URL, {})
        self.assertContains(response, "We could not make a forecast yet")
        self.assertContains(response, "This field is required", count=7)       # date + 6 temperatures
        self.assertContains(response, "Choose a model.")
        self.assertContains(response, "highlighted 8 fields")
        self.assertNotIn("forecast", response.context)

    def test_non_numeric_text_is_rejected_with_a_clear_message(self):
        response = self.client.post(URL, valid_post(temp_2d_ago="abc"))
        self.assertContains(response, "Enter a number, for example 24.5")
        self.assertContains(response, "is-invalid")

    def test_comma_decimal_is_rejected(self):
        self.assertContains(self.client.post(URL, valid_post(avg_8d="24,5")), "use a dot, not a comma")

    def test_out_of_range_values_are_rejected(self):
        high = self.client.post(URL, valid_post(avg_30d="80"))
        self.assertContains(high, "Too high: the maximum accepted value is 55")
        low = self.client.post(URL, valid_post(avg_62d="-40"))
        self.assertContains(low, "Too low: the minimum accepted value is -10")

    def test_nan_and_infinity_are_rejected(self):
        for bad in ("nan", "inf", "-inf"):
            self.assertContains(self.client.post(URL, valid_post(temp_1y_ago=bad)), "is-invalid")

    def test_bad_date_and_out_of_range_date(self):
        self.assertContains(self.client.post(URL, valid_post(forecast_date="12/10/2026")), "valid date")
        self.assertContains(self.client.post(URL, valid_post(forecast_date="1999-01-01")), "Pick a date between")

    def test_unknown_model_is_rejected(self):
        self.assertContains(self.client.post(URL, valid_post(model="magic")), "not available")

    def test_unusual_but_valid_value_shows_a_warning_not_an_error(self):
        response = self.client.post(URL, valid_post(temp_1y_ago="45"))
        self.assertContains(response, "outside the")
        self.assertContains(response, "result-card")           # still forecasts

    def test_invalid_input_never_returns_a_server_error(self):
        for payload in ({}, {"forecast_date": "x", "temp_2d_ago": "∞"}, {"model": "ridge", "avg_8d": "1e999"}):
            self.assertEqual(self.client.post(URL, payload).status_code, 200)
