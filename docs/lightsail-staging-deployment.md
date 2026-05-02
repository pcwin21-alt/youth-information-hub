# Lightsail Staging Deployment

Lightsail은 현재 구조인 `정적 HTML + SQLite + Python batch`를 크게 바꾸지 않고 staging VM을 만들기 좋은 선택지다.

## Goal

- production 전환 전에 `staging` 서브도메인에서 자동 배치와 정적 서빙을 검증한다.
- 최소 3회 이상 자동 배치 성공을 확인한 뒤 공개 전환을 결정한다.

## Preparation

로컬에서 배포 입력값을 먼저 점검한다.

```powershell
python public-site\scripts\deployment_readiness.py
```

Lightsail 인스턴스에는 다음이 필요하다.

- Ubuntu LTS
- 고정 IP
- 방화벽 22, 80, 443 허용
- staging 서브도메인 DNS 연결

## Bootstrap

서버에서 저장소를 받을 준비를 한 뒤 아래 중 하나로 진행한다.

환경 파일 기반:

```bash
cd /opt/youth-together
cp public-site/deploy/lightsail/staging-config.env.example public-site/deploy/lightsail/staging-config.env
nano public-site/deploy/lightsail/staging-config.env
bash public-site/deploy/lightsail/run-staging-setup.sh
```

환경 변수 직접 지정:

```bash
cd /opt/youth-together
export REPO_URL="git@github.com:YOUR-ORG/YOUR-REPO.git"
export REPO_REF="main"
export DOMAIN="staging.example.com"
bash public-site/deploy/lightsail/bootstrap-staging.sh
```

## Update And HTTPS

```bash
cd /opt/youth-together
REPO_REF="main" RUN_PIPELINE_AFTER_UPDATE="1" bash public-site/deploy/linux/update_app.sh
DOMAIN="staging.example.com" CERTBOT_EMAIL="ops@example.com" bash public-site/deploy/lightsail/enable-https.sh
```

## Verification

```bash
systemctl status youth-together-pipeline.timer
systemctl status youth-together-pipeline.service
systemctl status youth-together-backup.timer
journalctl -u youth-together-pipeline.service -n 100 --no-pager
cat /opt/youth-together/runtime/pipeline/pipeline_status.json
bash /opt/youth-together/public-site/deploy/linux/check_deployment.sh
```

수동 백업:

```bash
bash /opt/youth-together/public-site/deploy/linux/backup_state.sh
```

## Promotion Checklist

- 09:00 / 15:00 / 21:00 KST 배치가 성공한다.
- `public-site/web/index.html`과 주요 페이지가 nginx로 정상 노출된다.
- `runtime/pipeline/pipeline_status.json`에 최근 성공 시각이 기록된다.
- 자동 백업이 생성된다.
- HTTPS가 정상 적용된다.
- 공개 전환 직전 수동 배치를 1회 실행하고 결과를 확인한다.

## Notes

- 배포용 환경변수 예시는 `public-site/deploy/env/youth-together.env.example`를 기준으로 한다.
- SQLite 기반 v1에서는 단일 VM이 적합하다. 트래픽이나 동시 쓰기가 커지면 DB 분리를 별도 계획으로 진행한다.
