# ManagerGPT

ManagerGPT is a full-stack decision support platform that simulates an autonomous AI workforce to evaluate business ideas. It coordinates planning, research, analysis, critique, and decision defense workflows, then generates a final recommendation with confidence, rationale, and export/share capabilities.

## What ManagerGPT does

Given a business goal, ManagerGPT:
- Creates a structured research and analysis session
- Orchestrates multiple specialized agents (planner, researcher, analyst, critic, etc.)
- Streams real-time agent activity to the frontend dashboard
- Produces a final business recommendation (for example: `PROCEED`, `STOP`, `INVESTIGATE`)
- Surfaces confidence, supporting context, and structured report data

## Core features

- **Agent-orchestrated workflow** for end-to-end business evaluation
- **Real-time updates (SSE)** to show progress and agent logs live
- **Session persistence (SQLite)** for historical analysis and reporting
- **Approval gates** that let users approve/reject intermediate steps
- **File uploads** (`.txt`, `.csv`, `.xlsx`, `.xls`, `.pdf`) for context-aware analysis
- **Shareable report links** and **PDF export** endpoint
- **Frontend dashboard** for interactive session execution and final report viewing

## Tech stack

### Backend
- Python 3.12
- FastAPI + Uvicorn
- SQLite
- Pydantic
- SSE (Server-Sent Events via `sse-starlette`)

### Frontend
- React 18
- Vite
- Tailwind CSS

### Tooling / Tests
- Pytest (backend API endpoint tests)
- GitHub Actions CI
- Docker / Docker Compose

## Project structure

```text
backend/                 FastAPI app, agents, orchestration, database layer
frontend/                React + Vite web app
schema.sql               SQLite schema
Dockerfile               Backend container image definition
docker-compose.yml       Local multi-service dev setup
.env.example             Environment template
```

## Environment setup

1. Copy environment template:

```bash
cp .env.example .env
```

2. Fill in your API keys inside `.env`.

### Environment variables

```env
OPEN_ROUTER_API_KEY=your_openrouter_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
SCRAPEGRAPH_API_KEY=your_scrapegraph_api_key_here
DEMO_DELAY_SECONDS=0
RESEARCH_CONCURRENCY=3
OPENROUTER_TIMEOUT_SECONDS=15
```

## Run locally (without Docker)

### Backend

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend default URL: `http://localhost:5173`  
Backend default URL: `http://localhost:8001`

## Run with Docker Compose

```bash
docker compose up --build
```

This starts:
- Backend at `http://localhost:8001`
- Frontend at `http://localhost:5173`

## API overview

- `POST /api/execute` — start a new business evaluation session
- `GET /api/stream/{session_id}` — stream live agent updates
- `GET /api/session/{session_id}` — fetch session result details
- `GET /api/sessions` — list previous sessions
- `POST /api/session/{session_id}/share` — create a public report link
- `GET /report/{share_token}` — fetch shared report content
- `GET /api/session/{session_id}/export/pdf` — export report as PDF
- `POST /api/upload` — upload supporting documents
- `GET /api/approvals/{session_id}/pending` — list pending approvals
- `POST /api/approvals/{gate_id}/respond` — respond to an approval gate

## Testing

Run backend API tests:

```bash
pytest backend/tests -q
```

## Screenshots

> Add your product screenshots under `docs/screenshots/` and keep these links updated.

### Dashboard

![ManagerGPT Dashboard](docs/screenshots/dashboard.png)

### Live agent workflow

![ManagerGPT Live Workflow](docs/screenshots/live-workflow.png)

### Final report

![ManagerGPT Final Report](docs/screenshots/final-report.png)

## Suggested GitHub topics

If you are maintaining this repo on GitHub, useful topic tags include:

- `fastapi`
- `react`
- `multi-agent`
- `business-intelligence`
- `decision-support`
- `ai`
- `sqlite`
- `vite`

## CI

A GitHub Actions workflow is included to run backend tests and frontend build checks on pushes and pull requests.
