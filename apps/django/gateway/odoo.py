"""Small JSON-RPC client used by every Django-to-Odoo call."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


class OdooError(RuntimeError):
    """Raised when Odoo is unreachable or rejects an RPC call."""


@dataclass(frozen=True, slots=True)
class OdooClient:
    """Call Odoo's RPC boundary without exposing transport details to views."""

    base_url: str
    database: str
    timeout: float = 5.0

    def version(self) -> dict[str, Any]:
        """Return the public Odoo server version payload."""
        result = self._call("common", "version", [])
        if not isinstance(result, dict):
            raise OdooError("Réponse de version Odoo invalide.")
        return result

    def _call(self, service: str, method: str, args: list[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": uuid4().hex,
        }
        request = Request(
            f"{self.base_url.rstrip('/')}/jsonrpc",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise OdooError("Odoo est indisponible.") from exc

        error = body.get("error") if isinstance(body, dict) else None
        if error:
            message = error.get("message", "Erreur RPC Odoo")
            raise OdooError(str(message))
        if not isinstance(body, dict) or "result" not in body:
            raise OdooError("Réponse RPC Odoo invalide.")
        return body["result"]
