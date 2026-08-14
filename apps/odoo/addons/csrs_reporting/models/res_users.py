"""CSRS identity extensions and temporary Django-hash compatibility."""

import re

from odoo import _, api, fields, models, tools
from odoo.addons.base.models.res_users import CryptContext, MIN_ROUNDS
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain


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
        return Domain("login", "=ilike", normalized) | Domain(
            "csrs_alias", "=ilike", normalized
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
        return super()._get_session_token_fields() | {"csrs_alias"}

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
