"""Authoritative CSRS organization and scoped-role extensions in Odoo."""

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class HrDepartment(models.Model):
    _inherit = "hr.department"

    csrs_source_id = fields.Integer(
        string="Identifiant source CSRS", index=True, readonly=True, copy=False
    )
    csrs_code = fields.Char(string="Code CSRS", index=True, copy=False)

    _csrs_department_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)",
        "Cet identifiant source appartient déjà à un autre service.",
    )
    _csrs_department_code_unique = models.Constraint(
        "UNIQUE (csrs_code)", "Ce code CSRS appartient déjà à un autre service."
    )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    csrs_source_id = fields.Integer(
        string="Identifiant utilisateur source CSRS",
        index=True,
        readonly=True,
        copy=False,
    )
    csrs_secondary_manager_user_ids = fields.Many2many(
        "res.users",
        "csrs_employee_secondary_manager_rel",
        "employee_id",
        "user_id",
        string="Responsables secondaires CSRS",
        copy=False,
    )

    _csrs_employee_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)",
        "Cet utilisateur source possède déjà un employé Odoo.",
    )


class CsrsOrganizationMembership(models.Model):
    _name = "csrs.organization.membership"
    _description = "Rattachement organisationnel CSRS"
    _order = "is_primary desc, start_date desc, id desc"

    csrs_source_id = fields.Integer(required=True, index=True, readonly=True, copy=False)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict", index=True)
    department_id = fields.Many2one(
        "hr.department", required=True, ondelete="restrict", index=True
    )
    job_title = fields.Char(string="Fonction")
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    is_primary = fields.Boolean(required=True, default=False)
    active = fields.Boolean(default=True)

    _csrs_membership_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Ce rattachement source a déjà été importé."
    )
    _csrs_membership_dates = models.Constraint(
        "CHECK (end_date IS NULL OR end_date >= start_date)",
        "La fin du rattachement doit suivre son début.",
    )


class CsrsRoleGrant(models.Model):
    _name = "csrs.role.grant"
    _description = "Délégation de rôle CSRS"
    _order = "active desc, valid_from desc, id desc"

    csrs_source_id = fields.Integer(required=True, index=True, readonly=True, copy=False)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict", index=True)
    department_id = fields.Many2one(
        "hr.department", required=True, ondelete="restrict", index=True
    )
    role_code = fields.Char(required=True, index=True)
    scope = fields.Selection(
        [("unit", "Ce service"), ("tree", "Ce service et ses sous-services")],
        required=True,
        default="tree",
    )
    valid_from = fields.Datetime(required=True)
    valid_until = fields.Datetime()
    active = fields.Boolean(default=True)

    _csrs_role_grant_source_unique = models.Constraint(
        "UNIQUE (csrs_source_id)", "Cette délégation source a déjà été importée."
    )
    _csrs_role_grant_dates = models.Constraint(
        "CHECK (valid_until IS NULL OR valid_until > valid_from)",
        "La fin de la délégation doit suivre son début.",
    )

    def action_revoke(self):
        if not self.env.user.has_group("csrs_reporting.group_csrs_it"):
            raise UserError(_("Seul un administrateur IT peut révoquer une délégation."))
        self.write({"active": False, "valid_until": fields.Datetime.now()})
        return True

    def unlink(self):
        raise ValidationError(
            _("Une délégation doit être révoquée et ne peut pas être supprimée.")
        )
