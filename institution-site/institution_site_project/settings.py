from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from .path_setup import BASE_DIR, RUNTIME_PIPELINE_ROOT, configure_shared_imports


configure_shared_imports()

RUNNING_TESTS = "test" in sys.argv or "PYTEST_CURRENT_TEST" in os.environ


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(f"{name} is required when DJANGO_DEBUG=0")


def database_config() -> dict[str, object]:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "app.db",
        }

    parsed = urlparse(url)
    if parsed.scheme in {"postgres", "postgresql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": parsed.port or "",
        }
    if parsed.scheme == "sqlite":
        sqlite_path = parsed.path.lstrip("/") or "app.db"
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / sqlite_path,
        }
    raise RuntimeError(f"unsupported_database_url_scheme:{parsed.scheme}")


DEBUG = env_bool("DJANGO_DEBUG", True if RUNNING_TESTS else False)
BEHIND_PROXY = env_bool("DJANGO_BEHIND_PROXY", False)

if DEBUG or RUNNING_TESTS:
    SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
else:
    SECRET_KEY = require_env("DJANGO_SECRET_KEY")
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", [])
    if not ALLOWED_HOSTS:
        raise RuntimeError("DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG=0")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE_SECONDS", 28_800)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "briefings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "institution_site_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "institution_site_project.context_processors.editorial_navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "institution_site_project.wsgi.application"
ASGI_APPLICATION = "institution_site_project.asgi.application"

DATABASES = {"default": database_config()}

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = LOGIN_URL

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

USE_X_FORWARDED_HOST = BEHIND_PROXY
SECURE_SSL_REDIRECT = BEHIND_PROXY and not DEBUG
SECURE_HSTS_SECONDS = 31_536_000 if BEHIND_PROXY and not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = BEHIND_PROXY and not DEBUG
SECURE_HSTS_PRELOAD = BEHIND_PROXY and not DEBUG
if BEHIND_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTITUTION_RUNTIME_PIPELINE_ROOT = str(RUNTIME_PIPELINE_ROOT)
