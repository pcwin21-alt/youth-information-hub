# 2026-10-18 홈페이지 연구소 로고 교체

## 요청 및 최소 계약

- 요청: 청년정책 홈페이지에 적재적소 연구소 최신 로고 반영.
- 대상: public-site의 공통 헤더·하단·기존 파비콘 참조. 기사·분류·수집·발송·구독 정책은 변경하지 않는다.
- 가설/검증: 공식 원본을 같은 로컬 자산으로 연결하면 상단·하단에서 동일 기관을 식별하고 정기 재생성 후에도 유지된다.
- 입력 → 행동 → 수락 증거 → 출력: 공식 사이트에 노출된 파일 확인 → 원본 바이트 보관·생성기 교체 → 해시/단위 검사/데스크톱·모바일 렌더/Pages 성공 → 배포된 홈페이지.
- 완료 기준: 공식 원본과 SHA256 일치, 생성기/생성물 일치, 비율 유지, 링크·키보드·반응형 확인, 기사 아카이브 불변.
- 상태: complete. 권한은 사용자의 홈페이지 로고 갱신 요청 범위에 한정한다.

## 원본 근거

- 공식 홈페이지: https://rightpolicy.co.kr/
- 실제 하단 로고 URL: https://rightpolicy.co.kr/file/388489206
- 관찰: PNG 845 × 325, 청록/남색 심벌과 국문·영문 기관명.
- 원본 SHA256: 7fe3436037ec2c501c493c9eff05174950275663f0902afcea3413a343cd2db5
- 보관: public-site/web/assets/branding/right-policy-institute-logo-20261018.png
- 다른 폴더의 오늘자 SVG/PNG 후보는 단색 파생본이었다. 수정일만으로 최신 정본으로 채택하지 않고 현재 공식 사이트의 컬러 원본을 선택했다. 이미지 재생성·보정 없이 그대로 사용한다.

## Harness routing

- always: canonical identity_harness AGENTS/00_START_HERE/Skill router/Brain.
- active: Project Execution, identity-harness-autopilot, codex-delivery-loop, publish, Source, Eval Global 및 관련 디자인·반응형 Gate, KRDS typography.
- reference: 기존 공통 CSS의 본문·헤딩·메타/조작 역할. 이번 작업은 타이포·색·정보구조를 재설계하지 않는다.
- excluded: 수집/큐레이션 변경, 새 서비스 기획, 이미지 생성, 외부 계정 설정, 다른 연구소 홈페이지 수정.
- inventory: 런타임 목록과 실제 SKILL.md, dashboard/harness_index.json 대조. 색인의 workspace_root는 옛 경로이나 활성 파일은 canonical identity_harness의 실제 파일을 사용한다.
- 절차: 공식 파일 확인 → 좁은 변경을 origin/main 관리 worktree에서 구현 → 단위/산출물/브라우저 검사 → 사전 생성 배포 → 실제 사이트 확인.
- Skill 영향: publish/KRDS의 생성기 정본 원칙에 따라 HTML만 교체하지 않고 생성기에도 변경. delivery loop에 따라 모바일/데스크톱과 링크를 검수한다.
- 원천: 공식 사이트 로고는 사실 근거, 타 폴더 파생본은 참고, AI 생성 로고는 제외.
- 기존 사용자의 dirty 파일은 보존. 분리 worktree의 범위 변경만 배포한다.

## 검증 및 배포

- 단위 검사: 분리 worktree 전체 212개 통과, 로고/홈 관련 61개 통과. 주 작업 폴더의 로고 전용 4개도 통과.
- 공식 PNG 원본 SHA256 고정 검사, 공통 헤더/하단 동일 자산 사용, 파일 부재 시 구 운영사 로고 대체 금지, 파비콘 참조 검사 통과.
- `web_updater.py --archive-only --skip-thumbnail-fetch` 완료. 뉴스 2,978건 유지. 기사는 새로 수집하지 않았다.
- `verify_site_artifacts.py` 통과. 여기서 출력된 pipeline state는 기존 저장 상태이며 이번 로고 작업의 새 수집 성공을 뜻하지 않는다.
- 브라우저: 실제 1280px 데스크톱 상단, 390px 모바일 하단 로고 로딩/비율/가로 넘침 없음 확인. 하단 링크의 키보드 탐색 확인. 타이포/정보구조는 기존 것 유지.
- 배포 대상 기사 아카이브 SHA256: cee2be908e2cbae0cf05b036e6d2a2a4245223d822fbb3d85d54aead17d89933. 생성 과정에서 변경하지 않음.
- 주 작업 폴더와 분리 worktree의 아카이브는 원래 다르므로 서로 덮어쓰지 않았다.
- 정적 HTML의 이전 체크인본은 9월 데이터이고 현재 공개 사이트는 10월 아카이브 렌더다. 구형 체크인 HTML을 배포하지 않도록 생성기·로고·검사만 커밋하고 기존 `render_from_archive` 배포 모드로 최신 공개 아카이브를 렌더한다.
- 배포: commit 55bb4545e3b034c7670ec3d9cb10d113ef3279d4, Pages 실행 39097026617 build/deploy 모두 success.
- 실제 홈/뉴스 HTTP 200. 홈의 상단·하단 새 로고 URL 및 13:11 수집 시각 유지 확인. 실제 로고 이미지 SHA256은 공식 원본과 일치.
- 공개 사이트 브라우저에서 새 하단 로고 DOM/이미지 로딩 확인. 데스크톱/모바일 상세 레이아웃은 동일 생성물의 로컬 미리보기에서 확인.
- Eval: Global Gate 및 이번 범위의 로고 출처·생성기 지속성·비율/좁은 화면/링크 검사 통과. 전체 서비스의 별도 200% 확대·본문 재검수는 로고 교체 범위 밖이며 수행하지 않았다.
- 정리: 기존 로고 파일과 사용자 변경은 삭제하지 않는다. 신규 의존성·자동화·외부 발송 없음.

