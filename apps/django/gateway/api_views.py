"""Typed HTTP endpoints delegating every business operation to Odoo."""

from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from typing import cast

from django.conf import settings
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .odoo import (
    JsonObject,
    JsonValue,
    OdooAuthenticationError,
    OdooClient,
    OdooConflictError,
    OdooError,
    OdooNotFoundError,
    OdooPermissionError,
    OdooValidationError,
)
from .serializers import (
    AgendaDraftSerializer,
    AgendaGenerateSerializer,
    AvailabilitySerializer,
    CancelSerializer,
    ObservationSerializer,
    PasswordSerializer,
    PlanningPreviewSerializer,
    ProgressSerializer,
    ProposalCreateSerializer,
    ProposalDecisionSerializer,
    ProposalUpdateSerializer,
    RevisionSerializer,
    TaskCreateSerializer,
    TaskBulkDeleteSerializer,
    TaskManagementQuerySerializer,
    TaskUpdateSerializer,
    TransitionSerializer,
    StateTokenSerializer,
    UserBulkActionSerializer,
    UserManagementQuerySerializer,
    UserUpdateSerializer,
    UserWriteSerializer,
    OrganizationUnitSerializer,
    OrganizationUnitUpdateSerializer,
    RevokeGrantSerializer,
    ResearchProjectCreateSerializer,
    ResearchProjectItemSerializer,
    ResearchProjectTransitionSerializer,
    ResearchProjectUpdateSerializer,
    RoleGrantSerializer,
    ProjectSectionTransitionSerializer,
    ProcessCreateSerializer,
    ProcessTransitionSerializer,
    VisitSerializer,
)


def _client() -> OdooClient:
    return OdooClient(
        base_url=settings.ODOO_URL,
        database=settings.ODOO_DATABASE,
        timeout=settings.ODOO_TIMEOUT,
    )


def _validation_fields(detail: object) -> dict[str, list[str]]:
    if not isinstance(detail, dict):
        return {"non_field_errors": [str(detail)]}
    fields: dict[str, list[str]] = {}
    for key, value in detail.items():
        values = value if isinstance(value, list) else [value]
        fields[str(key)] = [str(item) for item in values]
    return fields


def _error(code: str, message: str, http_status: int) -> Response:
    return Response(
        {"error": {"code": code, "message": message, "fields": {}}},
        status=http_status,
    )


def _payload(
    serializer_class: type[serializers.Serializer[dict[str, object]]],
    data: object,
) -> JsonObject:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return cast(JsonObject, dict(serializer.data))


@method_decorator(csrf_protect, name="dispatch")
class OdooAPIView(APIView):
    """Authenticate via the relayed Odoo session and normalize RPC failures."""

    def rpc(
        self,
        request: Request,
        method: str,
        args: list[JsonValue] | None = None,
    ) -> JsonValue:
        session_id = request.session.get("odoo_session_id")
        if not isinstance(session_id, str) or not session_id:
            raise OdooAuthenticationError("Authentification requise.")
        return _client().call(session_id, method, args)

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, DrfValidationError):
            fields = _validation_fields(exc.detail)
            return Response(
                {
                    "error": {
                        "code": "invalid_request",
                        "message": "Corrigez les champs indiqués.",
                        "fields": fields,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, OdooAuthenticationError):
            self.request.session.flush()
            return _error("authentication_required", str(exc), 401)
        if isinstance(exc, OdooPermissionError):
            return _error("permission_denied", str(exc), 403)
        if isinstance(exc, OdooNotFoundError):
            return _error("not_found", str(exc), 404)
        if isinstance(exc, OdooConflictError):
            return _error("stale_revision", str(exc), 409)
        if isinstance(exc, OdooValidationError):
            return _error("business_validation", str(exc), 422)
        if isinstance(exc, OdooError):
            return _error("odoo_unavailable", "Odoo est indisponible.", 503)
        return super().handle_exception(exc)


class SessionPasswordView(OdooAPIView):
    @extend_schema(request=PasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        payload = _payload(PasswordSerializer, request.data)
        self.rpc(
            request,
            "api_change_password",
            [payload["current_password"], payload["new_password"]],
        )
        return Response(status=204)


class DashboardView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(
                request,
                "api_dashboard",
                [request.query_params.get("week"), request.query_params.get("month")],
            )
        )


class PlanningOptionsView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_planning_options"))


class PlanningPreviewView(OdooAPIView):
    @extend_schema(request=PlanningPreviewSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(PlanningPreviewSerializer, request.data)
        return Response(self.rpc(request, "api_planning_preview", [payload]))


class TaskCreateView(OdooAPIView):
    @extend_schema(request=TaskCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(TaskCreateSerializer, request.data)
        return Response(self.rpc(request, "api_task_create", [payload]), status=201)


class TaskDetailView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk: int) -> Response:
        return Response(self.rpc(request, "api_task", [pk]))

    @extend_schema(request=TaskUpdateSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(TaskUpdateSerializer, request.data)
        return Response(self.rpc(request, "api_task_update", [pk, payload]))


class TaskProgressView(OdooAPIView):
    @extend_schema(request=ProgressSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(ProgressSerializer, request.data)
        return Response(self.rpc(request, "api_task_progress", [pk, payload]))


class TaskObservationView(OdooAPIView):
    @extend_schema(request=ObservationSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(ObservationSerializer, request.data)
        return Response(self.rpc(request, "api_task_comment", [pk, payload]))


class TaskTransitionView(OdooAPIView):
    @extend_schema(request=TransitionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(TransitionSerializer, request.data)
        return Response(self.rpc(request, "api_task_transition", [pk, payload]))


class TaskManagementView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        payload = _payload(TaskManagementQuerySerializer, request.query_params)
        return Response(
            self.rpc(
                request,
                "api_task_management",
                [
                    payload["q"],
                    payload["status"],
                    payload.get("employee_id"),
                    payload["page"],
                    payload["page_size"],
                ],
            )
        )


class TaskBulkDeleteView(OdooAPIView):
    @extend_schema(request=TaskBulkDeleteSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(TaskBulkDeleteSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_task_bulk_delete",
                [payload["assignments"], payload["reason"]],
            )
        )


class UserListCreateView(OdooAPIView):
    @extend_schema(operation_id="user_list", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        payload = _payload(UserManagementQuerySerializer, request.query_params)
        return Response(
            self.rpc(
                request,
                "api_users",
                [
                    payload["q"],
                    payload["state"],
                    payload.get("unit_id"),
                    payload["page"],
                    payload["page_size"],
                ],
            )
        )

    @extend_schema(request=UserWriteSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(UserWriteSerializer, request.data)
        return Response(self.rpc(request, "api_user_create", [payload]), status=201)


class UserOptionsView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_user_options"))


class UserDetailView(OdooAPIView):
    @extend_schema(operation_id="user_retrieve", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk: int) -> Response:
        return Response(self.rpc(request, "api_user", [pk]))

    @extend_schema(request=UserUpdateSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(UserUpdateSerializer, request.data)
        return Response(self.rpc(request, "api_user_update", [pk, payload]))


class UserActiveView(OdooAPIView):
    active = False

    @extend_schema(request=StateTokenSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(StateTokenSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_user_set_active",
                [pk, payload["state_token"], self.active],
            )
        )


class UserDeactivateView(UserActiveView):
    active = False


class UserReactivateView(UserActiveView):
    active = True


class UserTemporaryPasswordView(OdooAPIView):
    @extend_schema(request=StateTokenSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(StateTokenSerializer, request.data)
        response = Response(
            self.rpc(
                request,
                "api_user_temporary_password",
                [pk, payload["state_token"]],
            )
        )
        response["Cache-Control"] = "no-store"
        return response


class UserBulkActionView(OdooAPIView):
    @extend_schema(request=UserBulkActionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(UserBulkActionSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_user_bulk_action",
                [payload["action"], payload["users"], payload.get("reason", "")],
            )
        )


class OrganizationView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_organization"))


class OrganizationUnitCreateView(OdooAPIView):
    @extend_schema(request=OrganizationUnitSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(OrganizationUnitSerializer, request.data)
        return Response(
            self.rpc(request, "api_organization_unit_create", [payload]), status=201
        )


class OrganizationUnitDetailView(OdooAPIView):
    @extend_schema(
        request=OrganizationUnitUpdateSerializer, responses=OpenApiTypes.OBJECT
    )
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(OrganizationUnitUpdateSerializer, request.data)
        return Response(self.rpc(request, "api_organization_unit_update", [pk, payload]))


class RoleGrantCreateView(OdooAPIView):
    @extend_schema(request=RoleGrantSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(RoleGrantSerializer, request.data)
        return Response(self.rpc(request, "api_role_grant_create", [payload]), status=201)


class RoleGrantRevokeView(OdooAPIView):
    @extend_schema(request=RevokeGrantSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(RevokeGrantSerializer, request.data)
        return Response(
            self.rpc(request, "api_role_grant_revoke", [pk, payload["reason"]])
        )


class ProposalListCreateView(OdooAPIView):
    @extend_schema(operation_id="proposal_list", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_proposals"))

    @extend_schema(request=ProposalCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(ProposalCreateSerializer, request.data)
        return Response(self.rpc(request, "api_proposal_create", [payload]), status=201)


class ProposalDetailView(OdooAPIView):
    @extend_schema(operation_id="proposal_retrieve", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk: int) -> Response:
        return Response(self.rpc(request, "api_proposal", [pk]))

    @extend_schema(request=ProposalUpdateSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(ProposalUpdateSerializer, request.data)
        return Response(self.rpc(request, "api_proposal_update", [pk, payload]))


class ProposalResubmitView(OdooAPIView):
    @extend_schema(request=RevisionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(RevisionSerializer, request.data)
        return Response(
            self.rpc(request, "api_proposal_resubmit", [pk, payload["revision"]])
        )


class ProposalDecisionView(OdooAPIView):
    @extend_schema(request=ProposalDecisionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(ProposalDecisionSerializer, request.data)
        return Response(self.rpc(request, "api_proposal_decide", [pk, payload]))


class TeamView(OdooAPIView):
    @extend_schema(operation_id="team_overview", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(
                request,
                "api_team",
                [request.query_params.get("week"), request.query_params.get("month")],
            )
        )


class TeamEmployeeView(OdooAPIView):
    @extend_schema(operation_id="team_employee", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk: int) -> Response:
        return Response(
            self.rpc(
                request,
                "api_team_employee",
                [
                    pk,
                    request.query_params.get("week"),
                    request.query_params.get("month"),
                ],
            )
        )


class VisitListCreateView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(
                request,
                "api_visits",
                [
                    request.query_params.get("period_start"),
                    request.query_params.get("period_end"),
                ],
            )
        )

    @extend_schema(request=VisitSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(VisitSerializer, request.data)
        return Response(self.rpc(request, "api_visit_create", [payload]), status=201)


class VisitDepartureView(OdooAPIView):
    @extend_schema(request=RevisionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(RevisionSerializer, request.data)
        return Response(
            self.rpc(request, "api_visit_departure", [pk, payload["revision"]])
        )


class AvailabilityListCreateView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(request, "api_availability", [request.query_params.get("week")])
        )

    @extend_schema(request=AvailabilitySerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(AvailabilitySerializer, request.data)
        return Response(self.rpc(request, "api_availability_save", [payload]), status=201)


class AvailabilityDetailView(OdooAPIView):
    @extend_schema(request=AvailabilitySerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(AvailabilitySerializer, request.data)
        return Response(self.rpc(request, "api_availability_save", [payload, pk]))


class AvailabilityCancelView(OdooAPIView):
    @extend_schema(request=CancelSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(CancelSerializer, request.data)
        return Response(self.rpc(request, "api_availability_cancel", [pk, payload]))


class AgendaPreviewView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(
                request,
                "api_agenda_preview",
                [
                    request.query_params.get("period_start"),
                    request.query_params.get("period_end"),
                    request.query_params.get("agenda_direction", "programs"),
                ],
            )
        )


class AgendaDraftView(OdooAPIView):
    @extend_schema(request=AgendaDraftSerializer, responses=OpenApiTypes.OBJECT)
    def put(self, request: Request) -> Response:
        payload = _payload(AgendaDraftSerializer, request.data)
        return Response(self.rpc(request, "api_agenda_update_draft", [payload]))


class AgendaVersionListCreateView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(
            self.rpc(
                request,
                "api_agenda_versions",
                [
                    request.query_params.get("period_start"),
                    request.query_params.get("period_end"),
                ],
            )
        )

    @extend_schema(request=AgendaGenerateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(AgendaGenerateSerializer, request.data)
        return Response(self.rpc(request, "api_agenda_generate", [payload]), status=201)


class AgendaVersionPdfView(OdooAPIView):
    @extend_schema(responses={(200, "application/pdf"): bytes})
    def get(self, request: Request, pk: int) -> HttpResponse:
        result = self.rpc(request, "api_agenda_pdf", [pk])
        if not isinstance(result, dict):
            raise OdooError("Réponse PDF Odoo invalide.")
        name = result.get("name")
        content = result.get("content")
        if not isinstance(name, str) or not isinstance(content, str):
            raise OdooError("Réponse PDF Odoo invalide.")
        try:
            pdf = b64decode(content, validate=True)
        except (Base64Error, ValueError) as exc:
            raise OdooError("Réponse PDF Odoo invalide.") from exc
        if not pdf.startswith(b"%PDF-") or len(pdf) > 50 * 1024 * 1024:
            raise OdooError("Réponse PDF Odoo invalide.")
        response = HttpResponse(pdf, content_type="application/pdf")
        safe_name = name.replace("/", "-").replace("\\", "-")
        response["Content-Disposition"] = (
            content_disposition_header(False, safe_name)
            or f'inline; filename="{safe_name}"'
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ResearchProjectListCreateView(OdooAPIView):
    @extend_schema(operation_id="research_projects_list", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_research_projects"))

    @extend_schema(request=ResearchProjectCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(ResearchProjectCreateSerializer, request.data)
        return Response(
            self.rpc(request, "api_research_project_create", [payload]), status=201
        )


class ResearchProjectOptionsView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_research_project_options"))


class ResearchProjectDetailView(OdooAPIView):
    @extend_schema(
        operation_id="research_projects_retrieve", responses=OpenApiTypes.OBJECT
    )
    def get(self, request: Request, pk: int) -> Response:
        return Response(self.rpc(request, "api_research_project", [pk]))

    @extend_schema(request=ResearchProjectUpdateSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int) -> Response:
        payload = _payload(ResearchProjectUpdateSerializer, request.data)
        return Response(self.rpc(request, "api_research_project_update", [pk, payload]))


class ResearchProjectTransitionView(OdooAPIView):
    @extend_schema(
        request=ResearchProjectTransitionSerializer, responses=OpenApiTypes.OBJECT
    )
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(ResearchProjectTransitionSerializer, request.data)
        return Response(
            self.rpc(request, "api_research_project_transition", [pk, payload])
        )


class ResearchProjectSectionTransitionView(OdooAPIView):
    @extend_schema(
        request=ProjectSectionTransitionSerializer, responses=OpenApiTypes.OBJECT
    )
    def post(self, request: Request, pk: int, section_pk: int) -> Response:
        payload = _payload(ProjectSectionTransitionSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_research_project_section_transition",
                [pk, section_pk, payload],
            )
        )


class ResearchProjectItemCreateView(OdooAPIView):
    @extend_schema(request=ResearchProjectItemSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int, resource: str) -> Response:
        payload = _payload(ResearchProjectItemSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_research_project_item_save",
                [pk, resource, payload, None],
            ),
            status=201,
        )


class ResearchProjectItemUpdateView(OdooAPIView):
    @extend_schema(request=ResearchProjectItemSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, pk: int, resource: str, item_pk: int) -> Response:
        payload = _payload(ResearchProjectItemSerializer, request.data)
        return Response(
            self.rpc(
                request,
                "api_research_project_item_save",
                [pk, resource, payload, item_pk],
            )
        )


class ProcessOptionsView(OdooAPIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_process_options"))


class ProcessListCreateView(OdooAPIView):
    @extend_schema(operation_id="processes_list", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        return Response(self.rpc(request, "api_processes"))

    @extend_schema(request=ProcessCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        payload = _payload(ProcessCreateSerializer, request.data)
        return Response(self.rpc(request, "api_process_create", [payload]), status=201)


class ProcessDetailView(OdooAPIView):
    @extend_schema(operation_id="processes_retrieve", responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk: int) -> Response:
        return Response(self.rpc(request, "api_process", [pk]))


class ProcessTransitionView(OdooAPIView):
    @extend_schema(request=ProcessTransitionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, pk: int) -> Response:
        payload = _payload(ProcessTransitionSerializer, request.data)
        return Response(self.rpc(request, "api_process_transition", [pk, payload]))
