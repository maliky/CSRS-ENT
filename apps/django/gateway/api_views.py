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
    TaskUpdateSerializer,
    TransitionSerializer,
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
