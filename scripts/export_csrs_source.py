"""Emit the CSRS reporting snapshot; redirect stdout to a mode-0600 file."""

import base64
import json
import sys

from django.utils import timezone

from access.models import RoleGrant
from accounts.models import User
from agenda.models import AgendaDraft, AgendaVersion, StaffAvailability, VisitorVisit
from agenda.services import agenda_pdf_bytes
from work.models import (
    ActionPlan,
    HistoricalProgressEntry,
    HistoricalTask,
    HistoricalTaskAssignment,
    HistoricalTaskProposal,
    InstitutionalAction,
    OrganizationMembership,
    OrganizationUnit,
    OrganizationUnitLink,
    ProgressEntry,
    ReportingLine,
    StrategicPlan,
    Task,
    TaskActivity,
    TaskAssignment,
    TaskProposal,
    WorkCalendar,
    WorkCalendarDay,
)


now = timezone.now()
active_units = OrganizationUnit.objects.filter(active=True)
active_unit_ids = set(active_units.values_list("id", flat=True))
active_memberships = OrganizationMembership.objects.filter(
    end_date__isnull=True,
    unit_id__in=active_unit_ids,
    user__is_active=True,
)
primary_unit_by_user = dict(
    active_memberships.filter(is_primary=True).values_list("user_id", "unit_id")
)
open_lines = ReportingLine.objects.filter(
    end_date__isnull=True,
    employee__is_active=True,
    supervisor__is_active=True,
)
managed_user_ids = set(open_lines.values_list("employee_id", flat=True))


def iso_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def iso_date(value):
    return value.isoformat() if value else None


def decimal_string(value):
    return str(value) if value is not None else None


def history_common(row):
    return {
        "history_id": row.history_id,
        "record_id": row.id,
        "history_date": iso_datetime(row.history_date),
        "history_type": row.history_type,
        "history_user_source_id": row.history_user_id,
        "history_change_reason": row.history_change_reason or "",
    }


payload = {
    "version": 4,
    "extracted_at": now.isoformat(),
    "users": [
        {
            "source_id": user.id,
            "email": user.email,
            "alias": user.login_alias,
            "name": user.get_full_name() or str(user),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "job_title": user.position,
            "agenda_direction": user.agenda_direction,
            "include_in_direction_agendas": user.include_in_direction_agendas,
            "active": user.is_active,
            "is_it_admin": user.is_it_admin or user.is_superuser,
            "is_dg": (
                user.id not in managed_user_ids
                and not (user.is_it_admin or user.is_superuser)
            ),
            "password_hash": user.password,
        }
        for user in User.objects.filter(is_active=True).order_by("id")
    ],
    "departments": [
        {
            "source_id": unit.id,
            "code": unit.code,
            "name": unit.long_name,
            "short_name": unit.short_name,
            "kind": unit.kind,
            "display_order": unit.display_order,
            "active": unit.active,
        }
        for unit in active_units.order_by("id")
    ],
    "department_links": [
        {
            "source_id": link.id,
            "parent_source_id": link.supervisor_service_id,
            "child_source_id": link.collaborator_service_id,
        }
        for link in OrganizationUnitLink.objects.filter(
            supervisor_service_id__in=active_unit_ids,
            collaborator_service_id__in=active_unit_ids,
        ).order_by("id")
    ],
    "memberships": [
        {
            "source_id": membership.id,
            "user_source_id": membership.user_id,
            "department_source_id": membership.unit_id,
            "job_title": membership.job_title,
            "start_date": membership.start_date.isoformat(),
            "end_date": membership.end_date.isoformat() if membership.end_date else None,
            "is_primary": membership.is_primary,
        }
        for membership in active_memberships.order_by("id")
    ],
    "reporting_lines": [
        {
            "source_id": line.id,
            "employee_source_id": line.employee_id,
            "supervisor_source_id": line.supervisor_id,
            "department_source_id": (
                line.unit_id
                if line.unit_id in active_unit_ids
                else primary_unit_by_user[line.employee_id]
            ),
            "start_date": line.start_date.isoformat(),
            "end_date": line.end_date.isoformat() if line.end_date else None,
            "is_primary": line.is_primary,
        }
        for line in open_lines.order_by("id")
        if line.unit_id in active_unit_ids or line.employee_id in primary_unit_by_user
    ],
    "role_grants": [
        {
            "source_id": grant.id,
            "user_source_id": grant.user_id,
            "department_source_id": grant.unit_id,
            "role_code": grant.role.code,
            "scope": grant.scope,
            "valid_from": iso_datetime(grant.valid_from),
            "valid_until": iso_datetime(grant.valid_until),
            "active": True,
        }
        for grant in RoleGrant.objects.active_at(now)
        .filter(unit_id__in=active_unit_ids)
        .select_related("role")
        .order_by("id")
    ],
    "strategic_plans": [
        {
            "source_id": row.id,
            "name": row.name,
            "start_date": iso_date(row.start_date),
            "end_date": iso_date(row.end_date),
            "active": row.active,
        }
        for row in StrategicPlan.objects.order_by("id")
    ],
    "action_plans": [
        {
            "source_id": row.id,
            "strategic_plan_source_id": row.strategic_plan_id,
            "name": row.name,
            "code": row.code,
            "active": True,
        }
        for row in ActionPlan.objects.order_by("id")
    ],
    "institutional_actions": [
        {
            "source_id": row.id,
            "action_plan_source_id": row.action_plan_id,
            "name": row.name,
            "code": row.code,
            "active": row.active,
        }
        for row in InstitutionalAction.objects.order_by("id")
    ],
    "work_calendars": [
        {
            "source_id": row.id,
            "name": row.name,
            "version": row.version,
            "is_default": row.is_default,
            "active": row.active,
        }
        for row in WorkCalendar.objects.order_by("id")
    ],
    "work_calendar_days": [
        {
            "source_id": row.id,
            "calendar_source_id": row.calendar_id,
            "day": iso_date(row.day),
            "name": row.name,
            "is_working_day": row.is_working_day,
        }
        for row in WorkCalendarDay.objects.order_by("id")
    ],
    "tasks": [
        {
            "source_id": row.id,
            "code": row.code,
            "title": row.title,
            "description": row.description,
            "action_source_id": row.action_id,
            "created_by_source_id": row.created_by_id,
            "created_at": iso_datetime(row.created_at),
            "updated_at": iso_datetime(row.updated_at),
        }
        for row in Task.objects.order_by("id")
    ],
    "task_assignments": [
        {
            "source_id": row.id,
            "task_source_id": row.task_id,
            "employee_source_id": row.employee_id,
            "manager_source_id": row.manager_id,
            "organization_unit_source_id": row.organization_unit_id,
            "calendar_source_id": row.calendar_id,
            "start_date": iso_date(row.start_date),
            "due_date": iso_date(row.due_date),
            "estimated_work_days": decimal_string(row.estimated_work_days),
            "status": row.status,
            "closed_reason": row.closed_reason,
            "completed_at": iso_datetime(row.completed_at),
            "revision": row.revision,
        }
        for row in TaskAssignment.objects.order_by("id")
    ],
    "task_proposals": [
        {
            "source_id": row.id,
            "employee_source_id": row.employee_id,
            "organization_unit_source_id": row.organization_unit_id,
            "title": row.title,
            "description": row.description,
            "action_source_id": row.action_id,
            "calendar_source_id": row.calendar_id,
            "start_date": iso_date(row.start_date),
            "due_date": iso_date(row.due_date),
            "estimated_work_days": decimal_string(row.estimated_work_days),
            "status": row.status,
            "reviewed_by_source_id": row.reviewed_by_id,
            "accepted_assignment_source_id": row.accepted_assignment_id,
            "decision_note": row.decision_note,
            "decided_at": iso_datetime(row.decided_at),
            "revision": row.revision,
            "created_at": iso_datetime(row.created_at),
        }
        for row in TaskProposal.objects.order_by("id")
    ],
    "progress_entries": [
        {
            "source_id": row.id,
            "assignment_source_id": row.assignment_id,
            "entry_date": iso_date(row.entry_date),
            "percentage": row.percentage,
            "note": row.note,
            "blocked": row.blocked,
            "author_source_id": row.author_id,
            "created_at": iso_datetime(row.created_at),
            "updated_at": iso_datetime(row.updated_at),
        }
        for row in ProgressEntry.objects.order_by("id")
    ],
    "task_activities": [
        {
            "source_id": row.id,
            "assignment_source_id": row.assignment_id,
            "kind": row.kind,
            "actor_source_id": row.actor_id,
            "occurred_at": iso_datetime(row.occurred_at),
            "message": row.message,
            "percentage_before": row.percentage_before,
            "percentage_after": row.percentage_after,
            "progress_source_id": row.progress_entry_id,
            "details": row.details,
            "supersedes_source_id": row.supersedes_id,
        }
        for row in TaskActivity.objects.order_by("id")
    ],
    "task_history": [
        {
            **history_common(row),
            "code": row.code,
            "title": row.title,
            "description": row.description,
            "action_source_id": row.action_id,
            "created_by_source_id": row.created_by_id,
            "created_at": iso_datetime(row.created_at),
            "updated_at": iso_datetime(row.updated_at),
        }
        for row in HistoricalTask.objects.order_by("history_date", "history_id")
    ],
    "assignment_history": [
        {
            **history_common(row),
            "task_source_id": row.task_id,
            "employee_source_id": row.employee_id,
            "manager_source_id": row.manager_id,
            "organization_unit_source_id": row.organization_unit_id,
            "calendar_source_id": row.calendar_id,
            "start_date": iso_date(row.start_date),
            "due_date": iso_date(row.due_date),
            "estimated_work_days": decimal_string(row.estimated_work_days),
            "status": row.status,
            "closed_reason": row.closed_reason,
            "completed_at": iso_datetime(row.completed_at),
            "revision": row.revision,
        }
        for row in HistoricalTaskAssignment.objects.order_by("history_date", "history_id")
    ],
    "proposal_history": [
        {
            **history_common(row),
            "employee_source_id": row.employee_id,
            "organization_unit_source_id": row.organization_unit_id,
            "title": row.title,
            "description": row.description,
            "action_source_id": row.action_id,
            "calendar_source_id": row.calendar_id,
            "start_date": iso_date(row.start_date),
            "due_date": iso_date(row.due_date),
            "estimated_work_days": decimal_string(row.estimated_work_days),
            "status": row.status,
            "reviewed_by_source_id": row.reviewed_by_id,
            "accepted_assignment_source_id": row.accepted_assignment_id,
            "decision_note": row.decision_note,
            "decided_at": iso_datetime(row.decided_at),
            "revision": row.revision,
            "created_at": iso_datetime(row.created_at),
        }
        for row in HistoricalTaskProposal.objects.order_by("history_date", "history_id")
    ],
    "progress_history": [
        {
            **history_common(row),
            "assignment_source_id": row.assignment_id,
            "entry_date": iso_date(row.entry_date),
            "percentage": row.percentage,
            "note": row.note,
            "blocked": row.blocked,
            "author_source_id": row.author_id,
            "created_at": iso_datetime(row.created_at),
            "updated_at": iso_datetime(row.updated_at),
        }
        for row in HistoricalProgressEntry.objects.order_by("history_date", "history_id")
    ],
    "visitor_visits": [
        {
            "source_id": row.id,
            "party_size": row.party_size,
            "visitor_names": row.visitor_names,
            "arrived_at": iso_datetime(row.arrived_at),
            "departed_at": iso_datetime(row.departed_at),
            "cancelled_at": iso_datetime(row.cancelled_at),
            "cancellation_reason": row.cancellation_reason,
            "revision": row.revision,
            "recorded_by_source_id": row.recorded_by_id,
            "updated_by_source_id": row.updated_by_id,
        }
        for row in VisitorVisit.objects.order_by("id")
    ],
    "staff_availability": [
        {
            "source_id": row.id,
            "employee_source_id": row.employee_id,
            "kind": row.kind,
            "start_date": iso_date(row.start_date),
            "end_date": iso_date(row.end_date),
            "note": row.note,
            "cancelled_at": iso_datetime(row.cancelled_at),
            "cancellation_reason": row.cancellation_reason,
            "revision": row.revision,
            "recorded_by_source_id": row.recorded_by_id,
            "updated_by_source_id": row.updated_by_id,
        }
        for row in StaffAvailability.objects.order_by("id")
    ],
    "agenda_drafts": [
        {
            "source_id": row.id,
            "period_start": iso_date(row.period_start),
            "period_end": iso_date(row.period_end),
            "major_events": row.major_events,
            "revision": row.revision,
            "updated_by_source_id": row.updated_by_id,
            "updated_at": iso_datetime(row.updated_at),
        }
        for row in AgendaDraft.objects.order_by("id")
    ],
    "agenda_versions": [
        {
            "source_id": row.id,
            "draft_source_id": row.draft_id,
            "period_start": iso_date(row.period_start),
            "period_end": iso_date(row.period_end),
            "agenda_direction": row.agenda_direction,
            "version": row.version,
            "snapshot": row.snapshot,
            "snapshot_sha256": row.snapshot_sha256,
            "pdf_base64": base64.b64encode(agenda_pdf_bytes(row)).decode("ascii"),
            "pdf_sha256": row.pdf_sha256,
            "pdf_size": row.pdf_size,
            "generated_by_source_id": row.generated_by_id,
            "generated_at": iso_datetime(row.generated_at),
        }
        for row in AgendaVersion.objects.order_by("id")
    ],
}

json.dump(payload, sys.stdout, ensure_ascii=True, separators=(",", ":"))
