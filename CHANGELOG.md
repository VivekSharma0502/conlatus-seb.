# Changelog

All notable changes to this project will be documented here.

---

## [Unreleased]

### Fixed
- **SEB intermittent bypass bug** (`backend/core/config.py`): `pydantic-settings` was loading `.env`
  via a relative path (`".env"`), which resolves against the process CWD. When uvicorn was started
  from the repo root (`c:\seb`) it loaded `c:\seb\.env` (which had `DEV_SKIP_SEB=false` and a key
  set), and when started from `c:\seb\backend` it loaded `backend/.env` (which had
  `DEV_SKIP_SEB=true`). This made SEB enforcement CWD-dependent and intermittent.
  **Fix:** `env_file` is now resolved to an absolute path using `Path(__file__).resolve().parent.parent / ".env"`,
  guaranteeing `backend/.env` is always loaded regardless of CWD.

### Added
- **Startup SEB status log** (`backend/main.py`): On every startup the `seb` logger emits exactly
  one line: `"SEB check ENABLED | SEB_CONFIG_KEY set: <true|false>"` or, when bypassed, a loud
  `WARNING: SEB check DISABLED (DEV_SKIP_SEB=true) — Safe Exam Browser is NOT enforced.
  SEB_CONFIG_KEY set: <true|false>"`. The key value is never logged.
- **README** updated with canonical start command, env var table, and CWD note.
- **`docs/test-log.md`** — curl verification commands for SEB enforcement.

