"""
Django settings for the Cairo temperature forecast app.

Everything that changes between your laptop and a public server is read from
environment variables (see .env.example), so no code edits are needed to deploy.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------- security
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-local-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)          # keep OFF in production

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Hosting platforms announce their public hostname through env variables.
for _host in (os.environ.get("RENDER_EXTERNAL_HOSTNAME"), os.environ.get("RAILWAY_PUBLIC_DOMAIN"), os.environ.get("VERCEL_URL")):
    if _host:
        ALLOWED_HOSTS.append(_host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

ALLOWED_HOSTS.append(".vercel.app")

# Only switch these on behind HTTPS (Render / Railway); they would break plain-http local runs.
if env_bool("DJANGO_SECURE_COOKIES", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 3600

# --------------------------------------------------------------------------- apps
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "forecast",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",       # serves CSS/JS in production
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# The app has no database: the model and the history are plain files.
DATABASES = {}

# --------------------------------------------------------------------------- static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
try:                                  # WhiteNoise warns when the folder does not exist yet
    STATIC_ROOT.mkdir(exist_ok=True)
except OSError:
    pass
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True      # also works before `collectstatic` (local runs)
WHITENOISE_AUTOREFRESH = DEBUG

# --------------------------------------------------------------------------- ML artefacts
ARTIFACTS_DIR = BASE_DIR / "artifacts"      # trained models + metadata.json
DATA_DIR = BASE_DIR / "data"                # history used for presets and the training script

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
