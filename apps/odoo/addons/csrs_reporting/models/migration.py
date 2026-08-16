"""Validated, idempotent import of the active CSRS identity snapshot."""

from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tools import html2plaintext


class CsrsMigrationImporter(models.AbstractModel):
    _name = "csrs.migration.importer"
    _description = "Import contrôlé de la source CSRS"

    @api.model
    def import_payload(self, payload, apply=False, reconcile=False):
        """Validate a versioned snapshot, then optionally upsert it atomically."""
        snapshot = self._validate_payload(payload)
        report = {
            "mode": "reconcile" if reconcile else ("apply" if apply else "dry-run"),
            "created": defaultdict(int),
            "updated": defaultdict(int),
            "unchanged": defaultdict(int),
        }
        report.update(
            {
                name: len(rows)
                for name, rows in snapshot.items()
                if isinstance(rows, list)
            }
        )
        if not apply:
            report["created"] = {}
            report["updated"] = {}
            report["unchanged"] = {}
            return report

        if reconcile:
            self._remove_demo_identity_snapshot(snapshot["users"], report)
            self._prepare_department_reconciliation(
                snapshot["departments"], report
            )
        departments = self._upsert_departments(snapshot["departments"], report)
        self._link_departments(snapshot["department_links"], departments)
        users, employees = self._upsert_users(snapshot["users"], report)
        self._upsert_memberships(
            snapshot["memberships"], users, employees, departments, report
        )
        self._apply_reporting_lines(
            snapshot["reporting_lines"], users, employees, report
        )
        self._upsert_role_grants(
            snapshot["role_grants"], users, departments, report
        )
        if snapshot["version"] == 3:
            plans, action_plans, actions = self._upsert_planning(snapshot, report)
            calendars = self._upsert_calendars(snapshot, report)
            task_definitions, tasks = self._upsert_tasks(
                snapshot, users, departments, actions, calendars, report
            )
            proposals = self._upsert_proposals(
                snapshot, users, actions, calendars, tasks, report
            )
            self._upsert_progress_history(snapshot, users, tasks, report)
            self._upsert_task_activities(snapshot, users, tasks, report)
            self._upsert_legacy_revisions(
                snapshot, users, task_definitions, tasks, proposals, report
            )
            del plans, action_plans
        if reconcile:
            self._archive_absent_source_records(snapshot, report)
        report["created"] = dict(report["created"])
        report["updated"] = dict(report["updated"])
        report["unchanged"] = dict(report["unchanged"])
        return report

    @staticmethod
    def _changes(record, values):
        changes = {}
        for key, value in values.items():
            current = record[key]
            field_type = record._fields[key].type
            if field_type == "many2one":
                current = current.id or False
            elif field_type == "datetime" and value:
                value = fields.Datetime.to_datetime(value)
            elif field_type == "many2many":
                current = tuple(sorted(current.ids))
                if (
                    isinstance(value, (list, tuple))
                    and len(value) == 1
                    and value[0][0] == Command.SET
                ):
                    value = tuple(sorted(value[0][2]))
            elif field_type == "html":
                current = html2plaintext(current or "").strip()
                value = html2plaintext(value or "").strip()
            if current in (None, "") and value in (None, "", False):
                continue
            if current != value:
                changes[key] = value
        return changes

    def _write_or_report(self, record, values, report, label):
        changes = self._changes(record, values)
        if changes:
            record.write(changes)
            report["updated"][label] += 1
            return True
        report["unchanged"][label] += 1
        return False

    @staticmethod
    def _link_group(user, group):
        if group not in user.group_ids:
            user.write({"group_ids": [Command.link(group.id)]})

    def _validate_payload(self, payload):
        if not isinstance(payload, dict) or payload.get("version") not in {2, 3}:
            raise ValidationError(_("Version de fichier de migration invalide."))
        names = [
            "users",
            "departments",
            "department_links",
            "memberships",
            "reporting_lines",
            "role_grants",
        ]
        extended_names = [
            "strategic_plans",
            "action_plans",
            "institutional_actions",
            "work_calendars",
            "work_calendar_days",
            "tasks",
            "task_assignments",
            "task_proposals",
            "progress_entries",
            "task_activities",
            "task_history",
            "assignment_history",
            "proposal_history",
            "progress_history",
        ]
        if payload["version"] == 3:
            names.extend(extended_names)
        snapshot = {name: self._records(payload, name) for name in names}
        snapshot["version"] = payload["version"]
        for name in extended_names:
            snapshot.setdefault(name, [])
        self._unique(snapshot["users"], "source_id", "utilisateur")
        self._unique(snapshot["users"], "email", "email", casefold=True)
        self._unique(
            [row for row in snapshot["users"] if row.get("alias")],
            "alias",
            "alias",
            casefold=True,
        )
        emails = {
            row["email"].strip().casefold()
            for row in snapshot["users"]
            if isinstance(row.get("email"), str)
        }
        aliases = {
            row["alias"].strip().casefold()
            for row in snapshot["users"]
            if isinstance(row.get("alias"), str) and row["alias"]
        }
        if emails & aliases:
            raise ValidationError(_("Un alias entre en collision avec un email."))
        self._unique(snapshot["departments"], "source_id", "service")
        self._unique(snapshot["departments"], "code", "code service", casefold=True)
        self._unique(snapshot["memberships"], "source_id", "rattachement")
        self._unique(snapshot["reporting_lines"], "source_id", "ligne hiérarchique")
        self._unique(snapshot["role_grants"], "source_id", "délégation")

        user_ids = {self._positive_int(row, "source_id") for row in snapshot["users"]}
        department_ids = {
            self._positive_int(row, "source_id") for row in snapshot["departments"]
        }
        for row in snapshot["users"]:
            self._required_string(row, "email")
            self._required_string(row, "name")
            self._required_string(row, "password_hash")
            direction = row.get("agenda_direction") or ""
            if direction not in ("", "programs", "administration"):
                raise ValidationError(_("Direction d'agenda invalide."))
        for row in snapshot["departments"]:
            self._required_string(row, "code")
            self._required_string(row, "name")
            self._required_string(row, "short_name")
            self._required_string(row, "kind")
            display_order = row.get("display_order")
            if not isinstance(display_order, int) or isinstance(display_order, bool):
                raise ValidationError(_("Ordre d'affichage de service invalide."))
        self._validate_department_graph(snapshot["department_links"], department_ids)
        for row in snapshot["memberships"]:
            self._reference(row, "user_source_id", user_ids)
            self._reference(row, "department_source_id", department_ids)
            self._required_string(row, "start_date")
        for row in snapshot["reporting_lines"]:
            employee_id = self._reference(row, "employee_source_id", user_ids)
            supervisor_id = self._reference(row, "supervisor_source_id", user_ids)
            if employee_id == supervisor_id:
                raise ValidationError(_("Une ligne hiérarchique est réflexive."))
            self._reference(row, "department_source_id", department_ids)
            self._required_string(row, "start_date")
        for row in snapshot["role_grants"]:
            self._reference(row, "user_source_id", user_ids)
            self._reference(row, "department_source_id", department_ids)
            self._required_string(row, "role_code")
            if row.get("scope") not in ("unit", "tree"):
                raise ValidationError(_("Portée de délégation invalide."))
        if snapshot["version"] == 3:
            self._validate_work_snapshot(snapshot, user_ids, department_ids)
        return snapshot

    @staticmethod
    def _records(payload, name):
        rows = payload.get(name)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValidationError(_("Collection de migration invalide : %s.", name))
        return rows

    def _validate_work_snapshot(self, snapshot, user_ids, department_ids):
        collections = (
            "strategic_plans",
            "action_plans",
            "institutional_actions",
            "work_calendars",
            "work_calendar_days",
            "tasks",
            "task_assignments",
            "task_proposals",
            "progress_entries",
            "task_activities",
            "task_history",
            "assignment_history",
            "proposal_history",
            "progress_history",
        )
        for name in collections:
            key = "history_id" if name.endswith("_history") else "source_id"
            self._unique(snapshot[name], key, name)
        plan_ids = {
            self._positive_int(row, "source_id") for row in snapshot["strategic_plans"]
        }
        action_plan_ids = {
            self._positive_int(row, "source_id") for row in snapshot["action_plans"]
        }
        action_ids = {
            self._positive_int(row, "source_id")
            for row in snapshot["institutional_actions"]
        }
        calendar_ids = {
            self._positive_int(row, "source_id") for row in snapshot["work_calendars"]
        }
        task_ids = {
            self._positive_int(row, "source_id") for row in snapshot["tasks"]
        }
        assignment_ids = {
            self._positive_int(row, "source_id")
            for row in snapshot["task_assignments"]
        }
        proposal_ids = {
            self._positive_int(row, "source_id")
            for row in snapshot["task_proposals"]
        }
        progress_ids = {
            self._positive_int(row, "source_id")
            for row in snapshot["progress_entries"]
        }
        for row in snapshot["strategic_plans"]:
            self._required_string(row, "name")
            self._required_string(row, "start_date")
            self._required_string(row, "end_date")
        for row in snapshot["action_plans"]:
            self._reference(row, "strategic_plan_source_id", plan_ids)
            self._required_string(row, "code")
            self._required_string(row, "name")
        for row in snapshot["institutional_actions"]:
            self._reference(row, "action_plan_source_id", action_plan_ids)
            self._required_string(row, "code")
            self._required_string(row, "name")
        for row in snapshot["work_calendar_days"]:
            self._reference(row, "calendar_source_id", calendar_ids)
            self._required_string(row, "day")
        for row in snapshot["tasks"]:
            self._required_string(row, "code")
            self._required_string(row, "title")
            self._reference(row, "created_by_source_id", user_ids)
            self._optional_reference(row, "action_source_id", action_ids)
        seen_task_assignments = set()
        for row in snapshot["task_assignments"]:
            task_id = self._reference(row, "task_source_id", task_ids)
            if task_id in seen_task_assignments:
                raise ValidationError(_("Une tâche source possède plusieurs affectations."))
            seen_task_assignments.add(task_id)
            self._reference(row, "employee_source_id", user_ids)
            self._reference(row, "manager_source_id", user_ids)
            # Historical tasks can point to a deleted unit; the assignment is
            # authoritative through its employee, manager and Odoo project.
            if row.get("organization_unit_source_id"):
                self._positive_int(row, "organization_unit_source_id")
            self._reference(row, "calendar_source_id", calendar_ids)
            self._required_string(row, "start_date")
            self._required_string(row, "due_date")
            if row.get("status") not in {
                "planned",
                "active",
                "awaiting_validation",
                "completed",
                "closed_early",
            }:
                raise ValidationError(_("État d'affectation source invalide."))
        for row in snapshot["task_proposals"]:
            self._reference(row, "employee_source_id", user_ids)
            if row.get("organization_unit_source_id"):
                self._positive_int(row, "organization_unit_source_id")
            self._optional_reference(row, "action_source_id", action_ids)
            self._reference(row, "calendar_source_id", calendar_ids)
            self._optional_reference(row, "reviewed_by_source_id", user_ids)
            self._optional_reference(
                row, "accepted_assignment_source_id", assignment_ids
            )
            if row.get("status") not in {"submitted", "accepted", "rejected"}:
                raise ValidationError(_("État de proposition source invalide."))
        for row in snapshot["progress_entries"]:
            self._reference(row, "assignment_source_id", assignment_ids)
            self._reference(row, "author_source_id", user_ids)
        for row in snapshot["task_activities"]:
            self._reference(row, "assignment_source_id", assignment_ids)
            self._reference(row, "actor_source_id", user_ids)
            self._optional_reference(row, "progress_source_id", progress_ids)
        for name in (
            "task_history",
            "assignment_history",
            "proposal_history",
            "progress_history",
        ):
            for row in snapshot[name]:
                self._positive_int(row, "history_id")
                self._positive_int(row, "record_id")
                self._required_string(row, "history_date")
                self._optional_reference(
                    row, "history_user_source_id", user_ids
                )
        del proposal_ids

    @staticmethod
    def _positive_int(row, key):
        value = row.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValidationError(_("Identifiant source invalide : %s.", key))
        return value

    @staticmethod
    def _required_string(row, key):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(_("Valeur source absente : %s.", key))
        return value.strip()

    def _reference(self, row, key, allowed):
        value = self._positive_int(row, key)
        if value not in allowed:
            raise ValidationError(_("Référence source inconnue : %s.", key))
        return value

    def _optional_reference(self, row, key, allowed):
        value = row.get(key)
        if value in (None, False, ""):
            return None
        return self._reference(row, key, allowed)

    def _unique(self, rows, key, label, casefold=False):
        seen = set()
        for row in rows:
            value = row.get(key)
            if isinstance(value, str) and casefold:
                value = value.strip().casefold()
            if value in seen:
                raise ValidationError(_("Doublon dans la source : %s.", label))
            seen.add(value)

    def _validate_department_graph(self, rows, department_ids):
        parents = {}
        children = defaultdict(list)
        for row in rows:
            parent = self._reference(row, "parent_source_id", department_ids)
            child = self._reference(row, "child_source_id", department_ids)
            if parent == child or child in parents:
                raise ValidationError(_("Hiérarchie de services ambiguë ou réflexive."))
            parents[child] = parent
            children[parent].append(child)
        visiting = set()
        visited = set()

        def visit(node):
            if node in visiting:
                raise ValidationError("La hiérarchie des services contient un cycle.")
            if node in visited:
                return
            visiting.add(node)
            for child in children.get(node, ()):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for department_id in department_ids:
            visit(department_id)

    def _upsert_departments(self, rows, report):
        Department = self.env["hr.department"].sudo().with_context(active_test=False)
        result = {}
        for row in rows:
            source_id = row["source_id"]
            department = Department.search([("csrs_source_id", "=", source_id)], limit=1)
            by_code = Department.search([("csrs_code", "=ilike", row["code"])], limit=1)
            if department and by_code and department != by_code:
                raise ValidationError(_("Collision entre identifiant et code de service."))
            department = department or by_code
            values = {
                "name": row["name"],
                "active": bool(row.get("active", True)),
                "csrs_source_id": source_id,
                "csrs_code": row["code"].strip().upper(),
                "csrs_short_name": row["short_name"].strip(),
                "csrs_kind": row["kind"].strip(),
                "csrs_display_order": row["display_order"],
            }
            if department:
                self._write_or_report(
                    department, values, report, "departments"
                )
            else:
                department = Department.create(values)
                report["created"]["departments"] += 1
            result[source_id] = department
        return result

    def _prepare_department_reconciliation(
        self, rows: list[dict[str, object]], report: dict[str, object]
    ) -> None:
        """Release obsolete numeric identities before adopting stable codes."""
        Department = self.env["hr.department"].sudo().with_context(active_test=False)
        source_codes = {
            row["source_id"]: str(row["code"]).strip().upper() for row in rows
        }
        incoming_codes = frozenset(source_codes.values())
        incoming_source_ids = frozenset(source_codes)
        released = Department.browse()
        displaced = Department.browse()
        for department in Department.search([("csrs_source_id", "!=", False)]):
            current_source_id = department.csrs_source_id
            current_code = (department.csrs_code or "").strip().upper()
            if source_codes.get(current_source_id) == current_code:
                continue
            if (
                current_source_id in incoming_source_ids
                or current_code in incoming_codes
            ):
                released |= department
                if current_code not in incoming_codes:
                    displaced |= department
        if released:
            Department.flush_model(["csrs_source_id"])
            self.env.cr.execute(
                "UPDATE hr_department SET csrs_source_id=NULL WHERE id = ANY(%s)",
                [released.ids],
            )
            released.invalidate_recordset(["csrs_source_id"])
            report["updated"]["department_source_ids_released"] += len(released)
        if displaced:
            displaced.write({"active": False})
            report["updated"]["departments_archived"] += len(displaced)

    def _link_departments(self, rows, departments):
        parents = {
            row["child_source_id"]: row["parent_source_id"] for row in rows
        }
        for source_id, department in departments.items():
            parent = departments.get(parents.get(source_id))
            parent_id = parent.id if parent else False
            if (department.parent_id.id or False) != parent_id:
                department.parent_id = parent_id

    def _upsert_users(self, rows, report):
        Users = (
            self.env["res.users"]
            .sudo()
            .with_context(
                active_test=False,
                no_reset_password=True,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        Employees = (
            self.env["hr.employee"]
            .sudo()
            .with_context(
                active_test=False,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        internal_group = self.env.ref("base.group_user")
        agent_group = self.env.ref("csrs_reporting.group_csrs_agent")
        users = {}
        employees = {}
        for row in rows:
            source_id = row["source_id"]
            user = Users.search([("csrs_source_id", "=", source_id)], limit=1)
            by_login = Users.search([("login", "=ilike", row["email"])], limit=1)
            by_email = Users.search([("email", "=ilike", row["email"])], limit=2)
            alias = (row.get("alias") or "").strip()
            by_alias = (
                Users.search([("csrs_alias", "=ilike", alias)], limit=2)
                if alias
                else Users
            )
            candidates = user | by_login | by_email | by_alias
            if len(candidates) > 1:
                raise ValidationError(
                    _("Collision entre identifiant source, email et alias.")
                )
            user = candidates
            first_source_import = not user or (
                not user.csrs_source_id and user.csrs_alias != "dev"
            )
            values = {
                "name": row["name"],
                "login": row["email"].strip().lower(),
                "email": row["email"].strip().lower(),
                "phone": (row.get("phone") or "").strip() or False,
                "active": bool(row.get("active", True)),
                "csrs_source_id": source_id,
                "csrs_alias": (row.get("alias") or "").strip() or False,
                "csrs_first_name": (row.get("first_name") or "").strip() or False,
                "csrs_last_name": (row.get("last_name") or "").strip() or False,
            }
            if user:
                if user.csrs_source_id and user.csrs_source_id != source_id:
                    raise ValidationError(_("Un compte Odoo appartient à une autre source."))
                self._write_or_report(user, values, report, "users")
            else:
                values["group_ids"] = [
                    Command.link(internal_group.id),
                    Command.link(agent_group.id),
                ]
                user = Users.create(values)
                report["created"]["users"] += 1
            self._link_group(user, agent_group)
            user.csrs_import_legacy_password_hash(
                row["password_hash"], replace_native=first_source_import
            )
            self._assign_user_kind_groups(user, row)
            employee = Employees.search([("csrs_source_id", "=", source_id)], limit=1)
            by_user = Employees.search([("user_id", "=", user.id)], limit=1)
            if employee and by_user and employee != by_user:
                raise ValidationError(
                    _("Collision entre identifiant source et employé Odoo.")
                )
            employee = employee or by_user
            employee_values = {
                "name": row["name"],
                "user_id": user.id,
                "work_email": row["email"].strip().lower(),
                "work_phone": (row.get("phone") or "").strip() or False,
                "active": bool(row.get("active", True)),
                "csrs_source_id": source_id,
                "csrs_agenda_direction": row.get("agenda_direction") or False,
                "csrs_include_in_agenda": bool(
                    row.get("include_in_direction_agendas", True)
                ),
            }
            if not employee or not employee.csrs_source_id:
                employee_values["job_title"] = (
                    (row.get("job_title") or "").strip() or False
                )
            if employee:
                if employee.csrs_source_id and employee.csrs_source_id != source_id:
                    raise ValidationError(
                        _("Une fiche employé appartient à une autre source.")
                    )
                self._write_or_report(
                    employee, employee_values, report, "employees"
                )
            else:
                employee = Employees.create(employee_values)
                report["created"]["employees"] += 1
            users[source_id] = user
            employees[source_id] = employee
        return users, employees

    def _assign_user_kind_groups(self, user, row):
        xmlids = []
        if row.get("is_it_admin"):
            xmlids.extend(("base.group_system", "csrs_reporting.group_csrs_it"))
        if row.get("is_dg"):
            xmlids.append("csrs_reporting.group_csrs_dg")
        if xmlids:
            for xmlid in xmlids:
                self._link_group(user, self.env.ref(xmlid))

    def _upsert_memberships(
        self, rows, users, employees, departments, report
    ):
        Membership = self.env["csrs.organization.membership"].sudo().with_context(
            active_test=False
        )
        for row in rows:
            source_id = row["source_id"]
            membership = Membership.search(
                [("csrs_source_id", "=", source_id)], limit=1
            )
            values = {
                "csrs_source_id": source_id,
                "user_id": users[row["user_source_id"]].id,
                "department_id": departments[row["department_source_id"]].id,
                "job_title": (row.get("job_title") or "").strip() or False,
                "start_date": fields.Date.to_date(row["start_date"]),
                "end_date": fields.Date.to_date(row["end_date"])
                if row.get("end_date")
                else False,
                "is_primary": bool(row.get("is_primary")),
                "active": not bool(row.get("end_date")),
            }
            if membership:
                self._write_or_report(
                    membership, values, report, "memberships"
                )
            else:
                Membership.create(values)
                report["created"]["memberships"] += 1
            if row.get("is_primary") and not row.get("end_date"):
                employee = employees[row["user_source_id"]]
                self._write_or_report(
                    employee,
                    {
                        "department_id": departments[row["department_source_id"]].id,
                        "job_title": (row.get("job_title") or "").strip() or False,
                    },
                    report,
                    "employee_primary_memberships",
                )

    def _apply_reporting_lines(self, rows, users, employees, report):
        ReportingLine = self.env["csrs.reporting.line"].sudo().with_context(
            active_test=False
        )
        primary_group = self.env.ref("csrs_reporting.group_csrs_primary_manager")
        secondary_group = self.env.ref("csrs_reporting.group_csrs_secondary_manager")
        secondaries = defaultdict(list)
        for row in rows:
            employee = employees[row["employee_source_id"]]
            supervisor_employee = employees[row["supervisor_source_id"]]
            supervisor_user = users[row["supervisor_source_id"]]
            source_id = row["source_id"]
            line = ReportingLine.search(
                [("csrs_source_id", "=", source_id)], limit=1
            )
            values = {
                "csrs_source_id": source_id,
                "employee_id": users[row["employee_source_id"]].id,
                "supervisor_id": supervisor_user.id,
                "department_id": self.env["hr.department"].search(
                    [("csrs_source_id", "=", row["department_source_id"])], limit=1
                ).id,
                "start_date": fields.Date.to_date(row["start_date"]),
                "end_date": fields.Date.to_date(row["end_date"])
                if row.get("end_date")
                else False,
                "is_primary": bool(row.get("is_primary")),
                "active": not bool(row.get("end_date")),
            }
            if line:
                self._write_or_report(line, values, report, "reporting_lines")
            else:
                ReportingLine.create(values)
                report["created"]["reporting_lines"] += 1
            if row.get("is_primary"):
                if employee.parent_id != supervisor_employee:
                    employee.parent_id = supervisor_employee
                    report["updated"]["primary_reporting_lines"] += 1
                else:
                    report["unchanged"]["primary_reporting_lines"] += 1
                self._link_group(supervisor_user, primary_group)
            else:
                secondaries[employee.id].append(supervisor_user.id)
                self._link_group(supervisor_user, secondary_group)
        for employee in employees.values():
            expected = set(secondaries.get(employee.id, []))
            if set(employee.csrs_secondary_manager_user_ids.ids) != expected:
                employee.csrs_secondary_manager_user_ids = [Command.set(expected)]

    def _upsert_role_grants(self, rows, users, departments, report):
        Grant = self.env["csrs.role.grant"].sudo().with_context(active_test=False)
        for row in rows:
            source_id = row["source_id"]
            grant = Grant.search([("csrs_source_id", "=", source_id)], limit=1)
            values = {
                "csrs_source_id": source_id,
                "user_id": users[row["user_source_id"]].id,
                "department_id": departments[row["department_source_id"]].id,
                "role_code": row["role_code"],
                "scope": row["scope"],
                "valid_from": fields.Datetime.to_datetime(row["valid_from"]),
                "valid_until": fields.Datetime.to_datetime(row["valid_until"])
                if row.get("valid_until")
                else False,
                "active": bool(row.get("active", True)),
            }
            if grant:
                self._write_or_report(grant, values, report, "role_grants")
            else:
                Grant.create(values)
                report["created"]["role_grants"] += 1

    def _remove_demo_identity_snapshot(
        self, rows: list[dict[str, object]], report: dict[str, object]
    ) -> None:
        """Delete only the known demo identities while preserving ``dev``."""
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        Employees = self.env["hr.employee"].sudo().with_context(active_test=False)
        administrator = self.env.ref("base.user_admin")
        by_source_id = {row["source_id"]: row for row in rows}
        by_email = {
            str(row["email"]).strip().casefold(): row for row in rows
        }
        by_alias = {
            str(row["alias"]).strip().casefold(): row
            for row in rows
            if row.get("alias")
        }

        def source_row(user):
            matches = {
                row["source_id"]: row
                for row in (
                    by_source_id.get(user.csrs_source_id),
                    by_email.get((user.login or "").strip().casefold()),
                    by_email.get((user.email or "").strip().casefold()),
                    by_alias.get((user.csrs_alias or "").strip().casefold()),
                )
                if row
            }
            if len(matches) > 1:
                raise ValidationError(
                    _(
                        "Une identité de démonstration correspond à plusieurs "
                        "comptes source."
                    )
                )
            return next(iter(matches.values()), None)

        demos = Users.search(
            [
                "|",
                ("login", "ilike", "@demo.invalid"),
                ("email", "ilike", "@demo.invalid"),
            ]
        )
        authoritative = {user.id: source_row(user) for user in demos}
        preserved = demos.filtered(
            lambda user: user == administrator
            or user.csrs_alias == "dev"
            or bool(authoritative[user.id])
        )
        rebound = preserved.filtered(
            lambda user: (
                authoritative[user.id]
                and user.csrs_source_id
                != authoritative[user.id]["source_id"]
            )
            or (
                not authoritative[user.id]
                and user.csrs_alias == "dev"
                and bool(user.csrs_source_id)
            )
        )
        if rebound:
            Users.flush_model(["csrs_source_id"])
            self.env.cr.execute(
                "UPDATE res_users SET csrs_source_id=NULL WHERE id = ANY(%s)",
                [rebound.ids],
            )
            rebound.invalidate_recordset(["csrs_source_id"])
            employees = Employees.search([("user_id", "in", rebound.ids)])
            if employees:
                Employees.flush_model(["csrs_source_id"])
                self.env.cr.execute(
                    "UPDATE hr_employee SET csrs_source_id=NULL WHERE id = ANY(%s)",
                    [employees.ids],
                )
                employees.invalidate_recordset(["csrs_source_id"])
        removable = demos - preserved
        if not removable:
            report["unchanged"]["demo_users_removed"] += 1
            return
        ids = removable.ids
        self.env.cr.execute(
            "UPDATE csrs_audit_event SET actor_id=%s WHERE actor_id = ANY(%s)",
            [administrator.id, ids],
        )
        self.env.cr.execute(
            "DELETE FROM csrs_role_grant WHERE user_id = ANY(%s) OR granted_by_id = ANY(%s) OR revoked_by_id = ANY(%s)",
            [ids, ids, ids],
        )
        self.env["csrs.reporting.line"].sudo().with_context(active_test=False).search(
            ["|", ("employee_id", "in", ids), ("supervisor_id", "in", ids)]
        ).unlink()
        self.env["csrs.organization.membership"].sudo().with_context(
            active_test=False
        ).search([("user_id", "in", ids)]).unlink()
        employees = self.env["hr.employee"].sudo().with_context(active_test=False).search(
            [("user_id", "in", ids)]
        )
        employees.unlink()
        removable.unlink()
        report["updated"]["demo_users_removed"] += len(ids)

    def _archive_absent_source_records(self, snapshot, report):
        source_user_ids = {row["source_id"] for row in snapshot["users"]}
        source_department_ids = {row["source_id"] for row in snapshot["departments"]}
        stale_users = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("csrs_source_id", "!=", False),
                    ("csrs_source_id", "not in", sorted(source_user_ids) or [0]),
                ]
            )
        )
        if stale_users:
            stale_users.write({"active": False})
            self.env["hr.employee"].sudo().with_context(active_test=False).search(
                [("user_id", "in", stale_users.ids)]
            ).write({"active": False})
            report["updated"]["users_archived"] += len(stale_users)
        stale_departments = (
            self.env["hr.department"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("csrs_source_id", "!=", False),
                    (
                        "csrs_source_id",
                        "not in",
                        sorted(source_department_ids) or [0],
                    ),
                ]
            )
        )
        if stale_departments:
            stale_departments.write({"active": False})
            report["updated"]["departments_archived"] += len(stale_departments)

    def _upsert_planning(self, snapshot, report):
        Strategic = self.env["csrs.strategic.plan"].sudo().with_context(
            active_test=False
        )
        ActionPlan = self.env["csrs.action.plan"].sudo().with_context(active_test=False)
        Action = self.env["csrs.institutional.action"].sudo().with_context(
            active_test=False
        )
        strategic = {}
        for row in snapshot["strategic_plans"]:
            record = Strategic.search([("csrs_source_id", "=", row["source_id"])], limit=1)
            values = {
                "csrs_source_id": row["source_id"],
                "name": row["name"],
                "start_date": fields.Date.to_date(row["start_date"]),
                "end_date": fields.Date.to_date(row["end_date"]),
                "active": bool(row.get("active", True)),
            }
            if record:
                self._write_or_report(record, values, report, "strategic_plans")
            else:
                record = Strategic.create(values)
                report["created"]["strategic_plans"] += 1
            strategic[row["source_id"]] = record
        plans = {}
        for row in snapshot["action_plans"]:
            record = ActionPlan.search(
                [("csrs_source_id", "=", row["source_id"])], limit=1
            )
            values = {
                "csrs_source_id": row["source_id"],
                "strategic_plan_id": strategic[row["strategic_plan_source_id"]].id,
                "code": row["code"],
                "name": row["name"],
                "active": bool(row.get("active", True)),
            }
            if record:
                self._write_or_report(record, values, report, "action_plans")
            else:
                record = ActionPlan.create(values)
                report["created"]["action_plans"] += 1
            plans[row["source_id"]] = record
        actions = {}
        for row in snapshot["institutional_actions"]:
            record = Action.search(
                [("csrs_source_id", "=", row["source_id"])], limit=1
            )
            values = {
                "csrs_source_id": row["source_id"],
                "action_plan_id": plans[row["action_plan_source_id"]].id,
                "code": row["code"],
                "name": row["name"],
                "active": bool(row.get("active", True)),
            }
            if record:
                self._write_or_report(record, values, report, "institutional_actions")
            else:
                record = Action.create(values)
                report["created"]["institutional_actions"] += 1
            actions[row["source_id"]] = record
        return strategic, plans, actions

    def _upsert_calendars(self, snapshot, report):
        Calendar = self.env["resource.calendar"].sudo().with_context(active_test=False)
        Leave = self.env["resource.calendar.leaves"].sudo()
        calendars = {}
        for row in snapshot["work_calendars"]:
            record = Calendar.search([("csrs_source_id", "=", row["source_id"])], limit=1)
            if not record and row.get("is_default"):
                record = self.env.company.resource_calendar_id
            values = {
                "name": f"{row['name']} ({row['version']})",
                "active": bool(row.get("active", True)),
                "csrs_source_id": row["source_id"],
                "csrs_source_version": row["version"],
            }
            if record:
                self._write_or_report(record, values, report, "work_calendars")
            else:
                record = Calendar.create(values)
                report["created"]["work_calendars"] += 1
            calendars[row["source_id"]] = record
        for row in snapshot["work_calendar_days"]:
            record = Leave.search([("csrs_source_id", "=", row["source_id"])], limit=1)
            day = fields.Date.to_date(row["day"])
            values = {
                "name": row["name"],
                "calendar_id": calendars[row["calendar_source_id"]].id,
                "date_from": datetime.combine(day, time.min),
                "date_to": datetime.combine(day + timedelta(days=1), time.min),
                "csrs_source_id": row["source_id"],
                "csrs_is_working_day": bool(row.get("is_working_day")),
            }
            if record:
                self._write_or_report(record, values, report, "work_calendar_days")
            elif not row.get("is_working_day"):
                Leave.create(values)
                report["created"]["work_calendar_days"] += 1
            else:
                report["unchanged"]["working_day_overrides"] += 1
        return calendars

    def _upsert_tasks(
        self, snapshot, users, departments, actions, calendars, report
    ):
        del departments
        Task = self.env["project.task"].sudo().with_context(active_test=False)
        definitions = {row["source_id"]: row for row in snapshot["tasks"]}
        assignments = {
            row["task_source_id"]: row for row in snapshot["task_assignments"]
        }
        tasks = {}
        for source_id, definition in definitions.items():
            assignment = assignments.get(source_id)
            record = Task.search([("csrs_task_source_id", "=", source_id)], limit=1)
            action = actions.get(definition.get("action_source_id"))
            if assignment:
                employee = users[assignment["employee_source_id"]]
                manager = users[assignment["manager_source_id"]]
                calendar = calendars[assignment["calendar_source_id"]]
                values = {
                    "active": True,
                    "name": definition["title"],
                    "description": definition["description"],
                    "csrs_source_id": assignment["source_id"],
                    "csrs_task_source_id": source_id,
                    "csrs_code": definition["code"],
                    "csrs_managed": True,
                    "csrs_manager_id": manager.id,
                    "user_ids": [(6, 0, employee.ids)],
                    "csrs_calendar_id": calendar.id,
                    "csrs_start_date": fields.Date.to_date(assignment["start_date"]),
                    "date_deadline": fields.Date.to_date(assignment["due_date"]),
                    "csrs_estimated_work_days": float(
                        assignment["estimated_work_days"]
                    ),
                    "csrs_status": assignment["status"],
                    "csrs_close_reason": assignment.get("closed_reason") or False,
                    "csrs_completed_at": fields.Datetime.to_datetime(
                        assignment["completed_at"]
                    )
                    if assignment.get("completed_at")
                    else False,
                    "csrs_revision": int(assignment.get("revision") or 1),
                    "csrs_institutional_action_id": action.id if action else False,
                }
            else:
                creator = users[definition["created_by_source_id"]]
                values = {
                    "active": False,
                    "name": definition["title"],
                    "description": definition["description"],
                    "csrs_task_source_id": source_id,
                    "csrs_code": definition["code"],
                    "csrs_managed": True,
                    "csrs_manager_id": creator.id,
                    "user_ids": [(6, 0, [])],
                    "csrs_status": "closed_early",
                    "csrs_close_reason": "Définition historique sans affectation active",
                    "csrs_institutional_action_id": action.id if action else False,
                }
            if record:
                self._write_or_report(
                    record.with_context(csrs_authorized_mutation=True),
                    values,
                    report,
                    "tasks",
                )
            else:
                record = Task.with_context(csrs_authorized_mutation=True).create(values)
                report["created"]["tasks"] += 1
            tasks[source_id] = record
        assignment_tasks = {
            row["source_id"]: tasks[row["task_source_id"]]
            for row in snapshot["task_assignments"]
        }
        return tasks, assignment_tasks

    def _upsert_proposals(
        self, snapshot, users, actions, calendars, tasks, report
    ):
        Proposal = self.env["csrs.task.proposal"].sudo().with_context(
            active_test=False,
            csrs_migration_import=True,
        )
        employees = self.env["hr.employee"].sudo().with_context(active_test=False)
        proposals = {}
        for row in snapshot["task_proposals"]:
            record = Proposal.search([("csrs_source_id", "=", row["source_id"])], limit=1)
            author = users[row["employee_source_id"]]
            reviewed = users.get(row.get("reviewed_by_source_id"))
            employee = employees.search([("user_id", "=", author.id)], limit=1)
            manager = reviewed or employee.parent_id.user_id or author
            accepted = tasks.get(row.get("accepted_assignment_source_id"))
            action = actions.get(row.get("action_source_id"))
            values = {
                "csrs_source_id": row["source_id"],
                "code": f"LEGACY-P-{row['source_id']:06d}",
                "title": row["title"],
                "description": row["description"],
                "author_id": author.id,
                "manager_id": manager.id,
                "institutional_action_id": action.id if action else False,
                "calendar_id": calendars[row["calendar_source_id"]].id,
                "start_date": fields.Date.to_date(row["start_date"]),
                "due_date": fields.Date.to_date(row["due_date"]),
                "estimated_work_days": float(row["estimated_work_days"]),
                "state": row["status"],
                "decision_note": row.get("decision_note") or False,
                "accepted_task_id": accepted.id if accepted else False,
                "revision": int(row.get("revision") or 1),
            }
            if record:
                self._write_or_report(record, values, report, "task_proposals")
            else:
                record = Proposal.with_context(csrs_authorized_mutation=True).create(values)
                report["created"]["task_proposals"] += 1
            proposals[row["source_id"]] = record
        return proposals

    def _upsert_progress_history(self, snapshot, users, tasks, report):
        Progress = self.env["csrs.progress.entry"].sudo()
        history_by_assignment = defaultdict(list)
        for row in snapshot["progress_history"]:
            if row.get("history_type") != "-":
                history_by_assignment[row["assignment_source_id"]].append(row)
        current_by_assignment = defaultdict(list)
        for row in snapshot["progress_entries"]:
            current_by_assignment[row["assignment_source_id"]].append(row)
        for assignment_id, task in tasks.items():
            rows = history_by_assignment.get(assignment_id)
            if not rows:
                rows = [
                    {
                        **row,
                        "history_id": None,
                        "history_date": row.get("updated_at") or row.get("created_at"),
                    }
                    for row in current_by_assignment.get(assignment_id, [])
                ]
            previous = 0.0
            last = None
            revision = 0
            for row in sorted(
                rows,
                key=lambda item: (
                    item.get("history_date") or "",
                    item.get("history_id") or 0,
                ),
            ):
                revision += 1
                history_id = row.get("history_id")
                existing = (
                    Progress.search([("csrs_history_id", "=", history_id)], limit=1)
                    if history_id
                    else Progress.search(
                        [
                            ("csrs_source_id", "=", row["source_id"]),
                            ("task_id", "=", task.id),
                        ],
                        limit=1,
                    )
                )
                author = users.get(row.get("author_source_id")) or task.csrs_manager_id
                values = {
                    "task_id": task.id,
                    "csrs_source_id": row.get("source_id") or row.get("record_id"),
                    "csrs_history_id": history_id or False,
                    "author_id": author.id,
                    "recorded_at": fields.Datetime.to_datetime(
                        row.get("history_date") or row.get("updated_at")
                    ),
                    "previous_progress_percent": previous,
                    "progress_percent": float(row["percentage"]),
                    "blocked": bool(row.get("blocked")),
                    "observation": row.get("note") or "",
                    "revision": revision,
                }
                if existing:
                    report["unchanged"]["progress_history"] += 1
                else:
                    Progress.create(values)
                    report["created"]["progress_history"] += 1
                previous = float(row["percentage"])
                last = row
            current = sorted(
                current_by_assignment.get(assignment_id, []),
                key=lambda item: (item["entry_date"], item["source_id"]),
            )
            if current:
                last = current[-1]
            if last:
                next_revision = max(task.csrs_revision, revision)
                task.with_context(csrs_authorized_mutation=True).write(
                    {
                        "csrs_progress_percent": float(last["percentage"]),
                        "csrs_blocked": bool(last.get("blocked")),
                        "csrs_revision": next_revision,
                    }
                )

    def _upsert_task_activities(self, snapshot, users, tasks, report):
        Messages = self.env["mail.message"].sudo()
        for row in snapshot["task_activities"]:
            message_id = f"<legacy-task-activity-{row['source_id']}@csrs-ent.invalid>"
            if Messages.search([("message_id", "=", message_id)], limit=1):
                report["unchanged"]["task_activities"] += 1
                continue
            task = tasks[row["assignment_source_id"]]
            actor = users[row["actor_source_id"]]
            Messages.create(
                {
                    "model": "project.task",
                    "res_id": task.id,
                    "message_type": "comment",
                    "body": row["message"] or row["kind"],
                    "author_id": actor.partner_id.id,
                    "date": fields.Datetime.to_datetime(row["occurred_at"]),
                    "message_id": message_id,
                }
            )
            report["created"]["task_activities"] += 1

    def _upsert_legacy_revisions(
        self, snapshot, users, task_definitions, tasks, proposals, report
    ):
        Revision = self.env["csrs.legacy.task.revision"].sudo()
        mappings = (
            ("task_history", "task", task_definitions, "record_id"),
            ("assignment_history", "assignment", tasks, "record_id"),
            ("proposal_history", "proposal", proposals, "record_id"),
            ("progress_history", "progress", tasks, "assignment_source_id"),
        )
        for collection, source_model, targets, target_key in mappings:
            for row in snapshot[collection]:
                target = targets.get(row.get(target_key))
                if not target:
                    report["unchanged"][f"{collection}_without_target"] += 1
                    continue
                existing = Revision.search(
                    [
                        ("source_model", "=", source_model),
                        ("source_history_id", "=", row["history_id"]),
                    ],
                    limit=1,
                )
                if existing:
                    report["unchanged"][collection] += 1
                    continue
                actor = users.get(row.get("history_user_source_id"))
                values = {
                    "source_model": source_model,
                    "source_history_id": row["history_id"],
                    "source_record_id": row["record_id"],
                    "actor_id": actor.id if actor else False,
                    "occurred_at": fields.Datetime.to_datetime(row["history_date"]),
                    "change_kind": row.get("history_type") or "",
                    "snapshot": row,
                }
                if source_model == "proposal":
                    values["proposal_id"] = target.id
                else:
                    values["task_id"] = target.id
                Revision.create(values)
                report["created"][collection] += 1
