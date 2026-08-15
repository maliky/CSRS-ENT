"""WSGI entry point for CSRS ENT."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "csrs_ent.settings")
application = get_wsgi_application()
