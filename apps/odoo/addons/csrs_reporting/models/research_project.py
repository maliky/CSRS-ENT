"""Research-project governance built on Odoo project and accounting models."""

from hashlib import sha256
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command


SECTION_CODES = (
    ("project", "Projet"),
    ("action_plan", "Plan d'action"),
    ("results", "Résultats"),
    ("deliverables", "Livrables"),
    ("finance", "Finances"),
    ("compliance", "Conformité"),
    ("risks", "Risques"),
    ("reports", "Rapports"),
    ("closure", "Clôture"),
)

SECTION_STATES = (
    ("draft", "Brouillon"),
    ("submitted", "Soumis"),
    ("correction", "À corriger"),
    ("verified", "Vérifié"),
    ("validated", "Validé"),
    ("closed", "Clôturé"),
)

SECTION_CONTROLLER_ROLES = {
    "project": "PROJECT_CONTROLLER",
    "action_plan": "PROJECT_CONTROLLER",
    "results": "PROJECT_CONTROLLER",
    "deliverables": "PROJECT_CONTROLLER",
    "finance": "PROJECT_FINANCE",
    "compliance": "PROJECT_COMPLIANCE",
    "risks": "PROJECT_CONTROLLER",
    "reports": "PROJECT_CONTROLLER",
    "closure": "PROJECT_CONTROLLER",
}


class ProjectProject(models.Model):
    _inherit = "project.project"

    csrs_research_project = fields.Boolean(
        string="Projet de recherche CSRS", default=False, index=True, copy=False
    )
    csrs_reference = fields.Char(readonly=True, copy=False, index=True)
    csrs_proposer_id = fields.Many2one(
        "res.users", string="Proposé par", readonly=True, copy=False, index=True
    )
    csrs_lead_id = fields.Many2one(
        "res.users", string="Chef de projet", tracking=True, index=True
    )
    csrs_team_user_ids = fields.Many2many(
        "res.users",
        "csrs_research_project_team_rel",
        "project_id",
        "user_id",
        string="Équipe de recherche",
        tracking=True,
        copy=False,
    )
    csrs_donor_id = fields.Many2one(
        "res.partner", string="Bailleur", tracking=True, ondelete="restrict"
    )
    csrs_partner_ids = fields.Many2many(
        "res.partner",
        "csrs_research_project_partner_rel",
        "project_id",
        "partner_id",
        string="Partenaires",
        copy=False,
    )
    csrs_objectives = fields.Text(string="Objectifs", tracking=True)
    csrs_institutional_commitments = fields.Text(
        string="Engagements institutionnels", tracking=True
    )
    csrs_state = fields.Selection(
        [
            ("proposal", "Proposition"),
            ("active", "Actif"),
            ("rejected", "Rejeté"),
            ("closed", "Clôturé"),
        ],
        string="État CSRS",
        default="proposal",
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )
    csrs_revision = fields.Integer(default=1, required=True, readonly=True, copy=False)
    csrs_section_ids = fields.One2many(
        "csrs.project.section", "project_id", string="Contrôles des onglets", copy=False
    )
    csrs_result_ids = fields.One2many(
        "csrs.project.result", "project_id", string="Résultats", copy=False
    )
    csrs_budget_line_ids = fields.One2many(
        "csrs.project.budget.line", "project_id", string="Budget", copy=False
    )
    csrs_compliance_item_ids = fields.One2many(
        "csrs.project.compliance", "project_id", string="Conformité", copy=False
    )
    csrs_risk_ids = fields.One2many(
        "csrs.project.risk", "project_id", string="Risques", copy=False
    )
    csrs_report_ids = fields.One2many(
        "csrs.project.report", "project_id", string="Rapports", copy=False
    )
    csrs_closure_id = fields.One2many(
        "csrs.project.closure", "project_id", string="Clôture", copy=False
    )

    _csrs_reference_unique = models.Constraint(
        "UNIQUE (csrs_reference)", "Cette référence de projet est déjà utilisée."
    )

    def _csrs_is_dg(self):
        return self.env.user.has_group("csrs_reporting.group_csrs_dg")

    def _csrs_is_it(self):
        return self.env.user.has_group("csrs_reporting.group_csrs_it")

    def _csrs_can_view(self):
        self.ensure_one()
        user = self.env.user
        if self._csrs_is_dg() or self._csrs_is_it():
            return True
        if user in (self.csrs_proposer_id | self.csrs_lead_id | self.csrs_team_user_ids):
            return True
        member_employees = (
            self.env["hr.employee"]
            .sudo()
            .search([("user_id", "in", self.csrs_team_user_ids.ids)])
        )
        return any(
            user in employee.parent_id.user_id
            or user in employee.parent_id.parent_id.user_id
            for employee in member_employees
        )

    def _csrs_can_edit(self):
        self.ensure_one()
        return (
            self.env.user == self.csrs_lead_id
            or (self.csrs_state == "proposal" and self.env.user == self.csrs_proposer_id)
            or self._csrs_is_dg()
        )

    def _csrs_check_revision(self, expected_revision):
        self.ensure_one()
        if expected_revision is not None and self.csrs_revision != int(expected_revision):
            raise UserError(_("Le projet a changé. Rechargez-le avant de continuer."))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("csrs_research_project"):
                if not self.env.user.has_group("project.group_project_manager"):
                    raise AccessError(
                        _("Seuls les projets de recherche CSRS sont autorisés.")
                    )
                continue
            proposer_id = values.get("csrs_proposer_id") or self.env.user.id
            if proposer_id != self.env.user.id and not self.env.user.has_group(
                "csrs_reporting.group_csrs_it"
            ):
                raise AccessError(
                    _("Vous ne pouvez proposer un projet que pour vous-même.")
                )
            values["csrs_proposer_id"] = proposer_id
            values.setdefault(
                "csrs_reference",
                self.env["ir.sequence"].next_by_code("csrs.research.project"),
            )
            values.setdefault("privacy_visibility", "followers")
        projects = super().create(values_list)
        Section = self.env["csrs.project.section"].sudo()
        for project in projects.filtered("csrs_research_project"):
            existing = set(project.csrs_section_ids.mapped("code"))
            Section.create(
                [
                    {"project_id": project.id, "code": code}
                    for code, _label in SECTION_CODES
                    if code not in existing
                ]
            )
            if project.csrs_proposer_id.partner_id:
                project.message_subscribe(project.csrs_proposer_id.partner_id.ids)
        return projects

    def action_csrs_approve(self, lead_id, expected_revision=None):
        self.ensure_one()
        if not self._csrs_is_dg():
            raise AccessError(_("Seul le DG peut autoriser un projet de recherche."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_state != "proposal":
            raise UserError(_("Seule une proposition peut être autorisée."))
        lead = self.env["res.users"].browse(int(lead_id)).exists()
        if not lead or not lead.active or lead.share:
            raise ValidationError(_("Chef de projet invalide."))
        account = self.account_id
        if not account:
            analytic_plan = self.env.ref("analytic.analytic_plan_projects")
            account = (
                self.env["account.analytic.account"]
                .sudo()
                .create(
                    {
                        "name": f"{self.csrs_reference} — {self.name}",
                        "plan_id": analytic_plan.id,
                        "company_id": (self.company_id or self.env.company).id,
                        "partner_id": self.csrs_donor_id.id or False,
                    }
                )
            )
        self.sudo().with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_lead_id": lead.id,
                "csrs_team_user_ids": [Command.link(lead.id)],
                "csrs_state": "active",
                "csrs_revision": self.csrs_revision + 1,
                "account_id": account.id,
                "user_id": lead.id,
            }
        )
        self.sudo().message_subscribe(lead.partner_id.ids)
        self.sudo().message_post(
            body=_("Projet autorisé par la Direction générale."),
            author_id=self.env.user.partner_id.id,
        )
        return True

    def action_csrs_reject(self, reason, expected_revision=None):
        self.ensure_one()
        if not self._csrs_is_dg():
            raise AccessError(_("Seul le DG peut rejeter une proposition de projet."))
        self._csrs_check_revision(expected_revision)
        reason = str(reason or "").strip()
        if not reason:
            raise ValidationError(_("Le motif de rejet est obligatoire."))
        self.sudo().with_context(csrs_authorized_mutation=True).write(
            {"csrs_state": "rejected", "csrs_revision": self.csrs_revision + 1}
        )
        self.sudo().message_post(body=reason, author_id=self.env.user.partner_id.id)
        return True

    def action_csrs_close(self, expected_revision=None):
        self.ensure_one()
        if not self._csrs_is_dg():
            raise AccessError(_("Seul le DG peut clôturer un projet."))
        self._csrs_check_revision(expected_revision)
        sections = self.csrs_section_ids
        if len(sections) != len(SECTION_CODES) or any(
            state != "closed" for state in sections.mapped("state")
        ):
            raise UserError(_("Tous les onglets doivent être clôturés."))
        self.sudo().with_context(csrs_authorized_mutation=True).write(
            {"csrs_state": "closed", "csrs_revision": self.csrs_revision + 1}
        )
        return True

    def write(self, values):
        protected = {"csrs_state", "csrs_revision", "csrs_reference"}
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une action métier du projet."))
        if not self.env.context.get("csrs_authorized_mutation"):
            if self.filtered(lambda item: not item.csrs_research_project) and not (
                self.env.user.has_group("project.group_project_manager")
            ):
                raise AccessError(_("Ce projet n'est pas administré par CSRS ENT."))
            for project in self.filtered("csrs_research_project"):
                if not project._csrs_can_edit():
                    raise AccessError(_("Vous ne pouvez pas modifier ce projet."))
        return super().write(values)


class CsrsProjectSection(models.Model):
    _name = "csrs.project.section"
    _description = "Cycle de validation d'un onglet de projet"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "project_id, id"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    code = fields.Selection(SECTION_CODES, required=True, index=True)
    state = fields.Selection(
        SECTION_STATES, default="draft", required=True, tracking=True, index=True
    )
    revision = fields.Integer(default=1, required=True, readonly=True, copy=False)
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True, copy=False)
    validated_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    validated_at = fields.Datetime(readonly=True, copy=False)
    correction_reason = fields.Text(readonly=True, copy=False)
    approval_ids = fields.One2many(
        "csrs.project.approval", "section_id", string="Approbations", copy=False
    )

    _project_code_unique = models.Constraint(
        "UNIQUE (project_id, code)", "Cet onglet existe déjà pour ce projet."
    )

    def _check_revision(self, expected_revision):
        self.ensure_one()
        if expected_revision is not None and self.revision != int(expected_revision):
            raise UserError(_("L'onglet a changé. Rechargez-le avant de continuer."))

    def _can_control(self):
        self.ensure_one()
        role = SECTION_CONTROLLER_ROLES[self.code]
        return self.env.user.csrs_has_active_role_grant(role) or self.env.user.has_group(
            "csrs_reporting.group_csrs_dg"
        )

    def _transition(self, values, message):
        self.ensure_one()
        author = self.env.user.partner_id
        values["revision"] = self.revision + 1
        self.sudo().with_context(csrs_authorized_mutation=True).write(values)
        self.sudo().message_post(body=message, author_id=author.id)
        return True

    def action_submit(self, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        if not self.project_id._csrs_can_edit():
            raise AccessError(_("Seul le chef de projet peut soumettre cet onglet."))
        if self.state not in {"draft", "correction"}:
            raise UserError(_("Cet onglet ne peut pas être soumis dans cet état."))
        return self._transition(
            {
                "state": "submitted",
                "submitted_by_id": self.env.user.id,
                "submitted_at": fields.Datetime.now(),
                "correction_reason": False,
            },
            _("Onglet soumis pour contrôle."),
        )

    def action_request_correction(self, reason, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        reason = str(reason or "").strip()
        if not self._can_control():
            raise AccessError(_("Vous ne pouvez pas demander cette correction."))
        if self.state not in {"submitted", "verified"}:
            raise UserError(_("Cet onglet ne peut pas être corrigé dans cet état."))
        if not reason:
            raise ValidationError(_("Le motif de correction est obligatoire."))
        return self._transition(
            {"state": "correction", "correction_reason": reason}, reason
        )

    def action_verify(self, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        if not self._can_control():
            raise AccessError(_("Vous ne pouvez pas vérifier cet onglet."))
        if self.state != "submitted":
            raise UserError(_("Seul un onglet soumis peut être vérifié."))
        return self._transition(
            {
                "state": "verified",
                "verified_by_id": self.env.user.id,
                "verified_at": fields.Datetime.now(),
            },
            _("Onglet vérifié."),
        )

    def _signature_snapshot(self):
        self.ensure_one()
        attachments = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "project.project"),
                    ("res_id", "=", self.project_id.id),
                ]
            )
        )
        return {
            "project_id": self.project_id.id,
            "project_reference": self.project_id.csrs_reference,
            "project_revision": self.project_id.csrs_revision,
            "section": self.code,
            "section_revision": self.revision,
            "write_date": fields.Datetime.to_string(self.write_date),
            "attachments": [
                {"id": item.id, "name": item.name, "checksum": item.checksum or ""}
                for item in attachments.sorted("id")
            ],
        }

    def action_validate(self, confirmation, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        if not self.env.user.has_group("csrs_reporting.group_csrs_dg"):
            raise AccessError(_("Seul le DG peut valider cet onglet."))
        if self.state != "verified":
            raise UserError(_("Seul un onglet vérifié peut être validé."))
        expected = f"VALIDÉ LE {fields.Date.context_today(self):%d/%m/%Y}"
        if str(confirmation or "").strip() != expected:
            raise ValidationError(_("Saisissez exactement : %s", expected))
        snapshot = self._signature_snapshot()
        digest = sha256(
            json.dumps(snapshot, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest()
        approval = (
            self.env["csrs.project.approval"]
            .sudo()
            .create(
                {
                    "section_id": self.id,
                    "signer_id": self.env.user.id,
                    "confirmation": expected,
                    "snapshot": snapshot,
                    "snapshot_sha256": digest,
                }
            )
        )
        self._transition(
            {
                "state": "validated",
                "validated_by_id": self.env.user.id,
                "validated_at": fields.Datetime.now(),
            },
            _("Onglet validé électroniquement."),
        )
        return approval.id

    def action_close(self, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        if not self.env.user.has_group("csrs_reporting.group_csrs_dg"):
            raise AccessError(_("Seul le DG peut clôturer cet onglet."))
        if self.state != "validated":
            raise UserError(_("Seul un onglet validé peut être clôturé."))
        return self._transition({"state": "closed"}, _("Onglet clôturé."))

    def unlink(self):
        raise UserError(_("Un cycle de validation ne peut pas être supprimé."))

    def write(self, values):
        protected = {
            "state",
            "revision",
            "submitted_by_id",
            "submitted_at",
            "verified_by_id",
            "verified_at",
            "validated_by_id",
            "validated_at",
            "correction_reason",
        }
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une transition de l'onglet."))
        return super().write(values)


class CsrsProjectApproval(models.Model):
    _name = "csrs.project.approval"
    _description = "Approbation électronique d'un onglet de projet"
    _order = "signed_at desc, id desc"

    section_id = fields.Many2one(
        "csrs.project.section", required=True, ondelete="restrict", index=True
    )
    signer_id = fields.Many2one(
        "res.users", required=True, readonly=True, ondelete="restrict", index=True
    )
    confirmation = fields.Char(required=True, readonly=True)
    snapshot = fields.Json(required=True, readonly=True)
    snapshot_sha256 = fields.Char(required=True, readonly=True, index=True)
    signed_at = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.is_superuser():
            raise AccessError(_("Utilisez l'action de validation de l'onglet."))
        return super().create(values_list)

    def write(self, values):
        raise UserError(_("Une approbation électronique est immuable."))

    def unlink(self):
        raise UserError(_("Une approbation électronique est immuable."))


class CsrsProjectResult(models.Model):
    _name = "csrs.project.result"
    _description = "Résultat d'un projet de recherche"
    _order = "project_id, sequence, id"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    indicator = fields.Char(required=True)
    target_value = fields.Char(required=True)
    achieved_value = fields.Char()
    owner_id = fields.Many2one("res.users", ondelete="restrict", index=True)
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "csrs_project_result_attachment_rel",
        "result_id",
        "attachment_id",
    )


class ProjectMilestone(models.Model):
    _inherit = "project.milestone"

    csrs_deliverable = fields.Boolean(default=False, index=True)
    csrs_version = fields.Char(string="Version")
    csrs_at_risk = fields.Boolean(string="À risque", default=False, tracking=True)
    csrs_evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "csrs_milestone_attachment_rel",
        "milestone_id",
        "attachment_id",
        string="Preuves",
    )


class CsrsProjectBudgetLine(models.Model):
    _name = "csrs.project.budget.line"
    _description = "Ligne budgétaire d'un projet de recherche"
    _order = "project_id, code, id"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    activity_task_id = fields.Many2one(
        "project.task", ondelete="restrict", domain="[('project_id', '=', project_id)]"
    )
    currency_id = fields.Many2one(related="project_id.currency_id", readonly=True)
    planned_amount = fields.Monetary(required=True, currency_field="currency_id")
    committed_amount = fields.Monetary(
        default=0, readonly=True, currency_field="currency_id"
    )
    actual_amount = fields.Monetary(
        compute="_compute_amounts", currency_field="currency_id"
    )
    available_amount = fields.Monetary(
        compute="_compute_amounts", currency_field="currency_id"
    )
    active = fields.Boolean(default=True)

    _project_code_unique = models.Constraint(
        "UNIQUE (project_id, code)", "Ce code budgétaire existe déjà dans le projet."
    )
    _planned_non_negative = models.Constraint(
        "CHECK (planned_amount >= 0)", "Le budget prévu ne peut pas être négatif."
    )

    @api.depends("planned_amount", "committed_amount", "project_id.account_id")
    def _compute_amounts(self):
        AnalyticLine = self.env["account.analytic.line"].sudo()
        for line in self:
            actual = 0.0
            if line.project_id.account_id:
                actual = -sum(
                    AnalyticLine.search(
                        [("account_id", "=", line.project_id.account_id.id)]
                    ).mapped("amount")
                )
            line.actual_amount = max(0.0, actual)
            line.available_amount = (
                line.planned_amount - line.committed_amount - line.actual_amount
            )

    def action_reserve(self, amount):
        self.ensure_one()
        amount = float(amount)
        if amount <= 0:
            raise ValidationError(_("Le montant à réserver doit être positif."))
        if amount > self.available_amount:
            raise ValidationError(_("La ligne budgétaire ne couvre pas ce montant."))
        self.sudo().write({"committed_amount": self.committed_amount + amount})
        return True


class CsrsProjectCompliance(models.Model):
    _name = "csrs.project.compliance"
    _description = "Élément de conformité d'un projet"
    _order = "due_date, id"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    kind = fields.Selection(
        [
            ("ethics", "Éthique"),
            ("contract", "Contrat"),
            ("purchase", "Achat"),
            ("donor", "Obligation bailleur"),
            ("other", "Autre"),
        ],
        required=True,
    )
    description = fields.Text(required=True)
    owner_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    due_date = fields.Date()
    state = fields.Selection(
        [("open", "Ouvert"), ("incident", "Incident"), ("corrected", "Corrigé")],
        default="open",
        required=True,
    )
    corrective_action = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment", "csrs_compliance_attachment_rel", "item_id", "attachment_id"
    )


class CsrsProjectRisk(models.Model):
    _name = "csrs.project.risk"
    _description = "Risque d'un projet de recherche"
    _order = "severity desc, id"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    title = fields.Char(required=True)
    description = fields.Text()
    probability = fields.Integer(required=True, default=1)
    impact = fields.Integer(required=True, default=1)
    severity = fields.Integer(compute="_compute_severity", store=True)
    owner_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    treatment = fields.Text(required=True)
    residual_risk = fields.Text()
    state = fields.Selection(
        [("open", "Ouvert"), ("treated", "Traité"), ("accepted", "Accepté")],
        default="open",
        required=True,
    )

    @api.depends("probability", "impact")
    def _compute_severity(self):
        for risk in self:
            risk.severity = risk.probability * risk.impact

    @api.constrains("probability", "impact")
    def _check_scale(self):
        for risk in self:
            if risk.probability not in range(1, 6) or risk.impact not in range(1, 6):
                raise ValidationError(
                    _("Probabilité et impact doivent être compris entre 1 et 5.")
                )


class CsrsProjectReport(models.Model):
    _name = "csrs.project.report"
    _description = "Rapport d'un projet de recherche"
    _order = "due_date desc, id desc"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    title = fields.Char(required=True)
    report_type = fields.Selection(
        [("technical", "Technique"), ("financial", "Financier"), ("final", "Final")],
        required=True,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    due_date = fields.Date(required=True)
    state = fields.Selection(
        [("draft", "Brouillon"), ("submitted", "Soumis"), ("validated", "Validé")],
        default="draft",
        required=True,
    )
    comments = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "csrs_project_report_attachment_rel",
        "report_id",
        "attachment_id",
    )

    @api.constrains("period_start", "period_end")
    def _check_period(self):
        for report in self:
            if report.period_end < report.period_start:
                raise ValidationError(_("La fin de période doit suivre son début."))


class CsrsProjectClosure(models.Model):
    _name = "csrs.project.closure"
    _description = "Dossier de clôture d'un projet de recherche"

    project_id = fields.Many2one(
        "project.project", required=True, ondelete="cascade", index=True
    )
    assessment = fields.Text(required=True)
    equipment_disposition = fields.Text(required=True)
    data_disposition = fields.Text(required=True)
    final_balance = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="project_id.currency_id", readonly=True)
    outlook = fields.Text()
    residual_liabilities = fields.Text()
    sustainability = fields.Text(required=True)

    _one_closure_per_project = models.Constraint(
        "UNIQUE (project_id)", "Un seul dossier de clôture est autorisé par projet."
    )
