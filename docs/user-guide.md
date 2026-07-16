# DevOps Agent SaaS — User Guide

This guide walks you through the complete user journey from registration to viewing agent health.

---

## Step 1 — Register an Account

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "<password>"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Save the `access_token` — you will use it for all authenticated requests.

---

## Step 2 — Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=alice@example.com&password=<password>"
```

Returns the same `access_token` structure.

---

## Step 3 — Create a Project

```bash
curl -X POST http://localhost:8000/api/v1/projects/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-service",
    "description": "Node.js Express API",
    "repo_url": "https://github.com/user/my-service"
  }'
```

**Response:** `201 Created` with project object containing `id`.

---

## Step 4 — Start a Run

```bash
curl -X POST http://localhost:8000/api/v1/runs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "config": "{\"stage\": \"dockerfile\"}"}'
```

Poll run status with:
```bash
curl http://localhost:8000/api/v1/runs/1 \
  -H "Authorization: Bearer <token>"
```

---

## Step 5 — Create a Video Job

```bash
curl -X POST http://localhost:8000/api/v1/video/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate a demo video for the login flow", "project_id": 1}'
```

Check status:
```bash
curl http://localhost:8000/api/v1/video/jobs/1 \
  -H "Authorization: Bearer <token>"
```

---

## Step 6 — Register an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "builder-agent-1", "capabilities": "[\"dockerfile\", \"github-actions\"]"}'
```

---

## Step 7 — Send Agent Heartbeat

```bash
curl -X POST http://localhost:8000/api/v1/agents/1/heartbeat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "busy"}'
```

---

## Step 8 — Run an Evaluation

```bash
curl -X POST http://localhost:8000/api/v1/evaluation/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "predictions": [1, 0, 1, 1, 0],
    "ground_truth": [1, 0, 1, 0, 0],
    "project_id": 1
  }'
```

**Response:**
```json
{
  "id": 1,
  "metric": "cohens_kappa",
  "score": 0.6666666666666666,
  "created_at": "2026-06-09T12:00:00Z"
}
```

---

## Step 9 — View Agent Health (Admin)

```bash
curl http://localhost:8000/api/v1/admin/health \
  -H "Authorization: Bearer <token>"
```

```bash
curl http://localhost:8000/api/v1/admin/stats \
  -H "Authorization: Bearer <token>"
```

---

## Running the Server

```bash
cd /home/nithin/repos/devops_agent
source venv/bin/activate
python main.py --mode server --port 8000
```

API docs available at `http://localhost:8000/api/docs` (Swagger UI).