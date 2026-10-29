import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ForecastConfig(AppConfig):
    name = "forecast"
    verbose_name = "Cairo temperature forecast"

    def ready(self):
        """Load the trained models ONCE, when the server starts (not on every request)."""
        from .ml.predictor import get_registry

        try:
            get_registry().load()
        except Exception as exc:  # keep `manage.py` commands usable even without artefacts
            logger.warning("Models were not loaded at start-up: %s", exc)
