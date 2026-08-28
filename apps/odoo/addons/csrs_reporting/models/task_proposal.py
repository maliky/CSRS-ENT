"""Task proposals that become Odoo project tasks only after approval."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


class CsrsTaskProposal(models.Model):
    _name = "csrs.task.proposal"
    _description = "Proposition de tâche CSRS ENT"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    code = fields.Char(readonly=True, copy=False, index=True)
    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    title = fields.Char(string="Nom court", required=True, tracking=True)
    description = fields.Text(string="Résultat attendu", required=True, tracking=True)
    author_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, index=True
    )
    manager_id = fields.Many2one("res.users", required=True, index=True)
    project_id = fields.Many2one(
        "project.project", string="Projet de recherche", ondelete="restrict"
    )
    institutional_action_id = fields.Many2one(
        "csrs.institutional.action",
        string="Action institutionnelle",
        ondelete="restrict",
    )
    calendar_id = fields.Many2one(
        "resource.calendar",
        required=True,
        default=lambda self: self.env.company.resource_calendar_id,
        ondelete="restrict",
    )
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    due_date = fields.Date(required=True)
    estimated_work_days = fields.Float(required=True, default=1.0)
    state = fields.Selection(
        [
            ("submitted", "Soumise"),
            ("rejected", "Rejetée"),
            ("accepted", "Acceptée"),
            ("withdrawn", "Retirée"),
        ],
        required=True,
        default="submitted",
        tracking=True,
        copy=False,
    )
    decision_note = fields.Text(readonly=True, copy=False)
    accepted_task_id = fields.Many2one(
        "project.task", readonly=True, copy=False, ondelete="restrict"
    )
    revision = fields.Integer(required=True, default=1, readonly=True, copy=False)

    _code_unique = models.Constraint(
        "UNIQUE (code)", "Ce code de proposition CSRS ENT est déjà utilisé."
    )
    _source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Cette proposition source est déjà importée."
    )

    @api.constrains("start_date", "due_date", "estimated_work_days")
    def _check_schedule(self):
        for proposal in self:
            if proposal.estimated_work_days <= 0:
                raise ValidationError(_("La charge estimée doit être positive."))
            if proposal.start_date and proposal.due_date < proposal.start_date:
                raise ValidationError(_("La fin prévue doit suivre la date de début."))

    @api.model
    def _manager_for_user(self, user):
        employee = self.env["hr.employee"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            limit=1,
        )
        manager = employee.parent_id.user_id if employee and employee.parent_id else False
        if not manager:
            raise ValidationError(
                _("Aucun responsable principal actif n'est défini pour ce compte.")
            )
        return manager

    def _check_revision(self, expected_revision):
        self.ensure_one()
        if expected_revision is not None and self.revision != expected_revision:
            raise UserError(_("La proposition a changé. Rechargez-la avant de continuer."))

    def action_csrs_update(self, values, expected_revision=None):
        """Let the author correct a rejected proposal without erasing its audit."""
        self.ensure_one()
        self._check_revision(expected_revision)
        if self.author_id != self.env.user or self.state not in {"submitted", "rejected"}:
            raise UserError(_("Cette proposition ne peut pas être modifiée."))
        allowed = {
            "title",
            "description",
            "project_id",
            "institutional_action_id",
            "calendar_id",
            "start_date",
            "due_date",
            "estimated_work_days",
        }
        clean_values = {key: value for key, value in values.items() if key in allowed}
        clean_values["revision"] = self.revision + 1
        self.with_context(csrs_authorized_mutation=True).write(clean_values)
        return True

    def action_csrs_resubmit(self, expected_revision=None):
        self.ensure_one()
        self._check_revision(expected_revision)
        if self.author_id != self.env.user or self.state != "rejected":
            raise UserError(_("Seule une proposition rejetée peut être resoumise."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "state": "submitted",
                "decision_note": False,
                "revision": self.revision + 1,
            }
        )
        self.message_post(body=_("Proposition corrigée et resoumise."))
        return True

    def action_csrs_withdraw(self, reason="", expected_revision=None):
        """Let the author withdraw a pending proposal without erasing its audit."""
        self.ensure_one()
        self._check_revision(expected_revision)
        if self.author_id != self.env.user or self.state != "submitted":
            raise UserError(_("Seule votre proposition soumise peut être retirée."))
        note = (reason or "").strip()
        if len(note) > 500:
            raise ValidationError(_("Le motif ne peut pas dépasser 500 caractères."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "state": "withdrawn",
                "decision_note": note,
                "revision": self.revision + 1,
            }
        )
        self.message_post(body=note or _("Proposition retirée par son auteur."))
        return True

    def action_csrs_decide(self, decision, note="", expected_revision=None):
        """Accept atomically into one task or reject with a required reason."""
        self.ensure_one()
        self._check_revision(expected_revision)
        current_manager = self._manager_for_user(self.author_id)
        if current_manager != self.env.user:
            raise UserError(_("Seul le responsable principal peut décider."))
        if self.state != "submitted":
            raise UserError(_("Cette proposition a déjà été examinée."))
        note = (note or "").strip()
        if decision not in {"accept", "reject"}:
            raise ValidationError(_("Décision invalide."))
        if decision == "reject" and not note:
            raise ValidationError(_("Le motif du rejet est obligatoire."))

        if decision == "reject":
            self.with_context(csrs_authorized_mutation=True).write(
                {
                    "state": "rejected",
                    "decision_note": note,
                    "revision": self.revision + 1,
                }
            )
            self.message_post(body=note)
            return False

        task = self.env["project.task"].create(
            {
                "name": self.title,
                "description": self.description,
                "project_id": self.project_id.id,
                "csrs_institutional_action_id": self.institutional_action_id.id,
                "user_ids": [Command.set(self.author_id.ids)],
                "csrs_managed": True,
                "csrs_manager_id": current_manager.id,
                "csrs_calendar_id": self.calendar_id.id,
                "csrs_start_date": self.start_date,
                "date_deadline": self.due_date,
                "csrs_estimated_work_days": self.estimated_work_days,
            }
        )
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "state": "accepted",
                "decision_note": note,
                "accepted_task_id": task.id,
                "revision": self.revision + 1,
            }
        )
        self.message_post(body=note or _("Proposition acceptée."))
        return task

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            author = self.env["res.users"].browse(values.get("author_id") or self.env.user.id)
            if (
                not self.env.context.get("csrs_migration_import")
                and author != self.env.user
                and not self.env.user.csrs_has_effective_group(
                    "csrs_reporting.group_csrs_it"
                )
            ):
                raise UserError(_("Vous ne pouvez proposer une tâche que pour vous-même."))
            values["author_id"] = author.id
            if not values.get("manager_id"):
                values["manager_id"] = self._manager_for_user(author).id
            values.setdefault("code", self.env["ir.sequence"].next_by_code("csrs.proposal"))
        return super().create(values_list)

    def write(self, values):
        if not self.env.context.get("csrs_authorized_mutation"):
            raise UserError(_("Utilisez une action métier de proposition."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Une proposition auditée ne peut pas être supprimée."))
