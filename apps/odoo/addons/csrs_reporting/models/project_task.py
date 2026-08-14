"""Authoritative CSRS task progress models stored only in Odoo."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectTask(models.Model):
    _inherit = "project.task"

    csrs_manager_id = fields.Many2one(
        "res.users",
        string="Responsable principal CSRS",
        tracking=True,
        index=True,
    )
    csrs_progress_percent = fields.Float(
        string="Progression CSRS (%)",
        default=0.0,
        tracking=True,
    )
    csrs_revision = fields.Integer(
        string="Révision CSRS",
        default=0,
        readonly=True,
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

    def action_csrs_record_progress(self, progress, observation="", expected_revision=None):
        """Record one atomic, revision-checked progress update."""
        self.ensure_one()
        observation = (observation or "").strip()
        is_manager = self.csrs_manager_id == self.env.user
        is_assignee = self.env.user in self.user_ids
        is_admin = self.env.user.has_group("base.group_system")
        if not (is_manager or is_assignee or is_admin):
            raise UserError(_("Vous ne pouvez pas modifier la progression de cette tâche."))
        if expected_revision is not None and self.csrs_revision != expected_revision:
            raise UserError(_("La tâche a changé. Rechargez-la avant de continuer."))
        if not 0 <= progress <= 100:
            raise ValidationError(_("La progression doit être comprise entre 0 et 100."))
        if progress < self.csrs_progress_percent and not observation:
            raise ValidationError(_("Une baisse de progression exige une observation."))
        if progress == 100 and not (is_manager or is_admin):
            raise UserError(_("Seul le responsable principal peut valider 100 %."))

        revision = self.csrs_revision + 1
        self.with_context(csrs_record_progress=True).write(
            {
                "csrs_progress_percent": progress,
                "csrs_revision": revision,
            }
        )
        return self.env["csrs.progress.entry"].sudo().create(
            {
                "task_id": self.id,
                "author_id": self.env.user.id,
                "progress_percent": progress,
                "observation": observation,
                "revision": revision,
            }
        )

    def write(self, values):
        guarded = {"csrs_progress_percent", "csrs_revision"}
        if guarded.intersection(values) and not self.env.context.get(
            "csrs_record_progress"
        ):
            raise UserError(_("Utilisez l'action de progression CSRS."))
        return super().write(values)


class CsrsProgressEntry(models.Model):
    _name = "csrs.progress.entry"
    _description = "Entrée de progression CSRS"
    _order = "recorded_at desc, id desc"

    task_id = fields.Many2one(
        "project.task",
        string="Tâche",
        required=True,
        ondelete="cascade",
        index=True,
    )
    author_id = fields.Many2one(
        "res.users",
        string="Auteur",
        required=True,
        ondelete="restrict",
        index=True,
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

    _sql_constraints = [
        (
            "csrs_progress_task_revision_unique",
            "unique(task_id, revision)",
            "Une seule progression est autorisée par révision de tâche.",
        ),
        (
            "csrs_progress_percent_range",
            "check(progress_percent >= 0 AND progress_percent <= 100)",
            "La progression doit être comprise entre 0 et 100.",
        ),
    ]

    def write(self, values):
        raise UserError(_("L'historique de progression est immuable."))

    def unlink(self):
        raise UserError(_("L'historique de progression est immuable."))
