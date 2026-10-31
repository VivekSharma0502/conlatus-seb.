# Architecture Decision Records (ADR)

This document captures key technical and architectural decisions for the Conlatus platform.

---

## ADR-001: Anti-Cheat Gating via Safe Exam Browser (SEB)

### Status
Accepted

### Context
Technical interviews conducted remotely require security against unauthorized browser extensions, external screen sharing, unauthorized tabs, and automated response assistance. Custom browser extensions can be bypassed or disabled.

### Decision
Integrate **Safe Exam Browser (SEB)** as the primary anti-cheat runtime:
1. SEB locks down the operating system kiosk mode, preventing task switching, screenshots, copy-paste, and external application execution.
2. SEB signs all HTTP requests with cryptographic header hashes:
   - `X-SafeExamBrowser-ConfigKeyHash = SHA256(URL + ConfigKey)`
3. The backend validates this hash on all stateful interview endpoints (`/interview/*`) before processing.
4. When `DEV_SKIP_SEB=true`, developers can bypass the check for rapid local iteration, but a loud warning is emitted on server startup.

### Consequences
- **Positive:** Robust OS-level kiosk security without maintaining proprietary desktop binaries.
- **Negative:** Candidates must have SEB installed on their machine; mitigated by providing a pre-flight download gate at `/interview/[code]`.

---

## ADR-002: Absolute `.env` Path Resolution in Pydantic Settings

### Status
Accepted

### Context
`pydantic-settings` defaults to resolving `env_file=".env"` relative to the current working directory of the process. In development, developers frequently launch commands from either the repository root (`c:\seb`) or the backend directory (`c:\seb\backend`). When different `.env` files existed or when CWD differed, settings loaded inconsistent configuration, leading to intermittent 403 vs 405 behavior.

### Decision
Anchor the `.env` path in `backend/core/config.py` using `Path(__file__).resolve().parent.parent / ".env"`.

### Consequences
- Guaranteed deterministic loading of `backend/.env` regardless of where `uvicorn`, `pytest`, or `python` is invoked.

---

## ADR-003: Dual Candidate URL Matching for SEB Middleware

### Status
Accepted

### Context
In SEB 3.x on Windows, JavaScript `fetch()` calls originating from a webpage inside SEB's browser engine calculate the `X-SafeExamBrowser-ConfigKeyHash` using the top-level webpage URL (e.g., `http://localhost:3000/interview/demo`) rather than the destination API endpoint URL (e.g., `http://localhost:8000/interview/start`). Standard browsers also default to `strict-origin-when-cross-origin` referrer policy, truncating the `Referer` header to the origin and stripping the path.

### Decision
1. **Frontend:** Configure `referrerPolicy: "unsafe-url"` on all client-side API fetches to transmit the complete page URL in the `Referer` header.
2. **Backend:** In `SEBMiddleware`, test the incoming hash against two candidate URLs:
   - Candidate (a): The API request URL (`request.url`).
   - Candidate (b): The `Referer` header with any `#fragment` removed.
3. Accept the request if `hmac.compare_digest(SHA256(candidate + key), sent)` matches for either candidate and any configured key.

### Consequences
- Both direct page loads and subsequent client-side AJAX/fetch requests from inside SEB are reliably authenticated.
- Timing attack resistance is preserved via constant-time comparison.

---

## ADR-004: CORS Middleware Placement Relative to Security Middleware

### Status
Accepted

### Context
When requests originate from a frontend on `http://localhost:3000` to a backend on `http://localhost:8000`, browsers send CORS preflight `OPTIONS` requests and require `Access-Control-Allow-Origin` on error responses (like `403 Forbidden`). If security middleware intercepts requests before CORS middleware, preflights fail with 403 and responses lack CORS headers, causing opaque browser network errors.

### Decision
1. Register `SEBMiddleware` first, and `CORSMiddleware` second in `main.py`. Because Starlette middleware wraps in reverse order, `CORSMiddleware` executes outermost on incoming requests and outgoing responses.
2. Explicitly bypass SEB validation for `request.method == "OPTIONS"`.

### Consequences
- Preflight `OPTIONS` requests receive immediate 200 OK responses with allowed methods and headers.
- When SEB check fails with `403 Forbidden`, `CORSMiddleware` attaches `Access-Control-Allow-Origin: http://localhost:3000`, enabling the frontend to display the user-friendly SEB warning screen.

---

## ADR-005: Safe Logging & Secrets Policy

### Status
Accepted

### Context
Diagnostic logging can inadvertently log sensitive tokens, SEB config keys, or user credentials into server logs or test runners.

### Decision
1. Never log full keys, tokens, or raw secrets.
2. On startup, log only whether `SEB_CONFIG_KEY` is configured (boolean `True`/`False`).
3. On verification failure, log only safe metadata: the request URL, whether a header was present, and status codes.
4. Remove temporary debugging pages and diagnostic helpers before marking tasks as complete.

### Consequences
- Logs remain clean, safe for telemetry aggregation, and compliant with production security guidelines.

