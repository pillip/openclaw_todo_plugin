# Project Status — OpenClaw TODO Plugin

**Last updated:** 2026-03-01
**PRD version:** v1.2

## Current Phase

**Core implementation complete** — PRD v1.2 반영 문서 갱신 완료. UX/응답 포맷 정합 및 신규 기능 구현 대기.

## Milestones

| Milestone | Description | Status | Issues |
|-----------|-------------|--------|--------|
| M0 | Plugin skeleton + `todo:` command prefix + manifest bypass_llm | **Done** | #1, #29 (Open) |
| M1 | DB init + migrations + schema_version | **Done** | #2, #3, #4 |
| M2 | Parser (`todo:` 단일 접두사, Slack mention, /p, /s, due 보정) | **Done** | #5, #30 (Open) |
| M3 | Commands (add/list/board/move/done/drop/edit) | **Done** | #6~#12, #16, #17, #31~#35 (Open) |
| M4 | Project commands (list/set-private/set-shared) | **Done** | #13, #14, #15, #36 (Open) |
| M5 | Tests (parser/unit + sqlite E2E) | **Done** | #18, #19, #22, #37~#39 (Open) |
| M6 | Packaging / deployment | **Done** | #20, #40 (Open) |
| DevOps | GitHub Actions CI | **Done** | #21 |
| M7 | HTTP bridge for JS/TS gateway | **Done** | #23, #28 (Open) |

## Open Issues (PRD v1.2 반영)

| # | Title | Priority | Estimate |
|---|-------|----------|----------|
| ~~#029~~ | ~~manifest에 command_prefix 및 bypass_llm 필드 추가~~ | ~~P0~~ | Done → PR #51 |
| ~~#030~~ | ~~list/board에서 open/done/drop status 필터 토큰 파싱~~ | ~~P1~~ | Done |
| ~~#031~~ | ~~help 커맨드 및 상세 도움말 출력~~ | ~~P1~~ | Done |
| ~~#032~~ | ~~UX 명세에 맞는 응답 메시지 포맷 통일~~ | ~~P0~~ | Done → PR #53 |
| ~~#033~~ | ~~add 시 존재하지 않는 프로젝트 자동 생성 (shared)~~ | ~~P1~~ | Done |
| ~~#034~~ | ~~move 커맨드에서 /s 없이 section 직접 지정~~ | ~~P1~~ | Done |
| ~~#035~~ | ~~에러 메시지 UX 명세 정합~~ | ~~P1~~ | Done |
| ~~#036~~ | ~~set-private 에러에 Slack 멘션 포맷 적용~~ | ~~P2~~ | Done |
| ~~#037~~ | ~~parser 단위 테스트 보강 (엣지 케이스)~~ | ~~P1~~ | Done → PR #65 |
| ~~#038~~ | ~~E2E 테스트 보강 (scope/다중 사용자)~~ | ~~P1~~ | Done → PR #67 |
| ~~#039~~ | ~~server.py HTTP endpoint 테스트 보강~~ | ~~P2~~ | Done |
| ~~#027~~ | ~~ruff/black target-version 정합~~ | ~~P2~~ | Done |
| ~~#028~~ | ~~Bridge serverUrl config 연동~~ | ~~P2~~ | Done |
| ~~#040~~ | ~~bridge TypeScript 빌드 및 npm 패키지 구성~~ | ~~P1~~ | Done |
| ~~#041~~ | ~~bridge handler 버그 수정 (ctx.commandBody 중복 등 4건)~~ | ~~P0~~ | Done → PR #80 |

## Next Steps (권장 순서)

1. ~~**#029** (P0) — manifest bypass_llm 필드 추가~~ ✅
2. ~~**#032** (P0) — 응답 메시지 포맷 UX 명세 정합~~ ✅
3. **#030, #031, #033~#035** (P1) — 기능 보강
4. **#037, #038** (P1) — 테스트 보강
5. **#027, #028, #036, #039** (P2) — 정비 작업

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite write contention under concurrent access | Low | Medium | WAL mode + busy_timeout=3000 |
| Private/shared name collision user confusion | Medium | Low | Option A (private-first) + guidance |
| Schema migration failures on upgrade | Low | High | schema_version table + sequential migrations |
| Slack rate limits on heavy usage | Low | Low | Responses are single messages per command |
| Gateway가 command_prefix 매칭 미지원 | Medium | Medium | LLM 라우팅 폴백 경로 유지 |
| Bridge cleanup 후 기존 사용자 혼란 | Low | Low | 문서 안내 + 점진적 전환 |

## Generated Documents

- [x] `docs/requirements.md` — v3.0, 기능/비기능 요구사항 (14 FR, 9 NFR, 8 US)
- [x] `docs/ux_spec.md` — v2.0, 전체 커맨드 UX 흐름 및 응답 포맷
- [x] `docs/architecture.md` — v2.1, 13개 섹션 시스템 아키텍처
- [x] `docs/test_plan.md` — 101개 테스트 케이스 + 16개 스모크 체크리스트
- [x] `issues.md` — 41개 이슈 (27 Done, 14 Open)
