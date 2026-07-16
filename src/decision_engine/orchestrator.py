import copy
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional

from src.schemas import ProjectContext
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.decision_engine.planner.architecture_planner import ArchitecturePlanner
from src.decision_engine.generator.llm_generator import LLMGenerator
from src.decision_engine.scoring.evaluator import Evaluator
from src.utils.prompt_loader import load_prompt
from src.llm_clients.nvidia_client import NvidiaClient
from src.engine.validate import Validator
from src.engine.heal import Healer
from src.engine.models import GeneratedFile
from src.engine.artifact_manager import ArtifactManager
from src.engine.severity import Severity
from src.engine.policy_engine import PolicyEngine, ProjectModel

logger = logging.getLogger("devops-agent")

# Maps stage key → (prompt_dir, prompt_file)
_PROMPT_MAP: dict[str, tuple[str, str]] = {
    "dockerfile":      ("docker", "docker_production"),
    "docker_compose":  ("docker", "docker_compose"),
    "kubernetes":      ("k8s",    "k8s_production"),
    "cicd":            ("cicd",   "cicd_production"),
    "github_actions":  ("cicd",   "github_actions"),
    "gitops_manifests":("k8s",    "argocd"),
    "secrets_doc":     ("docs",   "secrets"),
    "scan":            ("debug",  "healer"),
}

# Stages that produce per-service output vs project-wide
_PER_SERVICE_STAGES = {"dockerfile", "github_actions", "kubernetes"}

# Fallback filenames when LLM doesn't emit FILENAME: blocks
_FALLBACK_FILENAMES: dict[str, str] = {
    "cicd":            ".github/workflows/ci.yml",
    "docker_compose":  "docker-compose.yml",
    "dockerfile":      "Dockerfile",
    "kubernetes":      "k8s/manifests.yaml",
    "gitops_manifests":"applicationset.yaml",
    "secrets_doc":     "docs/secrets.md",
}


class V2Orchestrator:
    def __init__(self, environment: str = "dev"):
        self.planner = ArchitecturePlanner()
        self.evaluator = Evaluator()
        self.validator = Validator()
        self.healer = Healer()
        self.environment = environment
        self._custom_prompt_initialized = False
        self._custom_prompt_text = ""
        self.publisher = None
        self.generators: list[LLMGenerator] = []
        self._init_generators()

    def _init_generators(self) -> None:
        primary = os.environ.get("LLM_PRIMARY", "").lower()
        if primary != "nvidia":
            raise RuntimeError(f"Only NVIDIA provider is supported. Got LLM_PRIMARY={primary!r}")
        try:
            client = NvidiaClient()
            self.generators.append(LLMGenerator(client, "NVIDIA"))
            logger.info("Initialized NVIDIA LLM provider")
        except Exception as e:
            msg = (
                "\n❌ NVIDIA LLM PROVIDER NOT CONFIGURED — ABORTING\n"
                "The pipeline requires a real NVIDIA LLM backend.\n"
                "  export NVIDIA_API_KEY=nvapi-...\n"
            )
            logger.critical(msg)
            raise RuntimeError("NVIDIA LLM provider not available. Configure NVIDIA_API_KEY.") from e

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def run_pipeline(
        self,
        project_path: str,
        context: ProjectContext,
        environment: str = "dev",
        gitops: bool = False,
        gitops_repo: Optional[str] = None,
        target_service: Optional[str] = None,
        publisher=None,
        no_prompts: bool = False,
        no_heal: bool = False,
    ) -> None:
        self.publisher = publisher

        if gitops and gitops_repo:
            self._setup_gitops_repo(project_path, gitops_repo)

        plan = self.planner.create_plan(context)
        print(f"🏗️  Architecture Plan: {plan.service_type.upper()} | Scaling: {plan.scaling_strategy} | DB: {plan.requires_database}")

        self._print_analysis_summary(context)

        is_mono = "microservices" not in context.architecture
        services = context.microservice_dirs or (["."] if is_mono else [])
        if target_service:
            services = [target_service] if target_service in services else []
            print(f"🎯 Target Service Filter: {target_service} (found: {bool(services)})")

        per_service_contexts = {
            svc: self._isolate_context(context, svc, environment)
            for svc in services
        }

        stages = ["dockerfile", "docker_compose", "kubernetes", "github_actions"]
        stages += ["gitops_manifests", "secrets_doc"] if gitops else ["cicd"]

        all_artifacts: dict[str, str] = {}
        for stage in stages:
            if stage in _PER_SERVICE_STAGES:
                for svc in services:
                    files = self._run_stage(
                        stage, project_path, per_service_contexts[svc],
                        plan, environment, svc, no_prompts, no_heal,
                    )
                    all_artifacts.update({f.path: f.content for f in files})
            else:
                if stage == "gitops_manifests":
                    setattr(context, "resource_profiles", {
                        svc: per_service_contexts[svc].resources
                        for svc in services
                        if per_service_contexts[svc].resources
                    })
                files = self._run_stage(
                    stage, project_path, context,
                    plan, environment, None, no_prompts, no_heal,
                )
                all_artifacts.update({f.path: f.content for f in files})

        print("\n🎉 Pipeline Execution Completed Successfully!")
        for name in [".devops_context.json", ".devops_memory.json"]:
            fpath = os.path.join(project_path, name)
            try:
                os.remove(fpath)
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------------ #
    #  Stage runner — thin coordinator                                     #
    # ------------------------------------------------------------------ #

    def _run_stage(
        self,
        stage_key: str,
        project_path: str,
        context: ProjectContext,
        plan: ArchitecturePlan,
        environment: str,
        service_name: Optional[str],
        no_prompts: bool,
        no_heal: bool,
    ) -> list[GeneratedFile]:
        display = f"{stage_key.replace('_', ' ')} ({service_name})" if service_name else stage_key.replace("_", " ")
        print(f"\n--- Stage: {display} ---")

        template = self._build_prompt(stage_key, context, plan, service_name, no_prompts)

        svc = service_name or getattr(context, "project_name", "unknown")
        prompt_context = {
            "context":      context.raw_context_summary,
            "plan_summary": str(plan),
            "svc_name":     svc,
            "service_name": svc,
            "project_name": getattr(context, "project_name", svc),
            "language":     context.language,
            "resources":    str(context.resources) if context.resources else "",
            "service_path": getattr(context, "service_path", ""),
        }

        candidates: list[InfraSpec] = []
        for g in self.generators:
            try:
                candidates.append(g.generate(template, prompt_context, task_type=stage_key))
            except Exception as e:
                logger.error("Generator failed for stage %s: %s", stage_key, e)

        candidates = [c for c in candidates if c.file_content and len(c.file_content.strip()) > 50]
        if not candidates:
            logger.error("Stage %s: all generators returned empty output", display)
            print(f"❌ Stage {display} failed: all generators returned empty output.")
            return []

        self._score_candidates(candidates, stage_key)
        best_spec, best_score = self.evaluator.evaluate_candidates(candidates)
        print(f"🏆 Selected from {best_spec.model_name} (score: {best_score:.1f})")

        policy_engine = PolicyEngine(
            ProjectModel(project_name=context.project_name, services=[], environment=environment)
        )

        return self._validate_and_write(
            best_spec.file_content, stage_key, project_path,
            environment, service_name, policy_engine, no_heal,
        )

    # ------------------------------------------------------------------ #
    #  1. Prompt assembly — pure, no side effects, fully testable          #
    # ------------------------------------------------------------------ #

    def _build_prompt(
        self,
        stage_key: str,
        context: ProjectContext,
        plan: ArchitecturePlan,
        service_name: Optional[str],
        no_prompts: bool,
    ) -> str:
        prompt_dir, prompt_name = _PROMPT_MAP.get(stage_key, (stage_key, "writer_a"))
        try:
            template = load_prompt(prompt_dir, prompt_name)
        except Exception as e:
            logger.warning("Prompt %s/%s not found (%s), falling back", prompt_dir, prompt_name, e)
            if "docker" in stage_key:
                template = load_prompt("docker", "docker_production")
            elif any(k in stage_key for k in ("k8s", "kubernetes", "gitops")):
                template = load_prompt("k8s", "k8s_production")
            elif "ci" in stage_key:
                template = load_prompt("cicd", "cicd_production")
            else:
                raise FileNotFoundError(f"No prompt found for stage: {stage_key!r}") from e

        # --- Stage-specific prompt augmentations ---

        if stage_key == "kubernetes":
            template += (
                "\n\nCRITICAL: Output EACH Kubernetes resource in its OWN SEPARATE file:\n"
                "FILENAME: k8s/filename.yaml\n```yaml\n<content>\n```"
            )
            ci = self._configure_customization(stage_key, no_prompts)
            if ci:
                template += f"\n\nUSER CUSTOM INSTRUCTIONS (MUST FOLLOW):\n{ci}"

        if stage_key == "dockerfile" and context.microservice_dirs:
            dirs = ", ".join(context.microservice_dirs)
            template += (
                f"\n\nCRITICAL: Generate a separate Dockerfile for EACH directory: {dirs}\n"
                "FILENAME: <dir>/Dockerfile\n```dockerfile\n<content>\n```"
            )

        if stage_key == "docker_compose" and context.microservice_dirs:
            svc_lines = "\n".join(
                f"- {d}: ports {context.microservice_details.get(d, {}).get('ports', ['8080'])}, "
                f"databases: {context.microservice_details.get(d, {}).get('databases', [])}"
                for d in context.microservice_dirs
            )
            template += (
                f"\n\nCRITICAL: Generate docker-compose.yml for ALL {len(context.microservice_dirs)} services:\n"
                f"{svc_lines}\nUse FILENAME: docker-compose.yml"
            )

        if stage_key == "kubernetes" and context.microservice_dirs:
            template += (
                f"\n\nCRITICAL: Generate K8s manifests for ALL services: {', '.join(context.microservice_dirs)}.\n"
                "Include Namespace, Service, Deployment, HPA, PodDisruptionBudget, NetworkPolicy.\n"
                "For HPA use apiVersion: autoscaling/v2. DO NOT put 'selector' in HPA spec root.\n"
                "Use FILENAME: k8s/<svc>/<file>.yaml format."
            )

        if stage_key == "kubernetes" and context.resources:
            r = context.resources
            template += (
                f"\n\nCRITICAL: Use these container resources exactly:\n"
                f"requests.cpu: {r.get('cpu_req', '250m')}\n"
                f"requests.memory: {r.get('mem_req', '256Mi')}\n"
                f"limits.cpu: {r.get('cpu_lim', '500m')}\n"
                f"limits.memory: {r.get('mem_lim', '512Mi')}\n"
            )

        if stage_key == "gitops_manifests" and getattr(context, "resource_profiles", None):
            rp_str = json.dumps(context.resource_profiles, indent=2)
            template += (
                f"\n\nCRITICAL: Use this resource_profiles map for exact limits/requests:\n"
                f"```json\n{rp_str}\n```\nDo NOT invent values."
            )

        return template

    # ------------------------------------------------------------------ #
    #  2. Candidate scoring — heuristic, mutates scores in-place           #
    # ------------------------------------------------------------------ #

    def _score_candidates(self, candidates: list[InfraSpec], stage_key: str) -> None:
        for c in candidates:
            content = c.file_content.lower()
            score = 50

            if stage_key == "dockerfile":
                if "from " in content and " as " in content: score += 15
                if any(u in content for u in ["user appuser", "runuser"]):  score += 15
                if "healthcheck" in content:                                 score += 10
                if any(b in content for b in ["npm ci", "pip install", "go build", "mvn package"]): score += 5
                if ":latest" not in content:                                 score += 5
            elif stage_key == "kubernetes":
                if "hpa" in content:                                         score += 10
                if "networkpolicy" in content:                               score += 10
                if "poddisruptionbudget" in content:                         score += 5
                if "requests:" in content and "limits:" in content:          score += 15
                if "livenessprobe" in content and "readinessprobe" in content: score += 10
            elif stage_key in ("cicd", "github_actions"):
                if any(t in content for t in ["trivy", "gitleaks", "sonar"]): score += 20
                if "permissions:" in content:                                score += 10
                if "needs:" in content:                                      score += 5

            if "privileged: true" in content: score -= 30
            if "env_file:" in content:        score -= 10

            c.security_score = min(100, max(0, score))

            bp = 60
            if "as builder" in content:                                      bp += 15
            if "workdir" in content:                                         bp += 10
            if 'cmd ["' in content:                                          bp += 10
            if "label org.opencontainers" in content:                        bp += 5
            c.best_practice_score = min(100, bp)

    # ------------------------------------------------------------------ #
    #  3. Validate + heal + write — testable with mock GeneratedFile list  #
    # ------------------------------------------------------------------ #

    def _validate_and_write(
        self,
        content: str,
        stage_key: str,
        project_path: str,
        environment: str,
        service_name: Optional[str],
        policy_engine: PolicyEngine,
        no_heal: bool,
    ) -> list[GeneratedFile]:
        art_mgr = ArtifactManager(project_path, environment)

        # Parse FILENAME: blocks; fall back to single-file if none found
        pattern = r"FILENAME: (.*?)\n```(?:\w+)?\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        if not matches:
            raw_name = _FALLBACK_FILENAMES.get(stage_key, "generated_file")
            rel_path = self._output_path(raw_name, stage_key, service_name)
            matches = [(rel_path, content)]
            single_file = True
        else:
            single_file = False

        processed: list[GeneratedFile] = []
        for raw_path, file_content in matches:
            rel_path = raw_path.strip() if single_file else self._output_path(raw_path.strip(), stage_key, service_name)

            if len(rel_path) > 255 or "\n" in rel_path:
                logger.warning("Skipping malformed FILENAME token (%d chars)", len(rel_path))
                continue

            gen_file = GeneratedFile(path=rel_path, content=file_content.strip())
            val_res = self.validator.validate(gen_file)

            policy_findings = policy_engine.validate_artifact(rel_path, file_content)
            if policy_findings:
                val_res.passed = False
                val_res.errors.extend([f"POLICY: {msg}" for _, msg in policy_findings])

            if not no_heal and not val_res.passed:
                print(f"  [!] Validation failed for {rel_path} — healing...")
                gen_file = self.healer.heal(gen_file, val_res.errors)
                val_res = self.validator.validate(gen_file)

            sev = Severity.LOW if val_res.passed else Severity.MEDIUM
            art_mgr.write_gate(gen_file.path, gen_file.content, sev)
            processed.append(gen_file)

        if self.publisher and stage_key in ("github_actions", "gitops_manifests") and processed:
            try:
                self.publisher.publish(
                    files={f.path: f.content for f in processed},
                    stage=stage_key,
                    run_id=getattr(self, "run_id", "v2-auto"),
                    reasoning=f"devops-agent automated {stage_key} generation",
                    project_path=project_path,
                )
            except Exception as e:
                logger.error("Publisher failed: %s", e)

        return processed

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _output_path(self, rel_path: str, stage_key: str, service_name: Optional[str]) -> str:
        """Map a raw relative path to the tiered outputs/ layout."""
        import re
        def _sanitize(value: str) -> str:
            return re.sub(r'[^a-zA-Z0-9._\-]', '_', os.path.basename(os.path.normpath(value)))

        safe_rel = _sanitize(rel_path)
        if service_name:
            safe_svc = _sanitize(service_name)
            return os.path.normpath(f"outputs/per-service/{safe_svc}/{safe_rel}")
        if stage_key == "docker_compose":
            return f"outputs/shared/{safe_rel}"
        if stage_key == "gitops_manifests":
            clean = rel_path[7:] if rel_path.startswith("gitops/") else rel_path
            return f"gitops-repo/{_sanitize(clean)}"
        if "doc" in stage_key:
            return f"outputs/docs/{safe_rel}"
        return f"outputs/shared/{safe_rel}"

    def _configure_customization(self, stage_key: str, no_prompts: bool) -> str:
        """Return custom instructions string for K8s stage, or '' in non-interactive mode."""
        if no_prompts:
            self._custom_prompt_initialized = True
            return ""
        if stage_key != "kubernetes":
            return self._custom_prompt_text
        if self._custom_prompt_initialized:
            return self._custom_prompt_text

        ans = input("Would you like to customize Kubernetes manifests? [y/n]: ").strip().lower()
        if ans not in ("y", "yes"):
            self._custom_prompt_initialized = True
            self._custom_prompt_text = ""
            return ""

        print("\nKubernetes customization options:")
        print("  1. Provide a path to a file with instructions")
        print("  2. Answer a short set of questions now")
        choice = input("Choice (1/2): ").strip()

        custom = ""
        if choice == "1":
            filepath = input("Enter file path: ").strip()
            try:
                from src.tools.file_ops import read_file
                custom = read_file(filepath)
            except Exception as e:
                print(f"Failed to read file: {e}")
        else:
            ns     = input("Namespace (default 'default'): ").strip() or "default"
            domain = input("Ingress host/domain (blank = no ingress): ").strip()
            env    = input("Environment label (default 'dev'): ").strip() or "dev"
            lines  = [f"- Use namespace: {ns}", f"- Environment label: {env}"]
            if domain:
                lines.append(f"- Expose HTTP ingress at host: {domain}")
            lines.append("- Use resource limits exactly as provided in resource_profiles where available.")
            custom = "KUBERNETES CUSTOMIZATION:\n" + "\n".join(lines)

        self._custom_prompt_initialized = True
        self._custom_prompt_text = custom.strip()
        return self._custom_prompt_text

    def _isolate_context(self, base_context: ProjectContext, service_name: str, environment: str = "dev") -> ProjectContext:
        """Return a deep-copied context scoped to one service with its resource profile."""
        from src.config.settings import RESOURCE_PROFILES

        ctx = copy.deepcopy(base_context)
        svc_detail = base_context.microservice_details.get(service_name, {})

        ctx.microservice_dirs = [service_name]
        ctx.microservice_details = {service_name: svc_detail}
        ctx.project_name = service_name
        ctx.language = svc_detail.get("language", "unknown")
        ctx.ports = svc_detail.get("ports", ["8080"])
        ctx.frameworks = svc_detail.get("frameworks", [])
        ctx.service_path = svc_detail.get("path", service_name)

        fw_lower  = str(svc_detail.get("frameworks", [])).lower()
        base_img  = str(svc_detail.get("base_image", "")).lower()
        svc_type  = svc_detail.get("language", "unknown").lower()
        if "spring boot" in fw_lower:                          svc_type = "java-spring-boot"
        elif "fastapi" in fw_lower:                            svc_type = "python-fastapi"
        elif "react" in fw_lower or "nginx" in base_img:       svc_type = "react-nginx"
        elif "express" in fw_lower or "nestjs" in fw_lower or "node" in svc_type:
                                                               svc_type = "node-express"

        env_profiles = RESOURCE_PROFILES.get("environments", {})
        ctx.resources = (
            env_profiles.get(environment, {}).get(svc_type)
            or env_profiles.get(environment, {}).get("default")
            or {"cpu_req": "100m", "cpu_lim": "500m", "mem_req": "128Mi", "mem_lim": "512Mi", "replicas": 1}
        )

        truncated = ctx.raw_context_summary[:12000]
        if len(ctx.raw_context_summary) > 12000:
            truncated += "\n...[TRUNCATED]..."
        ctx.raw_context_summary = (
            f"Isolated Context for {service_name}\nResources: {ctx.resources}\n"
            f"Original context follows:\n{truncated}"
        )
        return ctx

    def _print_analysis_summary(self, context: ProjectContext) -> None:
        is_mono = "microservices" not in context.architecture
        dbs = context.databases or {}

        def _norm(d):
            if isinstance(d, list): return {k: [] for k in d}
            if isinstance(d, dict): return d
            return {}

        rdbms  = _norm(dbs.get("rdbms", {}))
        cache  = _norm(dbs.get("cache", {}))
        nosql  = _norm(dbs.get("nosql", {}))
        broker = _norm(dbs.get("broker", {}))
        if not rdbms and "postgres" in context.architecture: rdbms = {"PostgreSQL": []}
        if not cache  and "redis"    in context.architecture: cache = {"Redis": []}

        svc_index = {s: f"#{i+1}" for i, s in enumerate(context.microservice_dirs)}

        def _db_tag(svcs: list) -> str:
            if not svcs: return ""
            return "  ← " + ", ".join(f"{svc_index.get(s, s)} {s}" for s in svcs)

        W = 64
        print("\n" + "=" * W)
        print("  📋  CODE ANALYSIS SUMMARY")
        print("=" * W)
        print(f"  📁  Project       : {context.project_name}")
        print(f"  🏛️   Architecture  : {'Microservices' if not is_mono else 'Monolith'}")
        print(f"  🐳  Dockerfiles   : {len(context.microservice_dirs) if not is_mono else 1} file(s) will be generated")

        all_ports = [
            p for svc in context.microservice_dirs
            for p in context.microservice_details.get(svc, {}).get("ports", [])
        ]
        if all_ports:
            print(f"  🔌  Port chain    : {'  →  '.join(f':{p}' for p in dict.fromkeys(all_ports))}")
        print()

        if not is_mono and context.microservice_dirs:
            print("  ── MICROSERVICES " + "─" * (W - 18))
            for idx, svc in enumerate(context.microservice_dirs, start=1):
                d = context.microservice_details.get(svc, {})
                fw_str = f" · {', '.join(d.get('frameworks', []))}" if d.get("frameworks") else ""
                ports  = d.get("ports", [])
                print(f"  #{idx}  {svc}/  —  {d.get('role', 'Microservice')}")
                print(f"       Language    : {d.get('language', 'Node.js')}{fw_str}")
                print(f"       Base image  : {d.get('base_image', 'node:20-alpine')}")
                print(f"       Port chain  : {'  →  '.join(f':{p}' for p in ports) or 'auto'}")
                if d.get("key_deps"):
                    print(f"       Key deps    : {', '.join(d['key_deps'])}")
                if d.get("databases"):
                    print(f"       Uses DBs    : {', '.join(d['databases'])}")
                print()

        if rdbms or cache or nosql or broker:
            print("  ── DATABASES " + "─" * (W - 14))
            for n, s in rdbms.items():  print(f"  🗄️   RDBMS   {n:<22}{_db_tag(s)}")
            for n, s in cache.items():  print(f"  ⚡  Cache   {n:<22}{_db_tag(s)}")
            for n, s in nosql.items():  print(f"  🍃  NoSQL   {n:<22}{_db_tag(s)}")
            for n, s in broker.items(): print(f"  📨  Broker  {n:<22}{_db_tag(s)}")
            print()

        if context.env_vars:
            shown = context.env_vars[:7]
            print("  ── CONFIGURATION " + "─" * (W - 18))
            print(f"  🔐  Env vars      : {', '.join(shown)}{'...' if len(context.env_vars) > 7 else ''}")
            print()

        print("=" * W + "\n")

    def _setup_gitops_repo(self, project_path: str, repo_url: str) -> None:
        """Initialize GitOps repo structure using gitpython (no shell execution)."""
        from pathlib import Path
        from src.utils.errors import ConfigError

        _SAFE_REPO_RE = re.compile(
            r'^(https://(github\.com|gitlab\.com|bitbucket\.org)'
            r'/[\w.\-]+/[\w.\-]+(\.git)?'
            r'|git@(github\.com|gitlab\.com):[\w.\-]+/[\w.\-]+(\.git)?)$'
        )

        gitops_dir = Path(project_path) / "gitops-repo"

        if repo_url and (repo_url.startswith("http") or repo_url.startswith("git@")):
            if not _SAFE_REPO_RE.match(repo_url):
                raise ConfigError(
                    f"Rejected unsafe repo URL: {repo_url!r}. "
                    "Only github.com, gitlab.com, bitbucket.org HTTPS/SSH URLs allowed."
                )
            try:
                from git import Repo
                if not gitops_dir.exists():
                    logger.info("Cloning GitOps repo: %s", repo_url)
                    Repo.clone_from(repo_url, str(gitops_dir), depth=1)
                else:
                    logger.info("Pulling latest from GitOps repo")
                    Repo(str(gitops_dir)).remotes.origin.pull()
            except ImportError:
                raise ConfigError("gitpython required: pip install gitpython>=3.1.40")
            except Exception as e:
                logger.error("GitOps repo operation failed: %s", e)

        if not gitops_dir.exists():
            (gitops_dir / "argocd").mkdir(parents=True, exist_ok=True)
            (gitops_dir / "namespaces").mkdir(parents=True, exist_ok=True)
            (gitops_dir / "README.md").write_text(
                "# GitOps Repository\nManaged by devops-agent\n\n"
                "## Layout\n- `argocd/`: ApplicationSet manifests\n"
                "- `namespaces/`: Namespace declarations\n"
                "- `apps/<svc>/`: Per-service manifests\n"
            )
        else:
            (gitops_dir / "argocd").mkdir(exist_ok=True)
            (gitops_dir / "namespaces").mkdir(exist_ok=True)
