"""Routes exposed by the PENT gateway."""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import api_views, views


urlpatterns = [
    path("", views.index, name="index"),
    path("app/", views.react_app, name="react_app"),
    path("app/<path:path>", views.react_app, name="react_app_route"),
    path("connexion/", views.login_page, name="login_page"),
    path("healthz/", views.health, name="health"),
    path("readyz/", views.readiness, name="readiness"),
    path("api/v1/session/", views.session_detail, name="session_detail"),
    path("api/v1/session/login/", views.session_login, name="session_login"),
    path("api/v1/session/logout/", views.session_logout, name="session_logout"),
    path("api/v1/session/password/", api_views.SessionPasswordView.as_view()),
    path("api/v1/openapi/", SpectacularAPIView.as_view(), name="openapi"),
    path(
        "api/v1/documentation/",
        SpectacularSwaggerView.as_view(url_name="openapi"),
        name="api_documentation",
    ),
    path("api/v1/dashboard/", api_views.DashboardView.as_view()),
    path("api/v1/planning/options/", api_views.PlanningOptionsView.as_view()),
    path("api/v1/planning/preview/", api_views.PlanningPreviewView.as_view()),
    path("api/v1/tasks/", api_views.TaskCreateView.as_view()),
    path("api/v1/tasks/<int:pk>/", api_views.TaskDetailView.as_view()),
    path("api/v1/tasks/<int:pk>/progress/", api_views.TaskProgressView.as_view()),
    path(
        "api/v1/tasks/<int:pk>/observations/",
        api_views.TaskObservationView.as_view(),
    ),
    path(
        "api/v1/tasks/<int:pk>/transition/",
        api_views.TaskTransitionView.as_view(),
    ),
    path("api/v1/proposals/", api_views.ProposalListCreateView.as_view()),
    path("api/v1/proposals/<int:pk>/", api_views.ProposalDetailView.as_view()),
    path(
        "api/v1/proposals/<int:pk>/resubmit/",
        api_views.ProposalResubmitView.as_view(),
    ),
    path(
        "api/v1/proposals/<int:pk>/decision/",
        api_views.ProposalDecisionView.as_view(),
    ),
    path("api/v1/team/", api_views.TeamView.as_view()),
    path("api/v1/team/<int:pk>/", api_views.TeamEmployeeView.as_view()),
    path("api/v1/visits/", api_views.VisitListCreateView.as_view()),
    path(
        "api/v1/visits/<int:pk>/departure/",
        api_views.VisitDepartureView.as_view(),
    ),
    path("api/v1/availability/", api_views.AvailabilityListCreateView.as_view()),
    path(
        "api/v1/availability/<int:pk>/",
        api_views.AvailabilityDetailView.as_view(),
    ),
    path(
        "api/v1/availability/<int:pk>/cancel/",
        api_views.AvailabilityCancelView.as_view(),
    ),
    path("api/v1/agenda/preview/", api_views.AgendaPreviewView.as_view()),
    path("api/v1/agenda/draft/", api_views.AgendaDraftView.as_view()),
    path(
        "api/v1/agenda/versions/",
        api_views.AgendaVersionListCreateView.as_view(),
    ),
    path(
        "api/v1/agenda/versions/<int:pk>/pdf/",
        api_views.AgendaVersionPdfView.as_view(),
    ),
]
