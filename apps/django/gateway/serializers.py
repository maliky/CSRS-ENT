"""Input contracts for the Django-to-Odoo façade."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

from rest_framework import serializers


class ScheduleSerializer(serializers.Serializer[dict[str, object]]):
    start_date = serializers.DateField()
    due_date = serializers.DateField()
    estimated_work_days = serializers.DecimalField(
        max_digits=9, decimal_places=4, min_value=Decimal("0.0001")
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if cast(date, attrs["due_date"]) < cast(date, attrs["start_date"]):
            raise serializers.ValidationError(
                {"due_date": "La fin doit suivre le début."}
            )
        return attrs


class TaskCreateSerializer(ScheduleSerializer):
    title = serializers.CharField(max_length=180)
    description = serializers.CharField()
    employee_id = serializers.IntegerField(min_value=1)
    action_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    calendar_id = serializers.IntegerField(min_value=1)


class TaskUpdateSerializer(ScheduleSerializer):
    revision = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=180)
    description = serializers.CharField()
    action_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class ProgressSerializer(serializers.Serializer[dict[str, object]]):
    revision = serializers.IntegerField(min_value=1)
    entry_date = serializers.DateField(required=False)
    percentage = serializers.IntegerField(min_value=0, max_value=100)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    blocked = serializers.BooleanField(required=False, default=False)


class ObservationSerializer(serializers.Serializer[dict[str, object]]):
    revision = serializers.IntegerField(min_value=1)
    message = serializers.CharField()


class TransitionSerializer(serializers.Serializer[dict[str, object]]):
    revision = serializers.IntegerField(min_value=1)
    transition = serializers.ChoiceField(choices=("validate", "reject", "close_early"))
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class TaskManagementQuerySerializer(serializers.Serializer[dict[str, object]]):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=("planned", "active", "awaiting_validation", "completed", "closed_early"),
        required=False,
        allow_blank=True,
        default="",
    )
    employee_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=50
    )


class TaskSelectionSerializer(serializers.Serializer[dict[str, object]]):
    id = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=1)


class TaskBulkDeleteSerializer(serializers.Serializer[dict[str, object]]):
    assignments = TaskSelectionSerializer(many=True, allow_empty=False)
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)
    confirmation = serializers.ChoiceField(choices=("SUPPRIMER",))

    def validate_assignments(
        self, value: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        ids = [item["id"] for item in value]
        if len(ids) > 100:
            raise serializers.ValidationError("La sélection est limitée à 100 tâches.")
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Une tâche ne peut apparaître qu'une fois.")
        return value


class UserManagementQuerySerializer(serializers.Serializer[dict[str, object]]):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    state = serializers.ChoiceField(
        choices=("active", "inactive"), required=False, allow_blank=True, default=""
    )
    unit_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=50
    )


class UserWriteSerializer(serializers.Serializer[dict[str, object]]):
    email = serializers.EmailField(max_length=254)
    login_alias = serializers.RegexField(
        r"^[a-z][a-z0-9_-]*$",
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    position = serializers.CharField(max_length=160, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    agenda_direction = serializers.ChoiceField(
        choices=("", "programs", "administration", "research"),
        required=False,
        allow_blank=True,
    )
    include_in_direction_agendas = serializers.BooleanField(required=False, default=True)
    unit_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    primary_unit_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    primary_supervisor_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    organization_effective_date = serializers.DateField()
    state_token = serializers.CharField(required=False, allow_blank=False)

    def validate_unit_ids(self, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Une unité ne peut apparaître qu'une fois.")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        unit_ids = set(cast(list[int], attrs.get("unit_ids", [])))
        primary = attrs.get("primary_unit_id")
        if primary is not None and primary not in unit_ids:
            raise serializers.ValidationError(
                {"primary_unit_id": "L'unité principale doit être sélectionnée."}
            )
        if attrs.get("primary_supervisor_id") is not None and primary is None:
            raise serializers.ValidationError(
                {"primary_supervisor_id": "Choisissez d'abord une unité principale."}
            )
        return attrs


class UserUpdateSerializer(UserWriteSerializer):
    state_token = serializers.CharField(allow_blank=False)


class StateTokenSerializer(serializers.Serializer[dict[str, object]]):
    state_token = serializers.CharField(allow_blank=False)


class UserSelectionSerializer(serializers.Serializer[dict[str, object]]):
    id = serializers.IntegerField(min_value=1)
    state_token = serializers.CharField(allow_blank=False)


class UserBulkActionSerializer(serializers.Serializer[dict[str, object]]):
    action = serializers.ChoiceField(choices=("deactivate", "delete"))
    users = UserSelectionSerializer(many=True, allow_empty=False)
    reason = serializers.CharField(
        min_length=3,
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )
    confirmation = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_users(self, value: list[dict[str, object]]) -> list[dict[str, object]]:
        ids = [item["id"] for item in value]
        if len(ids) > 100:
            raise serializers.ValidationError("La sélection est limitée à 100 comptes.")
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Un compte ne peut apparaître qu'une fois.")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if attrs["action"] == "delete":
            if len(str(attrs.get("reason") or "").strip()) < 3:
                raise serializers.ValidationError(
                    {"reason": "Le motif de suppression est obligatoire."}
                )
            if attrs.get("confirmation") != "SUPPRIMER":
                raise serializers.ValidationError(
                    {"confirmation": "Saisissez exactement SUPPRIMER."}
                )
        return attrs


class OrganizationUnitSerializer(serializers.Serializer[dict[str, object]]):
    code = serializers.RegexField(r"^[A-Za-z0-9_-]{1,32}$", max_length=32)
    short_name = serializers.CharField(max_length=80)
    long_name = serializers.CharField(max_length=180)
    kind = serializers.CharField(max_length=32, required=False, default="unit")
    display_order = serializers.IntegerField(min_value=0, required=False, default=0)
    parent_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    active = serializers.BooleanField(required=False, default=True)
    state_token = serializers.CharField(required=False, allow_blank=False)
    reason = serializers.CharField(
        min_length=3, max_length=500, required=False, allow_blank=True, default=""
    )


class OrganizationUnitUpdateSerializer(OrganizationUnitSerializer):
    state_token = serializers.CharField(allow_blank=False)


class PartnerQuerySerializer(serializers.Serializer[dict[str, object]]):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    state = serializers.ChoiceField(
        choices=("active", "inactive"), required=False, allow_blank=True, default="active"
    )


class PartnerWriteSerializer(serializers.Serializer[dict[str, object]]):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    active = serializers.BooleanField(required=False, default=True)


class PartnerUpdateSerializer(PartnerWriteSerializer):
    state_token = serializers.CharField(allow_blank=False)


class RoleGrantSerializer(serializers.Serializer[dict[str, object]]):
    user_id = serializers.IntegerField(min_value=1)
    department_id = serializers.IntegerField(min_value=1)
    role_code = serializers.CharField(max_length=64)
    scope = serializers.ChoiceField(choices=("unit", "tree"))
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(min_length=3, max_length=500)


class RevokeGrantSerializer(serializers.Serializer[dict[str, object]]):
    reason = serializers.CharField(min_length=3, max_length=500)


class ProposalCreateSerializer(ScheduleSerializer):
    title = serializers.CharField(max_length=180)
    description = serializers.CharField()
    action_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    calendar_id = serializers.IntegerField(min_value=1)


class ProposalUpdateSerializer(ProposalCreateSerializer):
    revision = serializers.IntegerField(min_value=1)


class RevisionSerializer(serializers.Serializer[dict[str, object]]):
    revision = serializers.IntegerField(min_value=1)


class ProposalDecisionSerializer(RevisionSerializer):
    decision = serializers.ChoiceField(choices=("accept", "reject"))
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PlanningPreviewSerializer(serializers.Serializer[dict[str, object]]):
    calendar_id = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    # DRF's runtime field intentionally shares a name with Serializer.source.
    source = cast(Any, serializers.ChoiceField(choices=("workload", "due")))
    due_date = serializers.DateField(required=False)
    estimated_work_days = serializers.DecimalField(
        max_digits=9,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        required = "estimated_work_days" if attrs["source"] == "workload" else "due_date"
        if required not in attrs:
            raise serializers.ValidationError({required: "Ce champ est obligatoire."})
        return attrs


class PasswordSerializer(serializers.Serializer[dict[str, object]]):
    current_password = serializers.CharField(trim_whitespace=False, max_length=4096)
    new_password = serializers.CharField(
        trim_whitespace=False, min_length=12, max_length=4096
    )
    new_password_confirmation = serializers.CharField(
        trim_whitespace=False, min_length=12, max_length=4096
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if attrs["new_password"] != attrs["new_password_confirmation"]:
            raise serializers.ValidationError(
                {"new_password_confirmation": "Les deux mots de passe sont différents."}
            )
        return attrs


class VisitSerializer(serializers.Serializer[dict[str, object]]):
    party_size = serializers.IntegerField(min_value=1, max_value=999)
    visitor_names = serializers.ListField(
        child=serializers.CharField(max_length=160), required=False, default=list
    )


class AvailabilitySerializer(serializers.Serializer[dict[str, object]]):
    employee_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=("leave", "absence", "mission"))
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
    revision = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if cast(date, attrs["end_date"]) < cast(date, attrs["start_date"]):
            raise serializers.ValidationError(
                {"end_date": "La fin doit suivre le début."}
            )
        return attrs


class CancelSerializer(RevisionSerializer):
    reason = serializers.CharField(min_length=1, max_length=500)


class AgendaPeriodSerializer(serializers.Serializer[dict[str, object]]):
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        start = cast(date, attrs["period_start"])
        end = cast(date, attrs["period_end"])
        if end < start:
            raise serializers.ValidationError({"period_end": "Période invalide."})
        if (end - start).days > 30:
            raise serializers.ValidationError(
                {"period_end": "La période ne peut pas dépasser 31 jours."}
            )
        return attrs


class AgendaDraftSerializer(AgendaPeriodSerializer):
    major_events = serializers.CharField(required=False, allow_blank=True, default="")
    revision = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class AgendaGenerateSerializer(AgendaPeriodSerializer):
    agenda_direction = serializers.ChoiceField(
        choices=("programs", "administration", "research")
    )


class ResearchProjectCreateSerializer(serializers.Serializer[dict[str, object]]):
    name = serializers.CharField(max_length=200)
    objectives = serializers.CharField()
    institutional_commitments = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    date_start = serializers.DateField(required=False, allow_null=True)
    date_end = serializers.DateField(required=False, allow_null=True)
    donor_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    partner_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    team_user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        start = attrs.get("date_start")
        end = attrs.get("date_end")
        if start and end and cast(date, end) < cast(date, start):
            raise serializers.ValidationError(
                {"date_end": "La fin doit suivre le début."}
            )
        return attrs


class ResearchProjectQuerySerializer(serializers.Serializer[dict[str, object]]):
    status = serializers.ChoiceField(
        choices=("active", "archived"), required=False, default="active"
    )


class ResearchProjectUpdateSerializer(ResearchProjectCreateSerializer):
    revision = serializers.IntegerField(min_value=1)


class ResearchProjectTransitionSerializer(RevisionSerializer):
    action = serializers.ChoiceField(
        choices=("approve", "reject", "close", "archive")
    )
    lead_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if attrs["action"] == "approve" and not attrs.get("lead_id"):
            raise serializers.ValidationError(
                {"lead_id": "Choisissez le chef de projet."}
            )
        if attrs["action"] in {"reject", "archive"} and not str(
            attrs.get("reason") or ""
        ).strip():
            raise serializers.ValidationError(
                {"reason": "Le motif est obligatoire."}
            )
        return attrs


class ProjectSectionTransitionSerializer(RevisionSerializer):
    action = serializers.ChoiceField(
        choices=("submit", "verify", "correct", "validate", "close")
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    confirmation = serializers.CharField(required=False, allow_blank=True, default="")


class ResearchProjectItemSerializer(serializers.Serializer[dict[str, object]]):
    revision = serializers.IntegerField(min_value=1)
    values = serializers.DictField()


class ProcessDocumentSerializer(serializers.Serializer[dict[str, object]]):
    name = serializers.CharField(max_length=255)
    mimetype = serializers.ChoiceField(
        choices=("application/pdf", "image/jpeg", "image/png")
    )
    content_base64 = serializers.RegexField(
        r"^[A-Za-z0-9+/]*={0,2}$", max_length=14_000_000
    )


class ProcessCreateSerializer(serializers.Serializer[dict[str, object]]):
    process_type = serializers.ChoiceField(
        choices=(
            "fund",
            "purchase",
            "absence",
            "mission",
            "payment_notice",
            "visa",
            "data",
        )
    )
    origin_department_id = serializers.IntegerField(min_value=1)
    project_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    subject = serializers.CharField(max_length=200)
    description = serializers.CharField()
    amount = serializers.DecimalField(
        max_digits=16,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        default=Decimal("0"),
    )
    details = serializers.DictField()
    documents = ProcessDocumentSerializer(many=True, required=False, default=list)


class ProcessTransitionSerializer(RevisionSerializer):
    action = serializers.CharField(max_length=32)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    confirmation = serializers.CharField(required=False, allow_blank=True, default="")
