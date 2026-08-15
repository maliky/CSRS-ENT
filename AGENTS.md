# Instructions de travail

Ces directives s'appliquent à tout le dépôt CSRS ENT.

## Architecture obligatoire

- Odoo est l'unique source de vérité pour les comptes, l'organigramme, les tâches, les progressions, les agendas et les processus CSRS.
- Ne pas créer de modèle métier Django ni de migration métier Django. Django sert l'interface, les API, les sessions techniques et l'intégration via `apps/django/gateway/`.
- Réutiliser les modèles Odoo standard avant de créer un modèle spécifique. Les extensions CSRS vivent dans `apps/odoo/addons/csrs_reporting/`.
- Appliquer les autorisations métier, ACL et règles d'enregistrement dans Odoo. Un contrôle ou un masquage dans Django ou React ne remplace jamais une autorisation Odoo.
- Tout nouvel accès Odoo depuis Django passe par le client central de `gateway/odoo.py`; ne pas disperser les appels RPC dans les vues.
- L'ancienne base de `csrs_report` sur `report.ent.koba.sarl` est une source de migration en lecture seule, pas une dépendance métier permanente. La reprise crée les comptes et l'organigramme dans Odoo par une commande explicite, réexécutable et auditée.

## Méthode

- Lire `DEV.org` et la décision d'architecture concernée avant une modification importante.
- Vérifier l'état Git et les fichiers concernés avant d'éditer; traiter tout commentaire de décision destiné à l'agent comme une instruction active jusqu'à son intégration explicite.
- Distinguer les besoins confirmés, les hypothèses et les questions ouvertes; ne pas marquer une capacité terminée sans code et vérification correspondants.
- Commencer par le comportement observable, écrire le test qui l'exprime, implémenter le plus petit changement, puis refactoriser sous tests.
- Préférer de petits changements vérifiables et réutiliser les fonctions, services et conventions existants avant d'ajouter une abstraction.
- Garder l'application et sa documentation utilisateur principalement en français. Garder les identifiants de code cohérents avec les conventions Python, Odoo et TypeScript du dépôt.
- Rester sobre dans les explications et ne pas allonger un texte sans justification fonctionnelle, factuelle ou technique.
- Ne pas envelopper manuellement la prose dans les fichiers `.org` et `.md`.
- Modifier les sources maintenues plutôt que leurs artefacts générés et garder les caches, données locales et sorties de déploiement hors Git.
- Préserver les modifications locales sans rapport avec la tâche et ne pas créer de commit sans demande explicite.

## Style fonctionnel et effets

- Séparer un cœur fonctionnel d'une enveloppe impérative : validation, normalisation, correspondance et décisions métier sont des fonctions déterministes; HTTP, RPC, ORM, horloge, environnement et journalisation restent aux frontières.
- Passer explicitement les données et dépendances; éviter l'état global mutable, les fonctions qui lisent implicitement l'environnement et les objets qui mélangent calcul, transport et persistance.
- Préférer des valeurs immuables pour les échanges internes, notamment `@dataclass(frozen=True, slots=True)`, tuples, `frozenset` et objets de valeur nommés.
- Garder les vues Django minces. Elles valident l'entrée, appellent un cas d'usage ou la passerelle, puis traduisent le résultat HTTP.
- Dans Odoo, regrouper chaque mutation métier dans une méthode explicite et transactionnelle. Les contraintes, ACL et règles d'enregistrement restent la dernière ligne de défense.
- Rendre les reprises de données idempotentes avec un mode `--dry-run`, des clés de correspondance stables, un rapport d'écarts et aucun écrasement silencieux.

## Typage fort

- Annoter les paramètres, retours et attributs du code Python nouveau ou modifié; TypeScript reste en mode strict dans le frontend React.
- Modéliser les structures connues avec `dataclass`, `TypedDict`, `Protocol`, `Literal` ou `Enum`; éviter les dictionnaires non structurés et les chaînes magiques.
- Confiner `Any` et les données RPC non fiables à la frontière, puis les valider et les convertir immédiatement vers un type interne précis.
- Ne pas ajouter de `cast` ou de `# type: ignore` pour masquer une erreur. Une exception imposée par Django ou Odoo doit être ciblée, commentée et couverte par un test.
- Exécuter le vérificateur de types en mode strict dès que sa configuration est introduite; une modification ne doit pas augmenter la dette de typage existante.

## Approche de test

- Nommer les tests par comportement et condition, avec une lecture Given/When/Then ou Arrange/Act/Assert claire.
- Tester les fonctions pures sans base ni réseau, les contrats RPC à la frontière, les réponses HTTP côté Django et les règles métier/permissions dans des tests Odoo transactionnels.
- Pour chaque écriture métier, couvrir au minimum le succès, le refus d'autorisation, l'entrée invalide et le conflit de révision lorsque la concurrence intervient.
- Tester les rôles réels : responsable principal, responsable secondaire, agent, RH, secrétariat, DG et administrateur IT. Un test d'interface ne remplace pas un test d'autorisation Odoo.
- Simuler uniquement les frontières externes. Ne pas mocker la règle métier testée ni reproduire l'implémentation dans les assertions.
- Une correction de défaut ajoute d'abord un test de régression qui échoue pour la cause observée.

## Branches et promotion

- `dev` est la branche d'intégration et la cible normale des changements terminés.
- `preprod` reçoit uniquement une promotion validée de `dev` et correspond à l'environnement de préproduction de cet hôte.
- `prod` est la branche de production; ne pas maintenir simultanément une quatrième branche `main` ou `master` sans décision explicite.
- Ne pas développer directement sur `preprod` ou `prod`, ne pas forcer leur publication et promouvoir le même commit testé entre les environnements.

## Sécurité et exploitation

- Ne jamais committer de secret, mot de passe, jeton, clé privée, dump ou donnée personnelle réelle.
- Committer uniquement les exemples d'environnement; les valeurs réelles restent dans `.env` ou dans la plateforme de déploiement.
- Ne pas modifier `/home/jil/csrs_report`, le dépôt `ent.git`, leurs conteneurs, volumes, réseaux, domaines ou services. Leur consultation pour préparer une migration reste en lecture seule.
- Ne jamais lancer `docker compose down -v`, un prune large ou une suppression non ciblée.
- Garder PostgreSQL privé. Les ports de développement et de préproduction sont liés à `127.0.0.1` par défaut.
- Valider les fichiers Compose avant tout déploiement et préserver les volumes Odoo lors des reconstructions.
- Ne jamais afficher, journaliser ni committer les empreintes de mot de passe. Leur transport de migration reste limité à un fichier temporaire de mode `0600`, transmis par l'entrée standard puis supprimé après vérification; le mécanisme compatible doit être couvert par des tests.

## Vérification minimale

- `PYENV_VERSION=csrs python apps/django/manage.py check`
- `PYENV_VERSION=csrs pytest`
- `PYENV_VERSION=csrs python -m ruff check apps/django`
- `PYENV_VERSION=csrs mypy apps/django`
- `npm run format:check --prefix frontend`, `npm test --prefix frontend` et `npm run build --prefix frontend`
- `docker-compose --env-file .env.example -f infrastructure/compose/compose.yaml config --quiet` sur cet hôte; accepter l'équivalent `docker compose` lorsqu'un greffon Compose v2 est disponible.
- Vérifier la syntaxe Python, XML et Bash du module et de l'image Odoo, puis exécuter les tests transactionnels Odoo dans l'image construite.
