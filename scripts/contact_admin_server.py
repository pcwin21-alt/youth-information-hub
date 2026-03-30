from __future__ import annotations

import argparse
import base64
import html
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.contact_config import (
    CONTACT_SETTINGS_PATH,
    load_admin_settings,
    load_contact_settings,
    save_contact_settings,
    verify_password,
)
from youth_info_platform.io_utils import write_json


WEB_UPDATER_PATH = ROOT / ".claude" / "skills" / "publish" / "scripts" / "web_updater.py"
ADMIN_USERNAME = "admin"


def render_admin_page(
    contact_settings: dict[str, str],
    *,
    message: str = "",
    error: str = "",
    public_base_url: str = "http://127.0.0.1:8765",
) -> str:
    def value(key: str) -> str:
        return html.escape(contact_settings.get(key, ""))

    banner = ""
    if message:
        banner = f'<div class="banner success">{html.escape(message)}</div>'
    elif error:
        banner = f'<div class="banner error">{html.escape(error)}</div>'

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>연락 정보 관리자</title>
  <style>
    :root {{
      --bg: #eef3f8;
      --panel: #ffffff;
      --line: rgba(23, 33, 49, 0.12);
      --text: #172131;
      --muted: #657286;
      --accent: #1f6f5f;
      --danger: #a63d40;
      --shadow: 0 18px 32px rgba(23, 33, 49, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 32px 16px;
      background: linear-gradient(180deg, #f4f7fb 0%, var(--bg) 100%);
      color: var(--text);
      font-family: "Noto Sans KR", sans-serif;
    }}
    .shell {{
      max-width: 860px;
      margin: 0 auto;
      display: grid;
      gap: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    h1, h2 {{ margin: 0; letter-spacing: -0.03em; }}
    h1 {{ font-size: 1.9rem; }}
    h2 {{ font-size: 1.1rem; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.6; }}
    .intro {{ display: grid; gap: 10px; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      margin-top: 6px;
      font-size: 0.84rem;
      color: var(--muted);
    }}
    .banner {{
      border-radius: 16px;
      padding: 12px 14px;
      font-size: 0.94rem;
      font-weight: 700;
    }}
    .banner.success {{
      background: rgba(31, 111, 95, 0.12);
      color: var(--accent);
    }}
    .banner.error {{
      background: rgba(166, 61, 64, 0.12);
      color: var(--danger);
    }}
    form {{
      display: grid;
      gap: 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }}
    label {{
      display: grid;
      gap: 8px;
      font-size: 0.92rem;
      font-weight: 700;
    }}
    input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      font: inherit;
      color: var(--text);
      background: #fbfcfe;
    }}
    textarea {{
      min-height: 110px;
      resize: vertical;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    button, .button-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 46px;
      padding: 0 16px;
      border-radius: 14px;
      border: 0;
      background: #1c2736;
      color: white;
      font: inherit;
      font-weight: 800;
      text-decoration: none;
      cursor: pointer;
    }}
    .button-link.secondary {{
      background: transparent;
      color: var(--text);
      border: 1px solid var(--line);
    }}
    .help {{
      font-size: 0.84rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="panel intro">
      <h1>연락 정보 관리자</h1>
      <p>여기서 저장한 내용은 홈 하단 연락 블록과 연락 페이지에 함께 반영됩니다.</p>
      <div class="meta">
        <span>최근 저장 {value("updated_at") or "-"}</span>
        <span>공개 페이지 <a href="{html.escape(public_base_url)}/contact.html" target="_blank" rel="noreferrer">열기</a></span>
      </div>
    </section>
    <section class="panel">
      {banner}
      <form method="post" action="/admin/contact">
        <div class="grid">
          <label>
            단체명
            <input type="text" name="organization_name" value="{value("organization_name")}" maxlength="120" required>
          </label>
          <label>
            저작권 표기
            <input type="text" name="copyright_text" value="{value("copyright_text")}" maxlength="80" required>
          </label>
          <label>
            버전
            <input type="text" name="version_text" value="{value("version_text")}" maxlength="80" required>
          </label>
          <label>
            이메일
            <input type="email" name="email" value="{value("email")}" maxlength="160" required>
          </label>
        </div>
        <label>
          안내 문구 1
          <textarea name="extra_line_1" maxlength="180" required>{value("extra_line_1")}</textarea>
        </label>
        <label>
          안내 문구 2
          <textarea name="extra_line_2" maxlength="180">{value("extra_line_2")}</textarea>
        </label>
        <div class="actions">
          <button type="submit">저장하고 다시 생성</button>
          <a class="button-link secondary" href="{html.escape(public_base_url)}/" target="_blank" rel="noreferrer">홈 보기</a>
          <a class="button-link secondary" href="{html.escape(public_base_url)}/contact.html" target="_blank" rel="noreferrer">연락 페이지 보기</a>
        </div>
        <p class="help">비밀번호는 브라우저 기본 인증으로 보호됩니다. 저장 후 정적 HTML이 즉시 다시 생성됩니다.</p>
      </form>
    </section>
  </div>
</body>
</html>
"""


def render_setup_page() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>관리자 비밀번호 설정 필요</title>
  <style>
    body { margin: 0; padding: 32px 16px; font-family: "Noto Sans KR", sans-serif; background: #eef3f8; color: #172131; }
    .panel { max-width: 680px; margin: 0 auto; padding: 24px; background: white; border-radius: 24px; border: 1px solid rgba(23, 33, 49, 0.12); }
    code { background: #f5f7fa; padding: 2px 6px; border-radius: 8px; }
  </style>
</head>
<body>
  <div class="panel">
    <h1>관리자 비밀번호 설정이 필요합니다.</h1>
    <p><code>python scripts/set_contact_admin_password.py</code>를 한 번 실행한 뒤 다시 접속해 주세요.</p>
  </div>
</body>
</html>
"""


class ContactAdminHandler(BaseHTTPRequestHandler):
    public_base_url = "http://127.0.0.1:8765"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/admin/contact"}:
            if not self._require_auth():
                return
            params = parse_qs(parsed.query)
            message = "저장되었습니다." if params.get("saved") else ""
            error = params.get("error", [""])[0]
            self._send_html(
                render_admin_page(
                    load_contact_settings(),
                    message=message,
                    error=error,
                    public_base_url=self.public_base_url,
                )
            )
            return

        if self.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/admin/contact":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._require_auth():
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        form = {key: values[0].strip() for key, values in parse_qs(raw_body, keep_blank_values=True).items()}
        previous_settings = load_contact_settings()

        try:
            save_contact_settings(form)
            self._regenerate_public_pages()
        except Exception as exc:  # noqa: BLE001
            write_json(CONTACT_SETTINGS_PATH, previous_settings)
            self._send_html(
                render_admin_page(
                    {**previous_settings, **form},
                    error=str(exc),
                    public_base_url=self.public_base_url,
                ),
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/admin/contact?saved=1")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_html(self, content: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _require_auth(self) -> bool:
        admin_settings = load_admin_settings()
        if not admin_settings:
            self._send_html(render_setup_page(), status=HTTPStatus.SERVICE_UNAVAILABLE)
            return False

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
                username, password = decoded.split(":", 1)
            except Exception:  # noqa: BLE001
                username = ""
                password = ""
            if username == ADMIN_USERNAME and verify_password(password, admin_settings):
                return True

        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Contact Admin"')
        self.end_headers()
        return False

    def _regenerate_public_pages(self) -> None:
        subprocess.run(
            [sys.executable, str(WEB_UPDATER_PATH)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--public-base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()

    ContactAdminHandler.public_base_url = args.public_base_url.rstrip("/")
    server = ThreadingHTTPServer((args.host, args.port), ContactAdminHandler)
    print(f"contact_admin_url=http://{args.host}:{args.port}/admin/contact")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
