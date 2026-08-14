from passlib.hash import django_pbkdf2_sha256

from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged("post_install", "-at_install")
class CsrsPermissionTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent_group = cls.env.ref("csrs_reporting.group_csrs_agent")
        primary_group = cls.env.ref("csrs_reporting.group_csrs_primary_manager")
        secondary_group = cls.env.ref("csrs_reporting.group_csrs_secondary_manager")

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
        cls.project = cls.env["project.project"].create(
            {"name": "Projet CSRS", "privacy_visibility": "employees"}
        )
        cls.task = cls.env["project.task"].create(
            {
                "name": "Rapport hebdomadaire",
                "project_id": cls.project.id,
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
            task.action_csrs_record_progress(25, expected_revision=0)

    def test_unrelated_agent_cannot_read_a_csrs_task(self):
        visible = (
            self.env["project.task"]
            .with_user(self.outsider)
            .search_count([("id", "=", self.task.id)])
        )

        self.assertEqual(visible, 0)

    def test_agent_cannot_validate_one_hundred_percent(self):
        with self.assertRaises(UserError):
            self.task.with_user(self.agent).action_csrs_record_progress(
                100, expected_revision=0
            )

    def test_primary_manager_validates_and_closes_with_revision_checks(self):
        task = self.task.with_user(self.manager)

        task.action_csrs_record_progress(100, "Travail vérifié", expected_revision=0)
        task.action_csrs_close(expected_revision=1)

        self.assertEqual(task.csrs_status, "closed")
        self.assertEqual(task.csrs_revision, 2)
        with self.assertRaises(UserError):
            task.action_csrs_close(expected_revision=1)

    def test_django_hash_is_accepted_then_marked_for_odoo_upgrade(self):
        password_hash = django_pbkdf2_sha256.using(rounds=1_000_000).hash(
            "LegacyPassword123!"
        )

        self.agent.csrs_import_legacy_password_hash(
            password_hash, replace_native=True
        )

        context = self.agent._crypt_context()
        valid, replacement = context.verify_and_update(
            "LegacyPassword123!", password_hash
        )
        self.assertTrue(valid)
        self.assertTrue(replacement.startswith("$pbkdf2-sha512$"))

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
