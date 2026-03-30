# Lightsail 기준 스테이징 배포안

## 1. 왜 Lightsail인가

현재 프로젝트는 `정적 웹 + SQLite + 정시 배치` 구조다.
즉, 복잡한 컨테이너 오케스트레이션보다 `항상 켜진 소형 VPS`가 더 잘 맞는다.

Lightsail 기준으로 보면 장점은 다음과 같다.

- VM 개념이 단순하다.
- Ubuntu 기반으로 바로 운영 가능하다.
- systemd timer + nginx + Python 조합이 자연스럽다.
- 현재 레포 구조를 크게 바꾸지 않아도 된다.

## 2. 권장 사용 방식

### 2.1 1차 목표

- 메인 도메인 전환 전 `staging` 서브도메인으로 먼저 올린다.
- 최소 3일 이상 자동 배치 관찰
- 홈/정책/허브 품질 확인 후 운영 공개

### 2.2 권장 인스턴스 성격

- Ubuntu LTS
- 소형 인스턴스부터 시작
- 디스크는 로그와 SQLite를 고려해 여유 있게

## 3. 배포 순서

1. Lightsail 인스턴스 생성
2. 고정 IP 연결
3. 보안 그룹/방화벽에서 80, 443, 22 허용
4. `staging` 서브도메인을 인스턴스로 연결
5. 이 레포를 서버에 clone
6. `deploy/lightsail/bootstrap-staging.sh` 실행
7. 자동 배치 3회 이상 관찰
8. 자동 백업 타이머 동작 확인
9. HTTPS 적용
10. 공개 여부 결정

## 4. 부트스트랩 사용법

먼저 로컬에서 입력값 준비도를 확인한다.

```powershell
python scripts/deployment_readiness.py
```

그 다음 `deploy/lightsail/staging-config.env.example`를
`deploy/lightsail/staging-config.env`로 복사해 실제 값으로 채운다.

서버에서 설정 파일 기반으로 한 번에 실행하려면 다음처럼 진행한다.

```bash
cp deploy/lightsail/staging-config.env.example deploy/lightsail/staging-config.env
nano deploy/lightsail/staging-config.env
bash deploy/lightsail/run-staging-setup.sh
```

환경변수를 직접 export해서 실행하려면 아래 방식도 가능하다.

```bash
export REPO_URL="git@github.com:YOUR-ORG/YOUR-REPO.git"
export REPO_REF="main"
export DOMAIN="staging.example.com"
bash deploy/lightsail/bootstrap-staging.sh
```

배포 후 코드 업데이트는 서버에서 아래처럼 진행한다.

```bash
REPO_REF="main" RUN_PIPELINE_AFTER_UPDATE="1" bash deploy/linux/update_app.sh
```

HTTPS는 아래 스크립트로 적용할 수 있다.

```bash
DOMAIN="staging.example.com" CERTBOT_EMAIL="ops@example.com" bash deploy/lightsail/enable-https.sh
```

## 5. 배포 후 확인

```bash
systemctl status youth-together-pipeline.timer
systemctl status youth-together-pipeline.service
systemctl status youth-together-backup.timer
journalctl -u youth-together-pipeline.service -n 100 --no-pager
cat /opt/youth-together/output/pipeline_status.json
bash /opt/youth-together/deploy/linux/check_deployment.sh
```

수동 백업이 필요하면 다음 명령으로 바로 실행할 수 있다.

```bash
bash /opt/youth-together/deploy/linux/backup_state.sh
```

배포용 서비스 환경변수는 `deploy/env/youth-together.env.example`를 참고해
`/etc/youth-together.env`에 둔다.

## 6. 운영 공개 전환

### 6.1 staging에서 확인할 것

- 09:00 / 15:00 / 21:00 배치 성공
- 정책 페이지 최신 반영
- 활동가 허브 분류 확인
- 허브/정책/뉴스 페이지 모바일 확인

### 6.2 공개 전환 방식

- `staging.example.com`에서 충분히 검증
- 이후 `www.example.com` 또는 메인 도메인 DNS 전환
- 공개 직전 한 번 더 수동 배치 실행

## 7. 주의점

- 이 프로젝트는 아직 SQLite 기반이라, 동시 쓰기 부하가 큰 구조에는 맞지 않는다.
- v1에서는 단일 VM에 적합하지만, 트래픽이 커지면 DB와 웹을 분리해야 한다.
- 백업은 반드시 `articles.db`, `pipeline_status.json`, `scheduler_logs/` 기준으로 잡는다.
