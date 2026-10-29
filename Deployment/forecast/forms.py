"""Input form: labelled fields, clear messages, and soft warnings for unusual values."""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .ml import history
from .ml.predictor import get_registry

DATE_MIN, DATE_MAX = date(2021, 1, 1), date(2035, 12, 31)
TEMP_MIN, TEMP_MAX = -10.0, 55.0     # hard limits (°C): anything outside is rejected


def _temperature(label, help_text):
    return forms.FloatField(
        label=label,
        help_text=help_text,
        min_value=TEMP_MIN,
        max_value=TEMP_MAX,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal",
                                      "placeholder": "e.g. 24.5", "autocomplete": "off"}),
        error_messages={
            "required": "This field is required: enter a temperature in °C.",
            "invalid": "Enter a number, for example 24.5 (use a dot, not a comma).",
            "min_value": f"Too low: the minimum accepted value is {TEMP_MIN:g} °C.",
            "max_value": f"Too high: the maximum accepted value is {TEMP_MAX:g} °C.",
        },
    )


def validate_forecast_date(value):
    if not DATE_MIN <= value <= DATE_MAX:
        raise ValidationError(f"Pick a date between {DATE_MIN:%d %b %Y} and {DATE_MAX:%d %b %Y}.")


class ForecastForm(forms.Form):
    forecast_date = forms.DateField(
        label="Forecast date",
        help_text="The day you want the temperature for.",
        input_formats=["%Y-%m-%d"],
        validators=[validate_forecast_date],
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        error_messages={"required": "This field is required: choose a date.",
                        "invalid": "Enter a valid date (YYYY-MM-DD)."},
    )
    temp_2d_ago = _temperature("Temperature 2 days before", "Mean temperature two days before the forecast date.")
    temp_24d_ago = _temperature("Temperature 24 days before", "Mean temperature 24 days before the forecast date.")
    temp_1y_ago = _temperature("Temperature 1 year before", "Same time last year (366 days before).")
    avg_8d = _temperature("Average of the last 8 days", "Mean of the 4 most recent readings.")
    avg_30d = _temperature("Average of the last 30 days", "Mean of the 15 most recent readings.")
    avg_62d = _temperature("Average of the last 62 days", "Mean of the 31 most recent readings.")
    model = forms.ChoiceField(
        label="Model",
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": "Choose a model.", "invalid_choice": "That model is not available."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        registry = get_registry().ensure_loaded()
        self.fields["model"].choices = registry.choices()
        self.fields["model"].initial = registry.default_key
        self.warnings = []

    def full_clean(self):
        super().full_clean()
        for name in self.errors:                      # red outline on every invalid field
            widget = self.fields[name].widget
            widget.attrs["class"] = f'{widget.attrs.get("class", "")} is-invalid'.strip()

    def clean(self):
        cleaned = super().clean()
        meta = get_registry().meta
        lo, hi = meta["target_range"]["min"] - 3, meta["target_range"]["max"] + 3
        outside = [self.fields[n].label for n in ("temp_2d_ago", "temp_24d_ago", "temp_1y_ago", "avg_8d", "avg_30d", "avg_62d")
                   if cleaned.get(n) is not None and not lo <= cleaned[n] <= hi]
        if outside:
            self.warnings.append(
                f"{', '.join(outside)} is outside the {lo:.0f}–{hi:.0f} °C range the model was trained on, "
                "so the forecast may be unreliable.")
        d = cleaned.get("forecast_date")
        if d and (d - history.last_date()).days > 30:
            self.warnings.append(
                f"The history ends on {history.last_date():%d %b %Y}; a forecast this far ahead relies entirely on "
                "the values you typed.")
        return cleaned
