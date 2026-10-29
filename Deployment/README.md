# Cairo Temperature Forecast — Django app

A small web app that wraps a trained time-series model in Django. You type a forecast date and a few recent
temperature readings; the app returns the predicted temperature for that date with an uncertainty range.

| Form + result | Validation messages | Phone |
|---|---|---|
| ![result](docs/screenshots/02_result_desktop.png) | ![errors](docs/screenshots/03_validation_errors_desktop.png) | ![mobile](docs/screenshots/06_result_mobile.png) |

**Highlights**

- Models are **loaded once at server start-up** (`ForecastConfig.ready`) and reused by every request.
- Card-style Bootstrap 5 form with grouped, labelled inputs, **inline validation messages** and soft warnings.
- Colour-coded result panel (cool / mild / warm / hot), **80% and 95% ranges** and a chart of your inputs vs the forecast.
- Works on phones (the result moves above the form after you submit).
- Bonus features: **model dropdown** (3 models), **JSON API**, **in-memory cache** for repeated inputs, chart.
- 28 automated tests, plus a notebook that proves the app reproduces the notebook predictions.

---

## Run it locally

Requires Python 3.11+ (3.12 recommended).

```bash
# 1. create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell:  .venv\Scripts\Activate.ps1

# 2. install the dependencies
pip install -r requirements.txt

# 3. start the server
python manage.py runserver
```

Open <http://127.0.0.1:8000>. The form is pre-filled with the latest real readings, so you can simply press
**Forecast temperature**. Set `DJANGO_DEBUG=1` first if you want Django's debug pages while developing
(`$env:DJANGO_DEBUG=1` in PowerShell). No database or migrations are needed.

## Using the app

| Field | Meaning |
|---|---|
| Forecast date | The day you want the temperature for |
| Temperature 2 days / 24 days / 1 year before | Mean temperature at those moments before the forecast date |
| Average of the last 8 / 30 / 62 days | Mean of the 4 / 15 / 31 most recent 2-day readings |
| Model | Ridge regression (default, most accurate), Random forest or Gradient boosting |

Use **Try it with real data** to fill the form from the dataset (the dropdown lists the next forecast date and the
most recent observed dates; for observed dates the page also shows the recorded value so you can judge the forecast).

## The model

The data is NASA POWER daily temperature for Cairo (2021-2026), sampled every 2 days and prepared in the
`Preprocessing` notebook. The model predicts **the next 2-day reading** from the time of year and recent history.
Eight features are used, exactly as built in the preprocessing step:

`day_of_year_sin`, `day_of_year_cos`, `lag_1` (2 days before), `lag_12` (24 days), `lag_183` (about 1 year),
`roll_mean_4`, `roll_mean_15`, `roll_mean_31`.

Weekday, weekend and rolling-std features were dropped: they carry no signal (correlation ≈ 0) and cross-validation
error improved without them. Humidity, pressure and wind are not inputs because their same-day values are not known at forecast time.

| Model | CV MAE (°C) | Hold-out MAE (°C) |
|---|---|---|
| **Ridge regression** (default) | **1.39** | 0.76 |
| Random forest | 1.56 | 0.84 |
| Gradient boosting | 1.64 | 0.85 |
| *Baseline: same as 2 days ago* | 1.59 | 0.92 |
| *Baseline: same day last year* | 2.28 | 0.92 |

*CV* = 5 expanding, time-ordered folds over the 861 training rows (the evidence to trust). *Hold-out* = the last 21 days
(11 readings, same split as the Preprocessing task); it is small and from a calm autumn stretch, so it is optimistic.

**Uncertainty.** The 80% / 95% ranges are the empirical quantiles of the model's out-of-sample errors during cross-validation,
added to the forecast. They are global (one range for all seasons) and therefore approximate; errors are larger in spring.

**Limitations.** One step ahead only (the next 2-day reading); a date far beyond the history relies entirely on the values you type;
inputs outside the 4–38 °C range seen in training trigger a warning.

### Retrain or replace the model

```bash
python scripts/train_models.py        # rewrites everything in artifacts/
```

To serve a different scikit-learn model, add it to `_model_factories()` in `forecast/ml/training.py` (keep `FEATURE_ORDER`) and rerun the script.

## Tests

```bash
python manage.py test                 # 28 tests
```

They check that the features built by the app equal **all 872 rows** of the notebook's model-ready CSV (max difference < 1e-9),
that predictions equal the models called directly, that models load once, form validation (empty, non-numeric, out-of-range, bad date,
unknown model), the JSON API and the cache.
`notebooks/verify_app_matches_notebook.ipynb` shows the same comparison step by step (difference ≈ 0).

## JSON API (bonus)

```bash
curl -X POST http://127.0.0.1:8000/api/predict/ -H "Content-Type: application/json" -d '{
  "forecast_date": "2026-10-12", "temp_2d_ago": 24.61, "temp_24d_ago": 28.52, "temp_1y_ago": 22.84,
  "avg_8d": 24.48, "avg_30d": 26.85, "avg_62d": 28.78, "model": "ridge"}'
```

```json
{"ok": true, "forecast_date": "2026-10-12", "predicted_temperature_c": 24.4,
 "interval_80": [22.32, 26.76], "interval_95": [20.94, 28.76], "model": "ridge",
 "model_label": "Ridge regression", "cached": false, "warnings": []}
```

Invalid input returns HTTP 400 with one message list per field (`{"ok": false, "errors": {...}}`).
Also: `GET /api/sample/?date=2026-10-12` (real inputs for a date) and `GET /health/`.

## Deploy to a public URL (optional)

Static files are served by WhiteNoise, so no extra web server is needed.

**Render** (free tier works): push the repository to GitHub → *New* → *Web Service* → pick the repo, then set

| Setting | Value |
|---|---|
| Root Directory | `Deployment` |
| Build Command | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Start Command | `gunicorn config.wsgi:application --workers 2 --timeout 60` |
| Health Check Path | `/health/` |
| Environment | `PYTHON_VERSION=3.12.3`, `DJANGO_DEBUG=0`, `DJANGO_SECURE_COOKIES=1`, `DJANGO_SECRET_KEY=<long random string>` |

Render's hostname is added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` automatically (`RENDER_EXTERNAL_HOSTNAME`). A custom domain must be listed in
`DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` (see `.env.example`). **Railway** works the same way using the included `Procfile`
(set the service's root directory to `Deployment`; the same variables apply).

Production checklist: debug off · secret key from the environment · allowed hosts set · `collectstatic` in the build · models are small (≈1.4 MB in total), so they are committed to the repository.

## Project structure

```
Deployment/
├── manage.py · requirements.txt · Procfile · runtime.txt · render.yaml · .env.example
├── config/                    # settings (env-driven), urls, wsgi
├── forecast/                  # the Django app
│   ├── ml/                    # ML logic, independent of Django views
│   │   ├── features.py        #   feature engineering (mirrors the preprocessing notebook)
│   │   ├── predictor.py       #   model registry (loaded once), cached prediction, result bands
│   │   ├── history.py         #   the 2-day history behind the presets
│   │   ├── training.py        #   training + evaluation + saving
│   │   └── chart.py           #   inline SVG chart
│   ├── forms.py               # validation rules and messages
│   ├── views.py · urls.py     # HTML page + JSON API
│   ├── templates/forecast/    # base.html, index.html, _field.html
│   ├── static/forecast/       # app.css, app.js, vendored Bootstrap 5.3 + Bootstrap Icons
│   └── tests/                 # parity, form/view and API tests
├── artifacts/                 # trained models (.joblib), metadata.json, holdout_predictions.csv
├── data/                      # model-ready features + target history (CSV)
├── scripts/                   # train_models.py, prepare_data.py
├── notebooks/                 # verify_app_matches_notebook.ipynb
└── docs/screenshots/          # UI screenshots
```

## Task checklist

| Requirement | Where |
|---|---|
| Django project with a dedicated inference app | `config/` + `forecast/` |
| Load the serialized model once | `ForecastConfig.ready()` → `ModelRegistry.load()` |
| Form for user input | `forecast/forms.py`, `templates/forecast/index.html` |
| Prediction shown on the same page, with a range | result panel (80% / 95% intervals) |
| Bootstrap UI, responsive, consistent palette | `static/forecast/css/app.css`, screenshots in `docs/screenshots/` |
| Invalid / missing / out-of-range input | `ForecastForm` messages, `tests/test_forms_views.py` |
| Prediction matches the notebook | `tests/test_parity.py`, `notebooks/verify_app_matches_notebook.ipynb` |
| Bonus: chart · model dropdown · JSON API · cache | `ml/chart.py` · model field · `/api/predict/` · `lru_cache` in `ml/predictor.py` |

## Credits

Weather data: NASA POWER. Bootstrap 5.3 and Bootstrap Icons (MIT) are bundled in `forecast/static/forecast/vendor/` so the app works offline.
