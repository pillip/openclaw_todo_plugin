# PR #46 Review Notes -- Issue #23: HTTP Server Bridge for JS/TS OpenClaw Gateway

> Reviewer: Claude Opus 4.6 (automated review)
> Date: 2026-02-21
> Branch: `feature/023-http-bridge`

---

## Code Review

### Overall Assessment

The PR is well-structured and follows the project conventions. The HTTP bridge
adds a clean integration path for JS/TS OpenClaw gateways with zero runtime
dependencies on both sides. Code is readable, well-documented, and comes with
9 (now 10) tests covering the happy path and error handling.

### Findings

#### 1. server.py -- Clean architecture (Positive)

The closure-based `_make_handler_class(db_path)` pattern avoids globals and
makes testing straightforward. The handler only exposes two endpoints (`GET
/health`, `POST /message`) and rejects everything else with 404. Input
validation is thorough: empty body, invalid JSON, non-dict JSON, missing
required fields.

#### 2. server.py -- No request body size limit (Fixed)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/server.py`

The original code read `Content-Length` bytes without any upper bound. A
malicious or buggy client could send a multi-gigabyte `Content-Length` and
force the server to allocate that much memory.

**Fix applied:** Added `MAX_BODY_BYTES = 1_048_576` (1 MiB) constant. Requests
with `Content-Length` exceeding this limit are rejected with HTTP 413. A test
(`test_oversized_body_413`) was added to cover this path.

#### 3. server.py -- Uncaught ValueError on invalid port env var (Fixed)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/server.py`

`int(os.environ.get("OPENCLAW_TODO_PORT", ...))` would crash with
`ValueError` if the env var was set to a non-numeric string. Wrapped in
try/except with a warning log and fallback to `DEFAULT_PORT`.

#### 4. server.py -- Uncaught ValueError on invalid Content-Length header (Fixed)

**File:** `/Users/pillip/project/practice/openclaw_todo_plugin/src/openclaw_todo/server.py`

`int(self.headers.get("Content-Length", 0))` could raise `ValueError` on
malformed headers. Wrapped in try/except returning 400.

#### 5. __main__.py -- Correct and minimal (Positive)

The `if __name__ == "__main__"` guard is correct. The module-level import
means `python -m openclaw_todo` works as expected.

#### 6. bridge/openclaw-todo/index.ts -- Clean (Positive)

The TypeScript bridge is minimal and correct. It uses Node built-in `fetch`
(Node 18+), checks `res.ok`, and throws with the error body on failure.
`OPENCLAW_TODO_URL` defaults to localhost.

#### 7. Test coverage (Good, +1 new test)

Original PR had 9 tests. This review added 1 test for the 413 body size
limit. All 253 tests pass (252 existing + 1 new). Test coverage areas:
- Health endpoint (200, 404)
- Message dispatch (add, non-todo, usage)
- Error handling (empty body, invalid JSON, missing fields, wrong path, oversized body)

#### 8. pyproject.toml -- Entry point (Positive)

`openclaw-todo-server = "openclaw_todo.server:run"` correctly points to the
`run()` function. Note: `run()` is blocking by design -- this is expected for
a CLI entry point.

### Follow-up Issues (Not blocking merge)

1. **Rate limiting:** The server has no request rate limiting. For a
   localhost-only bridge this is acceptable, but if deployment scenarios change
   this should be addressed.

2. **Structured logging:** `log_message` routes through Python logging but
   `BaseHTTPRequestHandler` default format strings use `%s`-style formatting.
   Consider structured request logging (method, path, status, duration) in a
   future PR.

3. **Graceful shutdown test:** No test covers the SIGINT/SIGTERM shutdown
   path. This is hard to test portably but could be added with
   `signal.raise_signal()` in a subprocess test.

4. **TS bridge -- no timeout on fetch:** The JS bridge `fetch()` call has no
   `signal` / `AbortController` timeout. If the Python server hangs, the
   gateway hangs indefinitely.

---

## Security Findings

### Medium Severity

#### M1. No request body size limit (FIXED)

**Location:** `src/openclaw_todo/server.py` line 73 (original)
**Description:** `self.rfile.read(content_length)` would allocate memory based
on an attacker-controlled `Content-Length` header with no upper bound.
**Impact:** Denial of service via memory exhaustion.
**Mitigation:** Localhost-only binding reduces exposure. Applied fix: reject
requests with `Content-Length > 1 MiB` with HTTP 413.
**Status:** Fixed.

### Low Severity

#### L1. No authentication on HTTP endpoints

**Location:** `src/openclaw_todo/server.py`
**Description:** The `/message` endpoint accepts requests from any client that
can reach the server. There is no API key, token, or other authentication.
**Impact:** Any process on the same machine can send commands.
**Mitigation:** The server binds to `127.0.0.1` (not `0.0.0.0`), limiting
access to the local machine. This is acceptable for the bridge pattern where
the JS gateway and Python server run on the same host.
**Recommendation:** If the server is ever exposed beyond localhost, add a
shared-secret header check (e.g., `Authorization: Bearer <token>` from an env
var). Log as a follow-up.

#### L2. Invalid OPENCLAW_TODO_PORT causes unhandled crash (FIXED)

**Location:** `src/openclaw_todo/server.py` line 35 (original)
**Description:** Setting `OPENCLAW_TODO_PORT=abc` would crash the server at
startup with an unhandled `ValueError`.
**Impact:** Server fails to start; no data loss.
**Status:** Fixed with try/except fallback.

#### L3. No CORS headers

**Location:** `src/openclaw_todo/server.py`
**Description:** No CORS headers are set. This means browser-based clients
cannot call the API directly.
**Impact:** None currently (bridge calls from Node, not browser). Positive
from a security standpoint -- no unintended browser access.
**Recommendation:** Do NOT add permissive CORS unless explicitly needed.

#### L4. TypeScript bridge has no fetch timeout

**Location:** `bridge/openclaw-todo/index.ts` line 26
**Description:** `fetch()` has no `AbortController` timeout. A hung Python
server would block the gateway indefinitely.
**Impact:** Gateway thread/promise hangs.
**Recommendation:** Add a timeout in a follow-up PR:
```typescript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 5000);
const res = await fetch(url, { signal: controller.signal, ... });
clearTimeout(timeout);
```

### Not Applicable

- **SQL Injection:** All database queries use parameterized statements (`?`
  placeholders). The `cmd_edit.py` dynamic SQL builds column names from
  hardcoded strings, not user input. No risk found.
- **Command Injection:** No shell execution anywhere in the codebase.
- **Hardcoded Secrets:** No API keys, passwords, or tokens found in code or
  config files.
- **Dependency CVEs:** Zero runtime dependencies (stdlib only on Python side,
  built-in fetch on Node side). No vulnerable packages.
- **XSS:** Server returns JSON only, no HTML rendering.

---

## Changes Applied in This Review

| File | Change |
|------|--------|
| `src/openclaw_todo/server.py` | Added `MAX_BODY_BYTES` constant (1 MiB) |
| `src/openclaw_todo/server.py` | Added Content-Length size check returning 413 |
| `src/openclaw_todo/server.py` | Added try/except around Content-Length parsing |
| `src/openclaw_todo/server.py` | Added try/except around port env var parsing |
| `tests/test_server.py` | Added `test_oversized_body_413` test |

## Test Results After Fixes

```
253 passed in 6.39s
ruff check: All checks passed!
```
