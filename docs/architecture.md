# Architecture PENT

## Une seule source métier

Le navigateur appelle Django, Django traduit le cas d'usage, puis Odoo applique l'accès et persiste l'opération. Django ne possède ni copie locale ni table miroir des objets Odoo.

```text
navigateur
  -> Django PENT (vues, JSON, CSRF, présentation)
  -> gateway/odoo.py
  -> Odoo (règles, ACL, modèles CSRS)
  -> PostgreSQL Odoo
```

La base PostgreSQL de la stack appartient exclusivement à Odoo. `DATABASES = {}` est volontaire dans Django. Si un stockage technique devient nécessaire pour les sessions, files ou caches, il devra être décrit comme infrastructure et ne devra contenir aucun modèle métier.

## Correspondance initiale

| Domaine `csrs_report` | Cible Odoo | Décision |
| --- | --- | --- |
| Compte utilisateur | `res.users` et `res.partner` | Réutiliser le standard |
| Unité et agent | `hr.department` et `hr.employee` | Réutiliser puis compléter l'historisation datée |
| Plan et action | `project.project` et métadonnées CSRS | À préciser avant portage |
| Tâche | `project.task` étendu | Première tranche créée |
| Affectation et ligne hiérarchique | relations Odoo ou modèle CSRS daté | À concevoir dans Odoo |
| Progression | `csrs.progress.entry` | Append-only dans Odoo |
| Agenda, visite, absence | modules HR/Calendar et extensions CSRS | À rapprocher avant création |
| Processus et ordre de mission | activités/projets ou module CSRS | À rapprocher avant création |

## Interdits structurels

- Aucun `django.db.models.Model` métier.
- Aucun import direct de tables Odoo depuis Django.
- Aucun accès RPC Odoo hors de `gateway/`.
- Aucun secret Odoo dans le code, les journaux ou une session lisible.
- Aucune autorisation exclusivement implémentée dans l'interface Django.
