{
    "name": "CSRS Reporting",
    "summary": "Suivi des tâches CSRS avec Odoo comme source de vérité",
    "version": "19.0.2.0.0",
    "category": "Services/Project",
    "author": "CSRS",
    "license": "LGPL-3",
    "depends": ["base", "hr", "project"],
    "data": [
        "security/csrs_reporting_groups.xml",
        "security/ir.model.access.csv",
        "security/csrs_reporting_rules.xml",
    ],
    "application": True,
    "installable": True,
}
