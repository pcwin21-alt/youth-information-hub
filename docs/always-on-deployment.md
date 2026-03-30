# 항상 켜짐형 배포 설계

## 1. 목표

이 프로젝트는 더 이상 `내 PC가 켜져 있을 때만` 동작하는 로컬 배치가 아니라,
`매일 09:00 / 15:00 / 21:00 (Asia/Seoul)`에 자동으로 크롤링과 발행이 실행되는
항상 켜짐형 운영 구조가 필요하다.

현재 코드 구조는 다음 성질을 가진다.

- 크롤링/분류/발행 파이프라인은 Python 배치로 닫혀 있다.
- 최종 웹 결과물은 `web/` 디렉터리의 정적 HTML이다.
- 데이터 저장은 `db/articles.db` SQLite 기반이다.
- 상태 확인은 `output/pipeline_status.json`으로 가능하다.

즉, v1 기준 최적 구조는 `항상 켜져 있는 Linux VM 한 대`에서
배치와 정적 사이트를 함께 운영하는 방식이다.

## 2. 권장 아키텍처

### 2.1 v1 권장안: 단일 VM 운영

```text
systemd timer (09:00 / 15:00 / 21:00 KST)
        |
        v
run_pipeline.sh
        |
        v
cron_runner.py
        |
        +--> output/*.json
        +--> db/articles.db
        +--> web/*.html
        |
        v
nginx가 web/ 를 정적 서빙
```

### 2.2 왜 이 구조가 맞는가

- 현재 앱은 API 서버보다 `정적 발행물` 중심이다.
- SQLite를 그대로 유지할 수 있어 초기 마이그레이션 비용이 낮다.
- systemd timer는 고정 시각 배치에 적합하다.
- nginx로 바로 서빙할 수 있어 배포 복잡도가 낮다.
- 이후 필요할 때만 DB를 PostgreSQL로 옮기면 된다.

## 3. 인프라 구성

### 3.1 컴퓨트

- 소형 Linux VM 1대
- Ubuntu LTS 권장
- 리전은 한국 또는 사용자와 가까운 리전 우선
- 디스크는 SQLite와 로그 보관을 고려해 여유 있게 설정

### 3.2 런타임

- Python 3.11+
- 프로젝트 checkout 경로 예시: `/opt/youth-together`
- 가상환경 경로 예시: `/opt/youth-together/.venv`

### 3.3 웹 서빙

- nginx가 `web/` 정적 파일 서빙
- 필요 시 `pipeline_status.json`만 별도 노출
- HTTPS는 reverse proxy 또는 CDN에서 종료

### 3.4 저장소

- `db/articles.db`: v1 지속 사용
- `output/`: 상태 파일, 중간 산출물, 로그
- `web/`: 정적 최종 산출물

## 4. 스케줄링 설계

### 4.1 실행 시각

- 매일 `09:00`
- 매일 `15:00`
- 매일 `21:00`
- 기준 시간대: `Asia/Seoul`

### 4.2 실행 도구

- Linux: `systemd service + systemd timer`
- `Persistent=true`를 사용해 서버가 꺼져 있던 동안 놓친 실행을 부팅 후 보완
- 중복 실행 방지는 파이프라인 내부 lock + systemd 단일 실행 원칙으로 보완

### 4.3 실행 흐름

1. timer가 service 호출
2. `run_pipeline.sh`가 가상환경과 로그 경로를 정리
3. `cron_runner.py` 실행
4. `pipeline.lock`이 있으면 중복 실행 차단
5. 실행 결과를 `output/pipeline_status.json`과 로그 파일에 기록
6. nginx가 최신 `web/` 결과를 그대로 노출

## 5. 운영 파일 구조

```text
/opt/youth-together
├── .venv/
├── .claude/
├── db/
├── docs/
├── output/
│   ├── pipeline_status.json
│   ├── scheduler_logs/
│   └── ...
├── scripts/
├── src/
├── web/
└── deploy/
```

## 6. 배포 템플릿

이 저장소에는 다음 템플릿을 함께 둔다.

- `deploy/linux/run_pipeline.sh`
- `deploy/linux/update_app.sh`
- `deploy/linux/backup_state.sh`
- `deploy/linux/check_deployment.sh`
- `deploy/lightsail/staging-config.env.example`
- `deploy/lightsail/run-staging-setup.sh`
- `deploy/systemd/youth-together-pipeline.service`
- `deploy/systemd/youth-together-pipeline.timer`
- `deploy/systemd/youth-together-backup.service`
- `deploy/systemd/youth-together-backup.timer`
- `deploy/nginx/youth-together.conf`

즉, VM만 준비되면 현재 레포 기준으로 거의 그대로 옮길 수 있어야 한다.

## 7. 비밀값과 환경변수

환경변수 또는 별도 env 파일로 관리한다.

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `SLACK_WEBHOOK_URL`
- 추후 API 키 및 외부 서비스 자격증명

권장 위치:

- `/etc/youth-together.env`

서비스는 이 파일을 `EnvironmentFile`로 읽는다.

## 8. 모니터링 설계

### 8.1 기본 모니터링

- `output/pipeline_status.json`
- `output/scheduler_logs/*.log`
- `systemctl status youth-together-pipeline.service`
- `systemctl status youth-together-pipeline.timer`

### 8.2 추천 운영 체크

- 마지막 성공 시각
- 다음 실행 시각
- 마지막 종료 코드
- 수집 기사 수 / 필터 후 기사 수 / 최종 발행 수
- 최근 7일 연속 실패 여부

### 8.3 향후 확장

- Slack 실패 알림
- 외부 heartbeat 서비스 연동
- `/healthz` 또는 상태 JSON 공개

## 9. 백업 설계

v1에서는 SQLite 백업만 해도 충분하다.

- 일 1회 `articles.db` 백업
- 최근 7~14일 로테이션
- 선택적으로 object storage 업로드
- 현재 템플릿 기준 자동 백업 시각은 `02:30 (Asia/Seoul)`

백업 대상:

- `db/articles.db`
- `output/pipeline_status.json`
- 중요 설정 파일

## 10. 장애 대응

### 10.1 중복 실행

- 파이프라인 내부 `pipeline.lock`으로 차단

### 10.2 비정상 종료

- lock 파일이 너무 오래되면 stale 처리
- 다음 배치에서 자동 회복 시도

### 10.3 서버 재부팅

- `systemd timer Persistent=true`로 놓친 실행 보완

### 10.4 크롤링 실패

- 일부 소스 실패는 스킵
- 전체 실패는 상태 파일과 로그로 남김
- 추후 Slack/Telegram 에스컬레이션 연동

## 11. v2 확장 방향

### 11.1 구조 분리

트래픽이나 데이터가 커지면 다음처럼 분리한다.

- 배치 VM/worker
- 정적 사이트 CDN/정적 호스팅
- DB 분리(PostgreSQL)

### 11.2 허브/커뮤니티 확장

- 활동가 허브용 별도 테이블
- 운영자 주제 설정형 익명 토론 저장소
- 커뮤니티 결과 요약 발행 파이프라인

## 12. 권장 결론

현 시점 최적안은 다음이다.

1. 항상 켜져 있는 Linux VM 1대 준비
2. 이 저장소를 VM에 배포
3. `systemd timer`로 09:00 / 15:00 / 21:00 실행
4. nginx가 `web/`를 정적 서빙
5. 상태 JSON, 로그, SQLite 백업을 같이 운영

이 구조가 현재 MVP와 가장 잘 맞고,
추후 `worker + static hosting + managed DB`로 확장하기도 쉽다.

### 12.1 현재 추천 공급자

현재 기준으로는 `AWS Lightsail의 Ubuntu 인스턴스`처럼 단순한 VPS형 환경이 가장 잘 맞는다.

- 이유 1: 현재 레포가 정적 웹 + SQLite + Python 배치라서 VM이 단순하다.
- 이유 2: systemd timer와 nginx를 그대로 사용할 수 있다.
- 이유 3: 나중에 staging -> production 전환도 쉽다.

Lightsail 기준의 구체적 스테이징 배포안은 `docs/lightsail-staging-deployment.md`를 따른다.
HTTPS 적용은 `deploy/lightsail/enable-https.sh` 템플릿을 기준으로 진행한다.
배포 입력값 점검은 `python scripts/deployment_readiness.py`로 먼저 확인한다.

## 13. 서버 셋업 체크리스트

### 13.1 초기 설치

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

### 13.2 코드 배치

```bash
sudo mkdir -p /opt/youth-together
sudo chown -R "$USER":"$USER" /opt/youth-together
git clone <repo-url> /opt/youth-together
cd /opt/youth-together
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
chmod +x deploy/linux/run_pipeline.sh
chmod +x deploy/linux/*.sh
```

### 13.3 환경변수

```bash
sudo cp /dev/null /etc/youth-together.env
sudo nano /etc/youth-together.env
```

예시:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SLACK_WEBHOOK_URL=...
```

### 13.4 systemd 등록

```bash
sudo cp deploy/systemd/youth-together-pipeline.service /etc/systemd/system/
sudo cp deploy/systemd/youth-together-pipeline.timer /etc/systemd/system/
sudo cp deploy/systemd/youth-together-backup.service /etc/systemd/system/
sudo cp deploy/systemd/youth-together-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now youth-together-pipeline.timer
sudo systemctl enable --now youth-together-backup.timer
sudo systemctl start youth-together-pipeline.service
```

주의:

- service 파일의 `User`, `Group`, `WorkingDirectory`는 실제 서버 계정/경로에 맞게 바꿔야 한다.
- `ExecStart` 경로도 실제 배포 경로에 맞게 치환해야 한다.
- 서버 시간대는 `Asia/Seoul`로 맞추는 편이 안전하다.

### 13.5 nginx 등록

```bash
sudo cp deploy/nginx/youth-together.conf /etc/nginx/sites-available/youth-together.conf
sudo ln -s /etc/nginx/sites-available/youth-together.conf /etc/nginx/sites-enabled/youth-together.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 13.6 운영 확인

```bash
systemctl status youth-together-pipeline.timer
systemctl status youth-together-pipeline.service
bash deploy/linux/check_deployment.sh
python scripts/status_report.py
```
