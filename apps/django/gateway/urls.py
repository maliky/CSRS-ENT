"""Routes exposed by the CSRS ENT gateway."""

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
    path("api/v1/task-management/", api_views.TaskManagementView.as_view()),
    path("api/v1/tasks/bulk-delete/", api_views.TaskBulkDeleteView.as_view()),
    path("api/v1/users/", api_views.UserListCreateView.as_view()),
    path("api/v1/users/options/", api_views.UserOptionsView.as_view()),
    path("api/v1/users/bulk-action/", api_views.UserBulkActionView.as_view()),
    path("api/v1/users/<int:pk>/", api_views.UserDetailView.as_view()),
    path(
        "api/v1/users/<int:pk>/deactivate/",
        api_views.UserDeactivateView.as_view(),
    ),
    path(
        "api/v1/users/<int:pk>/reactivate/",
        api_views.UserReactivateView.as_view(),
    ),
    path(
        "api/v1/users/<int:pk>/temporary-password/",
        api_views.UserTemporaryPasswordView.as_view(),
    ),
    path("api/v1/organization/", api_views.OrganizationView.as_view()),
    path(
        "api/v1/organization/units/",
        api_views.OrganizationUnitCreateView.as_view(),
    ),
    path(
        "api/v1/organization/units/<int:pk>/",
        api_views.OrganizationUnitDetailView.as_view(),
    ),
    path("api/v1/partners/", api_views.PartnerListCreateView.as_view()),
    path("api/v1/partners/<int:pk>/", api_views.PartnerDetailView.as_view()),
    path(
        "api/v1/organization/grants/",
        api_views.RoleGrantCreateView.as_view(),
    ),
    path(
        "api/v1/organization/grants/<int:pk>/revoke/",
        api_views.RoleGrantRevokeView.as_view(),
    ),
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
    path(
        "api/v1/team/<int:pk>/avatar/",
        api_views.TeamEmployeeAvatarView.as_view(),
    ),
    path(
        "api/v1/team/<int:pk>/tor-document/",
        api_views.TeamEmployeeTorDocumentView.as_view(),
    ),
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
    path(
        "api/v1/research-projects/",
        api_views.ResearchProjectListCreateView.as_view(),
    ),
    path(
        "api/v1/research-projects/options/",
        api_views.ResearchProjectOptionsView.as_view(),
    ),
    path(
        "api/v1/research-projects/<int:pk>/",
        api_views.ResearchProjectDetailView.as_view(),
    ),
    path(
        "api/v1/research-projects/<int:pk>/transition/",
        api_views.ResearchProjectTransitionView.as_view(),
    ),
    path(
        "api/v1/research-projects/<int:pk>/sections/<int:section_pk>/transition/",
        api_views.ResearchProjectSectionTransitionView.as_view(),
    ),
    path(
        "api/v1/research-projects/<int:pk>/items/<str:resource>/",
        api_views.ResearchProjectItemCreateView.as_view(),
    ),
    path(
        "api/v1/research-projects/<int:pk>/items/<str:resource>/<int:item_pk>/",
        api_views.ResearchProjectItemUpdateView.as_view(),
    ),
    path("api/v1/processes/options/", api_views.ProcessOptionsView.as_view()),
    path("api/v1/processes/", api_views.ProcessListCreateView.as_view()),
    path("api/v1/processes/<int:pk>/", api_views.ProcessDetailView.as_view()),
    path(
        "api/v1/processes/<int:pk>/transition/",
        api_views.ProcessTransitionView.as_view(),
    ),
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
