"""Private, namespaced browser-test fixtures for disposable environments."""

from base64 import b64encode
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
    "csrs.purchase.evidence",
    "csrs.purchase.quotation",
    "csrs.fund.request",
    "csrs.purchase.request",
    "hr.leave",
    "csrs.agenda.version",
    "ir.attachment",
    "csrs.agenda.draft",
    "csrs.task.proposal",
    "project.task",
    "csrs.process.case",
    "csrs.project.budget.line",
    "project.project",
    "csrs.institutional.action",
    "csrs.action.plan",
    "csrs.strategic.plan",
    "hr.employee",
    "res.users",
    "res.partner",
    "product.product",
    "hr.department",
)
EXPECTED_COUNTS = {
    "hr.department": 2,
    "res.users": len(ROLE_GROUPS),
    "res.partner": len(ROLE_GROUPS) + 2,
    "product.product": 1,
    "hr.employee": len(ROLE_GROUPS),
    "ir.attachment": 1,
    "csrs.strategic.plan": 1,
    "csrs.action.plan": 1,
    "csrs.institutional.action": 1,
    "project.project": 2,
    "project.task": 2,
    "csrs.task.proposal": 1,
    "hr.leave": 1,
    "csrs.agenda.draft": 1,
    "csrs.process.case": len(PROCESS_TYPES),
    "csrs.project.budget.line": 1,
    "csrs.fund.request": 1,
    "csrs.purchase.request": 1,
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
        return self._track_name(_external_name(dataset, key), record)

    def _track_name(self, name, record):
        ModelData = self.env["ir.model.data"].sudo()
        existing = ModelData.search(
            [("module", "=", EXTERNAL_ID_MODULE), ("name", "=", name)], limit=1
        )
        if existing:
            if existing.model != record._name or existing.res_id != record.id:
                raise ValidationError(_("Référence E2E incohérente."))
            return record
        ModelData.create(
            {
                "module": EXTERNAL_ID_MODULE,
                "name": name,
                "model": record._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
        return record

    def _track_agenda_version(self, draft, version):
        suffix = "__agenda_draft"
        draft_reference = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [
                    ("module", "=", EXTERNAL_ID_MODULE),
                    ("model", "=", draft._name),
                    ("res_id", "=", draft.id),
                    ("name", "like", f"%{suffix}"),
                ],
                limit=1,
            )
        )
        if not draft_reference or not draft_reference.name.endswith(suffix):
            return version
        prefix = draft_reference.name[: -len(suffix)]
        self._track_name(f"{prefix}__agenda_version_{version.id}", version.sudo())
        if version.pdf_attachment_id:
            self._track_name(
                f"{prefix}__agenda_attachment_{version.pdf_attachment_id.id}",
                version.pdf_attachment_id.sudo(),
            )
        return version

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
        _reference, draft = self._find(dataset, "agenda_draft")
        if draft:
            return draft.period_start, draft.period_end
        offset = int.from_bytes(sha256(dataset.encode()).digest()[:2], "big") % 2500
        start = date(2090, 1, 2) + timedelta(days=offset)
        start -= timedelta(days=start.weekday())
        Draft = self.env["csrs.agenda.draft"].sudo()
        for _attempt in range(5200):
            end = start + timedelta(days=6)
            if not Draft.search_count(
                [("period_start", "=", start), ("period_end", "=", end)], limit=1
            ):
                return start, end
            start += timedelta(days=7)
        raise ValidationError(_("Aucune période E2E libre n'est disponible."))

    def _seed(self, dataset, password):
        if not isinstance(password, str) or len(password) < 16:
            raise ValidationError(_("Le mot de passe E2E doit contenir au moins 16 caractères."))
        created = defaultdict(int)
        marker = f"[E2E:{dataset}]"
        manual = dataset == "e2e-manual"

        def visible(default, manual_value=None):
            return (manual_value or default) if manual else f"{marker} {default}"

        manual_roles = {
            "agent": ("Agent demandeur", "Chargé de programme"),
            "manager": ("Responsable principal", "Responsable des programmes"),
            "secondary": ("Responsable secondaire", "Appui à la supervision"),
            "hr": ("Responsable RH", "Ressources humaines"),
            "secretariat": ("Secrétariat de direction", "Secrétariat"),
            "dg": ("Direction générale", "Direction générale"),
            "finance": ("Responsable financier", "Finances et comptabilité"),
            "procurement": ("Responsable des achats", "Achats"),
            "compliance": ("Responsable conformité", "Conformité"),
            "data": ("Gestionnaire des données", "Gestion des données"),
            "fleet": ("Responsable du parc automobile", "Parc automobile"),
            "it": ("Administrateur IT", "Systèmes d'information"),
        }
        manual_currency = (
            self.env.ref("base.XOF", raise_if_not_found=False)
            if manual
            else self.env.company.currency_id
        ) or self.env.company.currency_id
        root = self._ensure(
            dataset,
            "department_root",
            "hr.department",
            {
                "name": visible("Direction de recette", "Direction des opérations"),
                "csrs_code": "DOP" if manual else f"{_external_prefix(dataset).upper()}-ROOT",
                "csrs_short_name": "DOP" if manual else "E2E",
            },
            created,
        )
        child = self._ensure(
            dataset,
            "department_child",
            "hr.department",
            {
                "name": visible("Service de recette", "Service des programmes"),
                "csrs_code": "PROG" if manual else f"{_external_prefix(dataset).upper()}-UNIT",
                "csrs_short_name": "PROGRAMMES" if manual else "E2E-UNIT",
                "parent_id": root.id,
            },
            created,
        )

        users = {}
        agent_group = self.env.ref("csrs_reporting.group_csrs_agent")
        for role, label, group_xmlid in ROLE_GROUPS:
            group = self.env.ref(group_xmlid)
            manual_login = {
                "agent": "agent.demandeur@demo.invalid",
                "manager": "responsable.principal@demo.invalid",
                "secondary": "responsable.secondaire@demo.invalid",
                "hr": "responsable.rh@demo.invalid",
                "secretariat": "secretariat.direction@demo.invalid",
                "dg": "direction.generale@demo.invalid",
                "finance": "responsable.finance@demo.invalid",
                "procurement": "responsable.achats@demo.invalid",
                "compliance": "responsable.conformite@demo.invalid",
                "data": "gestionnaire.donnees@demo.invalid",
                "fleet": "responsable.parc@demo.invalid",
                "it": "administration.it@demo.invalid",
            }[role]
            login = manual_login if manual else f"{dataset}-{role}@example.invalid"
            user = self._ensure(
                dataset,
                f"user_{role}",
                "res.users",
                {
                    "name": manual_roles[role][0] if manual else f"{marker} {label}",
                    "login": login,
                    "email": login,
                    "csrs_alias": (
                        manual_login.partition("@")[0]
                        if manual
                        else f"{_external_prefix(dataset)}-{role}"[:64]
                    ),
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

        organization = self._ensure(
            dataset,
            "project_partner",
            "res.partner",
            {
                "name": visible("Fondation partenaire", "Fondation pour les communautés"),
                "company_type": "company",
                "email": "fondation@example.invalid",
            },
            created,
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
                "job_title": (
                    manual_roles["manager"][1] if manual else "Responsable de recette"
                ),
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
                    "job_title": (
                        manual_roles[role][1]
                        if manual
                        else f"Fonction de recette {role}"
                    ),
                    "csrs_agenda_direction": "research"
                    if role in {"agent", "data"}
                    else "administration",
                },
                created,
            )

        agent_employee = employees["agent"]
        tor_attachment = self._ensure(
            dataset,
            "employee_agent_tor",
            "ir.attachment",
            {
                "name": visible("cahier-des-charges.pdf"),
                "mimetype": "application/pdf",
                "datas": b64encode(b"%PDF-1.4\n% CSRS ENT fixture\n%%EOF\n"),
                "res_model": "hr.employee",
                "res_id": agent_employee.id,
            },
            created,
        )
        agent_employee.write(
            {
                "image_1920": (
                    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
                    b"+A8AAQUBAScY42YAAAAASUVORK5CYII="
                ),
                "csrs_terms_of_reference": (
                    "Préparer les activités de terrain, documenter les résultats et "
                    "rendre compte chaque semaine au responsable principal."
                ),
                "csrs_terms_of_reference_attachment_id": tor_attachment.id,
            }
        )

        strategic = self._ensure(
            dataset,
            "strategic_plan",
            "csrs.strategic.plan",
            {
                "name": visible("Plan stratégique", "Plan stratégique institutionnel"),
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
                "code": "PA" if manual else f"{_external_prefix(dataset).upper()}-PA",
                "name": visible("Plan d'action", "Plan d'action institutionnel"),
            },
            created,
        )
        action = self._ensure(
            dataset,
            "institutional_action",
            "csrs.institutional.action",
            {
                "action_plan_id": action_plan.id,
                "code": "ACT" if manual else f"{_external_prefix(dataset).upper()}-ACT",
                "name": visible("Action institutionnelle"),
            },
            created,
        )
        standard_project = self._ensure(
            dataset,
            "task_project",
            "project.project",
            {
                "name": visible("Activités institutionnelles"),
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
                    "name": visible(
                        f"Tâche de recette {index}", f"Tâche prioritaire {index}"
                    ),
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
                "title": visible("Proposition de recette", "Proposition d'activité terrain"),
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
                "name": visible(
                    "Projet de recherche", "Projet d'appui aux activités communautaires"
                ),
                "csrs_research_project": True,
                "csrs_objectives": "Exercer les neuf onglets du projet.",
                "csrs_institutional_commitments": "Jeu de données jetable.",
                "date_start": "2095-01-01",
                "date": "2095-12-31",
                "csrs_donor_id": organization.id,
                "csrs_team_user_ids": [Command.set(users["agent"].ids)],
            },
            created,
            user=users["agent"],
        )
        vendor = self._ensure(
            dataset,
            "purchase_vendor",
            "res.partner",
            {
                "name": visible("Fournisseur", "Fournitures et services du territoire"),
                "is_company": True,
                "supplier_rank": 1,
            },
            created,
            user=users["it"],
        )
        product = self._ensure(
            dataset,
            "purchase_product",
            "product.product",
            {
                "name": visible("Service terrain", "Kit de collecte terrain"),
                "type": "service",
                "purchase_ok": True,
            },
            created,
            user=users["it"],
        )
        budget_line = self._ensure(
            dataset,
            "research_budget_line",
            "csrs.project.budget.line",
            {
                "project_id": research_project.id,
                "code": "TERRAIN" if manual else "E2E-TERRAIN",
                "name": "Activités de terrain",
                "planned_amount": 1_000_000,
            },
            created,
        )
        for process_type, label in PROCESS_TYPES:
            case = self._ensure(
                dataset,
                f"process_{process_type}",
                "csrs.process.case",
                {
                    "process_type": process_type,
                    "requester_id": users["agent"].id,
                    "origin_department_id": child.id,
                    "project_id": research_project.id,
                    "subject": visible(
                        label,
                        {
                            "fund": "Frais de déplacement terrain",
                            "purchase": "Achat de kits de collecte",
                            "absence": "Demande d'absence annuelle",
                        }.get(process_type, label),
                    ),
                    "description": (
                        "Dossier d'exemple destiné au guide utilisateur."
                        if manual
                        else "Dossier de recette navigateur."
                    ),
                    "amount": (
                        {"fund": 250_000, "purchase": 300_000}.get(process_type, 0)
                        if manual
                        else (1000 if process_type in {"fund", "purchase"} else 0)
                    ),
                    "currency_id": manual_currency.id,
                },
                created,
                user=users["agent"],
            )
            if process_type == "fund":
                self._ensure(
                    dataset,
                    "fund_request",
                    "csrs.fund.request",
                    {
                        "case_id": case.id,
                        "budget_line_id": budget_line.id,
                        "beneficiary_id": users["agent"].partner_id.id,
                        "initiator_id": users["agent"].id,
                        "purpose": (
                            "Frais de déplacement pour le suivi des activités terrain."
                            if manual
                            else "Frais de terrain de recette."
                        ),
                    },
                    created,
                )
            if process_type == "purchase":
                self._ensure(
                    dataset,
                    "purchase_request",
                    "csrs.purchase.request",
                    {
                        "case_id": case.id,
                        "budget_line_id": budget_line.id,
                        "quantity": 2,
                        "estimated_amount": 300_000 if manual else 1000,
                    },
                    created,
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
                    "note": visible("Mission de recette", "Mission de suivi terrain"),
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
                    "major_events": visible(
                        "Réunion de coordination",
                        "Réunion de coordination des programmes",
                    ),
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
        marker = f"[E2E:{dataset}]"
        marked_cases = self.env["csrs.process.case"].sudo().search(
            [("subject", "ilike", marker)]
        )
        referenced_cases = self.env["csrs.process.case"].sudo().browse(
            [record.id for _reference, record in by_model["csrs.process.case"]]
        )
        tracked_cases = marked_cases | referenced_cases
        purchase_requests = self.env["csrs.purchase.request"].sudo().search(
            [("case_id", "in", tracked_cases.ids)]
        )
        orders = self.env["purchase.order"].sudo().search(
            [("csrs_process_case_id", "in", tracked_cases.ids)]
        )
        if purchase_requests:
            purchase_requests.write(
                {
                    "selected_quotation_id": False,
                    "purchase_order_id": False,
                    "vendor_bill_id": False,
                }
        )
        for order in orders:
            if order.state != "cancel":
                order.button_cancel()
            order.unlink()
        for model_name, records in (
            (
                "csrs.process.event",
                self.env["csrs.process.event"].sudo().search(
                    [("case_id", "in", tracked_cases.ids)]
                ),
            ),
            ("csrs.purchase.evidence", purchase_requests.evidence_ids),
            ("csrs.purchase.quotation", purchase_requests.quotation_ids),
            ("csrs.fund.request", self.env["csrs.fund.request"].sudo().search([("case_id", "in", tracked_cases.ids)])),
            ("csrs.purchase.request", purchase_requests),
        ):
            if records:
                models.Model.unlink(records.sudo())
        generated_attachments = self.env["ir.attachment"].sudo().search(
            [("res_model", "=", "csrs.process.case"), ("res_id", "in", tracked_cases.ids)]
        )
        generated_attachments.unlink()
        if tracked_cases:
            models.Model.unlink(tracked_cases)
        for model_name in DELETE_MODEL_ORDER:
            for reference, record in by_model.pop(model_name, []):
                if record.exists():
                    if model_name in {
                        "csrs.agenda.version",
                        "csrs.agenda.draft",
                        "csrs.task.proposal",
                        "csrs.process.case",
                        "csrs.purchase.evidence",
                        "csrs.purchase.quotation",
                        "project.project",
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
