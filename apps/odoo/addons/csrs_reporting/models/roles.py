"""Immutable catalog of roles available to the IT administrator."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CsrsRoleProfile:
    code: str
    label: str
    group_xmlids: frozenset[str]


AGENT_GROUP = "csrs_reporting.group_csrs_agent"
IT_GROUP = "csrs_reporting.group_csrs_it"


def _profile(code: str, label: str, group_xmlid: str) -> CsrsRoleProfile:
    return CsrsRoleProfile(
        code=code,
        label=label,
        group_xmlids=frozenset({AGENT_GROUP, group_xmlid}),
    )


ROLE_PROFILES = (
    CsrsRoleProfile("agent", "Agent", frozenset({AGENT_GROUP})),
    _profile(
        "primary_manager",
        "Responsable principal",
        "csrs_reporting.group_csrs_primary_manager",
    ),
    _profile(
        "secondary_manager",
        "Responsable secondaire",
        "csrs_reporting.group_csrs_secondary_manager",
    ),
    _profile("hr", "Ressources humaines", "csrs_reporting.group_csrs_hr"),
    _profile(
        "secretariat", "Secrétariat", "csrs_reporting.group_csrs_secretariat"
    ),
    _profile("dg", "Direction générale", "csrs_reporting.group_csrs_dg"),
    _profile(
        "finance",
        "Finances et comptabilité",
        "csrs_reporting.group_csrs_finance",
    ),
    _profile(
        "procurement", "Cellule achat", "csrs_reporting.group_csrs_procurement"
    ),
    _profile(
        "compliance",
        "Conformité et qualité",
        "csrs_reporting.group_csrs_compliance",
    ),
    _profile(
        "data_manager",
        "Gestion des données",
        "csrs_reporting.group_csrs_data_manager",
    ),
    _profile("fleet", "Parc automobile", "csrs_reporting.group_csrs_fleet"),
)
ROLE_PROFILE_BY_CODE = {profile.code: profile for profile in ROLE_PROFILES}
SWITCHABLE_GROUP_XMLIDS = frozenset(
    {IT_GROUP, *(group for profile in ROLE_PROFILES for group in profile.group_xmlids)}
)
