# DevOps Agent SaaS — API Reference

Base URL: `http://localhost:8000/api/v1`

All authenticated endpoints require:
```
Authorization: Bearer <access_token>
```

---

## Authentication

### `POST /api/v1/auth/register`
Register a new user account.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "<password>"
}
```
**Response:** `201 Created`
```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

---

### `POST /api/v1/auth/login`
Login with existing credentials (form-encoded).

**Request body (form):** `username=email&password=password`

**Response:** `200 OK`
```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

---

## Projects

### `GET /api/v1/projects/`
List all projects for the authenticated user.

**Response:** `200 OK` — array of project objects.

---

### `POST /api/v1/projects/`
Create a new project.

**Request body:**
```json
{
  "name": "my-service",
  "description": "Optional description",
  "repo_url": "https://github.com/user/repo"
}
```
**Response:** `201 Created`

---

### `GET /api/v1/projects/{id}`
Get a single project by ID.

**Response:** `200 OK` or `404 Not Found`

---

### `PUT /api/v1/projects/{id}`
Update a project.

**Request body:** partial project fields.

**Response:** `200 OK`

---

### `DELETE /api/v1/projects/{id}`
Delete a project.

**Response:** `204 No Content`

---

## Runs

### `GET /api/v1/runs/`
List all runs for the authenticated user.

**Query params:** `skip=0`, `limit=100`

**Response:** `200 OK` — array of run objects.

---

### `POST /api/v1/runs/`
Create a new run (kick off a pipeline).

**Request body:**
```json
{
  "project_id": 1,
  "config": "{\"stage\": \"dockerfile\"}"
}
```
**Response:** `201 Created`

---

### `GET /api/v1/runs/{id}`
Get a single run by ID.

**Response:** `200 OK` or `404 Not Found`

---

### `PUT /api/v1/runs/{id}`
Update run status/stage/results.

**Request body:** `status`, `stage`, `results`, `logs`

**Response:** `200 OK`

---

### `DELETE /api/v1/runs/{id}`
Delete a run.

**Response:** `204 No Content`

---

## Video Jobs

### `POST /api/v1/video/jobs`
Submit a video generation job.

**Request body:**
```json
{
  "prompt": "Generate a demo video for the login flow",
  "project_id": 1
}
```
**Response:** `201 Created` — VideoTask object.

---

### `GET /api/v1/video/jobs`
List all video tasks for the authenticated user.

**Query params:** `skip=0`, `limit=100`

**Response:** `200 OK` — array of VideoTask objects.

---

### `GET /api/v1/video/jobs/{task_id}`
Get a specific video task.

**Response:** `200 OK` or `404 Not Found`

---

## Agents

### `POST /api/v1/agents/`
Register a new agent.

**Request body:**
```json
{
  "name": "builder-agent-1",
  "capabilities": "[\"dockerfile\", \"github-actions\"]"
}
```
**Response:** `201 Created` — Agent object.

---

### `GET /api/v1/agents/`
List all agents for the authenticated user.

**Response:** `200 OK` — array of Agent objects.

---

### `GET /api/v1/agents/{id}`
Get a specific agent by ID.

**Response:** `200 OK` or `404 Not Found`

---

### `POST /api/v1/agents/{id}/heartbeat`
Send an agent heartbeat (updates last_heartbeat timestamp and status).

**Request body:**
```json
{
  "status": "busy"
}
```
**Response:** `200 OK` — updated Agent object or `404 Not Found`.

---

## Evaluation

### `POST /api/v1/evaluation/`
Compute Cohen's kappa score and store the evaluation result.

**Request body:**
```json
{
  "predictions": [1, 0, 1, 1, 0],
  "ground_truth": [1, 0, 1, 0, 0],
  "project_id": 1
}
```
**Response:** `201 Created`
```json
{
  "id": 1,
  "metric": "cohens_kappa",
  "score": 0.666...,
  "created_at": "2026-06-09T12:00:00Z"
}
```

---

### `GET /api/v1/evaluation/`
List all evaluation results for the authenticated user.

**Query params:** `skip=0`, `limit=100`

**Response:** `200 OK` — array of EvaluationRead objects (predictions/ground_truth decoded from JSON).

---

### `GET /api/v1/evaluation/{id}`
Get a specific evaluation result.

**Response:** `200 OK` or `404 Not Found`

---

## Admin

### `GET /api/v1/admin/health`
Health check endpoint.

**Response:** `200 OK` — system health status.

---

### `GET /api/v1/admin/stats`
System statistics (requires admin privileges).

**Response:** `200 OK` — stats object.

---

## Error Responses

| Status | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — insufficient permissions |
| `404` | Resource not found |
| `422` | Pydantic validation error |
| `500` | Internal server error |