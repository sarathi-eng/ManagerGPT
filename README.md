# ManagerGPT

An AI-powered business analysis platform that uses a multi-agent system to evaluate business ideas, providing comprehensive reports with competitive analysis, risk assessment, and strategic recommendations.

## Features

- **Multi-Agent Orchestration** — Specialized AI agents collaborate to research, analyze, and critique business ideas
- **Real-Time Dashboard** — Stream agent activity as it happens via Server-Sent Events
- **Comprehensive Reports** — Pros/cons, sustainability scores, investment estimates, competitor & vendor analysis, and more
- **Hallucination Detection** — Cross-references AI claims against source material
- **Approval Gates** — Pause execution for user confirmation before costly research steps
- **Document Upload** — Attach PDFs, spreadsheets, or text files as additional context
- **PDF Export & Shareable Links** — Export reports or share them via unique URLs

## Architecture

```
frontend/          React + Vite + Tailwind CSS
backend/           FastAPI (Python)
  ├── agents/      AI agents (Planner, Researcher, Business Analyst,
  │                Competitor Analyst, Critic, Strategist, and more)
  ├── utils/       LLM helpers, JSON parsing, search, retry logic
  ├── main.py      API endpoints
  ├── orchestrator.py  Workflow coordination
  ├── database.py  SQLite persistence
  └── models.py    Pydantic models
schema.sql         Database schema
```

### Agent Pipeline

1. **Classifier** — Detects business type and industry
2. **Planner** — Breaks the user goal into research tasks
3. **Researcher** — Gathers data via web search (Tavily)
4. **Business Analyst** — Produces a comprehensive analysis with recommendation
5. **Business Strategist** — Generates break-even, pricing, launch, and unit-economics strategy
6. **Hallucination Detector** — Flags unsupported claims
7. **Competitor Analyst** — Maps the competitive landscape
8. **Critic** — Reviews and challenges the analysis
9. **Narrative Generator** — Writes an executive summary
10. **Decision Defender** — Argues why alternatives were rejected

## Prerequisites

- Python 3.10+
- Node.js 18+

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sarathi-eng/ManagerGPT.git
cd ManagerGPT
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
OPEN_ROUTER_API_KEY=your-openrouter-api-key
TAVILY_API_KEY=your-tavily-api-key

# Optional
SCRAPEGRAPH_API_KEY=your-scrapegraph-api-key
DEMO_DELAY_SECONDS=0
RESEARCH_CONCURRENCY=3
OPENROUTER_TIMEOUT_SECONDS=15
```

### 3. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Running

### Start the backend

```bash
uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Start the frontend

```bash
cd frontend
npm run dev
```

The UI will be available at `http://localhost:5173`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/execute` | Start a new analysis session |
| `GET` | `/api/stream/{session_id}` | Stream real-time agent activity (SSE) |
| `GET` | `/api/session/{session_id}` | Get full session report |
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/session/{session_id}/share` | Create a shareable report link |
| `GET` | `/api/session/{session_id}/export/pdf` | Export report as PDF |
| `POST` | `/api/upload` | Upload a document (PDF, CSV, XLSX, TXT) |
| `GET` | `/api/approvals/{session_id}/pending` | Get pending approval gates |
| `POST` | `/api/approvals/{gate_id}/respond` | Approve or reject a gate |

## Tech Stack

- **Backend:** FastAPI, Pydantic, SQLite, httpx, SSE-Starlette
- **Frontend:** React 18, Vite, Tailwind CSS, Lucide React
- **AI:** OpenRouter (LLM gateway), Tavily (web search)
- **Reports:** ReportLab (PDF generation), PyPDF2, Pandas

## License

This project is provided as-is. See the repository for license details.
