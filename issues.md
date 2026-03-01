# OpenClaw TODO Plugin -- Implementation Issues

> SSOT: Progress and completion are tracked by the Status field in this document (not inferred from code analysis)
> Rule: **1 Issue = 1 PR** (GitHub-first)
> PRD v1.2 WBS(Section 10) 기반 구현 이슈 분해.
> 각 이슈는 0.5~1.5d 단위로 분할. Track/Status/Priority/Estimate/Branch/GH-Issue/PR 컨벤션 준수.
> Date: 2026-02-24

## Conventions
- Track: `product` | `platform`
- Status: `backlog` | `doing` | `waiting` | `done` | `drop`
- Priority: `P0` | `P1` | `P2`
- Estimate: `0.5d` | `1d` | `1.5d`
- Branch: `issue/ISSUE-<NNN>-<slug>`
- GitHub: **/implement creates a GH Issue (if missing) + PR and links them (Closes #N)**

---

## Board

### Backlog
- [x] ISSUE-029: manifest에 command_prefix 및 bypass_llm 필드 추가 _(track: platform, P0, 0.5d)_ → PR #51
- [ ] ISSUE-030: list/board에서 open|done|drop status 필터 토큰 파싱 지원 _(track: product, P1, 1d)_
- [ ] ISSUE-031: help 커맨드 및 빈 todo: 입력 시 상세 도움말 출력 _(track: product, P1, 0.5d)_
- [ ] ISSUE-032: UX 명세에 맞는 응답 메시지 포맷 통일 _(track: product, P0, 1.5d)_
- [ ] ISSUE-033: add 시 존재하지 않는 프로젝트 자동 생성 (shared) _(track: product, P1, 1d)_
- [ ] ISSUE-034: move 커맨드에서 /s 없이 section 직접 지정 지원 _(track: product, P1, 0.5d)_
- [ ] ISSUE-035: 에러 메시지 UX 명세 정합 _(track: product, P1, 1d)_
- [x] ISSUE-036: set-private 에러 메시지에 Slack 멘션 포맷 적용 _(track: product, P2, 0.5d)_ → PR #72
- [ ] ISSUE-037: parser 단위 테스트 보강 -- 엣지 케이스 _(track: platform, P1, 1d)_
- [ ] ISSUE-038: E2E 테스트 보강 -- scope 필터 및 다중 사용자 시나리오 _(track: platform, P1, 1d)_
- [x] ISSUE-039: server.py HTTP endpoint 테스트 보강 _(track: platform, P2, 0.5d)_ → PR #74
- [x] ISSUE-040: bridge TypeScript 빌드 및 npm 패키지 구성 _(track: platform, P1, 1d)_ → PR #70

### Doing

### Waiting

### Done
- [x] ISSUE-001 ~ ISSUE-026: M0~M5 핵심 구현 완료 (상세 내역은 하단 참조)
- [x] ISSUE-027: ruff/black target-version 정합성 수정 -> **재개 (아래 참조)**
- [x] ISSUE-028: Bridge serverUrl config 연동 -> **재개 (아래 참조)**

### Drop

---

## 완료 이슈 요약 (ISSUE-001 ~ ISSUE-026)

> M0~M5 핵심 로직은 모두 구현 완료. 상세 내역은 git history 및 이전 버전의 이 문서 참조.

| Range | Milestone | Summary |
|-------|-----------|---------|
| #1 | M0 | Plugin skeleton + manifest + command prefix |
| #2~#4 | M1 | DB init + migrations + V1 schema + Inbox seed |
| #5~#6 | M2 | Parser tokenizer + Dispatcher routing |
| #7~#14 | M3 | Project resolver, permissions, add/list/board/move/done/drop/edit commands, scope builder + event logger |
| #15~#17 | M4 | project list/set-private/set-shared commands |
| #18~#23 | M5 | Parser/command/E2E/infra/install tests |
| #24~#26 | M6 | Packaging, HTTP bridge server, CI workflow |

---

## 잔여 이슈 상세

---

### ISSUE-029: manifest에 command_prefix 및 bypass_llm 필드 추가
- Track: platform
- PRD-Ref: PRD#1.2, PRD#2.4, PRD#9 (AC 마지막 항목)
- Priority: P0
- Estimate: 0.5d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-029-manifest-bypass-llm`
- GH-Issue: #50
- PR: #51

#### Goal
PRD 1.2/2.4에 따라 `openclaw.plugin.json`에 `command_prefix: "todo:"` 및 `bypass_llm: true` 최상위 필드를 추가하여 Gateway가 LLM 없이 직접 플러그인을 호출하도록 한다.

#### Scope
- In:
  - `bridge/openclaw-todo/openclaw.plugin.json`에 `command_prefix`, `bypass_llm` 필드 추가
  - 기존 `triggers` 블록 유지 (폴백 호환)
- Out:
  - Gateway 측 코드 변경 (Gateway가 이 필드를 소비하는 것은 Gateway 측 책임)

#### Acceptance Criteria (DoD)
- [ ] `openclaw.plugin.json`에 `"command_prefix": "todo:"` 최상위 필드 존재
- [ ] `openclaw.plugin.json`에 `"bypass_llm": true` 최상위 필드 존재
- [ ] 기존 `triggers.dm.pattern` 블록 유지
- [ ] JSON 유효성 검증 통과

#### Tests
- [ ] Unit: `tests/test_manifest.py` -- JSON 로드 후 `command_prefix`, `bypass_llm` 키 존재 및 값 검증
- Test Command: `uv run pytest tests/test_manifest.py -q`

#### Observability (Minimal)
- [ ] Logs: Gateway 로그에서 `bypass_llm=true` 매칭 여부 확인 (Gateway 측)

#### Rollback
- 필드 제거만으로 원복 가능 (기존 triggers로 폴백 동작)

#### Dependencies / Blockers
- 없음 (독립 작업)

---

### ISSUE-030: list/board에서 open|done|drop status 필터 토큰 파싱 지원
- Track: product
- PRD-Ref: PRD#5.2, PRD#5.3
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-030-status-filter-token`
- GH-Issue: #54
- PR: #55

#### Goal
`todo: list done`, `todo: board drop` 처럼 title_tokens에 `open|done|drop` 키워드가 올 때 status 필터로 인식하도록 수정한다.

#### Scope
- In:
  - `src/openclaw_todo/cmd_list.py` -- title_tokens에서 `open|done|drop` 추출
  - `src/openclaw_todo/cmd_board.py` -- 동일 로직 적용
- Out:
  - parser.py 자체는 변경하지 않음 (커맨드 핸들러에서 처리)

#### Acceptance Criteria (DoD)
- [ ] `todo: list done` 입력 시 status=done인 태스크만 반환
- [ ] `todo: list drop` 입력 시 status=dropped인 태스크만 반환
- [ ] `todo: list open` 입력 시 status=open (기본값과 동일)
- [ ] `todo: board done` 동일 동작
- [ ] 기존 `/s done` 방식과 충돌 없음

#### Implementation Notes
- 현재 `cmd_list.py`에서 `parsed.section`이 `done|drop`일 때만 status를 변경하는 로직이 있음
- title_tokens 순회 시 `open|done|drop` 키워드를 별도 변수로 추출하여 status 필터에 반영
- `/s done`과 `done` (title_token)이 동시에 오면 `/s`가 section 필터, title_token이 status 필터

#### Tests
- [ ] Unit: `tests/test_cmd_list.py` -- `list done`, `list drop`, `list open` 각각 검증
- [ ] Unit: `tests/test_cmd_board.py` -- `board done` 검증
- Test Command: `uv run pytest tests/test_cmd_list.py tests/test_cmd_board.py -q`

#### Observability (Minimal)
- [ ] Logs: dispatcher 로그에 적용된 status 필터 값 기록

#### Rollback
- 토큰 인식 코드 제거로 원복 (기존 `/s` 방식만 지원)

#### Dependencies / Blockers
- 없음

---

### ISSUE-031: help 커맨드 및 빈 todo: 입력 시 상세 도움말 출력
- Track: product
- PRD-Ref: UX 명세 7.2
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-031-help-command`
- GH-Issue: #56
- PR: #57

#### Goal
`todo:` 빈 입력 또는 `todo: help` 입력 시 UX 명세에 정의된 커맨드별 상세 도움말을 반환한다.

#### Scope
- In:
  - `src/openclaw_todo/dispatcher.py` -- `USAGE` 문자열을 상세 도움말로 교체
  - `src/openclaw_todo/dispatcher.py` -- `help`를 유효 커맨드로 추가
- Out:
  - 커맨드 실행 로직 변경 없음

#### Acceptance Criteria (DoD)
- [ ] `todo:` (빈 입력) 시 UX 명세 7.2의 상세 도움말 반환
- [ ] `todo: help` 입력 시 동일 도움말 반환
- [ ] `help`가 "Unknown command"로 처리되지 않음
- [ ] 도움말에 모든 커맨드(add, list, board, move, done, drop, edit, project) 포함

#### Tests
- [ ] Unit: `tests/test_plugin.py` -- `handle_message("todo:", ...)` 응답에 `add`, `list`, `board` 포함
- [ ] Unit: `tests/test_dispatcher.py` -- `dispatch("help", ...)` 응답 검증
- Test Command: `uv run pytest tests/test_plugin.py tests/test_dispatcher.py -q`

#### Observability (Minimal)
- [ ] Logs: N/A (단순 문자열 반환)

#### Rollback
- 기존 한 줄짜리 USAGE 문자열로 원복

#### Dependencies / Blockers
- 없음

---

### ISSUE-032: UX 명세에 맞는 응답 메시지 포맷 통일
- Track: product
- PRD-Ref: UX 명세 4.1~4.3, PRD#5.1~5.7
- Priority: P0
- Estimate: 1.5d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-032-ux-response-format`
- GH-Issue: #52
- PR: #53

#### Goal
모든 커맨드 핸들러의 응답 메시지를 UX 명세(ux_spec.md) 4.1~4.3에 정의된 포맷으로 통일한다.

#### Scope
- In:
  - `src/openclaw_todo/cmd_add.py` -- 응답 포맷 수정
  - `src/openclaw_todo/cmd_done_drop.py` -- project/title 정보 포함, 포맷 수정
  - `src/openclaw_todo/cmd_move.py` -- title 포함, 포맷 수정
  - `src/openclaw_todo/cmd_edit.py` -- 전체 태스크 상태 표시
  - `src/openclaw_todo/cmd_list.py` -- 헤더/footer 포맷 수정
  - `src/openclaw_todo/cmd_board.py` -- 헤더 포맷 수정
- Out:
  - 에러 메시지는 ISSUE-035에서 별도 처리

#### Acceptance Criteria (DoD)
- [ ] `add` 응답: `"Added #N (project/section) due:X assignees:Y -- title"` 포맷 (PRD 5.1)
- [ ] `done` 응답: `"Done #N (project) -- title"` 포맷 (UX 4.3)
- [ ] `drop` 응답: `"Dropped #N (project) -- title"` 포맷 (UX 4.3)
- [ ] `move` 응답: `"Moved #N to section (project) -- title"` 포맷 (UX 4.3)
- [ ] `edit` 응답: `"Edited #N (project/section) due:X assignees:Y -- title"` 포맷 (UX 4.3)
- [ ] `list` 헤더: `"TODO List (scope / status) [/p project] -- N tasks"` 포맷 (UX 6.2)
- [ ] `list` footer: `"Showing N of M. Use limit:N to see more."` limit 초과 시 (UX 6.2)
- [ ] `board` 헤더: `"Board (scope / status) [/p project]"` 포맷 (UX 5.2)

#### Implementation Notes
- 현재 `cmd_done_drop.py`의 `_close_task()`는 title/project를 DB에서 조회하지 않음 -- 추가 SELECT 필요
- 현재 `cmd_move.py`는 title을 응답에 포함하지 않음 -- 기존 SELECT에서 title 가져오기
- `cmd_list.py`는 total count를 위해 COUNT 쿼리 또는 limit+1 페치 필요
- 기존 테스트의 assertion 문자열도 함께 업데이트 필요

#### Tests
- [ ] Unit: 기존 `tests/test_cmd_*.py`의 응답 assertion을 새 포맷에 맞게 업데이트
- [ ] Integration: `tests/test_e2e.py`의 assertion 업데이트
- Test Command: `uv run pytest -q`

#### Observability (Minimal)
- [ ] Logs: 변경 없음 (표현 계층만 수정)

#### Rollback
- git revert로 이전 메시지 포맷 원복

#### Dependencies / Blockers
- ISSUE-035 (에러 메시지)와 병행 시 코드 충돌 가능 -- 순차 작업 권장

---

### ISSUE-033: add 시 존재하지 않는 프로젝트 자동 생성 (shared)
- Track: product
- PRD-Ref: UX 명세 7.6, PRD#5.1
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-033-auto-create-project`
- GH-Issue: #58
- PR: #59

#### Goal
`todo: add ... /p NewProject`에서 존재하지 않는 프로젝트명을 지정하면 shared 프로젝트를 자동 생성하고 태스크를 추가한다.

#### Scope
- In:
  - `src/openclaw_todo/cmd_add.py` -- `ProjectNotFoundError` 발생 시 shared 프로젝트 자동 생성
  - 응답에 프로젝트 자동 생성 안내 추가
- Out:
  - `list`, `board`, `move`, `edit` 등에서는 자동 생성하지 않음 (add 전용)
  - `project_resolver.py` 자체는 변경하지 않음 (cmd_add에서 처리)

#### Acceptance Criteria (DoD)
- [ ] `todo: add task /p NewProject` 시 `NewProject` shared 프로젝트 자동 생성
- [ ] 응답에 프로젝트 자동 생성 안내 포함 (`Project "NewProject" was created (shared).`)
- [ ] 이미 존재하는 프로젝트명이면 기존 동작 유지
- [ ] 자동 생성된 프로젝트가 shared, owner_user_id=NULL인지 확인
- [ ] private 이름 충돌 시 private 우선 resolve 규칙 유지

#### Tests
- [ ] Unit: `tests/test_cmd_add.py` -- 미존재 프로젝트로 add 시 프로젝트 생성 + 태스크 생성
- [ ] Unit: `tests/test_cmd_add.py` -- 자동 생성된 프로젝트의 visibility=shared 확인
- [ ] Integration: `tests/test_e2e.py` -- 전체 흐름 테스트
- Test Command: `uv run pytest tests/test_cmd_add.py tests/test_e2e.py -q`

#### Observability (Minimal)
- [ ] Logs: `event_logger`에 `project.auto_create` 이벤트 기록

#### Rollback
- `cmd_add.py`에서 자동 생성 로직 제거, 기존 에러 반환으로 원복

#### Dependencies / Blockers
- 없음

---

### ISSUE-034: move 커맨드에서 /s 없이 section 직접 지정 지원
- Track: product
- PRD-Ref: PRD#5.4
- Priority: P1
- Estimate: 0.5d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-034-move-section-shorthand`
- GH-Issue: #60
- PR: #61

#### Goal
PRD 5.4 문법 `todo: move <id> <section>`을 지원한다. 현재는 `todo: move 50 /s doing`만 동작하고 `todo: move 50 doing`은 동작하지 않는다.

#### Scope
- In:
  - `src/openclaw_todo/cmd_move.py` -- title_tokens에서 유효한 section enum 값 추출
- Out:
  - parser.py 변경 없음

#### Acceptance Criteria (DoD)
- [ ] `todo: move 50 doing` 정상 동작 (section=doing으로 이동)
- [ ] `todo: move 50 /s doing` 기존 방식도 유지
- [ ] 무효한 section 입력 시 에러 메시지 반환
- [ ] section 없이 `todo: move 50` 입력 시 적절한 에러

#### Implementation Notes
- `cmd_move.py`에서 `parsed.section`이 None일 때 `parsed.title_tokens`에서 유효한 section 검색
- VALID_SECTIONS = `{backlog, doing, waiting, done, drop}`과 매칭

#### Tests
- [ ] Unit: `tests/test_cmd_move.py` -- `/s` 없이 section 직접 지정 테스트
- [ ] Unit: `tests/test_cmd_move.py` -- 잘못된 section 입력 테스트
- Test Command: `uv run pytest tests/test_cmd_move.py -q`

#### Observability (Minimal)
- [ ] Logs: 기존 로그에 target_section 이미 포함

#### Rollback
- title_tokens 파싱 로직 제거, `/s` 전용으로 원복

#### Dependencies / Blockers
- 없음

---

### ISSUE-035: 에러 메시지 UX 명세 정합
- Track: product
- PRD-Ref: UX 명세 3.1~3.5
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: pillip
- Branch: `issue/ISSUE-035-error-message-alignment`
- GH-Issue: #62
- PR: #63

#### Goal
UX 명세 3.1~3.5에 정의된 에러 메시지 패턴과 현재 코드의 에러 메시지를 일치시킨다.

#### Scope
- In:
  - 모든 커맨드 핸들러의 에러 응답 문자열 수정
  - `src/openclaw_todo/dispatcher.py` -- unknown command 메시지
  - `src/openclaw_todo/parser.py` -- parse error 메시지
  - `src/openclaw_todo/cmd_*.py` -- 각 핸들러 에러 메시지
- Out:
  - 성공 메시지 포맷은 ISSUE-032에서 처리

#### Acceptance Criteria (DoD)
- [ ] unknown command: `"Unknown command. Available: add, list, board, move, done, drop, edit, project"`
- [ ] title 누락: `"Title is required. Usage: todo: add <title> [options]"`
- [ ] task ID 누락: `"Task ID is required. Usage: todo: <command> <id>"`
- [ ] invalid task ID: `"Invalid task ID \"<input>\". Must be a number."`
- [ ] task not found: `"Task #<id> not found."`
- [ ] invalid section: `"Invalid section \"<input>\". Must be one of: backlog, doing, waiting, done, drop"`
- [ ] permission denied: `"You don't have permission to modify task #<id>."`
- [ ] private assignee 거부: UX 명세 3.4 한국어 메시지 준수
- [ ] set-private 검증 실패: UX 명세 3.3 포맷 준수

#### Tests
- [ ] Unit: 기존 에러 케이스 테스트의 assertion 문자열 업데이트
- [ ] Unit: 에러 메시지 패턴별 단위 테스트 추가
- Test Command: `uv run pytest -q`

#### Observability (Minimal)
- [ ] Logs: 변경 없음

#### Rollback
- git revert

#### Dependencies / Blockers
- ISSUE-032와 병행 시 충돌 주의 -- 순차 작업 권장 (ISSUE-032 이후)

---

### ISSUE-036: set-private 에러 메시지에 Slack 멘션 포맷 적용
- Track: product
- PRD-Ref: PRD#3.4, UX 명세 3.3
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-036-set-private-mention-format`
- GH-Issue: #71
- PR: #72

#### Goal
`cmd_project_set_private.py`의 에러 메시지에서 assignee를 `<@UXXXX>` Slack 멘션 포맷으로 표시하고, task별 assignee를 그룹화하여 PRD 3.4 에러 예시와 일치시킨다.

#### Scope
- In:
  - `src/openclaw_todo/cmd_project_set_private.py` -- `_convert_shared_to_private()` 에러 메시지 수정
- Out:
  - 성공 메시지는 변경 없음

#### Acceptance Criteria (DoD)
- [ ] 에러 메시지에 assignee가 `<@UXXXX>` 포맷으로 표시
- [ ] task별 assignee 그룹화: `#12 assignees:<@U2>, #18 assignees:<@U3>`
- [ ] 최대 10개 task 표시 유지
- [ ] 10개 초과 시 `... and N more tasks` 접미사

#### Tests
- [ ] Unit: `tests/test_cmd_project_set_private.py` -- 에러 메시지에 `<@` 포맷 포함 확인
- Test Command: `uv run pytest tests/test_cmd_project_set_private.py -q`

#### Observability (Minimal)
- [ ] Logs: 기존 로그에 violation 수 포함

#### Rollback
- 포맷 변경 원복

#### Dependencies / Blockers
- ISSUE-035 이후 권장 (에러 메시지 통일 후 세부 포맷 조정)

---

### ISSUE-037: parser 단위 테스트 보강 -- 엣지 케이스
- Track: platform
- PRD-Ref: UX 명세 7.7~7.9
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-037-parser-test-edge-cases`
- GH-Issue: #64
- PR: #65

#### Goal
UX 명세 7.7~7.9에 정의된 엣지 케이스에 대한 parser 테스트를 보강한다.

#### Scope
- In:
  - `tests/test_parser.py` -- 엣지 케이스 테스트 추가
- Out:
  - parser.py 자체 수정은 테스트 실패 시에만 (버그 발견 시)

#### Acceptance Criteria (DoD)
- [ ] 대소문자 처리: `parse("ADD task")` -> command="add"
- [ ] section 대소문자: `parse("add /s DOING task")` -> section="doing"
- [ ] 무효 날짜: `due:02-29` (비윤년), `due:00-01`, `due:12-32` -> ParseError
- [ ] 연속 공백 제목 테스트
- [ ] due 클리어: `due:-` -> DUE_CLEAR
- [ ] 빈 title: `parse("add")` -> title_tokens=[]

#### Tests
- [ ] Unit: `tests/test_parser.py`에 위 케이스 추가
- Test Command: `uv run pytest tests/test_parser.py -q`

#### Observability (Minimal)
- [ ] Logs: N/A

#### Rollback
- 테스트 코드 제거 (프로덕션 코드 무영향)

#### Dependencies / Blockers
- ISSUE-030 이후 권장 (status 필터 토큰이 추가되면 관련 테스트도 포함)

---

### ISSUE-038: E2E 테스트 보강 -- scope 필터 및 다중 사용자 시나리오
- Track: platform
- PRD-Ref: PRD#5.2 scope, PRD#3.2 이름 충돌
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-038-e2e-scope-multiuser`
- GH-Issue: #66
- PR: #67

#### Goal
E2E 테스트에 scope 필터 및 다중 사용자 시나리오를 추가하여 커버리지를 높인다.

#### Scope
- In:
  - `tests/test_e2e.py` -- 새 시나리오 클래스 추가
- Out:
  - 프로덕션 코드 변경 없음 (테스트만)

#### Acceptance Criteria (DoD)
- [ ] `list <@U002>` 특정 유저 scope 테스트 통과
- [ ] 다중 사용자 shared 프로젝트 작업 테스트 통과
- [ ] assignee 기반 권한 (U002가 할당받은 task를 수정) 테스트 통과
- [ ] private/shared 이름 충돌 resolve (private 우선) 테스트 통과

#### Tests
- [ ] Integration: `tests/test_e2e.py`에 새 시나리오 클래스 추가
- Test Command: `uv run pytest tests/test_e2e.py -q`

#### Observability (Minimal)
- [ ] Logs: N/A

#### Rollback
- 테스트 코드 제거

#### Dependencies / Blockers
- ISSUE-030, ISSUE-032, ISSUE-033, ISSUE-034 이후 권장 (기능 변경 반영 후 테스트)

---

### ISSUE-039: server.py HTTP endpoint 테스트 보강
- Track: platform
- PRD-Ref: N/A (품질 향상)
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-039-server-test-coverage`
- GH-Issue: #73
- PR: #74

#### Goal
`test_server.py`의 커버리지를 확인하고 누락된 시나리오를 추가한다.

#### Scope
- In:
  - `tests/test_server.py` -- 테스트 보강
- Out:
  - server.py 코드 변경 없음

#### Acceptance Criteria (DoD)
- [ ] `GET /health` 200 응답 테스트
- [ ] `POST /message` 정상 요청 테스트
- [ ] `POST /message` 누락 필드 (422) 테스트
- [ ] `POST /message` 잘못된 JSON (400) 테스트
- [ ] `POST /message` body 초과 (413) 테스트
- [ ] 알 수 없는 경로 (404) 테스트

#### Tests
- [ ] Unit: `tests/test_server.py` 보강
- Test Command: `uv run pytest tests/test_server.py -q`

#### Observability (Minimal)
- [ ] Logs: N/A

#### Rollback
- 테스트 코드 제거

#### Dependencies / Blockers
- 없음 (독립 작업)

---

### ISSUE-027 (재개): ruff/black target-version 정합성 수정
- Track: platform
- PRD-Ref: PR #49 review follow-up
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-027-lint-target-version`
- GH-Issue: #75
- PR: #76

#### Goal
`pyproject.toml`의 `requires-python >= 3.10`과 ruff/black target-version을 `py310`으로 통일한다.

#### Acceptance Criteria (DoD)
- [ ] `tool.ruff.target-version` = `"py310"`
- [ ] `tool.black.target-version` = `["py310"]`
- [ ] `uv run ruff check .` 통과
- [ ] `uv run black --check .` 통과

#### Tests
- [ ] Smoke: CI에서 ruff/black 체크 통과 확인
- Test Command: `uv run ruff check . && uv run black --check .`

#### Observability (Minimal)
- [ ] Logs: N/A

#### Rollback
- `py311`로 원복

#### Dependencies / Blockers
- 없음

---

### ISSUE-028 (재개): Bridge serverUrl config 연동
- Track: platform
- PRD-Ref: PR #49 review follow-up
- Priority: P2
- Estimate: 0.5d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-028-bridge-config`
- GH-Issue: #77
- PR: #78

#### Goal
`bridge/openclaw-todo/index.ts`에서 plugin config의 `serverUrl`을 참조하거나, env var 우선 정책을 문서화한다.

#### Acceptance Criteria (DoD)
- [ ] `index.ts`에서 plugin config의 `serverUrl`을 우선 사용, env var 폴백
- [ ] config/env var 모두 없으면 `http://127.0.0.1:8200` 기본값
- [ ] 사용 중인 URL 출처를 로그에 출력

#### Tests
- [ ] Smoke: TypeScript 빌드 성공 확인 (`npm run build`)
- Test Command: `cd bridge/openclaw-todo && npm run build`

#### Observability (Minimal)
- [ ] Logs: 서버 URL 출처(config vs env) 로그 출력

#### Rollback
- 기존 env var 전용 로직으로 원복

#### Dependencies / Blockers
- 없음

---

### ISSUE-040: bridge TypeScript 빌드 및 npm 패키지 구성
- Track: platform
- PRD-Ref: PRD#10 M6
- Priority: P1
- Estimate: 1d
- Status: done
- Owner: claude
- Branch: `issue/ISSUE-040-bridge-npm-package`
- GH-Issue: #69
- PR: #70

#### Goal
bridge 디렉토리의 TypeScript 코드를 빌드 가능한 npm 패키지로 구성한다.

#### Scope
- In:
  - `bridge/openclaw-todo/package.json` -- `files` 필드 추가
  - `bridge/openclaw-todo/tsconfig.json` -- 빌드 설정 확인
  - `.npmignore` 또는 `files` 필드로 배포 대상 명시
- Out:
  - 실제 npm publish (별도 릴리스 프로세스)

#### Acceptance Criteria (DoD)
- [ ] `cd bridge/openclaw-todo && npm install && npm run build` 성공
- [ ] `dist/index.js` 생성 확인
- [ ] `package.json`에 `files` 필드로 배포 대상 명시
- [ ] 소스/설정 파일이 배포 대상에서 제외

#### Tests
- [ ] Smoke: CI에서 TypeScript 빌드 성공 확인
- Test Command: `cd bridge/openclaw-todo && npm install && npm run build`

#### Observability (Minimal)
- [ ] Logs: 빌드 아티팩트 크기 확인

#### Rollback
- package.json 변경 원복

#### Dependencies / Blockers
- ISSUE-029, ISSUE-028 이후 권장

---

## 이슈 의존성 그래프

```
Phase 1 (핵심 기능 정합 -- P0/P1):
  #029 (manifest)       -- 독립
  #030 (status filter)  -- 독립
  #032 (response format)-- 독립, #035와 순차
  #033 (auto-create)    -- 독립
  #034 (move shorthand) -- 독립

Phase 2 (UX 정합 -- P1):
  #031 (help command)   -- 독립
  #035 (error messages) -- #032 이후
  #036 (mention format) -- #035 이후

Phase 3 (테스트 보강 -- P1/P2):
  #037 (parser tests)   -- #030 이후
  #038 (e2e tests)      -- #030, #032, #033, #034 이후
  #039 (server tests)   -- 독립

Phase 4 (패키징/정리 -- P2):
  #027 (lint version)   -- 독립
  #028 (bridge config)  -- 독립
  #040 (npm build)      -- #029, #028 이후
```

## 진행 현황 요약

| Milestone | 이슈 수 | Done | Backlog |
|-----------|---------|------|---------|
| M0 | 2 | 2 | 0 |
| M1 | 3 | 3 | 0 |
| M2 | 4 | 2 | 2 (#030, #031) |
| M3 | 11 | 7 | 4 (#032, #033, #034, #035) |
| M4 | 4 | 3 | 1 (#036) |
| M5 | 8 | 5 | 3 (#037, #038, #039) |
| M6 | 8 | 4 | 4 (#027, #028, #029, #040) |
| **Total** | **40** | **26** | **14** |
