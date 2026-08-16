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
        cls.donor = cls.env["res.partner"].sudo().create(
            {"name": "Bailleur de test", "company_type": "company"}
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
                    "csrs_donor_id": self.donor.id,
                    "csrs_team_user_ids": [Command.link(self.agent.id)],
                    "date_start": "2026-09-01",
                    "date": "2027-08-31",
                }
            )
        )

    def _add_action_plan(self, project):
        return self.env["csrs.api"].with_user(self.agent).api_research_project_item_save(
            project.id,
            "action_plan",
            {
                "revision": project.csrs_revision,
                "values": {
                    "name": "Collecte terrain",
                    "description": "Préparer les enquêtes.",
                    "user_ids": [self.agent.id],
                    "csrs_start_date": "2026-09-01",
                    "date_deadline": "2026-09-02",
                    "csrs_estimated_work_days": 1,
                },
            },
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
        self._add_action_plan(project)
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
        self._add_action_plan(project)
        result_revision = project.csrs_revision

        detail = api.api_research_project_item_save(
            project.id,
            "results",
            {
                "revision": result_revision,
                "values": {
                    "name": "Résultat 1",
                    "indicator": "Incidence",
                    "target_value": "10 %",
                },
            },
        )

        self.assertEqual(detail["revision"], result_revision + 1)
        self.assertEqual(detail["results"][0]["name"], "Résultat 1")
        with self.assertRaises(UserError):
            api.api_research_project_item_save(
                project.id,
                "results",
                {
                    "revision": result_revision,
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
                {
                    "revision": detail["revision"],
                    "values": {"create_uid": self.it.id},
                },
            )
        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.outsider).api_research_project_item_save(
                project.id,
                "results",
                {
                    "revision": detail["revision"],
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

    def test_project_selects_existing_company_partners_without_creating_them(self):
        donor = self.env["res.partner"].sudo().create(
            {"name": "Fondation santé", "company_type": "company"}
        )
        partner = self.env["res.partner"].sudo().create(
            {"name": "Université partenaire", "company_type": "company"}
        )
        before = self.env["res.partner"].sudo().search_count([])

        detail = self.env["csrs.api"].with_user(self.agent).api_research_project_create(
            {
                "name": "Projet partenaires existants",
                "objectives": "Vérifier les liens Odoo.",
                "donor_id": donor.id,
                "partner_ids": [partner.id],
                "team_user_ids": [self.agent.id],
            }
        )

        self.assertEqual(detail["donor"]["id"], donor.id)
        self.assertEqual(detail["partners"][0]["id"], partner.id)
        self.assertEqual(self.env["res.partner"].sudo().search_count([]), before)
        with self.assertRaises(ValidationError):
            self.env["csrs.api"].with_user(self.agent).api_research_project_create(
                {
                    "name": "Projet partenaire invalide",
                    "objectives": "Refuser un contact individuel.",
                    "donor_id": self.agent.partner_id.id,
                }
            )

        donor.active = False
        updated = self.env["csrs.api"].with_user(self.agent).api_research_project_update(
            detail["id"],
            {
                "name": detail["name"],
                "objectives": detail["objectives"],
                "revision": detail["revision"],
                "donor_id": donor.id,
                "partner_ids": [partner.id],
            },
        )
        self.assertEqual(updated["donor"]["id"], donor.id)

    def test_only_it_can_manage_company_partners(self):
        with self.assertRaises(AccessError):
            self.env["csrs.api"].with_user(self.agent).api_partner_create(
                {"name": "Organisation interdite"}
            )

        facade = self.env["csrs.api"].with_user(self.it)
        partner = facade.api_partner_create(
            {"name": "Organisation de recherche", "email": "contact@example.test"}
        )
        self.assertTrue(partner["active"])
        with self.assertRaises(ValidationError):
            facade.api_partner_create({"name": "organisation de recherche"})

        archived = facade.api_partner_update(
            partner["id"],
            {
                "name": partner["name"],
                "email": partner["email"],
                "phone": partner["phone"],
                "active": False,
                "state_token": partner["state_token"],
            },
        )
        self.assertFalse(archived["active"])

    def test_plan_and_finance_require_drafts_and_lock_after_submission(self):
        project = self._project()
        project.with_user(self.dg).action_csrs_approve(self.agent.id, 1)
        action_plan = project.csrs_section_ids.filtered(
            lambda item: item.code == "action_plan"
        )
        finance = project.csrs_section_ids.filtered(lambda item: item.code == "finance")

        with self.assertRaises(ValidationError):
            action_plan.with_user(self.agent).action_submit(1)
        with self.assertRaises(UserError):
            finance.with_user(self.agent).action_submit(1)

        api = self.env["csrs.api"].with_user(self.agent)
        self._add_action_plan(project)
        action_plan.with_user(self.agent).action_submit(1)
        api.api_research_project_item_save(
            project.id,
            "finance",
            {
                "revision": project.csrs_revision,
                "values": {
                    "code": "FIELD",
                    "name": "Terrain",
                    "planned_amount": 500000,
                },
            },
        )
        finance.with_user(self.agent).action_submit(1)

        with self.assertRaises(UserError):
            api.api_research_project_item_save(
                project.id,
                "finance",
                {
                    "revision": project.csrs_revision,
                    "values": {
                        "code": "TRAVEL",
                        "name": "Déplacements",
                        "planned_amount": 100000,
                    },
                },
            )
        finance.with_user(self.dg).action_request_correction("Préciser le budget.", 2)
        api.api_research_project_item_save(
            project.id,
            "finance",
            {
                "revision": project.csrs_revision,
                "values": {
                    "code": "TRAVEL",
                    "name": "Déplacements",
                    "planned_amount": 100000,
                },
            },
        )

    def test_numbered_journey_unlocks_after_required_drafts_are_complete(self):
        donor = self.env["res.partner"].sudo().create(
            {"name": "Bailleur parcours", "company_type": "company"}
        )
        project = self._project()
        api = self.env["csrs.api"].with_user(self.agent)
        api.api_research_project_update(
            project.id,
            {
                "name": project.name,
                "objectives": project.csrs_objectives,
                "revision": project.csrs_revision,
                "donor_id": donor.id,
                "team_user_ids": [self.agent.id],
                "date_start": "2026-09-01",
                "date_end": "2027-08-31",
            },
        )

        detail = api.api_research_project(project.id)
        sections = {item["code"]: item for item in detail["sections"]}
        self.assertTrue(sections["project"]["required"])
        self.assertTrue(sections["action_plan"]["unlocked"])
        self.assertFalse(sections["results"]["unlocked"])
        self.assertFalse(detail["recap_unlocked"])
        with self.assertRaises(UserError):
            api.api_research_project_item_save(
                project.id,
                "results",
                {
                    "revision": project.csrs_revision,
                    "values": {
                        "name": "Résultat prématuré",
                        "indicator": "Test",
                        "target_value": "1",
                    },
                },
            )

        api.api_research_project_item_save(
            project.id,
            "action_plan",
            {
                "revision": project.csrs_revision,
                "values": {
                    "name": "Activité initiale",
                    "description": "Préparer le terrain.",
                    "user_ids": [self.agent.id],
                    "csrs_start_date": "2026-09-01",
                    "date_deadline": "2026-09-02",
                    "csrs_estimated_work_days": 1,
                },
            },
        )
        detail = api.api_research_project(project.id)
        sections = {item["code"]: item for item in detail["sections"]}
        self.assertTrue(sections["results"]["unlocked"])
        self.assertTrue(sections["results"]["ready"])
        self.assertTrue(sections["finance"]["unlocked"])
        self.assertFalse(sections["closure"]["unlocked"])

        api.api_research_project_item_save(
            project.id,
            "finance",
            {
                "revision": project.csrs_revision,
                "values": {
                    "code": "FIELD",
                    "name": "Terrain",
                    "planned_amount": 500000,
                },
            },
        )
        detail = api.api_research_project(project.id)
        sections = {item["code"]: item for item in detail["sections"]}
        self.assertTrue(sections["closure"]["unlocked"])
        self.assertFalse(sections["closure"]["ready"])

        api.api_research_project_item_save(
            project.id,
            "closure",
            {
                "revision": project.csrs_revision,
                "values": {
                    "assessment": "Objectifs atteints.",
                    "equipment_disposition": "Matériel conservé.",
                    "data_disposition": "Données archivées.",
                    "final_balance": 0,
                    "outlook": "Publication.",
                    "residual_liabilities": "Aucune.",
                    "sustainability": "Suivi annuel.",
                },
            },
        )
        self.assertTrue(api.api_research_project(project.id)["recap_unlocked"])

    def test_recursive_supervisor_edits_requests_correction_and_archives(self):
        agent_group = self.env.ref("csrs_reporting.group_csrs_agent")

        def create_user(login):
            current = self.env["res.users"].with_context(no_reset_password=True).create(
                {
                    "name": login,
                    "login": f"{login}@example.test",
                    "email": f"{login}@example.test",
                    "group_ids": [Command.link(agent_group.id)],
                }
            )
            self.env["hr.employee"].create(
                {
                    "name": current.name,
                    "user_id": current.id,
                    "department_id": self.department.id,
                }
            )
            return current

        manager = create_user("project-manager")
        director = create_user("project-director")
        self.env["csrs.reporting.line"].sudo().create(
            {
                "employee_id": self.agent.id,
                "supervisor_id": manager.id,
                "department_id": self.department.id,
                "start_date": "2026-01-01",
                "is_primary": True,
            }
        )
        self.env["csrs.reporting.line"].sudo().create(
            {
                "employee_id": manager.id,
                "supervisor_id": director.id,
                "department_id": self.department.id,
                "start_date": "2026-01-01",
                "is_primary": True,
            }
        )
        project = self._project()
        project._csrs_refresh_supervisor_access()

        self.assertIn(manager, project.csrs_supervisor_user_ids)
        self.assertIn(director, project.csrs_supervisor_user_ids)
        detail = self.env["csrs.api"].with_user(director).api_research_project(project.id)
        self.assertTrue(detail["capabilities"]["supervise"])
        self.assertTrue(detail["capabilities"]["edit"])
        with self.assertRaises(AccessError):
            project.with_user(self.outsider).action_csrs_archive("Intrusion", 1)

        project.with_user(director).action_csrs_archive(
            "Projet remplacé par une convention actualisée.", 1
        )

        self.assertFalse(project.active)
        audit = self.env["csrs.audit.event"].sudo().search(
            [("event_type", "=", "project_archive")], limit=1
        )
        self.assertEqual(audit.actor_id, director)
        self.assertEqual(audit.snapshot["reference"], project.csrs_reference)
        with self.assertRaises(UserError):
            audit.unlink()
