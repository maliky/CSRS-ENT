from datetime import timedelta

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
        draft = self.env.ref("csrs_reporting_e2e.e2e_transaction__agenda_draft")
        secretariat = self.env.ref(
            "csrs_reporting_e2e.e2e_transaction__user_secretariat"
        )
        self.env["csrs.api"].with_user(secretariat).api_agenda_generate(
            {
                "period_start": draft.period_start.isoformat(),
                "period_end": draft.period_end.isoformat(),
                "agenda_direction": "research",
            }
        )
        generated_status = fixture._execute("status", dataset)
        self.assertEqual(generated_status["counts"]["csrs.agenda.version"], 1)
        self.assertEqual(generated_status["counts"]["ir.attachment"], 2)
        purchase_case = self.env["csrs.process.case"].search(
            [("subject", "like", f"[E2E:{dataset}]"), ("process_type", "=", "purchase")],
            limit=1,
        )
        purchase_case.with_user(purchase_case.requester_id).action_transition(
            "submit", purchase_case.revision
        )
        self.assertTrue(purchase_case.event_ids)

        cleaned = fixture._execute("clean", dataset)

        self.assertGreater(cleaned["deleted_total"], 0)
        self.assertEqual(fixture._execute("status", dataset)["total"], 0)
        self.assertTrue(unrelated.exists())

    def test_fixture_period_moves_to_the_next_free_week_on_hash_collision(self):
        fixture = self.env["csrs.e2e.fixture"]
        first_start, first_end = fixture._fixture_period("e2e-23")
        self.env["csrs.agenda.draft"].sudo().create(
            {
                "period_start": first_start,
                "period_end": first_end,
                "major_events": "Période déjà attribuée.",
                "updated_by_id": self.env.user.id,
            }
        )

        second_start, second_end = fixture._fixture_period("e2e-24")

        self.assertNotEqual((second_start, second_end), (first_start, first_end))
        self.assertEqual(second_start, first_start + timedelta(days=7))

    def test_manual_fixture_keeps_tracking_technical_and_display_values_readable(self):
        fixture = self.env["csrs.e2e.fixture"]
        dataset = "e2e-manual"

        fixture._execute("seed", dataset, password="FixturePassword-2026!")

        agent = self.env.ref("csrs_reporting_e2e.e2e_manual__user_agent")
        fund = self.env.ref("csrs_reporting_e2e.e2e_manual__process_fund")
        purchase = self.env.ref("csrs_reporting_e2e.e2e_manual__process_purchase")
        purchase_request = self.env.ref(
            "csrs_reporting_e2e.e2e_manual__purchase_request"
        )
        vendor = self.env.ref("csrs_reporting_e2e.e2e_manual__purchase_vendor")
        self.assertEqual(agent.name, "Agent demandeur")
        self.assertEqual(agent.login, "agent.demandeur@demo.invalid")
        self.assertEqual(agent.csrs_alias, "agent.demandeur")
        self.assertNotIn("E2E", agent.name)
        self.assertEqual(fund.subject, "Frais de déplacement terrain")
        self.assertEqual(fund.currency_id.name, "XOF")
        self.assertEqual(fund.amount, 250_000)
        self.assertEqual(purchase.amount, 300_000)
        quotation = self.env["csrs.purchase.quotation"].create(
            {
                "purchase_request_id": purchase_request.id,
                "vendor_id": vendor.id,
                "reference": "COT-2026-014",
                "quotation_date": "2026-08-20",
                "amount": 290_000,
            }
        )
        order = self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "csrs_process_case_id": purchase.id,
            }
        )
        purchase_request.write(
            {
                "selected_quotation_id": quotation.id,
                "purchase_order_id": order.id,
            }
        )

        fixture._execute("clean", dataset)

        self.assertFalse(quotation.exists())
        self.assertFalse(order.exists())
        self.assertEqual(fixture._execute("status", dataset)["total"], 0)
