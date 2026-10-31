# Conlatus AI Interview Platform

A production-grade, full-stack AI technical interview platform featuring dynamic role curriculum generation, adaptive multi-turn audio/text conversational evaluation, deterministic rubric scoring, and an administrative telemetry command center with Safe Exam Browser (SEB) anti-cheat gating.

---

## Project Structure

```text
├── backend/       # FastAPI application, Groq LLM & Whisper STT, async SQLAlchemy 2.0, pytest suite
├── frontend/      # Next.js App Router (Turbopack, Tailwind CSS, Framer Motion, Specular UI)
├── docs/          # Architecture, decisions, API design, and verification logs
├── READMEs/       # Feature registry (FEATURES.md)
└── seb/           # Safe Exam Browser configuration files (.seb)
```

---

## Prerequisites

- **Node.js**: `v18+` and **npm**: `v9+`
- **Python**: `3.10+` with `pip`
- **Groq API Key**: Obtainable at [console.groq.com](https://console.groq.com)
- **Safe Exam Browser** (optional for dev): Version 3.x+ for Windows/macOS if testing anti-cheat enforcement.

---

## Quickstart

### 1. Installation

Install Node.js dependencies from the repository root:
```bash
npm install
```

Install Python backend dependencies:
```bash
pip install -r backend/requirements.txt
```

---

### 2. Configure Environment Variables

#### Backend (`backend/.env`)
Create `backend/.env` (see `backend/.env.example`):
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
DATABASE_URL=sqlite+aiosqlite:///conlatus.db
JWT_SECRET_KEY=conlatus_super_secret_jwt_key_2026_change_in_production_32bytes

# Safe Exam Browser Enforcement
DEV_SKIP_SEB=false
SEB_CONFIG_KEY=your_seb_config_key_hash_here
```

| Variable | Type | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | str | — | **Required.** Groq API key for LLM and Whisper STT. |
| `DATABASE_URL` | str | `sqlite+aiosqlite:///conlatus.db` | SQLAlchemy async DB connection string. |
| `JWT_SECRET_KEY` | str | default dev secret | Secret key used to sign session JWTs. |
| `DEV_SKIP_SEB` | bool | `false` | If `true`, bypasses all Safe Exam Browser checks. A loud startup warning is logged. |
| `SEB_CONFIG_KEY` | str | `""` | Comma-separated SEB Config Key hashes. Required when `DEV_SKIP_SEB=false`. |

#### Frontend (`frontend/.env.local`)
Create `frontend/.env.local` (see `frontend/.env.example`):
```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SEB_CONFIG_HOST=localhost:8000
```

| Variable | Type | Default | Description |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | str | `http://localhost:8000` | Backend REST API base URL. |
| `NEXT_PUBLIC_SEB_CONFIG_HOST` | str | `localhost:8000` | Host (host:port) serving `/seb/config.seb` for deep-link generation. |

---

### 3. Canonical Start Commands

#### Start the Backend (Port 8000)
> **Always start the backend from the `backend/` directory:**
```bash
cd backend
python -m uvicorn main:app --port 8000 --reload
```
- Startup logs confirm whether SEB check is `ENABLED` or `DISABLED (DEV_SKIP_SEB=true)` and whether `SEB_CONFIG_KEY` is configured (boolean flag only, keys are never logged).
- `config.py` resolves `backend/.env` using an absolute path relative to `__file__`, guaranteeing the correct environment is loaded regardless of current working directory.

#### Start the Frontend (Port 3000)
```bash
cd frontend
npm run dev
```

---

## Application Routes

### Candidate Interface (Frontend: Port 3000)
- **Landing Page & Quick Access:** `http://localhost:3000/`
- **Direct Access Code Entrance:** `http://localhost:3000/interview/[code]`
  - If opened outside SEB: Displays the branded **Safe Exam Browser Required** gate with download buttons and the deep-link launcher (`seb://localhost:8000/seb/config.seb`).
  - If opened inside SEB: Directly enters the interview staging room.
- **Active Interview Room:** `http://localhost:3000/interview` (interactive audio/text dialogue).

### Admin & Recruiter Suite (Frontend: Port 3000)
- **Admin Login:** `http://localhost:3000/admin/login`
- **Dashboard Overview:** `http://localhost:3000/admin`
- **Candidate Pipeline:** `http://localhost:3000/admin/candidates`
- **Interview Template Setup:** `http://localhost:3000/admin/setup`
- **Settings & Model Calibrations:** `http://localhost:3000/admin/settings`

### Backend Endpoints (Port 8000)
- **Health Check:** `GET http://localhost:8000/`
- **SEB Config File:** `GET / HEAD http://localhost:8000/seb/config.seb` (serves `conlatus.seb` with `application/octet-stream`)
- **API Documentation (Swagger):** `http://localhost:8000/docs`
- **Developer Test Dashboard:** `http://localhost:8000/dev/dashboard`

---

## Safe Exam Browser (SEB) Architecture

1. **Gating Model**: Endpoints under `/interview/` (such as `POST /interview/join`, `POST /interview/start`, `POST /interview/{sid}/audio-message`) require valid SEB verification when `DEV_SKIP_SEB=false`.
2. **Public Exceptions**: `/interview/details/{code}` (pre-join check), `/seb/config.seb` (config download), and all root routes are public.
3. **Dual Candidate Matching**:
   - Because fetch calls from the candidate page can be signed by SEB using either the request URL or the calling page's URL, the backend computes hashes against two candidate URLs:
     - Candidate (a): The API request URL (e.g. `http://localhost:8000/interview/start`).
     - Candidate (b): The calling page URL from the `Referer` header (e.g. `http://localhost:3000/interview/demo`), with any `#fragment` removed.
   - The frontend sets `referrerPolicy: "unsafe-url"` across API calls so the full page URL is transmitted in `Referer`.
   - Matching uses constant-time comparison (`hmac.compare_digest`).
4. **CORS Integration**: `CORSMiddleware` is configured outermost so preflight `OPTIONS` requests pass through untouched and 403 Forbidden responses still include valid `Access-Control-Allow-Origin` headers.

---

## How to Test

### 1. Verification with curl (Outside SEB)
```bash
# Protected endpoint must return 403 Forbidden when DEV_SKIP_SEB=false:
curl -s -o - -w "\nHTTP %{http_code}\n" http://localhost:8000/interview/start

# Public endpoints return 200:
curl -s -o - -w "\nHTTP %{http_code}\n" http://localhost:8000/interview/details/demo
curl -s -I http://localhost:8000/seb/config.seb
```

### 2. End-to-End Test Inside SEB
1. Launch `conlatus.seb` or open `seb://localhost:8000/seb/config.seb` in your browser.
2. SEB starts with the configured start URL (`http://localhost:3000/interview/demo`).
3. Complete the microphone test and join the interview.
4. Speak your answer; Whisper transcribes the response and the interview progresses through the multi-turn evaluation loop.
