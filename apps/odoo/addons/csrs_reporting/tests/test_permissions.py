from datetime import timedelta

from passlib.hash import django_pbkdf2_sha256

from odoo import fields
from odoo.fields import Command
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged("post_install", "-at_install")
class CsrsPermissionTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent_group = cls.env.ref("csrs_reporting.group_csrs_agent")
        primary_group = cls.env.ref("csrs_reporting.group_csrs_primary_manager")
        secondary_group = cls.env.ref("csrs_reporting.group_csrs_secondary_manager")
        secretariat_group = cls.env.ref("csrs_reporting.group_csrs_secretariat")
        it_group = cls.env.ref("csrs_reporting.group_csrs_it")

        def user(login, group):
            return cls.env["res.users"].with_context(no_reset_password=True).create(
                {
                    "name": login,
                    "login": login,
                    "email": f"{login}@example.test",
                    "password": "ValidPassword123!",
                    "group_ids": [
                        Command.link(agent_group.id),
                        Command.link(group.id),
                    ],
                }
            )

        cls.manager = user("manager", primary_group)
        cls.secondary = user("secondary", secondary_group)
        cls.agent = user("agent", agent_group)
        cls.outsider = user("outsider", agent_group)
        cls.secretariat = user("secretariat", secretariat_group)
        cls.it = user("it", it_group)
        cls.manager_employee = cls.env["hr.employee"].create(
            {"name": "manager", "user_id": cls.manager.id}
        )
        cls.agent_employee = cls.env["hr.employee"].create(
            {
                "name": "agent",
                "user_id": cls.agent.id,
                "parent_id": cls.manager_employee.id,
            }
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Projet CSRS", "privacy_visibility": "employees"}
        )
        cls.task = cls.env["project.task"].create(
            {
                "name": "Rapport hebdomadaire",
                "project_id": cls.project.id,
                "csrs_managed": True,
                "csrs_manager_id": cls.manager.id,
                "csrs_secondary_manager_user_ids": [Command.set(cls.secondary.ids)],
                "user_ids": [Command.set(cls.agent.ids)],
            }
        )

    def test_new_task_uses_the_csrs_ent_sequence_prefix(self):
        self.assertTrue(self.task.csrs_code.startswith("CSRS-ENT-T-"))

    def test_secondary_manager_can_comment_but_cannot_edit_progress(self):
        task = self.task.with_user(self.secondary)

        message = task.action_csrs_comment("Observation secondaire")

        self.assertTrue(message)
        with self.assertRaises(UserError):
            task.action_csrs_record_progress(25, expected_revision=1)

    def test_unrelated_agent_cannot_read_a_csrs_task(self):
        visible = (
            self.env["project.task"]
            .with_user(self.outsider)
            .search_count([("id", "=", self.task.id)])
        )

        self.assertEqual(visible, 0)

    def test_dg_session_can_scope_the_team_without_hr_private_access(self):
        dg_group = self.env.ref("csrs_reporting.group_csrs_dg")
        self.manager.sudo().write({"group_ids": [Command.link(dg_group.id)]})

        session = self.env["csrs.api"].with_user(self.manager).api_session()

        self.assertTrue(session["capabilities"]["view_team"])
        self.assertFalse(session["capabilities"]["manage_users"])

    def test_it_session_exposes_task_user_and_organization_management(self):
        session = self.env["csrs.api"].with_user(self.it).api_session()

        self.assertTrue(session["capabilities"]["delete_tasks"])
        self.assertTrue(session["capabilities"]["manage_users"])
        self.assertTrue(session["capabilities"]["manage_organization"])

    def test_it_cannot_reset_the_protected_odoo_administrator(self):
        administrator = self.env.ref("base.user_admin")
        token = self.env["csrs.api"].with_user(self.it)._user_state_token(
            administrator
        )

        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.it).api_user_temporary_password(
                administrator.id, token
            )

    def test_delegations_respect_role_dates_without_linking_global_groups(self):
        root = self.env["hr.department"].create(
            {"name": "CSRS", "csrs_code": "ROOT"}
        )
        child = self.env["hr.department"].create(
            {"name": "Recherche", "csrs_code": "RECH", "parent_id": root.id}
        )
        self.agent_employee.department_id = child
        now = fields.Datetime.now()
        facade = self.env["csrs.api"].with_user(self.it)
        common = {
            "user_id": self.outsider.id,
            "valid_from": fields.Datetime.to_string(now - timedelta(days=1)),
            "valid_until": False,
            "reason": "Délégation de test",
        }

        facade.api_role_grant_create(
            {
                **common,
                "department_id": root.id,
                "role_code": "MISSION_SIGNER",
                "scope": "tree",
            }
        )
        facade.api_role_grant_create(
            {
                **common,
                "department_id": child.id,
                "role_code": "AGENDA_SECRETARIAT",
                "scope": "unit",
            }
        )
        facade.api_role_grant_create(
            {
                **common,
                "department_id": root.id,
                "role_code": "UNIT_MANAGER",
                "scope": "tree",
                "valid_from": fields.Datetime.to_string(now + timedelta(days=1)),
            }
        )

        delegated = self.env["csrs.api"].with_user(self.outsider)
        session = delegated.api_session()
        self.assertTrue(session["capabilities"]["prepare_weekly_agenda"])
        self.assertNotIn(self.agent, delegated._managed_users())
        self.assertNotIn(
            self.env.ref("csrs_reporting.group_csrs_dg"), self.outsider.group_ids
        )
        self.assertNotIn(
            self.env.ref("csrs_reporting.group_csrs_secretariat"),
            self.outsider.group_ids,
        )

        today = fields.Date.context_today(self)
        self.assertEqual(
            delegated.api_agenda_preview(
                today.isoformat(),
                (today + timedelta(days=6)).isoformat(),
                "programs",
            )["snapshot"]["agenda_direction"],
            "programs",
        )
        self.assertEqual(
            delegated.api_agenda_preview(
                today.isoformat(),
                (today + timedelta(days=6)).isoformat(),
                "administration",
            )["snapshot"]["agenda_direction"],
            "administration",
        )
        self.assertEqual(
            delegated.api_agenda_preview(
                today.isoformat(),
                (today + timedelta(days=6)).isoformat(),
                "research",
            )["snapshot"]["agenda_direction"],
            "research",
        )

    def test_it_bulk_delete_is_revision_checked_and_audited(self):
        task_id = self.task.id

        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.manager).api_task_bulk_delete(
                [{"id": task_id, "revision": 1}], "Nettoyage de test"
            )
        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.it).api_task_bulk_delete(
                [{"id": task_id, "revision": 99}], "Nettoyage de test"
            )
        self.assertTrue(self.task.exists())

        result = self.env["csrs.api"].with_user(self.it).api_task_bulk_delete(
            [{"id": task_id, "revision": 1}], "Nettoyage de test"
        )

        self.assertFalse(self.task.exists())
        audit = self.env["csrs.audit.event"].sudo().browse(result["audit_id"])
        self.assertEqual(audit.event_type, "task_bulk_delete")
        self.assertEqual(audit.actor_id, self.it)
        self.assertEqual(audit.snapshot[0]["id"], task_id)

    def test_it_task_management_filters_without_bypassing_the_facade(self):
        page = self.env["csrs.api"].with_user(self.it).api_task_management(
            query="Rapport", status="planned", page=1, page_size=20
        )

        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["id"], self.task.id)
        with self.assertRaises(UserError):
            self.env["csrs.api"].with_user(self.manager).api_task_management()

    def test_it_unit_editor_rejects_a_cycle_and_preserves_revision(self):
        parent = self.env["hr.department"].create(
            {"name": "Parent", "csrs_code": "PARENT"}
        )
        child = self.env["hr.department"].create(
            {"name": "Enfant", "csrs_code": "CHILD", "parent_id": parent.id}
        )
        token = self.env["csrs.api"].with_user(self.it)._department_state_token(parent)

        with self.assertRaises(ValidationError):
            self.env["csrs.api"].with_user(self.it).api_organization_unit_update(
                parent.id,
                {
                    "code": "PARENT",
                    "short_name": "Parent",
                    "long_name": "Parent",
                    "kind": "unit",
                    "display_order": 0,
                    "parent_id": child.id,
                    "active": True,
                    "state_token": token,
                },
            )
        self.assertFalse(parent.parent_id)

    def test_reporting_lines_are_limited_to_the_people_concerned(self):
        department = self.env["hr.department"].create(
            {"name": "Gouvernance", "csrs_code": "GOUV"}
        )
        own_line = self.env["csrs.reporting.line"].sudo().create(
            {
                "employee_id": self.agent.id,
                "supervisor_id": self.manager.id,
                "department_id": department.id,
                "start_date": "2026-08-15",
                "is_primary": True,
            }
        )
        unrelated_line = self.env["csrs.reporting.line"].sudo().create(
            {
                "employee_id": self.outsider.id,
                "supervisor_id": self.secondary.id,
                "department_id": department.id,
                "start_date": "2026-08-15",
                "is_primary": True,
            }
        )

        self.assertEqual(
            self.env["csrs.reporting.line"]
            .with_user(self.agent)
            .search([("id", "in", (own_line.id, unrelated_line.id))]),
            own_line,
        )
        self.assertEqual(
            self.env["csrs.reporting.line"]
            .with_user(self.manager)
            .search([("id", "in", (own_line.id, unrelated_line.id))]),
            own_line,
        )
        self.assertEqual(
            self.env["csrs.reporting.line"]
            .with_user(self.it)
            .search_count([("id", "in", (own_line.id, unrelated_line.id))]),
            2,
        )

    def test_it_creates_a_user_in_the_odoo_organization(self):
        department = self.env["hr.department"].create(
            {
                "name": "Recherche",
                "csrs_code": "RECH",
                "csrs_short_name": "Recherche",
                "csrs_kind": "direction",
            }
        )
        self.manager_employee.department_id = department
        payload = {
            "email": "new-agent@example.invalid",
            "login_alias": "new-agent",
            "first_name": "Nouvel",
            "last_name": "Agent",
            "position": "Analyste",
            "phone": "",
            "agenda_direction": "research",
            "include_in_direction_agendas": True,
            "unit_ids": [department.id],
            "primary_unit_id": department.id,
            "primary_supervisor_id": self.manager.id,
            "organization_effective_date": "2026-08-15",
        }

        result = self.env["csrs.api"].with_user(self.it).api_user_create(payload)

        user = self.env["res.users"].sudo().browse(result["id"])
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id)]
        )
        self.assertEqual(employee.parent_id, self.manager_employee)
        self.assertEqual(employee.csrs_agenda_direction, "research")
        self.assertEqual(
            self.env["csrs.organization.membership"].sudo().search_count(
                [
                    ("user_id", "=", user.id),
                    ("department_id", "=", department.id),
                    ("is_primary", "=", True),
                    ("end_date", "=", False),
                ]
            ),
            1,
        )
        self.assertEqual(
            self.env["csrs.reporting.line"].sudo().search_count(
                [
                    ("employee_id", "=", user.id),
                    ("supervisor_id", "=", self.manager.id),
                    ("end_date", "=", False),
                ]
            ),
            1,
        )

    def test_manager_change_transfers_active_tasks_and_keeps_history(self):
        department = self.env["hr.department"].create(
            {"name": "Administration", "csrs_code": "ADM"}
        )
        self.manager_employee.department_id = department
        self.agent_employee.department_id = department
        replacement_employee = self.env["hr.employee"].create(
            {
                "name": "secondary",
                "user_id": self.secondary.id,
                "department_id": department.id,
            }
        )
        self.env["csrs.organization.membership"].sudo().create(
            {
                "user_id": self.agent.id,
                "department_id": department.id,
                "start_date": "2026-01-01",
                "is_primary": True,
            }
        )
        self.env["csrs.reporting.line"].sudo().create(
            {
                "employee_id": self.agent.id,
                "supervisor_id": self.manager.id,
                "department_id": department.id,
                "start_date": "2026-01-01",
                "is_primary": True,
            }
        )
        token = self.env["csrs.api"].with_user(self.it)._user_state_token(self.agent)
        payload = {
            "email": self.agent.email,
            "login_alias": self.agent.csrs_alias,
            "first_name": "Agent",
            "last_name": "Test",
            "position": "Agent",
            "phone": "",
            "agenda_direction": "administration",
            "include_in_direction_agendas": True,
            "unit_ids": [department.id],
            "primary_unit_id": department.id,
            "primary_supervisor_id": self.secondary.id,
            "organization_effective_date": "2026-08-15",
            "state_token": token,
        }

        self.env["csrs.api"].with_user(self.it).api_user_update(
            self.agent.id, payload
        )

        self.assertEqual(self.agent_employee.parent_id, replacement_employee)
        self.assertEqual(self.task.csrs_manager_id, self.secondary)
        self.assertEqual(self.task.csrs_revision, 2)
        closed = self.env["csrs.reporting.line"].sudo().with_context(
            active_test=False
        ).search(
            [
                ("employee_id", "=", self.agent.id),
                ("supervisor_id", "=", self.manager.id),
            ]
        )
        self.assertEqual(closed.end_date.isoformat(), "2026-08-15")

    def test_public_facade_uses_model_level_rpc_contract(self):
        facade = self.env["csrs.api"].with_user(self.manager)
        public_methods = [
            name
            for name in dir(type(facade))
            if name.startswith("api_") and callable(getattr(type(facade), name, None))
        ]

        self.assertTrue(public_methods)
        for method_name in public_methods:
            self.assertTrue(
                getattr(getattr(type(facade), method_name), "_api_model", False),
                method_name,
            )

        session = call_kw(facade, "api_session", [], {})
        self.assertEqual(session["user"]["id"], self.manager.id)

    def test_agent_reports_one_hundred_percent_without_validating(self):
        task = self.task.with_user(self.agent)

        task.action_csrs_record_progress(100, expected_revision=1)

        self.assertEqual(task.csrs_status, "awaiting_validation")
        self.assertEqual(task.csrs_revision, 2)

    def test_primary_manager_validates_and_closes_with_revision_checks(self):
        task = self.task.with_user(self.manager)

        task.action_csrs_record_progress(100, "Travail vérifié", expected_revision=1)
        task.action_csrs_validate_completion(expected_revision=2)

        self.assertEqual(task.csrs_status, "completed")
        self.assertEqual(task.csrs_revision, 3)
        with self.assertRaises(UserError):
            task.action_csrs_validate_completion(expected_revision=2)

    def test_blocking_progress_requires_an_observation(self):
        with self.assertRaises(ValidationError):
            self.task.with_user(self.agent).action_csrs_record_progress(
                20, blocked=True, expected_revision=1
            )

    def test_rejected_proposal_is_corrected_then_accepted_atomically(self):
        proposal = self.env["csrs.task.proposal"].with_user(self.agent).create(
            {
                "title": "Préparer la note",
                "description": "Note relue et prête à signer",
                "project_id": self.project.id,
                "calendar_id": self.env.company.resource_calendar_id.id,
                "start_date": "2026-08-17",
                "due_date": "2026-08-21",
                "estimated_work_days": 2,
            }
        )

        proposal.with_user(self.manager).action_csrs_decide(
            "reject", "Préciser le livrable", expected_revision=1
        )
        proposal.with_user(self.agent).action_csrs_update(
            {"description": "Note validée et prête à signer"}, expected_revision=2
        )
        proposal.with_user(self.agent).action_csrs_resubmit(expected_revision=3)
        task = proposal.with_user(self.manager).action_csrs_decide(
            "accept", expected_revision=4
        )

        self.assertEqual(proposal.state, "accepted")
        self.assertEqual(proposal.accepted_task_id, task)
        self.assertEqual(task.user_ids, self.agent)
        self.assertEqual(task.csrs_manager_id, self.manager)

    def test_agenda_version_is_rendered_and_immutable(self):
        draft = self.env["csrs.agenda.draft"].sudo().create(
            {
                "period_start": "2026-08-17",
                "period_end": "2026-08-23",
                "major_events": "Réunion de coordination",
                "updated_by_id": self.secretariat.id,
            }
        )
        snapshot = {
            "schema_version": 1,
            "period_start": "2026-08-17",
            "period_end": "2026-08-23",
            "agenda_direction": "research",
            "agenda_direction_label": "Direction de la recherche",
            "major_events": "Réunion de coordination",
            "unclassified_users": [],
            "arrivals": [],
            "departures": [],
            "availability": [],
            "units": [],
        }

        with self.assertRaises(UserError):
            self.env["csrs.agenda.version"].with_user(
                self.agent
            ).create_from_snapshot(draft, "administration", snapshot)

        version = self.env["csrs.agenda.version"].with_user(
            self.secretariat
        ).create_from_snapshot(draft, "research", snapshot)

        self.assertTrue(version.pdf_attachment_id)
        self.assertGreater(version.pdf_size, 0)
        with self.assertRaises(UserError):
            version.with_user(self.secretariat).write({"version": 2})

    def test_django_hash_survives_registry_init_then_upgrades_on_login(self):
        password_hash = django_pbkdf2_sha256.using(rounds=1_000_000).hash(
            "LegacyPassword123!"
        )

        self.agent.csrs_import_legacy_password_hash(
            password_hash, replace_native=True
        )
        self.env["res.users"].init()
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [self.agent.id]
        )
        [stored_legacy_hash] = self.env.cr.fetchone()

        context = self.agent._crypt_context()
        self.assertLess(
            context.schemes().index("django_pbkdf2_sha256"),
            context.schemes().index("plaintext"),
        )
        self.assertEqual(
            context.identify(stored_legacy_hash), "django_pbkdf2_sha256"
        )
        authenticated = self.agent.with_user(self.agent)._check_credentials(
            {"type": "password", "password": "LegacyPassword123!"},
            {"interactive": True},
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [self.agent.id]
        )
        [stored_native_hash] = self.env.cr.fetchone()

        self.assertEqual(authenticated["uid"], self.agent.id)
        self.assertEqual(context.identify(stored_native_hash), "pbkdf2_sha512")

    def test_reimport_does_not_downgrade_an_upgraded_odoo_hash(self):
        legacy_hash = django_pbkdf2_sha256.using(rounds=1_000_000).hash(
            "LegacyPassword123!"
        )
        native_hash = self.agent._crypt_context().hash("LegacyPassword123!")
        self.agent._set_encrypted_password(self.agent.id, native_hash)

        changed = self.agent.csrs_import_legacy_password_hash(legacy_hash)
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [self.agent.id]
        )
        [stored_hash] = self.env.cr.fetchone()

        self.assertFalse(changed)
        self.assertEqual(stored_hash, native_hash)
