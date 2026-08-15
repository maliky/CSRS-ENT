"""Typed CSRS process dossiers and auditable workflow transitions."""

from hashlib import sha256
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


PROCESS_TYPES = (
    ("fund", "Bon de sortie de fonds"),
    ("purchase", "Demande d'achat"),
    ("absence", "Demande d'absence"),
    ("mission", "Ordre de mission"),
    ("payment_notice", "Notification de paiement"),
    ("visa", "Visa ou prolongation"),
    ("data", "Gestion des données"),
)

TRANSITIONS = {
    "fund": {
        ("draft", "submit"): "finance_review",
        ("finance_review", "approve"): "requester_visa",
        ("requester_visa", "approve"): "finance_head",
        ("finance_head", "approve"): "daf_review",
        ("daf_review", "approve"): "project_accounting",
        ("project_accounting", "approve"): "dg_review",
        ("dg_review", "approve"): "payment_preparation",
        ("payment_preparation", "pay"): "completed",
    },
    "purchase": {
        ("draft", "submit"): "daf_review",
        ("daf_review", "approve"): "dg_review",
        ("dg_review", "approve"): "procurement",
        ("procurement", "order"): "ordered",
        ("ordered", "receive"): "delivered",
        ("delivered", "invoice"): "invoiced",
        ("invoiced", "pay"): "completed",
    },
    "absence": {
        ("draft", "submit"): "supervisor_review",
        ("supervisor_review", "approve"): "hr_review",
        ("hr_review", "approve"): "dg_review",
        ("dg_review", "approve"): "secretariat",
        ("secretariat", "complete"): "completed",
    },
    "mission": {
        ("draft", "submit"): "assistance",
        ("assistance", "approve"): "dg_review",
        ("dg_review", "approve"): "secretariat",
        ("secretariat", "distribute"): "accounting",
        ("accounting", "approve"): "fleet",
        ("fleet", "complete"): "completed",
    },
    "payment_notice": {
        ("draft", "submit"): "accounting",
        ("accounting", "notify"): "notified",
        ("notified", "acknowledge"): "completed",
    },
    "visa": {
        ("draft", "submit"): "research_assistance",
        ("research_assistance", "approve"): "i2a_review",
        ("i2a_review", "approve"): "dg_review",
        ("dg_review", "approve"): "secretariat",
        ("secretariat", "transmit"): "mae_followup",
        ("mae_followup", "complete"): "completed",
    },
    "data": {
        ("draft", "submit"): "systems_validation",
        ("systems_validation", "approve"): "quality_review",
        ("quality_review", "approve"): "active_processing",
        ("active_processing", "audit"): "audit_review",
        ("audit_review", "archive"): "archived",
        ("archived", "dispose"): "completed",
    },
}

CORRECTABLE_STATES = {
    "finance_review",
    "finance_head",
    "daf_review",
    "project_accounting",
    "dg_review",
    "supervisor_review",
    "hr_review",
    "assistance",
    "research_assistance",
    "i2a_review",
    "systems_validation",
    "quality_review",
    "audit_review",
}

STEP_ROLE_CODES = {
    "finance_review": "FINANCE_AGENT",
    "requester_visa": "REQUESTER",
    "finance_head": "FINANCE_HEAD",
    "daf_review": "DAF",
    "project_accounting": "PROJECT_ACCOUNTANT",
    "dg_review": "DG",
    "payment_preparation": "CASHIER",
    "procurement": "PROCUREMENT",
    "ordered": "PROCUREMENT",
    "delivered": "PROCUREMENT",
    "invoiced": "FINANCE_AGENT",
    "supervisor_review": "PRIMARY_MANAGER",
    "hr_review": "HR",
    "secretariat": "SECRETARIAT",
    "assistance": "MISSION_ASSISTANCE",
    "accounting": "FINANCE_AGENT",
    "fleet": "FLEET",
    "notified": "REQUESTER",
    "research_assistance": "RESEARCH_ASSISTANCE",
    "i2a_review": "I2A",
    "mae_followup": "SECRETARIAT",
    "systems_validation": "IT_SYSTEMS",
    "quality_review": "QUALITY",
    "active_processing": "DATA_MANAGER",
    "audit_review": "QUALITY",
    "archived": "DATA_MANAGER",
}


class CsrsProcessCase(models.Model):
    _name = "csrs.process.case"
    _description = "Dossier de processus CSRS"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    process_type = fields.Selection(PROCESS_TYPES, required=True, index=True)
    state = fields.Char(default="draft", required=True, tracking=True, index=True)
    revision = fields.Integer(default=1, required=True, readonly=True, copy=False)
    requester_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    origin_department_id = fields.Many2one(
        "hr.department", required=True, ondelete="restrict", index=True
    )
    project_id = fields.Many2one(
        "project.project",
        ondelete="restrict",
        domain="[('csrs_research_project', '=', True)]",
    )
    subject = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True)
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    attachment_ids = fields.Many2many(
        "ir.attachment", "csrs_process_attachment_rel", "case_id", "attachment_id"
    )
    correction_reason = fields.Text(readonly=True, copy=False)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    event_ids = fields.One2many(
        "csrs.process.event", "case_id", string="Événements", copy=False
    )

    _reference_unique = models.Constraint(
        "UNIQUE (reference)", "Cette référence de processus est déjà utilisée."
    )

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            requester_id = values.get("requester_id") or self.env.user.id
            if requester_id != self.env.user.id and not self.env.user.has_group(
                "csrs_reporting.group_csrs_it"
            ):
                raise AccessError(
                    _("Vous ne pouvez créer un dossier que pour vous-même.")
                )
            values["requester_id"] = requester_id
            process_type = values.get("process_type")
            if process_type not in dict(PROCESS_TYPES):
                raise ValidationError(_("Type de processus invalide."))
            values.setdefault(
                "reference",
                self.env["ir.sequence"].next_by_code(f"csrs.process.{process_type}"),
            )
        return super().create(values_list)

    def _check_revision(self, expected_revision):
        self.ensure_one()
        if expected_revision is not None and self.revision != int(expected_revision):
            raise UserError(_("Le dossier a changé. Rechargez-le avant de continuer."))

    def _is_dg(self):
        return self.env.user.has_group("csrs_reporting.group_csrs_dg")

    def _is_it(self):
        return self.env.user.has_group("csrs_reporting.group_csrs_it")

    def _can_handle(self):
        self.ensure_one()
        if self.state == "draft" or self.state == "correction":
            return self.env.user == self.requester_id
        role = STEP_ROLE_CODES.get(self.state)
        if role == "REQUESTER":
            return self.env.user == self.requester_id
        if role == "DG":
            return self._is_dg()
        if role == "PRIMARY_MANAGER":
            employee = (
                self.env["hr.employee"]
                .sudo()
                .search([("user_id", "=", self.requester_id.id)], limit=1)
            )
            return bool(employee.parent_id.user_id == self.env.user)
        group_by_role = {
            "HR": "csrs_reporting.group_csrs_hr",
            "SECRETARIAT": "csrs_reporting.group_csrs_secretariat",
            "MISSION_ASSISTANCE": "csrs_reporting.group_csrs_secretariat",
            "RESEARCH_ASSISTANCE": "csrs_reporting.group_csrs_secretariat",
            "FINANCE_AGENT": "csrs_reporting.group_csrs_finance",
            "FINANCE_HEAD": "csrs_reporting.group_csrs_finance",
            "PROJECT_ACCOUNTANT": "csrs_reporting.group_csrs_finance",
            "DAF": "csrs_reporting.group_csrs_finance",
            "CASHIER": "csrs_reporting.group_csrs_finance",
            "PROCUREMENT": "csrs_reporting.group_csrs_procurement",
            "FLEET": "csrs_reporting.group_csrs_fleet",
            "QUALITY": "csrs_reporting.group_csrs_compliance",
            "DATA_MANAGER": "csrs_reporting.group_csrs_data_manager",
            "IT_SYSTEMS": "csrs_reporting.group_csrs_it",
        }
        if role in group_by_role and self.env.user.has_group(group_by_role[role]):
            return True
        return bool(role and self.env.user.csrs_has_active_role_grant(role))

    def _event(self, action, from_state, to_state, note="", details=None):
        return (
            self.env["csrs.process.event"]
            .sudo()
            .create(
                {
                    "case_id": self.id,
                    "actor_id": self.env.user.id,
                    "action": action,
                    "from_state": from_state,
                    "to_state": to_state,
                    "note": note,
                    "details": details or {},
                }
            )
        )

    def _signature_details(self, confirmation):
        expected = f"VALIDÉ LE {fields.Date.context_today(self):%d/%m/%Y}"
        if str(confirmation or "").strip() != expected:
            raise ValidationError(_("Saisissez exactement : %s", expected))
        snapshot = {
            "case_id": self.id,
            "reference": self.reference,
            "revision": self.revision,
            "process_type": self.process_type,
            "state": self.state,
            "amount": self.amount,
            "currency": self.currency_id.name,
            "attachments": [
                {"id": item.id, "name": item.name, "checksum": item.checksum or ""}
                for item in self.attachment_ids.sorted("id")
            ],
        }
        return {
            "confirmation": expected,
            "snapshot_sha256": sha256(
                json.dumps(snapshot, sort_keys=True, ensure_ascii=True).encode("utf-8")
            ).hexdigest(),
            "snapshot": snapshot,
        }

    def action_transition(self, action, expected_revision=None, note="", confirmation=""):
        self.ensure_one()
        self._check_revision(expected_revision)
        action = str(action or "").strip()
        note = str(note or "").strip()
        if not self._can_handle():
            raise AccessError(_("Vous ne pouvez pas traiter cette étape."))
        from_state = self.state
        if action == "correct":
            if from_state not in CORRECTABLE_STATES:
                raise UserError(_("Cette étape ne peut pas demander de correction."))
            if not note:
                raise ValidationError(_("Le motif de correction est obligatoire."))
            to_state = "correction"
        elif action == "resubmit" and from_state == "correction":
            to_state = TRANSITIONS[self.process_type][("draft", "submit")]
        elif action == "reject" and from_state in CORRECTABLE_STATES:
            if not note:
                raise ValidationError(_("Le motif de rejet est obligatoire."))
            to_state = "rejected"
        else:
            to_state = TRANSITIONS[self.process_type].get((from_state, action))
            if not to_state:
                raise UserError(_("Transition invalide pour cette étape."))
        details = {}
        if from_state == "dg_review" and action == "approve":
            details = self._signature_details(confirmation)
        values = {
            "state": to_state,
            "revision": self.revision + 1,
            "correction_reason": note if to_state == "correction" else False,
        }
        if from_state == "draft" and action == "submit":
            values["submitted_at"] = fields.Datetime.now()
        if to_state == "completed":
            values["completed_at"] = fields.Datetime.now()
        self.sudo().with_context(csrs_authorized_mutation=True).write(values)
        self._event(action, from_state, to_state, note, details)
        self.sudo().message_post(
            body=note or _("Étape traitée : %s", action),
            author_id=self.env.user.partner_id.id,
        )
        self._after_transition(from_state, action, to_state)
        return True

    def _after_transition(self, from_state, action, to_state):
        self.ensure_one()
        if (
            self.process_type == "fund"
            and from_state == "dg_review"
            and action == "approve"
        ):
            fund = (
                self.env["csrs.fund.request"]
                .sudo()
                .search([("case_id", "=", self.id)], limit=1)
            )
            if fund.budget_line_id:
                fund.budget_line_id.action_reserve(self.amount)
        if (
            self.process_type == "mission"
            and from_state == "accounting"
            and action == "approve"
        ):
            mission = (
                self.env["csrs.mission.order"]
                .sudo()
                .search([("case_id", "=", self.id)], limit=1)
            )
            if mission and not mission.vehicle_required:
                self.sudo().with_context(csrs_authorized_mutation=True).write(
                    {
                        "state": "completed",
                        "revision": self.revision + 1,
                        "completed_at": fields.Datetime.now(),
                    }
                )
                self._event("complete", "fleet", "completed", _("Aucun véhicule requis."))

    def write(self, values):
        protected = {"state", "revision", "submitted_at", "completed_at"}
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une action métier du processus."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Un dossier audité ne peut pas être supprimé."))


class CsrsProcessEvent(models.Model):
    _name = "csrs.process.event"
    _description = "Événement immuable d'un processus CSRS"
    _order = "occurred_at, id"

    case_id = fields.Many2one(
        "csrs.process.case", required=True, ondelete="restrict", index=True
    )
    actor_id = fields.Many2one(
        "res.users", required=True, readonly=True, ondelete="restrict"
    )
    action = fields.Char(required=True, readonly=True)
    from_state = fields.Char(required=True, readonly=True)
    to_state = fields.Char(required=True, readonly=True)
    note = fields.Text(readonly=True)
    details = fields.Json(default=dict, readonly=True)
    occurred_at = fields.Datetime(
        default=fields.Datetime.now, required=True, readonly=True
    )

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.is_superuser():
            raise AccessError(_("Utilisez une transition de dossier."))
        return super().create(values_list)

    def write(self, values):
        raise UserError(_("Un événement de processus est immuable."))

    def unlink(self):
        raise UserError(_("Un événement de processus est immuable."))


class CsrsFundRequest(models.Model):
    _name = "csrs.fund.request"
    _description = "Bon de sortie de fonds CSRS"

    case_id = fields.Many2one(
        "csrs.process.case", required=True, ondelete="restrict", index=True
    )
    budget_line_id = fields.Many2one(
        "csrs.project.budget.line", required=True, ondelete="restrict"
    )
    activity_task_id = fields.Many2one("project.task", ondelete="restrict")
    beneficiary_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    initiator_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    purpose = fields.Text(required=True)
    requires_purchase = fields.Boolean(default=False)
    payment_method = fields.Selection(
        [("cash", "Espèces"), ("check", "Chèque")], readonly=True
    )
    purchase_case_id = fields.Many2one("csrs.process.case", readonly=True)
    payment_id = fields.Many2one("account.payment", readonly=True, ondelete="restrict")

    _case_unique = models.Constraint(
        "UNIQUE (case_id)", "Ce dossier possède déjà un BSF."
    )

    @api.constrains("case_id", "budget_line_id")
    def _check_project(self):
        for request in self:
            if request.case_id.process_type != "fund":
                raise ValidationError(_("Le dossier doit être un BSF."))
            if request.case_id.project_id != request.budget_line_id.project_id:
                raise ValidationError(
                    _("La ligne budgétaire appartient à un autre projet.")
                )


class CsrsPurchaseRequest(models.Model):
    _name = "csrs.purchase.request"
    _description = "Demande d'achat CSRS"

    case_id = fields.Many2one(
        "csrs.process.case", required=True, ondelete="restrict", index=True
    )
    budget_line_id = fields.Many2one(
        "csrs.project.budget.line", required=True, ondelete="restrict"
    )
    vendor_id = fields.Many2one("res.partner", ondelete="restrict")
    product_id = fields.Many2one("product.product", ondelete="restrict")
    quantity = fields.Float(default=1.0, required=True)
    estimated_amount = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="case_id.currency_id", readonly=True)
    purchase_order_id = fields.Many2one(
        "purchase.order", readonly=True, ondelete="restrict"
    )
    vendor_bill_id = fields.Many2one("account.move", readonly=True, ondelete="restrict")
    delivery_confirmed_at = fields.Datetime(readonly=True)

    _case_unique = models.Constraint(
        "UNIQUE (case_id)", "Ce dossier possède déjà une demande d'achat."
    )

    def action_create_purchase_order(self):
        self.ensure_one()
        if self.purchase_order_id:
            return self.purchase_order_id
        if not self.vendor_id or not self.product_id:
            raise ValidationError(_("Le fournisseur et le produit sont obligatoires."))
        distribution = {}
        if self.case_id.project_id.account_id:
            distribution[str(self.case_id.project_id.account_id.id)] = 100
        order = (
            self.env["purchase.order"]
            .sudo()
            .create(
                {
                    "partner_id": self.vendor_id.id,
                    "origin": self.case_id.reference,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product_id.id,
                                "name": self.case_id.subject,
                                "product_qty": self.quantity,
                                "product_uom": self.product_id.uom_id.id,
                                "price_unit": self.estimated_amount / self.quantity,
                                "analytic_distribution": distribution or False,
                            },
                        )
                    ],
                }
            )
        )
        self.sudo().write({"purchase_order_id": order.id})
        return order


class CsrsAbsenceRequest(models.Model):
    _name = "csrs.absence.request"
    _description = "Demande d'absence CSRS"

    case_id = fields.Many2one("csrs.process.case", required=True, ondelete="restrict")
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict")
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    emergency_contact = fields.Char(required=True)
    interim_user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    destination = fields.Char()
    service = fields.Char()
    leave_id = fields.Many2one("hr.leave", readonly=True, ondelete="restrict")

    _case_unique = models.Constraint("UNIQUE (case_id)", "Cette demande existe déjà.")

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for request in self:
            if request.end_date < request.start_date:
                raise ValidationError(_("La fin doit suivre le début de l'absence."))


class CsrsMissionOrder(models.Model):
    _name = "csrs.mission.order"
    _description = "Ordre de mission CSRS"

    case_id = fields.Many2one("csrs.process.case", required=True, ondelete="restrict")
    destination = fields.Char(required=True)
    purpose = fields.Text(required=True)
    departure_date = fields.Date(required=True)
    return_date = fields.Date(required=True)
    transport_mode = fields.Char()
    vehicle_required = fields.Boolean(default=False)
    official_number = fields.Char(readonly=True)

    _case_unique = models.Constraint("UNIQUE (case_id)", "Cet ordre existe déjà.")


class CsrsPaymentNotification(models.Model):
    _name = "csrs.payment.notification"
    _description = "Notification de paiement CSRS"

    case_id = fields.Many2one("csrs.process.case", required=True, ondelete="restrict")
    payment_nature = fields.Selection(
        [
            ("salary", "Salaire"),
            ("honorarium", "Honoraire"),
            ("mission", "Mission"),
            ("field", "Terrain"),
            ("other", "Autre"),
        ],
        required=True,
    )
    payment_date = fields.Date(required=True)
    sender = fields.Char(required=True)
    sending_bank = fields.Char()
    receiving_bank = fields.Char()
    check_number = fields.Char()
    proof_attachment_id = fields.Many2one(
        "ir.attachment", required=True, ondelete="restrict"
    )

    _case_unique = models.Constraint(
        "UNIQUE (case_id)", "Cette notification existe déjà."
    )


class CsrsVisaRequest(models.Model):
    _name = "csrs.visa.request"
    _description = "Demande de visa CSRS"

    case_id = fields.Many2one("csrs.process.case", required=True, ondelete="restrict")
    visitor_name = fields.Char(required=True)
    nationality = fields.Char(required=True)
    passport_number = fields.Char(required=True)
    visa_kind = fields.Selection(
        [("new", "Nouveau visa"), ("extension", "Prolongation")], required=True
    )
    desired_start_date = fields.Date(required=True)
    desired_end_date = fields.Date(required=True)
    mae_reference = fields.Char()

    _case_unique = models.Constraint("UNIQUE (case_id)", "Cette demande existe déjà.")


class CsrsDataManagementCase(models.Model):
    _name = "csrs.data.management.case"
    _description = "Gestion des données d'une étude CSRS"

    case_id = fields.Many2one("csrs.process.case", required=True, ondelete="restrict")
    study_objectives = fields.Text(required=True)
    management_plan = fields.Text(required=True)
    classification = fields.Selection(
        [("public", "Public"), ("internal", "Interne"), ("sensitive", "Sensible")],
        required=True,
    )
    storage_location = fields.Char(required=True)
    retention_until = fields.Date(required=True)
    legal_hold = fields.Boolean(default=False)
    legal_hold_reason = fields.Text()

    _case_unique = models.Constraint("UNIQUE (case_id)", "Ce dossier existe déjà.")

    @api.constrains("legal_hold", "legal_hold_reason")
    def _check_hold(self):
        for case in self:
            if case.legal_hold and not (case.legal_hold_reason or "").strip():
                raise ValidationError(
                    _("Le motif de conservation légale est obligatoire.")
                )
