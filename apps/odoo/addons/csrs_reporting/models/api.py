"""Narrow JSON-serializable CSRS ENT use cases called only through Django."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import unescape
from hashlib import sha256
import json
import re
import secrets
import string

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command, Domain


TAG_RE = re.compile(r"<[^>]+>")
STATUS_LABELS = {
    "planned": "Planifiée",
    "active": "En cours",
    "awaiting_validation": "À valider",
    "completed": "Terminée",
    "closed_early": "Clôturée avant achèvement",
}
PROPOSAL_LABELS = {
    "submitted": "Soumise",
    "rejected": "Rejetée",
    "accepted": "Acceptée",
}
AGENDA_LABELS = {
    "programs": "Direction des programmes",
    "administration": "Direction administrative",
}
ROLE_GROUPS = {
    "AGENDA_HR": "csrs_reporting.group_csrs_hr",
    "AGENDA_SECRETARIAT": "csrs_reporting.group_csrs_secretariat",
    "AGENDA_VIEWER": "csrs_reporting.group_csrs_agent",
    "MISSION_ASSISTANCE": "csrs_reporting.group_csrs_secretariat",
    "MISSION_FLEET": "csrs_reporting.group_csrs_secretariat",
    "MISSION_SECRETARIAT": "csrs_reporting.group_csrs_secretariat",
    "MISSION_SIGNER": "csrs_reporting.group_csrs_dg",
    "UNIT_MANAGER": "csrs_reporting.group_csrs_primary_manager",
    "UNIT_VIEWER": "csrs_reporting.group_csrs_secondary_manager",
}


def _plain_html(value):
    return unescape(TAG_RE.sub(" ", value or "")).strip()


def _iso(value):
    if not value:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return fields.Date.to_date(value) if value else None


def _decimal(value):
    return str(Decimal(str(value or 0)).quantize(Decimal("0.1"), ROUND_HALF_UP))


class CsrsApi(models.AbstractModel):
    _name = "csrs.api"
    _description = "Façade RPC métier CSRS ENT"

    def _require_group(self, *xmlids):
        if not any(self.env.user.has_group(xmlid) for xmlid in xmlids):
            raise AccessError(_("Cette opération n'est pas autorisée."))

    def _require_group_or_global_role(self, xmlids, role_codes):
        if any(self.env.user.has_group(xmlid) for xmlid in xmlids):
            return
        if self.env.user.csrs_has_global_role_grant(*role_codes):
            return
        raise AccessError(_("Cette opération n'est pas autorisée."))

    def _employee_for_user(self, user):
        """Resolve the private HR row only after the use case has scoped the user."""
        return self.env["hr.employee"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            limit=1,
        )

    def _person(self, user):
        employee = self._employee_for_user(user)
        return {
            "id": user.id,
            "name": user.name,
            "position": employee.job_title if employee else "",
            "login_alias": user.csrs_alias or None,
        }

    def _user_state_token(self, user):
        employee = self._employee_for_user(user)
        memberships = self.env["csrs.organization.membership"].sudo().search(
            [("user_id", "=", user.id)], order="id"
        )
        lines = self.env["csrs.reporting.line"].sudo().search(
            ["|", ("employee_id", "=", user.id), ("supervisor_id", "=", user.id)],
            order="id",
        )
        payload = {
            "user": [user.id, _iso(user.write_date), bool(user.active)],
            "employee": [employee.id, _iso(employee.write_date)] if employee else None,
            "memberships": [[item.id, _iso(item.write_date)] for item in memberships],
            "lines": [[item.id, _iso(item.write_date)] for item in lines],
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _check_user_state(self, user, expected):
        if not expected or self._user_state_token(user) != expected:
            raise UserError(_("Ce compte a changé. Rechargez la fiche."))

    @staticmethod
    def _unit_payload(unit):
        return {
            "id": unit.id,
            "code": unit.csrs_code or "",
            "short_name": unit.csrs_short_name or unit.name,
            "long_name": unit.name,
            "label": f"{unit.csrs_code or ''} — {unit.name}".strip(" —"),
        }

    def _user_has_password(self, user):
        self.env.cr.execute("SELECT password FROM res_users WHERE id=%s", [user.id])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _user_summary(self, user):
        employee = self._employee_for_user(user)
        membership = self.env["csrs.organization.membership"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("is_primary", "=", True),
                ("end_date", "=", False),
            ],
            limit=1,
        )
        protected = user.id == self.env.ref("base.user_admin").id
        return {
            **self._person(user),
            "email": user.email or user.login,
            "is_active": bool(user.active),
            "is_superuser": protected,
            "password_change_required": bool(user.csrs_password_change_required),
            "has_usable_password": self._user_has_password(user),
            "primary_unit": self._unit_payload(membership.department_id)
            if membership
            else None,
            "state_token": self._user_state_token(user),
            "batch_capabilities": {
                "deactivate": bool(user.active)
                and user != self.env.user
                and not protected,
                "delete": not user.active
                and not user.csrs_source_id
                and user != self.env.user
                and not protected,
            },
            "position": employee.job_title if employee else "",
        }

    def _user_detail(self, user):
        summary = self._user_summary(user)
        employee = self._employee_for_user(user)
        memberships = self.env["csrs.organization.membership"].sudo().search(
            [("user_id", "=", user.id), ("end_date", "=", False)],
            order="is_primary desc, id",
        )
        primary = memberships.filtered("is_primary")[:1]
        line = self.env["csrs.reporting.line"].sudo().search(
            [
                ("employee_id", "=", user.id),
                ("is_primary", "=", True),
                ("end_date", "=", False),
            ],
            limit=1,
        )
        protected = user.id == self.env.ref("base.user_admin").id
        summary.update(
            {
                "first_name": user.csrs_first_name or "",
                "last_name": user.csrs_last_name or "",
                "phone": user.phone or "",
                "agenda_direction": employee.csrs_agenda_direction
                if employee
                else "",
                "include_in_direction_agendas": bool(
                    employee.csrs_include_in_agenda if employee else True
                ),
                "unit_ids": memberships.department_id.ids,
                "primary_unit_id": primary.department_id.id if primary else None,
                "primary_supervisor": self._person(line.supervisor_id)
                if line
                else None,
                "capabilities": {
                    "deactivate": bool(user.active)
                    and user != self.env.user
                    and not protected,
                    "reactivate": not user.active and not protected,
                    "reset_password": bool(user.active)
                    and user != self.env.user
                    and not protected,
                    "send_activation": False,
                    "edit": not protected or user == self.env.user,
                },
            }
        )
        return summary

    def _period(self, week=None, month=None):
        today = fields.Date.context_today(self)
        if month:
            try:
                year, month_number = (int(part) for part in str(month).split("-", 1))
                start = date(year, month_number, 1)
            except (TypeError, ValueError):
                raise ValidationError(_("Mois invalide.")) from None
            end = date(year, month_number, monthrange(year, month_number)[1])
            previous = (start - timedelta(days=1)).replace(day=1)
            after = end + timedelta(days=1)
            return {
                "kind": "month",
                "label": start.strftime("%m/%Y"),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "query": f"month={start:%Y-%m}",
                "previous_query": f"month={previous:%Y-%m}",
                "next_query": f"month={after:%Y-%m}",
            }
        if week:
            try:
                selected = fields.Date.to_date(week)
            except (TypeError, ValueError):
                raise ValidationError(_("Semaine invalide.")) from None
            start = selected - timedelta(days=selected.weekday())
        else:
            start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return {
            "kind": "week",
            "label": f"du {start:%d/%m/%Y} au {end:%d/%m/%Y}",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "query": f"week={start.isoformat()}",
            "previous_query": f"week={(start - timedelta(days=7)).isoformat()}",
            "next_query": f"week={(start + timedelta(days=7)).isoformat()}",
        }

    def _managed_users(self):
        user = self.env.user
        if user.has_group("csrs_reporting.group_csrs_it"):
            employees = self.env["hr.employee"].sudo().search([("user_id", "!=", False)])
            return employees.user_id
        if user.has_group("csrs_reporting.group_csrs_dg"):
            employees = self.env["hr.employee"].sudo().search(
                [("user_id", "!=", False)]
            )
            return employees.user_id | user
        employee = self._employee_for_user(user)
        direct = self.env["hr.employee"]
        if employee:
            direct = self.env["hr.employee"].sudo().search(
                [("parent_id", "=", employee.id), ("user_id", "!=", False)]
            )
        delegated = self.env["res.users"]
        grants = user.csrs_active_role_grants(("UNIT_MANAGER",))
        for grant in grants:
            operator = "child_of" if grant.scope == "tree" else "="
            delegated |= self.env["hr.employee"].sudo().search(
                [("department_id", operator, grant.department_id.id)]
            ).user_id
        return direct.user_id | delegated

    @api.model
    def api_session(self):
        user = self.env.user
        managed = self._managed_users()
        is_it = user.has_group("csrs_reporting.group_csrs_it")
        is_secretariat = user.has_group(
            "csrs_reporting.group_csrs_secretariat"
        ) or user.csrs_has_global_role_grant("AGENDA_SECRETARIAT")
        is_hr = user.has_group(
            "csrs_reporting.group_csrs_hr"
        ) or user.csrs_has_global_role_grant("AGENDA_HR")
        is_agenda_viewer = user.csrs_has_global_role_grant("AGENDA_VIEWER")
        is_dg = user.has_group("csrs_reporting.group_csrs_dg")
        return {
            "user": self._person(user),
            "capabilities": {
                "create_task": bool(managed) or is_it,
                "create_proposal": True,
                "view_team": bool(managed) or is_dg or is_it,
                "self_assign": is_dg or is_it,
                "admin": is_it,
                "manage_visits": is_secretariat or is_it,
                "manage_availability": is_hr or is_it,
                "prepare_weekly_agenda": is_secretariat or is_it,
                "view_weekly_agenda": is_secretariat
                or is_agenda_viewer
                or is_dg
                or is_it,
                "delete_tasks": is_it,
                "manage_users": is_it,
                "manage_organization": is_it,
                "password_change_required": bool(
                    user.csrs_password_change_required
                ),
            },
        }

    @api.model
    def api_change_password(self, current_password, new_password):
        self.env.user.action_csrs_change_own_password(current_password, new_password)
        return True

    def _task_domain_for_period(self, period):
        return [
            ("csrs_managed", "=", True),
            ("csrs_start_date", "<=", period["end"]),
            ("date_deadline", ">=", period["start"]),
        ]

    def _progress_at(self, task, selected):
        entry = task.csrs_progress_entry_ids.filtered(
            lambda item: item.recorded_at.date() <= selected
        ).sorted("recorded_at")[-1:]
        return entry.progress_percent if entry else 0.0

    def _task_summary(self, task, period=None):
        today = fields.Date.context_today(self)
        total = Decimal(str(task.csrs_estimated_work_days or 0))
        percentage = Decimal(str(task.csrs_progress_percent or 0))
        completed = total * percentage / Decimal("100")
        remaining = max(Decimal("0"), total - completed)
        delta = 0.0
        if period:
            start = fields.Date.to_date(period["start"])
            end = fields.Date.to_date(period["end"])
            delta = self._progress_at(task, end) - self._progress_at(
                task, start - timedelta(days=1)
            )
        latest = task.csrs_progress_entry_ids.sorted("recorded_at", reverse=True)[:1]
        due = _as_date(task.date_deadline) or task.csrs_start_date or today
        if task.csrs_status in {"completed", "closed_early"}:
            deadline_level = "done"
        elif due < today:
            deadline_level = "late"
        elif due <= today + timedelta(days=3):
            deadline_level = "near"
        else:
            deadline_level = "normal"
        employee = task.user_ids[:1] or task.csrs_manager_id
        return {
            "id": task.id,
            "revision": task.csrs_revision,
            "code": task.csrs_code or f"CSRS-ENT-{task.id}",
            "title": task.name,
            "status": task.csrs_status,
            "status_label": STATUS_LABELS.get(task.csrs_status, task.csrs_status),
            "percentage": task.csrs_progress_percent,
            "progress_delta": delta,
            "start_date": _iso(task.csrs_start_date),
            "today": today.isoformat(),
            "due_date": _iso(due),
            "workload": {
                "total": _decimal(total),
                "completed": _decimal(completed),
                "remaining": _decimal(remaining),
            },
            "deadline_level": deadline_level,
            "blocked": task.csrs_blocked,
            "latest_note": latest.observation if latest else "",
            "employee": self._person(employee),
            "manager": self._person(task.csrs_manager_id),
            "action": (
                {"id": task.project_id.id, "label": task.project_id.name}
                if task.project_id
                else None
            ),
        }

    def _task_chart(self, task):
        today = fields.Date.context_today(self)
        start = task.csrs_start_date or today
        due = _as_date(task.date_deadline) or start
        end = max(today, due)
        if (end - start).days > 730:
            end = start + timedelta(days=730)
        entries = {entry.recorded_at.date(): entry for entry in task.csrs_progress_entry_ids}
        latest = 0.0
        points = []
        current = start
        while current <= end:
            entry = entries.get(current)
            if entry:
                latest = entry.progress_percent
            elapsed = max(0, (min(current, due) - start).days + 1)
            planned = max(1, (due - start).days + 1)
            points.append(
                {
                    "task_id": task.id,
                    "start_date": start.isoformat(),
                    "day": current.isoformat(),
                    "is_working_day": current.weekday() < 5,
                    "due_date": due.isoformat(),
                    "planned_work_days": planned,
                    "elapsed_work_days": elapsed,
                    "remaining_schedule_days": max(0, (due - current).days),
                    "overdue_days": max(0, (current - due).days),
                    "percentage": latest,
                    "observed": bool(entry),
                }
            )
            current += timedelta(days=1)
        return points

    def _task_activities(self, task):
        activities = []
        for entry in task.csrs_progress_entry_ids:
            activities.append(
                {
                    "id": entry.id * 2,
                    "kind": "progress",
                    "message": entry.observation or _("Progression mise à jour."),
                    "occurred_at": _iso(entry.recorded_at),
                    "actor": self._person(entry.author_id),
                    "actor_short_name": entry.author_id.name,
                    "percentage_before": entry.previous_progress_percent,
                    "percentage_after": entry.progress_percent,
                }
            )
        for message in task.message_ids.filtered(lambda item: item.message_type == "comment"):
            author = message.author_id.user_ids[:1] or task.csrs_manager_id
            activities.append(
                {
                    "id": message.id * 2 + 1,
                    "kind": "observation",
                    "message": _plain_html(message.body),
                    "occurred_at": _iso(message.date),
                    "actor": self._person(author),
                    "actor_short_name": author.name,
                    "percentage_before": None,
                    "percentage_after": None,
                }
            )
        return sorted(activities, key=lambda item: item["occurred_at"], reverse=True)

    def _task_detail(self, task):
        task.ensure_one()
        summary = self._task_summary(task)
        is_admin = task._csrs_is_admin()
        manage = task.csrs_manager_id == self.env.user or is_admin
        comment = (
            self.env.user in task.user_ids
            or manage
            or self.env.user in task.csrs_secondary_manager_user_ids
        )
        summary.update(
            {
                "description": _plain_html(task.description),
                "estimated_work_days": _decimal(task.csrs_estimated_work_days),
                "calendar": {
                    "id": task.csrs_calendar_id.id,
                    "label": task.csrs_calendar_id.name,
                },
                "chart": self._task_chart(task),
                "activities": self._task_activities(task),
                "capabilities": {
                    "manage": manage,
                    "comment": comment,
                    "update_progress": self.env.user in task.user_ids or manage,
                    "self_managed": task.csrs_manager_id in task.user_ids,
                },
            }
        )
        return summary

    @api.model
    def api_dashboard(self, week=None, month=None):
        period = self._period(week, month)
        tasks = self.env["project.task"].search(
            self._task_domain_for_period(period)
            + [("user_ids", "in", [self.env.user.id])],
            order="date_deadline, name",
        )
        return {
            "period": period,
            "today": fields.Date.context_today(self).isoformat(),
            "tasks": [self._task_summary(task, period) for task in tasks],
        }

    @api.model
    def api_planning_options(self):
        managed = self._managed_users()
        if self.env.user.has_group("csrs_reporting.group_csrs_dg"):
            managed |= self.env.user
        calendar = self.env.company.resource_calendar_id
        today = fields.Date.context_today(self)
        due = calendar.plan_hours(
            calendar.hours_per_day,
            datetime.combine(today, time.min, tzinfo=timezone.utc),
        )
        return {
            "employees": [self._person(user) for user in managed.sorted("name")],
            "actions": [
                {"id": project.id, "label": project.name}
                for project in self.env["project.project"].search([], order="name")
            ],
            "calendars": [
                {"id": item.id, "label": item.name}
                for item in self.env["resource.calendar"].search([], order="name")
            ],
            "defaults": {
                "calendar_id": calendar.id,
                "start_date": today.isoformat(),
                "due_date": (due.date() if due else today).isoformat(),
                "estimated_work_days": "1.0",
            },
        }

    @api.model
    def api_planning_preview(self, payload):
        calendar = self.env["resource.calendar"].browse(int(payload["calendar_id"])).exists()
        if not calendar:
            raise ValidationError(_("Calendrier introuvable."))
        start = fields.Date.to_date(payload["start_date"])
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        source = payload.get("source", "workload")
        if source == "due":
            due = fields.Date.to_date(payload["due_date"])
            if due < start:
                raise ValidationError(_("La fin prévue doit suivre le début."))
            duration = calendar.get_work_duration_data(
                start_dt,
                datetime.combine(due, time.max, tzinfo=timezone.utc),
                compute_leaves=True,
            )["days"]
            workload = max(0.1, float(duration))
        else:
            workload = float(payload["estimated_work_days"])
            if workload <= 0:
                raise ValidationError(_("La charge estimée doit être positive."))
            planned = calendar.plan_hours(
                workload * calendar.hours_per_day,
                start_dt,
                compute_leaves=True,
            )
            if not planned:
                raise ValidationError(_("La date de fin n'a pas pu être calculée."))
            due = planned.date()
        return {
            "start_date": start.isoformat(),
            "due_date": due.isoformat(),
            "estimated_work_days": _decimal(workload),
        }

    @api.model
    def api_task(self, task_id):
        task = self.env["project.task"].browse(int(task_id)).exists()
        if not task or not task.csrs_managed:
            raise UserError(_("Tâche introuvable."))
        task.check_access("read")
        return self._task_detail(task)

    @api.model
    def api_task_create(self, payload):
        employee = self.env["res.users"].browse(int(payload["employee_id"])).exists()
        if not employee or employee not in self._managed_users():
            raise AccessError(_("Ce collaborateur n'est pas dans votre périmètre."))
        task = self.env["project.task"].create(
            {
                "name": str(payload["title"]).strip(),
                "description": str(payload["description"]).strip(),
                "project_id": int(payload.get("action_id") or 0),
                "user_ids": [Command.set(employee.ids)],
                "csrs_managed": True,
                "csrs_manager_id": self.env.user.id,
                "csrs_calendar_id": int(payload["calendar_id"]),
                "csrs_start_date": payload["start_date"],
                "date_deadline": payload["due_date"],
                "csrs_estimated_work_days": float(payload["estimated_work_days"]),
            }
        )
        return self._task_detail(task)

    @api.model
    def api_task_update(self, task_id, payload):
        task = self.env["project.task"].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("Tâche introuvable."))
        if not task._csrs_can_manage():
            raise AccessError(_("Seul le responsable principal peut modifier la tâche."))
        task._csrs_check_revision(payload.get("revision"))
        task.with_context(csrs_authorized_mutation=True).write(
            {
                "name": str(payload["title"]).strip(),
                "description": str(payload["description"]).strip(),
                "project_id": int(payload.get("action_id") or 0),
                "csrs_start_date": payload["start_date"],
                "date_deadline": payload["due_date"],
                "csrs_estimated_work_days": float(payload["estimated_work_days"]),
                "csrs_revision": task.csrs_revision + 1,
            }
        )
        return self._task_detail(task)

    @api.model
    def api_task_progress(self, task_id, payload):
        task = self.env["project.task"].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("Tâche introuvable."))
        task.action_csrs_record_progress(
            float(payload["percentage"]),
            str(payload.get("note") or ""),
            bool(payload.get("blocked")),
            payload.get("revision"),
        )
        return self._task_detail(task)

    @api.model
    def api_task_comment(self, task_id, payload):
        task = self.env["project.task"].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("Tâche introuvable."))
        task._csrs_check_revision(payload.get("revision"))
        task.action_csrs_comment(str(payload.get("message") or ""))
        task.with_context(csrs_authorized_mutation=True).write(
            {"csrs_revision": task.csrs_revision + 1}
        )
        return self._task_detail(task)

    @api.model
    def api_task_transition(self, task_id, payload):
        task = self.env["project.task"].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("Tâche introuvable."))
        transition = payload.get("transition")
        if transition == "validate":
            task.action_csrs_validate_completion(payload.get("revision"))
        elif transition == "reject":
            task.action_csrs_request_rework(
                payload.get("reason"), payload.get("revision")
            )
        elif transition == "close_early":
            task.action_csrs_close_early(
                payload.get("reason"), payload.get("revision")
            )
        else:
            raise ValidationError(_("Transition invalide."))
        return self._task_detail(task)

    @api.model
    def api_task_management(
        self, query="", status="", employee_id=None, page=1, page_size=50
    ):
        self._require_group("csrs_reporting.group_csrs_it")
        domain = Domain("csrs_managed", "=", True)
        query = str(query or "").strip()
        if query:
            domain &= (
                Domain("csrs_code", "ilike", query)
                | Domain("name", "ilike", query)
                | Domain("user_ids.name", "ilike", query)
            )
        if status:
            if status not in STATUS_LABELS:
                raise ValidationError(_("Statut de tâche invalide."))
            domain &= Domain("csrs_status", "=", status)
        if employee_id:
            domain &= Domain("user_ids", "in", [int(employee_id)])
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 50)))
        Task = self.env["project.task"].sudo()
        total = Task.search_count(domain)
        tasks = Task.search(
            domain,
            order="csrs_code, id",
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        employee_users = Task.search(
            [("csrs_managed", "=", True)]
        ).mapped("user_ids")
        return {
            "items": [
                {
                    "id": task.id,
                    "task_id": task.id,
                    "revision": task.csrs_revision,
                    "code": task.csrs_code or "",
                    "title": task.name,
                    "status": task.csrs_status,
                    "status_label": STATUS_LABELS[task.csrs_status],
                    "percentage": task.csrs_progress_percent,
                    "start_date": _iso(task.csrs_start_date),
                    "due_date": _iso(task.date_deadline),
                    "employee": self._person(task.user_ids[:1] or task.csrs_manager_id),
                    "manager": self._person(task.csrs_manager_id),
                }
                for task in tasks
            ],
            "total": total,
            "page": page,
            "pages": max(1, (total + page_size - 1) // page_size),
            "page_size": page_size,
            "employees": [
                self._person(user) for user in employee_users.sorted("name")
            ],
        }

    @api.model
    def api_task_bulk_delete(self, selections, reason):
        self._require_group("csrs_reporting.group_csrs_it")
        reason = str(reason or "").strip()
        if len(reason) < 3:
            raise ValidationError(_("Le motif de suppression est obligatoire."))
        if not isinstance(selections, list) or not 1 <= len(selections) <= 100:
            raise ValidationError(_("Sélection de tâches invalide."))
        ids = [int(item.get("id", 0)) for item in selections if isinstance(item, dict)]
        if len(ids) != len(selections) or len(set(ids)) != len(ids):
            raise ValidationError(_("Sélection de tâches invalide."))
        tasks = self.env["project.task"].sudo().browse(ids).exists()
        if len(tasks) != len(ids) or any(not task.csrs_managed for task in tasks):
            raise UserError(_("Tâche introuvable."))
        expected = {int(item["id"]): int(item.get("revision", 0)) for item in selections}
        for task in tasks:
            task._csrs_check_revision(expected[task.id])
        snapshot = [
            {
                "id": task.id,
                "code": task.csrs_code,
                "title": task.name,
                "revision": task.csrs_revision,
                "status": task.csrs_status,
                "percentage": task.csrs_progress_percent,
                "employee_ids": task.user_ids.ids,
                "manager_id": task.csrs_manager_id.id,
                "start_date": _iso(task.csrs_start_date),
                "due_date": _iso(task.date_deadline),
            }
            for task in tasks
        ]
        audit = self.env["csrs.audit.event"].sudo().create(
            {
                "event_type": "task_bulk_delete",
                "actor_id": self.env.user.id,
                "reason": reason,
                "snapshot": snapshot,
            }
        )
        proposals = self.env["csrs.task.proposal"].sudo().search(
            [("accepted_task_id", "in", tasks.ids)]
        )
        if proposals:
            proposals.with_context(csrs_authorized_mutation=True).write(
                {"accepted_task_id": False}
            )
        tasks.unlink()
        return {
            "audit_id": audit.id,
            "deleted_assignments": len(ids),
            "deleted_tasks": len(ids),
        }

    def _user_write_values(self, payload, user=None):
        email = str(payload.get("email") or "").strip().lower()
        alias = str(payload.get("login_alias") or "").strip().lower()
        first_name = str(payload.get("first_name") or "").strip()
        last_name = str(payload.get("last_name") or "").strip()
        if not email or "@" not in email or len(email) > 254:
            raise ValidationError(_("Adresse email invalide."))
        if alias and not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", alias):
            raise ValidationError(_("Identifiant court invalide."))
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        collisions = Users.search(
            Domain("login", "=ilike", email)
            | Domain("email", "=ilike", email)
            | Domain("csrs_alias", "=ilike", email)
        )
        if user:
            collisions -= user
        if collisions:
            raise ValidationError(_("Cette adresse email est déjà utilisée."))
        if alias:
            alias_collisions = Users.search(
                Domain("login", "=ilike", alias)
                | Domain("email", "=ilike", alias)
                | Domain("csrs_alias", "=ilike", alias)
            )
            if user:
                alias_collisions -= user
            if alias_collisions:
                raise ValidationError(_("Cet identifiant court est déjà utilisé."))
        name = " ".join(part for part in (first_name, last_name) if part) or email
        return {
            "name": name,
            "login": email,
            "email": email,
            "phone": str(payload.get("phone") or "").strip() or False,
            "csrs_alias": alias or False,
            "csrs_first_name": first_name or False,
            "csrs_last_name": last_name or False,
        }

    def _sync_user_organization(self, user, employee, payload):
        effective = fields.Date.to_date(payload["organization_effective_date"])
        unit_ids = [int(value) for value in payload.get("unit_ids", [])]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValidationError(_("Une unité ne peut apparaître qu'une fois."))
        primary_id = int(payload["primary_unit_id"]) if payload.get("primary_unit_id") else None
        if primary_id and primary_id not in unit_ids:
            raise ValidationError(_("L'unité principale doit être sélectionnée."))
        Department = self.env["hr.department"].sudo().with_context(active_test=False)
        departments = Department.browse(unit_ids).exists()
        if len(departments) != len(unit_ids) or any(not item.active for item in departments):
            raise ValidationError(_("Une unité sélectionnée est introuvable ou inactive."))
        Membership = self.env["csrs.organization.membership"].sudo().with_context(
            active_test=False
        )
        current = Membership.search(
            [("user_id", "=", user.id), ("end_date", "=", False)]
        )
        desired = {unit_id: unit_id == primary_id for unit_id in unit_ids}
        kept = set()
        for membership in current:
            expected_primary = desired.get(membership.department_id.id)
            if expected_primary is not None and membership.is_primary == expected_primary:
                kept.add(membership.department_id.id)
                continue
            membership.write({"end_date": effective, "active": False})
        for unit_id, is_primary in desired.items():
            if unit_id in kept:
                continue
            Membership.create(
                {
                    "user_id": user.id,
                    "department_id": unit_id,
                    "job_title": str(payload.get("position") or "").strip() or False,
                    "start_date": effective,
                    "is_primary": is_primary,
                    "active": True,
                }
            )
        supervisor_id = (
            int(payload["primary_supervisor_id"])
            if payload.get("primary_supervisor_id")
            else None
        )
        if supervisor_id == user.id:
            raise ValidationError(_("Une personne ne peut pas être son propre responsable."))
        supervisor = self.env["res.users"].sudo().browse(supervisor_id).exists()
        supervisor_employee = self._employee_for_user(supervisor) if supervisor else False
        if supervisor_id and (not supervisor or not supervisor_employee or not supervisor.active):
            raise ValidationError(_("Responsable principal invalide."))
        ancestor = supervisor_employee
        while ancestor:
            if ancestor == employee:
                raise ValidationError(_("Ce rattachement créerait une boucle hiérarchique."))
            ancestor = ancestor.parent_id
        ReportingLine = self.env["csrs.reporting.line"].sudo().with_context(
            active_test=False
        )
        current_line = ReportingLine.search(
            [
                ("employee_id", "=", user.id),
                ("is_primary", "=", True),
                ("end_date", "=", False),
            ],
            limit=1,
        )
        old_manager = current_line.supervisor_id if current_line else employee.parent_id.user_id
        if current_line and current_line.supervisor_id.id != supervisor_id:
            current_line.write({"end_date": effective, "active": False})
        if supervisor and (not current_line or current_line.supervisor_id != supervisor):
            if not primary_id:
                raise ValidationError(_("Choisissez une unité principale avant le responsable."))
            ReportingLine.create(
                {
                    "employee_id": user.id,
                    "supervisor_id": supervisor.id,
                    "department_id": primary_id,
                    "start_date": effective,
                    "is_primary": True,
                    "active": True,
                }
            )
        employee.write(
            {
                "name": user.name,
                "work_email": user.email,
                "work_phone": user.phone or False,
                "job_title": str(payload.get("position") or "").strip() or False,
                "department_id": primary_id or False,
                "parent_id": supervisor_employee.id if supervisor_employee else False,
                "csrs_agenda_direction": payload.get("agenda_direction") or False,
                "csrs_include_in_agenda": bool(
                    payload.get("include_in_direction_agendas", True)
                ),
            }
        )
        if old_manager and old_manager != supervisor:
            tasks = self.env["project.task"].sudo().search(
                [
                    ("csrs_managed", "=", True),
                    ("user_ids", "in", [user.id]),
                    ("csrs_manager_id", "=", old_manager.id),
                    ("csrs_status", "not in", ["completed", "closed_early"]),
                ]
            )
            for task in tasks:
                task.with_context(csrs_authorized_mutation=True).write(
                    {
                        "csrs_manager_id": supervisor.id if supervisor else False,
                        "csrs_revision": task.csrs_revision + 1,
                    }
                )

    @api.model
    def api_user_options(self):
        self._require_group("csrs_reporting.group_csrs_it")
        departments = self.env["hr.department"].sudo().search(
            [("active", "=", True)], order="csrs_display_order, name"
        )
        users = self.env["res.users"].sudo().with_context(active_test=False).search(
            [("active", "=", True), ("share", "=", False)], order="name"
        )
        return {
            "today": fields.Date.context_today(self).isoformat(),
            "units": [self._unit_payload(unit) for unit in departments],
            "users": [self._person(user) for user in users if self._employee_for_user(user)],
            "agenda_directions": [
                {"value": value, "label": label}
                for value, label in AGENDA_LABELS.items()
            ],
        }

    @api.model
    def api_users(self, query="", state="", unit_id=None, page=1, page_size=50):
        self._require_group("csrs_reporting.group_csrs_it")
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        users = Users.search([("share", "=", False)], order="name")
        users = users.filtered(lambda item: bool(self._employee_for_user(item)))
        normalized = str(query or "").strip().casefold()
        if normalized:
            users = users.filtered(
                lambda item: normalized
                in " ".join(
                    [
                        item.name or "",
                        item.email or "",
                        item.login or "",
                        item.csrs_alias or "",
                        self._employee_for_user(item).job_title or "",
                    ]
                ).casefold()
            )
        if state == "active":
            users = users.filtered("active")
        elif state == "inactive":
            users = users.filtered(lambda item: not item.active)
        elif state:
            raise ValidationError(_("État de compte invalide."))
        if unit_id:
            member_ids = self.env["csrs.organization.membership"].sudo().search(
                [("department_id", "=", int(unit_id)), ("end_date", "=", False)]
            ).user_id.ids
            users = users.filtered(lambda item: item.id in member_ids)
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 50)))
        total = len(users)
        selected = users[(page - 1) * page_size : page * page_size]
        return {
            "items": [self._user_summary(user) for user in selected],
            "total": total,
            "page": page,
            "pages": max(1, (total + page_size - 1) // page_size),
            "page_size": page_size,
        }

    @api.model
    def api_user(self, user_id):
        self._require_group("csrs_reporting.group_csrs_it")
        user = self.env["res.users"].sudo().with_context(active_test=False).browse(
            int(user_id)
        ).exists()
        if not user or not self._employee_for_user(user):
            raise UserError(_("Compte introuvable."))
        return self._user_detail(user)

    @api.model
    def api_user_create(self, payload):
        self._require_group("csrs_reporting.group_csrs_it")
        values = self._user_write_values(payload)
        internal_group = self.env.ref("base.group_user")
        agent_group = self.env.ref("csrs_reporting.group_csrs_agent")
        values.update(
            {
                "active": True,
                "group_ids": [
                    Command.link(internal_group.id),
                    Command.link(agent_group.id),
                ],
                "csrs_password_change_required": True,
            }
        )
        user = self.env["res.users"].sudo().with_context(
            no_reset_password=True, tracking_disable=True, mail_create_nolog=True
        ).create(values)
        employee = self.env["hr.employee"].sudo().create(
            {"name": user.name, "user_id": user.id, "work_email": user.email}
        )
        self._sync_user_organization(user, employee, payload)
        return self._user_detail(user)

    @api.model
    def api_user_update(self, user_id, payload):
        self._require_group("csrs_reporting.group_csrs_it")
        user = self.env["res.users"].sudo().with_context(active_test=False).browse(
            int(user_id)
        ).exists()
        if not user or not self._employee_for_user(user):
            raise UserError(_("Compte introuvable."))
        if user.id == self.env.ref("base.user_admin").id and user != self.env.user:
            raise AccessError(_("Le compte administrateur protégé ne peut pas être modifié."))
        self._check_user_state(user, payload.get("state_token"))
        user.write(self._user_write_values(payload, user))
        self._sync_user_organization(user, self._employee_for_user(user), payload)
        self.env["csrs.audit.event"].sudo().create(
            {
                "event_type": "organization_change",
                "actor_id": self.env.user.id,
                "reason": "Mise à jour de la fiche utilisateur",
                "snapshot": {"user_id": user.id},
            }
        )
        return self._user_detail(user)

    @api.model
    def api_user_set_active(self, user_id, expected_token, active):
        self._require_group("csrs_reporting.group_csrs_it")
        user = self.env["res.users"].sudo().with_context(active_test=False).browse(
            int(user_id)
        ).exists()
        if not user or not self._employee_for_user(user):
            raise UserError(_("Compte introuvable."))
        if user == self.env.user or user.id == self.env.ref("base.user_admin").id:
            raise AccessError(_("Ce compte ne peut pas être désactivé."))
        self._check_user_state(user, expected_token)
        user.write({"active": bool(active)})
        self._employee_for_user(user).write({"active": bool(active)})
        return self._user_detail(user)

    @api.model
    def api_user_temporary_password(self, user_id, expected_token):
        self._require_group("csrs_reporting.group_csrs_it")
        user = self.env["res.users"].sudo().with_context(active_test=False).browse(
            int(user_id)
        ).exists()
        if (
            not user
            or not user.active
            or user == self.env.user
            or user.id == self.env.ref("base.user_admin").id
        ):
            raise UserError(_("Ce mot de passe ne peut pas être réinitialisé."))
        self._check_user_state(user, expected_token)
        alphabet = string.ascii_letters + string.digits + "!@#%+-_"
        password = "".join(secrets.choice(alphabet) for _ in range(20))
        user.with_context(no_reset_password=True).write(
            {"password": password, "csrs_password_change_required": True}
        )
        return {
            "temporary_password": password,
            "state_token": self._user_state_token(user),
        }

    def _user_can_be_deleted(self, user):
        if user.active or user.csrs_source_id or user == self.env.user:
            return False
        checks = (
            self.env["csrs.organization.membership"].sudo().search_count(
                [("user_id", "=", user.id)], limit=1
            ),
            self.env["csrs.reporting.line"].sudo().search_count(
                ["|", ("employee_id", "=", user.id), ("supervisor_id", "=", user.id)],
                limit=1,
            ),
            self.env["csrs.role.grant"].sudo().search_count(
                [("user_id", "=", user.id)], limit=1
            ),
            self.env["project.task"].sudo().search_count(
                ["|", ("user_ids", "in", [user.id]), ("csrs_manager_id", "=", user.id)],
                limit=1,
            ),
            self.env["csrs.task.proposal"].sudo().search_count(
                ["|", ("author_id", "=", user.id), ("manager_id", "=", user.id)],
                limit=1,
            ),
        )
        return not any(checks)

    @api.model
    def api_user_bulk_action(self, action, selections, reason=""):
        self._require_group("csrs_reporting.group_csrs_it")
        if action not in {"deactivate", "delete"}:
            raise ValidationError(_("Action groupée invalide."))
        if not isinstance(selections, list) or not 1 <= len(selections) <= 100:
            raise ValidationError(_("Sélection de comptes invalide."))
        ids = [int(item.get("id", 0)) for item in selections if isinstance(item, dict)]
        if len(ids) != len(selections) or len(set(ids)) != len(ids):
            raise ValidationError(_("Sélection de comptes invalide."))
        users = self.env["res.users"].sudo().with_context(active_test=False).browse(ids).exists()
        if len(users) != len(ids):
            raise UserError(_("Compte introuvable."))
        tokens = {int(item["id"]): item.get("state_token") for item in selections}
        for user in users:
            self._check_user_state(user, tokens[user.id])
        if action == "deactivate":
            for user in users:
                if not user.active or user == self.env.user or user.id == self.env.ref("base.user_admin").id:
                    raise AccessError(_("Un compte sélectionné ne peut pas être désactivé."))
            users.write({"active": False})
            self.env["hr.employee"].sudo().search(
                [("user_id", "in", users.ids)]
            ).write({"active": False})
            return {"action": action, "affected": len(users)}
        reason = str(reason or "").strip()
        if len(reason) < 3:
            raise ValidationError(_("Le motif de suppression est obligatoire."))
        if any(not self._user_can_be_deleted(user) for user in users):
            raise AccessError(_("Un compte sélectionné doit être inactif, natif et sans historique."))
        audit = self.env["csrs.audit.event"].sudo().create(
            {
                "event_type": "user_delete",
                "actor_id": self.env.user.id,
                "reason": reason,
                "snapshot": [{"id": user.id, "login": user.login} for user in users],
            }
        )
        employees = self.env["hr.employee"].sudo().with_context(active_test=False).search(
            [("user_id", "in", users.ids)]
        )
        employees.unlink()
        users.unlink()
        return {"action": action, "affected": len(ids), "audit_id": audit.id}

    def _department_state_token(self, department):
        payload = [
            department.id,
            _iso(department.write_date),
            department.parent_id.id or None,
            bool(department.active),
        ]
        return sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()

    def _department_detail(self, department):
        return {
            **self._unit_payload(department),
            "kind": department.csrs_kind or "unit",
            "display_order": department.csrs_display_order,
            "active": bool(department.active),
            "parent_id": department.parent_id.id or None,
            "state_token": self._department_state_token(department),
        }

    def _department_values(self, payload, department=None):
        code = str(payload.get("code") or "").strip().upper()
        short_name = str(payload.get("short_name") or "").strip()
        long_name = str(payload.get("long_name") or "").strip()
        kind = str(payload.get("kind") or "unit").strip()
        if not re.fullmatch(r"[A-Z0-9_-]{1,32}", code):
            raise ValidationError(_("Code d'unité invalide."))
        if not short_name or not long_name:
            raise ValidationError(_("Les noms court et long sont obligatoires."))
        Department = self.env["hr.department"].sudo().with_context(active_test=False)
        collision = Department.search([("csrs_code", "=ilike", code)], limit=1)
        if collision and collision != department:
            raise ValidationError(_("Ce code d'unité est déjà utilisé."))
        parent_id = int(payload["parent_id"]) if payload.get("parent_id") else False
        parent = Department.browse(parent_id).exists()
        if parent_id and (not parent or not parent.active):
            raise ValidationError(_("Unité parente invalide."))
        if department and parent:
            ancestor = parent
            while ancestor:
                if ancestor == department:
                    raise ValidationError(_("Cette hiérarchie créerait un cycle."))
                ancestor = ancestor.parent_id
        return {
            "name": long_name,
            "csrs_code": code,
            "csrs_short_name": short_name,
            "csrs_kind": kind,
            "csrs_display_order": int(payload.get("display_order") or 0),
            "parent_id": parent_id,
            "active": bool(payload.get("active", True)),
        }

    def _grant_payload(self, grant):
        return {
            "id": grant.id,
            "user": self._person(grant.user_id),
            "department": self._unit_payload(grant.department_id),
            "role_code": grant.role_code,
            "scope": grant.scope,
            "valid_from": _iso(grant.valid_from),
            "valid_until": _iso(grant.valid_until),
            "active": bool(grant.active),
            "grant_reason": grant.grant_reason or "",
            "revoke_reason": grant.revoke_reason or "",
        }

    @api.model
    def api_organization(self):
        self._require_group("csrs_reporting.group_csrs_it")
        departments = self.env["hr.department"].sudo().with_context(
            active_test=False
        ).search([], order="csrs_display_order, name")
        grants = self.env["csrs.role.grant"].sudo().with_context(
            active_test=False
        ).search([], order="active desc, valid_from desc")
        return {
            "units": [self._department_detail(item) for item in departments],
            "grants": [self._grant_payload(item) for item in grants],
            "role_codes": [
                {"value": code, "label": code.replace("_", " ").title()}
                for code in ROLE_GROUPS
            ],
            "users": [
                self._person(item)
                for item in self.env["res.users"].sudo().search(
                    [("active", "=", True), ("share", "=", False)], order="name"
                )
                if self._employee_for_user(item)
            ],
        }

    @api.model
    def api_organization_unit_create(self, payload):
        self._require_group("csrs_reporting.group_csrs_it")
        unit = self.env["hr.department"].sudo().create(
            self._department_values(payload)
        )
        return self._department_detail(unit)

    @api.model
    def api_organization_unit_update(self, unit_id, payload):
        self._require_group("csrs_reporting.group_csrs_it")
        unit = self.env["hr.department"].sudo().with_context(active_test=False).browse(
            int(unit_id)
        ).exists()
        if not unit:
            raise UserError(_("Unité introuvable."))
        if self._department_state_token(unit) != payload.get("state_token"):
            raise UserError(_("Cette unité a changé. Rechargez l'organigramme."))
        unit.write(self._department_values(payload, unit))
        self.env["csrs.audit.event"].sudo().create(
            {
                "event_type": "organization_change",
                "actor_id": self.env.user.id,
                "reason": str(payload.get("reason") or "Mise à jour d'une unité").strip(),
                "snapshot": {"unit_id": unit.id},
            }
        )
        return self._department_detail(unit)

    @api.model
    def api_role_grant_create(self, payload):
        self._require_group("csrs_reporting.group_csrs_it")
        role_code = str(payload.get("role_code") or "")
        if role_code not in ROLE_GROUPS:
            raise ValidationError(_("Rôle délégué invalide."))
        reason = str(payload.get("reason") or "").strip()
        if len(reason) < 3:
            raise ValidationError(_("Le motif d'attribution est obligatoire."))
        user = self.env["res.users"].sudo().browse(int(payload.get("user_id") or 0)).exists()
        department = self.env["hr.department"].sudo().browse(
            int(payload.get("department_id") or 0)
        ).exists()
        if not user or not department or not user.active or not department.active:
            raise ValidationError(_("Compte ou unité invalide."))
        scope = payload.get("scope")
        if scope not in {"unit", "tree"}:
            raise ValidationError(_("Portée de délégation invalide."))
        grant = self.env["csrs.role.grant"].sudo().create(
            {
                "user_id": user.id,
                "department_id": department.id,
                "role_code": role_code,
                "scope": scope,
                "valid_from": fields.Datetime.to_datetime(payload["valid_from"]),
                "valid_until": fields.Datetime.to_datetime(payload["valid_until"])
                if payload.get("valid_until")
                else False,
                "active": True,
                "granted_by_id": self.env.user.id,
                "grant_reason": reason,
            }
        )
        return self._grant_payload(grant)

    @api.model
    def api_role_grant_revoke(self, grant_id, reason):
        self._require_group("csrs_reporting.group_csrs_it")
        grant = self.env["csrs.role.grant"].sudo().browse(int(grant_id)).exists()
        if not grant or not grant.active:
            raise UserError(_("Délégation active introuvable."))
        grant.with_user(self.env.user).action_revoke(reason)
        return self._grant_payload(grant)

    def _proposal_payload(self, proposal):
        review = proposal.manager_id == self.env.user and proposal.state == "submitted"
        return {
            "id": proposal.id,
            "revision": proposal.revision,
            "title": proposal.title,
            "description": proposal.description,
            "status": proposal.state,
            "status_label": PROPOSAL_LABELS[proposal.state],
            "start_date": _iso(proposal.start_date),
            "due_date": _iso(proposal.due_date),
            "estimated_work_days": _decimal(proposal.estimated_work_days),
            "action": (
                {"id": proposal.project_id.id, "label": proposal.project_id.name}
                if proposal.project_id
                else None
            ),
            "calendar": {
                "id": proposal.calendar_id.id,
                "label": proposal.calendar_id.name,
            },
            "employee": self._person(proposal.author_id),
            "accepted_assignment_id": proposal.accepted_task_id.id or None,
            "decision_note": proposal.decision_note or "",
            "created_at": _iso(proposal.create_date),
            "can_review": review,
            "capabilities": {
                "edit": proposal.author_id == self.env.user
                and proposal.state in {"submitted", "rejected"},
                "resubmit": proposal.author_id == self.env.user
                and proposal.state == "rejected",
                "review": review,
            },
        }

    @api.model
    def api_proposals(self):
        records = self.env["csrs.task.proposal"].search(
            Domain("author_id", "=", self.env.user.id)
            | Domain("manager_id", "=", self.env.user.id),
            order="create_date desc",
        )
        own = records.filtered(lambda item: item.author_id == self.env.user)
        reviewable = records.filtered(
            lambda item: item.manager_id == self.env.user and item.state == "submitted"
        )
        read_only = records - own - reviewable
        return {
            "own": [self._proposal_payload(item) for item in own],
            "reviewable": [self._proposal_payload(item) for item in reviewable],
            "read_only": [self._proposal_payload(item) for item in read_only],
        }

    @api.model
    def api_proposal(self, proposal_id):
        proposal = self.env["csrs.task.proposal"].browse(int(proposal_id)).exists()
        if not proposal:
            raise UserError(_("Proposition introuvable."))
        proposal.check_access("read")
        return self._proposal_payload(proposal)

    @api.model
    def api_proposal_create(self, payload):
        proposal = self.env["csrs.task.proposal"].create(
            {
                "title": str(payload["title"]).strip(),
                "description": str(payload["description"]).strip(),
                "project_id": int(payload.get("action_id") or 0),
                "calendar_id": int(payload["calendar_id"]),
                "start_date": payload["start_date"],
                "due_date": payload["due_date"],
                "estimated_work_days": float(payload["estimated_work_days"]),
            }
        )
        return self._proposal_payload(proposal)

    @api.model
    def api_proposal_update(self, proposal_id, payload):
        proposal = self.env["csrs.task.proposal"].browse(int(proposal_id)).exists()
        if not proposal:
            raise UserError(_("Proposition introuvable."))
        proposal.action_csrs_update(payload, payload.get("revision"))
        return self._proposal_payload(proposal)

    @api.model
    def api_proposal_resubmit(self, proposal_id, revision):
        proposal = self.env["csrs.task.proposal"].browse(int(proposal_id)).exists()
        if not proposal:
            raise UserError(_("Proposition introuvable."))
        proposal.action_csrs_resubmit(revision)
        return self._proposal_payload(proposal)

    @api.model
    def api_proposal_decide(self, proposal_id, payload):
        proposal = self.env["csrs.task.proposal"].browse(int(proposal_id)).exists()
        if not proposal:
            raise UserError(_("Proposition introuvable."))
        proposal.action_csrs_decide(
            payload.get("decision"),
            payload.get("reason"),
            payload.get("revision"),
        )
        return self._proposal_payload(proposal)

    def _team_node(self, employee, period):
        children = self.env["hr.employee"].search(
            [("parent_id", "=", employee.id), ("user_id", "!=", False)], order="name"
        )
        task_count = self.env["project.task"].search_count(
            self._task_domain_for_period(period)
            + [("user_ids", "in", [employee.user_id.id])]
        )
        return {
            "employee": self._person(employee.user_id),
            "task_count": task_count,
            "children": [self._team_node(child, period) for child in children],
        }

    @api.model
    def api_team(self, week=None, month=None):
        period = self._period(week, month)
        users = self._managed_users()
        employees = self.env["hr.employee"].sudo().search(
            [("user_id", "in", users.ids)]
        )
        roots = employees.filtered(lambda item: item.parent_id not in employees)
        return {
            "period": period,
            "nodes": [self._team_node(employee, period) for employee in roots],
        }

    @api.model
    def api_team_employee(self, user_id, week=None, month=None):
        user = self.env["res.users"].browse(int(user_id)).exists()
        if not user or user not in self._managed_users():
            raise AccessError(_("Ce collaborateur n'est pas dans votre périmètre."))
        period = self._period(week, month)
        tasks = self.env["project.task"].search(
            self._task_domain_for_period(period) + [("user_ids", "in", [user.id])],
            order="date_deadline, name",
        )
        return {
            "period": period,
            "employee": self._person(user),
            "tasks": [self._task_summary(task, period) for task in tasks],
        }

    def _visit_payload(self, visit):
        return {
            "id": visit.id,
            "revision": visit.revision,
            "party_size": visit.party_size,
            "visitor_names": visit.visitor_names or [],
            "arrived_at": _iso(visit.arrived_at),
            "departed_at": _iso(visit.departed_at),
            "cancelled_at": _iso(visit.cancelled_at),
        }

    @api.model
    def api_visits(self, period_start, period_end):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_dg",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT",),
        )
        visits = self.env["csrs.visitor.visit"].sudo().search(
            [
                ("arrived_at", ">=", f"{period_start} 00:00:00"),
                ("arrived_at", "<=", f"{period_end} 23:59:59"),
            ]
        )
        return {
            "period_start": period_start,
            "period_end": period_end,
            "visits": [self._visit_payload(visit) for visit in visits],
        }

    @api.model
    def api_visit_create(self, payload):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT",),
        )
        names = [str(name).strip() for name in payload.get("visitor_names", []) if str(name).strip()]
        visit = self.env["csrs.visitor.visit"].sudo().create(
            {
                "party_size": int(payload["party_size"]),
                "visitor_names": names,
                "arrived_at": payload.get("arrived_at") or fields.Datetime.now(),
            }
        )
        return self._visit_payload(visit)

    @api.model
    def api_visit_departure(self, visit_id, revision):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT",),
        )
        visit = self.env["csrs.visitor.visit"].sudo().browse(int(visit_id)).exists()
        if not visit:
            raise UserError(_("Visite introuvable."))
        visit.action_departure(revision)
        return self._visit_payload(visit)

    def _availability_payload(self, leave):
        return {
            "id": leave.id,
            "revision": leave.csrs_revision,
            "employee": self._person(leave.employee_id.user_id),
            "kind": leave.csrs_kind,
            "kind_label": dict(leave._fields["csrs_kind"].selection)[leave.csrs_kind],
            "start_date": _iso(leave.request_date_from),
            "end_date": _iso(leave.request_date_to),
            "note": leave.csrs_note or "",
            "cancelled_at": _iso(leave.csrs_cancelled_at),
        }

    @api.model
    def api_availability(self, week):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_hr",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_HR",),
        )
        period = self._period(week=week)
        leaves = self.env["hr.leave"].sudo().search(
            [
                ("csrs_managed", "=", True),
                ("request_date_from", "<=", period["end"]),
                ("request_date_to", ">=", period["start"]),
            ],
            order="request_date_from, employee_id",
        )
        employees = self.env["hr.employee"].sudo().search(
            [("user_id", "!=", False)], order="name"
        )
        return {
            "week_start": period["start"],
            "items": [self._availability_payload(leave) for leave in leaves],
            "employees": [self._person(employee.user_id) for employee in employees],
            "kinds": [
                {"value": "leave", "label": "Congé"},
                {"value": "absence", "label": "Absence"},
                {"value": "mission", "label": "Mission"},
            ],
        }

    def _leave_type(self, kind):
        xmlids = {
            "leave": "csrs_reporting.leave_type_csrs_leave",
            "absence": "csrs_reporting.leave_type_csrs_absence",
            "mission": "csrs_reporting.leave_type_csrs_mission",
        }
        try:
            xmlid = xmlids[kind]
        except KeyError:
            raise ValidationError(_("Nature d'indisponibilité invalide.")) from None
        return self.env.ref(xmlid)

    @api.model
    def api_availability_save(self, payload, leave_id=None):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_hr",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_HR",),
        )
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", int(payload["employee_id"]))], limit=1
        )
        if not employee:
            raise ValidationError(_("Collaborateur introuvable."))
        values = {
            "name": str(payload.get("note") or dict(
                self.env["hr.leave"]._fields["csrs_kind"].selection
            )[payload["kind"]]),
            "employee_id": employee.id,
            "holiday_status_id": self._leave_type(payload["kind"]).id,
            "request_date_from": payload["start_date"],
            "request_date_to": payload["end_date"],
            "csrs_managed": True,
            "csrs_kind": payload["kind"],
            "csrs_note": str(payload.get("note") or "").strip(),
        }
        if leave_id:
            leave = self.env["hr.leave"].sudo().browse(int(leave_id)).exists()
            if not leave:
                raise UserError(_("Indisponibilité introuvable."))
            if leave.csrs_revision != payload.get("revision"):
                raise UserError(_("L'indisponibilité a changé. Rechargez-la."))
            values["csrs_revision"] = leave.csrs_revision + 1
            leave.with_context(csrs_authorized_mutation=True).write(values)
        else:
            leave = self.env["hr.leave"].sudo().create(values)
        return self._availability_payload(leave)

    @api.model
    def api_availability_cancel(self, leave_id, payload):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_hr",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_HR",),
        )
        leave = self.env["hr.leave"].sudo().browse(int(leave_id)).exists()
        if not leave:
            raise UserError(_("Indisponibilité introuvable."))
        leave.with_user(self.env.user).action_csrs_cancel(
            payload.get("reason"), payload.get("revision")
        )
        return self._availability_payload(leave)

    def _agenda_snapshot(self, draft, direction):
        if direction not in AGENDA_LABELS:
            raise ValidationError(_("Direction d'agenda invalide."))
        start = draft.period_start
        end = draft.period_end
        employees = self.env["hr.employee"].sudo().search(
            [
                ("user_id", "!=", False),
                ("csrs_include_in_agenda", "=", True),
                "|",
                ("csrs_agenda_direction", "=", direction),
                ("csrs_agenda_direction", "=", False),
            ],
            order="department_id, name",
        )
        employees = employees.filtered(
            lambda item: not item.user_id.has_group("csrs_reporting.group_csrs_dg")
        )
        unclassified = employees.filtered(lambda item: not item.csrs_agenda_direction)
        tasks = self.env["project.task"].sudo().search(
            [
                ("csrs_managed", "=", True),
                ("user_ids", "in", employees.user_id.ids),
                ("csrs_start_date", "<=", end),
                ("date_deadline", ">=", start),
            ]
        )
        leaves = self.env["hr.leave"].sudo().search(
            [
                ("csrs_managed", "=", True),
                ("csrs_cancelled_at", "=", False),
                ("employee_id", "in", employees.ids),
                ("request_date_from", "<=", end),
                ("request_date_to", ">=", start),
            ]
        )
        visits = self.env["csrs.visitor.visit"].sudo().search(
            [("cancelled_at", "=", False)]
        )
        units = []
        departments = employees.department_id.sorted("name")
        for order, department in enumerate(departments, start=1):
            people = employees.filtered(lambda item: item.department_id == department)
            employee_payloads = []
            for employee in people:
                employee_tasks = tasks.filtered(
                    lambda task: employee.user_id in task.user_ids
                )
                if not employee_tasks:
                    continue
                task_payloads = []
                for task in employee_tasks:
                    latest = task.csrs_progress_entry_ids.sorted(
                        "recorded_at", reverse=True
                    )[:1]
                    task_payloads.append(
                        {
                            "id": task.id,
                            "title": task.name,
                            "status": task.csrs_status,
                            "status_label": STATUS_LABELS[task.csrs_status],
                            "percentage": task.csrs_progress_percent,
                            "progress_delta": self._progress_at(task, end)
                            - self._progress_at(task, start - timedelta(days=1)),
                            "observation": latest.observation if latest else "",
                        }
                    )
                rate = sum(item["percentage"] for item in task_payloads) / len(
                    task_payloads
                )
                employee_payloads.append(
                    {
                        "person": self._person(employee.user_id),
                        "unclassified": not bool(employee.csrs_agenda_direction),
                        "completion_rate": rate,
                        "tasks": task_payloads,
                    }
                )
            if employee_payloads:
                units.append(
                    {
                        "id": department.id,
                        "code": department.csrs_code or "",
                        "name": department.name,
                        "display_order": order,
                        "employees": employee_payloads,
                    }
                )
        visit_payloads = [self._visit_payload(visit) for visit in visits]
        return {
            "schema_version": 1,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "agenda_direction": direction,
            "agenda_direction_label": AGENDA_LABELS[direction],
            "major_events": draft.major_events or "RAS",
            "unclassified_users": [
                self._person(employee.user_id) for employee in unclassified
            ],
            "arrivals": [
                item
                for item in visit_payloads
                if item["arrived_at"]
                and start.isoformat() <= item["arrived_at"][:10] <= end.isoformat()
            ],
            "departures": [
                item
                for item in visit_payloads
                if item["departed_at"]
                and start.isoformat() <= item["departed_at"][:10] <= end.isoformat()
            ],
            "availability": [self._availability_payload(leave) for leave in leaves],
            "units": units,
        }

    def _draft_payload(self, draft, start, end):
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "major_events": draft.major_events if draft else "",
            "revision": draft.revision if draft else 0,
        }

    @api.model
    def api_agenda_preview(self, period_start, period_end, direction):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_dg",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT", "AGENDA_VIEWER"),
        )
        start = fields.Date.to_date(period_start)
        end = fields.Date.to_date(period_end)
        draft = self.env["csrs.agenda.draft"].sudo().search(
            [("period_start", "=", start), ("period_end", "=", end)], limit=1
        )
        if draft:
            snapshot = self._agenda_snapshot(draft, direction)
        else:
            ephemeral = self.env["csrs.agenda.draft"].new(
                {"period_start": start, "period_end": end, "major_events": ""}
            )
            ephemeral._check_period()
            snapshot = self._agenda_snapshot(ephemeral, direction)
        return {
            "draft": self._draft_payload(draft, start, end),
            "snapshot": snapshot,
        }

    @api.model
    def api_agenda_update_draft(self, payload):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT",),
        )
        start = fields.Date.to_date(payload["period_start"])
        end = fields.Date.to_date(payload["period_end"])
        draft = self.env["csrs.agenda.draft"].sudo().search(
            [("period_start", "=", start), ("period_end", "=", end)], limit=1
        )
        expected = payload.get("revision", 0)
        if draft:
            draft.with_user(self.env.user).action_update(
                payload.get("major_events"), expected
            )
        else:
            if expected not in {None, 0}:
                raise UserError(_("Le brouillon a changé. Rechargez-le."))
            draft = self.env["csrs.agenda.draft"].sudo().create(
                {
                    "period_start": start,
                    "period_end": end,
                    "major_events": str(payload.get("major_events") or "").strip(),
                    "updated_by_id": self.env.user.id,
                }
            )
        return self._draft_payload(draft, start, end)

    def _version_payload(self, version):
        return {
            "id": version.id,
            "period_start": _iso(version.period_start),
            "period_end": _iso(version.period_end),
            "agenda_direction": version.agenda_direction,
            "agenda_direction_label": AGENDA_LABELS[version.agenda_direction],
            "version": version.version,
            "snapshot_sha256": version.snapshot_sha256,
            "pdf_sha256": version.pdf_sha256,
            "pdf_size": version.pdf_size,
            "generated_by": self._person(version.generated_by_id),
            "generated_at": _iso(version.generated_at),
            "pdf_url": f"/api/v1/agenda/versions/{version.id}/pdf/",
        }

    @api.model
    def api_agenda_versions(self, period_start=None, period_end=None):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_dg",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT", "AGENDA_VIEWER"),
        )
        domain = []
        if period_start:
            domain.append(("period_start", "=", period_start))
        if period_end:
            domain.append(("period_end", "=", period_end))
        versions = self.env["csrs.agenda.version"].sudo().search(domain)
        return {"versions": [self._version_payload(version) for version in versions]}

    @api.model
    def api_agenda_generate(self, payload):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT",),
        )
        draft = self.env["csrs.agenda.draft"].sudo().search(
            [
                ("period_start", "=", payload["period_start"]),
                ("period_end", "=", payload["period_end"]),
            ],
            limit=1,
        )
        if not draft:
            raise ValidationError(_("Enregistrez le brouillon avant de générer."))
        snapshot = self._agenda_snapshot(draft, payload["agenda_direction"])
        version = self.env["csrs.agenda.version"].create_from_snapshot(
            draft, payload["agenda_direction"], snapshot
        )
        return self._version_payload(version)

    @api.model
    def api_agenda_pdf(self, version_id):
        self._require_group_or_global_role(
            (
                "csrs_reporting.group_csrs_secretariat",
                "csrs_reporting.group_csrs_dg",
                "csrs_reporting.group_csrs_it",
            ),
            ("AGENDA_SECRETARIAT", "AGENDA_VIEWER"),
        )
        version = self.env["csrs.agenda.version"].sudo().browse(int(version_id)).exists()
        if not version or not version.pdf_attachment_id:
            raise UserError(_("PDF introuvable."))
        return {
            "name": version.pdf_attachment_id.name,
            "content": version.pdf_attachment_id.datas.decode(),
        }
