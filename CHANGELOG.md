# Changelog

All notable changes to the Conlatus platform are documented in this file.

---

## [Unreleased] - 2026-11-01

### Fixed
- **SEB Config Key Path Bug (`backend/core/config.py`)**:
  - `pydantic-settings` previously resolved `env_file=".env"` using a relative path, which caused the environment to be resolved against the process current working directory.
  - When starting from the project root (`c:\seb`), it read root `.env`; when starting from `backend/`, it read `backend/.env`. This resulted in intermittent 405 vs 403 status codes depending on which directory uvicorn was launched from.
  - **Resolution**: `model_config` now specifies an absolute path anchored to `Path(__file__).resolve().parent.parent / ".env"`, guaranteeing consistent loading of `backend/.env` regardless of process invocation CWD.

- **Safe Exam Browser Launch URL Deep-Link Fix (`frontend/src/lib/brand.ts`, `frontend/src/components/interview/SebGate.tsx`)**:
  - The launch button previously built `sebs://localhost:3000/seb/config.seb?code=demo` using `window.location.host`, which caused connection errors because the Next.js frontend was not serving the `.seb` configuration binary.
  - **Resolution**: Gating link now points to the backend configuration host via `NEXT_PUBLIC_SEB_CONFIG_HOST` (defaulting to `localhost:8000`).
  - Added protocol negotiation: uses `seb://` (plain HTTP) for `localhost` and `127.0.0.1`, and `sebs://` (HTTPS) for production domains.
  - Stripped redundant `?code=` query from config download URL, ensuring clean SEB client profile ingestion.

- **SEB Config Key Hash Mismatch on Subresource Fetch Calls (`backend/core/seb.py`, `frontend/src/lib/api.ts`)**:
  - When candidates initiated audio or text responses from within the SEB browser window via `fetch()`, SEB computed the `x-safeexambrowser-configkeyhash` header based on the active browser page URL rather than the backend REST endpoint URL.
  - **Resolution**: `SEBMiddleware` now verifies against a list of candidate URLs:
    - Candidate (a): The backend API request URL (`_public_url(request)`).
    - Candidate (b): The frontend page URL retrieved from the `Referer` header (with `#fragment` stripped).
  - Added `referrerPolicy: "unsafe-url"` across frontend `api.ts`, candidate interview pages, and room components to guarantee the full page path is transmitted in `Referer`.
  - Matching uses constant-time `hmac.compare_digest` against all configured keys.

- **SEB Configuration Endpoint Method Support (`backend/main.py`)**:
  - Changed `@app.get("/seb/config.seb")` to `@app.api_route("/seb/config.seb", methods=["GET", "HEAD"])` to allow HTTP `HEAD` probes often sent by browser downloaders and SEB initialization checks.

- **Cleaned Accidental Leaked Keys in Repository**:
  - Removed leaked placeholder lines from `backend/alembic/env.py`.
  - Confirmed all `.env.example` templates contain only empty keys or generic placeholders.
  - Completely removed temporary `/seb-debug` diagnostic page.

### Added
- **Startup Enforcement Logging**:
  - On application startup, the backend lifespan emits a single informational or warning log line declaring whether SEB enforcement is `ENABLED` or `DISABLED (DEV_SKIP_SEB=true)` and whether `SEB_CONFIG_KEY` is present. Actual key values are never logged.
- **Verification Documentation & Test Logs**:
  - Added `docs/test-log.md` detailing automated and manual test runs across Chrome and SEB environments.
  - Added `docs/decisions.md` capturing architectural rationale for SEB anti-cheat gating.
