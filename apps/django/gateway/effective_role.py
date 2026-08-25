"""Pure helpers for the server-side effective-role session context."""

from __future__ import annotations

from .odoo import JsonObject


SESSION_EFFECTIVE_ROLE_KEY = "odoo_effective_role"


def effective_role_rpc_kwargs(value: object) -> JsonObject | None:
    """Build an Odoo context only from a previously validated session value."""
    if not isinstance(value, str):
        return None
    role_code = value.strip()
    if not role_code or len(role_code) > 64:
        return None
    return {"context": {"csrs_effective_role": role_code}}
