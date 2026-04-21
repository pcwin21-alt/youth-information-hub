from __future__ import annotations

import os

from .path_setup import configure_shared_imports


configure_shared_imports()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "institution_site_project.settings")

from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()
