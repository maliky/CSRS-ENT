"""Routes exposed by the PENT gateway."""

from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("healthz/", views.health, name="health"),
    path("readyz/", views.readiness, name="readiness"),
]
