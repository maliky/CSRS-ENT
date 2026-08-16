"""Private, namespaced browser-test fixtures for disposable environments."""

from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
import re

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command

from .processes import PROCESS_TYPES


DATASET_PATTERN = re.compile(r"^e2e-[a-z0-9-]{1,40}$")
EXTERNAL_ID_MODULE = "csrs_reporting_e2e"
ROLE_GROUPS = (
    ("agent", "Agent", "csrs_reporting.group_csrs_agent"),
    ("manager", "Responsable principal", "csrs_reporting.group_csrs_primary_manager"),
    ("secondary", "Responsable secondaire", "csrs_reporting.group_csrs_secondary_manager"),
    ("hr", "Ressources humaines", "csrs_reporting.group_csrs_hr"),
    ("secretariat", "Secrétariat", "csrs_reporting.group_csrs_secretariat"),
    ("dg", "Direction générale", "csrs_reporting.group_csrs_dg"),
    ("finance", "Finances", "csrs_reporting.group_csrs_finance"),
    ("procurement", "Achats", "csrs_reporting.group_csrs_procurement"),
    ("compliance", "Conformité", "csrs_reporting.group_csrs_compliance"),
    ("data", "Gestion des données", "csrs_reporting.group_csrs_data_manager"),
    ("fleet", "Parc automobile", "csrs_reporting.group_csrs_fleet"),
    ("it", "Administration IT", "csrs_reporting.group_csrs_it"),
)
DELETE_MODEL_ORDER = (
    "hr.leave",
    "csrs.agenda.version",
    "csrs.agenda.draft",
    "csrs.task.proposal",
    "project.task",
    "csrs.process.case",
    "project.project",
    "csrs.institutional.action",
    "csrs.action.plan",
    "csrs.strategic.plan",
    "hr.employee",
    "res.users",
    "res.partner",
    "hr.department",
)
EXPECTED_COUNTS = {
    "hr.department": 2,
    "res.users": len(ROLE_GROUPS),
    "res.partner": len(ROLE_GROUPS),
    "hr.employee": len(ROLE_GROUPS),
    "csrs.strategic.plan": 1,
    "csrs.action.plan": 1,
    "csrs.institutional.action": 1,
    "project.project": 2,
    "project.task": 2,
    "csrs.task.proposal": 1,
    "hr.leave": 1,
    "csrs.agenda.draft": 1,
    "csrs.process.case": len(PROCESS_TYPES),
}


def _validate_dataset(dataset):
    normalized = str(dataset or "").strip().lower()
    if not DATASET_PATTERN.fullmatch(normalized):
        raise ValidationError(
            _("Le jeu de données doit respecter le format e2e-nom-en-minuscules.")
        )
    return normalized


def _external_prefix(dataset):
    return dataset.replace("-", "_")


def _external_name(dataset, key):
    return f"{_external_prefix(dataset)}__{key}"


class CsrsE2EFixture(models.AbstractModel):
    _name = "csrs.e2e.fixture"
    _description = "Jeu de données privé pour la recette navigateur"

    def _tracked(self, dataset):
        prefix = f"{_external_prefix(dataset)}__"
        references = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [
                    ("module", "=", EXTERNAL_ID_MODULE),
                    ("name", "like", f"{prefix}%"),
                ],
                order="id",
            )
        )
        tracked = []
        for reference in references:
            record = self.env[reference.model].sudo().browse(reference.res_id).exists()
            if record:
                tracked.append((reference, record))
            else:
                reference.unlink()
        return tracked

    def _status(self, dataset):
        counts = defaultdict(int)
        for _reference, record in self._tracked(dataset):
            counts[record._name] += len(record)
        normalized = dict(sorted(counts.items()))
        return {
            "dataset": dataset,
            "counts": normalized,
            "total": sum(normalized.values()),
        }

    def _find(self, dataset, key):
        reference = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [
                    ("module", "=", EXTERNAL_ID_MODULE),
                    ("name", "=", _external_name(dataset, key)),
                ],
                limit=1,
            )
        )
        if not reference:
            return self.env["ir.model.data"], False
        record = self.env[reference.model].sudo().browse(reference.res_id).exists()
        if not record:
            reference.unlink()
        return reference, record

    def _track(self, dataset, key, record):
        self.env["ir.model.data"].sudo().create(
            {
                "module": EXTERNAL_ID_MODULE,
                "name": _external_name(dataset, key),
                "model": record._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
        return record

    def _ensure(self, dataset, key, model_name, values, created, user=None):
        _reference, record = self._find(dataset, key)
        if record:
            if record._name != model_name:
                raise ValidationError(_("Référence E2E incohérente."))
            return record
        model = self.env[model_name].with_context(no_reset_password=True)
        model = model.with_user(user) if user else model.sudo()
        record = model.create(values)
        self._track(dataset, key, record.sudo())
        created[model_name] += 1
        return record.sudo()

    def _fixture_period(self, dataset):
        offset = int.from_bytes(sha256(dataset.encode()).digest()[:2], "big") % 2500
        start = date(2090, 1, 2) + timedelta(days=offset)
        start -= timedelta(days=start.weekday())
        return start, start + timedelta(days=6)

    def _seed(self, dataset, password):
        if not isinstance(password, str) or len(password) < 16:
            raise ValidationError(_("Le mot de passe E2E doit contenir au moins 16 caractères."))
        created = defaultdict(int)
        marker = f"[E2E:{dataset}]"
        root = self._ensure(
            dataset,
            "department_root",
            "hr.department",
            {
                "name": f"{marker} Direction de recette",
                "csrs_code": f"{_external_prefix(dataset).upper()}-ROOT",
                "csrs_short_name": "E2E",
            },
            created,
        )
        child = self._ensure(
            dataset,
            "department_child",
            "hr.department",
            {
                "name": f"{marker} Service de recette",
                "csrs_code": f"{_external_prefix(dataset).upper()}-UNIT",
                "csrs_short_name": "E2E-UNIT",
                "parent_id": root.id,
            },
            created,
        )

        users = {}
        agent_group = self.env.ref("csrs_reporting.group_csrs_agent")
        for role, label, group_xmlid in ROLE_GROUPS:
            group = self.env.ref(group_xmlid)
            login = f"{dataset}-{role}@example.invalid"
            user = self._ensure(
                dataset,
                f"user_{role}",
                "res.users",
                {
                    "name": f"{marker} {label}",
                    "login": login,
                    "email": login,
                    "csrs_alias": f"{_external_prefix(dataset)}-{role}"[:64],
                    "password": password,
                    "group_ids": [
                        Command.link(agent_group.id),
                        Command.link(group.id),
                    ],
                },
                created,
            )
            users[role] = user
            self._ensure(
                dataset,
                f"partner_{role}",
                "res.partner",
                {"name": user.partner_id.name},
                created,
            ) if not user.partner_id else self._track_existing_partner(
                dataset, role, user.partner_id, created
            )

        employees = {}
        manager_employee = self._ensure(
            dataset,
            "employee_manager",
            "hr.employee",
            {
                "name": users["manager"].name,
                "user_id": users["manager"].id,
                "department_id": root.id,
                "job_title": "Responsable de recette",
            },
            created,
        )
        employees["manager"] = manager_employee
        for role, _label, _group_xmlid in ROLE_GROUPS:
            if role == "manager":
                continue
            employees[role] = self._ensure(
                dataset,
                f"employee_{role}",
                "hr.employee",
                {
                    "name": users[role].name,
                    "user_id": users[role].id,
                    "department_id": child.id,
                    "parent_id": manager_employee.id,
                    "job_title": f"Fonction de recette {role}",
                    "csrs_agenda_direction": "research"
                    if role in {"agent", "data"}
                    else "administration",
                },
                created,
            )

        strategic = self._ensure(
            dataset,
            "strategic_plan",
            "csrs.strategic.plan",
            {
                "name": f"{marker} Plan stratégique",
                "start_date": "2090-01-01",
                "end_date": "2099-12-31",
            },
            created,
        )
        action_plan = self._ensure(
            dataset,
            "action_plan",
            "csrs.action.plan",
            {
                "strategic_plan_id": strategic.id,
                "code": f"{_external_prefix(dataset).upper()}-PA",
                "name": f"{marker} Plan d'action",
            },
            created,
        )
        action = self._ensure(
            dataset,
            "institutional_action",
            "csrs.institutional.action",
            {
                "action_plan_id": action_plan.id,
                "code": f"{_external_prefix(dataset).upper()}-ACT",
                "name": f"{marker} Action institutionnelle",
            },
            created,
        )
        standard_project = self._ensure(
            dataset,
            "task_project",
            "project.project",
            {
                "name": f"{marker} Activités institutionnelles",
                "privacy_visibility": "employees",
            },
            created,
        )
        for index, progress in enumerate((25, 75), start=1):
            self._ensure(
                dataset,
                f"task_{index}",
                "project.task",
                {
                    "name": f"{marker} Tâche de recette {index}",
                    "project_id": standard_project.id,
                    "csrs_managed": True,
                    "csrs_manager_id": users["manager"].id,
                    "user_ids": [Command.set(users["agent"].ids)],
                    "csrs_institutional_action_id": action.id,
                    "csrs_start_date": "2095-01-03",
                    "date_deadline": "2095-01-10",
                    "csrs_estimated_work_days": 1.0,
                    "csrs_progress_percent": progress,
                },
                created,
                user=users["manager"],
            )
        self._ensure(
            dataset,
            "proposal",
            "csrs.task.proposal",
            {
                "title": f"{marker} Proposition de recette",
                "description": "Vérifier le parcours complet de proposition.",
                "author_id": users["agent"].id,
                "manager_id": users["manager"].id,
                "institutional_action_id": action.id,
                "calendar_id": self.env.company.resource_calendar_id.id,
                "start_date": "2095-01-03",
                "due_date": "2095-01-10",
                "estimated_work_days": 1.0,
            },
            created,
            user=users["agent"],
        )
        research_project = self._ensure(
            dataset,
            "research_project",
            "project.project",
            {
                "name": f"{marker} Projet de recherche",
                "csrs_research_project": True,
                "csrs_objectives": "Exercer les neuf onglets du projet.",
                "csrs_institutional_commitments": "Jeu de données jetable.",
                "date_start": "2095-01-01",
                "date": "2095-12-31",
                "csrs_team_user_ids": [Command.set(users["agent"].ids)],
            },
            created,
            user=users["agent"],
        )
        for process_type, label in PROCESS_TYPES:
            self._ensure(
                dataset,
                f"process_{process_type}",
                "csrs.process.case",
                {
                    "process_type": process_type,
                    "requester_id": users["agent"].id,
                    "origin_department_id": child.id,
                    "project_id": research_project.id,
                    "subject": f"{marker} {label}",
                    "description": "Dossier de recette navigateur.",
                    "amount": 1000 if process_type in {"fund", "purchase"} else 0,
                },
                created,
                user=users["agent"],
            )

        start, end = self._fixture_period(dataset)
        facade = self.env["csrs.api"].with_user(users["it"])
        _reference, leave = self._find(dataset, "availability")
        if not leave:
            payload = facade.api_availability_save(
                {
                    "employee_id": users["agent"].id,
                    "kind": "mission",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "note": f"{marker} Mission de recette",
                }
            )
            leave = self.env["hr.leave"].sudo().browse(payload["id"])
            self._track(dataset, "availability", leave)
            created["hr.leave"] += 1
        _reference, draft = self._find(dataset, "agenda_draft")
        if not draft:
            facade.api_agenda_update_draft(
                {
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "major_events": f"{marker} Réunion de coordination",
                    "revision": 0,
                }
            )
            draft = (
                self.env["csrs.agenda.draft"]
                .sudo()
                .search(
                    [
                        ("period_start", "=", start),
                        ("period_end", "=", end),
                    ],
                    limit=1,
                )
            )
            self._track(dataset, "agenda_draft", draft)
            created["csrs.agenda.draft"] += 1

        report = self._status(dataset)
        report["created"] = dict(sorted(created.items()))
        return report

    def _track_existing_partner(self, dataset, role, partner, created):
        _reference, tracked = self._find(dataset, f"partner_{role}")
        if not tracked:
            self._track(dataset, f"partner_{role}", partner.sudo())
            created["res.partner"] += 1
        elif tracked != partner:
            raise ValidationError(_("Partenaire E2E incohérent."))
        return partner

    def _clean(self, dataset):
        tracked = self._tracked(dataset)
        deleted = defaultdict(int)
        by_model = defaultdict(list)
        for reference, record in tracked:
            by_model[record._name].append((reference, record))
        for model_name in DELETE_MODEL_ORDER:
            for reference, record in by_model.pop(model_name, []):
                if record.exists():
                    if model_name in {
                        "csrs.agenda.version",
                        "csrs.agenda.draft",
                        "csrs.task.proposal",
                        "csrs.process.case",
                    }:
                        models.Model.unlink(record.sudo())
                    else:
                        record.sudo().unlink()
                    deleted[model_name] += 1
                reference.exists().unlink()
        if by_model:
            raise ValidationError(
                _("Le nettoyage E2E ne connaît pas toutes les dépendances suivies.")
            )
        return {
            "dataset": dataset,
            "deleted": dict(sorted(deleted.items())),
            "deleted_total": sum(deleted.values()),
        }

    def _execute(self, mode, dataset, password=None, dry_run=False):
        dataset = _validate_dataset(dataset)
        if mode not in {"status", "seed", "clean", "reseed"}:
            raise ValidationError(_("Mode E2E invalide."))
        if mode == "status":
            return self._status(dataset)
        if dry_run:
            current = self._status(dataset)
            return {
                **current,
                "dry_run": True,
                "planned": (
                    dict(sorted(EXPECTED_COUNTS.items()))
                    if mode in {"seed", "reseed"}
                    else current["counts"]
                ),
            }
        if mode == "clean":
            return self._clean(dataset)
        if mode == "reseed":
            cleaned = self._clean(dataset)
            seeded = self._seed(dataset, password)
            seeded["cleaned"] = cleaned["deleted"]
            return seeded
        return self._seed(dataset, password)
