from unittest.mock import patch

from django.test import SimpleTestCase

from gateway.odoo import OdooError


class GatewayViewTests(SimpleTestCase):
    def test_index_declares_odoo_as_source_of_truth(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_of_truth"], "odoo")

    def test_health_does_not_depend_on_odoo(self) -> None:
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "django"})

    @patch("gateway.views.OdooClient.version")
    def test_readiness_reports_odoo_version(self, version: object) -> None:
        version.return_value = {"server_version": "19.0"}  # type: ignore[attr-defined]

        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["server_version"], "19.0")

    @patch("gateway.views.OdooClient.version", side_effect=OdooError("offline"))
    def test_readiness_fails_closed_when_odoo_is_unavailable(
        self, version: object
    ) -> None:
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"status": "unavailable", "service": "odoo"}
        )
