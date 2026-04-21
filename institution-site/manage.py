#!/usr/bin/env python
from __future__ import annotations

import os
import sys

from institution_site_project.path_setup import configure_shared_imports


def main() -> None:
    configure_shared_imports()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "institution_site_project.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
