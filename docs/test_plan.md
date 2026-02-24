# OpenClaw TODO Plugin -- Test Plan v2.1

> PRD v1.2 기준 | 작성일: 2026-02-24
> 프레임워크: **pytest** | DB: **SQLite3 (tmp_path 기반)** | 실행: `uv run pytest`

---

## 목차

1. [테스트 전략](#1-테스트-전략)
2. [Critical Flows (핵심 흐름)](#2-critical-flows)
3. [테스트 픽스처 가이드](#3-테스트-픽스처-가이드)
4. [테스트 케이스 -- 접두사 인식](#4-테스트-케이스--접두사-인식)
5. [테스트 케이스 -- 커맨드 파서](#5-테스트-케이스--커맨드-파서)
6. [테스트 케이스 -- add](#6-테스트-케이스--add)
7. [테스트 케이스 -- list](#7-테스트-케이스--list)
8. [테스트 케이스 -- board](#8-테스트-케이스--board)
9. [테스트 케이스 -- move](#9-테스트-케이스--move)
10. [테스트 케이스 -- done / drop](#10-테스트-케이스--done--drop)
11. [테스트 케이스 -- edit](#11-테스트-케이스--edit)
12. [테스트 케이스 -- project](#12-테스트-케이스--project)
13. [테스트 케이스 -- LLM 바이패스 검증](#13-테스트-케이스--llm-바이패스-검증)
14. [테스트 케이스 -- DB 초기화 및 마이그레이션](#14-테스트-케이스--db-초기화-및-마이그레이션)
15. [Edge Case / Error Scenario 종합](#15-edge-case--error-scenario-종합)
16. [수용 기준 추적표](#16-수용-기준-추적표)
17. [자동화 후보](#17-자동화-후보)
18. [스모크 테스트 체크리스트](#18-스모크-테스트-체크리스트)

---

## 1. 테스트 전략

### 1.1 목표

- PRD v1.2의 수용 기준(Section 9) 전체를 검증한다.
- 파서 정확성 (멘션, `/p`, `/s`, `due:` 토큰 처리)을 보장한다.
- DB 스키마 생성, 마이그레이션, CRUD 무결성을 확인한다.
- private/shared 프로젝트 접근 제어 규칙을 검증한다.
- `todo:` 단일 접두사 정책 및 `/todo` 미지원 정책을 확인한다.
- LLM 바이패스 구조가 유지되는지 확인한다.

### 1.2 테스트 계층

| 계층 | 도구 | 범위 | 비율(목표) |
|------|------|------|------------|
| **단위 테스트** | `pytest` | 파서, 개별 커맨드 핸들러, 권한 검증, 프로젝트 리졸버 | 60% |
| **통합 테스트** | `pytest` + SQLite (tmp_path) | 커맨드 핸들러 + DB 연동, 디스패처 라우팅, 마이그레이션 | 25% |
| **E2E 테스트** | `pytest` + `handle_message()` 전체 경로 | `todo: ...` 입력부터 응답 문자열까지 전 경로 | 15% |

### 1.3 원칙

- **격리**: 각 테스트는 `tmp_path` 기반 임시 SQLite DB를 사용하여 테스트 간 상태 오염을 방지한다.
- **결정적 실행**: 외부 네트워크 호출이 없다 (SQLite 로컬, LLM 바이패스 설계). 플레이키 테스트를 금지한다.
- **mock 최소화**: 실제 SQLite를 사용하므로 DB 레이어 mock은 불필요하다. Gateway/Slack API 연동 부분만 필요 시 mock 한다.
- **커버리지 목표**: 라인 커버리지 80% 이상 (`pytest-cov`)
- **한글/유니코드 지원**: title, project name에 한글/이모지가 포함된 케이스를 반드시 검증한다.
- **edge case 우선**: 정상 경로보다 경계값/에러 경로에 더 많은 케이스를 배치한다.

### 1.4 실행 방법

```bash
# 전체 테스트
uv run pytest -q

# 커버리지 포함
uv run pytest --cov=src/openclaw_todo --cov-report=term-missing

# 특정 모듈
uv run pytest tests/test_parser.py -v

# 특정 마크만 실행
uv run pytest -m "not integration" -q
```

### 1.5 테스트 파일 구조

```
tests/
  conftest.py                     # 공용 픽스처 (conn, seed_task, _load_v1)
  test_parser.py                  # 파서 단위 테스트
  test_dispatcher.py              # 디스패처 라우팅 테스트
  test_cmd_add.py                 # add 핸들러 테스트
  test_cmd_list.py                # list 핸들러 테스트
  test_cmd_board.py               # board 핸들러 테스트
  test_cmd_move.py                # move 핸들러 테스트
  test_cmd_done_drop.py           # done/drop 핸들러 테스트
  test_cmd_edit.py                # edit 핸들러 테스트
  test_cmd_project.py             # project list 테스트
  test_cmd_project_set_private.py # set-private 테스트
  test_cmd_project_set_shared.py  # set-shared 테스트
  test_permissions.py             # 권한 로직 테스트
  test_project_resolver.py        # 프로젝트 resolve 로직 테스트
  test_migrations.py              # 스키마 마이그레이션 테스트
  test_schema_v1.py               # V1 스키마 검증
  test_plugin.py                  # 플러그인 진입점 (접두사 인식)
  test_e2e.py                     # E2E 시나리오
  test_db.py                      # DB 연결/설정 테스트
  test_server.py                  # HTTP 서버 테스트
  test_plugin_install_e2e.py      # 플러그인 설치 E2E 테스트
```

---

## 2. Critical Flows

플러그인의 핵심 비즈니스 흐름으로, 테스트 실패 시 서비스 전체에 영향이 있다. 스모크 테스트 및 회귀 테스트에서 최우선으로 검증한다.

### CF-01: Task 생성 -> 조회 라운드트립

```
todo: add <title> -> Added #N 응답 -> todo: list -> 해당 task 표시
```
- 검증 포인트: DB 삽입, default project(Inbox)/section(backlog)/assignee(sender), 응답 포맷

### CF-02: Task 상태 전이 (생명주기)

```
add -> move /s doing -> board에서 DOING 확인 -> done -> list(open)에서 미표시
```
- 검증 포인트: section/status 변경, closed_at 기록, 정렬/필터 정확성

### CF-03: Private 프로젝트 격리

```
U001: project set-private Secret -> add task /p Secret
U002: list all -> Secret task 미표시
U002: edit/move/done/drop <Secret task id> -> 권한 거부
```
- 검증 포인트: 읽기/쓰기 모두 non-owner 차단

### CF-04: Private 프로젝트 전환 검증

```
shared project에 타인 assignee task 존재 -> project set-private -> 에러 (위반 task 정보 포함)
shared project에 owner만 assignee -> project set-private -> 성공
```
- 검증 포인트: assignee 스캔, 에러 메시지 포맷, DB 상태 유지/변경

### CF-05: Private 프로젝트 assignee 제한

```
private project에 add <@타인> -> 경고 후 거부 (task 미생성)
private project에 edit <id> <@타인> -> 경고 후 거부 (변경 미적용)
```
- 검증 포인트: 경고 메시지, DB 무변경 확인

### CF-06: 프로젝트 이름 충돌 해소 (옵션 A)

```
private "Work" (owner=sender) + shared "Work" 공존
add task /p Work -> private "Work"에 생성됨 (private 우선)
```
- 검증 포인트: resolve 순서

### CF-07: DB 초기화 + 마이그레이션

```
DB 파일 미존재 상태 -> 첫 todo: 커맨드 -> DB 생성 + 스키마 적용 + Inbox 프로젝트 생성
```
- 검증 포인트: 파일 생성, 테이블 존재, schema_version, Inbox 존재

---

## 3. 테스트 픽스처 가이드

### 3.1 핵심 픽스처 (`tests/conftest.py`)

| 픽스처 | 스코프 | 용도 |
|--------|--------|------|
| `_load_v1` (autouse) | function | V1 마이그레이션 등록을 보장한다. 모든 테스트에 자동 적용된다. |
| `conn(tmp_path)` | function | 마이그레이션 완료된 SQLite Connection을 반환한다. `yield` 후 `close()` 한다. |
| `seed_task(conn, ...)` | 헬퍼 함수 | project/task/assignee를 한 번에 삽입하는 헬퍼이다. `task_id`를 반환한다. |

`seed_task` 파라미터:
```python
seed_task(
    conn,
    project_name="Inbox",   # 프로젝트 이름 (없으면 자동 생성)
    visibility="shared",     # shared | private
    owner=None,              # private 프로젝트의 owner_user_id
    title="Test task",       # task 제목
    section="backlog",       # backlog | doing | waiting | done | drop
    created_by="U001",       # task 생성자
    assignees=None,          # None이면 created_by가 기본 assignee
    due=None,                # YYYY-MM-DD 또는 None
)
```

### 3.2 E2E 픽스처 (`tests/test_e2e.py`)

| 픽스처/헬퍼 | 용도 |
|-------------|------|
| `db_path(tmp_path)` | `str(tmp_path / "e2e.sqlite3")` 경로 문자열을 반환한다. |
| `_msg(text, sender, db_path)` | `handle_message("todo: " + text, ...)` 호출 후 응답을 반환하는 헬퍼이다. |
| `_extract_task_id(result)` | `"Added #N"` 응답에서 task ID를 추출한다. |
| `_query_task(db_path, task_id, columns)` | SQL injection 방지 화이트리스트 기반 직접 DB 조회 헬퍼이다. |

### 3.3 픽스처 작성 지침

- **ParsedCommand 헬퍼**: 각 커맨드 테스트 파일에서 `_make_parsed(...)` 팩토리 함수를 정의하여 `ParsedCommand` 생성을 간소화한다:

```python
def _make_parsed(*, title_tokens=None, project=None, section=None,
                 due=None, mentions=None) -> ParsedCommand:
    return ParsedCommand(
        command="add", args=[], project=project, section=section,
        due=due, mentions=mentions or [], title_tokens=title_tokens or [],
    )
```

- **sender_id 규칙**: 테스트에서 `U001`(owner/sender), `U002`(타인), `U003`(제3자) 등 일관된 ID를 사용한다.
- **프로젝트 시드 데이터**: private/shared 프로젝트 생성이 필요한 테스트에서는 직접 SQL INSERT 또는 `seed_task()`를 사용한다.

### 3.4 추가 권장 픽스처

```python
@pytest.fixture()
def shared_project(conn):
    """미리 생성된 shared project 'TestProj' 반환."""
    conn.execute("INSERT INTO projects (name, visibility) VALUES ('TestProj', 'shared');")
    conn.commit()
    return conn.execute("SELECT id FROM projects WHERE name='TestProj'").fetchone()[0]

@pytest.fixture()
def private_project(conn):
    """owner='U001'인 private project 'Secret' 반환."""
    conn.execute(
        "INSERT INTO projects (name, visibility, owner_user_id) "
        "VALUES ('Secret', 'private', 'U001');"
    )
    conn.commit()
    return conn.execute("SELECT id FROM projects WHERE name='Secret'").fetchone()[0]
```

---

## 4. 테스트 케이스 -- 접두사 인식

> 대상 모듈: `src/openclaw_todo/plugin.py` (`handle_message`, `_TODO_PREFIX`)
> 테스트 파일: `tests/test_plugin.py`

### TC-01: `todo:` 접두사 정상 인식

| 항목 | 내용 |
|------|------|
| **ID** | TC-01 |
| **설명** | `todo: add buy milk` 메시지가 정상 처리되어 응답을 반환한다 |
| **사전 조건** | DB 경로 준비 (tmp_path) |
| **단계** | `handle_message("todo: add buy milk", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | 문자열 응답 반환 (None이 아님), `isinstance(result, str)` |

### TC-02: `todo:` 뒤에 공백 없이 문자가 이어지면 무시

| 항목 | 내용 |
|------|------|
| **ID** | TC-02 |
| **설명** | `todo:x something` 같은 메시지는 TODO 커맨드로 인식하지 않는다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("todo:x something", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | `None` 반환 |

### TC-03: `/todo` 접두사 미지원

| 항목 | 내용 |
|------|------|
| **ID** | TC-03 |
| **설명** | `/todo add task` 메시지는 무시한다. Slack 슬래시 커맨드 미사용 정책에 따라 `/todo`는 지원하지 않는다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("/todo add task", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | `None` 반환 |

### TC-04: `/todo:` 접두사 미지원

| 항목 | 내용 |
|------|------|
| **ID** | TC-04 |
| **설명** | `/todo: add task` 메시지도 무시한다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("/todo: add task", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | `None` 반환 |

### TC-05: 일반 텍스트 무시

| 항목 | 내용 |
|------|------|
| **ID** | TC-05 |
| **설명** | `todo:` 접두사가 없는 일반 메시지는 무시한다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("hello world", ...)`, `handle_message("", ...)`, `handle_message("some random text", ...)` 각각 호출 |
| **기대 결과** | 모두 `None` 반환 |

### TC-06: `todo:` 만 입력 시 Usage 반환

| 항목 | 내용 |
|------|------|
| **ID** | TC-06 |
| **설명** | 커맨드 없이 `todo:` 만 입력하면 사용법 안내 메시지를 반환한다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("todo:", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | `"Usage"` 포함된 문자열 반환 |

### TC-07: 선행/후행 공백 허용

| 항목 | 내용 |
|------|------|
| **ID** | TC-07 |
| **설명** | `"  todo: add task  "` 처럼 공백이 있어도 정상 인식한다 |
| **사전 조건** | 없음 |
| **단계** | `handle_message("  todo: add task  ", {"sender_id": "U1"}, db_path)` 호출 |
| **기대 결과** | 문자열 응답 반환 (None이 아님) |

### TC-08: 알 수 없는 커맨드 시 도움말 반환

| 항목 | 내용 |
|------|------|
| **ID** | TC-08 |
| **설명** | `todo: foobar`처럼 알 수 없는 커맨드 입력 시 "Unknown command"와 도움말을 반환한다 |
| **사전 조건** | 없음 |
| **단계** | dispatcher를 통해 `"foobar something"` 디스패치 |
| **기대 결과** | 응답에 `"Unknown command"`, `"foobar"`, `"Commands:"` 포함 |

---

## 5. 테스트 케이스 -- 커맨드 파서

> 대상 모듈: `src/openclaw_todo/parser.py`
> 테스트 파일: `tests/test_parser.py`

### 5.1 기본 커맨드/토큰 추출

| ID | 설명 | 입력 | 기대 결과 |
|----|------|------|-----------|
| TC-09 | 첫 토큰이 command로 추출 | `"list mine /p Work"` | `command="list"`, `"mine" in title_tokens` |
| TC-10 | `/p` project 추출 | `"add Buy milk /p MyProject"` | `project="MyProject"`, title에 `/p`/`MyProject` 없음 |
| TC-11 | `/s` 유효 섹션 추출 (5가지) | `"add Task /s <section>"` | 각 유효 section 정상 설정 |
| TC-12 | `/s` 무효 섹션 | `"add Task /s invalid_section"` | `ParseError("Invalid section")` |
| TC-24 | command 대소문자 정규화 | `"ADD Task"`, `"LiSt"` | `command="add"`, `command="list"` |
| TC-25 | section 대소문자 정규화 | `"add Task /s DOING"` | `section="doing"` |

### 5.2 due 파서

| ID | 설명 | 입력 | 기대 결과 |
|----|------|------|-----------|
| TC-13 | `MM-DD` 현재연도 보정 | `"add Task due:03-15"` | `due="{current_year}-03-15"` |
| TC-14 | `M-D` 한 자리 보정 | `"add Task due:1-1"` | `due="{current_year}-01-01"` |
| TC-15 | `YYYY-MM-DD` 그대로 유지 | `"add Task due:2026-06-01"` | `due="2026-06-01"` |
| TC-16 | 무효 날짜 (02-30) | `"add Task due:2026-02-30"` | `ParseError("Invalid due date")` |
| TC-17 | 월 범위 초과 (13-01) | `"add Task due:13-01"` | `ParseError` |
| TC-18 | garbage 문자열 | `"add Task due:notadate"` | `ParseError` |
| TC-19 | `due:-` 클리어 | `"add Task due:-"` | `due == DUE_CLEAR` |
| TC-20 | 윤년 02-29 | `"add Task due:2028-02-29"` | `due="2028-02-29"` |
| TC-21 | 비윤년 02-29 에러 | `"add Task due:2026-02-29"` | `ParseError` |

### 5.3 Slack mention 추출

| ID | 설명 | 입력 | 기대 결과 |
|----|------|------|-----------|
| TC-22 | 단일/복수 mention 추출 | `"add Task <@U12345> <@UABCDE>"` | `mentions=["U12345","UABCDE"]`, title에서 제거 |

### 5.4 에러/edge case

| ID | 설명 | 입력 | 기대 결과 |
|----|------|------|-----------|
| TC-23 | 빈 입력 / 공백만 | `""`, `"   "` | `ParseError("Empty command")` |
| TC-26 | 한글/유니코드 title | `"add 우유 사기 /p 집"` | `title_tokens=["우유","사기"]`, `project="집"` |
| TC-27 | `/p` 값 없이 끝남 | `"add Task /p"` | `ParseError("/p requires a project name")` |
| TC-28 | `/s` 값 없이 끝남 | `"add Task /s"` | `ParseError("/s requires a section name")` |
| TC-29 | 중복 옵션 마지막 우선 | `"add Task /p Alpha /p Beta"` | `project="Beta"` |
| TC-30 | 옵션 위치 자유 | `"add /p Work /s doing due:... title"` | 모든 필드 정상 추출 |

### 5.5 ID 추출 커맨드

| ID | 설명 | 입력 | 기대 결과 |
|----|------|------|-----------|
| TC-31a | move ID 추출 | `"move 42 /s doing"` | `args=["42"]` |
| TC-31b | done ID 추출 | `"done 99"` | `args=["99"]` |
| TC-31c | drop ID 추출 | `"drop 7"` | `args=["7"]` |
| TC-31d | edit ID + title | `"edit 3 New title"` | `args=["3"]`, `title_tokens=["New","title"]` |
| TC-31e | add는 ID 미추출 | `"add 42 is answer"` | `args=[]`, title에 "42" 포함 |

### 5.6 공백/탭 처리

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-32a | 선행/후행 공백 strip | `"  add  Task  "` -> 정상 파싱 |
| TC-32b | 다중 공백 | `"add   Buy   milk"` -> title 정상 |
| TC-32c | 탭 문자 | `"add\tTask\t/s\tdoing"` -> 정상 파싱 |

---

## 6. 테스트 케이스 -- add

> 대상 모듈: `src/openclaw_todo/cmd_add.py`
> 테스트 파일: `tests/test_cmd_add.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-33 | 기본값으로 Inbox/backlog에 추가 | `"Added #1 (Inbox/backlog)"`, status="open", sender가 assignee |
| TC-34 | 명시적 project/section/due | DB에 지정값 저장, 응답에 반영 |
| TC-35 | assignee 미지정 시 sender 기본 | `task_assignees`에 sender만 |
| TC-36 | 다중 assignee | `task_assignees`에 모두 기록 |
| TC-37 | **private + 타인 assignee -> 경고 후 거부** | `"Warning"`, `"NOT created"`, task 미생성 |
| TC-38 | private + owner assignee -> 허용 | `"Added #"` 정상 응답 |
| TC-39 | 빈 title -> 에러 | `"Error"` 포함, task 미생성 |
| TC-40 | 존재하지 않는 project -> 에러 | `"Error"` + project name 포함 |
| TC-41 | `due:-` -> DB에 NULL 저장 | `due IS NULL` |
| TC-42 | add 이벤트 로깅 | `events.action='task.add'`, payload에 title/project/section |

---

## 7. 테스트 케이스 -- list

> 대상 모듈: `src/openclaw_todo/cmd_list.py`
> 테스트 파일: `tests/test_cmd_list.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-43 | 기본 scope=mine, status=open | sender의 open task만 반환, done 미포함 |
| TC-44 | scope=all (shared + sender private) | shared + sender private 포함, 타인 private 미포함 |
| TC-45 | `/p <project>` 필터 | 해당 project task만 |
| TC-46 | 정렬: due 우선, due ASC, id DESC | 올바른 정렬 순서 |
| TC-47 | `limit:N` 적용 | 최대 N개 반환, 기본 30 |
| TC-48 | private task가 타인에게 미노출 | U002의 `list all`에 U001 private 미포함 |

---

## 8. 테스트 케이스 -- board

> 대상 모듈: `src/openclaw_todo/cmd_board.py`
> 테스트 파일: `tests/test_cmd_board.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-49 | 섹션 헤더 순서 | BACKLOG -> DOING -> WAITING -> DONE -> DROP |
| TC-50 | task가 올바른 섹션에 표시 | doing task가 DOING 아래 표시 |
| TC-51 | `limitPerSection:N` 적용 | 섹션당 최대 N개, 기본 10 |
| TC-52 | private task 격리 | sender private만 표시, 타인 private 미표시 |

---

## 9. 테스트 케이스 -- move

> 대상 모듈: `src/openclaw_todo/cmd_move.py`
> 테스트 파일: `tests/test_cmd_move.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-53 | 정상 섹션 이동 | `"moved"` 응답, DB section 변경 |
| TC-54 | 존재하지 않는 task ID | 에러 응답 |
| TC-55 | private task -- 비owner 접근 거부 | `"denied"` 또는 `"error"` 포함, DB 미변경 |
| TC-56 | shared task -- assignee/created_by만 이동 가능 | 관련 user 성공, 무관 user 거부 |

---

## 10. 테스트 케이스 -- done / drop

> 대상 모듈: `src/openclaw_todo/cmd_done_drop.py`
> 테스트 파일: `tests/test_cmd_done_drop.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-57 | done 정상 처리 | status="done", section="done", closed_at NOT NULL |
| TC-58 | done된 task가 기본 list에 미표시 | `list`(open)에서 미포함 |
| TC-59 | drop 정상 처리 | status="dropped", section="drop", closed_at NOT NULL |
| TC-60 | private task의 done/drop -- 비owner 거부 | 권한 거부 응답 |

---

## 11. 테스트 케이스 -- edit

> 대상 모듈: `src/openclaw_todo/cmd_edit.py`
> 테스트 파일: `tests/test_cmd_edit.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-61 | title 변경 | DB title 업데이트, `"Edited"` 응답 |
| TC-62 | section 변경 | DB section 업데이트 |
| TC-63 | due 변경 | DB due 업데이트 |
| TC-64 | `due:-` 클리어 | DB `due IS NULL` |
| TC-65 | assignee 완전 교체 | mention 제공 시 `task_assignees` 전체 교체 |
| TC-66 | **private + 타인 assignee 교체 -> 거부** | `"Warning"`, 변경 미적용 |
| TC-67 | **private project로 이동 + 비owner assignee -> 거부** | `"Warning"`, 변경 미적용 |
| TC-68 | title 미지정 시 기존 값 유지 | 옵션만 변경, title 불변 |
| TC-69 | 존재하지 않는 task ID | 에러 응답 |

---

## 12. 테스트 케이스 -- project

> 대상 모듈: `src/openclaw_todo/cmd_project_list.py`, `cmd_project_set_private.py`, `cmd_project_set_shared.py`
> 테스트 파일: `tests/test_cmd_project.py`, `test_cmd_project_set_private.py`, `test_cmd_project_set_shared.py`

### project list

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-70 | shared + sender private 반환 | shared 전체 + sender private만 표시 |
| TC-71 | 타인의 private 미노출 | U002 private가 U001 `project list`에 미포함 |

### project set-private

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-72 | 이미 private -> noop | `"already private"` |
| TC-73 | shared -> private 전환 성공 (owner만 assignee) | `"now private"`, DB 반영 |
| TC-74 | shared -> private (task 없으면 성공) | `"now private"` |
| TC-75 | **shared -> private 거부 (비owner assignee)** | `"cannot"`, DB visibility 유지 |
| TC-76 | 에러 메시지에 위반 task ID + assignee 포함 | `"Cannot make"`, `"non-owner assignees"`, ID/user 포함 |
| TC-77 | owner assignee만 있는 task는 위반 아님 | 해당 task ID 미포함, 위반 task만 보고 |
| TC-78 | 둘 다 없으면 새 private 생성 | `"created private"`, DB 신규 행 |
| TC-79 | 타인 동명 private 존재 시 별도 생성 | projects에 2행 공존 |
| TC-80 | project name 누락 -> 에러 | `"project name required"` |
| TC-81 | 전환/생성 시 이벤트 로깅 | events에 `project.set_private` / `project.create_private` |

### project set-shared

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-82 | 새 shared 생성 | `"created"`, DB 반영 |
| TC-83 | 이미 shared 존재 -> noop | 중복 에러 없이 정상 |
| TC-84 | shared 이름 충돌 (전역 유니크) | exists/noop 응답 |

### 프로젝트 이름 충돌 해소

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-85 | private 우선 (옵션 A) | sender private "Work" + shared "Work" 시 private 선택 |
| TC-86 | private 없으면 shared 사용 | shared "Work"만 있으면 shared로 resolve |

### 서브커맨드 라우팅

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-87 | `project` 서브커맨드 미지정 | PROJECT_USAGE 반환 |
| TC-88 | 미지원 서브커맨드 | `"Unknown project subcommand"` |

---

## 13. 테스트 케이스 -- LLM 바이패스 검증

> PRD v1.2 핵심 요구사항: manifest에 `command_prefix: "todo:"`, `bypass_llm: true` 등록 시 Gateway가 LLM 없이 직접 플러그인을 호출한다

| ID | 설명 | 검증 방식 |
|----|------|-----------|
| TC-89 | 코드 경로에 LLM 의존성 없음 | `plugin.py` -> `dispatcher.py` 경로에 LLM import/호출 없음 확인 |
| TC-90 | manifest 설정 검증 | manifest 파일에 `command_prefix="todo:"`, `bypass_llm=true` 존재 |
| TC-91 | Gateway 통합 검증 (수동) | 스테이징에서 `todo: add test` 전송 시 LLM 호출 로그 미발생 확인 |

---

## 14. 테스트 케이스 -- DB 초기화 및 마이그레이션

> 대상 모듈: `src/openclaw_todo/db.py`, `migrations.py`, `schema_v1.py`
> 테스트 파일: `tests/test_migrations.py`, `tests/test_schema_v1.py`, `tests/test_db.py`

| ID | 설명 | 기대 결과 |
|----|------|-----------|
| TC-92 | 첫 실행 시 DB 파일 + 스키마 적용 | 파일 생성, schema_version >= 1 |
| TC-93 | Inbox 기본 프로젝트 자동 생성 | name="Inbox", visibility="shared" |
| TC-94 | 마이그레이션 멱등성 | 재실행 시 에러 없음, version 불변 |
| TC-95 | WAL + busy_timeout 설정 | journal_mode="wal", busy_timeout=3000 |
| TC-96 | shared 유니크 인덱스 | 동명 shared INSERT 시 IntegrityError |
| TC-97 | private owner+name 유니크 인덱스 | 같은 owner+name -> 에러, 다른 owner -> 허용 |
| TC-98 | 전체 테이블 존재 확인 | projects, tasks, task_assignees, events, schema_version |
| TC-99 | section/status CHECK 제약 | 무효 값 INSERT 시 에러 |
| TC-100 | migration 실패 시 rollback | 실패 migration 이전 version 유지, 성공 migration 보존 |
| TC-101 | 두 connection 동시 접근 | WAL 기반 무충돌 |

---

## 15. Edge Case / Error Scenario 종합

### 15.1 Private 프로젝트 제한

| 시나리오 | 관련 TC | 기대 |
|----------|---------|------|
| private project에 `add` + 타인 assignee | TC-37 | 경고 후 거부, task 미생성 |
| private project에서 `edit` + 타인 assignee 교체 | TC-66 | 경고 후 거부, 변경 미적용 |
| shared -> private 전환 시 non-owner assignee 존재 | TC-75, TC-76 | 에러 (task ID + assignee 포함) |
| non-owner가 private task에 `move`/`done`/`drop`/`edit` | TC-55, TC-60 | 권한 거부 |
| non-owner가 private project task를 `list`/`board` | TC-48, TC-52 | 미표시 |

### 15.2 Due Date 파싱 edge case

| 시나리오 | 관련 TC | 기대 |
|----------|---------|------|
| `due:02-30` (2월 30일) | TC-16 | ParseError |
| `due:13-01` (13월) | TC-17 | ParseError |
| `due:2025-02-29` (비윤년) | TC-21 | ParseError |
| `due:2028-02-29` (윤년) | TC-20 | 정상 |
| `due:notadate` | TC-18 | ParseError |
| `due:12-31` | TC-13 | 현재연도 12월 31일 |
| `due:-` | TC-19 | DUE_CLEAR sentinel |

### 15.3 이름 충돌

| 시나리오 | 관련 TC | 기대 |
|----------|---------|------|
| shared project 동일 name 생성 시도 | TC-84, TC-96 | 거부 (전역 유니크) |
| 같은 owner가 같은 이름 private 2개 | TC-97 | 거부 (owner+name 유니크) |
| 다른 owner가 같은 이름 private | TC-79, TC-97 | 허용 |
| private + shared 동일 이름 공존 시 resolve | TC-85 | private 우선 (옵션 A) |

### 15.4 존재하지 않는 리소스

| 시나리오 | 관련 TC | 기대 |
|----------|---------|------|
| 존재하지 않는 task ID로 `move`/`done`/`drop`/`edit` | TC-54, TC-69 | 에러 응답 |
| 존재하지 않는 project로 `add` | TC-40 | 에러 응답 (Inbox 제외) |
| 알 수 없는 command | TC-08 | USAGE 반환 |
| 알 수 없는 project subcommand | TC-88 | PROJECT_USAGE 반환 |

### 15.5 권한 모듈 (`permissions.py`)

| 시나리오 | 기대 |
|----------|------|
| private owner -> `can_write_task` True | 허용 |
| private non-owner -> `can_write_task` False | 거부 |
| shared assignee -> True | 허용 |
| shared created_by -> True | 허용 |
| shared unrelated user -> False | 거부 |
| 존재하지 않는 task -> False | 거부 |
| `validate_private_assignees` private + 타인 -> Warning | Warning 문자열 반환 |
| `validate_private_assignees` private + owner만 -> None | None |
| `validate_private_assignees` shared -> 항상 None | None |

---

## 16. 수용 기준 추적표

PRD Section 9의 각 수용 기준과 테스트 케이스의 매핑이다.

| PRD 수용 기준 | 테스트 케이스 |
|--------------|-------------|
| shared 프로젝트 이름 충돌 시 생성/변경 거부 | TC-84, TC-96 |
| private 프로젝트는 owner 단위로 유니크 | TC-79, TC-97 |
| `set-private` 시 비owner assignee 존재하면 에러 | TC-75, TC-76, TC-77 |
| private 프로젝트에 타 assignee 지정 시 경고 + 미생성/미수정 | TC-37, TC-38, TC-66, TC-67 |
| due `MM-DD` 입력 시 올해로 보정 | TC-13, TC-14 |
| DB 최초 실행 시 파일 생성 + schema + Inbox | TC-92, TC-93, TC-98 |
| `todo:` 접두사로 커맨드 정상 인식 | TC-01, TC-07 |
| `/todo` 접두사 미인식 | TC-03, TC-04 |
| manifest `command_prefix`/`bypass_llm` 설정 시 LLM 바이패스 | TC-89, TC-90, TC-91 |
| bridge `/todo` -> `todo:` 이중 변환 로직 제거 | TC-03, TC-04 (간접 검증) |

---

## 17. 자동화 후보

### 17.1 즉시 자동화 (CI 포함 권장)

| 대상 | 테스트 케이스 | 자동화 방식 | 이유 |
|------|-------------|------------|------|
| 접두사 인식 | TC-01 ~ TC-08 | pytest 단위 테스트 | `handle_message()` 단일 함수, 빠른 실행 |
| 커맨드 파서 | TC-09 ~ TC-32 | pytest + `@pytest.mark.parametrize` | 순수 함수, 외부 의존 없음, 대량 케이스에 최적 |
| add 핸들러 | TC-33 ~ TC-42 | pytest + tmp SQLite | 핵심 기능, private assignee 검증 포함 |
| list/board | TC-43 ~ TC-52 | pytest + tmp SQLite | 정렬/필터/격리 로직 검증 |
| move/done/drop | TC-53 ~ TC-60 | pytest + tmp SQLite | 상태 전이 + 권한 검증 |
| edit | TC-61 ~ TC-69 | pytest + tmp SQLite | 교체 로직 + private 검증 |
| project 커맨드 | TC-70 ~ TC-88 | pytest + tmp SQLite | set-private 검증이 핵심 비즈니스 로직 |
| DB/마이그레이션 | TC-92 ~ TC-101 | pytest + tmp SQLite | 스키마 무결성 자동 검증 |
| E2E 시나리오 | test_e2e.py 전체 | pytest + `handle_message()` | 전체 경로 회귀 방지 |
| 권한 모듈 | permissions 테스트 | pytest + parametrize | 조합이 많으므로 parametrize 활용 |

### 17.2 수동/반자동

| 대상 | 테스트 케이스 | 방식 | 이유 |
|------|-------------|------|------|
| LLM 바이패스 코드 리뷰 | TC-89 | 코드 리뷰 / 정적 분석 | 코드 구조 검증은 리뷰가 적합 |
| manifest 필드 검증 | TC-90 | CI에서 JSON 파싱 후 assert | manifest 파일 형식에 따라 구현 |
| Gateway 통합 LLM 바이패스 | TC-91 | 스테이징 환경 수동 확인 | Gateway 측 동작이므로 단독 자동화 불가 |
| Slack DM 실제 전송/수신 | - | 스테이징 수동 | Slack API 연동 최종 확인 |

### 17.3 CI 설정 예시

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: uv run pytest --cov=src/openclaw_todo --cov-report=term-missing -q
```

### 17.4 pytest 마크 권장

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: 순수 단위 테스트 (DB 미사용)",
    "integration: DB 또는 다중 컴포넌트 연동 테스트",
]
```

---

## 18. 스모크 테스트 체크리스트

> 배포/릴리스 전 반드시 통과해야 하는 최소 검증 항목이다.

| # | 항목 | 관련 TC | 확인 |
|---|------|---------|------|
| S-01 | `todo: add 테스트 항목` -> `"Added #N"` 응답 | TC-33 | [ ] |
| S-02 | `todo: list` -> 방금 추가한 항목 표시 | TC-43 | [ ] |
| S-03 | `todo: board` -> BACKLOG 헤더 아래에 항목 표시 | TC-49 | [ ] |
| S-04 | `todo: move <id> /s doing` -> `"moved"` 응답, board DOING 확인 | TC-53 | [ ] |
| S-05 | `todo: done <id>` -> `list`에서 미표시 | TC-57, TC-58 | [ ] |
| S-06 | `todo: drop <id>` -> status=dropped 확인 | TC-59 | [ ] |
| S-07 | `todo: edit <id> 새 제목` -> title 변경 확인 | TC-61 | [ ] |
| S-08 | `todo: project list` -> Inbox 포함 표시 | TC-70 | [ ] |
| S-09 | `todo: project set-private MyProj` -> private 생성/전환 확인 | TC-78 | [ ] |
| S-10 | `todo: project set-shared TeamProj` -> shared 생성 확인 | TC-82 | [ ] |
| S-11 | `/todo add task` -> **무시** (None 반환) | TC-03 | [ ] |
| S-12 | 일반 텍스트 -> **무시** | TC-05 | [ ] |
| S-13 | private project에 타인 assignee -> **경고 후 거부** | TC-37 | [ ] |
| S-14 | 비owner assignee 포함 project의 set-private -> **에러** | TC-75 | [ ] |
| S-15 | `due:02-30` -> ParseError | TC-16 | [ ] |
| S-16 | 신규 DB 경로 실행 -> 파일 생성 + Inbox 존재 | TC-92, TC-93 | [ ] |

실행 방법:
```bash
uv run pytest -q --tb=short
```

---

> 본 테스트 계획서는 PRD v1.2 기준으로 작성되었다. PRD 변경 시 동기화가 필요하다.
