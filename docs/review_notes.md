# PR #2 Review Notes -- Issue #1: Plugin skeleton and entry point

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-20
> Branch: `feature/001-plugin-skeleton`

---

## Code Review

### Acceptance Criteria Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| `pyproject.toml` with Python >=3.11, pytest, pytest-cov dev deps | PASS | Correct. Uses `dependency-groups` (PEP 735) with hatchling backend. |
| `src/openclaw_todo/__init__.py` exposes `__version__` | PASS | `__version__ = "0.1.0"` |
| `handle_message(text: str, context: dict) -> str` entry point | PASS (minor note) | Return type is `str | None`, not `str`. The AC literally says `-> str` but `None` for ignored messages is the intended behavior per the next AC. Acceptable. |
| Non-`/todo` messages silently ignored (returns `None`) | PASS | |
| `uv sync && uv run pytest -q` passes | PASS | 4 tests, 100% coverage |

### Required Tests

| Test | Status |
|------|--------|
| `test_ignores_non_todo_message` | PASS -- covers empty string, random text, `/todox` prefix-collision |
| `test_dispatches_todo_prefix` | PASS -- verifies non-None response with subcommand text |

### Findings

#### [Info] Return type annotation mismatch with AC

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- The AC states `-> str` but the implementation is `-> str | None`. This is correct behavior (returning `None` for non-todo messages is explicitly required). The AC text is slightly imprecise; the code is right.
- **Action**: None needed. Consider updating the AC wording if desired.

#### [Info] `context` parameter unused

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- `context: dict` is accepted but never read in this skeleton. This is expected for M0 -- it will be used once the dispatcher (Issue #16) and DB commands are wired in.
- **Action**: None. This is intentional scaffolding.

#### [Info] Placeholder response includes raw user input

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 32
- `f"TODO command received: {remainder}"` echoes back unescaped user input. This is a temporary placeholder (comment says "will be replaced by dispatcher in Issue #16"). In the current context (no HTML/web rendering, Slack DM only), this is not exploitable, but see Security Findings below.
- **Action**: Track as part of Issue #16.

#### [Info] Extra tests beyond AC requirements -- good

- `test_todo_prefix_with_whitespace` and `test_todo_without_subcommand` are bonus tests covering whitespace handling and bare `/todo` usage message. Good coverage instinct.

#### [Info] Version duplication

- Version `0.1.0` appears in both `pyproject.toml` and `__init__.py`. Consider using `importlib.metadata` or dynamic versioning in a future issue to keep a single source of truth. Not a concern for M0.

#### [Low] No type hints for `context` dict

- `context: dict` is untyped (could be `dict[str, Any]` or a TypedDict). For M0 this is fine, but a `TypedDict` or dataclass should be introduced when the context shape solidifies.

### Code Quality Summary

The implementation is clean, minimal, and well-structured for a skeleton:

- Prefix matching logic (`stripped == _TODO_PREFIX or stripped.startswith(_TODO_PREFIX + " ")`) correctly avoids false positives on `/todox`.
- Logging at appropriate levels (debug for all messages, info for matches).
- Usage help returned for bare `/todo` is a nice touch.
- Test coverage is 100%.

**Verdict: APPROVE** -- no blocking issues.

---

## Security Findings

### [Low] S1: User input echoed in placeholder response

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 32
- **Description**: The placeholder `f"TODO command received: {remainder}"` reflects user-supplied text without sanitization. In the current Slack DM context, Slack handles rendering and this is not exploitable for XSS. However, once a web dashboard or logging UI is introduced, unsanitized echo could become a reflected XSS vector.
- **Severity**: Low (Slack auto-escapes; placeholder will be replaced in Issue #16)
- **Recommendation**: When building the real dispatcher, ensure any user text echoed in responses is sanitized if it ever reaches a web context. No fix needed now.

### [Low] S2: No input length validation

- **File**: `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/plugin.py`, line 12
- **Description**: `handle_message` accepts arbitrarily long strings. A malicious or buggy client could send extremely large messages. Slack itself limits messages to ~40,000 characters, so this is mitigated at the transport layer.
- **Severity**: Low
- **Recommendation**: Consider adding a max-length guard in the dispatcher (Issue #16) if the plugin is ever exposed outside Slack.

### [Info] S3: No hardcoded secrets or credentials

- No API keys, tokens, or secrets found in any reviewed files. Environment variable approach is correctly deferred to future DB/config work.

### [Info] S4: Dependencies are minimal and current

- Only dev dependencies: `pytest>=7.0` and `pytest-cov>=4.0`. No known CVEs for these versions. No runtime dependencies beyond the standard library.
- Build backend `hatchling` is a well-maintained, standard tool.

### [Info] S5: No SQL, no deserialization, no file I/O

- The M0 skeleton has no database, no file operations, and no deserialization. The attack surface is effectively zero at this stage.

### Security Summary

No Critical or High severity findings. The codebase has a minimal attack surface appropriate for a plugin skeleton. Security considerations will become relevant starting with Issue #2 (DB connection) and Issue #5 (parser with user-controlled input).

---

## Follow-up Issues (proposed)

1. **Issue #16 (Dispatcher)**: When replacing the placeholder response, ensure user input is not echoed raw if the output context changes (e.g., web UI).
2. **Future**: Introduce a `TypedDict` or dataclass for the `context` parameter to enforce shape and enable static analysis.
3. **Future**: Consolidate version to a single source (e.g., `importlib.metadata.version("openclaw-todo-plugin")`).
