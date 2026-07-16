# Changelog

All notable changes to devops_agent are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

### Security (Critical Fixes)
- **[SEC-01]** Fixed prompt injection sandbox bypass: `LLMGenerator.generate()` now
  filters context to `ALLOWED_TEMPLATE_VARS` before calling `render_prompt()`,
  ensuring Jinja2 `SandboxedEnvironment` is active on 100% of runs
- **[SEC-02]** Fixed command injection in `_setup_gitops_repo()`: replaced
  `subprocess.run(["git", "clone", repo_url, ...])` with gitpython +
  regex URL allowlist (only github.com, gitlab.com, bitbucket.org)
- **[SEC-03]** Fixed silent None API key: `NvidiaClient.__init__()` now raises
  `RuntimeError` immediately with actionable message if key is empty
- **[SEC-04]** Confirmed `.env` excluded from git tracking via `.gitignore`
- **[SEC-05]** Wired OPA/Rego policy evaluation: `PolicyEngine.validate_artifact()`
  now calls `opa eval` against `policies/k8s/manifests.rego` for all YAML artifacts

### Added
- `src/utils/errors.py` — domain exception hierarchy (`ConfigError`, `LLMError`,
  `ValidationError`, `PolicyViolationError`, `PathTraversalError`, `PromptInjectionError`)
- `configs/resource_profiles.yaml` — externalized per-environment resource profiles
  (dev/staging/prod × node-express/python-fastapi/java-spring-boot/react-nginx/default)
- `configs/prompts/k8s/ingress.md` — nginx-ingress + cert-manager TLS generation prompt
- `configs/prompts/k8s/secrets.md` — Vault/SealedSecrets/ExternalSecrets generation prompt
- `--dry-run` flag: renders and validates artifacts, writes to history only, no primary write
- `--health` flag: preflight check for hadolint, kubeconform, opa, NVIDIA API reachability
- `--env` flag now enforces `choices=["dev", "staging", "prod"]`
- SIGTERM handler in `cli_main.py` for clean K8s Job shutdown (exit code 130)
- Audit log written to `audit_logs/<run_id>.json` after every run
- `scripts/` directory with `run_one.py`, `git_commit.py`, `scripts/README.md`
- New Makefile targets: `health`, `dry-run`, `diff`, `type-check`, `coverage`,
  `integration`, `audit`
- New tests: `test_code_analysis_agent.py`, `test_policy_engine.py`,
  `test_nvidia_client.py`, `test_integration_sample_node_app.py`

### Fixed
- `test_v2_modules.py::test_planner` — `framework="fastapi"` → `frameworks=["fastapi"]`
  (was a false-positive due to Pydantic `extra="allow"`)
- `test_rag_concurrency.py` — guarded with `pytest.mark.skipif` when chromadb not installed
- Double Docker build in CI — now uses `docker/build-push-action` with GHA layer cache
  and image artifact reuse between jobs
- Default log level changed from `WARNING` to `INFO`

### Removed
- `src/engine/llm.py` — deleted; `Healer` now uses `NvidiaClient` directly
  (single LLM code path for entire codebase)
- `langchain`, `langchain-core`, `langgraph`, `langsmith` from `pyproject.toml`
  (none were imported; ~60% install size reduction)

### Changed
- `chromadb` is now an optional dependency: `pip install devops-agent[rag]`
- `NvidiaClient` unified: single `.call()` method with `system_prompt`, `temperature`,
  `max_tokens`, `stream` kwargs; used by both `LLMGenerator` and `Healer`
- `_isolate_context()` loads resource profiles from `configs/resource_profiles.yaml`
  keyed by environment, replacing hardcoded dict
- `docs/architecture.md` fully rewritten to reflect CLI-only architecture
- CI workflow: single cached Docker build, Trivy SARIF upload, OPA install, type-check job

## [2.0.0] — CLI-only refactor

### Changed
- Removed server/API mode — CLI-only
- Removed GitOps PR publishing — local writes only
- Removed multi-provider routing — NVIDIA-only
- Added V2 Orchestrator with planner/generator/evaluator/healer pipeline
- Added ArtifactManager with write gate and quarantine
- Added Jinja2 SandboxedEnvironment for prompt rendering
- Added path traversal protection in file_ops.py
