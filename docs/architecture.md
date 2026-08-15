# Architecture PENT

## Une seule source métier

Le navigateur appelle l'interface React servie par Django. Django valide le contrat HTTP, traduit le cas d'usage, puis Odoo applique l'accès et persiste l'opération. Django ne possède ni copie locale ni table miroir des objets Odoo.

```text
navigateur
  -> React PENT sous /app/
  -> API Django (session, JSON, CSRF)
  -> gateway/odoo.py (client RPC unique)
  -> csrs.api (façade de cas d'usage Odoo)
  -> Odoo (règles, ACL, modèles CSRS)
  -> PostgreSQL Odoo
```

La base PostgreSQL de la stack appartient exclusivement à Odoo. `DATABASES = {}` est volontaire dans Django. Redis ne conserve que les sessions techniques Django et les compteurs de limitation; il ne contient aucun objet métier. Mailpit capture les notifications de préproduction sans livraison réelle.

## Authentification et reprise

Django normalise l'identifiant, transmet la tentative à l'API de session Odoo par `gateway/odoo.py`, puis conserve seulement l'identifiant opaque de session Odoo dans sa session Redis. Les API de connexion et déconnexion sont protégées par CSRF, les échecs sont limités et une session est revalidée auprès d'Odoo.

La reprise en lecture seule de `csrs_report` crée les comptes, employés, services, rattachements actifs, lignes hiérarchiques et délégations dans Odoo au moyen d'identifiants source stables. Les empreintes Django PBKDF2 sont acceptées transitoirement par Odoo puis converties vers le schéma Odoo après une connexion réussie; un nouvel import ne remplace jamais une empreinte déjà convertie.

## Correspondance initiale

| Domaine `csrs_report` | Cible Odoo | Décision |
| --- | --- | --- |
| Compte utilisateur | `res.users` et `res.partner` | Réutiliser le standard |
| Unité et agent | `hr.department`, `hr.employee` et `csrs.organization.membership` | État actif repris; historique différé |
| Plan et action | `project.project` et métadonnées CSRS | À préciser avant portage |
| Tâche | `project.task` étendu | Cycle de vie, révision et validation PENT |
| Proposition de tâche | `csrs.task.proposal` | Acceptation atomique vers `project.task` |
| Affectation et ligne hiérarchique | responsable principal standard et responsables secondaires CSRS | Autorisations appliquées dans Odoo |
| Progression | `csrs.progress.entry` | Append-only dans Odoo |
| Congé, absence et mission | `hr.leave` étendu | Alimente les agendas selon la période |
| Visite | `csrs.visitor.visit` | Arrivée et départ auditables |
| Agenda | `csrs.agenda.draft` et `csrs.agenda.version` | Brouillon courant, PDF et versions immuables |
| Processus et ordre de mission | activités/projets ou module CSRS | À rapprocher avant création |

## Interdits structurels

- Aucun `django.db.models.Model` métier.
- Aucun import direct de tables Odoo depuis Django.
- Aucun accès RPC Odoo hors de `gateway/`.
- Aucun secret Odoo dans le code, les journaux ou une session lisible.
- Aucune autorisation exclusivement implémentée dans l'interface Django.
