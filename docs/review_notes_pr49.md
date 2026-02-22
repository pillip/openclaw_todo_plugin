# Review Notes -- PR #49

**PR**: fix: OpenClaw plugin integration fixes
**Reviewer**: Claude Opus 4.6 (automated)
**Date**: 2026-02-22
**Verdict**: Approve with minor suggestions

---

## Code Review

### 1. `src/openclaw_todo/server.py` -- ReusableHTTPServer

**Change**: Replaces bare `HTTPServer` with a `ReusableHTTPServer` subclass that sets
`allow_reuse_address = True`.

**Assessment**: Correct. This is standard practice for avoiding `OSError: [Errno 48]
Address already in use` on rapid restarts (systemd, development). The `SO_REUSEADDR`
socket option is set before `bind()` by `socketserver.TCPServer` when this class
attribute is `True`.

**Minor note**: The class is defined inside `run()`. This works fine since `run()` is
called once, but moving it to module level would be slightly more conventional. Not
worth changing.

### 2. `bridge/openclaw-todo/openclaw.plugin.json` -- configSchema

**Change**: Adds a `configSchema` with a `serverUrl` property (default
`http://127.0.0.1:8200`).

**Assessment**: The schema itself is well-formed JSON Schema. However, the bridge code
in `index.ts` currently reads the server URL from `process.env.OPENCLAW_TODO_URL` and
does **not** consume `serverUrl` from any config object. The schema is presumably
declarative for OpenClaw platform validation, but the disconnect should be tracked.

**Follow-up**: Wire `serverUrl` from the plugin config into `index.ts` (or document
that the env var takes precedence).

### 3. `.gitignore` -- Node artifacts

**Change**: Adds `node_modules/` and `package-lock.json`.

**Assessment**: Correct. The bridge directory contains TypeScript source, so these
entries are appropriate.

### 4. `pyproject.toml` -- Python version relaxed to >=3.10

**Change**: `requires-python` changed from `>=3.11` to `>=3.10`.

**Assessment**: Safe. All source files use `from __future__ import annotations`, which
makes PEP 604 union syntax (`X | Y`) and PEP 585 generics (`list[int]`) valid at
runtime on Python 3.10. The `dataclasses.field` usage is also 3.10-compatible.

**Minor inconsistency**: `tool.ruff.target-version` is still `"py311"` and
`tool.black.target-version` is still `["py311"]`. These should be updated to `"py310"`
to match the new `requires-python`. This means ruff/black may not flag syntax that
would fail on 3.10 (though with `__future__` annotations this is unlikely to matter in
practice).

**Follow-up**: Update `tool.ruff.target-version` and `tool.black.target-version` to
`py310` for consistency.

---

## Security Findings

### Low

**L-1: configSchema default URL uses loopback address (informational)**
File: `bridge/openclaw-todo/openclaw.plugin.json`, line 13

The default `serverUrl` is `http://127.0.0.1:8200` (plain HTTP on loopback). This is
acceptable for local development. If the server is ever deployed on a separate host,
HTTPS should be enforced. No action needed now.

### No Critical / High / Medium findings

The change set is small and introduces no new attack surface:
- No new user input paths
- No secrets or credentials
- No dependency changes
- `allow_reuse_address` does not weaken security (it only affects `TIME_WAIT` socket
  reuse, not port hijacking on modern kernels)

---

## Test Results

```
253 passed in 5.88s
```

All existing tests pass. No new tests needed for these changes (infrastructure/config
only).

---

## Summary of Follow-up Items

| Item | Priority | Description |
|------|----------|-------------|
| 1 | Low | Wire `serverUrl` from plugin config into `index.ts` or document env-var precedence |
| 2 | Low | Update `tool.ruff.target-version` and `tool.black.target-version` to `py310` |
