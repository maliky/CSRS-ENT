"""Authoritative CSRS task progress models stored only in Odoo."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    csrs_manager_id = fields.Many2one(
        "res.users", string="Responsable principal CSRS", tracking=True, index=True
    )
    csrs_secondary_manager_user_ids = fields.Many2many(
        "res.users",
        "csrs_task_secondary_manager_rel",
        "task_id",
        "user_id",
        string="Responsables secondaires CSRS",
        tracking=True,
        copy=False,
    )
    csrs_progress_percent = fields.Float(
        string="Progression CSRS (%)", default=0.0, tracking=True
    )
    csrs_revision = fields.Integer(
        string="Révision CSRS", default=0, readonly=True, copy=False
    )
    csrs_status = fields.Selection(
        [
            ("open", "Ouverte"),
            ("validated", "Validée"),
            ("closed", "Fermée"),
        ],
        string="État CSRS",
        default="open",
        required=True,
        tracking=True,
        copy=False,
    )
    csrs_progress_entry_ids = fields.One2many(
        "csrs.progress.entry",
        "task_id",
        string="Historique de progression CSRS",
        copy=False,
    )

    @api.constrains("csrs_progress_percent")
    def _check_csrs_progress_percent(self):
        for task in self:
            if not 0 <= task.csrs_progress_percent <= 100:
                raise ValidationError(_("La progression doit être comprise entre 0 et 100."))

    def _csrs_is_admin(self):
        return self.env.user.has_group("csrs_reporting.group_csrs_it") or self.env.user.has_group(
            "base.group_system"
        )

    def _csrs_check_revision(self, expected_revision):
        if expected_revision is not None and self.csrs_revision != expected_revision:
            raise UserError(_("La tâche a changé. Rechargez-la avant de continuer."))

    def action_csrs_record_progress(
        self, progress, observation="", expected_revision=None
    ):
        """Record one atomic, revision-checked progress update."""
        self.ensure_one()
        observation = (observation or "").strip()
        is_manager = self.csrs_manager_id == self.env.user
        is_assignee = self.env.user in self.user_ids
        is_admin = self._csrs_is_admin()
        if not (is_manager or is_assignee or is_admin):
            raise UserError(_("Vous ne pouvez pas modifier la progression de cette tâche."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_status == "closed":
            raise UserError(_("Une tâche fermée ne peut plus être modifiée."))
        if not 0 <= progress <= 100:
            raise ValidationError(_("La progression doit être comprise entre 0 et 100."))
        if progress < self.csrs_progress_percent and not observation:
            raise ValidationError(_("Une baisse de progression exige une observation."))
        if progress == 100 and not (is_manager or is_admin):
            raise UserError(_("Seul le responsable principal peut valider 100 %."))

        revision = self.csrs_revision + 1
        values = {
            "csrs_progress_percent": progress,
            "csrs_revision": revision,
        }
        if progress == 100:
            values["csrs_status"] = "validated"
        self.with_context(csrs_authorized_mutation=True).write(values)
        return self.env["csrs.progress.entry"].sudo().create(
            {
                "task_id": self.id,
                "author_id": self.env.user.id,
                "progress_percent": progress,
                "observation": observation,
                "revision": revision,
            }
        )

    def action_csrs_comment(self, body):
        """Allow participants and secondary supervisors to comment without editing."""
        self.ensure_one()
        message = (body or "").strip()
        if not message:
            raise ValidationError(_("Le commentaire ne peut pas être vide."))
        allowed = (
            self.env.user in self.user_ids
            or self.env.user == self.csrs_manager_id
            or self.env.user in self.csrs_secondary_manager_user_ids
            or self._csrs_is_admin()
        )
        if not allowed:
            raise UserError(_("Vous ne pouvez pas commenter cette tâche."))
        return self.sudo().message_post(body=message, message_type="comment")

    def action_csrs_close(self, expected_revision=None):
        self.ensure_one()
        if self.env.user != self.csrs_manager_id and not self._csrs_is_admin():
            raise UserError(_("Seul le responsable principal peut fermer la tâche."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_progress_percent != 100 or self.csrs_status != "validated":
            raise UserError(_("La tâche doit être validée à 100 % avant sa fermeture."))
        self.with_context(csrs_authorized_mutation=True).write(
            {"csrs_status": "closed", "csrs_revision": self.csrs_revision + 1}
        )
        return True

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.user.has_group("base.group_system"):
            for values in values_list:
                manager_id = values.get("csrs_manager_id")
                if manager_id and manager_id != self.env.user.id:
                    raise UserError(
                        _("Le responsable principal doit créer la tâche CSRS.")
                    )
        return super().create(values_list)

    def write(self, values):
        guarded = {"csrs_progress_percent", "csrs_revision", "csrs_status"}
        if guarded.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une action métier CSRS."))
        if not self.env.context.get("csrs_authorized_mutation"):
            for task in self.filtered("csrs_manager_id"):
                if self.env.user != task.csrs_manager_id and not task._csrs_is_admin():
                    raise UserError(
                        _("Seul le responsable principal peut modifier la tâche CSRS.")
                    )
        return super().write(values)

    def unlink(self):
        for task in self.filtered("csrs_manager_id"):
            if self.env.user != task.csrs_manager_id and not task._csrs_is_admin():
                raise UserError(
                    _("Seul le responsable principal peut supprimer la tâche CSRS.")
                )
        return super().unlink()


class CsrsProgressEntry(models.Model):
    _name = "csrs.progress.entry"
    _description = "Entrée de progression CSRS"
    _order = "recorded_at desc, id desc"

    task_id = fields.Many2one(
        "project.task", string="Tâche", required=True, ondelete="cascade", index=True
    )
    author_id = fields.Many2one(
        "res.users", string="Auteur", required=True, ondelete="restrict", index=True
    )
    recorded_at = fields.Datetime(
        string="Enregistrée le",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    progress_percent = fields.Float(string="Progression (%)", required=True, readonly=True)
    observation = fields.Text(string="Observation", readonly=True)
    revision = fields.Integer(string="Révision", required=True, readonly=True)

    _csrs_progress_task_revision_unique = models.Constraint(
        "UNIQUE (task_id, revision)",
        "Une seule progression est autorisée par révision de tâche.",
    )
    _csrs_progress_percent_range = models.Constraint(
        "CHECK (progress_percent >= 0 AND progress_percent <= 100)",
        "La progression doit être comprise entre 0 et 100.",
    )

    def write(self, values):
        raise UserError(_("L'historique de progression est immuable."))

    def unlink(self):
        raise UserError(_("L'historique de progression est immuable."))
