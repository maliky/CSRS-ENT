"""Validated, idempotent import of the active CSRS identity snapshot."""

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


GROUP_BY_ROLE = {
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


class CsrsMigrationImporter(models.AbstractModel):
    _name = "csrs.migration.importer"
    _description = "Import contrôlé de la source CSRS"

    @api.model
    def import_payload(self, payload, apply=False):
        """Validate a versioned snapshot, then optionally upsert it atomically."""
        snapshot = self._validate_payload(payload)
        report = {
            "mode": "apply" if apply else "dry-run",
            "users": len(snapshot["users"]),
            "departments": len(snapshot["departments"]),
            "department_links": len(snapshot["department_links"]),
            "memberships": len(snapshot["memberships"]),
            "reporting_lines": len(snapshot["reporting_lines"]),
            "role_grants": len(snapshot["role_grants"]),
            "created": defaultdict(int),
            "updated": defaultdict(int),
            "unchanged": defaultdict(int),
        }
        if not apply:
            report["created"] = {}
            report["updated"] = {}
            report["unchanged"] = {}
            return report

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
        report["created"] = dict(report["created"])
        report["updated"] = dict(report["updated"])
        report["unchanged"] = dict(report["unchanged"])
        return report

    @staticmethod
    def _changes(record, values):
        changes = {}
        for key, value in values.items():
            current = record[key]
            if record._fields[key].type == "many2one":
                current = current.id or False
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
        if not isinstance(payload, dict) or payload.get("version") != 2:
            raise ValidationError(_("Version de fichier de migration invalide."))
        names = (
            "users",
            "departments",
            "department_links",
            "memberships",
            "reporting_lines",
            "role_grants",
        )
        snapshot = {name: self._records(payload, name) for name in names}
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
        return snapshot

    @staticmethod
    def _records(payload, name):
        rows = payload.get(name)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValidationError(_("Collection de migration invalide : %s.", name))
        return rows

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
            if row.get("is_it_admin"):
                by_login = user or by_login or self.env.ref("base.user_admin")
            if user and by_login and user != by_login:
                raise ValidationError(_("Collision entre identifiant source et email."))
            user = user or by_login
            first_source_import = not user or not user.csrs_source_id
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
            group_xmlid = GROUP_BY_ROLE.get(row["role_code"])
            if group_xmlid:
                self._link_group(
                    users[row["user_source_id"]], self.env.ref(group_xmlid)
                )
