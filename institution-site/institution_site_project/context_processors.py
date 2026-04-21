from __future__ import annotations

from briefings.editorial import user_can_manage_editorial


def editorial_navigation(request):  # noqa: ANN001
    return {
        "can_manage_editorial": user_can_manage_editorial(getattr(request, "user", None)),
    }
