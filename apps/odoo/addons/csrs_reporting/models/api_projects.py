"""Project and procedure use cases exposed through the central CSRS facade."""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command

from .processes import CORRECTABLE_STATES, PROCESS_TYPES, TRANSITIONS
from .research_project import SECTION_CODES


PROJECT_STATE_LABELS = {
    "proposal": "Proposition",
    "active": "Actif",
    "rejected": "Rejeté",
    "closed": "Clôturé",
}

PROCESS_STATE_LABELS = {
    "draft": "Brouillon",
    "correction": "À corriger",
    "rejected": "Rejeté",
    "completed": "Terminé",
    "archived": "Archivé",
    "finance_review": "Contrôle financier",
    "requester_visa": "Visa du demandeur",
    "finance_head": "Responsable finances",
    "daf_review": "Contrôle DAF",
    "project_accounting": "Comptabilité projet",
    "dg_review": "Validation DG",
    "payment_preparation": "Préparation du paiement",
    "procurement": "Traitement achat",
    "ordered": "Commandé",
    "delivered": "Livré",
    "invoiced": "Facturé",
    "supervisor_review": "Responsable hiérarchique",
    "hr_review": "Contrôle RH",
    "secretariat": "Secrétariat",
    "assistance": "Assistance de recherche",
    "accounting": "Comptabilité",
    "fleet": "Parc automobile",
    "notified": "Bénéficiaire notifié",
    "research_assistance": "Assistance de recherche",
    "i2a_review": "Contrôle I2A",
    "mae_followup": "Suivi MAE",
    "systems_validation": "Validation systèmes",
    "quality_review": "Contrôle qualité",
    "active_processing": "Traitement actif",
    "audit_review": "Audit",
}

PROCESS_DETAIL_MODELS = {
    "fund": (
        "csrs.fund.request",
        {
            "budget_line_id",
            "activity_task_id",
            "beneficiary_id",
            "purpose",
            "requires_purchase",
        },
    ),
    "purchase": (
        "csrs.purchase.request",
        {
            "budget_line_id",
            "vendor_id",
            "product_id",
            "quantity",
            "estimated_amount",
        },
    ),
    "absence": (
        "csrs.absence.request",
        {
            "employee_id",
            "start_date",
            "end_date",
            "emergency_contact",
            "interim_user_id",
            "destination",
            "service",
        },
    ),
    "mission": (
        "csrs.mission.order",
        {
            "destination",
            "purpose",
            "departure_date",
            "return_date",
            "transport_mode",
            "vehicle_required",
        },
    ),
    "payment_notice": (
        "csrs.payment.notification",
        {
            "payment_nature",
            "payment_date",
            "sender",
            "sending_bank",
            "receiving_bank",
            "check_number",
            "proof_attachment_id",
        },
    ),
    "visa": (
        "csrs.visa.request",
        {
            "visitor_name",
            "nationality",
            "passport_number",
            "visa_kind",
            "desired_start_date",
            "desired_end_date",
            "mae_reference",
        },
    ),
    "data": (
        "csrs.data.management.case",
        {
            "study_objectives",
            "management_plan",
            "classification",
            "storage_location",
            "retention_until",
            "legal_hold",
            "legal_hold_reason",
        },
    ),
}

PROJECT_ITEM_MODELS = {
    "action_plan": (
        "project.task",
        {
            "name",
            "description",
            "user_ids",
            "csrs_start_date",
            "date_deadline",
            "csrs_estimated_work_days",
        },
    ),
    "results": (
        "csrs.project.result",
        {"sequence", "name", "indicator", "target_value", "achieved_value", "owner_id"},
    ),
    "deliverables": (
        "project.milestone",
        {"name", "deadline", "csrs_version", "csrs_at_risk"},
    ),
    "finance": (
        "csrs.project.budget.line",
        {"code", "name", "activity_task_id", "planned_amount", "active"},
    ),
    "compliance": (
        "csrs.project.compliance",
        {"kind", "description", "owner_id", "due_date", "state", "corrective_action"},
    ),
    "risks": (
        "csrs.project.risk",
        {
            "title",
            "description",
            "probability",
            "impact",
            "owner_id",
            "treatment",
            "residual_risk",
            "state",
        },
    ),
    "reports": (
        "csrs.project.report",
        {
            "title",
            "report_type",
            "period_start",
            "period_end",
            "due_date",
            "state",
            "comments",
        },
    ),
    "closure": (
        "csrs.project.closure",
        {
            "assessment",
            "equipment_disposition",
            "data_disposition",
            "final_balance",
            "outlook",
            "residual_liabilities",
            "sustainability",
        },
    ),
}


def _value(record, field_name):
    field = record._fields[field_name]
    value = record[field_name]
    if field.type == "many2one":
        return value.id or None
    if field.type == "many2many":
        return value.ids
    if field.type in {"date", "datetime"}:
        return value.isoformat() if value else None
    return value


class CsrsApiProjects(models.AbstractModel):
    _inherit = "csrs.api"

    def _project_can_view(self, project):
        user = self.env.user
        return bool(
            user.has_group("csrs_reporting.group_csrs_dg")
            or user.has_group("csrs_reporting.group_csrs_it")
            or user
            in (
                project.csrs_proposer_id
                | project.csrs_lead_id
                | project.csrs_team_user_ids
            )
        )

    def _project_can_edit(self, project):
        user = self.env.user
        return bool(
            user.has_group("csrs_reporting.group_csrs_dg")
            or user == project.csrs_lead_id
            or (project.csrs_state == "proposal" and user == project.csrs_proposer_id)
        )

    def _project_record(self, project_id):
        project = (
            self.env["project.project"]
            .sudo()
            .browse(int(project_id))
            .exists()
            .filtered("csrs_research_project")
        )
        if not project or not self._project_can_view(project):
            raise UserError(_("Projet introuvable."))
        return project

    def _project_summary(self, project):
        return {
            "id": project.id,
            "reference": project.csrs_reference,
            "name": project.name,
            "state": project.csrs_state,
            "state_label": PROJECT_STATE_LABELS[project.csrs_state],
            "revision": project.csrs_revision,
            "proposer": self._person(project.csrs_proposer_id),
            "lead": self._person(project.csrs_lead_id) if project.csrs_lead_id else None,
            "date_start": project.date_start.isoformat() if project.date_start else None,
            "date_end": project.date.isoformat() if project.date else None,
            "capabilities": {
                "edit": self._project_can_edit(project),
                "approve": project.csrs_state == "proposal"
                and self.env.user.has_group("csrs_reporting.group_csrs_dg"),
                "reject": project.csrs_state == "proposal"
                and self.env.user.has_group("csrs_reporting.group_csrs_dg"),
                "close": project.csrs_state == "active"
                and self.env.user.has_group("csrs_reporting.group_csrs_dg"),
            },
        }

    def _project_detail(self, project):
        sections = []
        labels = dict(SECTION_CODES)
        for section in project.csrs_section_ids.sorted("id"):
            current_section = section.with_user(self.env.user)
            sections.append(
                {
                    "id": section.id,
                    "code": section.code,
                    "label": labels[section.code],
                    "state": section.state,
                    "revision": section.revision,
                    "correction_reason": section.correction_reason or "",
                    "capabilities": {
                        "submit": self._project_can_edit(project)
                        and section.state in {"draft", "correction"},
                        "verify": current_section._can_control()
                        and section.state == "submitted",
                        "correct": current_section._can_control()
                        and section.state in {"submitted", "verified"},
                        "validate": self.env.user.has_group(
                            "csrs_reporting.group_csrs_dg"
                        )
                        and section.state == "verified",
                        "close": self.env.user.has_group("csrs_reporting.group_csrs_dg")
                        and section.state == "validated",
                    },
                }
            )
        return {
            **self._project_summary(project),
            "objectives": project.csrs_objectives or "",
            "institutional_commitments": project.csrs_institutional_commitments or "",
            "team": [self._person(user) for user in project.csrs_team_user_ids],
            "donor": {
                "id": project.csrs_donor_id.id,
                "name": project.csrs_donor_id.name,
            }
            if project.csrs_donor_id
            else None,
            "partners": [
                {"id": partner.id, "name": partner.name}
                for partner in project.csrs_partner_ids
            ],
            "sections": sections,
            "action_plan": [
                {
                    "id": task.id,
                    "name": task.name,
                    "assignees": [self._person(user) for user in task.user_ids],
                    "start_date": task.csrs_start_date.isoformat()
                    if task.csrs_start_date
                    else None,
                    "deadline": task.date_deadline.date().isoformat()
                    if task.date_deadline
                    else None,
                    "estimated_work_days": task.csrs_estimated_work_days,
                    "progress": task.csrs_progress_percent,
                    "blocked": task.csrs_blocked,
                    "status": task.csrs_status,
                    "values": {
                        name: (
                            task.date_deadline.date().isoformat()
                            if name == "date_deadline" and task.date_deadline
                            else _value(task, name)
                        )
                        for name in PROJECT_ITEM_MODELS["action_plan"][1]
                    },
                }
                for task in self.env["project.task"]
                .sudo()
                .search(
                    [("project_id", "=", project.id), ("csrs_managed", "=", True)],
                    order="csrs_start_date, id",
                )
            ],
            "budget": [
                {
                    "id": line.id,
                    "code": line.code,
                    "name": line.name,
                    "planned_amount": line.planned_amount,
                    "committed_amount": line.committed_amount,
                    "actual_amount": line.actual_amount,
                    "available_amount": line.available_amount,
                    "values": {
                        name: _value(line, name)
                        for name in PROJECT_ITEM_MODELS["finance"][1]
                    },
                }
                for line in project.csrs_budget_line_ids
            ],
            "risks": [
                {
                    "id": risk.id,
                    "title": risk.title,
                    "severity": risk.severity,
                    "state": risk.state,
                    "values": {
                        name: _value(risk, name)
                        for name in PROJECT_ITEM_MODELS["risks"][1]
                    },
                }
                for risk in project.csrs_risk_ids
            ],
            "results": [
                {
                    "id": result.id,
                    "name": result.name,
                    "indicator": result.indicator,
                    "target_value": result.target_value,
                    "achieved_value": result.achieved_value or "",
                    "values": {
                        name: _value(result, name)
                        for name in PROJECT_ITEM_MODELS["results"][1]
                    },
                }
                for result in project.csrs_result_ids
            ],
            "deliverables": [
                {
                    "id": item.id,
                    "name": item.name,
                    "deadline": item.deadline.isoformat() if item.deadline else None,
                    "version": item.csrs_version or "",
                    "at_risk": item.csrs_at_risk,
                    "values": {
                        name: _value(item, name)
                        for name in PROJECT_ITEM_MODELS["deliverables"][1]
                    },
                }
                for item in self.env["project.milestone"]
                .sudo()
                .search(
                    [
                        ("project_id", "=", project.id),
                        ("csrs_deliverable", "=", True),
                    ]
                )
            ],
            "compliance": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "description": item.description,
                    "state": item.state,
                    "due_date": item.due_date.isoformat() if item.due_date else None,
                    "values": {
                        name: _value(item, name)
                        for name in PROJECT_ITEM_MODELS["compliance"][1]
                    },
                }
                for item in project.csrs_compliance_item_ids
            ],
            "reports": [
                {
                    "id": item.id,
                    "title": item.title,
                    "report_type": item.report_type,
                    "state": item.state,
                    "due_date": item.due_date.isoformat(),
                    "values": {
                        name: _value(item, name)
                        for name in PROJECT_ITEM_MODELS["reports"][1]
                    },
                }
                for item in project.csrs_report_ids
            ],
            "closure": [
                {
                    "id": item.id,
                    "assessment": item.assessment,
                    "values": {
                        name: _value(item, name)
                        for name in PROJECT_ITEM_MODELS["closure"][1]
                    },
                }
                for item in project.csrs_closure_id
            ],
        }

    @api.model
    def api_research_projects(self):
        projects = (
            self.env["project.project"]
            .sudo()
            .search(
                [("csrs_research_project", "=", True)], order="create_date desc, id desc"
            )
        )
        return {
            "items": [
                self._project_summary(project)
                for project in projects
                if self._project_can_view(project)
            ]
        }

    @api.model
    def api_research_project_options(self):
        users = (
            self.env["res.users"]
            .sudo()
            .search([("active", "=", True), ("share", "=", False)], order="name, id")
        )
        return {"users": [self._person(user) for user in users]}

    def _project_users(self, user_ids):
        normalized = tuple(sorted({int(user_id) for user_id in (user_ids or [])}))
        users = self.env["res.users"].sudo().browse(normalized).exists()
        if len(users) != len(normalized) or any(
            not user.active or user.share for user in users
        ):
            raise ValidationError(_("Un membre de l'équipe est invalide."))
        return users

    def _project_partner(self, name):
        normalized = str(name or "").strip()
        if not normalized:
            return self.env["res.partner"]
        partner = (
            self.env["res.partner"]
            .sudo()
            .search([("name", "=ilike", normalized), ("is_company", "=", True)], limit=1)
        )
        return partner or self.env["res.partner"].sudo().create(
            {"name": normalized, "is_company": True}
        )

    @api.model
    def api_research_project_create(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_("Projet invalide."))
        name = str(payload.get("name") or "").strip()
        objectives = str(payload.get("objectives") or "").strip()
        if not name or not objectives:
            raise ValidationError(_("Le nom et les objectifs sont obligatoires."))
        team = self._project_users(payload.get("team_user_ids"))
        donor = self._project_partner(payload.get("donor_name"))
        partners = self.env["res.partner"]
        for partner_name in payload.get("partner_names") or []:
            partners |= self._project_partner(partner_name)
        project = self.env["project.project"].create(
            {
                "name": name,
                "csrs_research_project": True,
                "csrs_objectives": objectives,
                "csrs_institutional_commitments": str(
                    payload.get("institutional_commitments") or ""
                ).strip(),
                "date_start": fields.Date.to_date(payload.get("date_start"))
                if payload.get("date_start")
                else False,
                "date": fields.Date.to_date(payload.get("date_end"))
                if payload.get("date_end")
                else False,
                "csrs_team_user_ids": [Command.set(team.ids)],
                "csrs_donor_id": donor.id or False,
                "csrs_partner_ids": [Command.set(partners.ids)],
            }
        )
        return self._project_detail(project.sudo())

    @api.model
    def api_research_project(self, project_id):
        return self._project_detail(self._project_record(project_id))

    @api.model
    def api_research_project_update(self, project_id, payload):
        project = self._project_record(project_id)
        if not self._project_can_edit(project):
            raise AccessError(_("Vous ne pouvez pas modifier ce projet."))
        project._csrs_check_revision(payload.get("revision"))
        team = self._project_users(
            payload.get("team_user_ids", project.csrs_team_user_ids.ids)
        )
        donor = self._project_partner(
            payload.get("donor_name", project.csrs_donor_id.name)
        )
        partners = self.env["res.partner"]
        partner_names = payload.get(
            "partner_names", project.csrs_partner_ids.mapped("name")
        )
        for partner_name in partner_names or []:
            partners |= self._project_partner(partner_name)
        values = {
            "name": str(payload.get("name") or "").strip(),
            "csrs_objectives": str(payload.get("objectives") or "").strip(),
            "csrs_institutional_commitments": str(
                payload.get("institutional_commitments") or ""
            ).strip(),
            "date_start": fields.Date.to_date(payload.get("date_start"))
            if payload.get("date_start")
            else False,
            "date": fields.Date.to_date(payload.get("date_end"))
            if payload.get("date_end")
            else False,
            "csrs_revision": project.csrs_revision + 1,
            "csrs_team_user_ids": [Command.set(team.ids)],
            "csrs_donor_id": donor.id or False,
            "csrs_partner_ids": [Command.set(partners.ids)],
        }
        if not values["name"] or not values["csrs_objectives"]:
            raise ValidationError(_("Le nom et les objectifs sont obligatoires."))
        project.with_context(csrs_authorized_mutation=True).write(values)
        return self._project_detail(project)

    @api.model
    def api_research_project_transition(self, project_id, payload):
        project = self._project_record(project_id).with_user(self.env.user)
        action = str(payload.get("action") or "")
        revision = payload.get("revision")
        if action == "approve":
            project.action_csrs_approve(payload.get("lead_id"), revision)
        elif action == "reject":
            project.action_csrs_reject(payload.get("reason"), revision)
        elif action == "close":
            project.action_csrs_close(revision)
        else:
            raise ValidationError(_("Transition de projet invalide."))
        return self._project_detail(project.sudo())

    @api.model
    def api_research_project_section_transition(self, project_id, section_id, payload):
        project = self._project_record(project_id)
        section = project.csrs_section_ids.filtered(
            lambda item: item.id == int(section_id)
        )
        if not section:
            raise UserError(_("Onglet introuvable."))
        section = section.with_user(self.env.user)
        action = str(payload.get("action") or "")
        revision = payload.get("revision")
        if action == "submit":
            section.action_submit(revision)
        elif action == "verify":
            section.action_verify(revision)
        elif action == "correct":
            section.action_request_correction(payload.get("reason"), revision)
        elif action == "validate":
            section.action_validate(payload.get("confirmation"), revision)
        elif action == "close":
            section.action_close(revision)
        else:
            raise ValidationError(_("Transition d'onglet invalide."))
        return self._project_detail(project)

    @api.model
    def api_research_project_item_save(self, project_id, resource, payload, item_id=None):
        project = self._project_record(project_id)
        if not self._project_can_edit(project):
            raise AccessError(_("Vous ne pouvez pas modifier ce projet."))
        if resource not in PROJECT_ITEM_MODELS or not isinstance(payload, dict):
            raise ValidationError(_("Ressource de projet invalide."))
        project._csrs_check_revision(payload.get("revision"))
        item_values = payload.get("values")
        if not isinstance(item_values, dict):
            raise ValidationError(_("Élément de projet invalide."))
        section = project.csrs_section_ids.filtered(lambda item: item.code == resource)
        if section and section.state in {"validated", "closed"}:
            raise UserError(_("Cet onglet validé est désormais immuable."))
        model_name, allowed = PROJECT_ITEM_MODELS[resource]
        unknown = set(item_values) - allowed
        if unknown:
            raise ValidationError(_("Champ de projet invalide."))
        values = dict(item_values)
        values["project_id"] = project.id
        if resource == "deliverables":
            values["csrs_deliverable"] = True
        elif resource == "action_plan":
            assignees = self._project_users(values.pop("user_ids", []))
            allowed_assignees = (
                project.csrs_team_user_ids
                | project.csrs_proposer_id
                | project.csrs_lead_id
            )
            if assignees - allowed_assignees:
                raise ValidationError(
                    _("Une activité ne peut être confiée qu'à l'équipe projet.")
                )
            values.update(
                {
                    "user_ids": [Command.set(assignees.ids)],
                    "csrs_managed": True,
                    "csrs_manager_id": (
                        project.csrs_lead_id or project.csrs_proposer_id
                    ).id,
                    "csrs_calendar_id": self.env.company.resource_calendar_id.id,
                }
            )
        Model = self.env[model_name].sudo()
        if item_id:
            record = Model.browse(int(item_id)).exists()
            if not record or record.project_id != project:
                raise UserError(_("Élément de projet introuvable."))
            if resource == "action_plan":
                values["csrs_revision"] = record.csrs_revision + 1
                record.with_context(csrs_authorized_mutation=True).write(values)
            else:
                record.write(values)
        else:
            record = Model.create(values)
        project.with_context(csrs_authorized_mutation=True).write(
            {"csrs_revision": project.csrs_revision + 1}
        )
        return self._project_detail(project)

    def _process_can_view(self, case):
        user = self.env.user
        governance_groups = (
            "csrs_reporting.group_csrs_hr",
            "csrs_reporting.group_csrs_secretariat",
            "csrs_reporting.group_csrs_dg",
            "csrs_reporting.group_csrs_finance",
            "csrs_reporting.group_csrs_procurement",
            "csrs_reporting.group_csrs_compliance",
            "csrs_reporting.group_csrs_data_manager",
            "csrs_reporting.group_csrs_fleet",
            "csrs_reporting.group_csrs_it",
        )
        return bool(
            user == case.requester_id
            or any(user.has_group(xmlid) for xmlid in governance_groups)
            or case.with_user(user)._can_handle()
        )

    def _process_record(self, case_id):
        case = self.env["csrs.process.case"].sudo().browse(int(case_id)).exists()
        if not case or not self._process_can_view(case):
            raise UserError(_("Dossier introuvable."))
        return case

    def _process_detail_values(self, case):
        model_name, allowed = PROCESS_DETAIL_MODELS[case.process_type]
        detail = self.env[model_name].sudo().search([("case_id", "=", case.id)], limit=1)
        if not detail:
            return {}
        return {name: _value(detail, name) for name in sorted(allowed)}

    def _process_summary(self, case, detail=False):
        type_labels = dict(PROCESS_TYPES)
        transitions = TRANSITIONS[case.process_type]
        actions = [action for state, action in transitions if state == case.state]
        can_handle = case.with_user(self.env.user)._can_handle()
        if can_handle and case.state in CORRECTABLE_STATES:
            actions.extend(["correct", "reject"])
        if can_handle and case.state == "correction":
            actions.append("resubmit")
        payload = {
            "id": case.id,
            "reference": case.reference,
            "process_type": case.process_type,
            "process_type_label": type_labels[case.process_type],
            "state": case.state,
            "state_label": PROCESS_STATE_LABELS.get(case.state, case.state),
            "revision": case.revision,
            "subject": case.subject,
            "description": case.description,
            "amount": case.amount,
            "currency": case.currency_id.name,
            "requester": self._person(case.requester_id),
            "origin_department": {
                "id": case.origin_department_id.id,
                "name": case.origin_department_id.name,
            },
            "project": {
                "id": case.project_id.id,
                "reference": case.project_id.csrs_reference,
                "name": case.project_id.name,
            }
            if case.project_id
            else None,
            "correction_reason": case.correction_reason or "",
            "available_actions": actions if can_handle else [],
        }
        if detail:
            payload["details"] = self._process_detail_values(case)
            payload["events"] = [
                {
                    "id": event.id,
                    "action": event.action,
                    "from_state": event.from_state,
                    "to_state": event.to_state,
                    "note": event.note or "",
                    "actor": self._person(event.actor_id),
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in case.event_ids
            ]
        return payload

    @api.model
    def api_process_options(self):
        current_employee = self._employee_for_user(self.env.user)
        projects = (
            self.env["project.project"]
            .sudo()
            .search(
                [("csrs_research_project", "=", True), ("csrs_state", "=", "active")],
                order="name",
            )
        )
        employees = (
            self.env["hr.employee"]
            .sudo()
            .search([("user_id", "!=", False), ("active", "=", True)], order="name")
        )
        return {
            "default_department_id": current_employee.department_id.id
            if current_employee
            else None,
            "process_types": [
                {"value": value, "label": label} for value, label in PROCESS_TYPES
            ],
            "departments": [
                {"id": item.id, "name": item.name}
                for item in self.env["hr.department"]
                .sudo()
                .search([("active", "=", True)], order="name")
            ],
            "projects": [
                {
                    "id": project.id,
                    "reference": project.csrs_reference,
                    "name": project.name,
                    "budget_lines": [
                        {
                            "id": line.id,
                            "code": line.code,
                            "name": line.name,
                            "available_amount": line.available_amount,
                        }
                        for line in project.csrs_budget_line_ids.filtered("active")
                    ],
                }
                for project in projects
                if self._project_can_view(project)
            ],
            "people": [
                {
                    **self._person(employee.user_id),
                    "employee_id": employee.id,
                    "partner_id": employee.user_id.partner_id.id,
                }
                for employee in employees
            ],
        }

    @api.model
    def api_processes(self):
        cases = self.env["csrs.process.case"].sudo().search([])
        return {
            "items": [
                self._process_summary(case)
                for case in cases
                if self._process_can_view(case)
            ]
        }

    @api.model
    def api_process_create(self, payload):
        if not isinstance(payload, dict) or payload.get("process_type") not in dict(
            PROCESS_TYPES
        ):
            raise ValidationError(_("Type de processus invalide."))
        employee = self._employee_for_user(self.env.user)
        department_id = int(payload.get("origin_department_id") or 0)
        if not employee or (
            department_id != employee.department_id.id
            and not self.env.user.has_group("csrs_reporting.group_csrs_it")
        ):
            raise AccessError(_("L'unité d'origine n'est pas autorisée."))
        project_id = int(payload.get("project_id") or 0)
        if project_id:
            self._project_record(project_id)
        subject = str(payload.get("subject") or "").strip()
        description = str(payload.get("description") or "").strip()
        if not subject or not description:
            raise ValidationError(_("L'objet et la description sont obligatoires."))
        case = self.env["csrs.process.case"].create(
            {
                "process_type": payload["process_type"],
                "origin_department_id": department_id,
                "project_id": project_id or False,
                "subject": subject,
                "description": description,
                "amount": float(payload.get("amount") or 0),
            }
        )
        details = payload.get("details")
        if not isinstance(details, dict):
            raise ValidationError(_("Les détails du formulaire sont obligatoires."))
        model_name, allowed = PROCESS_DETAIL_MODELS[case.process_type]
        unknown = set(details) - allowed
        if unknown:
            raise ValidationError(_("Champ de formulaire de processus invalide."))
        detail_values = {"case_id": case.id, **details}
        attachments = []
        for document in payload.get("documents") or []:
            if not isinstance(document, dict):
                raise ValidationError(_("Document de processus invalide."))
            attachments.append(
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": str(document.get("name") or "document"),
                        "mimetype": str(
                            document.get("mimetype") or "application/octet-stream"
                        ),
                        "datas": document.get("content_base64"),
                        "res_model": "csrs.process.case",
                        "res_id": case.id,
                    }
                )
            )
        if attachments:
            case.sudo().write(
                {"attachment_ids": [Command.link(item.id) for item in attachments]}
            )
        if case.process_type == "payment_notice" and attachments:
            detail_values.setdefault("proof_attachment_id", attachments[0].id)
        if case.process_type == "fund":
            detail_values["initiator_id"] = self.env.user.id
        self.env[model_name].sudo().create(detail_values)
        return self._process_summary(case.sudo(), detail=True)

    @api.model
    def api_process(self, case_id):
        return self._process_summary(self._process_record(case_id), detail=True)

    @api.model
    def api_process_transition(self, case_id, payload):
        case = self._process_record(case_id).with_user(self.env.user)
        case.action_transition(
            payload.get("action"),
            payload.get("revision"),
            note=payload.get("note") or "",
            confirmation=payload.get("confirmation") or "",
        )
        return self._process_summary(case.sudo(), detail=True)
