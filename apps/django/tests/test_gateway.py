from base64 import b64encode
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

    def test_nested_react_route_uses_the_application_shell(self) -> None:
        response = self.client.get("/app/projets")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="root"></div>', html=True)

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
        session = self.client.session
        session["odoo_effective_role"] = "hr"
        session.save()
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
        self.assertNotIn("odoo_effective_role", self.client.session)
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

    @patch("gateway.views.OdooClient.call")
    def test_effective_role_is_forwarded_from_the_server_side_session(
        self, call: MagicMock
    ) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session["odoo_effective_role"] = "hr"
        session.save()
        call.return_value = {"user": {"id": 7}, "capabilities": {}}

        response = self.client.get("/api/v1/session/")

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_session",
            kwargs={"context": {"csrs_effective_role": "hr"}},
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_administrator_role_switch_is_validated_by_odoo_then_stored(
        self, call: MagicMock
    ) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()
        call.return_value = {
            "user": {"id": 7, "name": "Admin", "position": "IT"},
            "capabilities": {"admin": False, "manage_availability": True},
            "role_switcher": {
                "can_switch": True,
                "active_code": "hr",
                "active_label": "Ressources humaines",
                "roles": [],
            },
        }

        response = self.client.post(
            "/api/v1/session/role/",
            data=json.dumps({"role_code": "hr"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["odoo_effective_role"], "hr")
        self.assertEqual(response.json()["role_switcher"]["active_code"], "hr")
        call.assert_called_once_with("opaque-session", "api_role_switch", ["hr"])

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
        client = OdooClient("http://odoo:8069", "csrs_ent")

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
        client = OdooClient("http://odoo:8069", "csrs_ent")

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
        client = OdooClient("http://odoo:8069", "csrs_ent")

        with self.assertRaises(OdooAuthenticationError):
            client.authenticate("agent", "secret")

    @patch("gateway.odoo.urlopen")
    def test_business_call_uses_only_the_central_facade(self, urlopen: MagicMock) -> None:
        urlopen.return_value = self._response(
            {"jsonrpc": "2.0", "result": {"period": {"kind": "week"}}}
        )
        client = OdooClient("http://odoo:8069", "csrs_ent")

        result = client.call("opaque", "api_dashboard", [None, None])

        self.assertEqual(result, {"period": {"kind": "week"}})
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://odoo:8069/web/dataset/call_kw/csrs.api/api_dashboard",
        )
        self.assertEqual(request.headers["Cookie"], "session_id=opaque")
        payload = json.loads(request.data)
        self.assertEqual(payload["params"]["model"], "csrs.api")
        self.assertEqual(payload["params"]["method"], "api_dashboard")
        self.assertEqual(payload["params"]["args"], [None, None])
        self.assertEqual(payload["params"]["kwargs"], {})


class BusinessApiTests(SimpleTestCase):
    def setUp(self) -> None:
        session = self.client.session
        session["odoo_session_id"] = "opaque-session"
        session.save()

    @patch("gateway.api_views.OdooClient.call")
    def test_employee_profile_update_validates_then_delegates(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"state_token": "b" * 64}
        payload = {
            "state_token": "a" * 64,
            "terms_of_reference": "Préparer les activités de terrain.",
            "document": {
                "name": "tor.pdf",
                "mimetype": "application/pdf",
                "content_base64": b64encode(b"%PDF-1.4\n%%EOF\n").decode(),
            },
            "avatar": None,
            "remove_avatar": False,
            "remove_document": False,
        }

        response = self.client.patch(
            "/api/v1/team/17/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session", "api_team_employee_profile_update", [17, payload]
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_employee_avatar_is_returned_without_caching(
        self, call: MagicMock
    ) -> None:
        png = b"\x89PNG\r\n\x1a\nfixture"
        call.return_value = {
            "name": "avatar-17.png",
            "mimetype": "image/png",
            "content": b64encode(png).decode(),
        }

        response = self.client.get("/api/v1/team/17/avatar/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, png)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        call.assert_called_once_with(
            "opaque-session", "api_team_employee_avatar", [17]
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_task_bulk_delete_validates_then_delegates(self, call: MagicMock) -> None:
        call.return_value = {
            "audit_id": 8,
            "deleted_assignments": 1,
            "deleted_tasks": 1,
        }

        response = self.client.post(
            "/api/v1/tasks/bulk-delete/",
            data=json.dumps(
                {
                    "assignments": [{"id": 17, "revision": 3}],
                    "reason": "Tâche créée par erreur",
                    "confirmation": "SUPPRIMER",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_task_bulk_delete",
            [[{"id": 17, "revision": 3}], "Tâche créée par erreur"],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_task_management_delegates_validated_filters(self, call: MagicMock) -> None:
        call.return_value = {"items": [], "total": 0}

        response = self.client.get(
            "/api/v1/task-management/?q=note&status=active&page=2&page_size=20"
        )

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_task_management",
            ["note", "active", None, 2, 20],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_user_create_delegates_complete_organization_payload(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 44, "name": "Awa Doe"}
        payload = {
            "email": "awa@example.invalid",
            "login_alias": "awa",
            "first_name": "Awa",
            "last_name": "Doe",
            "position": "Analyste",
            "phone": "",
            "agenda_direction": "programs",
            "include_in_direction_agendas": True,
            "unit_ids": [3],
            "primary_unit_id": 3,
            "primary_supervisor_id": 7,
            "organization_effective_date": "2026-08-15",
        }

        response = self.client.post(
            "/api/v1/users/", data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with("opaque-session", "api_user_create", [payload])

    @patch("gateway.api_views.OdooClient.call")
    def test_programs_agenda_generation_is_validated_then_delegated(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 51, "agenda_direction": "programs"}
        payload = {
            "period_start": "2026-08-17",
            "period_end": "2026-08-23",
            "agenda_direction": "programs",
        }

        response = self.client.post(
            "/api/v1/agenda/versions/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with(
            "opaque-session", "api_agenda_generate", [payload]
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_temporary_password_response_is_never_cacheable(
        self, call: MagicMock
    ) -> None:
        call.return_value = {
            "temporary_password": "Temporary-Secret-123",
            "state_token": "next-token",
        }

        response = self.client.post(
            "/api/v1/users/44/temporary-password/",
            data=json.dumps({"state_token": "current-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        call.assert_called_once_with(
            "opaque-session",
            "api_user_temporary_password",
            [44, "current-token"],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_user_deactivation_delegates_the_expected_state(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 44, "is_active": False}

        response = self.client.post(
            "/api/v1/users/44/deactivate/",
            data=json.dumps({"state_token": "current-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_user_set_active",
            [44, "current-token", False],
        )

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

    @patch("gateway.api_views.OdooClient.call")
    def test_research_project_create_validates_then_delegates(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 71, "reference": "PRJ-00071"}
        payload = {
            "name": "Surveillance paludisme",
            "objectives": "Mesurer l'incidence.",
            "institutional_commitments": "Laboratoire et terrain",
            "date_start": "2026-09-01",
            "date_end": "2027-08-31",
            "donor_id": 31,
            "partner_ids": [32],
        }

        response = self.client.post(
            "/api/v1/research-projects/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with(
            "opaque-session", "api_research_project_create", [payload]
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_research_project_list_delegates_the_archive_filter(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"items": []}

        response = self.client.get("/api/v1/research-projects/?status=archived")

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session", "api_research_projects", ["archived"]
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_research_project_archive_requires_a_reason_and_delegates(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 71, "archived": True, "revision": 5}

        invalid = self.client.post(
            "/api/v1/research-projects/71/transition/",
            data=json.dumps({"action": "archive", "revision": 4, "reason": ""}),
            content_type="application/json",
        )
        response = self.client.post(
            "/api/v1/research-projects/71/transition/",
            data=json.dumps(
                {
                    "action": "archive",
                    "revision": 4,
                    "reason": "Projet remplacé par la nouvelle convention",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_research_project_transition",
            [
                71,
                {
                    "action": "archive",
                    "revision": 4,
                    "lead_id": None,
                    "reason": "Projet remplacé par la nouvelle convention",
                },
            ],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_partner_administration_uses_typed_it_only_contract(
        self, call: MagicMock
    ) -> None:
        payload = {
            "name": "Fondation santé",
            "email": "contact@example.test",
            "phone": "01020304",
            "active": True,
        }
        call.return_value = {"id": 31, **payload, "state_token": "token"}

        response = self.client.post(
            "/api/v1/partners/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with("opaque-session", "api_partner_create", [payload])

    @patch("gateway.api_views.OdooClient.call")
    def test_partner_update_requires_its_state_token(self, call: MagicMock) -> None:
        response = self.client.patch(
            "/api/v1/partners/31/",
            data=json.dumps({"name": "Fondation santé", "active": False}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        call.assert_not_called()

    @patch("gateway.api_views.OdooClient.call")
    def test_project_section_transition_preserves_the_revision_contract(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 71, "revision": 4}

        response = self.client.post(
            "/api/v1/research-projects/71/sections/8/transition/",
            data=json.dumps(
                {
                    "action": "correct",
                    "revision": 3,
                    "reason": "Ajouter la preuve terrain",
                    "confirmation": "",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        call.assert_called_once_with(
            "opaque-session",
            "api_research_project_section_transition",
            [
                71,
                8,
                {
                    "action": "correct",
                    "revision": 3,
                    "reason": "Ajouter la preuve terrain",
                    "confirmation": "",
                },
            ],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_project_item_create_preserves_values_and_revision(
        self, call: MagicMock
    ) -> None:
        call.return_value = {"id": 71, "revision": 5}
        payload = {
            "revision": 4,
            "values": {
                "name": "Résultat scientifique",
                "indicator": "Publications",
                "target_value": "3",
            },
        }

        response = self.client.post(
            "/api/v1/research-projects/71/items/results/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with(
            "opaque-session",
            "api_research_project_item_save",
            [71, "results", payload, None],
        )

    @patch("gateway.api_views.OdooClient.call")
    def test_process_create_delegates_a_typed_mission_form(self, call: MagicMock) -> None:
        call.return_value = {"id": 19, "reference": "OM-00019"}
        payload = {
            "process_type": "mission",
            "origin_department_id": 4,
            "project_id": None,
            "subject": "Mission Korhogo",
            "description": "Supervision des sites",
            "amount": "0.00",
            "details": {
                "destination": "Korhogo",
                "purpose": "Supervision",
                "departure_date": "2026-09-01",
                "return_date": "2026-09-05",
                "vehicle_required": True,
            },
            "documents": [],
        }

        response = self.client.post(
            "/api/v1/processes/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        call.assert_called_once_with("opaque-session", "api_process_create", [payload])
