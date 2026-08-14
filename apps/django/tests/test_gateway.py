import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase

from gateway.odoo import (
    OdooAuthenticationError,
    OdooClient,
    OdooError,
    OdooIdentity,
    OdooSession,
    OdooVersion,
)


class GatewayViewTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_index_keeps_the_classic_django_entry_point(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PENT")
        self.assertContains(response, "/app/")

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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False})
        self.assertIn("csrftoken", response.cookies)

    @patch("gateway.views.OdooClient.authenticate")
    def test_login_stores_only_the_opaque_odoo_session(
        self, authenticate: MagicMock
    ) -> None:
        authenticate.return_value = OdooSession(
            session_id="opaque-session",
            identity=OdooIdentity(user_id=42, login="agent", name="Agent CSRS"),
        )

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

    @patch("gateway.views.OdooClient.session_identity")
    def test_session_is_revalidated_by_odoo(self, identity: MagicMock) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()
        identity.return_value = OdooIdentity(7, "agent", "Agent CSRS")

        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        identity.assert_called_once_with("opaque-session")

    @patch(
        "gateway.views.OdooClient.session_identity",
        side_effect=OdooAuthenticationError("revoked"),
    )
    def test_revoked_odoo_session_is_removed(self, identity: MagicMock) -> None:
        session = self.client.session
        session["odoo_session_id"] = "revoked-session"
        session.save()

        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.json(), {"authenticated": False})
        self.assertNotIn("odoo_session_id", self.client.session)
        identity.assert_called_once_with("revoked-session")

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
