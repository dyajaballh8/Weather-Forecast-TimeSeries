"""HTML page + JSON API. All prediction logic lives in forecast/ml, the views only wire things together."""
import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ForecastForm
from .ml import history
from .ml.chart import build_input_chart
from .ml.features import INPUT_ORDER
from .ml.predictor import describe_band, forecast, get_registry


def _run(form):
    """Validated form -> (Forecast, inputs dict, forecast date)."""
    data = form.cleaned_data
    inputs = {k: data[k] for k in INPUT_ORDER}
    return forecast(data["model"], data["forecast_date"], inputs), inputs, data["forecast_date"]


def _result_context(result, inputs, forecast_date):
    observed = history.observed_value(forecast_date)
    return {
        "forecast": result,
        "band": describe_band(result.value),
        "chart_svg": build_input_chart(inputs, result),
        "observed": observed,
        "observed_error": None if observed is None else result.value - observed,
        "forecast_date": forecast_date,
    }


@require_http_methods(["GET", "POST"])
def index(request):
    registry = get_registry().ensure_loaded()
    context = {"samples": history.sample_dates(), "meta": registry.meta,
               "default_meta": registry.meta["models"][registry.default_key]}
    if request.method == "POST":
        form = ForecastForm(request.POST)
        if form.is_valid():
            result, inputs, d = _run(form)
            context.update(_result_context(result, inputs, d))
    else:
        initial = history.latest_inputs() or {}
        initial["forecast_date"] = date.fromisoformat(initial["forecast_date"]) if initial else None
        form = ForecastForm(initial=initial)
    context["form"] = form
    return render(request, "forecast/index.html", context)


def _json_error(errors, status=400):
    return JsonResponse({"ok": False, "errors": errors}, status=status)


@csrf_exempt            # stateless JSON endpoint for other apps: no cookies, no session
@require_POST
def api_predict(request):
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        return _json_error({"__all__": ["Send a JSON object as the request body."]})
    data = {k: ("" if v is None else str(v)) for k, v in payload.items()}
    form = ForecastForm(data)
    if not form.is_valid():
        return _json_error({name: [str(e) for e in errs] for name, errs in form.errors.items()})
    result, _, d = _run(form)
    return JsonResponse({
        "ok": True,
        "forecast_date": d.isoformat(),
        "predicted_temperature_c": round(result.value, 2),
        "interval_80": [round(result.low80, 2), round(result.high80, 2)],
        "interval_95": [round(result.low95, 2), round(result.high95, 2)],
        "model": result.model_key,
        "model_label": result.model_label,
        "cached": result.cached,
        "warnings": form.warnings,
    })


@require_GET
def api_sample(request):
    """Real inputs from the history for a given date (used by the 'Load real data' button)."""
    raw = request.GET.get("date", "")
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return _json_error({"date": ["Use the format YYYY-MM-DD."]})
    inputs = history.inputs_for_date(d)
    if inputs is None:
        return _json_error({"date": [f"No real data for {raw}: pick a 2-day grid date between "
                                     f"{history.first_date():%d %b %Y} (+1 year) and the next forecast date."]}, status=404)
    observed = history.observed_value(d)
    return JsonResponse({"ok": True, **inputs, "observed": observed})


@require_GET
def health(request):
    registry = get_registry().ensure_loaded()
    return JsonResponse({"status": "ok", "models": list(registry.models), "default_model": registry.default_key})
