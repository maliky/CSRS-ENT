{
    "name": "CSRS Reporting",
    "summary": "Suivi des tâches CSRS avec Odoo comme source de vérité",
    "version": "19.0.5.0.0",
    "category": "Services/Project",
    "author": "CSRS",
    "license": "LGPL-3",
    "depends": ["base", "hr", "hr_holidays", "mail", "project", "web"],
    "data": [
        "security/csrs_reporting_groups.xml",
        "security/ir.model.access.csv",
        "security/csrs_reporting_rules.xml",
        "data/csrs_sequences.xml",
        "data/csrs_leave_types.xml",
        "reports/csrs_agenda_report.xml",
    ],
    "application": True,
    "installable": True,
}
