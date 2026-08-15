from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class CsrsResearchProjectTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent_group = cls.env.ref("csrs_reporting.group_csrs_agent")

        def user(login, *groups):
            return (
                cls.env["res.users"]
                .with_context(no_reset_password=True)
                .create(
                    {
                        "name": login,
                        "login": f"{login}@example.test",
                        "email": f"{login}@example.test",
                        "group_ids": [
                            Command.link(agent_group.id),
                            *(Command.link(group.id) for group in groups),
                        ],
                    }
                )
            )

        cls.agent = user("project-agent")
        cls.outsider = user("project-outsider")
        cls.dg = user("project-dg", cls.env.ref("csrs_reporting.group_csrs_dg"))
        cls.finance = user(
            "project-finance", cls.env.ref("csrs_reporting.group_csrs_finance")
        )
        cls.it = user("project-it", cls.env.ref("csrs_reporting.group_csrs_it"))
        cls.department = cls.env["hr.department"].create(
            {"name": "Recherche", "csrs_code": "RESEARCH-TEST"}
        )
        for current in (cls.agent, cls.outsider, cls.dg, cls.finance, cls.it):
            cls.env["hr.employee"].create(
                {
                    "name": current.name,
                    "user_id": current.id,
                    "department_id": cls.department.id,
                }
            )

    def _project(self):
        return (
            self.env["project.project"]
            .with_user(self.agent)
            .create(
                {
                    "name": "Étude paludisme",
                    "csrs_research_project": True,
                    "csrs_objectives": "Mesurer l'incidence.",
                    "date_start": "2026-09-01",
                    "date": "2027-08-31",
                }
            )
        )

    def test_research_proposal_creates_nine_sections_and_dg_approves(self):
        project = self._project()

        self.assertEqual(project.csrs_state, "proposal")
        self.assertEqual(len(project.csrs_section_ids), 9)
        self.assertEqual(project.csrs_proposer_id, self.agent)
        with self.assertRaises(AccessError):
            project.with_user(self.it).action_csrs_approve(self.agent.id, 1)

        project.with_user(self.dg).action_csrs_approve(self.agent.id, 1)

        self.assertEqual(project.csrs_state, "active")
        self.assertEqual(project.csrs_lead_id, self.agent)
        self.assertTrue(project.account_id)

    def test_section_cycle_is_revision_checked_and_signed(self):
        project = self._project()
        project.with_user(self.dg).action_csrs_approve(self.agent.id, 1)
        section = project.csrs_section_ids.filtered(lambda row: row.code == "results")

        section.with_user(self.agent).action_submit(1)
        with self.assertRaises(AccessError):
            section.with_user(self.outsider).action_verify(2)
        section.with_user(self.dg).action_verify(2)
        with self.assertRaises(ValidationError):
            section.with_user(self.dg).action_validate("VALIDÉ", 3)

        phrase = f"VALIDÉ LE {fields.Date.context_today(section):%d/%m/%Y}"
        approval_id = section.with_user(self.dg).action_validate(phrase, 3)

        approval = self.env["csrs.project.approval"].sudo().browse(approval_id)
        self.assertEqual(section.state, "validated")
        self.assertEqual(approval.signer_id, self.dg)
        self.assertEqual(len(approval.snapshot_sha256), 64)
        with self.assertRaises(UserError):
            approval.unlink()

    def test_fund_request_reserves_budget_after_the_documented_approvals(self):
        project = self._project()
        project.with_user(self.dg).action_csrs_approve(self.agent.id, 1)
        budget = (
            self.env["csrs.project.budget.line"]
            .sudo()
            .create(
                {
                    "project_id": project.id,
                    "code": "FIELD",
                    "name": "Terrain",
                    "planned_amount": 500_000,
                }
            )
        )
        case = (
            self.env["csrs.process.case"]
            .with_user(self.agent)
            .create(
                {
                    "process_type": "fund",
                    "requester_id": self.agent.id,
                    "origin_department_id": self.department.id,
                    "project_id": project.id,
                    "subject": "Mission terrain",
                    "description": "Frais de collecte",
                    "amount": 150_000,
                }
            )
        )
        self.env["csrs.fund.request"].sudo().create(
            {
                "case_id": case.id,
                "budget_line_id": budget.id,
                "beneficiary_id": self.agent.partner_id.id,
                "initiator_id": self.agent.id,
                "purpose": "Collecte de données",
            }
        )

        case.with_user(self.agent).action_transition("submit", 1)
        with self.assertRaises(AccessError):
            case.with_user(self.it).action_transition("approve", 2)
        case.with_user(self.finance).action_transition("approve", 2)
        case.with_user(self.agent).action_transition("approve", 3)
        case.with_user(self.finance).action_transition("approve", 4)
        case.with_user(self.finance).action_transition("approve", 5)
        case.with_user(self.finance).action_transition("approve", 6)
        phrase = f"VALIDÉ LE {fields.Date.context_today(case):%d/%m/%Y}"
        case.with_user(self.dg).action_transition("approve", 7, confirmation=phrase)

        self.assertEqual(case.state, "payment_preparation")
        self.assertEqual(budget.committed_amount, 150_000)
        with self.assertRaises(ValidationError):
            budget.action_reserve(400_000)

    def test_project_item_save_checks_permission_fields_and_revision(self):
        project = self._project()
        api = self.env["csrs.api"].with_user(self.agent)

        detail = api.api_research_project_item_save(
            project.id,
            "results",
            {
                "revision": 1,
                "values": {
                    "name": "Résultat 1",
                    "indicator": "Incidence",
                    "target_value": "10 %",
                },
            },
        )

        self.assertEqual(detail["revision"], 2)
        self.assertEqual(detail["results"][0]["name"], "Résultat 1")
        with self.assertRaises(UserError):
            api.api_research_project_item_save(
                project.id,
                "results",
                {
                    "revision": 1,
                    "values": {
                        "name": "Résultat concurrent",
                        "indicator": "Incidence",
                        "target_value": "5 %",
                    },
                },
            )

        with self.assertRaises(ValidationError):
            api.api_research_project_item_save(
                project.id,
                "results",
                {"revision": 2, "values": {"create_uid": self.it.id}},
            )
        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.outsider).api_research_project_item_save(
                project.id,
                "results",
                {
                    "revision": 2,
                    "values": {
                        "name": "Intrusion",
                        "indicator": "Aucun",
                        "target_value": "Aucun",
                    },
                },
            )

    def test_project_history_blocks_account_deletion(self):
        self._project()
        self.agent.active = False

        can_delete = self.env["csrs.api"].sudo()._user_can_be_deleted(self.agent)

        self.assertFalse(can_delete)
