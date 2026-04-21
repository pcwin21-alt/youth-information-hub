from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from youth_info_platform.auto_update_config import DEFAULT_AUTO_UPDATE_SETTINGS
from youth_info_platform.contact_config import DEFAULT_CONTACT_SETTINGS

from .admin import StaffProfileAdmin
from .editorial import PipelineLockedError
from .models import AdminAuditLog, PageViewEvent, StaffProfile, SyncedArticle


REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGE_PY = REPO_ROOT / "institution-site" / "manage.py"


class SecuritySettingsTests(TestCase):
    def _run_manage_command(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(MANAGE_PY), *args]
        full_env = os.environ.copy()
        full_env.setdefault("PYTHONUTF8", "1")
        full_env.setdefault("PYTHONIOENCODING", "utf-8")
        if env:
            full_env.update(env)
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=full_env,
        )

    def test_production_boot_fails_without_secret_key(self) -> None:
        env = {
            "DJANGO_DEBUG": "0",
            "DJANGO_ALLOWED_HOSTS": "example.com",
        }
        env.pop("DJANGO_SECRET_KEY", None)
        result = self._run_manage_command("check", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", (result.stderr or "") + (result.stdout or ""))

    def test_production_security_settings_are_enabled(self) -> None:
        env = {
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "test-secret-key-for-security-check",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DJANGO_BEHIND_PROXY": "1",
        }
        result = self._run_manage_command(
            "shell",
            "-c",
            (
                "import json; "
                "from django.conf import settings; "
                "print(json.dumps({"
                "'debug': settings.DEBUG, "
                "'session_cookie_secure': settings.SESSION_COOKIE_SECURE, "
                "'csrf_cookie_secure': settings.CSRF_COOKIE_SECURE, "
                "'session_cookie_httponly': settings.SESSION_COOKIE_HTTPONLY, "
                "'session_cookie_samesite': settings.SESSION_COOKIE_SAMESITE, "
                "'csrf_cookie_samesite': settings.CSRF_COOKIE_SAMESITE, "
                "'secure_ssl_redirect': settings.SECURE_SSL_REDIRECT, "
                "'secure_hsts_seconds': settings.SECURE_HSTS_SECONDS, "
                "'secure_hsts_include_subdomains': settings.SECURE_HSTS_INCLUDE_SUBDOMAINS, "
                "'x_frame_options': settings.X_FRAME_OPTIONS, "
                "'session_save_every_request': settings.SESSION_SAVE_EVERY_REQUEST"
                "}))"
            ),
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertFalse(payload["debug"])
        self.assertTrue(payload["session_cookie_secure"])
        self.assertTrue(payload["csrf_cookie_secure"])
        self.assertTrue(payload["session_cookie_httponly"])
        self.assertEqual(payload["session_cookie_samesite"], "Lax")
        self.assertEqual(payload["csrf_cookie_samesite"], "Lax")
        self.assertTrue(payload["secure_ssl_redirect"])
        self.assertEqual(payload["secure_hsts_seconds"], 31_536_000)
        self.assertTrue(payload["secure_hsts_include_subdomains"])
        self.assertEqual(payload["x_frame_options"], "DENY")
        self.assertTrue(payload["session_save_every_request"])

    def test_manage_check_deploy_passes_in_production_mode(self) -> None:
        env = {
            "DJANGO_DEBUG": "0",
            "DJANGO_SECRET_KEY": "test-secret-key-for-deploy-check",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DJANGO_BEHIND_PROXY": "1",
        }
        result = self._run_manage_command("check", "--deploy", env=env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class EditorialDashboardTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.platform_admin = user_model.objects.create_user(username="editor", password="pw123456789")
        self.platform_admin.staff_profile.role = self.platform_admin.staff_profile.ROLE_PLATFORM_ADMIN
        self.platform_admin.staff_profile.save(update_fields=["role"])

        self.staff_user = user_model.objects.create_user(username="staff", password="pw123456789")
        self.staff_user.staff_profile.role = self.staff_user.staff_profile.ROLE_STAFF
        self.staff_user.staff_profile.save(update_fields=["role"])

        self.article = SyncedArticle.objects.create(
            article_key="https://example.com/article-1",
            title="운영 기사",
            article_url="https://example.com/article-1",
            source_name="테스트신문",
            summary="요약",
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_non_logged_in_user_is_redirected_for_editorial_pages(self) -> None:
        for path in ("/editorial/", "/editorial/settings/", "/editorial/history/", "/editorial/analytics/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/accounts/login/", response["Location"])

    def test_non_logged_in_user_is_redirected_for_editorial_mutations(self) -> None:
        for path, payload in (
            ("/editorial/", {"action": "collect_and_refresh_public"}),
            ("/editorial/settings/", {"action": "save_auto_update_settings", "auto_update_enabled": "on"}),
        ):
            response = self.client.post(path, payload)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/accounts/login/", response["Location"])

    def test_staff_user_cannot_access_editorial_pages(self) -> None:
        self.client.force_login(self.staff_user)
        for path in ("/editorial/", "/editorial/settings/", "/editorial/history/", "/editorial/analytics/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 403)

    def test_staff_user_cannot_run_manual_refresh_or_change_auto_update_settings(self) -> None:
        self.client.force_login(self.staff_user)
        for path, payload in (
            ("/editorial/", {"action": "collect_and_refresh_public", "next": "/editorial/"}),
            (
                "/editorial/settings/",
                {"action": "save_auto_update_settings", "auto_update_enabled": "on", "auto_update_interval_minutes": "10"},
            ),
        ):
            response = self.client.post(path, payload)
            self.assertEqual(response.status_code, 403)

    def test_editorial_dashboard_updates_article_and_creates_audit_log(self) -> None:
        self.client.force_login(self.platform_admin)
        override_path = Path(self.temp_dir.name) / "editorial_overrides.json"

        with patch("briefings.editorial.editorial_overrides_path", return_value=override_path):
            response = self.client.post(
                "/editorial/",
                {
                    "action": "update_article",
                    "article_id": self.article.id,
                    "editorial_decision": SyncedArticle.DECISION_FEATURE,
                    "editorial_feature_rank": "1",
                    "editorial_note": "첫 화면 고정",
                    "next": "/editorial/",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.editorial_decision, SyncedArticle.DECISION_FEATURE)
        self.assertEqual(self.article.editorial_feature_rank, 1)
        self.assertEqual(self.article.editorial_note, "첫 화면 고정")

        payload = json.loads(override_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["articles"][0]["decision"], SyncedArticle.DECISION_FEATURE)

        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_EDITORIAL)
        self.assertEqual(log.actor, self.platform_admin)
        self.assertEqual(log.target_key, self.article.article_key)
        self.assertEqual(log.after_data["decision"], SyncedArticle.DECISION_FEATURE)

    def test_contact_settings_save_updates_json_and_creates_audit_log(self) -> None:
        self.client.force_login(self.platform_admin)
        contact_settings_path = Path(self.temp_dir.name) / "contact_settings.json"
        contact_settings_path.write_text(
            json.dumps(DEFAULT_CONTACT_SETTINGS, ensure_ascii=False),
            encoding="utf-8",
        )

        refresh_result = {
            "command": "web_updater.py",
            "returncode": 0,
            "stdout": "updated contact page",
            "stderr": "",
        }
        with (
            patch("youth_info_platform.contact_config.CONTACT_SETTINGS_PATH", contact_settings_path),
            patch("briefings.views.CONTACT_SETTINGS_PATH", contact_settings_path),
            patch("briefings.views.run_contact_settings_refresh", return_value=refresh_result),
        ):
            response = self.client.post(
                "/editorial/settings/",
                {
                    "organization_name": "청년 투게더 운영팀",
                    "copyright_text": "© 2026",
                    "version_text": "v0.4 admin",
                    "email": "ops@example.com",
                    "extra_line_1": "문의는 메일로 보내 주세요.",
                    "extra_line_2": "긴급 제보는 별도 연락 바랍니다.",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(contact_settings_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["organization_name"], "청년 투게더 운영팀")
        self.assertEqual(payload["email"], "ops@example.com")

        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_CONTACT)
        self.assertEqual(log.actor, self.platform_admin)
        self.assertEqual(log.after_data["contact_settings"]["organization_name"], "청년 투게더 운영팀")
        self.assertEqual(log.after_data["refresh_result"]["command"], "web_updater.py")

    def test_refresh_public_creates_publish_audit_log(self) -> None:
        self.client.force_login(self.platform_admin)
        outputs = [
            {"command": "run_curator.py", "stdout": "selected 16", "stderr": "", "returncode": 0},
            {"command": "db_writer.py", "stdout": "db updated", "stderr": "", "returncode": 0},
            {"command": "web_updater.py", "stdout": "web updated", "stderr": "", "returncode": 0},
        ]
        with (
            patch("briefings.views.run_public_editorial_refresh", return_value=outputs),
            patch("briefings.views.call_command"),
            patch("briefings.views.export_editorial_overrides", return_value="test_overrides.json"),
        ):
            response = self.client.post(
                "/editorial/",
                {"action": "refresh_public", "next": "/editorial/"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_PUBLISH, action="refresh_public")
        self.assertEqual(log.actor, self.platform_admin)
        self.assertEqual(len(log.after_data["outputs"]), 3)

    def test_collect_and_refresh_public_runs_full_pipeline_and_creates_audit_log(self) -> None:
        self.client.force_login(self.platform_admin)
        outputs = [
            {"command": "rss_fetcher.py", "stdout": "collected_articles=42", "stderr": "", "returncode": 0},
            {"command": "dedup_filter.py", "stdout": "filtered=31", "stderr": "", "returncode": 0},
            {"command": "run_curator.py", "stdout": "selected 16", "stderr": "", "returncode": 0},
            {"command": "db_writer.py", "stdout": "db updated", "stderr": "", "returncode": 0},
            {"command": "web_updater.py", "stdout": "web updated", "stderr": "", "returncode": 0},
        ]
        with (
            patch("briefings.views.run_manual_news_refresh", return_value=outputs),
            patch("briefings.views.call_command") as mocked_call_command,
            patch("briefings.views.export_editorial_overrides", return_value="test_overrides.json"),
        ):
            response = self.client.post(
                "/editorial/",
                {"action": "collect_and_refresh_public", "next": "/editorial/"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked_call_command.assert_called_once_with("sync_runtime_articles")
        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_PUBLISH, action="collect_and_refresh_public")
        self.assertEqual(log.actor, self.platform_admin)
        self.assertEqual(log.after_data["status"], "completed")
        self.assertEqual(len(log.after_data["outputs"]), 5)
        self.assertEqual(log.after_data["sync_runtime_articles"], "completed")

    def test_collect_and_refresh_public_handles_pipeline_lock_without_running(self) -> None:
        self.client.force_login(self.platform_admin)
        lock_snapshot = {
            "lock_path": str(Path(self.temp_dir.name) / "pipeline.lock"),
            "exists": True,
            "details": {"pid": 4321, "started_at": "2026-04-21T09:00:00+09:00"},
        }
        with (
            patch(
                "briefings.views.run_manual_news_refresh",
                side_effect=PipelineLockedError(lock_details=lock_snapshot),
            ),
            patch("briefings.views.export_editorial_overrides", return_value="test_overrides.json"),
            patch("briefings.views.call_command") as mocked_call_command,
        ):
            response = self.client.post(
                "/editorial/",
                {"action": "collect_and_refresh_public", "next": "/editorial/"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked_call_command.assert_not_called()
        self.assertContains(response, "이미 파이프라인 실행 중입니다.")
        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_PUBLISH, action="collect_and_refresh_public")
        self.assertEqual(log.after_data["status"], "blocked")
        self.assertEqual(log.after_data["lock_snapshot"]["details"]["pid"], 4321)

    def test_collect_and_refresh_public_logs_failures(self) -> None:
        self.client.force_login(self.platform_admin)
        error = subprocess.CalledProcessError(
            1,
            ["python", "rss_fetcher.py"],
            output="collected_articles=0",
            stderr="network timeout",
        )
        with (
            patch("briefings.views.run_manual_news_refresh", side_effect=error),
            patch("briefings.views.export_editorial_overrides", return_value="test_overrides.json"),
            patch("briefings.views.call_command") as mocked_call_command,
        ):
            response = self.client.post(
                "/editorial/",
                {"action": "collect_and_refresh_public", "next": "/editorial/"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked_call_command.assert_not_called()
        self.assertContains(response, "새 기사 수집과 공개 반영 중 오류가 발생했습니다.")
        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_PUBLISH, action="collect_and_refresh_public")
        self.assertEqual(log.after_data["status"], "failed")
        self.assertEqual(log.after_data["stderr"], "network timeout")

    def test_auto_update_settings_save_updates_json_and_creates_audit_log(self) -> None:
        self.client.force_login(self.platform_admin)
        auto_update_settings_path = Path(self.temp_dir.name) / "auto_update_settings.json"
        auto_update_settings_path.write_text(
            json.dumps(DEFAULT_AUTO_UPDATE_SETTINGS, ensure_ascii=False),
            encoding="utf-8",
        )

        with (
            patch("youth_info_platform.auto_update_config.AUTO_UPDATE_SETTINGS_PATH", auto_update_settings_path),
            patch("briefings.views.AUTO_UPDATE_SETTINGS_PATH", auto_update_settings_path),
        ):
            response = self.client.post(
                "/editorial/settings/",
                {
                    "action": "save_auto_update_settings",
                    "auto_update_enabled": "on",
                    "auto_update_interval_minutes": "12",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(auto_update_settings_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["interval_minutes"], 12)
        self.assertTrue(payload["skip_outbound_notifications"])

        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_PUBLISH, action="update_auto_update_settings")
        self.assertEqual(log.actor, self.platform_admin)
        self.assertTrue(log.after_data["enabled"])
        self.assertEqual(log.after_data["interval_minutes"], 12)

    def test_editorial_settings_shows_running_auto_update_state(self) -> None:
        self.client.force_login(self.platform_admin)
        now = timezone.now().replace(microsecond=0)
        settings = {
            **DEFAULT_AUTO_UPDATE_SETTINGS,
            "enabled": True,
            "interval_minutes": 10,
        }
        status = {
            "state": "checking",
            "updated_at": now.isoformat(),
            "last_checked_at": now.isoformat(),
            "last_published_at": now.isoformat(),
            "next_check_at": (now + timedelta(minutes=10)).isoformat(),
            "runner_pid": 2468,
        }
        with (
            patch("briefings.views.load_auto_update_settings", return_value=settings),
            patch("briefings.views.load_auto_update_status", return_value=status),
            patch("briefings.views._process_exists", return_value=True),
        ):
            response = self.client.get("/editorial/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "실행 중 · 기사 점검 중")
        self.assertContains(response, "2468")

    def test_editorial_settings_shows_runner_missing_state_when_enabled_but_stale(self) -> None:
        self.client.force_login(self.platform_admin)
        now = timezone.now().replace(microsecond=0)
        settings = {
            **DEFAULT_AUTO_UPDATE_SETTINGS,
            "enabled": True,
            "interval_minutes": 10,
        }
        status = {
            "state": "idle_no_change",
            "updated_at": (now - timedelta(minutes=45)).isoformat(),
            "last_checked_at": (now - timedelta(minutes=45)).isoformat(),
            "runner_pid": 1357,
            "last_error": "runner heartbeat missing",
        }
        with (
            patch("briefings.views.load_auto_update_settings", return_value=settings),
            patch("briefings.views.load_auto_update_status", return_value=status),
            patch("briefings.views._process_exists", return_value=False),
        ):
            response = self.client.get("/editorial/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "설정 ON / 러너 미실행")
        self.assertContains(response, r"public-site\scripts\start_auto_update.ps1")
        self.assertContains(response, "runner heartbeat missing")

    def test_history_view_lists_recent_logs_for_platform_admin(self) -> None:
        self.client.force_login(self.platform_admin)
        AdminAuditLog.objects.create(
            actor=self.platform_admin,
            scope=AdminAuditLog.SCOPE_EDITORIAL,
            action="update_article_editorial",
            target_key=self.article.article_key,
            summary="기사 운영 결정을 저장했습니다.",
        )

        response = self.client.get("/editorial/history/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "기사 운영 결정을 저장했습니다.")

    def test_analytics_collect_stores_page_view_event(self) -> None:
        payload = {
            "site_scope": "public",
            "visitor_id": "visitor-1",
            "session_id": "session-1",
            "page_path": "/news.html",
            "page_url": "https://example.com/news.html",
            "page_title": "청년 뉴스",
            "referrer": "https://search.naver.com/search.naver",
            "source_origin": "https://example.com",
        }
        response = self.client.post(
            "/analytics/collect/",
            data=json.dumps(payload),
            content_type="text/plain",
        )
        self.assertEqual(response.status_code, 204)
        event = PageViewEvent.objects.get()
        self.assertEqual(event.site_scope, PageViewEvent.SCOPE_PUBLIC)
        self.assertEqual(event.page_path, "/news.html")
        self.assertEqual(event.referrer_host, "search.naver.com")

    def test_analytics_dashboard_shows_counts(self) -> None:
        self.client.force_login(self.platform_admin)
        PageViewEvent.objects.create(
            site_scope=PageViewEvent.SCOPE_PUBLIC,
            visitor_id="visitor-1",
            session_id="session-1",
            page_path="/index.html",
            page_url="https://example.com/index.html",
            page_title="홈",
            referrer_host="",
        )
        PageViewEvent.objects.create(
            site_scope=PageViewEvent.SCOPE_PUBLIC,
            visitor_id="visitor-2",
            session_id="session-2",
            page_path="/news.html",
            page_url="https://example.com/news.html",
            page_title="뉴스",
            referrer_host="google.com",
        )

        response = self.client.get("/editorial/analytics/?scope=public")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "최근 7일 방문자")
        self.assertContains(response, "/news.html")


class StaffProfileAdminTests(TestCase):
    def test_staff_profile_admin_save_creates_role_audit_log(self) -> None:
        user_model = get_user_model()
        actor = user_model.objects.create_superuser(username="root", password="pw123456789")
        managed_user = user_model.objects.create_user(username="manager", password="pw123456789")
        profile = managed_user.staff_profile
        profile.role = StaffProfile.ROLE_PLATFORM_ADMIN

        request = RequestFactory().post("/admin/briefings/staffprofile/")
        request.user = actor
        model_admin = StaffProfileAdmin(StaffProfile, django_admin.site)
        model_admin.save_model(request, profile, Mock(changed_data=["role"]), change=True)

        log = AdminAuditLog.objects.get(scope=AdminAuditLog.SCOPE_ROLE)
        self.assertEqual(log.actor, actor)
        self.assertEqual(log.target_key, str(managed_user.id))
        self.assertEqual(log.after_data["role"], StaffProfile.ROLE_PLATFORM_ADMIN)


class UserSeparationTests(TestCase):
    def test_saved_articles_are_scoped_per_user(self) -> None:
        user_model = get_user_model()
        first_user = user_model.objects.create_user(username="alpha", password="pw123456789")
        second_user = user_model.objects.create_user(username="beta", password="pw123456789")
        article = SyncedArticle.objects.create(article_key="article-1", title="기사")

        article.saved_by.create(user=first_user)

        self.assertEqual(first_user.saved_articles.count(), 1)
        self.assertEqual(second_user.saved_articles.count(), 0)
