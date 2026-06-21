#!/usr/bin/env python3
"""HTTP client smoke tests for the DevOps Agent API."""
import sys
import httpx

BASE = "http://localhost:8000/api/v1"

# Fresh credentials per run to avoid collisions
EMAIL = f"smoke_{__import__('time').time_ns()}@test.com"
PASSWORD = "testsecret"

passed = 0
failed = 0


def check(name: str, condition: bool, got=None):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} — got: {got}")
        failed += 1


print("=== HTTP Client Smoke Tests ===\n")

# ── Register ──────────────────────────────────────────────────────────
print("[1/10] POST /auth/register")
r = httpx.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": PASSWORD})
check("register returns 201", r.status_code == 201, r.status_code)
token = r.json().get("access_token", "")
check("token returned", bool(token))

headers = {"Authorization": f"Bearer {token}"}

# ── Login ─────────────────────────────────────────────────────────────
print("\n[2/10] POST /auth/login")
r = httpx.post(
    f"{BASE}/auth/login",
    data={"username": EMAIL, "password": PASSWORD},
)
check("login returns 200", r.status_code == 200, r.status_code)
token2 = r.json().get("access_token", "")
check("token returned on login", bool(token2))
headers2 = {"Authorization": f"Bearer {token2}"}

# ── Projects CRUD ─────────────────────────────────────────────────────
print("\n[3/10] Projects CRUD")
r = httpx.post(f"{BASE}/projects/", json={"name": "Test Project"}, headers=headers)
check("create project returns 201", r.status_code == 201, r.status_code)
project_id = r.json().get("id")

r = httpx.get(f"{BASE}/projects/", headers=headers)
check("list projects returns 200", r.status_code == 200, r.status_code)
check("project in list", any(p.get("id") == project_id for p in r.json()), r.json())

r = httpx.get(f"{BASE}/projects/{project_id}", headers=headers)
check("get project returns 200", r.status_code == 200, r.status_code)
check("project name matches", r.json().get("name") == "Test Project", r.json())

# ── Runs CRUD ─────────────────────────────────────────────────────────
print("\n[4/10] Runs CRUD")
r = httpx.post(f"{BASE}/runs/", json={"project_id": project_id}, headers=headers)
check("create run returns 201", r.status_code == 202, r.status_code)
run_id = r.json().get("run_id")

r = httpx.get(f"{BASE}/runs/?project_id={project_id}", headers=headers)
check("list runs returns 200", r.status_code == 200, r.status_code)

r = httpx.get(f"{BASE}/runs/{run_id}", headers=headers)
check("get run returns 200", r.status_code == 200, r.status_code)

# ── Video Jobs ────────────────────────────────────────────────────────
print("\n[5/10] Video Jobs")
r = httpx.post(
    f"{BASE}/video/jobs",
    json={"prompt": "Test video prompt", "project_id": project_id},
    headers=headers,
)
check("create video job returns 201", r.status_code == 201, r.status_code)
video_id = r.json().get("id")

r = httpx.get(f"{BASE}/video/jobs", headers=headers)
check("list video jobs returns 200", r.status_code == 200, r.status_code)
check("video job in list", any(v.get("id") == video_id for v in r.json()), r.json())

r = httpx.get(f"{BASE}/video/jobs/{video_id}", headers=headers)
check("get video job returns 200", r.status_code == 200, r.status_code)

# ── Agents ────────────────────────────────────────────────────────────
print("\n[6/10] Agents")
r = httpx.post(
    f"{BASE}/agents/",
    json={"name": f"agent-{project_id}", "capabilities": '["dockerfile"]'},
    headers=headers,
)
check("register agent returns 201", r.status_code == 201, r.status_code)
agent_id = r.json().get("id")

r = httpx.get(f"{BASE}/agents/", headers=headers)
check("list agents returns 200", r.status_code == 200, r.status_code)
check("agent in list", any(a.get("id") == agent_id for a in r.json()), r.json())

r = httpx.get(f"{BASE}/agents/{agent_id}", headers=headers)
check("get agent returns 200", r.status_code == 200, r.status_code)

# ── Agent Heartbeat ───────────────────────────────────────────────────
print("\n[7/10] Agent Heartbeat")
r = httpx.post(
    f"{BASE}/agents/{agent_id}/heartbeat",
    json={"status": "busy"},
    headers=headers,
)
check("heartbeat returns 200", r.status_code == 200, r.status_code)
check("status updated", r.json().get("status") == "busy", r.json())

# ── Evaluation ────────────────────────────────────────────────────────
print("\n[8/10] Evaluation")
r = httpx.post(
    f"{BASE}/evaluation/",
    json={
        "predictions": [1, 0, 1, 1, 0],
        "ground_truth": [1, 0, 1, 0, 0],
        "project_id": project_id,
    },
    headers=headers,
)
check("create evaluation returns 201", r.status_code == 201, r.status_code)
eval_id = r.json().get("id")
check("kappa score returned", isinstance(r.json().get("score"), float), r.json())

r = httpx.get(f"{BASE}/evaluation/", headers=headers)
check("list evaluations returns 200", r.status_code == 200, r.status_code)

r = httpx.get(f"{BASE}/evaluation/{eval_id}", headers=headers)
check("get evaluation returns 200", r.status_code == 200, r.status_code)

# ── Admin Health ──────────────────────────────────────────────────────
print("\n[9/10] Admin Health")
r = httpx.get(f"{BASE}/admin/health", headers=headers)
check("health returns 200", r.status_code == 200, r.status_code)

# ── Admin Stats ───────────────────────────────────────────────────────
print("\n[10/10] Admin Stats")
r = httpx.get(f"{BASE}/admin/stats", headers=headers)
check("stats returns 200", r.status_code == 200, r.status_code)

# ── Summary ───────────────────────────────────────────────────────────
print(f"\nPASS: {passed}/10")
if failed > 0:
    print(f"FAIL: {failed}/10")
    sys.exit(1)
else:
    sys.exit(0)