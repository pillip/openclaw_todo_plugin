# Project Status — OpenClaw TODO Plugin

**Last updated:** 2026-03-06
**PRD version:** v1.3

## Current Phase

**v1.3 구현 완료** — PRD v1.3 반영 완료. `project create` / `project rename` / `project delete` 커맨드 구현 완료.

## Milestones

| Milestone | Description | Status | Issues |
|-----------|-------------|--------|--------|
| M0 | Plugin skeleton + `todo:` command prefix + manifest bypass_llm | **Done** | #1, #29 (Open) |
| M1 | DB init + migrations + schema_version | **Done** | #2, #3, #4 |
| M2 | Parser (`todo:` 단일 접두사, Slack mention, /p, /s, due 보정) | **Done** | #5, #30 (Open) |
| M3 | Commands (add/list/board/move/done/drop/edit) | **Done** | #6~#12, #16, #17, #31~#35 (Open) |
| M4 | Project commands (list/set-private/set-shared/create/rename/delete) | **Done** | #13~#15, #36, #42, #43, #44 |
| M5 | Tests (parser/unit + sqlite E2E) | **Done** | #18, #19, #22, #37~#39 (Open) |
| M6 | Packaging / deployment | **Done** | #20, #40 (Open) |
| DevOps | GitHub Actions CI | **Done** | #21 |
| M7 | HTTP bridge for JS/TS gateway | **Done** | #23, #28 (Open) |

## Open Issues (PRD v1.3 신규)

| # | Title | Priority | Estimate | Status |
|---|-------|----------|----------|--------|
| #042 | `/todo project create` 커맨드 구현 (shared/private 명시적 생성) | P0 | 1d | Done → PR #82 |
| #043 | `/todo project rename` 커맨드 구현 (이름 변경 + 중복 블락) | P0 | 1d | Done → PR #84 |
| #044 | `/todo project delete` 커맨드 구현 (태스크 존재 시 삭제 차단) | P0 | 1d | Done → PR #86 |

## Completed Issues (PRD v1.2)

<details><summary>v1.2 이슈 전체 완료 (15건)</summary>

| # | Title | Result |
|---|-------|--------|
| #029 | manifest에 command_prefix 및 bypass_llm 필드 추가 | Done → PR #51 |
| #030 | list/board에서 open/done/drop status 필터 토큰 파싱 | Done |
| #031 | help 커맨드 및 상세 도움말 출력 | Done |
| #032 | UX 명세에 맞는 응답 메시지 포맷 통일 | Done → PR #53 |
| #033 | add 시 존재하지 않는 프로젝트 자동 생성 (shared) | Done |
| #034 | move 커맨드에서 /s 없이 section 직접 지정 | Done |
| #035 | 에러 메시지 UX 명세 정합 | Done |
| #036 | set-private 에러에 Slack 멘션 포맷 적용 | Done → PR #72 |
| #037 | parser 단위 테스트 보강 (엣지 케이스) | Done → PR #65 |
| #038 | E2E 테스트 보강 (scope/다중 사용자) | Done → PR #67 |
| #039 | server.py HTTP endpoint 테스트 보강 | Done → PR #74 |
| #027 | ruff/black target-version 정합 | Done |
| #028 | Bridge serverUrl config 연동 | Done |
| #040 | bridge TypeScript 빌드 및 npm 패키지 구성 | Done → PR #70 |
| #041 | bridge handler 버그 수정 (ctx.commandBody 중복 등 4건) | Done → PR #80 |

</details>

## Next Steps (권장 순서)

1. ~~**#042** (P0) — `/todo project create` 구현~~ ✅ PR #82
2. ~~**#043** (P0) — `/todo project rename` 구현~~ ✅ PR #84
3. ~~**#044** (P0) — `/todo project delete` 구현~~ ✅ PR #86

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite write contention under concurrent access | Low | Medium | WAL mode + busy_timeout=3000 |
| Private/shared name collision user confusion | Medium | Low | Option A (private-first) + guidance |
| Schema migration failures on upgrade | Low | High | schema_version table + sequential migrations |
| Slack rate limits on heavy usage | Low | Low | Responses are single messages per command |
| Gateway가 command_prefix 매칭 미지원 | Medium | Medium | LLM 라우팅 폴백 경로 유지 |
| Bridge cleanup 후 기존 사용자 혼란 | Low | Low | 문서 안내 + 점진적 전환 |
| Rename 시 FK 정합성 (project_id 기반) | Low | Low | project_id FK 이므로 name 변경은 안전 |

## Generated Documents

- [x] `docs/requirements.md` — v4.0, 기능/비기능 요구사항 (16 FR, 9 NFR, 10 US)
- [x] `docs/ux_spec.md` — v3.0, 전체 커맨드 UX 흐름 및 응답 포맷
- [x] `docs/architecture.md` — v3.0, 신규 Section 6 (v1.3 커맨드)
- [x] `docs/test_plan.md` — v2.2, 130개 테스트 케이스 + 21개 스모크 체크리스트
- [x] `issues.md` — 44개 이슈 (43 Done, 1 Backlog)
