# OpenClaw TODO Plugin -- Requirements Document

> **Version**: 3.0
> **Date**: 2026-02-24
> **Source PRD**: `openclaw_todo_plugin_prd.md` v1.2
> **Status**: Draft

---

## 1. Purpose

Slack DM 기반 TODO 관리 플러그인(OpenClaw TODO Plugin)의 기능/비기능 요구사항을 정의한다.
`/todo` 접두사 커맨드를 통해 LLM 호출 없이(비용 0) 결정적(deterministic) 동작하며,
SQLite3에 데이터를 저장하고, private/shared 프로젝트 워크플로를 지원한다.

---

## 2. Scope

### 2.1 In Scope (MVP / v1)

| Area | Details |
|------|---------|
| **커맨드 인터페이스** | `/todo add`, `list`, `board`, `move`, `done`, `drop`, `edit` |
| **프로젝트 관리** | `/todo project list`, `set-private`, `set-shared` |
| **LLM 바이패스** | manifest `command_prefix` + `bypass_llm` 등록으로 Gateway가 LLM 없이 직접 플러그인 호출 |
| **커맨드 접두사** | `/todo` 단일 접두사 |
| **저장소** | 단일 공유 SQLite3 파일, WAL 모드 |
| **입력 채널** | OpenClaw Slack 봇과의 DM (기본 경로) |
| **Due date 파싱** | `YYYY-MM-DD` 및 `MM-DD` (연도 생략 시 현재 연도 보정) |
| **Assignee 해석** | Slack `<@U...>` 멘션 기반; 다중 assignee 지원 |
| **가시성 모델** | Private (owner 전용) 및 Shared 프로젝트 |
| **스키마 마이그레이션** | `schema_version` 테이블; 첫 실행 시 DB 자동 생성 + `Inbox` 프로젝트 생성 |
| **감사 로그** | `events` 테이블에 actor, action, task, payload 기록 |
| **Bridge 정리** | bridge 서버의 `/todo` -> `/todo` 이중 변환 로직 제거 |

### 2.2 Out of Scope

- 자연어/LLM 기반 태스크 생성 (Phase 2)
- 채널/스레드 기반 사용 (앱 멘션 `@openclaw /todo ...`)
- 반복(recurring) 태스크
- 리마인더, 알림, 정기 요약(digest)
- 멀티 워크스페이스 연동 또는 교차 공유
- 웹 UI 또는 대시보드
- 태스크 첨부파일/파일 업로드
- 외부 프로젝트 관리 도구와의 실시간 동기화
- `todo:` 접두사 (레거시 접두사, `/todo`로 통일됨)
- 태스크 삭제 (물리 삭제; drop으로 논리 삭제만 지원)
- assignee append/remove (v1은 완전 교체만)

---

## 3. Assumptions

| # | Assumption |
|---|-----------|
| A1 | OpenClaw Gateway가 이미 배포되어 있고, DM 메시지를 플러그인으로 라우팅할 수 있다. |
| A2 | Gateway가 manifest의 `command_prefix` 매칭을 지원하여 LLM 바이패스가 동작한다. 미지원 시 LLM 라우팅으로 폴백(임시). |
| A3 | 각 Slack 사용자는 고유하고 안정적인 `user_id` (`U...` 형식)를 가진다. |
| A4 | 단일 SQLite3 파일이 예상 동시성(소~중규모 팀, ~50명)에 충분하다. |
| A5 | 서버 타임존은 `Asia/Seoul`이며, 날짜 보정에 사용된다. |
| A6 | Slack 봇이 DM 읽기/쓰기 권한(OAuth scope: `im:read`, `im:write`, `im:history`)을 보유한다. |
| A7 | 플러그인 패키징 및 배포는 기존 OpenClaw 규약(npm)을 따른다. |
| A8 | Python 3.10 이상 런타임이 서버에 설치되어 있다. |

---

## 4. Constraints

| # | Constraint |
|---|-----------|
| C1 | LLM 호출 0건 -- 모든 파싱은 결정적(deterministic) 처리. |
| C2 | SQLite3만 사용; 외부 DB 의존성 없음. |
| C3 | DB 파일 경로: `~/.openclaw/workspace/.todo/todo.sqlite3` 고정. |
| C4 | Section 값은 닫힌 enum: `backlog`, `doing`, `waiting`, `done`, `drop`. |
| C5 | Status 값은 닫힌 enum: `open`, `done`, `dropped`. |
| C6 | 커맨드 접두사는 `/todo` 단일. |
| C7 | Assignee는 Slack 멘션(`<@U...>`) 형식만 허용; 일반 텍스트 이름은 assignee로 해석하지 않는다. |

---

## 5. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R1 | 높은 동시성에서 SQLite 쓰기 경합 | Medium | Medium | WAL 모드 + `busy_timeout=3000`; lock 대기 시간 모니터링 |
| R2 | Private/Shared 동일 이름 프로젝트 혼란 | Medium | Low | Private 우선 해석 + 동일 이름 사용 자제 운영 가이드 |
| R3 | 스키마 마이그레이션 실패로 DB 손상 | Low | High | 마이그레이션을 트랜잭션으로 래핑; 마이그레이션 전 DB 파일 백업 |
| R4 | Slack API 봇 DM 응답 rate limit | Low | Medium | 응답 큐잉; Slack rate limit 헤더 준수 |
| R5 | 날짜 파싱 엣지 케이스 (윤년, 로케일) | Low | Low | `datetime` 엄격 검증; 유효하지 않은 날짜는 명확한 에러 반환 |
| R6 | Gateway가 `command_prefix` 매칭을 미지원하여 LLM 바이패스 불가 | Medium | Medium | LLM 라우팅 폴백 경로 유지; Gateway 측 지원을 목표로 협의 |
| R7 | Bridge 이중 변환 로직 제거 시 기존 사용자 혼란 | Low | Low | 변경 내역 안내 공지; v1.2부터 `/todo` 단일 접두사임을 문서화 |

---

## 6. Dependencies

| # | Dependency | Type | Notes |
|---|-----------|------|-------|
| D1 | OpenClaw Gateway | Runtime | DM 메시지 수신 및 플러그인 라우팅 |
| D2 | Slack Bot (OAuth App) | Runtime | DM 읽기/쓰기 권한 필요 |
| D3 | Python >= 3.10 | Runtime | 서버 실행 환경 (pyproject.toml 기준) |
| D4 | SQLite3 (stdlib) | Runtime | 외부 패키지 불필요; Python 내장 모듈 사용 |
| D5 | Node.js / npm | Build/Deploy | Bridge 플러그인 패키징 (TypeScript -> JS) |
| D6 | pytest / pytest-cov | Dev | 테스트 프레임워크 |
| D7 | ruff / black | Dev | 린터 및 포맷터 |

---

## 7. User Stories & Acceptance Criteria

### US-01: 태스크 추가

> **As a** Slack 사용자, **I want to** DM에서 `/todo add` 커맨드로 태스크를 생성 **so that** 빠르게 할일을 기록할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-01.1 | `/todo add 장보기` 입력 시 Inbox/backlog에 태스크가 생성되고, sender가 assignee로 지정되며, `Added #N` 포함 응답이 반환된다. | 자동 테스트 |
| AC-01.2 | `/todo add Deploy <@U2> /p Ops /s doing due:03-15` 입력 시 프로젝트 Ops, 섹션 doing, due=현재연도-03-15, assignee=U2인 태스크가 생성된다. | 자동 테스트 |
| AC-01.3 | Private 프로젝트에 owner가 아닌 assignee를 지정하면 경고 메시지와 함께 태스크가 **생성되지 않는다**. | 자동 테스트 |
| AC-01.4 | DB 파일이 없는 상태에서 첫 커맨드 실행 시 DB 생성 + 스키마 적용 + Inbox 생성 후 태스크가 정상 생성된다. | 자동 테스트 |
| AC-01.5 | 멘션 없이 `/todo add` 실행 시 sender가 기본 assignee로 지정된다. | 자동 테스트 |
| AC-01.6 | 존재하지 않는 프로젝트에 add 시도 시 적절한 에러 메시지가 반환된다 (Inbox 제외). | 자동 테스트 |

### US-02: 태스크 목록 조회

> **As a** Slack 사용자, **I want to** `/todo list`로 내 할일을 조회 **so that** 현재 진행 상황을 파악할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-02.1 | `/todo list` 입력 시 sender가 assignee인 open 태스크만 반환되며, 최대 30개, due 우선 정렬된다. | 자동 테스트 |
| AC-02.2 | `/todo list all` 입력 시 shared 프로젝트 + sender의 private 프로젝트 태스크가 포함되고, 타인의 private 태스크는 **절대 제외**된다. | 자동 테스트 |
| AC-02.3 | `/todo list /p Ops /s doing` 입력 시 프로젝트 Ops, 섹션 doing 태스크만 반환된다. | 자동 테스트 |
| AC-02.4 | `/todo list done` 입력 시 status=done인 태스크만 반환된다. | 자동 테스트 |
| AC-02.5 | 정렬 순서: (1) due 있는 항목 우선, (2) due 오름차순, (3) id 내림차순. | 자동 테스트 |
| AC-02.6 | `/todo list <@U2>` 입력 시 U2가 assignee인 태스크만 반환된다 (shared 프로젝트 범위). | 자동 테스트 |

### US-03: 보드 뷰 조회

> **As a** Slack 사용자, **I want to** `/todo board`로 섹션별 그룹 뷰를 확인 **so that** 칸반 스타일로 진행 상태를 볼 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-03.1 | `/todo board /p Ops` 입력 시 BACKLOG, DOING, WAITING, DONE, DROP 순서로 그룹화된 태스크가 출력된다. | 자동 테스트 |
| AC-03.2 | 각 섹션은 기본 최대 10개 항목을 표시한다 (`limitPerSection` 기본값). | 자동 테스트 |
| AC-03.3 | 각 항목은 `#id due:YYYY-MM-DD|- assignees:<@U..> title` 형식으로 표시된다. | 자동 테스트 |

### US-04: 태스크 상태 변경

> **As a** Slack 사용자, **I want to** `/todo move/done/drop`으로 태스크 상태를 변경 **so that** 진행 상황을 업데이트할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-04.1 | `/todo move 42 doing` 입력 시 태스크 #42의 섹션이 doing으로 변경되고 확인 응답이 반환된다. | 자동 테스트 |
| AC-04.2 | `/todo done 42` 입력 시 태스크 #42의 status=done, section=done, closed_at이 기록된다. | 자동 테스트 |
| AC-04.3 | `/todo drop 42` 입력 시 태스크 #42의 status=dropped, section=drop, closed_at이 기록된다. | 자동 테스트 |
| AC-04.4 | Shared 태스크에 대해 assignee도 created_by도 아닌 사용자가 변경 시도하면 권한 에러가 반환된다. | 자동 테스트 |
| AC-04.5 | Private 프로젝트의 태스크는 owner만 변경할 수 있다. | 자동 테스트 |
| AC-04.6 | 유효하지 않은 섹션 값(예: `/todo move 42 invalid`)에 대해 에러가 반환된다. | 자동 테스트 |
| AC-04.7 | 존재하지 않는 task ID에 대해 에러가 반환된다. | 자동 테스트 |

### US-05: 태스크 수정

> **As a** Slack 사용자, **I want to** `/todo edit`으로 태스크 정보를 수정 **so that** 제목, 담당자, 기한 등을 갱신할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-05.1 | `/todo edit 42 New title due:04-01` 입력 시 제목과 due가 모두 업데이트되고 확인 응답이 반환된다. | 자동 테스트 |
| AC-05.2 | `/todo edit 42 <@U3>` 입력 시 assignees가 U3으로 **완전 교체**된다(기존 assignee 제거). | 자동 테스트 |
| AC-05.3 | `/todo edit 42 due:-` 입력 시 due가 NULL로 설정된다. | 자동 테스트 |
| AC-05.4 | Private 프로젝트 내 태스크에서 owner 외 assignee로 변경 시도하면 경고 후 변경이 **적용되지 않는다**. | 자동 테스트 |
| AC-05.5 | 옵션 토큰(`/p`, `/s`, `due:`, `<@U...>`) 이전 텍스트만 새 title로 적용되며, 해당 텍스트가 비어있으면 title 변경 없음. | 자동 테스트 |

### US-06: 프로젝트 관리

> **As a** Slack 사용자, **I want to** 프로젝트를 생성/조회/가시성 변경 **so that** 팀/개인 단위로 태스크를 구분 관리할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-06.1 | `/todo project list` 입력 시 shared 프로젝트 목록 + sender의 private 프로젝트 목록이 반환되며, 타인의 private 프로젝트는 **노출되지 않는다**. | 자동 테스트 |
| AC-06.2 | `/todo project set-private Biz` 입력 시, 프로젝트 내 모든 태스크의 assignee가 sender뿐이면 visibility=private로 전환 성공한다. | 자동 테스트 |
| AC-06.3 | `/todo project set-private Biz` 입력 시, 태스크 #12에 `<@U2>`가 할당되어 있으면 에러 메시지에 `#12`와 `<@U2>`가 포함되며 전환이 **거부**된다. | 자동 테스트 |
| AC-06.4 | set-private 에러 메시지에는 위반 task ID(최대 10개)와 위반 assignee 목록이 포함된다. | 자동 테스트 |
| AC-06.5 | `/todo project set-private NewProj` 입력 시, 해당 이름의 프로젝트가 없으면 sender를 owner로 하는 private 프로젝트가 생성된다. | 자동 테스트 |
| AC-06.6 | `/todo project set-shared TeamProj` 입력 시, 이미 동일 이름의 shared 프로젝트가 있으면 noop, 없으면 생성된다. | 자동 테스트 |
| AC-06.7 | Shared 프로젝트 이름 충돌(전역 유니크 위반) 시 에러가 반환된다. | 자동 테스트 |
| AC-06.8 | 이미 private인 프로젝트에 set-private 실행 시 멱등하게 성공한다. | 자동 테스트 |

### US-07: LLM 바이패스를 통한 즉시 응답

> **As a** Slack 사용자, **I want to** `/todo` 커맨드가 LLM 없이 직접 실행 **so that** 지연 없이 즉각 응답을 받을 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-07.1 | manifest에 `command_prefix: "/todo"`, `bypass_llm: true`가 설정되어 있다. | 수동 검증 (manifest 파일 검사) |
| AC-07.2 | `/todo`로 시작하는 메시지는 Gateway가 LLM 파이프라인을 건너뛰고 플러그인 핸들러를 직접 호출한다. | 통합 테스트 |
| AC-07.3 | `/todo`로 시작하지 않는 메시지는 v1에서 무시된다. | 자동 테스트 |
| AC-07.4 | `/todo`로 시작하지 않는 메시지는 무시된다. | 자동 테스트 |
| AC-07.5 | Bridge 서버의 `/todo` -> `/todo` 이중 변환 로직이 제거되어 있다. | 코드 리뷰 |

### US-08: DB 초기화 및 마이그레이션

> **As a** 시스템 운영자, **I want to** 플러그인이 첫 실행 시 자동으로 DB를 생성하고 스키마를 적용 **so that** 수동 설정 없이 즉시 사용할 수 있다.

**Acceptance Criteria:**

| ID | Criterion | Verification |
|----|-----------|-------------|
| AC-08.1 | DB 파일이 없는 상태에서 플러그인 로딩 시 `~/.openclaw/workspace/.todo/` 디렉토리와 `todo.sqlite3` 파일이 자동 생성된다. | 자동 테스트 |
| AC-08.2 | 스키마 생성 후 `schema_version` 테이블에 version=1이 기록된다. | 자동 테스트 |
| AC-08.3 | Shared 프로젝트 `Inbox`가 자동 생성되며, 이미 존재하면 중복 생성하지 않는다 (멱등). | 자동 테스트 |
| AC-08.4 | 모든 DB 연결에서 `PRAGMA journal_mode=WAL`과 `PRAGMA busy_timeout=3000`이 설정된다. | 자동 테스트 |

---

## 8. Functional Requirements

### FR-01: 커맨드 파서

| ID | Requirement | Testable Criterion |
|----|------------|-------------------|
| FR-01.1 | 플러그인은 `/todo`로 시작하는 메시지를 커맨드로 인식하고, 그 외 메시지는 무시해야 한다. | `/todo` prefix 있으면 파싱 성공, 없으면 None/무시 |
| FR-01.2 | `/todo`로 시작하지 않는 메시지는 무시해야 한다. | 비-todo 메시지 입력 시 무시 확인 |
| FR-01.3 | 파서는 title 텍스트, `<@U...>` 멘션, `/p <project>`, `/s <section>`, `due:` 값을 추출해야 한다. | 복합 커맨드 파싱 후 각 필드 검증 |
| FR-01.4 | `due:MM-DD` 또는 `due:M-D` 입력은 서버의 현재 연도를 사용하여 `due:YYYY-MM-DD`로 확장해야 한다. | `due:03-15` -> `2026-03-15` |
| FR-01.5 | 유효하지 않은 날짜(예: `02-30`)는 사용자에게 에러 메시지를 반환해야 한다. | 에러 응답 문자열 확인 |
| FR-01.6 | `due:-`는 due date를 NULL로 설정(클리어)해야 한다. | DB 저장값 NULL 확인 |

### FR-02: 태스크 커맨드 -- add

| ID | Requirement |
|----|------------|
| FR-02.1 | 제공된 title, assignees, project, section, due date로 태스크를 생성한다. |
| FR-02.2 | 기본값: project=`Inbox`, section=`backlog`, assignees=sender, due=NULL. |
| FR-02.3 | 대상 프로젝트가 없고 `Inbox`인 경우 shared로 자동 생성한다. |
| FR-02.4 | Private 프로젝트에 owner 외 assignee가 포함되면 경고 메시지 출력 후 태스크 생성을 **거부**한다. |
| FR-02.5 | 확인 응답에 task ID, project, section, due, assignees, title을 포함한다. |

### FR-03: 태스크 커맨드 -- list

| ID | Requirement |
|----|------------|
| FR-03.1 | scope(`mine`/`all`/`<@USER>`), project, section, status로 필터링하여 태스크를 조회한다. |
| FR-03.2 | 기본값: scope=`mine`, status=`open`, limit=30. |
| FR-03.3 | 정렬: due 있는 항목 우선, due 오름차순, id 내림차순. |
| FR-03.4 | `all` scope는 shared 태스크 + sender의 private 태스크를 포함하며, 타인의 private 태스크는 제외한다. |

### FR-04: 태스크 커맨드 -- board

| ID | Requirement |
|----|------------|
| FR-04.1 | BACKLOG, DOING, WAITING, DONE, DROP 순서로 섹션별 그룹화하여 태스크를 표시한다. |
| FR-04.2 | 기본값: scope=`mine`, status=`open`, limitPerSection=10. |
| FR-04.3 | 각 항목은 `#id due assignees title` 형식으로 표시한다. |

### FR-05: 태스크 커맨드 -- move

| ID | Requirement |
|----|------------|
| FR-05.1 | 지정된 섹션으로 태스크를 이동한다. |
| FR-05.2 | 섹션 값을 enum(`backlog`, `doing`, `waiting`, `done`, `drop`)에 대해 검증한다. |
| FR-05.3 | 권한: private 프로젝트는 owner만, shared 프로젝트는 assignee 또는 created_by만 수정 가능하다. |

### FR-06: 태스크 커맨드 -- done / drop

| ID | Requirement |
|----|------------|
| FR-06.1 | `/todo done <id>`: section=`done`, status=`done`, `closed_at` 기록. |
| FR-06.2 | `/todo drop <id>`: section=`drop`, status=`dropped`, `closed_at` 기록. |
| FR-06.3 | 권한 규칙은 FR-05.3과 동일하다. |

### FR-07: 태스크 커맨드 -- edit

| ID | Requirement |
|----|------------|
| FR-07.1 | 태스크의 title, assignees, project, section, due date를 수정한다. |
| FR-07.2 | 멘션이 제공되면 assignees를 **완전 교체**한다 (append가 아님). |
| FR-07.3 | `due:-`는 due date를 NULL로 설정한다. |
| FR-07.4 | Private 프로젝트로 이동하거나 private 프로젝트 내에서 owner 외 assignee가 포함되면 경고 후 변경을 거부한다. |
| FR-07.5 | 옵션 토큰 이전 텍스트를 새 title로 간주하며, 비어있으면 title 변경 없음. |

### FR-08: 프로젝트 커맨드 -- project list

| ID | Requirement |
|----|------------|
| FR-08.1 | 모든 shared 프로젝트와 sender의 private 프로젝트를 반환한다. |
| FR-08.2 | 타인의 private 프로젝트는 절대 노출하지 않는다. |

### FR-09: 프로젝트 커맨드 -- project set-private

| ID | Requirement |
|----|------------|
| FR-09.1 | Sender가 이미 해당 이름의 private 프로젝트를 소유하면 성공 반환 (멱등). |
| FR-09.2 | Shared 프로젝트가 존재하면 private로 전환을 시도한다 (owner=sender). |
| FR-09.3 | 전환 전 프로젝트 내 모든 태스크를 스캔하여, sender 외 assignee가 하나라도 존재하면 위반 task ID(최대 10개)와 assignee를 포함한 에러로 거부한다. |
| FR-09.4 | 어떤 프로젝트도 존재하지 않으면 sender를 owner로 하는 새 private 프로젝트를 생성한다. |

### FR-10: 프로젝트 커맨드 -- project set-shared

| ID | Requirement |
|----|------------|
| FR-10.1 | 동일 이름의 shared 프로젝트가 있으면 noop. |
| FR-10.2 | 없으면 새로 생성한다. |
| FR-10.3 | 전역 유니크 충돌 시 에러를 반환한다. |

### FR-11: 프로젝트 이름 해석 (Name Resolution)

| ID | Requirement |
|----|------------|
| FR-11.1 | `/p <name>` 해석 순서: (1) sender의 private 프로젝트, (2) shared 프로젝트, (3) 컨텍스트에 따라 에러 또는 자동 생성. |
| FR-11.2 | Shared 프로젝트 이름은 전역 유니크여야 한다. |
| FR-11.3 | Private 프로젝트 이름은 owner 단위로 유니크여야 한다 (다른 owner는 동일 name 허용). |

### FR-12: 데이터베이스 초기화

| ID | Requirement |
|----|------------|
| FR-12.1 | 첫 커맨드 또는 Gateway startup 시 `~/.openclaw/workspace/.todo/` 디렉토리를 생성한다 (없는 경우). |
| FR-12.2 | `todo.sqlite3` 파일이 없으면 v1 전체 스키마로 생성한다. |
| FR-12.3 | `schema_version` 테이블을 생성하고 version=1을 기록한다. |
| FR-12.4 | Shared 프로젝트 `Inbox`를 자동 생성한다 (멱등). |
| FR-12.5 | 모든 연결에서 `PRAGMA journal_mode=WAL`과 `PRAGMA busy_timeout=3000`을 설정한다. |

### FR-13: LLM 바이패스 (Direct Execution)

| ID | Requirement |
|----|------------|
| FR-13.1 | manifest에 `command_prefix: "/todo"` 및 `bypass_llm: true`를 등록한다. |
| FR-13.2 | Gateway는 `/todo`로 시작하는 메시지에 대해 LLM 파이프라인을 건너뛰고 플러그인 `handle_message()`를 직접 호출한다. |
| FR-13.3 | Gateway가 `command_prefix` 매칭을 지원하지 않는 경우 LLM 라우팅으로 폴백한다 (임시). |
| FR-13.4 | Bridge 서버의 `/todo` -> `/todo` 이중 변환 로직이 제거되어야 한다. |

### FR-14: 감사 이벤트

| ID | Requirement |
|----|------------|
| FR-14.1 | 상태 변경 커맨드(add, move, done, drop, edit, set-private, set-shared)는 반드시 `events` 테이블에 행을 삽입해야 한다. |
| FR-14.2 | 각 이벤트는 timestamp, actor user ID, action name, task ID (해당 시), before/after 상태를 포함하는 JSON payload를 기록한다. |

---

## 9. Non-Functional Requirements

| ID | Requirement | Metric | Measurement Method |
|----|------------|--------|-------------------|
| NFR-01 | **응답 지연**: 커맨드 응답 시간 | p95 < 500ms (Slack 네트워크 왕복 제외) | command handler 내 계측 타이머 |
| NFR-02 | **신뢰성**: 동시 쓰기 시 데이터 무손실 | WAL 모드에서 1,000건 동시 쓰기 시 데이터 손상 0건 | 부하 테스트 |
| NFR-03 | **가용성**: 플러그인 가동 시간 | OpenClaw Gateway 가동 시간에 연동; 독립적 장애 모드 없음 | Gateway 모니터링 |
| NFR-04 | **정확성**: 날짜 파싱 | 유효한 입력의 100% 올바르게 저장; 유효하지 않은 입력의 100% 에러 반환 | 단위 테스트 커버리지 |
| NFR-05 | **보안**: Private 프로젝트 격리 | 정보 유출 0건: private 태스크가 다른 사용자에게 절대 노출되지 않아야 함 | 보안 테스트 시나리오 |
| NFR-06 | **테스트 가능성**: 테스트 커버리지 | parser 및 command handler 모듈의 라인 커버리지 >= 80% | `pytest --cov` 리포트 |
| NFR-07 | **유지보수성**: 스키마 마이그레이션 | forward-only; 각 마이그레이션은 멱등하며 트랜잭션으로 래핑 | 마이그레이션 코드 리뷰 |
| NFR-08 | **용량**: 태스크 볼륨 | DB 파일당 최대 100,000 태스크 지원 (NFR-01 기준 내) | 부하 테스트 |
| NFR-09 | **LLM 비용**: 토큰 사용량 | 모든 `/todo` 커맨드 처리에 LLM 토큰 비용 0 | Gateway 로그 감사 |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|------------|
| 커맨드 성공률 | 정상 형식 커맨드의 >= 99%가 에러 없이 실행 | `events` 테이블: count(success) / count(total) |
| 채택률 | 배포 후 2주 내 >= 5명의 활성 사용자 | events 테이블의 distinct `actor_user_id` 수 |
| 태스크 처리량 | 팀 전체 주당 >= 50건 태스크 생성 | `add` action 이벤트 주간 집계 |
| 평균 응답 시간 | p50 < 300ms | command handler 내 계측 타이머 |
| 테스트 통과율 | CI 머지 전 100% 통과 | pytest exit code |
| LLM 호출 횟수 | `/todo` 커맨드 처리 시 0건 | Gateway 로그 내 LLM 호출 카운트 |

---

## 11. Data Model Summary

5개 테이블 (코어 4 + 메타데이터 1):

- **projects** (id, name, visibility, owner_user_id, created_at, updated_at)
  - Unique index: `name` WHERE `visibility='shared'`
  - Unique index: `(owner_user_id, name)` WHERE `visibility='private'`
- **tasks** (id, title, project_id, section, due, status, created_by, created_at, updated_at, closed_at)
- **task_assignees** (task_id, assignee_user_id) -- composite PK
  - Index: `(assignee_user_id, task_id)`
- **events** (id, ts, actor_user_id, action, task_id, payload)
- **schema_version** (version)

---

## 12. Traceability Matrix

| PRD Section | Requirement IDs |
|-------------|----------------|
| 1.2 (LLM 바이패스) | FR-13.1--13.4, NFR-09, US-07 |
| 2 (Slack 사용 방식) | FR-01.1--01.2, FR-13.1--13.4, US-07 |
| 2.2 (커맨드 접두사 정책) | FR-01.1, FR-01.2, C6, FR-13.4 |
| 3.1--3.2 (프로젝트 이름 정책) | FR-11.1--11.3 |
| 3.3 (Private assignee 제한) | FR-02.4, FR-07.4 |
| 3.4 (set-private 제약) | FR-09.3, AC-06.3, AC-06.4 |
| 4 (Due 파서) | FR-01.4--01.6 |
| 5 (커맨드 스펙) | FR-02--FR-10, US-01--US-06 |
| 6 (데이터 모델) | Section 11 |
| 7 (DB 초기화/마이그레이션) | FR-12.1--12.5, US-08 |
| 8 (권한/가시성) | FR-05.3, FR-06.3, NFR-05 |
| 9 (수용 기준) | All AC-* entries in Section 7 |
