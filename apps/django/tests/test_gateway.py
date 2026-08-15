import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase

from gateway.odoo import (
    OdooAuthenticationError,
    OdooClient,
    OdooConflictError,
    OdooError,
    OdooIdentity,
    OdooSession,
    OdooVersion,
)


class GatewayViewTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_root_redirects_to_the_unique_react_entry_point(self) -> None:
        response = self.client.get("/")

        self.assertRedirects(response, "/app/", fetch_redirect_response=False)

    def test_old_login_url_redirects_to_the_unique_react_entry_point(self) -> None:
        response = self.client.get("/connexion/")

        self.assertRedirects(response, "/app/", fetch_redirect_response=False)

    def test_health_does_not_depend_on_odoo(self) -> None:
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "django"})

    @patch("gateway.views.OdooClient.version", return_value=OdooVersion("19.0"))
    def test_readiness_reports_odoo_version(self, version: MagicMock) -> None:
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["server_version"], "19.0")
        version.assert_called_once_with()

    @patch("gateway.views.OdooClient.version", side_effect=OdooError("offline"))
    def test_readiness_fails_closed_when_odoo_is_unavailable(
        self, version: MagicMock
    ) -> None:
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable", "service": "odoo"})
        version.assert_called_once_with()

    def test_anonymous_session_response_sets_a_csrf_cookie(self) -> None:
        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")
        self.assertIn("csrftoken", response.cookies)

    @patch("gateway.views.OdooClient.call")
    @patch("gateway.views.OdooClient.authenticate")
    def test_login_stores_only_the_opaque_odoo_session(
        self, authenticate: MagicMock, call: MagicMock
    ) -> None:
        authenticate.return_value = OdooSession(
            session_id="opaque-session",
            identity=OdooIdentity(user_id=42, login="agent", name="Agent CSRS"),
        )
        call.return_value = {
            "user": {
                "id": 42,
                "name": "Agent CSRS",
                "position": "Agent",
                "login_alias": "agent",
            },
            "capabilities": {"create_task": False},
        }

        response = self.client.post(
            "/api/v1/session/login/",
            data=json.dumps({"login": " AGENT ", "password": "secret"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], 42)
        self.assertEqual(self.client.session["odoo_session_id"], "opaque-session")
        self.assertNotIn("password", dict(self.client.session))
        authenticate.assert_called_once_with("agent", "secret")
        call.assert_called_once_with("opaque-session", "api_session")

    @patch(
        "gateway.views.OdooClient.authenticate",
        side_effect=OdooAuthenticationError("invalid"),
    )
    def test_login_is_limited_after_five_failures(self, authenticate: MagicMock) -> None:
        payload = json.dumps({"login": "agent", "password": "bad"})
        for _ in range(5):
            response = self.client.post(
                "/api/v1/session/login/", data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 401)

        response = self.client.post(
            "/api/v1/session/login/", data=payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"error": "rate_limited"})
        self.assertEqual(authenticate.call_count, 5)

    def test_login_rejects_a_missing_csrf_token(self) -> None:
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            "/api/v1/session/login/",
            data=json.dumps({"login": "agent", "password": "secret"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("gateway.views.OdooClient.call")
    def test_session_is_revalidated_by_odoo(self, call: MagicMock) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()
        call.return_value = {
            "user": {
                "id": 7,
                "name": "Agent CSRS",
                "position": "Agent",
                "login_alias": "agent",
            },
            "capabilities": {"create_task": False},
        }

        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], 7)
        self.assertIn("csrf_token", response.json())
        call.assert_called_once_with("opaque-session", "api_session")

    @patch(
        "gateway.views.OdooClient.call",
        side_effect=OdooAuthenticationError("revoked"),
    )
    def test_revoked_odoo_session_is_removed(self, call: MagicMock) -> None:
        session = self.client.session
        session["odoo_session_id"] = "revoked-session"
        session.save()

        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("odoo_session_id", self.client.session)
        call.assert_called_once_with("revoked-session", "api_session")

    @patch("gateway.views.OdooClient.destroy_session")
    def test_logout_revokes_both_sessions(self, destroy: MagicMock) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()

        response = self.client.post("/api/v1/session/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("odoo_session_id", self.client.session)
        destroy.assert_called_once_with("opaque-session")


class OdooClientTests(SimpleTestCase):
    def _response(self, payload: object, cookie: str | None = None) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode()
        response.headers.get.return_value = cookie
        return response

    @patch("gateway.odoo.urlopen")
    def test_version_uses_the_supported_web_endpoint(self, urlopen: MagicMock) -> None:
        urlopen.return_value = self._response({"version": "19.0"})
        client = OdooClient("http://odoo:8069", "pent_odoo")

        version = client.version()

        self.assertEqual(version, OdooVersion("19.0"))
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://odoo:8069/web/version")

    @patch("gateway.odoo.urlopen")
    def test_authenticate_returns_only_validated_identity_and_cookie(
        self, urlopen: MagicMock
    ) -> None:
        urlopen.return_value = self._response(
            {
                "jsonrpc": "2.0",
                "result": {"uid": 9, "username": "agent@csrs", "name": "Agent"},
            },
            "session_id=opaque; HttpOnly; Path=/",
        )
        client = OdooClient("http://odoo:8069", "pent_odoo")

        session = client.authenticate("agent", "secret")

        self.assertEqual(session.session_id, "opaque")
        self.assertEqual(session.identity.user_id, 9)

    @patch("gateway.odoo.urlopen")
    def test_authenticate_maps_rpc_errors_to_a_safe_exception(
        self, urlopen: MagicMock
    ) -> None:
        urlopen.return_value = self._response(
            {"jsonrpc": "2.0", "error": {"message": "Access denied"}}
        )
        client = OdooClient("http://odoo:8069", "pent_odoo")

        with self.assertRaises(OdooAuthenticationError):
            client.authenticate("agent", "secret")

    @patch("gateway.odoo.urlopen")
    def test_business_call_uses_only_the_central_facade(self, urlopen: MagicMock) -> None:
        urlopen.return_value = self._response(
            {"jsonrpc": "2.0", "result": {"period": {"kind": "week"}}}
        )
        client = OdooClient("http://odoo:8069", "pent_odoo")

        result = client.call("opaque", "api_dashboard", [None, None])

        self.assertEqual(result, {"period": {"kind": "week"}})
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://odoo:8069/web/dataset/call_kw/csrs.api/api_dashboard",
        )
        self.assertEqual(request.headers["Cookie"], "session_id=opaque")


class BusinessApiTests(SimpleTestCase):
    def setUp(self) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()

    @patch("gateway.api_views.OdooClient.call")
    def test_progress_endpoint_validates_then_delegates(self, call: MagicMock) -> None:
        call.return_value = {"id": 17, "revision": 3, "percentage": 50}

        response = self.client.post(
            "/api/v1/tasks/17/progress/",
            data=json.dumps(
                {
                    "revision": 2,
                    "entry_date": "2026-08-15",
                    "percentage": 50,
                    "note": "À mi-parcours",
                    "blocked": False,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 3)
        call.assert_called_once_with(
            "opaque-session",
            "api_task_progress",
            [
                17,
                {
                    "revision": 2,
                    "entry_date": "2026-08-15",
                    "percentage": 50,
                    "note": "À mi-parcours",
                    "blocked": False,
                },
            ],
        )

    @patch(
        "gateway.api_views.OdooClient.call",
        side_effect=OdooConflictError("La tâche a changé. Rechargez-la."),
    )
    def test_stale_revision_is_an_http_conflict(self, call: MagicMock) -> None:
        response = self.client.post(
            "/api/v1/tasks/17/observations/",
            data=json.dumps({"revision": 2, "message": "Suivi"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "stale_revision")
        call.assert_called_once()

    def test_business_endpoint_requires_an_odoo_session(self) -> None:
        self.client.session.flush()

        response = self.client.get("/api/v1/dashboard/")

        self.assertEqual(response.status_code, 401)
