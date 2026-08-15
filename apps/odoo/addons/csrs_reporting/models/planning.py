"""Institutional planning taxonomy kept separate from research projects."""

from odoo import fields, models


class CsrsStrategicPlan(models.Model):
    _name = "csrs.strategic.plan"
    _description = "Plan stratégique CSRS"
    _order = "start_date desc, name, id"

    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    name = fields.Char(required=True, index="trigram")
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    active = fields.Boolean(default=True)
    action_plan_ids = fields.One2many(
        "csrs.action.plan", "strategic_plan_id", string="Plans d'action"
    )

    _source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Ce plan stratégique source est déjà importé."
    )


class CsrsActionPlan(models.Model):
    _name = "csrs.action.plan"
    _description = "Plan d'action institutionnel CSRS"
    _order = "code, name, id"

    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    strategic_plan_id = fields.Many2one(
        "csrs.strategic.plan", required=True, ondelete="restrict", index=True
    )
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, index="trigram")
    active = fields.Boolean(default=True)
    action_ids = fields.One2many(
        "csrs.institutional.action", "action_plan_id", string="Actions"
    )

    _source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Ce plan d'action source est déjà importé."
    )
    _code_unique = models.Constraint(
        "UNIQUE (code)", "Ce code de plan d'action est déjà utilisé."
    )


class CsrsInstitutionalAction(models.Model):
    _name = "csrs.institutional.action"
    _description = "Action institutionnelle CSRS"
    _order = "code, name, id"

    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    action_plan_id = fields.Many2one(
        "csrs.action.plan", required=True, ondelete="restrict", index=True
    )
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, index="trigram")
    active = fields.Boolean(default=True)

    _source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Cette action source est déjà importée."
    )
    _code_unique = models.Constraint(
        "UNIQUE (code)", "Ce code d'action institutionnelle est déjà utilisé."
    )


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    csrs_source_version = fields.Char(readonly=True, copy=False)

    _csrs_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Ce calendrier source est déjà importé."
    )


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    csrs_source_id = fields.Integer(index=True, readonly=True, copy=False)
    csrs_is_working_day = fields.Boolean(default=False, readonly=True, copy=False)

    _csrs_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Cette exception de calendrier est déjà importée."
    )
