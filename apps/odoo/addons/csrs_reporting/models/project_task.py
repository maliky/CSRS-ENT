"""Authoritative CSRS ENT task lifecycle stored only in Odoo."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


TERMINAL_STATUSES = {"completed", "closed_early"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    csrs_managed = fields.Boolean(
        string="Tâche CSRS ENT", default=False, required=True, index=True, copy=False
    )
    csrs_code = fields.Char(
        string="Code CSRS ENT", index=True, readonly=True, copy=False
    )
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
    csrs_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Calendrier de travail",
        default=lambda self: self.env.company.resource_calendar_id,
        ondelete="restrict",
    )
    csrs_start_date = fields.Date(
        string="Début prévu", default=fields.Date.context_today, tracking=True
    )
    csrs_estimated_work_days = fields.Float(
        string="Charge estimée (jours)", default=1.0, tracking=True
    )
    csrs_progress_percent = fields.Float(
        string="Progression CSRS (%)", default=0.0, tracking=True
    )
    csrs_blocked = fields.Boolean(
        string="Bloquée", default=False, tracking=True, copy=False
    )
    csrs_revision = fields.Integer(
        string="Révision CSRS", default=1, readonly=True, copy=False
    )
    csrs_status = fields.Selection(
        [
            ("planned", "Planifiée"),
            ("active", "En cours"),
            ("awaiting_validation", "À valider"),
            ("completed", "Terminée"),
            ("closed_early", "Clôturée avant achèvement"),
        ],
        string="État CSRS",
        default="planned",
        required=True,
        tracking=True,
        copy=False,
    )
    csrs_close_reason = fields.Text(
        string="Motif de clôture ou reprise", readonly=True, copy=False
    )
    csrs_completed_at = fields.Datetime(
        string="Terminée le", readonly=True, copy=False
    )
    csrs_progress_entry_ids = fields.One2many(
        "csrs.progress.entry",
        "task_id",
        string="Historique de progression CSRS",
        copy=False,
    )

    _csrs_code_unique = models.Constraint(
        "UNIQUE (csrs_code)", "Ce code de tâche CSRS ENT est déjà utilisé."
    )

    def init(self):
        """Map the bootstrap states to the final task lifecycle."""
        self.env.cr.execute(
            """
            UPDATE project_task
               SET csrs_status = CASE csrs_status
                   WHEN 'open' THEN 'active'
                   WHEN 'validated' THEN 'awaiting_validation'
                   WHEN 'closed' THEN 'completed'
                   ELSE csrs_status
               END
             WHERE csrs_status IN ('open', 'validated', 'closed')
            """
        )

    @api.constrains("csrs_progress_percent")
    def _check_csrs_progress_percent(self):
        for task in self:
            if not 0 <= task.csrs_progress_percent <= 100:
                raise ValidationError(_("La progression doit être comprise entre 0 et 100."))

    @api.constrains("csrs_start_date", "date_deadline", "csrs_estimated_work_days")
    def _check_csrs_schedule(self):
        for task in self.filtered("csrs_managed"):
            if task.csrs_estimated_work_days <= 0:
                raise ValidationError(_("La charge estimée doit être positive."))
            deadline = (
                fields.Datetime.to_datetime(task.date_deadline).date()
                if task.date_deadline
                else False
            )
            if task.csrs_start_date and deadline and deadline < task.csrs_start_date:
                raise ValidationError(_("La fin prévue doit suivre la date de début."))

    def _csrs_is_admin(self):
        return self.env.user.has_group(
            "csrs_reporting.group_csrs_it"
        ) or self.env.user.has_group("base.group_system")

    def _csrs_can_manage(self):
        self.ensure_one()
        return self.env.user == self.csrs_manager_id or self._csrs_is_admin()

    def _csrs_check_revision(self, expected_revision):
        self.ensure_one()
        if expected_revision is not None and self.csrs_revision != expected_revision:
            raise UserError(_("La tâche a changé. Rechargez-la avant de continuer."))

    def _csrs_next_revision(self):
        self.ensure_one()
        return self.csrs_revision + 1

    def action_csrs_record_progress(
        self,
        progress,
        observation="",
        blocked=False,
        expected_revision=None,
    ):
        """Record one atomic progress update and move the lifecycle forward."""
        self.ensure_one()
        observation = (observation or "").strip()
        is_manager = self._csrs_can_manage()
        is_assignee = self.env.user in self.user_ids
        if not (is_manager or is_assignee):
            raise UserError(_("Vous ne pouvez pas modifier la progression de cette tâche."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_status in TERMINAL_STATUSES:
            raise UserError(_("Une tâche terminée ne peut plus être modifiée."))
        if not 0 <= progress <= 100:
            raise ValidationError(_("La progression doit être comprise entre 0 et 100."))
        if (progress < self.csrs_progress_percent or blocked) and not observation:
            raise ValidationError(
                _("Une baisse de progression ou un blocage exige une observation.")
            )

        previous = self.csrs_progress_percent
        revision = self._csrs_next_revision()
        status = "awaiting_validation" if progress == 100 else "active"
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_progress_percent": progress,
                "csrs_blocked": bool(blocked),
                "csrs_revision": revision,
                "csrs_status": status,
                "csrs_close_reason": False,
            }
        )
        entry = self.env["csrs.progress.entry"].sudo().create(
            {
                "task_id": self.id,
                "author_id": self.env.user.id,
                "previous_progress_percent": previous,
                "progress_percent": progress,
                "blocked": bool(blocked),
                "observation": observation,
                "revision": revision,
            }
        )
        return entry

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

    def action_csrs_validate_completion(self, expected_revision=None):
        """Let only the primary manager accept a reported 100 percent."""
        self.ensure_one()
        if not self._csrs_can_manage():
            raise UserError(_("Seul le responsable principal peut valider la tâche."))
        self._csrs_check_revision(expected_revision)
        if (
            self.csrs_status != "awaiting_validation"
            or self.csrs_progress_percent != 100
        ):
            raise UserError(_("La tâche doit être à 100 % et en attente de validation."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_status": "completed",
                "csrs_completed_at": fields.Datetime.now(),
                "csrs_blocked": False,
                "csrs_revision": self._csrs_next_revision(),
            }
        )
        return True

    def action_csrs_request_rework(self, reason, expected_revision=None):
        """Return an awaiting task to active work with an auditable reason."""
        self.ensure_one()
        reason = (reason or "").strip()
        if not self._csrs_can_manage():
            raise UserError(_("Seul le responsable principal peut demander une reprise."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_status != "awaiting_validation":
            raise UserError(_("Seule une tâche à valider peut être reprise."))
        if not reason:
            raise ValidationError(_("Le motif de reprise est obligatoire."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_status": "active",
                "csrs_close_reason": reason,
                "csrs_revision": self._csrs_next_revision(),
            }
        )
        self.sudo().message_post(body=reason, message_type="comment")
        return True

    def action_csrs_close_early(self, reason, expected_revision=None):
        """Close unfinished work while keeping the remaining progress visible."""
        self.ensure_one()
        reason = (reason or "").strip()
        if not self._csrs_can_manage():
            raise UserError(_("Seul le responsable principal peut clôturer la tâche."))
        self._csrs_check_revision(expected_revision)
        if self.csrs_status in TERMINAL_STATUSES:
            raise UserError(_("Cette tâche est déjà terminée."))
        if not reason:
            raise ValidationError(_("Le motif de clôture est obligatoire."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_status": "closed_early",
                "csrs_close_reason": reason,
                "csrs_completed_at": fields.Datetime.now(),
                "csrs_blocked": False,
                "csrs_revision": self._csrs_next_revision(),
            }
        )
        self.sudo().message_post(body=reason, message_type="comment")
        return True

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            is_csrs = bool(values.get("csrs_managed") or values.get("csrs_manager_id"))
            if not is_csrs:
                continue
            values["csrs_managed"] = True
            values.setdefault("csrs_code", self.env["ir.sequence"].next_by_code("csrs.task"))
            manager_id = values.get("csrs_manager_id")
            is_admin = self.env.user.has_group(
                "csrs_reporting.group_csrs_it"
            ) or self.env.user.has_group("base.group_system")
            if not is_admin and manager_id != self.env.user.id:
                raise UserError(_("Le responsable principal doit créer la tâche CSRS."))
        return super().create(values_list)

    def write(self, values):
        protected = {
            "csrs_progress_percent",
            "csrs_revision",
            "csrs_status",
            "csrs_blocked",
            "csrs_close_reason",
            "csrs_completed_at",
        }
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une action métier CSRS."))
        if not self.env.context.get("csrs_authorized_mutation"):
            for task in self.filtered("csrs_managed"):
                if not task._csrs_can_manage():
                    raise UserError(
                        _("Seul le responsable principal peut modifier la tâche CSRS.")
                    )
        return super().write(values)

    def unlink(self):
        for task in self.filtered("csrs_managed"):
            if not task._csrs_is_admin():
                raise UserError(_("Seul un administrateur IT peut supprimer une tâche CSRS ENT."))
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
    previous_progress_percent = fields.Float(
        string="Progression précédente (%)", required=True, readonly=True
    )
    progress_percent = fields.Float(
        string="Progression (%)", required=True, readonly=True
    )
    blocked = fields.Boolean(string="Blocage", readonly=True)
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

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.is_superuser():
            raise UserError(_("Utilisez l'action de progression de la tâche."))
        return super().create(values_list)

    def write(self, values):
        raise UserError(_("L'historique de progression est immuable."))

    def unlink(self):
        raise UserError(_("L'historique de progression est immuable."))
