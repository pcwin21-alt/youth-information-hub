# Always-On Deployment Design

이 문서는 GitHub Pages가 아니라 상시 켜진 VM에서 공개 사이트를 직접 갱신하고 서빙하는 v1 운영안을 설명한다.

## Current Recommendation

- 단일 Linux VM에서 `systemd timer + Python pipeline + nginx`로 운영한다.
- 저장소 checkout 기준 경로 예시는 `/opt/youth-together`다.
- 공개 사이트 원본은 `public-site/web/`, nginx 문서 루트는 운영 환경에 맞춰 이 경로를 바라보게 한다.
- 상태와 중간 산출물은 `runtime/pipeline/`, SQLite는 `runtime/db/`, 로그는 `runtime/logs/`에 둔다.

## Runtime Flow

```text
systemd timer
  -> public-site/deploy/linux/run_pipeline.sh
  -> public-site/scripts/cron_runner.py
  -> runtime/pipeline/*.json
  -> runtime/db/articles.db
  -> public-site/web/*.html
  -> nginx static serving
```

## Repository Paths

- Pipeline runner: `public-site/scripts/cron_runner.py`
- Status report: `public-site/scripts/status_report.py`
- Deployment readiness check: `public-site/scripts/deployment_readiness.py`
- Linux deployment scripts: `public-site/deploy/linux/`
- Lightsail bootstrap scripts: `public-site/deploy/lightsail/`
- systemd templates: `public-site/deploy/systemd/`
- nginx template: `public-site/deploy/nginx/youth-together.conf`
- env template: `public-site/deploy/env/youth-together.env.example`

## Server Setup Checklist

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
sudo mkdir -p /opt/youth-together
sudo chown -R "$USER":"$USER" /opt/youth-together
git clone <repo-url> /opt/youth-together
cd /opt/youth-together
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./shared -e ./public-site
chmod +x public-site/deploy/linux/*.sh
```

## systemd Registration

```bash
sudo cp public-site/deploy/systemd/youth-together-pipeline.service /etc/systemd/system/
sudo cp public-site/deploy/systemd/youth-together-pipeline.timer /etc/systemd/system/
sudo cp public-site/deploy/systemd/youth-together-backup.service /etc/systemd/system/
sudo cp public-site/deploy/systemd/youth-together-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now youth-together-pipeline.timer
sudo systemctl enable --now youth-together-backup.timer
sudo systemctl start youth-together-pipeline.service
```

서비스 템플릿의 `User`, `Group`, `WorkingDirectory`, `ExecStart`는 실제 서버 경로와 계정에 맞춘다.

## nginx Registration

```bash
sudo cp public-site/deploy/nginx/youth-together.conf /etc/nginx/sites-available/youth-together.conf
sudo ln -s /etc/nginx/sites-available/youth-together.conf /etc/nginx/sites-enabled/youth-together.conf
sudo nginx -t
sudo systemctl reload nginx
```

## Monitoring

- `runtime/pipeline/pipeline_status.json`
- `runtime/pipeline/pipeline_feedback_report.json`
- `runtime/pipeline/pipeline_feedback_report.md`
- `runtime/logs/`
- `systemctl status youth-together-pipeline.service`
- `systemctl status youth-together-pipeline.timer`
- `bash public-site/deploy/linux/check_deployment.sh`
- `python public-site/scripts/status_report.py`
- `python public-site/scripts/pipeline_feedback.py --run-source-healthcheck`

## Backup

- 기본 백업 대상: `runtime/db/articles.db`, `runtime/pipeline/pipeline_status.json`, 주요 설정 파일
- 백업 스크립트: `public-site/deploy/linux/backup_state.sh`
- 백업 타이머: `public-site/deploy/systemd/youth-together-backup.timer`

## Important Distinctions

- GitHub Pages 배포와 VM 상시 배포는 별개 경로다.
- 로컬 자동 반영은 노트북 러너 기반 best effort이고, VM 운영은 systemd timer 기반이다.
- `public-site/web/`와 `public-site/dist/`를 혼동하지 않는다. VM은 보통 `public-site/web/`를 서빙하고, Pages는 `public-site/dist/`를 업로드한다.
