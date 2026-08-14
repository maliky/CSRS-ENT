"""Typed HTTP boundary used by every Django-to-Odoo call."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
import json
from typing import Any, TypeAlias
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
JsonObject: TypeAlias = dict[str, JsonValue]


class OdooError(RuntimeError):
    """Raised when Odoo is unreachable or returns an invalid response."""


class OdooAuthenticationError(OdooError):
    """Raised when Odoo rejects user credentials or a technical session."""


@dataclass(frozen=True, slots=True)
class OdooVersion:
    """Validated subset of Odoo's public version response."""

    server_version: str


@dataclass(frozen=True, slots=True)
class OdooIdentity:
    """Identity fields exposed to Django after Odoo authentication."""

    user_id: int
    login: str
    name: str


@dataclass(frozen=True, slots=True)
class OdooSession:
    """Revocable Odoo session relayed through Django's server-side session."""

    session_id: str
    identity: OdooIdentity


def _json_object(value: Any) -> JsonObject:
    """Validate an untrusted JSON value at the transport boundary."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OdooError("Réponse JSON Odoo invalide.")
    return value


def _required_int(payload: JsonObject, key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise OdooError(f"Champ Odoo invalide : {key}.")
    return value


def _required_string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise OdooError(f"Champ Odoo invalide : {key}.")
    return value


@dataclass(frozen=True, slots=True)
class OdooClient:
    """Call supported Odoo web controllers without leaking transport details."""

    base_url: str
    database: str
    timeout: float = 5.0

    def version(self) -> OdooVersion:
        """Return the public Odoo server version."""
        request = Request(
            f"{self.base_url.rstrip('/')}/web/version",
            headers={"Accept": "application/json"},
            method="GET",
        )
        payload, _ = self._send(request)
        version = payload.get("version", payload.get("server_version"))
        if not isinstance(version, str) or not version:
            raise OdooError("Champ Odoo invalide : version.")
        return OdooVersion(server_version=version)

    def authenticate(self, login: str, password: str) -> OdooSession:
        """Authenticate against Odoo and return its opaque session identifier."""
        payload, set_cookie = self._jsonrpc(
            "/web/session/authenticate",
            {"db": self.database, "login": login, "password": password},
        )
        result = self._result_object(payload, authentication=True)
        user_id = result.get("uid")
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            raise OdooAuthenticationError("Identifiants invalides.")
        cookie = SimpleCookie()
        if set_cookie:
            cookie.load(set_cookie)
        morsel = cookie.get("session_id")
        if morsel is None or not morsel.value:
            raise OdooError("Odoo n'a pas créé de session.")
        login_value = result.get("username")
        if not isinstance(login_value, str) or not login_value:
            login_value = login
        return OdooSession(
            session_id=morsel.value,
            identity=OdooIdentity(
                user_id=user_id,
                login=login_value,
                name=_required_string(result, "name"),
            ),
        )

    def session_identity(self, session_id: str) -> OdooIdentity:
        """Validate a stored session with Odoo and return its current identity."""
        payload, _ = self._jsonrpc(
            "/web/session/get_session_info", {}, session_id=session_id
        )
        result = self._result_object(payload, authentication=True)
        return OdooIdentity(
            user_id=_required_int(result, "uid"),
            login=_required_string(result, "username"),
            name=_required_string(result, "name"),
        )

    def destroy_session(self, session_id: str) -> None:
        """Revoke Odoo; callers may still clear their local session on error."""
        payload, _ = self._jsonrpc("/web/session/destroy", {}, session_id=session_id)
        self._raise_rpc_error(payload, authentication=True)

    def _jsonrpc(
        self,
        route: str,
        params: JsonObject,
        *,
        session_id: str | None = None,
    ) -> tuple[JsonObject, str | None]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if session_id:
            headers["Cookie"] = f"session_id={session_id}"
        request = Request(
            f"{self.base_url.rstrip('/')}{route}",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": params,
                    "id": uuid4().hex,
                }
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return self._send(request)

    def _send(self, request: Request) -> tuple[JsonObject, str | None]:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                set_cookie = response.headers.get("Set-Cookie")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise OdooError("Odoo est indisponible.") from exc
        try:
            payload = _json_object(json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, OdooError) as exc:
            raise OdooError("Réponse JSON Odoo invalide.") from exc
        return payload, set_cookie

    @staticmethod
    def _raise_rpc_error(payload: JsonObject, *, authentication: bool) -> None:
        error = payload.get("error")
        if error is None:
            return
        if authentication:
            raise OdooAuthenticationError("Session ou identifiants Odoo invalides.")
        raise OdooError("Odoo a rejeté la requête.")

    def _result_object(self, payload: JsonObject, *, authentication: bool) -> JsonObject:
        self._raise_rpc_error(payload, authentication=authentication)
        result = payload.get("result")
        if not isinstance(result, dict):
            if authentication:
                raise OdooAuthenticationError("Session ou identifiants Odoo invalides.")
            raise OdooError("Réponse RPC Odoo invalide.")
        return _json_object(result)
