from passlib.hash import django_pbkdf2_sha256

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class CsrsMigrationTests(TransactionCase):
    def payload(self):
        return {
            "version": 2,
            "users": [
                {
                    "source_id": 9_000_101,
                    "email": "csrs-ent-migration-test@example.invalid",
                    "alias": "csrs-ent-migration-test",
                    "name": "Compte Migration",
                    "first_name": "Compte",
                    "last_name": "Migration",
                    "phone": "",
                    "job_title": "Profil source",
                    "agenda_direction": "programs",
                    "include_in_direction_agendas": True,
                    "active": True,
                    "is_it_admin": False,
                    "is_dg": False,
                    "password_hash": django_pbkdf2_sha256.using(
                        rounds=1_000_000
                    ).hash("MigrationPassword123!"),
                }
            ],
            "departments": [
                {
                    "source_id": 9_000_201,
                    "code": "CSRSENTTEST",
                    "name": "Service test CSRS ENT",
                    "short_name": "Service test",
                    "kind": "unit",
                    "display_order": 7,
                    "active": True,
                }
            ],
            "department_links": [],
            "memberships": [
                {
                    "source_id": 9_000_301,
                    "user_source_id": 9_000_101,
                    "department_source_id": 9_000_201,
                    "job_title": "Agent",
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "is_primary": True,
                }
            ],
            "reporting_lines": [],
            "role_grants": [],
        }

    def test_dry_run_validates_without_creating_records(self):
        report = self.env["csrs.migration.importer"].import_payload(
            self.payload(), apply=False
        )

        self.assertEqual(report["mode"], "dry-run")
        self.assertFalse(
            self.env["res.users"].search_count(
                [("csrs_source_id", "=", 9_000_101)]
            )
        )

    def test_apply_is_idempotent(self):
        importer = self.env["csrs.migration.importer"]

        first = importer.import_payload(self.payload(), apply=True)
        second = importer.import_payload(self.payload(), apply=True)

        self.assertEqual(first["created"]["users"], 1)
        self.assertEqual(second["unchanged"]["users"], 1)
        self.assertEqual(second["unchanged"]["employees"], 1)
        self.assertEqual(second["unchanged"]["employee_primary_memberships"], 1)
        self.assertEqual(
            self.env["res.users"].search_count(
                [("csrs_source_id", "=", 9_000_101)]
            ),
            1,
        )
        user = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        employee = self.env["hr.employee"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        department = self.env["hr.department"].search(
            [("csrs_source_id", "=", 9_000_201)]
        )
        self.assertEqual(user.csrs_first_name, "Compte")
        self.assertEqual(user.csrs_last_name, "Migration")
        self.assertEqual(employee.csrs_agenda_direction, "programs")
        self.assertTrue(employee.csrs_include_in_agenda)
        self.assertEqual(department.csrs_short_name, "Service test")
        self.assertEqual(department.csrs_kind, "unit")
        self.assertEqual(department.csrs_display_order, 7)

    def test_reporting_lines_are_preserved_as_dated_records(self):
        payload = self.payload()
        manager = dict(payload["users"][0])
        manager.update(
            {
                "source_id": 9_000_102,
                "email": "csrs-ent-manager@example.invalid",
                "alias": "csrs-ent-manager",
                "name": "Responsable Migration",
                "first_name": "Responsable",
                "last_name": "Migration",
            }
        )
        payload["users"].append(manager)
        payload["reporting_lines"] = [
            {
                "source_id": 9_000_401,
                "employee_source_id": 9_000_101,
                "supervisor_source_id": 9_000_102,
                "department_source_id": 9_000_201,
                "start_date": "2026-01-01",
                "end_date": None,
                "is_primary": True,
            }
        ]

        importer = self.env["csrs.migration.importer"]
        importer.import_payload(payload, apply=True)
        importer.import_payload(payload, apply=True)

        line = self.env["csrs.reporting.line"].search(
            [("csrs_source_id", "=", 9_000_401)]
        )
        self.assertEqual(len(line), 1)
        self.assertTrue(line.is_primary)
        self.assertFalse(line.end_date)
        employee = self.env["hr.employee"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.assertEqual(employee.parent_id.user_id, line.supervisor_id)

    def test_version_one_payload_is_rejected_to_avoid_silent_data_loss(self):
        payload = self.payload()
        payload["version"] = 1

        with self.assertRaises(ValidationError):
            self.env["csrs.migration.importer"].import_payload(payload, apply=False)

    def test_existing_employee_is_adopted_for_an_existing_user(self):
        payload = self.payload()
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Compte Migration",
                "login": "csrs-ent-migration-test@example.invalid",
                "email": "csrs-ent-migration-test@example.invalid",
            }
        )
        employee = self.env["hr.employee"].create(
            {"name": "Compte Migration", "user_id": user.id}
        )

        self.env["csrs.migration.importer"].import_payload(payload, apply=True)

        self.assertEqual(employee.csrs_source_id, 9_000_101)
        self.assertEqual(
            self.env["hr.employee"].search_count([("user_id", "=", user.id)]), 1
        )

    def test_cycle_is_rejected_before_any_write(self):
        payload = self.payload()
        payload["departments"].append(
            {
                "source_id": 9_000_202,
                "code": "CSRSENTTEST2",
                "name": "Service 2",
                "short_name": "Service 2",
                "kind": "unit",
                "display_order": 8,
                "active": True,
            }
        )
        payload["department_links"] = [
            {
                "source_id": 9_000_001,
                "parent_source_id": 9_000_201,
                "child_source_id": 9_000_202,
            },
            {
                "source_id": 9_000_002,
                "parent_source_id": 9_000_202,
                "child_source_id": 9_000_201,
            },
        ]

        with self.assertRaises(ValidationError):
            self.env["csrs.migration.importer"].import_payload(payload, apply=False)

    def test_alias_cannot_collide_with_another_accounts_email(self):
        payload = self.payload()
        second = dict(payload["users"][0])
        second.update(
            {
                "source_id": 9_000_102,
                "email": "second-csrs-ent-test@example.invalid",
                "alias": payload["users"][0]["email"],
            }
        )
        payload["users"].append(second)

        with self.assertRaises(ValidationError):
            self.env["csrs.migration.importer"].import_payload(payload, apply=False)
