"""WSGI entry point for PENT."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pent.settings")
application = get_wsgi_application()
