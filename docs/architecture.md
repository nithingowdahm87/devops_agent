# devops_agent — Architecture

> **Version**: 2.x CLI-only | **LLM**: NVIDIA NIM | **Stack**: Generic K8s (EKS/GKE/bare-metal)

## Overview

devops_agent is a **CLI-only** single-process Python tool. There is no server, no
database, no background workers, and no API. One invocation runs the full pipeline
and exits with a structured exit code.

## End-to-End Pipeline

```
main.py (argparse)
└─► src/entrypoints/cli_main.run_cli()
      ├─ load_or_run_analysis(project_path)
      │     └─ CodeAnalysisAgent.analyze()
      │           ├─ ContextGatherer (raw text dump of project files)
      │           ├─ heuristic detectors (_detect_node, _detect_python,
      │           │   _detect_architecture, _detect_ports, _detect_env_vars)
      │           └─ ProjectContext (Pydantic v2) → .devops_context.json cache
      │
      └─ V2Orchestrator.run_pipeline()
            ├─ ArchitecturePlanner.create_plan()  → ArchitecturePlan
            ├─ _isolate_context() per service
            │     └─ loads resource profile from configs/resource_profiles.yaml
            │        keyed by environment (dev/staging/prod) + stack type
            │
            └─ for stage in [dockerfile, docker_compose, kubernetes,
                              ingress, secrets, github_actions]:
                  _execute_stage()
                    ├─ _build_prompt()
                    │     └─ load configs/prompts/{stage}/{role}.md
                    │        render via Jinja2 SandboxedEnvironment
                    │        (context filtered to ALLOWED_TEMPLATE_VARS only)
                    ├─ LLMGenerator.generate()
                    │     ├─ _fetch_rag_snippet() → ChromaDB local store (optional)
                    │     └─ NvidiaClient.call() → NVIDIA NIM API
                    ├─ heuristic scoring → InfraSpec.security_score
                    ├─ Evaluator.evaluate_candidates() → weighted_score()
                    ├─ Validator.validate()
                    │     ├─ hadolint (Dockerfiles)
                    │     ├─ kubeconform (K8s manifests)
                    │     ├─ yamllint (GitHub Actions)
                    │     └─ jsonschema (ArgoCD, GHA schemas)
                    ├─ PolicyEngine.validate_artifact()
                    │     ├─ Python rules (prod/dev environment-aware)
                    │     └─ OPA/Rego evaluation (policies/k8s/manifests.rego)
                    ├─ Healer.heal() — NvidiaClient.call() with error context
                    │   (skipped if --no-heal)
                    └─ ArtifactManager.write_gate()
                          ├─ CRITICAL → blocked entirely
                          ├─ HIGH     → .broken file (prod) or write-through (dev)
                          ├─ MEDIUM/LOW → written to outputs/
                          ├─ dry_run  → history only, no primary write
                          └─ always   → .artifacts_history/<env>/<run_id>/
```

## Output Structure

```
outputs/
  per-service/<svc>/
    Dockerfile
    .dockerignore
    k8s/
      deployment.yaml  service.yaml  hpa.yaml  pdb.yaml
      netpol.yaml      ingress.yaml
    secrets/
      sealedsecret.yaml          (or vault_policy.hcl / external-secret.yaml)
      SECRETS_REFERENCE.md
    .github/workflows/
      <svc>-ci.yml
  shared/
    docker-compose.yml

.artifacts_history/<env>/<run_id>/   ← immutable audit trail, every run
audit_logs/<run_id>.json             ← structured run summary
```

## Module Map

```
src/
  entrypoints/    cli_main.py — CLI parsing, SIGTERM handler, audit log write
  decision_engine/
    orchestrator.py          — V2Orchestrator, stage loop, _isolate_context
    planner/                 — ArchitecturePlanner, rules.py
    generator/               — LLMGenerator (RAG + NvidiaClient)
    scoring/                 — Evaluator, weighted_score()
    contracts/               — ArchitecturePlan, InfraSpec, DecisionResult
  engine/
    heal.py                  — Healer (uses NvidiaClient directly)
    validate.py              — Validator (hadolint, kubeconform, yamllint, jsonschema)
    policy_engine.py         — PolicyEngine (Python rules + OPA/Rego)
    artifact_manager.py      — write_gate(), quarantine, history, dry_run
    rag.py                   — ChromaDB singleton (optional, guarded by try/except)
    severity.py              — Severity enum, ExitCode, get_exit_code()
  llm_clients/
    nvidia_client.py         ← single LLM client for entire codebase
    mock_client.py           ← test-only mock
  analysis/
    code_analysis_agent.py   — heuristic project detection, .devops_context.json cache
  tools/
    file_ops.py              — _safe_path(), read_file(), write_file(), scan_directory()
    context_gatherer.py      — raw project text dump
  config/
    settings.py              — pydantic-settings, loads configs/resource_profiles.yaml
  utils/
    logger.py                — StructuredFormatter, ContextVar correlation_id
    prompt_loader.py         — PromptRenderer (Jinja2 SandboxedEnvironment, allowlist)
    errors.py                — domain exception hierarchy → ExitCode mapping
    analysis_utils.py        — load_or_run_analysis() with cache
  schemas.py                 — ProjectContext, InfraSpec, ArchitecturePlan,
                               StageResult (all Pydantic v2)
```

## Security Controls

| Control | Implementation |
|---|---|
| Prompt injection | Jinja2 `SandboxedEnvironment`, `ALLOWED_TEMPLATE_VARS` allowlist, per-var size caps |
| Path traversal | `_safe_path()` — null byte check, `os.path.abspath` prefix enforcement |
| Command injection | `_setup_gitops_repo()` uses gitpython + regex URL allowlist (no subprocess) |
| Write gate | `ArtifactManager.write_gate()` — CRITICAL blocked, HIGH quarantined as `.broken` |
| Fail-fast key | `NvidiaClient.__init__()` raises `RuntimeError` immediately if key is empty |
| Policy enforcement | Python rules + OPA/Rego (`policies/k8s/manifests.rego`) |
| Secret generation | Secrets prompts enforce placeholder-only values, never real credentials |

## Extension Points

| What to add | Where |
|---|---|
| New artifact type | `configs/prompts/<stage>/<role>.md` + add stage key to `prompt_map` in `_execute_stage()` |
| New K8s policy | `policies/k8s/manifests.rego` — auto-evaluated by OPA binary |
| New LLM provider | Implement `.call()` interface in `src/llm_clients/`, add to `_init_generators()` |
| New resource profile | Add entry to `configs/resource_profiles.yaml` |
| New stack detection | Add `_detect_<stack>()` in `src/analysis/code_analysis_agent.py` |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All stages succeeded |
| 1 | Critical failure (LLM unavailable, config error) |
| 2 | Policy violation in generated artifact |
| 3 | Integrity failure (path traversal attempt) |
| 130 | Interrupted by SIGTERM (K8s Job preemption) |
