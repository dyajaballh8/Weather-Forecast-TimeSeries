from django.urls import path

from . import views

app_name = "forecast"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/predict/", views.api_predict, name="api_predict"),
    path("api/sample/", views.api_sample, name="api_sample"),
    path("health/", views.health, name="health"),
]
