# Architecture -- OpenClaw TODO Plugin for Slack

> Version: 2.1
> Date: 2026-02-24
> Status: Implemented
> Derived from: `openclaw_todo_plugin_prd.md` v1.2

---

## 1. System Overview

OpenClaw TODO Plugin은 Slack DM을 통해 팀/개인용 TODO를 관리하는 OpenClaw 플러그인이다.
핵심 설계 원칙은 **LLM 비용 0, 결정적(deterministic) 동작, 런타임 외부 의존성 0**이다.

### 1.1 Component Diagram

```
+------------------+       +--------------------+       +-------------------------+
|                  |       |                    |       |   Python Plugin Core    |
|   Slack User     | DM    |   OpenClaw         |       |   (openclaw_todo)       |
|   (todo: add ..) +------>+   Gateway          +------>+                         |
|                  |       |                    |       |  plugin.py (entry)      |
+------------------+       |  command_prefix    |       |  dispatcher.py (route)  |
                           |  matching:         |       |  parser.py (tokenize)   |
                           |  "todo:" -> bypass |       |  cmd_*.py (handlers)    |
                           |  LLM pipeline      |       |  db.py + migrations.py  |
                           +--------------------+       |  SQLite3 (WAL mode)     |
                                                        +-------------------------+

--- 대안 배포 경로 (JS/TS Gateway인 경우) ---

+------------------+       +--------------------+       +------------------+       +--------------------+
|                  |       |                    |       |  JS Bridge       |       |  Python HTTP       |
|   Slack User     +------>+   OpenClaw         +------>+  (index.ts)      +------>+  Server            |
|                  |       |   Gateway (JS)     |       |  fetch() call    |       |  (server.py:8200)  |
+------------------+       +--------------------+       +------------------+       +--------------------+
                                                         openclaw.plugin.json      POST /message
                                                         pattern: ^todo:(\s|$)     GET  /health
```

### 1.2 Two Deployment Modes

| Mode | 설명 | Gateway 요구사항 |
|------|------|-----------------|
| **Native (Direct)** | Gateway가 Python entry-point(`openclaw.plugins`)를 직접 호출 | Python entry-point discovery 지원 |
| **Bridge (HTTP)** | JS bridge plugin이 Python HTTP 서버로 프록시 | JS plugin 로딩 + Python 서버 사이드카 |

---

## 2. Message Flow

### 2.1 Direct Execution (LLM Bypass)

Gateway manifest에 `command_prefix: "todo:"`, `bypass_llm: true`가 설정된 경우,
Gateway는 LLM 파이프라인을 완전히 건너뛰고 플러그인 핸들러를 즉시 호출한다.

```
1. Slack DM: "todo: add 장보기 due:03-15"
2. Gateway: prefix "todo:" 매칭 -> LLM 파이프라인 스킵
3. Gateway: handle_message(text, context) 직접 호출
4. plugin.py: "todo:" 접두사 strip -> remainder = "add 장보기 due:03-15"
5. dispatcher.py: parse(remainder) -> ParsedCommand(command="add", ...)
6. dispatcher.py: _init_db() -> migrate() -> cmd_add.add_handler()
7. cmd_add.py: resolve_project("Inbox") -> INSERT task -> INSERT assignees -> log_event
8. Response: "Added #1 (Inbox/backlog) due:2026-03-15 assignees:<@U123> -- 장보기"
```

### 2.2 Bridge Mode (JS/TS Gateway)

Gateway가 Python entry-point를 직접 지원하지 않는 경우, JS bridge가 HTTP 프록시 역할을 한다.

```
1. Slack DM: "todo: add 장보기"
2. Gateway: openclaw.plugin.json의 triggers.dm.pattern 매칭
3. Bridge index.ts: fetch("http://127.0.0.1:8200/message", {text, sender_id})
4. server.py: POST /message -> handle_message() -> JSON response
5. Bridge: {text: response} 반환 -> Gateway -> Slack DM
```

### 2.3 Prefix Matching Detail

```python
# plugin.py -- 접두사 매칭 로직
_TODO_PREFIX = "todo:"

# 매칭 조건: 정확히 "todo:" 이거나 "todo: " 으로 시작
stripped == _TODO_PREFIX or stripped.startswith(_TODO_PREFIX + " ")
```

- `/todo`는 의도적으로 미지원 (Slack 슬래시 커맨드 오인식 문제)
- `todo:` 단일 접두사로 통일하여 bridge 이중 변환 제거

---

## 3. Module Structure

### 3.1 파일 구조 (실제 구현)

```
src/openclaw_todo/
  __init__.py              # 패키지 메타 (__version__ = "0.1.0")
  __main__.py              # python -m openclaw_todo -> server.run()
  plugin.py                # Entry-point: handle_message() -- 접두사 매칭 + dispatch 위임
  dispatcher.py            # 커맨드 라우팅: parse -> handler registry -> execute
  parser.py                # 토크나이저: /p, /s, due:, <@U...> 추출 -> ParsedCommand
  db.py                    # SQLite 연결: 경로 결정, 디렉터리 생성, PRAGMA 설정
  migrations.py            # 순차 마이그레이션 러너: schema_version 테이블 기반
  schema_v1.py             # V1 DDL: projects, tasks, task_assignees, events + Inbox seed
  project_resolver.py      # Option A 해석: private-first -> shared -> auto-create Inbox
  permissions.py           # 쓰기 권한 검증 + private assignee 제약
  scope_builder.py         # list/board 공용 WHERE 절 빌더 (mine/all/user)
  event_logger.py          # events 테이블 INSERT 헬퍼
  cmd_add.py               # todo: add
  cmd_list.py              # todo: list
  cmd_board.py             # todo: board
  cmd_move.py              # todo: move
  cmd_done_drop.py         # todo: done / todo: drop (공유 _close_task 로직)
  cmd_edit.py              # todo: edit (title/assignee/project/section/due 변경)
  cmd_project_list.py      # todo: project list
  cmd_project_set_private.py  # todo: project set-private (shared->private 전환 검증 포함)
  cmd_project_set_shared.py   # todo: project set-shared (private->shared 전환)
  server.py                # stdlib HTTP 서버 (bridge mode용, 포트 8200)

bridge/openclaw-todo/
  openclaw.plugin.json     # OpenClaw JS manifest (triggers, configSchema)
  index.ts                 # JS bridge: fetch() -> Python server
  package.json             # npm 패키지 정의
  tsconfig.json            # TypeScript 빌드 설정

tests/
  conftest.py              # 공용 fixtures (in-memory DB, context 등)
  test_parser.py           # parser 단위 테스트
  test_cmd_add.py          # add 핸들러 테스트
  test_cmd_list.py         # list 핸들러 테스트
  test_cmd_board.py        # board 핸들러 테스트
  test_cmd_move.py         # move 핸들러 테스트
  test_cmd_done_drop.py    # done/drop 핸들러 테스트
  test_cmd_edit.py         # edit 핸들러 테스트
  test_cmd_project*.py     # project 서브커맨드 테스트
  test_permissions.py      # 권한 로직 테스트
  test_project_resolver.py # 프로젝트 해석 로직 테스트
  test_e2e.py              # 종단간 통합 테스트
  test_server.py           # HTTP 서버 테스트
  test_plugin.py           # plugin.py entry-point 테스트
  test_migrations.py       # 마이그레이션 러너 테스트
  test_schema_v1.py        # V1 스키마 DDL 테스트
  test_db.py               # DB 연결 테스트
  test_dispatcher.py       # 디스패처 테스트
  ...
```

### 3.2 Module Dependency Graph

```
plugin.py
  -> dispatcher.py
       -> parser.py           (토큰 파싱)
       -> db.py               (연결)
       -> migrations.py       (스키마 적용)
            -> schema_v1.py   (DDL 등록)
       -> cmd_add.py
       -> cmd_list.py
       -> cmd_board.py
       -> cmd_move.py
       -> cmd_done_drop.py
       -> cmd_edit.py
       -> cmd_project_list.py
       -> cmd_project_set_private.py
       -> cmd_project_set_shared.py

cmd_*.py (공통 의존)
  -> project_resolver.py     (프로젝트 이름 -> row)
  -> permissions.py           (쓰기 권한 체크)
  -> scope_builder.py         (list/board 쿼리 조건)
  -> event_logger.py          (감사 로그)

server.py
  -> plugin.py               (handle_message 재사용)
```

### 3.3 Handler Registry

`dispatcher.py`는 딕셔너리 기반 핸들러 레지스트리를 사용한다.

```python
# dispatcher.py -- 핸들러 타입과 레지스트리
HandlerFn = Callable[[ParsedCommand, sqlite3.Connection, dict], str]

_handlers: dict[str, HandlerFn] = {
    "add":                  _add_handler,
    "list":                 _list_handler,
    "move":                 _move_handler,
    "done":                 _done_handler,
    "drop":                 _drop_handler,
    "board":                _board_handler,
    "edit":                 _edit_handler,
    "project_list":         _project_list_handler,
    "project_set_private":  _set_private_handler,
    "project_set_shared":   _set_shared_handler,
}
```

- `register_handler(command, fn)`으로 외부 확장 가능
- `project` 서브커맨드는 `_dispatch_project()`에서 토큰 기반으로 `project_{sub}` 키로 재라우팅
- 미등록 커맨드는 `_stub_handler`로 폴백

### 3.4 Parser Output

`parser.py`는 모든 커맨드에 공통된 `ParsedCommand` 데이터클래스를 반환한다.

```python
@dataclass
class ParsedCommand:
    command: str                      # "add", "list", "project" 등
    args: list[str]                   # move/done/drop/edit의 <id>
    project: str | None               # /p <name>
    section: str | None               # /s <section>
    due: str | None                   # YYYY-MM-DD 또는 DUE_CLEAR("-")
    mentions: list[str]               # <@U...> 에서 추출된 user ID 목록
    title_tokens: list[str]           # 옵션 토큰 외 나머지 텍스트
```

---

## 4. Data Model (SQLite3)

### 4.1 DB 위치 및 설정

```
경로: ~/.openclaw/workspace/.todo/todo.sqlite3
PRAGMA journal_mode = WAL;      -- 동시 읽기 허용
PRAGMA busy_timeout = 3000;     -- 3초 재시도
PRAGMA foreign_keys = ON;       -- FK 강제
```

### 4.2 ER Diagram

```
+-------------------+       +-------------------+       +-------------------+
|    projects       |       |      tasks        |       |  task_assignees   |
+-------------------+       +-------------------+       +-------------------+
| id          PK    |<------| project_id   FK   |       | task_id      FK   |
| name        TEXT  |       | id          PK    |<------| assignee_user_id  |
| visibility  TEXT  |       | title       TEXT  |       | PK(task_id,       |
|   ('shared'|      |       | section     TEXT  |       |    assignee_uid)  |
|    'private')     |       |   (backlog|doing| |       +-------------------+
| owner_user_id     |       |    waiting|done|  |
|   TEXT NULL       |       |    drop)          |       +-------------------+
| created_at  TEXT  |       | due        TEXT?  |       |     events        |
| updated_at  TEXT  |       | status     TEXT   |       +-------------------+
+-------------------+       |   (open|done|     |       | id          PK    |
                            |    dropped)       |       | ts          TEXT   |
                            | created_by TEXT   |       | actor_user_id     |
                            | created_at  TEXT  |       | action      TEXT   |
                            | updated_at  TEXT  |       | task_id     INT?  |
                            | closed_at   TEXT? |       | payload     TEXT   |
                            +-------------------+       |   (JSON)          |
                                                        +-------------------+
```

### 4.3 Schema DDL (schema_v1.py)

```sql
CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    visibility      TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
    owner_user_id   TEXT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    section         TEXT NOT NULL CHECK (section IN ('backlog','doing','waiting','done','drop')),
    due             TEXT NULL,
    status          TEXT NOT NULL CHECK (status IN ('open','done','dropped')),
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT NULL
);

CREATE TABLE task_assignees (
    task_id             INTEGER NOT NULL REFERENCES tasks(id),
    assignee_user_id    TEXT NOT NULL,
    PRIMARY KEY (task_id, assignee_user_id)
);

CREATE TABLE events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    actor_user_id   TEXT,
    action          TEXT,
    task_id         INTEGER NULL,
    payload         TEXT
);
```

### 4.4 Indexes

| Index | 대상 | 조건 |
|-------|------|------|
| `ux_projects_shared_name` | `projects(name)` | `WHERE visibility='shared'` (전역 유니크) |
| `ux_projects_private_owner_name` | `projects(owner_user_id, name)` | `WHERE visibility='private'` (owner 내 유니크) |
| `ix_task_assignees_user` | `task_assignees(assignee_user_id, task_id)` | 무조건 (scope 쿼리 가속) |

### 4.5 Schema Versioning

```sql
-- migrations.py가 자동 생성
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
-- 초기값: 0 (빈 DB), V1 마이그레이션 후: 1
```

- `migrations.py`의 `@register` 데코레이터로 마이그레이션 함수를 순차 등록
- 각 마이그레이션은 트랜잭션 내에서 실행, 실패 시 롤백 + `RuntimeError`

### 4.6 초기화 시퀀스

```
dispatch() 호출
  -> _init_db()
       -> get_connection(db_path)
            1. db_path 결정 (인자 또는 기본 ~/.openclaw/workspace/.todo/todo.sqlite3)
            2. 디렉터리 없으면 mkdir -p
            3. sqlite3.connect() + PRAGMA 설정
       -> migrate(conn)
            1. schema_version 테이블 확인/생성
            2. 현재 버전 읽기
            3. 미적용 마이그레이션 순차 실행
            4. V1: 4개 테이블 생성 + shared Inbox 프로젝트 seed
```

---

## 5. APIs

### 5.1 Plugin API (Python Entry-Point)

```python
# plugin.py
def handle_message(text: str, context: dict, db_path: str | None = None) -> str | None:
    """Process an incoming Slack DM message.

    Returns a response string for todo: commands, or None if not a TODO command.
    """
```

- **text**: Slack 메시지 원문 (예: `"todo: add 장보기"`)
- **context**: `{"sender_id": "U12345"}` (최소 필수 필드)
- **db_path**: SQLite 경로 오버라이드 (테스트용)
- **반환**: 응답 문자열 또는 `None` (todo: 접두사 아닌 경우)

Entry-point 등록 (`pyproject.toml`):

```toml
[project.entry-points."openclaw.plugins"]
todo = "openclaw_todo.plugin:handle_message"
```

### 5.2 HTTP Bridge API (server.py)

| Endpoint | Method | 설명 |
|----------|--------|------|
| `/health` | GET | `{"status": "ok"}` |
| `/message` | POST | TODO 커맨드 처리 |

**POST /message** 요청:

```json
{
  "text": "todo: add 장보기",
  "sender_id": "U12345"
}
```

**성공 응답** (200):

```json
{
  "response": "Added #1 (Inbox/backlog) due:- assignees:<@U12345> -- 장보기"
}
```

**에러 응답**:

| Status | 사유 |
|--------|------|
| 400 | invalid JSON, empty body, invalid Content-Length |
| 404 | 잘못된 경로 |
| 413 | body > 1 MiB (`MAX_BODY_BYTES`) |
| 422 | `text` 또는 `sender_id` 누락 |

### 5.3 JS Bridge Manifest (openclaw.plugin.json)

```json
{
  "id": "openclaw-todo",
  "name": "openclaw-todo",
  "version": "0.1.0",
  "main": "dist/index.js",
  "triggers": {
    "dm": { "pattern": "^todo:(\\s|$)" }
  },
  "configSchema": {
    "properties": {
      "serverUrl": {
        "type": "string",
        "default": "http://127.0.0.1:8200"
      }
    }
  }
}
```

### 5.4 User-Facing Commands

| 커맨드 | 핸들러 | 설명 |
|--------|--------|------|
| `todo: add <title> [@user] [/p P] [/s S] [due:D]` | `cmd_add.py` | 태스크 생성 |
| `todo: list [mine\|all\|@user] [/p P] [/s S] [open\|done\|drop]` | `cmd_list.py` | 목록 조회 |
| `todo: board [mine\|all\|@user] [/p P]` | `cmd_board.py` | 칸반 보드 |
| `todo: move <id> /s <section>` | `cmd_move.py` | 섹션 이동 |
| `todo: done <id>` | `cmd_done_drop.py` | 완료 처리 |
| `todo: drop <id>` | `cmd_done_drop.py` | 드롭 처리 |
| `todo: edit <id> [title] [@user] [/p P] [/s S] [due:D\|-]` | `cmd_edit.py` | 태스크 수정 |
| `todo: project list` | `cmd_project_list.py` | 프로젝트 목록 |
| `todo: project set-private <name>` | `cmd_project_set_private.py` | private 전환 |
| `todo: project set-shared <name>` | `cmd_project_set_shared.py` | shared 전환 |

---

## 6. Jobs / Background Tasks

v1에는 별도의 백그라운드 잡이 없다. 모든 처리는 동기적 request-response 사이클 내에서 완료된다.

| Job (향후) | 트리거 | 목적 |
|-----------|--------|------|
| Due date 알림 | 스케줄러 (cron) | 만기 임박 태스크 Slack DM 알림 |
| Stale task 정리 | 주간 | 장기 미변경 태스크 자동 아카이브 |
| DB vacuum | 주간 | WAL 파일 정리, 디스크 회수 |

---

## 7. Observability

### 7.1 Logging

모든 모듈이 `logging.getLogger(__name__)`을 사용하며, 계층적 로거 이름 구조를 따른다.

```
openclaw_todo.plugin        INFO   메시지 수신, 접두사 매칭
openclaw_todo.dispatcher    INFO   커맨드 라우팅 결과
openclaw_todo.parser        DEBUG  ParsedCommand 내용
openclaw_todo.db            INFO   DB 생성/연결
                            DEBUG  기존 DB 열기
openclaw_todo.migrations    INFO   스키마 버전 전환
openclaw_todo.permissions   DEBUG  권한 체크 결과
openclaw_todo.cmd_*         INFO   핸들러 실행 결과
openclaw_todo.server        INFO   HTTP 요청 로그
```

### 7.2 Audit Events (events 테이블)

모든 상태 변경은 `event_logger.log_event()`를 통해 `events` 테이블에 기록된다.

```python
# event_logger.py
def log_event(conn, *, actor_user_id, action, payload, task_id=None):
    conn.execute(
        "INSERT INTO events (actor_user_id, action, task_id, payload) VALUES (?, ?, ?, ?);",
        (actor_user_id, action, task_id, json.dumps(payload)),
    )
```

| action | 발생 시점 |
|--------|----------|
| `task.add` | 태스크 생성 |
| `task.edit` | 태스크 수정 (변경 필드별 old/new 기록) |
| `task.move` | 섹션 이동 |
| `task.done` | 완료 처리 |
| `task.drop` | 드롭 처리 |
| `project.create_private` | private 프로젝트 신규 생성 |
| `project.create_shared` | shared 프로젝트 신규 생성 |
| `project.set_private` | shared -> private 전환 |
| `project.set_shared` | private -> shared 전환 |

### 7.3 Health Check

HTTP bridge 모드에서 `GET /health` 엔드포인트 제공. 응답: `{"status": "ok"}`

### 7.4 Metrics (향후)

Gateway가 메트릭 인터페이스를 제공하면 아래 항목을 계측:

- `todo_commands_total` (counter, labels: verb, status)
- `todo_command_duration_seconds` (histogram, labels: verb)
- `todo_db_errors_total` (counter)

---

## 8. Security

### 8.1 인증/인가

- **인증**: OpenClaw Gateway가 Slack OAuth를 처리. 플러그인은 `context["sender_id"]`(Slack User ID)를 신뢰한다.
- **인가**: `permissions.py`에서 태스크별 쓰기 권한을 검증한다.

| 프로젝트 종류 | 읽기 | 쓰기 |
|--------------|------|------|
| shared | scope 기반 (mine/all/user) | assignee 또는 created_by |
| private | owner만 | owner만 |

### 8.2 Private 프로젝트 assignee 제약

- private 프로젝트에 owner가 아닌 assignee를 지정하면 **경고 후 거부** (데이터 미생성/미수정)
- `validate_private_assignees()` 함수가 `cmd_add.py`, `cmd_edit.py`에서 호출됨
- `project set-private` 시 기존 태스크의 non-owner assignee가 있으면 전환 거부 (최대 10건 표시)

### 8.3 Input Validation

| 검증 대상 | 방식 | 위치 |
|----------|------|------|
| SQL Injection | 파라미터 바인딩 (`?`) 전용, 문자열 보간 없음 | 모든 SQL 실행부 |
| Payload 크기 | `MAX_BODY_BYTES = 1 MiB` 제한 | `server.py` |
| Section enum | `VALID_SECTIONS` frozenset 화이트리스트 | `parser.py` |
| Status enum | DB CHECK 제약 (`open`, `done`, `dropped`) | `schema_v1.py` |
| Due date | `_normalise_due()`에서 유효성 검증 후 `YYYY-MM-DD` 정규화 | `parser.py` |
| Slack mention | `<@U[A-Z0-9]+>` 정규식 매칭 | `parser.py` |

### 8.4 네트워크 보안

- HTTP 서버 기본 바인딩: `127.0.0.1:8200` (loopback only)
- 환경변수로 설정 주입 (DB 경로, 포트)
- 비밀정보 코드 내 하드코딩 없음. API 키/토큰은 Gateway가 관리

### 8.5 Data Isolation

Private 프로젝트 데이터는 쿼리 수준에서 격리된다. `scope_builder.py`의 모든 쿼리에
`(p.visibility = 'shared' OR p.owner_user_id = ?)` 조건이 포함되어 타인의 private 데이터 누출을 방지한다.

---

## 9. Deployment and Rollback

### 9.1 Deployment Topology

```
+--------------------------------------------------+
|                   Host Machine                    |
|                                                   |
|  +--------------------------+                     |
|  | OpenClaw Gateway         |                     |
|  |  - Slack Events API 수신 |                     |
|  |  - Plugin 로딩/라우팅    |                     |
|  +-----------+--------------+                     |
|              |                                    |
|    +---------+---------+                          |
|    |                   |                          |
|  [Native]           [Bridge]                      |
|    |                   |                          |
|    v                   v                          |
|  handle_message()    JS bridge (index.ts)         |
|  (in-process)          |                          |
|                        v                          |
|                   Python HTTP Server              |
|                   (server.py :8200)               |
|                   SO_REUSEADDR enabled            |
|                        |                          |
|                        v                          |
|                   ~/.openclaw/workspace/           |
|                     .todo/todo.sqlite3            |
+--------------------------------------------------+
```

### 9.2 Native Mode 배포

```bash
# 1. 패키지 빌드
uv build

# 2. Gateway 환경에 설치 (entry-point 자동 등록)
pip install dist/openclaw_todo_plugin-0.1.0-py3-none-any.whl

# pyproject.toml entry-point:
# [project.entry-points."openclaw.plugins"]
# todo = "openclaw_todo.plugin:handle_message"

# 3. Gateway가 openclaw.plugins entry-point를 탐색하여 자동 로딩
```

### 9.3 Bridge Mode 배포

```bash
# 1. Python 서버 시작
OPENCLAW_TODO_PORT=8200 uv run openclaw-todo-server
# 또는: python -m openclaw_todo

# 2. JS bridge 빌드
cd bridge/openclaw-todo && npm run build

# 3. openclaw.plugin.json을 Gateway 플러그인 디렉터리에 배치
```

### 9.4 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `OPENCLAW_TODO_PORT` | `8200` | HTTP 서버 포트 |
| `OPENCLAW_TODO_DB_PATH` | `~/.openclaw/workspace/.todo/todo.sqlite3` | DB 파일 경로 |
| `OPENCLAW_TODO_URL` | `http://127.0.0.1:8200` | JS bridge -> Python 서버 URL |

### 9.5 Rollback

| 단계 | 절차 |
|------|------|
| 1. 서비스 중지 | Gateway 또는 Python HTTP 서버 종료 (`SIGTERM` -> graceful shutdown) |
| 2. DB 복원 | `cp todo.sqlite3.bak.<ts> todo.sqlite3` (스키마 변경이 있었던 경우) |
| 3. 코드 복원 | 이전 버전 재설치: `pip install openclaw-todo-plugin==<prev>` |
| 4. 재시작 | Gateway / 서버 재시작 |

- **스키마 롤백**: 다운그레이드 마이그레이션은 v1에서 미지원. 수동 SQL 또는 DB 파일 백업/복원으로 대응
- **DB 백업 권장**: 배포 전 `cp todo.sqlite3 todo.sqlite3.bak.$(date +%s)`
- **Graceful shutdown**: `SIGINT`/`SIGTERM` 시그널 핸들러가 `server.py`에 등록됨

---

## 10. Key Design Decisions and Tradeoffs

### 10.1 `todo:` 단일 접두사 + LLM Bypass

| 항목 | 내용 |
|------|------|
| **결정** | `todo:` 접두사로 LLM 파이프라인 완전 우회 |
| **이점** | 응답 지연 최소화, LLM 토큰 비용 0, 결정적 동작 보장 |
| **트레이드오프** | 자연어 입력 불가 (Phase 2로 연기). 사용자가 접두사를 기억해야 함 |
| **기각된 대안** | `/todo` -- Slack 슬래시 커맨드 오인식 문제로 기각 |

### 10.2 Private-First 프로젝트 해석 (Option A)

| 항목 | 내용 |
|------|------|
| **결정** | `/p <name>` 해석 시 sender의 private 프로젝트 우선 검색 |
| **이점** | 개인 작업이 팀 프로젝트와 충돌하지 않음 |
| **트레이드오프** | private/shared 동명 프로젝트 존재 시 shared 접근 불편 (운영 가이드로 동명 사용 자제 권장) |
| **구현** | `project_resolver.py`: private -> shared -> Inbox auto-create 순서 |

### 10.3 SQLite3 단일 파일 DB

| 항목 | 내용 |
|------|------|
| **결정** | 외부 DBMS 없이 SQLite3 사용 |
| **이점** | 의존성 0, 배포 단순, 파일 복사 백업 |
| **트레이드오프** | 수평 확장 불가, 멀티 인스턴스 불가 (단일 Gateway 가정) |
| **완화** | WAL + busy_timeout=3000ms. DM 기반 단일 자릿수 QPS에서 충분 |

### 10.4 Zero Runtime Dependencies

| 항목 | 내용 |
|------|------|
| **결정** | Python stdlib만 사용 (`dependencies = []` in pyproject.toml) |
| **이점** | 설치 단순, 보안 공격 면적 최소, 빌드 시간 0 |
| **트레이드오프** | HTTP 서버가 `http.server` 기반 (프로덕션 수준 미달) |
| **향후** | 트래픽 증가 시 uvicorn/FastAPI 전환 고려 |

### 10.5 Bridge + Native Dual Mode

| 항목 | 내용 |
|------|------|
| **결정** | Python entry-point + HTTP bridge 동시 지원 |
| **이점** | Gateway 구현 언어(Python/JS)에 무관하게 동작 |
| **트레이드오프** | 유지보수 포인트 2개 (plugin.py + server.py + JS bridge) |
| **완화** | `server.py`가 `plugin.handle_message()`를 재사용하므로 로직 중복 없음 |

### 10.6 Assignee 완전 교체 (edit 시)

| 항목 | 내용 |
|------|------|
| **결정** | `todo: edit`에서 멘션 지정 시 assignee 목록을 **완전 교체** (append 아님) |
| **이점** | 단순한 멘탈 모델: "지금 입력한 사람들이 담당자" |
| **트레이드오프** | 기존 assignee 유지 + 추가하려면 전체 재지정 필요 |

### 10.7 Flat Module Structure (No Repository/Service Layer)

| 항목 | 내용 |
|------|------|
| **결정** | Repository/Service 패턴 대신 `cmd_*.py`에서 직접 SQL 실행 |
| **이점** | 간결함. 4개 테이블에 Repository 추상화는 과도 |
| **트레이드오프** | SQL이 핸들러에 분산됨. 규모 확대 시 리팩터링 필요 |
| **완화** | 공통 로직은 `project_resolver.py`, `scope_builder.py`, `permissions.py`로 분리 |

### 10.8 Audit Events (append-only)

| 항목 | 내용 |
|------|------|
| **결정** | 모든 상태 변경을 `events` 테이블에 JSON payload로 기록 |
| **이점** | 변경 이력 추적, 향후 undo/활동 피드 구현 기반 |
| **트레이드오프** | 매 커맨드마다 INSERT 추가. 삭제/아카이브 정책 미정 |
| **참고** | Event sourcing이 아님. 정상 상태(state of truth)는 tasks/projects 테이블 |

### 10.9 Forward-Only Migration

| 항목 | 내용 |
|------|------|
| **결정** | 다운그레이드 마이그레이션 미지원 |
| **이점** | 구현 단순화, 마이그레이션 코드량 절반 |
| **트레이드오프** | 롤백 시 수동 대응 필요 |
| **완화** | SQLite는 파일 복사로 백업이 간단. DB 파일 백업이 유일한 안전장치 |

### 10.10 동기 실행

| 항목 | 내용 |
|------|------|
| **결정** | 모든 핸들러가 동기 실행 (asyncio 미사용) |
| **이점** | 코드 단순성. SQLite 쿼리는 sub-ms 수준 |
| **트레이드오프** | Gateway가 async인 경우 블로킹 가능 |
| **완화** | 필요 시 `asyncio.to_thread()` 래퍼 추가로 대응 가능 |

---

## 11. Error Handling Strategy

### 11.1 Error Propagation Model

플러그인은 **예외를 사용자 응답 문자열로 변환**하는 전략을 사용한다.
모든 핸들러는 성공/실패 모두 `str`을 반환하며, 미처리 예외가 Slack 사용자에게 노출되지 않도록 한다.

```
사용자 입력
    |
    v
[parser.py]  -- ParseError 발생 가능
    |            dispatcher.py에서 catch -> "Parse error: ..." 문자열 반환
    v
[dispatcher.py]  -- Unknown command -> "Unknown command: ..." 문자열 반환
    |
    v
[cmd_*.py]  -- 비즈니스 에러는 즉시 문자열 반환 (예외 아님)
    |          - "Error: task #N not found."
    |          - "Error: permission denied for task #N."
    |          - "Error: project 'X' not found."
    |          - "Warning: private project ... Task was NOT created."
    v
[응답 문자열] -> Gateway -> Slack DM
```

### 11.2 Error Categories

| 카테고리 | 처리 방식 | 예시 |
|----------|----------|------|
| **Parse error** | `ParseError` 예외 -> dispatcher가 catch -> 에러 문자열 | `"Parse error: Invalid due date: '02-30'"` |
| **Validation error** | 핸들러 내 조기 반환 (문자열) | `"Error: task title is required."` |
| **Permission error** | `can_write_task()` false -> 에러 문자열 | `"Error: permission denied for task #5."` |
| **Not found** | DB 조회 결과 없음 -> 에러 문자열 | `"Error: task #99 not found."` |
| **Business rule** | 정책 위반 -> 경고 + 거부 문자열 | `"Warning: private project ... Task was NOT created."` |
| **Migration failure** | `RuntimeError` 발생 -> Gateway로 전파 (심각) | `"Migration to version 2 failed: ..."` |
| **HTTP bridge error** | JSON 에러 응답 + HTTP status code | `400`, `413`, `422` |

### 11.3 Transaction Safety

- 각 커맨드 핸들러는 **모든 변경을 적용한 후** `conn.commit()`을 한 번 호출
- 에러 발생 시 commit 전에 반환하므로 자동 롤백 (SQLite autocommit=off 기본)
- 마이그레이션은 개별 트랜잭션으로 실행, 실패 시 명시적 `conn.rollback()`

### 11.4 TOCTOU 방어

`cmd_project_set_shared.py`에서 concurrent request로 인한 TOCTOU(Time-of-check to time-of-use) 문제를 `sqlite3.IntegrityError` catch로 방어한다.

```python
# cmd_project_set_shared.py -- TOCTOU 방어 예시
try:
    cursor = conn.execute("INSERT INTO projects ...")
except sqlite3.IntegrityError:
    return f"Project '{project_name}' is already shared."
```

---

## 12. Testing Strategy

### 12.1 Test Pyramid

```
        +------------------+
        |  E2E Tests       |  test_e2e.py, test_plugin_install_e2e.py
        |  (시나리오 기반)   |  -- 전체 흐름 검증, 가장 느림
        +------------------+
       /                    \
      +----------------------+
      |  Integration Tests   |  test_cmd_*.py, test_dispatcher.py,
      |  (DB 연동)           |  test_plugin.py, test_server.py
      +----------------------+  -- 실제 SQLite DB 사용 (tmp_path)
     /                        \
    +----------------------------+
    |  Unit Tests                |  test_parser.py, test_permissions.py,
    |  (순수 로직)               |  test_project_resolver.py, test_migrations.py
    +----------------------------+  -- DB fixture 사용하나 격리된 로직 테스트
```

### 12.2 Test Infrastructure

**Fixtures** (`conftest.py`):

- `conn` fixture: `tmp_path` 기반 임시 SQLite DB 생성 + V1 마이그레이션 적용. 테스트 간 완전 격리
- `_load_v1` autouse fixture: 매 테스트마다 migration registry를 초기화하여 부작용 방지
- `seed_task()` 헬퍼: 프로젝트 + 태스크 + assignee를 한번에 삽입하는 유틸리티

```python
# conftest.py -- 핵심 fixture
@pytest.fixture()
def conn(tmp_path):
    c = get_connection(tmp_path / "test.sqlite3")
    migrate(c)
    yield c
    c.close()
```

### 12.3 Test Coverage

| 모듈 | 테스트 파일 | 검증 범위 |
|------|-----------|----------|
| `parser.py` | `test_parser.py` | 토큰 파싱, due 보정, 멘션 추출, 에러 케이스 |
| `cmd_add.py` | `test_cmd_add.py` | 태스크 생성, 기본값, private 제약, 프로젝트 해석 |
| `cmd_list.py` | `test_cmd_list.py` | scope 필터, 정렬, 페이지네이션 |
| `cmd_board.py` | `test_cmd_board.py` | 섹션별 그룹핑, limitPerSection |
| `cmd_move.py` | `test_cmd_move.py` | 섹션 이동, 권한 체크 |
| `cmd_done_drop.py` | `test_cmd_done_drop.py` | 완료/드롭 처리, 중복 처리 방지 |
| `cmd_edit.py` | `test_cmd_edit.py` | 부분 수정, assignee 교체, private 제약 |
| `cmd_project_*.py` | `test_cmd_project*.py` | 프로젝트 CRUD, 전환 검증 |
| `permissions.py` | `test_permissions.py` | private/shared 권한 로직 |
| `project_resolver.py` | `test_project_resolver.py` | Option A 해석 순서 |
| `migrations.py` | `test_migrations.py` | 순차 적용, 롤백, 버전 관리 |
| `schema_v1.py` | `test_schema_v1.py` | DDL 검증, Inbox seed |
| `dispatcher.py` | `test_dispatcher.py` | 라우팅, unknown command, project sub-routing |
| `plugin.py` | `test_plugin.py` | 접두사 매칭, None 반환, USAGE 표시 |
| `server.py` | `test_server.py` | HTTP 엔드포인트, 에러 응답 |
| `db.py` | `test_db.py` | 연결 생성, PRAGMA 적용, 디렉터리 생성 |
| E2E | `test_e2e.py` | 다중 커맨드 시나리오 |
| Install | `test_plugin_install_e2e.py` | wheel 설치 후 entry-point 탐색 |

### 12.4 실행 방법

```bash
# 전체 테스트
uv run pytest -q

# 커버리지 포함
uv run pytest --cov=src --cov-report=term-missing

# 특정 테스트만
uv run pytest tests/test_parser.py -v

# entry-point 설치 테스트 (wheel 빌드 필요)
uv run pytest -m install
```

### 12.5 테스트 원칙

- 외부 네트워크 호출 없음 (SQLite in tmp_path로 완전 자족)
- 각 테스트는 독립적 DB 인스턴스 사용 (flaky test 방지)
- 새 커맨드 추가 시 최소 1개 단위 테스트 동반 (PRD 수용 기준 대응)

---

## 13. Dependency Summary

| Dependency | Purpose | Required |
|------------|---------|----------|
| Python >= 3.10 | Runtime | Yes |
| sqlite3 (stdlib) | Database | Yes |
| pytest >= 7.0 | Testing | Dev only |
| pytest-cov >= 4.0 | Coverage | Dev only |
| ruff >= 0.4.0 | Linting | Dev only |
| black >= 24.0 | Formatting | Dev only |
| TypeScript ^5.0 | Bridge 빌드 | Bridge mode only |

런타임 외부 의존성: **없음** (`dependencies = []`).
