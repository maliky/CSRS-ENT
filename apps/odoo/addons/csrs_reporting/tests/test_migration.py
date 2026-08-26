from passlib.hash import django_pbkdf2_sha256

from odoo import fields
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

    def payload_v3(self):
        payload = self.payload()
        payload.update(
            {
                "version": 3,
                "strategic_plans": [
                    {
                        "source_id": 9_001_001,
                        "name": "Plan stratégique de test",
                        "start_date": "2026-01-01",
                        "end_date": "2030-12-31",
                        "active": True,
                    }
                ],
                "action_plans": [
                    {
                        "source_id": 9_001_002,
                        "strategic_plan_source_id": 9_001_001,
                        "code": "AP-TEST",
                        "name": "Plan d'action de test",
                        "active": True,
                    }
                ],
                "institutional_actions": [
                    {
                        "source_id": 9_001_003,
                        "action_plan_source_id": 9_001_002,
                        "code": "ACT-TEST",
                        "name": "Action de test",
                        "active": True,
                    }
                ],
                "work_calendars": [
                    {
                        "source_id": 9_001_004,
                        "name": "Calendrier test",
                        "version": "2026",
                        "is_default": False,
                        "active": True,
                    }
                ],
                "work_calendar_days": [
                    {
                        "source_id": 9_001_005,
                        "calendar_source_id": 9_001_004,
                        "day": "2026-08-15",
                        "name": "Jour non travaillé",
                        "is_working_day": False,
                    }
                ],
                "tasks": [
                    {
                        "source_id": 9_001_006,
                        "code": "TASK-TEST",
                        "title": "Tâche migrée",
                        "description": "Description source",
                        "action_source_id": 9_001_003,
                        "created_by_source_id": 9_000_101,
                        "created_at": "2026-08-01 08:00:00",
                        "updated_at": "2026-08-02 08:00:00",
                    }
                ],
                "task_assignments": [
                    {
                        "source_id": 9_001_007,
                        "task_source_id": 9_001_006,
                        "employee_source_id": 9_000_101,
                        "manager_source_id": 9_000_101,
                        "organization_unit_source_id": 9_000_201,
                        "calendar_source_id": 9_001_004,
                        "start_date": "2026-08-01",
                        "due_date": "2026-08-31",
                        "estimated_work_days": "10.0",
                        "status": "active",
                        "closed_reason": "",
                        "completed_at": None,
                        "revision": 2,
                    }
                ],
                "task_proposals": [
                    {
                        "source_id": 9_001_008,
                        "employee_source_id": 9_000_101,
                        "organization_unit_source_id": 9_000_201,
                        "title": "Proposition migrée",
                        "description": "Description proposition",
                        "action_source_id": 9_001_003,
                        "calendar_source_id": 9_001_004,
                        "start_date": "2026-09-01",
                        "due_date": "2026-09-30",
                        "estimated_work_days": "5.0",
                        "status": "submitted",
                        "reviewed_by_source_id": None,
                        "accepted_assignment_source_id": None,
                        "decision_note": "",
                        "decided_at": None,
                        "revision": 1,
                        "created_at": "2026-08-02 08:00:00",
                    }
                ],
                "progress_entries": [
                    {
                        "source_id": 9_001_009,
                        "assignment_source_id": 9_001_007,
                        "entry_date": "2026-08-10",
                        "percentage": 30,
                        "note": "Avancement source",
                        "blocked": False,
                        "author_source_id": 9_000_101,
                        "created_at": "2026-08-10 08:00:00",
                        "updated_at": "2026-08-10 08:00:00",
                    }
                ],
                "task_activities": [
                    {
                        "source_id": 9_001_010,
                        "assignment_source_id": 9_001_007,
                        "kind": "progress",
                        "actor_source_id": 9_000_101,
                        "occurred_at": "2026-08-10 08:00:00",
                        "message": "Progression enregistrée",
                        "percentage_before": 0,
                        "percentage_after": 30,
                        "progress_source_id": 9_001_009,
                        "details": {},
                        "supersedes_source_id": None,
                    }
                ],
                "task_history": [
                    {
                        "history_id": 9_002_001,
                        "record_id": 9_001_006,
                        "history_date": "2026-08-01 08:00:00",
                        "history_type": "+",
                        "history_user_source_id": 9_000_101,
                        "history_change_reason": "",
                        "code": "TASK-TEST",
                        "title": "Tâche migrée",
                    }
                ],
                "assignment_history": [
                    {
                        "history_id": 9_002_002,
                        "record_id": 9_001_007,
                        "history_date": "2026-08-01 08:05:00",
                        "history_type": "+",
                        "history_user_source_id": 9_000_101,
                        "history_change_reason": "",
                    }
                ],
                "proposal_history": [
                    {
                        "history_id": 9_002_003,
                        "record_id": 9_001_008,
                        "history_date": "2026-08-02 08:00:00",
                        "history_type": "+",
                        "history_user_source_id": 9_000_101,
                        "history_change_reason": "",
                    }
                ],
                "progress_history": [
                    {
                        "history_id": 9_002_004,
                        "record_id": 9_001_009,
                        "history_date": "2026-08-10 08:00:00",
                        "history_type": "+",
                        "history_user_source_id": 9_000_101,
                        "history_change_reason": "",
                        "assignment_source_id": 9_001_007,
                        "author_source_id": 9_000_101,
                        "percentage": 30,
                        "blocked": False,
                        "note": "Avancement source",
                    }
                ],
            }
        )
        return payload

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

    def test_version_three_work_history_is_imported_idempotently(self):
        importer = self.env["csrs.migration.importer"]

        first = importer.import_payload(self.payload_v3(), apply=True)
        task = self.env["project.task"].search(
            [("csrs_task_source_id", "=", 9_001_006)]
        )
        source_user = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        action = self.env["csrs.institutional.action"].search(
            [("csrs_source_id", "=", 9_001_003)]
        )
        calendar = self.env["resource.calendar"].search(
            [("csrs_source_id", "=", 9_001_004)]
        )
        self.assertEqual(
            importer._changes(
                task,
                {
                    "active": True,
                    "name": "Tâche migrée",
                    "description": "Description source",
                    "csrs_source_id": 9_001_007,
                    "csrs_task_source_id": 9_001_006,
                    "csrs_code": "TASK-TEST",
                    "csrs_managed": True,
                    "csrs_manager_id": source_user.id,
                    "user_ids": [(6, 0, source_user.ids)],
                    "csrs_calendar_id": calendar.id,
                    "csrs_start_date": fields.Date.to_date("2026-08-01"),
                    "date_deadline": fields.Date.to_date("2026-08-31"),
                    "csrs_estimated_work_days": 10.0,
                    "csrs_status": "active",
                    "csrs_close_reason": False,
                    "csrs_completed_at": False,
                    "csrs_revision": 2,
                    "csrs_institutional_action_id": action.id,
                },
            ),
            {},
        )

        identical = importer.import_payload(self.payload_v3(), apply=True)

        self.assertEqual(
            identical["unchanged"].get("task_progress_source_conflicts", 0), 0
        )
        task.with_context(csrs_authorized_mutation=True).write(
            {
                "csrs_status": "planned",
                "csrs_progress_percent": 77,
                "csrs_blocked": True,
                "csrs_revision": 99,
                "user_ids": [(6, 0, [])],
            }
        )
        proposal = self.env["csrs.task.proposal"].search(
            [("csrs_source_id", "=", 9_001_008)]
        )
        proposal.with_context(csrs_authorized_mutation=True).write(
            {"title": "Divergence locale"}
        )

        restored = importer.import_payload(self.payload_v3(), apply=True)
        third = importer.import_payload(self.payload_v3(), apply=True)

        self.assertEqual(first["created"]["tasks"], 1)
        self.assertEqual(restored["updated"]["tasks"], 1)
        self.assertEqual(restored["updated"]["task_proposals"], 1)
        self.assertEqual(
            restored["unchanged"].get("task_progress_source_conflicts", 0), 0
        )
        self.assertEqual(third["unchanged"]["tasks"], 1)
        self.assertEqual(task.csrs_status, "active")
        self.assertEqual(task.csrs_progress_percent, 30)
        self.assertFalse(task.csrs_blocked)
        self.assertEqual(task.csrs_revision, 2)
        self.assertEqual(task.user_ids, source_user)
        self.assertEqual(
            proposal.title,
            self.payload_v3()["task_proposals"][0]["title"],
        )
        self.assertEqual(len(task.csrs_progress_entry_ids), 1)
        self.assertEqual(len(task.csrs_legacy_revision_ids), 3)
        self.assertEqual(
            self.env["csrs.legacy.task.revision"].search_count(
                [("proposal_id", "=", proposal.id)]
            ),
            1,
        )

    def test_progress_revision_updates_are_reported_and_convergent(self):
        payload = self.payload_v3()
        payload["task_assignments"][0]["revision"] = 1
        second_progress_revision = dict(payload["progress_history"][0])
        second_progress_revision.update(
            {
                "history_id": 9_002_005,
                "history_date": "2026-08-10 09:00:00",
                "history_type": "~",
            }
        )
        payload["progress_history"].append(second_progress_revision)
        importer = self.env["csrs.migration.importer"]

        importer.import_payload(payload, apply=True, reconcile=True)
        task = self.env["project.task"].search(
            [("csrs_task_source_id", "=", 9_001_006)]
        )
        self.assertEqual(task.csrs_revision, 2)
        third_progress_revision = dict(second_progress_revision)
        third_progress_revision.update(
            {
                "history_id": 9_002_006,
                "history_date": "2026-08-10 10:00:00",
            }
        )
        payload["progress_history"].append(third_progress_revision)

        updated = importer.import_payload(payload, apply=True, reconcile=True)
        converged = importer.import_payload(payload, apply=True, reconcile=True)

        self.assertEqual(updated["updated"]["tasks"], 1)
        self.assertEqual(task.csrs_revision, 3)
        self.assertEqual(converged["updated"].get("tasks", 0), 0)

    def test_historical_work_accepts_a_deleted_organization_unit_reference(self):
        payload = self.payload_v3()
        payload["task_assignments"][0]["organization_unit_source_id"] = 9_999_991
        payload["task_proposals"][0]["organization_unit_source_id"] = 9_999_992

        report = self.env["csrs.migration.importer"].import_payload(
            payload, apply=False
        )

        self.assertEqual(report["mode"], "dry-run")

    def test_source_it_account_is_distinct_from_the_odoo_administrator(self):
        payload = self.payload()
        payload["users"][0]["is_it_admin"] = True

        self.env["csrs.migration.importer"].import_payload(payload, apply=True)

        imported = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.assertNotEqual(imported, self.env.ref("base.user_admin"))
        self.assertTrue(imported.has_group("csrs_reporting.group_csrs_it"))

    def test_reconcile_adopts_the_preserved_dev_alias(self):
        demo_dev = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Dev local",
                "login": "dev@demo.invalid",
                "email": "dev@demo.invalid",
                "csrs_alias": "dev",
                "password": "LocalDevPassword123!",
            }
        )
        employee = self.env["hr.employee"].create(
            {"name": demo_dev.name, "user_id": demo_dev.id}
        )
        payload = self.payload()
        payload["users"][0].update(
            {
                "email": "dev-real@example.invalid",
                "alias": "dev",
                "name": "Dev réel",
            }
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [demo_dev.id]
        )
        [password_before] = self.env.cr.fetchone()

        self.env["csrs.migration.importer"].import_payload(
            payload, apply=True, reconcile=True
        )

        imported = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.assertEqual(imported, demo_dev)
        self.assertEqual(employee.csrs_source_id, 9_000_101)
        self.assertEqual(imported.login, "dev-real@example.invalid")
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [demo_dev.id]
        )
        [password_after] = self.env.cr.fetchone()
        self.assertEqual(password_after, password_before)

    def test_reconcile_preserves_authoritative_demo_domain_identity(self):
        payload = self.payload()
        payload["users"][0].update(
            {
                "email": "authoritative-source@demo.invalid",
                "alias": "authoritative-source",
            }
        )
        importer = self.env["csrs.migration.importer"]
        importer.import_payload(payload, apply=True, reconcile=True)
        imported = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        imported.with_context(no_reset_password=True).write(
            {"password": "UpgradedSourcePassword123!"}
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [imported.id]
        )
        [password_before] = self.env.cr.fetchone()

        importer.import_payload(payload, apply=True, reconcile=True)

        preserved = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [preserved.id]
        )
        [password_after] = self.env.cr.fetchone()
        self.assertEqual(preserved, imported)
        self.assertEqual(password_after, password_before)

    def test_reconcile_preserves_source_identity_when_email_and_alias_change(self):
        payload = self.payload()
        payload["users"][0].update(
            {
                "email": "initial-source@demo.invalid",
                "alias": "initial-source",
            }
        )
        importer = self.env["csrs.migration.importer"]
        importer.import_payload(payload, apply=True, reconcile=True)
        imported = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        imported.with_context(no_reset_password=True).write(
            {"password": "UpgradedSourcePassword123!"}
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [imported.id]
        )
        [password_before] = self.env.cr.fetchone()
        payload["users"][0].update(
            {
                "email": "renamed-source@demo.invalid",
                "alias": "renamed-source",
            }
        )

        importer.import_payload(payload, apply=True, reconcile=True)

        preserved = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.env.cr.execute(
            "SELECT password FROM res_users WHERE id=%s", [preserved.id]
        )
        [password_after] = self.env.cr.fetchone()
        self.assertEqual(preserved, imported)
        self.assertEqual(preserved.login, "renamed-source@demo.invalid")
        self.assertEqual(password_after, password_before)

    def test_reconcile_adopts_demo_identity_matched_by_email(self):
        existing = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Identité source existante",
                "login": "legacy-login@demo.invalid",
                "email": "source-email@demo.invalid",
                "password": "ExistingSourcePassword123!",
            }
        )
        employee = self.env["hr.employee"].create(
            {"name": existing.name, "user_id": existing.id}
        )
        payload = self.payload()
        payload["users"][0].update(
            {"email": "source-email@demo.invalid", "alias": ""}
        )

        self.env["csrs.migration.importer"].import_payload(
            payload, apply=True, reconcile=True
        )

        imported = self.env["res.users"].search(
            [("csrs_source_id", "=", 9_000_101)]
        )
        self.assertEqual(imported, existing)
        self.assertEqual(employee.csrs_source_id, 9_000_101)
        self.assertEqual(
            self.env["res.users"].search_count(
                [("email", "=ilike", "source-email@demo.invalid")]
            ),
            1,
        )

    def test_reconcile_rebinds_department_source_ids_by_stable_code(self):
        payload = self.payload()
        payload["departments"].append(
            {
                "source_id": 9_000_202,
                "code": "CSRSENTTEST2",
                "name": "Service test CSRS ENT 2",
                "short_name": "Service test 2",
                "kind": "unit",
                "display_order": 8,
                "active": True,
            }
        )
        first = self.env["hr.department"].create(
            {
                "name": "Ancien service 1",
                "csrs_code": "CSRSENTTEST",
                "csrs_source_id": 9_000_202,
            }
        )
        second = self.env["hr.department"].create(
            {
                "name": "Ancien service 2",
                "csrs_code": "CSRSENTTEST2",
                "csrs_source_id": 9_000_201,
            }
        )

        report = self.env["csrs.migration.importer"].import_payload(
            payload, apply=True, reconcile=True
        )

        self.assertEqual(first.csrs_source_id, 9_000_201)
        self.assertEqual(second.csrs_source_id, 9_000_202)
        self.assertEqual(
            report["updated"]["department_source_ids_released"], 2
        )

    def test_reconcile_archives_a_displaced_department_absent_by_code(self):
        payload = self.payload()
        displaced = self.env["hr.department"].create(
            {
                "name": "Ancien service absent",
                "csrs_code": "ABSENT",
                "csrs_source_id": 9_000_201,
            }
        )

        report = self.env["csrs.migration.importer"].import_payload(
            payload, apply=True, reconcile=True
        )

        replacement = self.env["hr.department"].search(
            [("csrs_source_id", "=", 9_000_201)]
        )
        self.assertNotEqual(replacement, displaced)
        self.assertFalse(displaced.active)
        self.assertFalse(displaced.csrs_source_id)
        self.assertEqual(report["updated"]["departments_archived"], 1)

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

    def test_import_rejects_ambiguous_existing_email(self):
        payload = self.payload()
        email = payload["users"][0]["email"]
        existing = self.env["res.users"].browse()
        for index in range(2):
            existing |= self.env["res.users"].create(
                {
                    "name": f"Compte ambigu {index}",
                    "login": f"ambiguous-{index}@example.invalid",
                    "email": email,
                }
            )

        with self.assertRaises(ValidationError):
            self.env["csrs.migration.importer"].import_payload(payload, apply=True)

        self.assertFalse(any(existing.mapped("csrs_source_id")))
        self.assertFalse(
            self.env["res.users"].search([("csrs_source_id", "=", 9_000_101)])
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

    def test_v4_imports_legacy_agenda_archives_and_enables_read_only_mirror(self):
        import base64
        import hashlib
        import json

        payload = self.payload()
        payload["version"] = 4
        payload["extracted_at"] = "2026-08-25T08:00:00+00:00"
        payload["users"][0]["agenda_direction"] = "programs"
        for name in (
            "strategic_plans",
            "action_plans",
            "institutional_actions",
            "work_calendars",
            "work_calendar_days",
            "tasks",
            "task_assignments",
            "task_proposals",
            "progress_entries",
            "task_activities",
            "task_history",
            "assignment_history",
            "proposal_history",
            "progress_history",
        ):
            payload[name] = []
        snapshot = {
            "schema_version": 1,
            "period_start": "2026-08-24",
            "period_end": "2026-08-30",
            "agenda_direction": "programs",
            "agenda_direction_label": "Direction des programmes",
            "major_events": "RAS",
            "unclassified_users": [],
            "arrivals": [],
            "departures": [],
            "availability": [],
            "units": [],
        }
        canonical = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        pdf = b"%PDF-1.4\n%%EOF\n"
        payload.update(
            {
                "visitor_visits": [
                    {
                        "source_id": 9_100_001,
                        "party_size": 2,
                        "visitor_names": ["Visiteur Test"],
                        "arrived_at": "2026-08-25T08:00:00",
                        "departed_at": None,
                        "cancelled_at": None,
                        "cancellation_reason": "",
                        "revision": 1,
                    }
                ],
                "staff_availability": [
                    {
                        "source_id": 9_100_002,
                        "employee_source_id": 9_000_101,
                        "kind": "mission",
                        "start_date": "2026-08-25",
                        "end_date": "2026-08-26",
                        "note": "Mission de test",
                        "cancelled_at": None,
                        "cancellation_reason": "",
                        "revision": 1,
                    }
                ],
                "agenda_drafts": [
                    {
                        "source_id": 9_100_003,
                        "period_start": "2026-08-24",
                        "period_end": "2026-08-30",
                        "major_events": "RAS",
                        "revision": 1,
                        "updated_by_source_id": 9_000_101,
                        "updated_at": "2026-08-25T08:00:00",
                    }
                ],
                "agenda_versions": [
                    {
                        "source_id": 9_100_004,
                        "draft_source_id": 9_100_003,
                        "period_start": "2026-08-24",
                        "period_end": "2026-08-30",
                        "agenda_direction": "programs",
                        "version": 1,
                        "snapshot": snapshot,
                        "snapshot_sha256": hashlib.sha256(canonical).hexdigest(),
                        "pdf_base64": base64.b64encode(pdf).decode(),
                        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                        "pdf_size": len(pdf),
                        "generated_by_source_id": 9_000_101,
                        "generated_at": "2026-08-25T08:00:00",
                    }
                ],
            }
        )

        importer = self.env["csrs.migration.importer"]
        importer.import_payload(payload, apply=False)
        importer.import_payload(payload, apply=True, reconcile=True)
        local_visit = self.env["csrs.visitor.visit"].create(
            {
                "party_size": 1,
                "visitor_names": ["Essai préproduction"],
                "arrived_at": "2026-08-25 09:00:00",
            }
        )
        local_draft = self.env["csrs.agenda.draft"].create(
            {
                "period_start": "2026-09-07",
                "period_end": "2026-09-13",
                "major_events": "Essai local",
                "updated_by_id": self.env.user.id,
            }
        )
        imported_version = self.env["csrs.agenda.version"].search(
            [("csrs_source_id", "=", 9_100_004)]
        )
        local_attachment = self.env["ir.attachment"].create(
            {
                "name": "agenda-preprod-local.pdf",
                "type": "binary",
                "raw": b"%PDF-1.4\nAgenda preprod local\n",
                "mimetype": "application/pdf",
            }
        )
        local_version = imported_version.with_context(
            csrs_migration_import=True
        ).copy(
            {
                "csrs_source_id": False,
                "version": 99,
                "pdf_attachment_id": local_attachment.id,
            }
        )
        local_attachment.write(
            {
                "res_model": "csrs.agenda.version",
                "res_id": local_version.id,
            }
        )
        local_attachment_id = local_attachment.id
        second = importer.import_payload(payload, apply=True, reconcile=True)

        version = self.env["csrs.agenda.version"].search(
            [("csrs_source_id", "=", 9_100_004)]
        )
        self.assertEqual(len(version), 1)
        self.assertEqual(version.pdf_attachment_id.raw, pdf)
        self.assertEqual(second["unchanged"]["agenda_versions"], 1)
        self.assertFalse(local_visit.exists())
        self.assertFalse(local_draft.exists())
        self.assertFalse(local_version.exists())
        self.assertFalse(
            self.env["ir.attachment"].browse(local_attachment_id).exists()
        )
        self.assertEqual(second["deleted"]["visitor_visits"], 1)
        self.assertEqual(second["deleted"]["agenda_drafts"], 1)
        self.assertEqual(second["deleted"]["agenda_versions"], 1)
        session = self.env["csrs.api"].with_user(
            self.env["res.users"].search([("csrs_source_id", "=", 9_000_101)])
        ).api_session()
        self.assertEqual(session["reporting"]["mode"], "preprod_refresh")
        self.assertTrue(session["reporting"]["write_enabled"])
        self.assertTrue(session["reporting"]["authoritative_refresh"])
