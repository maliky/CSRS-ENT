"""Thin HTTP views for pages, health checks and relayed Odoo sessions."""

from __future__ import annotations

import json
from typing import TypedDict

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .auth import LoginRateLimiter, client_ip, normalize_login
from .odoo import OdooAuthenticationError, OdooClient, OdooError


class LoginPayload(TypedDict):
    login: str
    password: str


def _client() -> OdooClient:
    return OdooClient(
        base_url=settings.ODOO_URL,
        database=settings.ODOO_DATABASE,
        timeout=settings.ODOO_TIMEOUT,
    )


def _login_payload(request: HttpRequest) -> LoginPayload | None:
    if request.content_type != "application/json" or len(request.body) > 8192:
        return None
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    login = value.get("login")
    password = value.get("password")
    if not isinstance(login, str) or not isinstance(password, str):
        return None
    normalized = normalize_login(login)
    if not normalized or not password or len(normalized) > 254 or len(password) > 4096:
        return None
    return {"login": normalized, "password": password}


def _session_payload(request: HttpRequest) -> dict[str, object] | None:
    session_id = request.session.get("odoo_session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    try:
        payload = _client().call(session_id, "api_session")
    except (OdooAuthenticationError, OdooError):
        request.session.flush()
        return None
    if not isinstance(payload, dict):
        request.session.flush()
        return None
    return dict(payload)


@ensure_csrf_cookie
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    """Use React as the single public entry point."""
    return redirect("/app/")


@ensure_csrf_cookie
@require_GET
def react_app(request: HttpRequest) -> HttpResponse:
    """Serve the progressively enhanced React shell at /app/."""
    return render(request, "gateway/react.html")


@ensure_csrf_cookie
@require_GET
def login_page(request: HttpRequest) -> HttpResponse:
    """Keep old bookmarks working without exposing a second login surface."""
    return redirect("/app/")


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Report that the Django process can serve requests."""
    return JsonResponse({"status": "ok", "service": "django"})


@require_GET
def readiness(request: HttpRequest) -> JsonResponse:
    """Report whether Django can reach its authoritative Odoo service."""
    try:
        version = _client().version()
    except OdooError:
        return JsonResponse({"status": "unavailable", "service": "odoo"}, status=503)
    return JsonResponse(
        {
            "status": "ok",
            "service": "odoo",
            "server_version": version.server_version,
        }
    )


@ensure_csrf_cookie
@require_http_methods(["GET"])
def session_detail(request: HttpRequest) -> JsonResponse:
    """Return the current Odoo-backed identity without exposing its session id."""
    payload = _session_payload(request)
    if payload is None:
        return JsonResponse(
            {
                "error": {
                    "code": "authentication_required",
                    "message": "Authentification requise.",
                    "fields": {},
                }
            },
            status=401,
        )
    payload["csrf_token"] = get_token(request)
    return JsonResponse(payload)


@require_POST
def session_login(request: HttpRequest) -> JsonResponse:
    """Authenticate with Odoo and keep only its opaque session id in Redis."""
    payload = _login_payload(request)
    if payload is None:
        return JsonResponse({"error": "invalid_request"}, status=400)
    ip_address = client_ip(dict(request.META), settings.TRUSTED_PROXY_ADDRESSES)
    limiter = LoginRateLimiter(cache=cache)
    if limiter.is_blocked(ip_address, payload["login"]):
        return JsonResponse({"error": "rate_limited"}, status=429)
    try:
        odoo_session = _client().authenticate(payload["login"], payload["password"])
    except OdooAuthenticationError:
        limiter.record_failure(ip_address, payload["login"])
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    except OdooError:
        return JsonResponse({"error": "odoo_unavailable"}, status=503)
    limiter.clear(ip_address, payload["login"])
    request.session.cycle_key()
    request.session["odoo_session_id"] = odoo_session.session_id
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    session_payload = _session_payload(request)
    if session_payload is None:
        return JsonResponse({"error": "odoo_unavailable"}, status=503)
    session_payload["csrf_token"] = get_token(request)
    return JsonResponse(session_payload)


@require_POST
def session_logout(request: HttpRequest) -> JsonResponse:
    """Revoke Odoo best-effort and always remove the local technical session."""
    session_id = request.session.get("odoo_session_id")
    if isinstance(session_id, str) and session_id:
        try:
            _client().destroy_session(session_id)
        except OdooError:
            pass
    request.session.flush()
    return JsonResponse({"authenticated": False})
