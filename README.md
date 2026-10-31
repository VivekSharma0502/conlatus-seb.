# Conlatus AI Interview Platform

A production-grade, full-stack AI technical interview platform featuring dynamic role curriculum generation, adaptive multi-turn audio/text conversational evaluation, deterministic rubric scoring, and an administrative telemetry command center.

---

## Project Structure

```text
├── backend/       # FastAPI application, Groq LLM & Whisper STT, async SQLAlchemy 2.0, pytest suite
├── frontend/      # Next.js App Router (Turbopack, Tailwind CSS, Specular components)
├── docs/          # Architecture, API design, and feature specifications
├── READMEs/       # Feature registry (FEATURES.md)
└── .dev/devlogs/  # Developer logs and technical release narratives
```

---

## Quickstart

### Prerequisites
- **Node.js**: `v18+` and **npm**: `v9+` (or **pnpm**: `v8+`)
- **Python**: `3.10+` with pip
- **Groq API Key**: Set `GROQ_API_KEY` in `backend/.env` (obtainable at [console.groq.com](https://console.groq.com))

---

### 1. Installation

Install Node.js dependencies from the repository root:
```bash
npm install
```
*(If you prefer pnpm, run `pnpm install`)*

Install Python backend dependencies:
```bash
pip install -r backend/requirements.txt
```

Configure your environment variables:
```bash
# In backend/.env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

---

### 2. Start the Backend (FastAPI on Port 8000)

> **Always start the backend from the `backend/` directory:**

```bash
cd backend
python -m uvicorn main:app --port 8000 --reload
```

> **Note:** `config.py` resolves `backend/.env` using an absolute path (relative to `__file__`), so it is CWD-independent. However running from `backend/` remains the canonical approach.

- **API Health Check:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Developer Testing Dashboard:** [http://localhost:8000/dev/dashboard](http://localhost:8000/dev/dashboard)

#### Environment Variables (`backend/.env`)

| Variable | Type | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | str | � | **Required.** Groq API key from [console.groq.com](https://console.groq.com) |
| `DATABASE_URL` | str | `sqlite+aiosqlite:///conlatus.db` | SQLAlchemy async DB URL |
| `JWT_SECRET_KEY` | str | (insecure default) | Change in production |
| `DEV_SKIP_SEB` | bool | `false` | Set `true` in dev to bypass Safe Exam Browser enforcement. A loud WARNING is logged on startup when enabled. |
| `SEB_CONFIG_KEY` | str | `""` | Comma-separated SEB config key hashes. Required when `DEV_SKIP_SEB=false`. |

---

### 3. Start the Frontend (Next.js on Port 3000)

From the repository root:
```bash
npm run frontend
```
*(Or with pnpm: `pnpm frontend`)*

- **Candidate Room:** [http://localhost:3000/](http://localhost:3000/)
- **Admin Dashboard Overview:** [http://localhost:3000/admin](http://localhost:3000/admin)
- **Candidate Pipeline Tracker:** [http://localhost:3000/admin/candidates](http://localhost:3000/admin/candidates)
- **Model Calibration & Settings:** [http://localhost:3000/admin/settings](http://localhost:3000/admin/settings)
- **Dynamic Interview Builder:** [http://localhost:3000/admin/setup](http://localhost:3000/admin/setup)

---

## Testing & Quality Assurance

- **Run Modular Test Suite (55 automated tests):**
  ```bash
  npm run test:backend
  ```
  *(Or directly: `python -m pytest backend/tests -v`)*

- **Build Frontend Production Bundle:**
  ```bash
  npm run build:frontend
  ```
  *(Or with pnpm: `pnpm build:frontend`)*

- **Lint Frontend:**
  ```bash
  npm run lint:frontend
  ```
