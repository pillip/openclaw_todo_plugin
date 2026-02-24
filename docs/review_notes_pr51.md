# Review Notes -- PR #51

> **PR:** #51 -- manifest에 command_prefix 및 bypass_llm 필드 추가 (ISSUE-029)
> **Reviewer:** Claude Opus 4.6
> **Date:** 2026-02-24

---

## Code Review

### 1. Manifest changes (`bridge/openclaw-todo/openclaw.plugin.json`)

**Verdict: Correct and clean.**

The two new top-level fields `"command_prefix": "todo:"` and `"bypass_llm": true` are
well-placed, JSON is valid, and the existing `triggers` block is preserved for fallback
compatibility as specified in the issue scope.

No issues found.

### 2. Test file (`tests/test_manifest.py`)

**Verdict: Acceptable with minor improvement suggestions.**

**Positive observations:**
- Good coverage of the acceptance criteria: JSON validity, new fields, trigger block, existing fields.
- Uses `pathlib.Path` for cross-platform path resolution.
- Tests are clearly named and well-structured in a class.

**Suggestions (non-blocking):**

| # | Finding | Severity | Suggestion |
|---|---------|----------|------------|
| T1 | Repeated `json.loads(MANIFEST_PATH.read_text())` in every test method | Low / Style | Extract to a `pytest` fixture or a class-level `setup_method` / `@pytest.fixture(scope="class")`. This reduces I/O repetition and makes the test class easier to maintain. Not a correctness issue since the file is small and tests are fast (0.01s). |
| T2 | No negative test for unexpected field types | Low | Consider adding a test that asserts `isinstance(data["bypass_llm"], bool)` and `isinstance(data["command_prefix"], str)` to guard against accidental type changes (e.g., `"true"` instead of `true`). |
| T3 | `MANIFEST_PATH` relies on file-relative traversal | Info | The path `Path(__file__).resolve().parent.parent / "bridge" / ...` works correctly for the current project layout. If the test directory moves, this will break silently. Acceptable for now -- just documenting for awareness. |

### 3. Bookkeeping files (`issues.md`, `STATUS.md`)

Reviewed for consistency. The ISSUE-029 status is correctly updated to `done` with PR #51
reference. STATUS.md correctly strikes through #029 in the open issues table.

### 4. Overall assessment

This is a small, focused, low-risk change. The manifest fields are declarative configuration
consumed by an external Gateway, so the blast radius is minimal. The tests adequately verify
the acceptance criteria. **Approve with optional nits.**

### Follow-up issues (already tracked)

- ISSUE-028: Bridge `index.ts` does not yet read `command_prefix` or `bypass_llm` from the
  manifest at runtime. Currently the pattern is hardcoded in `api.registerMessageHandler`.
  This is intentional (Gateway-side responsibility), but worth noting.
- ISSUE-040: TypeScript build -- once the bridge is packaged, a build-time schema check
  against the manifest would catch structural drift.

---

## Security Findings

| # | Finding | Severity | Details |
|---|---------|----------|---------|
| S1 | No secrets or credentials in changed files | N/A | Confirmed: no API keys, tokens, or sensitive values in manifest or tests. |
| S2 | `configSchema.properties.serverUrl.default` uses `127.0.0.1` | **Low** | The default URL `http://127.0.0.1:8200` is localhost-only, which is appropriate for development. In production, this should be overridden via plugin config. No action needed -- this is by design and already documented. |
| S3 | `bypass_llm: true` skips LLM processing for matched commands | **Low** | This is the intended behavior per PRD 1.2/2.4. The security implication is that commands matching `todo:` prefix bypass any LLM-level content filtering. Since the TODO plugin processes structured commands (not free-form content), and input validation happens in the Python server's parser, the risk is negligible. The Gateway should still enforce authentication before routing. |
| S4 | Test file reads from filesystem without sandboxing | **Info** | `test_manifest.py` reads a real file on disk. This is standard for configuration validation tests and poses no security risk in a CI/test environment. |

**No Critical or High severity issues found. No fixes required.**

---

## Summary

- **Code quality:** Good. Small, focused PR. Tests cover all acceptance criteria.
- **Security:** No issues. No secrets, no injection vectors, no misconfigurations.
- **Recommendation:** Approve. Optional refactor of test fixture for DRY (T1) can be done
  in a future cleanup pass.
