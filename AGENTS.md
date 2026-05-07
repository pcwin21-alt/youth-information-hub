# Youth Info Platform Orchestrator

> 공통 운영 기준: 이 문서는 `C:\★_VIBE CODING\CODEX.md`의 공통 원칙을 따른다. 더 구체적인 하위 지침이 있으면 하위 지침을 우선한다.

이 저장소의 기본 실행 흐름은 아래와 같습니다.

1. `collect-news`가 기사 원본을 수집한다.
2. `dedup-filter`가 중복 제거와 기본 필터링을 수행한다.
3. `content-curator`가 분류, 선별, 요약을 수행한다.
4. `publish`가 DB 저장, 웹 갱신, 메시지 발송을 처리한다.

현재 MVP에서는 Step 3이 규칙 기반 파이프라인으로 구현되어 있으며, 이후 LLM 연동으로 대체할 수 있도록 입출력 JSON 형식을 고정한다.

