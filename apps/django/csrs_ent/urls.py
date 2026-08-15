"""CSRS ENT URL configuration."""

from django.urls import include, path


urlpatterns = [path("", include("gateway.urls"))]
