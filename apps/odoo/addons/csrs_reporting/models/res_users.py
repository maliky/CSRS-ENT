"""CSRS identity extensions and temporary Django-hash compatibility."""

import re

from odoo import _, api, fields, models, tools
from odoo.addons.base.models.res_users import CryptContext, MIN_ROUNDS
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

from .roles import IT_GROUP, ROLE_PROFILE_BY_CODE, SWITCHABLE_GROUP_XMLIDS


DJANGO_HASH_RE = re.compile(
    r"^pbkdf2_sha256\$(?P<rounds>[1-9][0-9]{4,7})\$[A-Za-z0-9]+\$[A-Za-z0-9+/=]+$"
)


class ResUsers(models.Model):
    _inherit = "res.users"

    csrs_source_id = fields.Integer(
        string="Identifiant source CSRS", index=True, readonly=True, copy=False
    )
    csrs_alias = fields.Char(
        string="Identifiant court CSRS", index=True, copy=False
    )
    csrs_first_name = fields.Char(string="Prénom CSRS", copy=False)
    csrs_last_name = fields.Char(string="Nom CSRS", copy=False)
    csrs_password_change_required = fields.Boolean(
        string="Changement de mot de passe requis", default=False, copy=False
    )

    _csrs_source_id_unique = models.Constraint(
        "UNIQUE (csrs_source_id)",
        "Cet identifiant source CSRS appartient déjà à un autre compte.",
    )
    _csrs_alias_unique = models.Constraint(
        "UNIQUE (csrs_alias)",
        "Cet identifiant court CSRS appartient déjà à un autre compte.",
    )

    def init(self):
        """Encrypt plaintext rows while preserving recognized legacy hashes."""
        self.env.cr.execute(
            r"""
            SELECT id, password FROM res_users
            WHERE password IS NOT NULL
              AND password !~ '^\$[^$]+\$[^$]+\$.'
            """
        )
        users = self.sudo()
        context = users._crypt_context()
        for user_id, password in self.env.cr.fetchall():
            if context.identify(password) == "plaintext":
                users.browse(user_id).password = password

    @api.model
    def _get_login_domain(self, login):
        normalized = (login or "").strip().lower()
        return (
            Domain("login", "=ilike", normalized)
            | Domain("email", "=ilike", normalized)
            | Domain("csrs_alias", "=ilike", normalized)
        )

    @tools.ormcache(cache="stable")
    def _crypt_context(self):
        config = self.env["ir.config_parameter"].sudo()
        return CryptContext(
            ["pbkdf2_sha512", "django_pbkdf2_sha256", "plaintext"],
            deprecated=["auto"],
            pbkdf2_sha512__rounds=max(
                MIN_ROUNDS,
                int(config.get_param("password.hashing.rounds", 0)),
            ),
        )

    def _get_session_token_fields(self):
        return super()._get_session_token_fields() | {"csrs_alias", "email"}

    def csrs_active_role_grants(self, role_codes):
        """Return only currently valid grants; groups never stand in for scope."""
        self.ensure_one()
        codes = [role_codes] if isinstance(role_codes, str) else list(role_codes)
        now = fields.Datetime.now()
        return self.env["csrs.role.grant"].sudo().search(
            [
                ("user_id", "=", self.id),
                ("role_code", "in", codes),
                ("active", "=", True),
                ("valid_from", "<=", now),
                "|",
                ("valid_until", "=", False),
                ("valid_until", ">", now),
            ]
        )

    def csrs_has_active_role_grant(self, *role_codes):
        """Feature roles follow legacy CSRS semantics while retaining grant dates."""
        self.ensure_one()
        return bool(self.csrs_active_role_grants(role_codes))

    def csrs_effective_role_code(self):
        """Return a validated role context only for the real IT administrator."""
        self.ensure_one()
        role_code = self.env.context.get("csrs_effective_role")
        if (
            self != self.env.user
            or not isinstance(role_code, str)
            or role_code not in ROLE_PROFILE_BY_CODE
            or not self.env.user.has_group(IT_GROUP)
        ):
            return None
        return role_code

    def csrs_has_effective_group(self, xmlid):
        """Resolve CSRS business groups through the administrator's selected role."""
        self.ensure_one()
        role_code = self.csrs_effective_role_code()
        if not role_code:
            return self.has_group(xmlid)
        if xmlid == "base.group_system":
            return False
        if xmlid in SWITCHABLE_GROUP_XMLIDS:
            return xmlid in ROLE_PROFILE_BY_CODE[role_code].group_xmlids
        return self.has_group(xmlid)

    def csrs_import_legacy_password_hash(self, password_hash, replace_native=False):
        """Install one validated Django hash without ever logging its value."""
        self.ensure_one()
        if not self.env.is_superuser() and not self.env.user.has_group(
            "csrs_reporting.group_csrs_it"
        ):
            raise AccessError(_("Seul un administrateur IT peut reprendre un mot de passe."))
        match = DJANGO_HASH_RE.fullmatch(password_hash or "")
        if not match:
            raise ValidationError(_("Empreinte Django invalide."))
        rounds = int(match.group("rounds"))
        if not 100_000 <= rounds <= 2_000_000:
            raise ValidationError(_("Facteur de travail Django non autorisé."))
        if self._crypt_context().identify(password_hash) != "django_pbkdf2_sha256":
            raise ValidationError(_("Algorithme de mot de passe non reconnu."))
        self.env.cr.execute("SELECT password FROM res_users WHERE id=%s", [self.id])
        [stored_hash] = self.env.cr.fetchone()
        if stored_hash == password_hash:
            return False
        stored_scheme = self._crypt_context().identify(stored_hash or "")
        if stored_scheme == "pbkdf2_sha512" and not replace_native:
            return False
        self._set_encrypted_password(self.id, password_hash)
        return True

    def action_csrs_change_own_password(self, current_password, new_password):
        """Change the current user's password without exposing it to Django state."""
        self.ensure_one()
        if self != self.env.user:
            raise AccessError(_("Vous ne pouvez modifier que votre mot de passe."))
        self._check_credentials(
            {"type": "password", "password": current_password},
            {"interactive": True},
        )
        if not isinstance(new_password, str) or len(new_password) < 12:
            raise ValidationError(
                _("Le nouveau mot de passe doit contenir au moins 12 caractères.")
            )
        if new_password == current_password:
            raise ValidationError(
                _("Le nouveau mot de passe doit être différent du mot de passe actuel.")
            )
        self.password = new_password
        self.csrs_password_change_required = False
        return True
