# Review Notes -- PR #67: E2E Integration Tests (Scenarios 10-13)

**Reviewer:** Claude Opus 4.6 (automated)
**Date:** 2026-02-26
**Scope:** `tests/test_e2e.py` -- 11 new test methods across 4 new test classes, no production code changes

---

## Code Review

### Summary

PR #67 adds 11 E2E integration tests covering four new scenarios in `tests/test_e2e.py`:

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestListScopeByMention` | 2 | Verify `list all <@UXXXX>` filters by assignee and respects private visibility |
| `TestMultiUserSharedCollaboration` | 4 | Multi-user add/move/done on shared projects; permission denial for unrelated users |
| `TestPrivateSharedNameCollision` | 2 | Private-first resolution when private and shared projects share a name |
| `TestStatusFilterE2E` | 3 | Status-based filtering for `list done`, `list drop`, `board done` |

All 31 E2E tests pass (0.23s). Full suite of 293 tests continues to pass.

### Positive Observations

- Tests are deterministic -- each uses `tmp_path` for a fresh SQLite database, no shared state between tests.
- Good use of the `_msg()` / `_extract_task_id()` / `_query_task()` helpers, consistent with the existing test patterns in the file.
- The `_query_task()` helper includes an allowlist (`_ALLOWED_COLUMNS`) to prevent SQL injection in test code -- a thoughtful defensive measure.
- Scenario 11 (`TestMultiUserSharedCollaboration`) exercises the full permission matrix: creator, assignee, and unrelated user. This is thorough.
- Scenario 12 (`TestPrivateSharedNameCollision`) tests a subtle resolution edge case from both the owner and non-owner perspectives, which is valuable for catching regressions.
- Tests verify both user-facing response text and underlying DB state (via `_query_task`), providing two layers of confidence.

### Issues

**1. Missing Scenario 9 class (cosmetic, Low)**
Lines 312-314 jump from "Scenario 9: full lifecycle" comment block to Scenario 10 without a corresponding `TestXxx` class for Scenario 9. The full lifecycle test exists later as Scenario 14 (`TestFullLifecycle`). This numbering gap is confusing. Consider either renumbering to remove the gap or adding a comment explaining that Scenario 9 was merged into Scenario 14.

**2. `_extract_task_id` is fragile on unexpected response format (Low)**
The helper `_extract_task_id()` at line 31 assumes the response always contains `#N `. If the response format ever changes (e.g., `#N.` or `#N\n`), the split on `" "` may produce unexpected results. This is acceptable for E2E tests tied to a known response format, but a regex like `r"#(\d+)"` would be more resilient.

**3. Assertions rely on substring matching in formatted output (Low)**
Tests like `assert "task for U001" not in result` depend on the exact task title appearing verbatim in the response. If the output format ever truncates titles or wraps them in markup, these assertions would break silently (false pass or false fail). This is an inherent tradeoff of E2E testing against formatted output and is acceptable, but worth noting.

### Coverage Gaps (Suggestions for Follow-up)

- **Scenario 11 gap -- creator modifying an assigned task:** The tests verify assignee can modify and unrelated user cannot, but do not explicitly test that the *creator* (U001) can still modify a task assigned to U002. This is implied by the permission model but worth a dedicated assertion.
- **Scenario 13 gap -- `list open` explicit filter:** Tests cover `list done` and `list drop` but not an explicit `list open` filter, which would confirm the filter mechanism works symmetrically rather than just relying on the default behavior.
- **Scenario 13 gap -- `board drop`:** Tests cover `board done` but not `board drop`, leaving that view path untested.
- **Negative case -- mention of nonexistent user:** `list all <@UXXX>` where UXXX has zero tasks is not tested. It would confirm the response is well-formed (empty list, not an error).
- **Scenario 12 -- non-owner adding to shared then listing from U001 perspective:** `test_non_owner_resolves_to_shared` verifies U001 does *not* see U002's shared task via `/p MyProj` (since it resolves to private for U001). A follow-up could verify U001 can reach the shared project explicitly (if such a mechanism exists) or via `list all` without `/p`.

---

## Security Findings

### Test Code Scope

This PR contains only test code. Test files do not ship to production and run in isolated `tmp_path` SQLite databases. Security findings here are limited to test hygiene.

**No Critical or High severity findings.**

**Medium -- None.**

**Low:**

1. **SQL construction in `_query_task` is adequately guarded (Low / Informational).**
   The `_query_task` helper on line 40-55 uses f-string interpolation for column names (`f"SELECT {safe_columns} FROM tasks WHERE id = ?;"`). This is mitigated by the `_ALLOWED_COLUMNS` allowlist on line 34-37, which restricts inputs to a known-safe set. The task ID is properly parameterized. No action needed, but the pattern should not be copied into production code without the same allowlist guard.

2. **No secrets or credentials in test code (Informational).** Confirmed -- user IDs are synthetic (`U001`, `U002`, `U003`), no API keys or tokens are present.

---

## Verdict

**Approve.** The 11 new tests are well-structured, deterministic, and cover important multi-user, permission, and resolution edge cases. The minor cosmetic issues (scenario numbering gap, fragile `_extract_task_id`) are not blocking. The suggested coverage gaps can be addressed in a follow-up PR.
