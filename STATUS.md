# Project Status — OpenClaw TODO Plugin

**Last updated:** 2026-02-20

## Current Phase

**Kickoff complete** — All planning documents generated. Ready to begin implementation.

## Milestones

| Milestone | Description | Status | Issues |
|-----------|-------------|--------|--------|
| M0 | Plugin skeleton + `/todo` command registration | **Done** | #1 |
| M1 | DB init + migrations + schema_version | In progress (#2 done) | #2, #3, #4 |
| M2 | Parser (Slack mention, /p, /s, due correction) | Not started | #5 |
| M3 | Commands (add/list/board/move/done/drop/edit) | Not started | #6–#12, #16, #17 |
| M4 | Project commands (list/set-private/set-shared) | Not started | #13, #14, #15 |
| M5 | Tests (parser/unit + sqlite E2E) | Not started | #18, #19 |
| M6 | Packaging / deployment | Not started | #20 |

## Critical Path

```
#1 (skeleton) → #2 (DB conn) → #3 (migration framework) → #4 (V1 schema) → #7 (project resolver) → commands
#5 (parser) can be developed in parallel with DB track
```

## Next Issues to Work On

1. **#3** — Schema migration framework (M1)
2. **#5** — Command parser / tokenizer (M2, parallelizable)
3. **#4** — V1 schema migration (M1)

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite write contention under concurrent access | Low | Medium | WAL mode + busy_timeout=3000 |
| Private/shared name collision user confusion | Medium | Low | Option A (private-first) + guidance |
| Schema migration failures on upgrade | Low | High | schema_version table + sequential migrations |
| Slack rate limits on heavy usage | Low | Low | Responses are single messages per command |

## Generated Documents

- [x] `docs/requirements.md` — Functional & non-functional requirements
- [x] `docs/ux_spec.md` — UX specification with all command flows
- [x] `docs/architecture.md` — Software architecture design
- [x] `docs/test_plan.md` — Test strategy with 80+ test cases
- [x] `issues.md` — 20 issues across 7 milestones
