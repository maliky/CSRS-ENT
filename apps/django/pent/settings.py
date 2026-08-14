"""Settings for the stateless-business PENT Django gateway."""

from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


def _csv_env(name: str, default: str = "") -> list[str]:
    return [
        value.strip() for value in os.getenv(name, default).split(",") if value.strip()
    ]


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.casefold() == "true"


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key")
DEBUG = _bool_env("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
TRUSTED_PROXY_ADDRESSES = frozenset(
    _csv_env("DJANGO_TRUSTED_PROXY_ADDRESSES", "127.0.0.1,::1")
)

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "gateway",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pent.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ]
        },
    }
]
WSGI_APPLICATION = "pent.wsgi.application"

# Odoo owns every persistent business object. Django has no ORM database.
DATABASES: dict[str, dict[str, str]] = {}

redis_url = os.getenv("REDIS_URL")
CACHES = (
    {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
        }
    }
    if redis_url
    else {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "pent-development",
        }
    }
)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_AGE_SECONDS", "28800"))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = _bool_env("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

ODOO_URL = os.getenv("ODOO_URL", "http://127.0.0.1:8069")
ODOO_DATABASE = os.getenv("ODOO_DB_NAME", "pent_odoo")
ODOO_TIMEOUT = float(os.getenv("ODOO_TIMEOUT", "5"))
