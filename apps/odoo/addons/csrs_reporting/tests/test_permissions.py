from passlib.hash import django_pbkdf2_sha256

from odoo.fields import Command
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
            "agenda_direction": "administration",
            "agenda_direction_label": "Direction administrative",
            "major_events": "Réunion de coordination",
            "unclassified_users": [],
            "arrivals": [],
            "departures": [],
            "availability": [],
            "units": [],
        }

        version = self.env["csrs.agenda.version"].with_user(
            self.secretariat
        ).create_from_snapshot(draft, "administration", snapshot)

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
