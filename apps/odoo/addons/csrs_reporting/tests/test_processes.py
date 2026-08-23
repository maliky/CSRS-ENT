from base64 import b64encode
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged

from ..models.processes import (
    TRANSITIONS,
    bsf_payment_method,
    validate_bsf_payment_date,
)


@tagged("post_install", "-at_install")
class CsrsProcessTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env["hr.department"].create(
            {"name": "Direction de recette", "csrs_code": "PROCESS-TEST"}
        )
        agent_group = cls.env.ref("csrs_reporting.group_csrs_agent")

        def user(login, group_xmlid=None):
            groups = [Command.link(agent_group.id)]
            if group_xmlid:
                groups.append(Command.link(cls.env.ref(group_xmlid).id))
            current = cls.env["res.users"].with_context(
                no_reset_password=True
            ).create(
                {
                    "name": login,
                    "login": f"{login}@example.test",
                    "email": f"{login}@example.test",
                    "group_ids": groups,
                }
            )
            return current

        cls.requester = user("process-requester")
        cls.outsider = user("process-outsider")
        cls.manager = user(
            "process-manager", "csrs_reporting.group_csrs_primary_manager"
        )
        cls.hr = user("process-hr", "csrs_reporting.group_csrs_hr")
        cls.secretariat = user(
            "process-secretariat", "csrs_reporting.group_csrs_secretariat"
        )
        cls.dg = user("process-dg", "csrs_reporting.group_csrs_dg")
        cls.finance = user("process-finance", "csrs_reporting.group_csrs_finance")
        cls.procurement = user(
            "process-procurement", "csrs_reporting.group_csrs_procurement"
        )
        cls.compliance = user(
            "process-compliance", "csrs_reporting.group_csrs_compliance"
        )
        cls.data_manager = user(
            "process-data", "csrs_reporting.group_csrs_data_manager"
        )
        cls.fleet = user("process-fleet", "csrs_reporting.group_csrs_fleet")
        cls.it = user("process-it", "csrs_reporting.group_csrs_it")
        cls.i2a = user("process-i2a")

        manager_employee = cls.env["hr.employee"].create(
            {
                "name": cls.manager.name,
                "user_id": cls.manager.id,
                "department_id": cls.department.id,
            }
        )
        for current in (
            cls.requester,
            cls.outsider,
            cls.hr,
            cls.secretariat,
            cls.dg,
            cls.finance,
            cls.procurement,
            cls.compliance,
            cls.data_manager,
            cls.fleet,
            cls.it,
            cls.i2a,
        ):
            cls.env["hr.employee"].create(
                {
                    "name": current.name,
                    "user_id": current.id,
                    "department_id": cls.department.id,
                    "parent_id": manager_employee.id,
                }
            )
        cls.env["csrs.role.grant"].sudo().create(
            {
                "user_id": cls.i2a.id,
                "department_id": cls.department.id,
                "role_code": "I2A",
                "scope": "tree",
                "valid_from": fields.Datetime.now() - timedelta(days=1),
            }
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Projet processus", "csrs_research_project": True}
        )
        cls.budget_line = cls.env["csrs.project.budget.line"].create(
            {
                "project_id": cls.project.id,
                "code": "PROCESS-BUDGET",
                "name": "Fonctionnement",
                "planned_amount": 1_000_000,
            }
        )
        cls.beneficiary = cls.env["res.partner"].create(
            {"name": "Bénéficiaire processus"}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Fournisseur processus", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Service processus", "type": "service", "purchase_ok": True}
        )
        cls.proof = cls.env["ir.attachment"].create(
            {
                "name": "preuve.pdf",
                "mimetype": "application/pdf",
                "datas": b64encode(b"preuve"),
            }
        )

    def _case(self, process_type):
        return self.env["csrs.process.case"].with_user(self.requester).create(
            {
                "process_type": process_type,
                "origin_department_id": self.department.id,
                "subject": f"Dossier {process_type}",
                "description": "Scénario de recette comportementale.",
            }
        )

    def _business_day(self):
        current = fields.Date.context_today(self.env.user)
        while current.weekday() not in {1, 3, 4}:
            current -= timedelta(days=1)
        return current

    def _advance_to(self, case, target):
        transitions = TRANSITIONS[case.process_type]
        while case.state != target:
            current = [
                (action, to_state)
                for (from_state, action), to_state in transitions.items()
                if from_state == case.state
            ][0]
            action, _to_state = current
            confirmation = ""
            if case.state == "dg_review" and action == "approve":
                confirmation = f"VALIDÉ LE {fields.Date.context_today(case):%d/%m/%Y}"
            case.with_user(self._actor_for_state(case.state)).action_transition(
                action,
                case.revision,
                confirmation=confirmation,
            )

    def _actor_for_state(self, state):
        return {
            "draft": self.requester,
            "finance_review": self.finance,
            "requester_visa": self.requester,
            "finance_head": self.finance,
            "daf_review": self.finance,
            "project_accounting": self.finance,
            "dg_review": self.dg,
            "payment_preparation": self.finance,
            "procurement": self.procurement,
            "ordered": self.procurement,
            "delivered": self.procurement,
            "invoiced": self.finance,
            "supervisor_review": self.manager,
            "hr_review": self.hr,
            "secretariat": self.secretariat,
            "assistance": self.secretariat,
            "accounting": self.finance,
            "fleet": self.fleet,
            "notified": self.requester,
            "research_assistance": self.secretariat,
            "i2a_review": self.i2a,
            "mae_followup": self.secretariat,
            "systems_validation": self.it,
            "quality_review": self.compliance,
            "active_processing": self.data_manager,
            "audit_review": self.compliance,
            "archived": self.data_manager,
        }[state]

    def test_each_documented_process_reaches_its_terminal_state_by_role(self):
        for process_type, transitions in TRANSITIONS.items():
            if process_type in {"fund", "purchase"}:
                continue
            case = self._case(process_type)
            for (from_state, action), to_state in transitions.items():
                self.assertEqual(case.state, from_state, process_type)
                actor = self._actor_for_state(from_state)
                confirmation = ""
                if from_state == "dg_review" and action == "approve":
                    confirmation = (
                        f"VALIDÉ LE {fields.Date.context_today(case):%d/%m/%Y}"
                    )
                case.with_user(actor).action_transition(
                    action,
                    expected_revision=case.revision,
                    confirmation=confirmation,
                )
                self.assertEqual(case.state, to_state, process_type)
            self.assertEqual(case.state, "completed", process_type)
            self.assertEqual(len(case.event_ids), len(transitions), process_type)

    def test_bsf_enforces_threshold_calendar_and_single_budget_reservation(self):
        self.assertEqual(bsf_payment_method(200_000), "cash")
        self.assertEqual(bsf_payment_method(200_001), "check")
        with self.assertRaises(ValidationError):
            validate_bsf_payment_date(date(2026, 8, 19), date(2026, 8, 20))

        case = self.env["csrs.process.case"].with_user(self.requester).create(
            {
                "process_type": "fund",
                "origin_department_id": self.department.id,
                "project_id": self.project.id,
                "subject": "BSF de recette",
                "description": "Paiement documenté.",
                "amount": 200_000,
            }
        )
        fund = self.env["csrs.fund.request"].create(
            {
                "case_id": case.id,
                "budget_line_id": self.budget_line.id,
                "beneficiary_id": self.beneficiary.id,
                "initiator_id": self.requester.id,
                "purpose": "Frais de terrain",
            }
        )
        self.assertEqual(fund.payment_method, "cash")
        self._advance_to(case, "dg_review")
        revision = case.revision
        confirmation = f"VALIDÉ LE {fields.Date.context_today(case):%d/%m/%Y}"
        case.with_user(self.dg).action_transition(
            "approve", revision, confirmation=confirmation
        )
        self.assertEqual(self.budget_line.committed_amount, 200_000)
        with self.assertRaises(UserError):
            case.with_user(self.dg).action_transition(
                "approve", revision, confirmation=confirmation
            )
        self.assertEqual(self.budget_line.committed_amount, 200_000)
        case.with_user(self.finance).action_transition(
            "pay",
            case.revision,
            stage_data={"payment_date": self._business_day().isoformat()},
        )
        self.assertEqual(case.state, "completed")
        self.assertEqual(fund.payment_date, self._business_day())

    def test_purchase_requires_documented_procurement_and_evidence(self):
        case = self.env["csrs.process.case"].with_user(self.requester).create(
            {
                "process_type": "purchase",
                "origin_department_id": self.department.id,
                "project_id": self.project.id,
                "subject": "DA de recette",
                "description": "Achat documenté.",
                "amount": 300_000,
            }
        )
        purchase = self.env["csrs.purchase.request"].create(
            {
                "case_id": case.id,
                "budget_line_id": self.budget_line.id,
                "quantity": 2,
                "estimated_amount": 300_000,
            }
        )
        self._advance_to(case, "procurement")
        with self.assertRaises(ValidationError):
            case.with_user(self.procurement).action_transition("order", case.revision)
        quote = self.env["csrs.purchase.quotation"].create(
            {
                "purchase_request_id": purchase.id,
                "vendor_id": self.vendor.id,
                "reference": "DEVIS-001",
                "quotation_date": fields.Date.context_today(case),
                "amount": 280_000,
                "attachment_ids": [Command.link(self.proof.id)],
            }
        )
        purchase.action_save_procurement(
            {
                "selected_quotation_id": quote.id,
                "product_id": self.product.id,
                "quantity": 2,
                "negotiated_amount": 280_000,
            }
        )
        case.with_user(self.procurement).action_transition("order", case.revision)
        self.assertEqual(purchase.purchase_order_id.state, "purchase")
        self.assertEqual(purchase.purchase_order_id.csrs_process_case_id, case)
        evidence = {
            "reference": "JUSTIFICATIF-001",
            "date": fields.Date.context_today(case).isoformat(),
            "attachment_id": self.proof.id,
        }
        case.with_user(self.procurement).action_transition(
            "receive", case.revision, stage_data=evidence
        )
        case.with_user(self.procurement).action_transition(
            "invoice", case.revision, stage_data={**evidence, "amount": 280_000}
        )
        with self.assertRaises(AccessError):
            case.with_user(self.outsider).action_transition(
                "pay", case.revision, stage_data={**evidence, "amount": 280_000}
            )
        case.with_user(self.finance).action_transition(
            "pay", case.revision, stage_data={**evidence, "amount": 280_000}
        )
        self.assertEqual(case.state, "completed")
        self.assertEqual(set(purchase.evidence_ids.mapped("kind")), {"delivery", "invoice", "payment"})

    def test_procurement_can_load_purchase_options_without_project_access(self):
        options = self.env["csrs.api"].with_user(self.procurement).api_process_options()

        self.assertIn(self.vendor.id, [item["id"] for item in options["vendors"]])
        self.assertIn(self.product.id, [item["id"] for item in options["products"]])
        self.assertNotIn(self.project.id, [item["id"] for item in options["projects"]])

    def test_wrong_role_and_stale_revision_cannot_advance_a_process(self):
        case = self._case("absence")
        case.with_user(self.requester).action_transition("submit", 1)

        with self.assertRaises(AccessError):
            case.with_user(self.outsider).action_transition("approve", 2)
        with self.assertRaises(UserError):
            case.with_user(self.manager).action_transition("approve", 1)

        self.assertEqual(case.state, "supervisor_review")
        self.assertEqual(case.revision, 2)

    def test_correction_requires_a_reason_and_keeps_an_immutable_audit(self):
        case = self._case("purchase")
        case.with_user(self.requester).action_transition("submit", 1)

        with self.assertRaises(ValidationError):
            case.with_user(self.finance).action_transition("correct", 2)
        case.with_user(self.finance).action_transition(
            "correct", 2, note="Préciser la quantité."
        )
        self.assertEqual(case.state, "correction")
        self.assertEqual(case.correction_reason, "Préciser la quantité.")

        case.with_user(self.requester).action_transition("resubmit", 3)
        event = case.event_ids[-1]
        self.assertEqual(case.state, "daf_review")
        with self.assertRaises(UserError):
            event.write({"note": "Altération"})
        with self.assertRaises(UserError):
            event.unlink()
