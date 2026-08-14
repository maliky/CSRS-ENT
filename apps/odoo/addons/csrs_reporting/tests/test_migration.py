from passlib.hash import django_pbkdf2_sha256

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class CsrsMigrationTests(TransactionCase):
    def payload(self):
        return {
            "version": 1,
            "users": [
                {
                    "source_id": 9_000_101,
                    "email": "pent-migration-test@example.invalid",
                    "alias": "pent-migration-test",
                    "name": "Compte Migration",
                    "phone": "",
                    "job_title": "Profil source",
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
                    "code": "PENTTEST",
                    "name": "Service test PENT",
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

    def test_existing_employee_is_adopted_for_an_existing_user(self):
        payload = self.payload()
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Compte Migration",
                "login": "pent-migration-test@example.invalid",
                "email": "pent-migration-test@example.invalid",
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
                "code": "PENTTEST2",
                "name": "Service 2",
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
                "email": "second-pent-test@example.invalid",
                "alias": payload["users"][0]["email"],
            }
        )
        payload["users"].append(second)

        with self.assertRaises(ValidationError):
            self.env["csrs.migration.importer"].import_payload(payload, apply=False)
