"""Immutable audit witnesses for destructive CSRS ENT operations."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CsrsAuditEvent(models.Model):
    _name = "csrs.audit.event"
    _description = "Événement d'audit CSRS ENT"
    _order = "recorded_at desc, id desc"

    event_type = fields.Selection(
        [
            ("task_bulk_delete", "Suppression de tâches"),
            ("user_delete", "Suppression de compte"),
            ("organization_change", "Modification d'organigramme"),
            ("partner_change", "Modification d'organisation partenaire"),
            ("project_archive", "Archivage de projet"),
            ("role_switch", "Changement de rôle effectif"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    actor_id = fields.Many2one(
        "res.users", required=True, readonly=True, ondelete="restrict", index=True
    )
    reason = fields.Text(required=True, readonly=True)
    snapshot = fields.Json(required=True, readonly=True)
    recorded_at = fields.Datetime(
        required=True, readonly=True, default=fields.Datetime.now, index=True
    )

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.is_superuser():
            raise UserError(_("Utilisez une opération métier auditée."))
        return super().create(values_list)

    def write(self, values):
        raise UserError(_("Un événement d'audit est immuable."))

    def unlink(self):
        raise UserError(_("Un événement d'audit est immuable."))
