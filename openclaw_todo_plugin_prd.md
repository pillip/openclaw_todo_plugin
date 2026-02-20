# OpenClaw TODO Plugin for Slack — PRD v1.1 (DM 기반)

> 변경사항 반영:
> 1) Slack **슬래시 커맨드 미사용** → **DM(또는 앱 멘션/일반 메시지)에서 `/todo …`**로 사용  
> 2) private 프로젝트: **same owner 내 name 유니크**  
> 3) `/todo project set-private` 실행 시: 해당 프로젝트 내 task 중 **owner가 아닌 assignee가 하나라도 있으면 에러**  
> 4) 프로젝트 이름 충돌 해소: **옵션 A(private 우선)** 유지  
> 5) DB **초기 생성/마이그레이션** 절차 추가

---

## 1) 개요

### 1.1 목표
OpenClaw 플러그인으로 Slack에서 다음을 **LLM 호출 없이(=비용 0)** 처리하는 팀/개인용 TODO 시스템을 제공한다.

- `/todo add|list|board|move|done|drop|edit`
- `/todo project list|set-private|set-shared`
- 저장소: **공유 SQLite3** (동일 Gateway/동일 DB 파일)
- 담당자(assignee): **Slack 멘션만 허용** (`<@U…>` 기반)
- due: `YYYY-MM-DD` 또는 `MM-DD` 허용, 연도 생략 시 **현재 연도**로 보정
- Private 프로젝트: **오직 owner만** 조회/수정 가능

---

## 2) Slack 사용 방식 (슬래시 커맨드 미사용)

### 2.1 사용 채널
슬래시 커맨드를 쓰지 않는다면, 일반적으로 다음 중 하나로 사용한다.

- **DM 채널**: OpenClaw Slack 앱(봇)과 1:1 대화에서 `/todo …` 입력  
- **채널/스레드**(옵션): 앱 멘션(`@openclaw /todo …`) 또는 특정 메시지 패턴을 OpenClaw가 수신하도록 설정된 경우

> v1은 **DM 사용을 기본 경로**로 가정한다.  
> 이유: 권한/노이즈/오작동 리스크가 낮고 운영이 단순함.

### 2.2 커맨드 인식 규칙
- 메시지의 첫 토큰이 `/todo`이면 플러그인이 처리한다.
- 그 외 메시지는 v1에서 무시(자연어 자동 등록은 Phase 2).

---

## 3) 핵심 정책

### 3.1 프로젝트 이름 유니크 정책
- **Shared 프로젝트**: 전역 유니크 (겹치면 생성/변경 거부)
- **Private 프로젝트**: **same owner 내에서만 유니크** (owner가 다르면 동일 name 허용)

### 3.2 프로젝트 이름 충돌 해소(옵션 A)
`/p <name>` 해석:
1) sender(owner)의 private 프로젝트 `<name>`가 존재하면 **private 우선**
2) 없으면 shared `<name>` 사용
3) 둘 다 없으면 (v1 정책에 따라) shared 자동 생성 또는 에러

> 운영 가이드: private와 shared에 같은 이름을 쓰지 않는 것을 권장(혼란 방지).

### 3.3 Private 프로젝트 assignee 제한(“경고 후 거부”)
- private 프로젝트는 **owner만 볼 수 있는 범위**이므로:
  - add/edit 시 owner 이외의 assignee가 포함되면 **경고 메시지 출력 후 작업 거부(변경/생성 미적용)**

경고/거부 응답 예시:
- `⚠️ Private 프로젝트(Personal)는 owner만 볼 수 있어요. 다른 담당자(<@U…>)를 지정할 수 없습니다. (요청이 적용되지 않았습니다.)`

### 3.4 `/todo project set-private` 추가 제약(요구사항)
- 프로젝트를 private로 전환할 때,
  - 해당 프로젝트 내 모든 task를 스캔하여
  - **owner가 아닌 assignee가 하나라도 존재하면 에러**로 실패해야 한다.
- 에러 메시지에는 최소한 아래 정보를 포함한다:
  - 실패 사유
  - 위반 task id 목록 일부(예: 최대 10개)
  - 위반 assignee 목록 일부

에러 예시:
- `❌ Cannot set project "Biz" to private: found tasks assigned to non-owner users. e.g. #12 assignees:<@U2>, #18 assignees:<@U3>`

---

## 4) due 파서 정책

허용 입력:
- `due:YYYY-MM-DD`
- `due:MM-DD` 또는 `due:M-D`

보정:
- 연도 생략 시: `YYYY = now().year` (서버 timezone은 Asia/Seoul 권장)

검증:
- 유효하지 않은 날짜(예: 02-30)는 에러
- DB에는 항상 `YYYY-MM-DD`로 저장

---

## 5) 커맨드 스펙

### 5.0 공통 토큰
- 프로젝트: `/p <projectName>`
- 섹션: `/s <section>`
- 섹션 enum: `backlog | doing | waiting | done | drop`
- due: `due:YYYY-MM-DD|MM-DD` 또는 `due:-`(클리어)

---

### 5.1 `/todo add`
문법:
```
/todo add <title...> [<@USER> ...] [/p <project>] [/s <section>] [due:YYYY-MM-DD|MM-DD]
```

기본값:
- project: `Inbox`
- section: `backlog`
- assignees:
  - 멘션 없으면 sender
  - 멘션 있으면 해당 유저들(다중)
- due: 없으면 NULL

검증:
- private 프로젝트에 sender 외 assignee 포함 시: **경고 후 거부**
- 프로젝트가 없으면:
  - `Inbox`는 shared로 자동 생성 가능(권장)

응답:
- `✅ Added #123 (Inbox/backlog) due:- assignees:<@U1> — 장보기`

---

### 5.2 `/todo list`
문법:
```
/todo list [mine|all|<@USER>] [/p <project>] [/s <section>] [open|done|drop] [limit:N]
```

기본값:
- scope: `mine`
- status: `open`
- limit: 30

scope 의미:
- `mine`: assignees에 sender 포함
- `<@USER>`: 해당 유저가 assignee인 task
- `all`: shared 전체 + sender의 private 프로젝트(타인의 private는 제외)

정렬:
1) due 있는 것 우선
2) due 오름차순
3) id 내림차순

---

### 5.3 `/todo board`
문법:
```
/todo board [mine|all|<@USER>] [/p <project>] [open|done|drop] [limitPerSection:N]
```

기본값:
- scope: mine
- status: open
- limitPerSection: 10

출력:
- BACKLOG → DOING → WAITING → DONE → DROP 순
- 항목 포맷: `#id due:YYYY-MM-DD| - assignees:<@U..> <@U..> title`

---

### 5.4 `/todo move`
문법:
```
/todo move <id> <section>
```

검증:
- 섹션 enum validate
- 권한:
  - private: owner만
  - shared: v1 권장 `assignee` 또는 `created_by`만 수정 가능

---

### 5.5 `/todo done`
```
/todo done <id>
```
- section=`done`, status=`done`, closed_at 기록

### 5.6 `/todo drop`
```
/todo drop <id>
```
- section=`drop`, status=`dropped`, closed_at 기록

---

### 5.7 `/todo edit`
문법(v1 replace 방식):
```
/todo edit <id> [<new title...>] [<@USER> ...] [/p <project>] [/s <section>] [due:YYYY-MM-DD|MM-DD|due:-]
```

규칙:
- 멘션이 있으면 assignees **완전 교체**
- `due:-` 는 due NULL
- title은 옵션 토큰 이전 텍스트를 새 title로 간주(비어있으면 변경 없음)

검증:
- private 프로젝트로 변경되거나 private 프로젝트에서 assignee 변경 시:
  - sender 외 assignee 포함이면 **경고 후 거부(변경 미적용)**

---

### 5.8 `/todo project list`
- 반환:
  - shared 프로젝트 목록
  - sender(owner)의 private 프로젝트 목록

---

### 5.9 `/todo project set-private <name>`
동작:
1) 대상 프로젝트를 resolve:
   - sender의 private `<name>` 존재 → already private (ok)
   - 없고 shared `<name>` 존재 → shared를 private로 “전환 시도”
   - 둘 다 없으면 → sender private `<name>` 생성 (owner=sender)

2) shared→private 전환 시도 시 검증:
   - 해당 프로젝트 내 tasks를 조회
   - 각 task에 대해 `task_assignees`를 확인
   - **owner(sender) 외 assignee가 하나라도 존재하면 실패(에러)**

3) 성공 시:
   - projects.visibility='private', owner_user_id=sender
   - (선택) 기존 task의 assignees가 모두 owner인지 확인되므로 유지 가능

---

### 5.10 `/todo project set-shared <name>`
동작:
- shared `<name>`이 없으면 생성
- 이미 있으면 noop
- 단, shared는 전역 유니크이므로 충돌 시 에러/exists

---

## 6) 데이터 모델 (SQLite3)

### 6.1 DB 파일 위치
- 기본: `~/.openclaw/workspace/.todo/todo.sqlite3`

### 6.2 동시성 설정
- `PRAGMA journal_mode=WAL;`
- `PRAGMA busy_timeout=3000;`

### 6.3 스키마(v1)

#### `projects`
- `id` INTEGER PK AUTOINCREMENT
- `name` TEXT NOT NULL
- `visibility` TEXT NOT NULL CHECK (visibility IN ('shared','private'))
- `owner_user_id` TEXT NULL
- `created_at` TEXT NOT NULL DEFAULT (datetime('now'))
- `updated_at` TEXT NOT NULL DEFAULT (datetime('now'))

Indexes:
- shared 전역 유니크:
  - `CREATE UNIQUE INDEX ux_projects_shared_name ON projects(name) WHERE visibility='shared';`
- private owner 내 유니크:
  - `CREATE UNIQUE INDEX ux_projects_private_owner_name ON projects(owner_user_id, name) WHERE visibility='private';`

#### `tasks`
- `id` INTEGER PK AUTOINCREMENT
- `title` TEXT NOT NULL
- `project_id` INTEGER NOT NULL REFERENCES projects(id)
- `section` TEXT NOT NULL CHECK (section IN ('backlog','doing','waiting','done','drop'))
- `due` TEXT NULL  -- YYYY-MM-DD
- `status` TEXT NOT NULL CHECK (status IN ('open','done','dropped'))
- `created_by` TEXT NOT NULL  -- Slack user id
- `created_at`, `updated_at`, `closed_at`

#### `task_assignees`
- `task_id` INTEGER NOT NULL REFERENCES tasks(id)
- `assignee_user_id` TEXT NOT NULL
- PRIMARY KEY(task_id, assignee_user_id)
- INDEX: `(assignee_user_id, task_id)`

#### `events` (audit, 권장)
- `id` INTEGER PK
- `ts` TEXT
- `actor_user_id` TEXT
- `action` TEXT
- `task_id` INTEGER NULL
- `payload` TEXT (JSON)

---

## 7) DB 초기 생성 / 마이그레이션(필수)

### 7.1 생성 타이밍
플러그인 로딩 후 첫 `/todo …` 실행 시 또는 gateway startup 시점에 아래를 수행:

1) workspace path 결정
2) `~/.openclaw/workspace/.todo/` 디렉토리 생성
3) `todo.sqlite3` 파일 존재 여부 확인
4) 없으면:
   - 파일 생성
   - schema migration 실행
   - `schema_version` 테이블 생성 및 version=1 기록

### 7.2 schema_version 테이블
- `schema_version(version INTEGER NOT NULL)`
- 초기: 1
- 향후:
  - 현재 버전 읽고, 필요한 migration 순차 실행

### 7.3 기본 프로젝트 생성(권장)
- DB 초기화 시 shared 프로젝트 `Inbox` 자동 생성 (중복이면 noop)

---

## 8) 권한/가시성

### 8.1 읽기
- private: owner만
- shared: scope에 따라 mine/all/<@USER>

### 8.2 쓰기
- private: owner만
- shared: v1 권장 `assignee` 또는 `created_by`만

---

## 9) 수용 기준(Acceptance Criteria)

- [ ] shared 프로젝트 이름 충돌 시 생성/변경 거부
- [ ] private 프로젝트는 owner 단위로 유니크 (owner A/B는 같은 name 허용)
- [ ] `/todo project set-private <name>` 실행 시:
  - 프로젝트 내 task 중 owner 외 assignee 존재하면 에러로 실패
- [ ] private 프로젝트에 타 assignee 지정 시: 경고 + 작업 미생성/미수정
- [ ] due `MM-DD` 입력 시 올해로 보정되어 저장
- [ ] DB 최초 실행 시 파일 생성 + schema 적용 + Inbox 생성

---

## 10) 구현 작업 분해(WBS)

- M0: plugin skeleton + `/todo` command 등록
- M1: DB init + migrations + schema_version
- M2: parser (Slack mention, /p, /s, due 보정)
- M3: commands (add/list/board/move/done/drop/edit)
- M4: project commands (list/set-private/set-shared + set-private 검증 로직)
- M5: tests (parser/unit + sqlite E2E)
- M6: packaging/배포(npm 권장)
