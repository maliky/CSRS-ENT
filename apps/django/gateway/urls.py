"""Routes exposed by the PENT gateway."""

from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("app/", views.react_app, name="react_app"),
    path("connexion/", views.login_page, name="login_page"),
    path("healthz/", views.health, name="health"),
    path("readyz/", views.readiness, name="readiness"),
    path("api/v1/session/", views.session_detail, name="session_detail"),
    path("api/v1/session/login/", views.session_login, name="session_login"),
    path("api/v1/session/logout/", views.session_logout, name="session_logout"),
]
