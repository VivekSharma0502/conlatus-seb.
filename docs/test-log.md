# SEB Middleware — Test Log

## Verification Commands

Run these after starting the backend. They do **not** require SEB headers, so they verify the middleware is enforcing correctly.

### 1. `GET /interview/start` must return 403 when SEB is enabled

```bash
# From backend/ with DEV_SKIP_SEB=false, SEB_CONFIG_KEY set to any non-empty value
curl -s -o - -w "\nHTTP %{http_code}\n" http://localhost:8000/interview/start
```

**Expected output:**
```
{"detail":"Safe Exam Browser required"}
HTTP 403
```

### 2. `GET /interview/details/demo` must return 200 (public prefix)

```bash
curl -s -o - -w "\nHTTP %{http_code}\n" http://localhost:8000/interview/details/demo
```

**Expected output:**
```
HTTP 200   (or 404 if the demo session does not exist — either way, NOT 403)
```

### 3. `GET /` must always be public

```bash
curl -s http://localhost:8000/
```

**Expected:** `{"status":"ok", ...}`

### 4. Startup log check (with `DEV_SKIP_SEB=true`)

Start the server and look for:
```
WARNING  seb:main.py:44 ⚠️  SEB check DISABLED (DEV_SKIP_SEB=true) — Safe Exam Browser is NOT enforced. SEB_CONFIG_KEY set: False
```

### 5. Startup log check (with `DEV_SKIP_SEB=false`)

Start the server and look for:
```
INFO     seb:main.py:47 SEB check ENABLED | SEB_CONFIG_KEY set: True
```

---

## Root Cause Record (2026-10-31)

**Bug:** `GET /interview/start` intermittently returned 405 instead of 403.

**Root cause:** `pydantic-settings` resolved `env_file=".env"` relative to CWD.
- CWD = `c:\seb` → loaded `c:\seb\.env` → `DEV_SKIP_SEB=false` → SEB enforced → 403 ✓
- CWD = `c:\seb\backend` → loaded `c:\seb\backend\.env` → `DEV_SKIP_SEB=true` → SEB skipped → request reached router → 405 (POST-only route) ✗

**Fix:** `env_file` in `core/config.py` changed to absolute path:
```python
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = str(_BACKEND_DIR / ".env")
```

