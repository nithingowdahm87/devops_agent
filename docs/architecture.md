# DevOps Agent SaaS — Architecture

## System Overview

```
                              ┌─────────────────────────────┐
                              │          Clients            │
                              │  Web UI / CLI / HTTP API    │
                              └──────────────┬──────────────┘
                                             │ HTTP/REST
                                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                             │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐    │
│  │   Auth   │  │ Projects │  │  Runs    │  │   Video Jobs         │    │
│  │ Router   │  │ Router   │  │ Router   │  │   Router             │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐    │
│  │  Agents  │  │Evaluation│  │  Admin   │  │  Observability       │    │
│  │ Router   │  │ Router   │  │ Router   │  │  Logging Middleware  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────────┘    │
│       │             │             │                                     │
└───────┼─────────────┼─────────────┼─────────────────────────────────────┘
        │             │             │
        ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          CRUD Layer (SQLAlchemy ORM)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐  │
│  │  Users   │  │ Projects │  │  Runs    │  │ VideoTasks / Agents /  │  │
│  │          │  │          │  │          │  │ EvaluationResults      │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Database (SQLite / Postgres)                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

| Component | Technology | Responsibility |
|---|---|---|
| **FastAPI App** | FastAPI + Uvicorn | HTTP server, routing, middleware, lifespan |
| **Auth Router** | `src/api/routers/auth.py` | Register, login → JWT token generation |
| **Projects Router** | `src/api/routers/projects.py` | CRUD for DevOps pipeline projects |
| **Runs Router** | `src/api/routers/runs.py` | CI/CD run lifecycle (queue → run → complete/fail) |
| **Video Router** | `src/api/routers/video.py` | Async video generation job submission & status |
| **Agents Router** | `src/api/routers/agents.py` | SaaS agent registry, heartbeat, capabilities |
| **Evaluation Router** | `src/api/routers/evaluation.py` | Cohen's kappa evaluation scoring |
| **Admin Router** | `src/api/routers/admin.py` | Health checks, system stats |
| **CRUD Layer** | `src/db/crud.py` + feature modules | Database operations per entity |
| **Models** | `src/db/models.py` + feature models | SQLAlchemy ORM table definitions |
| **Schemas** | `src/schemas.py` + feature schemas | Pydantic validation models |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Persistent storage via SQLAlchemy |
| **Observability** | `src/observability/logging.py` | Structured JSON logging, request middleware |

## CLI Integration

The FastAPI server is complemented by a CLI entry-point (`main.py --mode server`) and a Kimchi CLI agent (`src/agent/`) that:
- Analyzes codebases (Stage 1: Code Discovery)
- Routes to LLM providers (Stage 2: Multi-Provider Router)
- Generates GitOps pipelines (Stage 3: Pipeline Generation)
- Validates and heals artifacts (Stage 4: OODA Healing)
- Outputs structured artifacts (Stage 5: Artifact Hierarchy)

## Data Flow

1. **Client** authenticates via `POST /api/v1/auth/login` → receives JWT
2. **Client** creates a project via `POST /api/v1/projects/` with JWT bearer token
3. **Client** starts a run via `POST /api/v1/runs/` → agent picks up work
4. **Optional**: Client submits a video job via `POST /api/v1/video/jobs`
5. **Optional**: Client registers agents via `POST /api/v1/agents/` and sends heartbeats
6. **Optional**: Client runs evaluations via `POST /api/v1/evaluation/` (Cohen's kappa)
7. All resources scoped to the authenticated user via `get_current_user` dependency