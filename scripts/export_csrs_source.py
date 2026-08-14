"""Emit the active CSRS identity snapshot; redirect stdout to a mode-0600 file."""

import json
import sys

from django.utils import timezone

from access.models import RoleGrant
from accounts.models import User
from work.models import (
    OrganizationMembership,
    OrganizationUnit,
    OrganizationUnitLink,
    ReportingLine,
)


now = timezone.now()
active_units = OrganizationUnit.objects.filter(active=True)
active_unit_ids = set(active_units.values_list("id", flat=True))
active_memberships = OrganizationMembership.objects.filter(
    end_date__isnull=True,
    unit_id__in=active_unit_ids,
    user__is_active=True,
)
primary_unit_by_user = dict(
    active_memberships.filter(is_primary=True).values_list("user_id", "unit_id")
)
open_lines = ReportingLine.objects.filter(
    end_date__isnull=True,
    employee__is_active=True,
    supervisor__is_active=True,
)
managed_user_ids = set(open_lines.values_list("employee_id", flat=True))


def iso_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


payload = {
    "version": 1,
    "extracted_at": now.isoformat(),
    "users": [
        {
            "source_id": user.id,
            "email": user.email,
            "alias": user.login_alias,
            "name": user.get_full_name() or str(user),
            "phone": user.phone,
            "job_title": user.position,
            "active": user.is_active,
            "is_it_admin": user.is_it_admin or user.is_superuser,
            "is_dg": (
                user.id not in managed_user_ids
                and not (user.is_it_admin or user.is_superuser)
            ),
            "password_hash": user.password,
        }
        for user in User.objects.filter(is_active=True).order_by("id")
    ],
    "departments": [
        {
            "source_id": unit.id,
            "code": unit.code,
            "name": unit.long_name,
            "short_name": unit.short_name,
            "active": unit.active,
        }
        for unit in active_units.order_by("id")
    ],
    "department_links": [
        {
            "source_id": link.id,
            "parent_source_id": link.supervisor_service_id,
            "child_source_id": link.collaborator_service_id,
        }
        for link in OrganizationUnitLink.objects.filter(
            supervisor_service_id__in=active_unit_ids,
            collaborator_service_id__in=active_unit_ids,
        ).order_by("id")
    ],
    "memberships": [
        {
            "source_id": membership.id,
            "user_source_id": membership.user_id,
            "department_source_id": membership.unit_id,
            "job_title": membership.job_title,
            "start_date": membership.start_date.isoformat(),
            "end_date": membership.end_date.isoformat() if membership.end_date else None,
            "is_primary": membership.is_primary,
        }
        for membership in active_memberships.order_by("id")
    ],
    "reporting_lines": [
        {
            "source_id": line.id,
            "employee_source_id": line.employee_id,
            "supervisor_source_id": line.supervisor_id,
            "department_source_id": (
                line.unit_id
                if line.unit_id in active_unit_ids
                else primary_unit_by_user[line.employee_id]
            ),
            "start_date": line.start_date.isoformat(),
            "end_date": line.end_date.isoformat() if line.end_date else None,
            "is_primary": line.is_primary,
        }
        for line in open_lines.order_by("id")
        if line.unit_id in active_unit_ids or line.employee_id in primary_unit_by_user
    ],
    "role_grants": [
        {
            "source_id": grant.id,
            "user_source_id": grant.user_id,
            "department_source_id": grant.unit_id,
            "role_code": grant.role.code,
            "scope": grant.scope,
            "valid_from": iso_datetime(grant.valid_from),
            "valid_until": iso_datetime(grant.valid_until),
            "active": True,
        }
        for grant in RoleGrant.objects.active_at(now)
        .filter(unit_id__in=active_unit_ids)
        .select_related("role")
        .order_by("id")
    ],
}

json.dump(payload, sys.stdout, ensure_ascii=True, separators=(",", ":"))
