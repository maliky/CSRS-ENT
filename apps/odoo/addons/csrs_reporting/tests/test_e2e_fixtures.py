from odoo.tests.common import TransactionCase, tagged

from ..models.processes import PROCESS_TYPES


@tagged("post_install", "-at_install")
class CsrsE2EFixtureTests(TransactionCase):
    def test_fixture_dataset_is_repeatable_complete_and_scoped(self):
        fixture = self.env["csrs.e2e.fixture"]
        dataset = "e2e-transaction"
        password = "FixturePassword-2026!"
        unrelated = self.env["hr.department"].create({"name": "Unité préservée"})

        first = fixture._execute("seed", dataset, password=password)
        second = fixture._execute("seed", dataset, password=password)
        status = fixture._execute("status", dataset)

        self.assertGreater(first["created"]["res.users"], 0)
        self.assertGreater(first["created"]["hr.department"], 0)
        self.assertGreater(first["created"]["project.task"], 0)
        self.assertEqual(sum(second["created"].values()), 0)
        self.assertEqual(status["counts"], first["counts"])
        project = self.env.ref(
            "csrs_reporting_e2e.e2e_transaction__research_project"
        )
        self.assertEqual(len(project.csrs_section_ids), 9)
        process_types = set(
            self.env["csrs.process.case"]
            .search([("subject", "like", "[E2E:e2e-transaction]")])
            .mapped("process_type")
        )
        self.assertEqual(process_types, set(dict(PROCESS_TYPES)))

        cleaned = fixture._execute("clean", dataset)

        self.assertGreater(cleaned["deleted_total"], 0)
        self.assertEqual(fixture._execute("status", dataset)["total"], 0)
        self.assertTrue(unrelated.exists())
