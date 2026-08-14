"""Technical views for the PENT gateway."""

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .odoo import OdooClient, OdooError


@require_GET
def index(request: object) -> JsonResponse:
    """Describe the deliberately small initial application surface."""
    return JsonResponse(
        {
            "application": "PENT",
            "role": "Passerelle Django vers Odoo",
            "source_of_truth": "odoo",
        }
    )


@require_GET
def health(request: object) -> JsonResponse:
    """Report that the Django process can serve requests."""
    return JsonResponse({"status": "ok", "service": "django"})


@require_GET
def readiness(request: object) -> JsonResponse:
    """Report whether Django can reach its authoritative Odoo service."""
    client = OdooClient(
        base_url=settings.ODOO_URL,
        database=settings.ODOO_DATABASE,
        timeout=settings.ODOO_TIMEOUT,
    )
    try:
        version = client.version()
    except OdooError:
        return JsonResponse({"status": "unavailable", "service": "odoo"}, status=503)
    return JsonResponse(
        {
            "status": "ok",
            "service": "odoo",
            "server_version": version.get("server_version", "unknown"),
        }
    )
