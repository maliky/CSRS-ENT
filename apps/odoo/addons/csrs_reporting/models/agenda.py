"""Odoo-backed availability, visitors and immutable direction agendas."""

from __future__ import annotations

from hashlib import sha256
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


AGENDA_DIRECTIONS = [
    ("programs", "Direction des programmes"),
    ("administration", "Direction administrative"),
]


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    csrs_agenda_direction = fields.Selection(
        AGENDA_DIRECTIONS, string="Direction de l'agenda", tracking=True
    )
    csrs_include_in_agenda = fields.Boolean(
        string="Inclure dans les agendas de direction", default=True, tracking=True
    )


class HrLeave(models.Model):
    _inherit = "hr.leave"

    csrs_managed = fields.Boolean(default=False, required=True, index=True, copy=False)
    csrs_kind = fields.Selection(
        [
            ("leave", "Congé"),
            ("absence", "Absence"),
            ("mission", "Mission"),
        ],
        string="Nature CSRS ENT",
        index=True,
        copy=False,
    )
    csrs_note = fields.Text(string="Observation CSRS ENT", copy=False)
    csrs_revision = fields.Integer(default=1, required=True, readonly=True, copy=False)
    csrs_cancelled_at = fields.Datetime(readonly=True, copy=False)
    csrs_cancellation_reason = fields.Text(readonly=True, copy=False)

    @api.constrains("csrs_managed", "csrs_kind")
    def _check_csrs_kind(self):
        for leave in self:
            if leave.csrs_managed and not leave.csrs_kind:
                raise ValidationError(_("La nature de l'indisponibilité est obligatoire."))

    def action_csrs_cancel(self, reason, expected_revision=None):
        self.ensure_one()
        if (
            not self.env.user.has_group("csrs_reporting.group_csrs_hr")
            and not self.env.user.has_group("csrs_reporting.group_csrs_it")
            and not self.env.user.csrs_has_active_role_grant("AGENDA_HR")
        ):
            raise UserError(_("Seules les RH peuvent annuler cette indisponibilité."))
        if expected_revision is not None and self.csrs_revision != expected_revision:
            raise UserError(_("L'indisponibilité a changé. Rechargez-la."))
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("Le motif d'annulation est obligatoire."))
        if self.csrs_cancelled_at:
            raise UserError(_("Cette indisponibilité est déjà annulée."))
        self.sudo().with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_cancelled_at": fields.Datetime.now(),
                "csrs_cancellation_reason": reason,
                "csrs_revision": self.csrs_revision + 1,
            }
        )
        return True

    def write(self, values):
        protected = {
            "csrs_revision",
            "csrs_cancelled_at",
            "csrs_cancellation_reason",
        }
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez l'action métier d'indisponibilité."))
        return super().write(values)


class CsrsVisitorVisit(models.Model):
    _name = "csrs.visitor.visit"
    _description = "Visite CSRS ENT"
    _order = "arrived_at desc, id desc"

    party_size = fields.Integer(required=True, default=1)
    visitor_names = fields.Json(default=list)
    arrived_at = fields.Datetime(required=True, default=fields.Datetime.now)
    departed_at = fields.Datetime(readonly=True)
    cancelled_at = fields.Datetime(readonly=True)
    revision = fields.Integer(required=True, default=1, readonly=True)

    @api.constrains("party_size", "visitor_names")
    def _check_party(self):
        for visit in self:
            if visit.party_size <= 0:
                raise ValidationError(_("Le nombre de visiteurs doit être positif."))
            names = visit.visitor_names or []
            if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
                raise ValidationError(_("La liste des visiteurs est invalide."))

    def action_departure(self, expected_revision=None):
        self.ensure_one()
        if expected_revision is not None and self.revision != expected_revision:
            raise UserError(_("La visite a changé. Rechargez-la."))
        if self.departed_at or self.cancelled_at:
            raise UserError(_("Cette visite est déjà terminée."))
        self.with_context(csrs_authorized_mutation=True).write(
            {"departed_at": fields.Datetime.now(), "revision": self.revision + 1}
        )
        return True

    def write(self, values):
        protected = {"departed_at", "cancelled_at", "revision"}
        if protected.intersection(values) and not self.env.context.get(
            "csrs_authorized_mutation"
        ):
            raise UserError(_("Utilisez une action métier de visite."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Une visite auditée ne peut pas être supprimée."))


class CsrsAgendaDraft(models.Model):
    _name = "csrs.agenda.draft"
    _description = "Brouillon d'agenda CSRS ENT"
    _order = "period_start desc, period_end desc"

    period_start = fields.Date(required=True, index=True)
    period_end = fields.Date(required=True, index=True)
    major_events = fields.Text(default="")
    revision = fields.Integer(required=True, default=1, readonly=True)
    updated_by_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, readonly=True
    )

    _period_unique = models.Constraint(
        "UNIQUE (period_start, period_end)",
        "Un brouillon existe déjà pour cette période.",
    )

    @api.constrains("period_start", "period_end")
    def _check_period(self):
        for draft in self:
            if draft.period_end < draft.period_start:
                raise ValidationError(_("La fin doit suivre le début de la période."))
            if (draft.period_end - draft.period_start).days > 30:
                raise ValidationError(_("La période ne peut pas dépasser 31 jours inclusifs."))

    def action_update(self, major_events, expected_revision=None):
        self.ensure_one()
        if expected_revision is not None and self.revision != expected_revision:
            raise UserError(_("Le brouillon a changé. Rechargez-le."))
        self.with_context(csrs_authorized_mutation=True).write(
            {
                "major_events": (major_events or "").strip(),
                "updated_by_id": self.env.user.id,
                "revision": self.revision + 1,
            }
        )
        return True

    def write(self, values):
        if not self.env.context.get("csrs_authorized_mutation"):
            raise UserError(_("Utilisez l'action métier du brouillon."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Un brouillon d'agenda ne peut pas être supprimé."))


class CsrsAgendaVersion(models.Model):
    _name = "csrs.agenda.version"
    _description = "Version figée d'agenda CSRS ENT"
    _order = "period_start desc, agenda_direction, version desc"

    draft_id = fields.Many2one(
        "csrs.agenda.draft", required=True, ondelete="restrict", index=True
    )
    period_start = fields.Date(required=True, readonly=True, index=True)
    period_end = fields.Date(required=True, readonly=True, index=True)
    agenda_direction = fields.Selection(
        AGENDA_DIRECTIONS, required=True, readonly=True, index=True
    )
    version = fields.Integer(required=True, readonly=True)
    snapshot = fields.Json(required=True, readonly=True)
    snapshot_sha256 = fields.Char(required=True, readonly=True)
    pdf_attachment_id = fields.Many2one(
        "ir.attachment", readonly=True, ondelete="restrict"
    )
    pdf_sha256 = fields.Char(readonly=True)
    pdf_size = fields.Integer(readonly=True)
    generated_by_id = fields.Many2one("res.users", required=True, readonly=True)
    generated_at = fields.Datetime(
        required=True, default=fields.Datetime.now, readonly=True
    )

    _version_unique = models.Constraint(
        "UNIQUE (period_start, period_end, agenda_direction, version)",
        "Cette version d'agenda existe déjà.",
    )

    @api.model
    def create_from_snapshot(self, draft, direction, snapshot):
        """Create, render and freeze one direction-specific agenda version."""
        if (
            not self.env.user.has_group("csrs_reporting.group_csrs_secretariat")
            and not self.env.user.has_group("csrs_reporting.group_csrs_it")
            and not self.env.user.csrs_has_active_role_grant("AGENDA_SECRETARIAT")
        ):
            raise UserError(_("Seul le secrétariat peut générer un agenda."))
        canonical = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        latest = self.sudo().search(
            [
                ("period_start", "=", draft.period_start),
                ("period_end", "=", draft.period_end),
                ("agenda_direction", "=", direction),
            ],
            order="version desc",
            limit=1,
        )
        version = self.sudo().create(
            {
                "draft_id": draft.id,
                "period_start": draft.period_start,
                "period_end": draft.period_end,
                "agenda_direction": direction,
                "version": (latest.version if latest else 0) + 1,
                "snapshot": snapshot,
                "snapshot_sha256": sha256(canonical).hexdigest(),
                "generated_by_id": self.env.user.id,
            }
        )
        pdf, _ = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "csrs_reporting.report_csrs_agenda", res_ids=version.ids
        )
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": (
                    f"agenda-{direction}-{draft.period_start}-{draft.period_end}"
                    f"-v{version.version}.pdf"
                ),
                "type": "binary",
                "raw": pdf,
                "mimetype": "application/pdf",
                "res_model": self._name,
                "res_id": version.id,
            }
        )
        version.with_context(csrs_authorized_mutation=True).write(
            {
                "pdf_attachment_id": attachment.id,
                "pdf_sha256": sha256(pdf).hexdigest(),
                "pdf_size": len(pdf),
            }
        )
        return version

    def write(self, values):
        if not self.env.context.get("csrs_authorized_mutation"):
            raise UserError(_("Une version d'agenda est immuable."))
        allowed = {"pdf_attachment_id", "pdf_sha256", "pdf_size"}
        if set(values) - allowed:
            raise UserError(_("Une version d'agenda est immuable."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Une version d'agenda est immuable."))
