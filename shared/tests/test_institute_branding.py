from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "public-site/scripts/web_updater.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("institute_branding_updater", SCRIPT)
updater = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(updater)


class InstituteBrandingTests(unittest.TestCase):
    def test_official_logo_is_preserved_without_image_changes(self):
        logo = ROOT / "public-site/web" / updater.INSTITUTE_LOGO_PATH
        self.assertEqual(
            hashlib.sha256(logo.read_bytes()).hexdigest(),
            "7fe3436037ec2c501c493c9eff05174950275663f0902afcea3413a343cd2db5",
        )

    def test_page_header_and_footer_share_the_official_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "index.html"
            updater.write_page(output, "홈", "index.html", "<h1>검사</h1>", {}, {})
            page = output.read_text(encoding="utf-8")
        self.assertEqual(page.count(updater.INSTITUTE_LOGO_SRC), 2)
        self.assertIn('alt="적재적소 연구소" width="845" height="325"', page)
        self.assertIn('alt="적재적소 연구소 로고" width="845" height="325"', page)
        self.assertNotIn("right-policy-research-institute-banner.png", page)
        self.assertIn('href="https://rightpolicy.co.kr/"', page)

    def test_missing_verified_logo_does_not_fall_back_to_old_operator(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(updater, "PUBLIC_WEB_ROOT", Path(directory)):
                self.assertEqual(updater.youthside_footer_image_src(), "")
                self.assertEqual(updater.render_youthside_footer_image(), "")

    def test_favicon_uses_the_same_verified_logo(self):
        mark = (ROOT / "public-site/web/assets/branding/right-policy-mark.svg").read_text(encoding="utf-8")
        self.assertIn(Path(updater.INSTITUTE_LOGO_PATH).name, mark)
        self.assertNotIn("right-policy-research-institute-banner.png", mark)

