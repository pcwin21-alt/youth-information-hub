from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.auto_update_config import (  # noqa: E402
    normalize_auto_update_settings,
    validate_auto_update_settings,
)


class AutoUpdateConfigTests(unittest.TestCase):
    def test_normalize_auto_update_settings_coerces_types(self) -> None:
        settings = normalize_auto_update_settings(
            {
                "enabled": "1",
                "interval_minutes": "15",
                "skip_outbound_notifications": "false",
                "publish_on_article_change_only": "true",
            }
        )

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["interval_minutes"], 15)
        self.assertFalse(settings["skip_outbound_notifications"])
        self.assertTrue(settings["publish_on_article_change_only"])

    def test_validate_auto_update_settings_rejects_invalid_interval(self) -> None:
        with self.assertRaises(ValueError):
            validate_auto_update_settings({"enabled": True, "interval_minutes": 1})


if __name__ == "__main__":
    unittest.main()
