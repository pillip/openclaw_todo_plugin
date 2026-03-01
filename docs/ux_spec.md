# OpenClaw TODO Plugin — UX 명세서

> Version 2.0 | 2026-02-24
> PRD v1.2 (DM 기반) 기준 작성

---

## 목차

1. [사용자 인터랙션 흐름](#1-사용자-인터랙션-흐름)
2. [커맨드별 예시와 기대 응답](#2-커맨드별-예시와-기대-응답)
3. [에러 메시지 패턴](#3-에러-메시지-패턴)
4. [성공 메시지 패턴](#4-성공-메시지-패턴)
5. [Board 출력 포맷](#5-board-출력-포맷)
6. [List 출력 포맷](#6-list-출력-포맷)
7. [엣지 케이스 UX](#7-엣지-케이스-ux)

---

## 1. 사용자 인터랙션 흐름

### 1.1 진입점

사용자는 OpenClaw Slack 앱(봇)과의 **1:1 DM 채널**에서 `/todo` 접두사로 메시지를 보낸다.

```
사용자 → Slack DM → "/todo add 장보기"
                         ↓
              OpenClaw Gateway (command_prefix 매칭)
                         ↓ (LLM 바이패스)
              플러그인 handle_message() 직접 호출
                         ↓
              응답 메시지 → Slack DM
```

### 1.2 메시지 인식 규칙

| 메시지 패턴 | 봇 동작 |
|---|---|
| `/todo`로 시작 | 커맨드로 파싱하여 처리 |
| 그 외 모든 메시지 | 무시 (응답 없음) |

### 1.3 응답 방식

- 봇은 동일 DM 채널에 일반 메시지로 응답한다.
- v1에서는 인터랙티브 버튼, 모달, 확인 다이얼로그를 사용하지 않는다.
- 모든 커맨드는 수신 즉시 실행되거나 거부된다 (확인 절차 없음).

### 1.4 설계 원칙

- **모호함 제로**: 모든 커맨드는 정확히 하나의 응답을 생성한다. 성공/실패를 항상 알 수 있다.
- **최소 타이핑**: 기본값(project=`Inbox`, section=`backlog`, assignee=sender)이 적용되므로 대부분 제목만 입력하면 된다.
- **스캔 가능한 출력**: 고정 이모지 접두사, 일관된 포맷으로 빠르게 훑어볼 수 있다.
- **명시적 실패**: 잘못된 입력은 명확한 사유와 함께 거부된다. 부분 적용 없음.

---

## 2. 커맨드별 예시와 기대 응답

### 2.1 `/todo add` — 태스크 생성

**문법**:
```
/todo add <title> [<@USER> ...] [/p <project>] [/s <section>] [due:YYYY-MM-DD|MM-DD]
```

**기본값**:
| 파라미터 | 기본값 |
|---|---|
| project | `Inbox` |
| section | `backlog` |
| assignees | sender (본인) |
| due | 없음 (NULL) |

**예시 1 — 최소 입력**:
```
입력:  /todo add 장보기
응답:  ✅ Added #42 (Inbox/backlog) due:- assignees:<@U1234> — 장보기
```

**예시 2 — 전체 옵션 사용**:
```
입력:  /todo add 로그인 버그 수정 <@U5678> /p Backend /s doing due:2026-03-15
응답:  ✅ Added #43 (Backend/doing) due:2026-03-15 assignees:<@U5678> — 로그인 버그 수정
```

**예시 3 — 다중 담당자**:
```
입력:  /todo add PR 리뷰 <@U5678> <@U9999> /p Frontend
응답:  ✅ Added #44 (Frontend/backlog) due:- assignees:<@U5678>, <@U9999> — PR 리뷰
```

**예시 4 — 연도 생략 due**:
```
입력:  /todo add 보고서 작성 due:03-15
응답:  ✅ Added #45 (Inbox/backlog) due:2026-03-15 assignees:<@U1234> — 보고서 작성
```

---

### 2.2 `/todo list` — 태스크 목록 조회

**문법**:
```
/todo list [mine|all|<@USER>] [/p <project>] [/s <section>] [open|done|drop] [limit:N]
```

**기본값**:
| 파라미터 | 기본값 |
|---|---|
| scope | `mine` |
| status | `open` |
| limit | 30 |

**예시 1 — 기본 조회 (내 태스크)**:
```
입력:  /todo list
응답:
📋 TODO List (mine / open) — 3 tasks

#50  due:2026-02-21  (Backend/doing)    <@U1234>          Deploy hotfix
#48  due:2026-03-01  (Inbox/backlog)    <@U1234>          장보기
#45  due:-           (Frontend/waiting) <@U1234>, <@U5678> PR 리뷰

Showing 3 of 3. Use limit:N to see more.
```

**예시 2 — 프로젝트 필터링**:
```
입력:  /todo list /p Backend
응답:
📋 TODO List (mine / open) /p Backend — 1 task

#50  due:2026-02-21  (Backend/doing)  <@U1234>  Deploy hotfix

Showing 1 of 1. Use limit:N to see more.
```

**예시 3 — 전체 범위 조회**:
```
입력:  /todo list all
응답:
📋 TODO List (all / open) — 5 tasks
...
```

**예시 4 — 빈 결과**:
```
입력:  /todo list /p Backend /s waiting
응답:
📋 TODO List (mine / open) /p Backend /s waiting — 0 tasks

No tasks found.
```

**scope 동작**:
| scope | 조회 범위 |
|---|---|
| `mine` (기본) | sender가 assignee에 포함된 태스크 |
| `all` | shared 전체 + sender의 private 프로젝트 (타인 private는 제외) |
| `<@USER>` | 해당 유저가 assignee인 태스크 (shared + sender==해당유저면 private 포함) |

**정렬 규칙**:
1. due 있는 것 우선
2. due 오름차순
3. id 내림차순

---

### 2.3 `/todo board` — 칸반 보드 뷰

**문법**:
```
/todo board [mine|all|<@USER>] [/p <project>] [open|done|drop] [limitPerSection:N]
```

**기본값**:
| 파라미터 | 기본값 |
|---|---|
| scope | `mine` |
| status | `open` |
| limitPerSection | 10 |

**예시**:
```
입력:  /todo board /p Backend
응답:
📊 Board (mine / open) /p Backend

— BACKLOG (2) —
#50  due:2026-03-10  <@U1234>  CI 파이프라인 구축
#47  due:-           <@U1234>  마이그레이션 스크립트 작성

— DOING (1) —
#51  due:2026-02-22  <@U1234>  Deploy hotfix

— WAITING (0) —
(empty)

— DONE (0) —
(empty)

— DROP (0) —
(empty)
```

**섹션 규칙**:
- 출력 순서는 항상 고정: BACKLOG → DOING → WAITING → DONE → DROP
- 항목이 0개인 섹션도 `(empty)`로 표시하여 전체 보드 구조를 유지
- 각 섹션 헤더에 항목 수를 표시
- `limitPerSection` 초과 시 마지막 항목 아래에 `... and N more` 표시

---

### 2.4 `/todo move` — 태스크 섹션 이동

**문법**:
```
/todo move <id> <section>
```

**유효 섹션**: `backlog`, `doing`, `waiting`, `done`, `drop`

**예시**:
```
입력:  /todo move 50 doing
응답:  ➡️ Moved #50 to doing (Backend) — Deploy hotfix
```

**권한**:
- private 프로젝트: owner만 가능
- shared 프로젝트: assignee 또는 created_by만 가능

---

### 2.5 `/todo done` — 태스크 완료 처리

**문법**:
```
/todo done <id>
```

**동작**: section=`done`, status=`done`, `closed_at` 기록

**예시**:
```
입력:  /todo done 50
응답:  ✅ Done #50 (Backend) — Deploy hotfix
```

---

### 2.6 `/todo drop` — 태스크 드롭(취소)

**문법**:
```
/todo drop <id>
```

**동작**: section=`drop`, status=`dropped`, `closed_at` 기록

**예시**:
```
입력:  /todo drop 50
응답:  🗑️ Dropped #50 (Backend) — Deploy hotfix
```

---

### 2.7 `/todo edit` — 태스크 수정

**문법**:
```
/todo edit <id> [<new title>] [<@USER> ...] [/p <project>] [/s <section>] [due:YYYY-MM-DD|MM-DD|due:-]
```

**규칙**:
- `<@USER>` 멘션이 있으면 assignees를 **완전 교체** (추가가 아님)
- `due:-`는 due를 NULL로 클리어
- 옵션 토큰(`/p`, `/s`, `due:`, `<@...>`) 이전의 텍스트가 새 title (비어 있으면 title 변경 없음)
- 명시하지 않은 필드는 기존 값 유지

**예시 1 — 제목과 due 변경**:
```
입력:  /todo edit 50 Deploy hotfix v2 due:2026-03-01
응답:  ✏️ Edited #50 (Backend/doing) due:2026-03-01 assignees:<@U1234> — Deploy hotfix v2
```

**예시 2 — 담당자 교체**:
```
입력:  /todo edit 50 <@U5678> <@U9999>
응답:  ✏️ Edited #50 (Backend/doing) due:2026-03-01 assignees:<@U5678>, <@U9999> — Deploy hotfix v2
```

**예시 3 — due 클리어**:
```
입력:  /todo edit 50 due:-
응답:  ✏️ Edited #50 (Backend/doing) due:- assignees:<@U5678>, <@U9999> — Deploy hotfix v2
```

---

### 2.8 `/todo project list` — 프로젝트 목록 조회

**문법**:
```
/todo project list
```

**예시 — 프로젝트가 있는 경우**:
```
입력:  /todo project list
응답:
📁 Projects

Shared:
  - Inbox (12 tasks)
  - Backend (5 tasks)
  - Frontend (8 tasks)

Private (yours):
  - Personal (3 tasks)
  - Side Project (1 task)
```

**예시 — private 프로젝트가 없는 경우**:
```
입력:  /todo project list
응답:
📁 Projects

Shared:
  - Inbox (0 tasks)

Private (yours):
  (none)
```

---

### 2.9 `/todo project set-private` — 프로젝트 비공개 전환

**문법**:
```
/todo project set-private <name>
```

**Case A — 프로젝트가 존재하지 않음** (신규 private 생성):
```
입력:  /todo project set-private Personal
응답:  🔒 Created private project "Personal".
```

**Case B — 이미 sender의 private 프로젝트임**:
```
입력:  /todo project set-private Personal
응답:  🔒 Project "Personal" is already private.
```

**Case C — shared 프로젝트를 private로 전환 (성공)**:
```
입력:  /todo project set-private MyProject
응답:  🔒 Project "MyProject" is now private.
```

**Case D — shared 프로젝트를 private로 전환 (실패 — 비owner assignee 존재)**:
```
입력:  /todo project set-private Biz
응답:  ❌ Cannot set project "Biz" to private: found tasks assigned to non-owner users.
       e.g. #12 assignees:<@U2222>, #18 assignees:<@U3333>
       Please reassign or remove these assignees first.
```

- 위반 태스크는 최대 10개까지 표시
- 10개 초과 시: `... and N more tasks with external assignees.` 추가

---

### 2.10 `/todo project set-shared` — 프로젝트 공유 전환

**문법**:
```
/todo project set-shared <name>
```

**Case A — shared 프로젝트가 이미 존재**:
```
입력:  /todo project set-shared Backend
응답:  🌐 Project "Backend" is already shared.
```

**Case B — 신규 shared 프로젝트 생성 또는 private에서 전환 성공**:
```
입력:  /todo project set-shared NewProject
응답:  🌐 Project "NewProject" is now shared.
```

**Case C — shared 이름 충돌**:
```
입력:  /todo project set-shared Backend
응답:  ❌ A shared project named "Backend" already exists.
```

---

## 3. 에러 메시지 패턴

### 3.1 입력 검증 에러

| 상황 | 에러 메시지 |
|---|---|
| 알 수 없는 커맨드 | `❌ Unknown command. Available: add, list, board, move, done, drop, edit, project` |
| add에 제목 누락 | `❌ Title is required. Usage: /todo add <title> [options]` |
| 태스크 ID 누락 | `❌ Task ID is required. Usage: /todo <command> <id>` |
| 태스크 ID가 숫자가 아님 | `❌ Invalid task ID "<input>". Must be a number.` |
| 태스크를 찾을 수 없음 | `❌ Task #<id> not found.` |
| 잘못된 섹션 이름 | `❌ Invalid section "<input>". Must be one of: backlog, doing, waiting, done, drop` |
| 잘못된 날짜 형식 | `❌ Invalid date "<input>". Use YYYY-MM-DD or MM-DD.` |
| 존재하지 않는 날짜 (예: 02-30) | `❌ Invalid date "02-30". This date does not exist.` |
| /p 뒤에 프로젝트 이름 누락 | `❌ Project name is required after /p.` |

### 3.2 권한 에러

| 상황 | 에러 메시지 |
|---|---|
| 타인의 private 프로젝트 접근 시도 | `❌ Project "<name>" not found.` (존재 여부를 의도적으로 숨김) |
| 권한 없는 태스크 수정 시도 | `❌ You don't have permission to modify task #<id>.` |

### 3.3 set-private 검증 에러

shared 프로젝트를 private로 전환할 때 비owner assignee가 존재하는 경우:
```
❌ Cannot set project "<name>" to private: found tasks assigned to non-owner users.
e.g. #12 assignees:<@U2222>, #18 assignees:<@U3333>, #21 assignees:<@U4444>
Please reassign or remove these assignees first.
```
- 위반 태스크 최대 10개 표시
- 10개 초과 시: `... and N more tasks with external assignees.`

### 3.4 private 프로젝트 assignee 거부

private 프로젝트에 owner가 아닌 유저를 assignee로 지정하려 할 때 (add 또는 edit):
```
⚠️ Private 프로젝트("<name>")는 owner만 볼 수 있어요. 다른 담당자(<@U...>)를 지정할 수 없습니다.
(요청이 적용되지 않았습니다.)
```

### 3.5 프로젝트 이름 충돌

| 상황 | 에러 메시지 |
|---|---|
| 기존 shared 이름과 충돌 | `❌ A shared project named "<name>" already exists.` |
| 동일 owner의 private 이름 충돌 | `❌ You already have a private project named "<name>".` |

---

## 4. 성공 메시지 패턴

### 4.1 이모지 및 동사 매핑

| 액션 | 이모지 | 동사/키워드 |
|---|---|---|
| add | ✅ | Added |
| list | 📋 | TODO List |
| board | 📊 | Board |
| move | ➡️ | Moved |
| done | ✅ | Done |
| drop | 🗑️ | Dropped |
| edit | ✏️ | Edited |
| project list | 📁 | Projects |
| set-private | 🔒 | (상황에 따라 다름) |
| set-shared | 🌐 | (상황에 따라 다름) |
| 에러 | ❌ | (에러 메시지) |
| 경고/거부 | ⚠️ | (경고 메시지) |
| 정보성 안내 | ℹ️ | (안내 메시지) |

### 4.2 태스크 라인 포맷

성공 응답에서 태스크 정보를 표시하는 표준 포맷:
```
#<id> (<project>/<section>) due:<YYYY-MM-DD|-> assignees:<@U...>[, <@U...>] — <title>
```

### 4.3 단일 태스크 액션 응답 포맷

```
✅ Added #123 (Inbox/backlog) due:- assignees:<@U1234> — 장보기
➡️ Moved #123 to doing (Inbox) — 장보기
✅ Done #123 (Inbox) — 장보기
🗑️ Dropped #123 (Inbox) — 장보기
✏️ Edited #123 (Inbox/backlog) due:2026-03-15 assignees:<@U1234> — 장보기 수정
```

### 4.4 프로젝트 자동 생성 안내

존재하지 않는 프로젝트명으로 `/todo add`를 실행하면 shared 프로젝트를 자동 생성하고 안내:
```
✅ Added #55 (NewProject/backlog) due:- assignees:<@U1234> — 태스크 제목
ℹ️ Project "NewProject" was created (shared).
```

---

## 5. Board 출력 포맷

### 5.1 전체 구조 예시

```
📊 Board (mine / open) /p Backend

— BACKLOG (2) —
#50  due:2026-03-10  <@U1234>  CI 파이프라인 구축
#47  due:-           <@U1234>  마이그레이션 스크립트 작성

— DOING (1) —
#51  due:2026-02-22  <@U1234>  Deploy hotfix

— WAITING (0) —
(empty)

— DONE (0) —
(empty)

— DROP (0) —
(empty)
```

### 5.2 포맷 규칙

- **헤더**: `📊 Board (<scope> / <status>) [/p <project>]`
- **섹션 구분**: `— <SECTION_NAME> (<count>) —`
- **섹션 순서**: BACKLOG → DOING → WAITING → DONE → DROP (항상 고정)
- **빈 섹션**: `(empty)`로 표시 — 보드 구조의 완전성 유지
- **항목 포맷**: `#<id>  due:<YYYY-MM-DD|->  <assignees>  <title>`
- **limit 초과 시**: 해당 섹션 마지막에 `... and N more` 표시

### 5.3 limitPerSection 초과 예시

```
— BACKLOG (15) —
#60  due:2026-03-01  <@U1234>  태스크 1
#59  due:2026-03-02  <@U1234>  태스크 2
...
#51  due:2026-03-10  <@U1234>  태스크 10
... and 5 more
```

---

## 6. List 출력 포맷

### 6.1 전체 구조 예시

```
📋 TODO List (mine / open) — 3 tasks

#50  due:2026-02-21  (Backend/doing)    <@U1234>          Deploy hotfix
#48  due:2026-03-01  (Inbox/backlog)    <@U1234>          장보기
#45  due:-           (Frontend/waiting) <@U1234>, <@U5678> PR 리뷰

Showing 3 of 3. Use limit:N to see more.
```

### 6.2 포맷 규칙

- **헤더**: `📋 TODO List (<scope> / <status>) [/p <project>] [/s <section>] — <count> tasks`
- **항목 포맷**: `#<id>  due:<YYYY-MM-DD|->  (<project>/<section>)  <assignees>  <title>`
- **정렬**: due 있는 것 우선 → due 오름차순 → id 내림차순
- **limit 초과 시**: `Showing <displayed> of <total>. Use limit:N to see more.`

### 6.3 빈 결과 예시

```
📋 TODO List (mine / open) — 0 tasks

No tasks found.
```

### 6.4 scope별 필터 예시

```
입력:  /todo list all /p Backend done
응답:
📋 TODO List (all / done) /p Backend — 2 tasks

#40  due:2026-02-10  (Backend/done)  <@U1234>  API 리팩토링
#38  due:2026-02-05  (Backend/done)  <@U5678>  DB 마이그레이션

Showing 2 of 2. Use limit:N to see more.
```

---

## 7. 엣지 케이스 UX

### 7.1 빈 커맨드 (`/todo` 만 입력)

서브커맨드 없이 `/todo` 만 입력하면 도움말을 표시한다:
```
입력:  /todo
응답:
📖 OpenClaw TODO — Commands

/todo add <title> [@user] [/p project] [/s section] [due:date]
    Create a new task.

/todo list [mine|all|@user] [/p project] [/s section] [open|done|drop] [limit:N]
    List tasks.

/todo board [mine|all|@user] [/p project] [open|done|drop] [limitPerSection:N]
    Show kanban board view.

/todo move <id> <section>
    Move a task to a section (backlog, doing, waiting, done, drop).

/todo done <id>
    Mark a task as done.

/todo drop <id>
    Drop (cancel) a task.

/todo edit <id> [title] [@user] [/p project] [/s section] [due:date|due:-]
    Edit a task. Mentions replace all assignees. due:- clears the date.

/todo project list
    Show all visible projects.

/todo project set-private <name>
    Make a project private (owner-only).

/todo project set-shared <name>
    Make a project shared.
```

`/todo help`도 동일한 도움말을 표시한다.

### 7.2 알 수 없는 서브커맨드

```
입력:  /todo delete 50
응답:  ❌ Unknown command "delete". Available: add, list, board, move, done, drop, edit, project
```

### 7.3 중복 동작

| 상황 | 응답 |
|---|---|
| `/todo done 50` — 이미 done인 태스크 | `ℹ️ Task #50 is already done.` |
| `/todo drop 50` — 이미 dropped인 태스크 | `ℹ️ Task #50 is already dropped.` |
| `/todo move 50 doing` — 이미 doing인 태스크 | `ℹ️ Task #50 is already in doing.` |

### 7.4 edit에 변경사항 없음

```
입력:  /todo edit 50
응답:  ℹ️ No changes specified for #50.
```

### 7.5 프로젝트 자동 생성

`/todo add ... /p NewProject`에서 존재하지 않는 프로젝트를 참조하면 **shared** 프로젝트로 자동 생성한다:
```
입력:  /todo add 새 태스크 /p NewProject
응답:  ✅ Added #55 (NewProject/backlog) due:- assignees:<@U1234> — 새 태스크
       ℹ️ Project "NewProject" was created (shared).
```

`Inbox`는 DB 초기화 시 자동 생성되며, 존재하지 않을 경우에도 shared로 자동 생성된다.

### 7.6 대소문자 처리

| 대상 | 규칙 |
|---|---|
| 커맨드 (`add`, `LIST`, `Board`) | 대소문자 무시 — 모두 동일하게 처리 |
| 섹션 이름 (`DOING`, `Doing`, `doing`) | 대소문자 무시 — 저장 시 소문자로 정규화 |
| 프로젝트 이름 (`Backend` vs `backend`) | **대소문자 구분** — 서로 다른 프로젝트 |

### 7.7 공백 및 제목 정규화

- 제목의 앞뒤 공백은 제거 (trim)
- 단어 사이 연속 공백은 단일 공백으로 축약
- trim 후 빈 제목은 "title required" 에러

### 7.8 Due 날짜 엣지 케이스

| 입력 | 결과 (현재 연도 2026 기준) |
|---|---|
| `due:2026-03-15` | `2026-03-15` |
| `due:03-15` | `2026-03-15` |
| `due:3-5` | `2026-03-05` |
| `due:02-29` | 에러 (2026년은 윤년이 아님) |
| `due:00-01` | 에러 (유효하지 않은 월) |
| `due:12-32` | 에러 (유효하지 않은 일) |
| `due:-` | due 클리어 (NULL) |
| `due:yesterday` | 에러 (잘못된 형식) |

### 7.9 제목의 특수 문자

- 제목에는 줄바꿈을 제외한 모든 UTF-8 문자 사용 가능
- Slack mrkdwn 특수 문자(`*`, `_`, `~`, `` ` ``)는 응답 시 이스케이프 처리하여 포맷 깨짐 방지

---

## 부록: 입력 파싱 규칙

### A.1 토큰 인식

파서는 메시지를 좌→우로 처리한다. 인식되는 옵션 토큰:

| 토큰 | 패턴 | 설명 |
|---|---|---|
| `/p` | `/p <word>` | 다음 공백 구분 단어가 프로젝트 이름 |
| `/s` | `/s <word>` | 다음 공백 구분 단어가 섹션 이름 |
| `due:` | `due:<value>` | `due:`와 값 사이 공백 없음 |
| `@mention` | `<@UXXXXXXXX>` | Slack 유저 멘션 (복수 가능) |
| `limit:` | `limit:<N>` | 양의 정수 |
| `limitPerSection:` | `limitPerSection:<N>` | 양의 정수 |

### A.2 제목 추출 (add/edit)

인식된 옵션 토큰이나 멘션이 **아닌** 모든 텍스트가 제목으로 결합된다. 원래 순서가 유지된다.

파싱 예시:
```
/todo add 로그인 버그 수정 <@U5678> /p Backend due:03-15

파싱 결과:
  command   = add
  title     = "로그인 버그 수정"
  assignees = [<@U5678>]
  project   = "Backend"
  due       = "2026-03-15"
  section   = (기본값: backlog)
```

### A.3 프로젝트 이름 충돌 해소 (옵션 A — private 우선)

`/p <name>` 해석 우선순위:
1. sender(owner)의 private 프로젝트 `<name>`이 존재하면 **private 우선**
2. 없으면 shared `<name>` 사용
3. 둘 다 없으면 shared 자동 생성 (add 시) 또는 에러 (list/board 등)

> **운영 권장**: private와 shared에 같은 이름을 사용하지 않는 것을 권장 (혼란 방지).
