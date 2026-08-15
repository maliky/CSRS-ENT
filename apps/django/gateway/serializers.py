"""Input contracts for the Django-to-Odoo façade."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

from rest_framework import serializers


class ScheduleSerializer(serializers.Serializer[dict[str, object]]):
    start_date = serializers.DateField()
    due_date = serializers.DateField()
    estimated_work_days = serializers.DecimalField(
        max_digits=7, decimal_places=1, min_value=Decimal("0.1")
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
        max_digits=7, decimal_places=1, min_value=Decimal("0.1"), required=False
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
    agenda_direction = serializers.ChoiceField(choices=("programs", "administration"))
