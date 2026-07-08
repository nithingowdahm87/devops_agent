from __future__ import annotations
import logging
import os
import re
from typing import List, Dict, Any
from dataclasses import dataclass

# Schemas
from src.schemas import ProjectContext, Decision, StageResult
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan
from src.decision_engine.contracts.infra_spec import InfraSpec

# Modules
from src.decision_engine.planner.architecture_planner import ArchitecturePlanner
from src.decision_engine.generator.llm_generator import LLMGenerator
from src.decision_engine.scoring.evaluator import Evaluator

# Engine
from src.engine.validate import Validator
from src.engine.heal import Healer
from src.engine.models import GeneratedFile
from src.engine.idempotency import IdempotencyEngine
from src.engine.artifact_manager import ArtifactManager
from src.engine.severity import Severity
from src.engine.policy_engine import PolicyEngine
from src.memory.long_term_memory import LongTermMemory

# Tools
from src.tools.file_ops import write_file

# Clients
from src.llm_clients.nvidia_client import NvidiaClient

logger = logging.getLogger("devops-agent")


@dataclass
class ArtifactResult:
    """Result of generating and validating an artifact."""
    path: str
    content: str
    passed: bool
    errors: List[str]


class V2Orchestrator:
    """
    Single-path CLI orchestrator for DevOps artifact generation.

    Supported stages: dockerfile, docker_compose, kubernetes, github_actions
    Provider: NVIDIA only
    Output: Local files under outputs/ directory
    """

    # Stages that run per-service
    PER_SERVICE_STAGES = ["dockerfile", "github_actions", "kubernetes"]
    # Stages that run once per project
    PROJECT_STAGES = ["docker_compose"]
    # All stages in order
    STAGES = PER_SERVICE_STAGES + PROJECT_STAGES

    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.planner = ArchitecturePlanner()
        self.evaluator = Evaluator()
        self.validator = Validator()
        self.healer = Healer()
        self.policy_engine = PolicyEngine(None)  # ProjectModel not needed for CLI
        self.memory = None
        self.generators: List[LLMGenerator] = []
        self._init_llm_provider()

    def _init_llm_provider(self):
        """Initialize NVIDIA client only. Fail fast if not configured."""
        primary = os.environ.get("LLM_PRIMARY", "nvidia").lower()
        if primary != "nvidia":
            raise RuntimeError(f"Only NVIDIA provider is supported. Got LLM_PRIMARY={primary}")

        try:
            client = NvidiaClient()
            self.generators.append(LLMGenerator(client, "NVIDIA"))
            logger.info("Initialized NVIDIA LLM provider")
        except Exception as e:
            error_msg = (
                "\n❌ ════════════════════════════════════════════════════════════\n"
                "❌  NVIDIA LLM PROVIDER NOT CONFIGURED — ABORTING        ═\n"
                "═══════════════════════════════════════════════════════════════\n"
                "The pipeline requires a real NVIDIA LLM backend.\n\n"
                "To fix, set:\n"
                "  export NVIDIA_API_KEY=your_key_here\n\n"
                "Current LLM_PRIMARY: " + os.environ.get("LLM_PRIMARY", "(unset)") + "\n"
                "═══════════════════════════════════════════════════════════════\n"
            )
            logger.critical(error_msg)
            print(error_msg)
            raise RuntimeError("NVIDIA LLM provider not available. Configure NVIDIA_API_KEY.")

    def run_pipeline(
        self,
        project_path: str,
        context: ProjectContext,
        target_service: str = None,
        no_heal: bool = False,
    ) -> None:
        """
        Main entry point for V2 Pipeline (CLI auto-pilot mode).
        """
        self.memory = LongTermMemory(project_path)
        logger.info("🚀 Starting V2 Pipeline | env=%s", self.environment)

        # 1. Plan Architecture
        plan = self.planner.create_plan(context)
        print(f"🏗️  Architecture Plan: {plan.service_type.upper()} | Scaling: {plan.scaling_strategy} | DB: {plan.requires_database}")

        # 2. Print analysis summary
        self._print_analysis_summary(context)

        # 3. Discover and isolate per-service contexts
        services = self._get_services_to_process(context, target_service)
        per_service_contexts = {svc: self._isolate_context(context, svc) for svc in services}

        # 4. Run stages sequentially
        all_artifacts: Dict[str, str] = {}
        for stage in self.STAGES:
            try:
                artifacts = self._run_stage(
                    stage, project_path, context, plan, per_service_contexts,
                    target_service, no_heal
                )
                for art in artifacts:
                    all_artifacts[art.path] = art.content
            except Exception as e:
                logger.error("Stage %s failed: %s", stage, e)
                print(f"❌ Stage {stage} failed: {e}")
                raise

        # 5. Global integrity audit
        self._run_integrity_audit(project_path, context, all_artifacts)

        # 6. Generate secrets manifest
        from src.engine.secrets_manifest import SecretsManifest
        SecretsManifest.generate(project_path, all_artifacts)

        print("\n🎉 Pipeline Execution Completed Successfully!")
        self._cleanup_cache_files(project_path)

    def _get_services_to_process(self, context: ProjectContext, target_service: str = None) -> List[str]:
        """Determine which services to process."""
        is_mono = "microservices" not in context.architecture
        services = context.microservice_dirs if not is_mono else ["."]
        if target_service:
            services = [target_service] if target_service in services else []
            print(f"🎯 Target Service Filter: {target_service} (Found: {len(services) > 0})")
        return services

    def _print_analysis_summary(self, context: ProjectContext) -> None:
        """Print rich analysis summary."""
        is_mono = "microservices" not in context.architecture
        num_dockerfiles = len(context.microservice_dirs) if not is_mono else 1

        dbs = context.databases if context.databases else {}

        def _norm(d):
            if isinstance(d, list): return {k: [] for k in d}
            if isinstance(d, dict): return d
            return {}

        rdbms_dict = _norm(dbs.get("rdbms", {}))
        cache_dict = _norm(dbs.get("cache", {}))
        nosql_dict = _norm(dbs.get("nosql", {}))
        broker_dict = _norm(dbs.get("broker", {}))

        if not rdbms_dict and "postgres" in context.architecture:
            rdbms_dict = {"PostgreSQL": []}
        if not cache_dict and "redis" in context.architecture:
            cache_dict = {"Redis": []}

        svc_index = {svc: f"#{i+1}" for i, svc in enumerate(context.microservice_dirs)}

        all_ports = []
        for svc in context.microservice_dirs:
            for p in context.microservice_details.get(svc, {}).get("ports", []):
                if p not in all_ports:
                    all_ports.append(p)

        def _db_tag(svcs: list) -> str:
            if not svcs: return ""
            parts = [f"{svc_index.get(s, s)} {s}" for s in svcs]
            return f"  ← {', '.join(parts)}"

        W = 64
        print("\n" + "=" * W)
        print("  📋  CODE ANALYSIS SUMMARY")
        print("=" * W)
        print(f"  📁  Project       : {context.project_name}")
        print(f"  🏛️   Architecture  : {'Microservices' if not is_mono else 'Monolith'}")
        print(f"  🐳  Dockerfiles   : {num_dockerfiles} file(s) will be generated")
        if all_ports:
            chain = "  →  ".join(f":{p}" for p in all_ports)
            print(f"  🔌  Port chain    : {chain}")
        print()

        if not is_mono and context.microservice_dirs:
            print("  ── MICROSERVICES " + "─" * (W - 18))
            for idx, svc in enumerate(context.microservice_dirs, start=1):
                detail = context.microservice_details.get(svc, {})
                lang = detail.get("language", "Node.js")
                frameworks = detail.get("frameworks", [])
                version = detail.get("runtime_version", "?")
                base_img = detail.get("base_image", "node:20-alpine")
                ports = detail.get("ports", [])
                key_deps = detail.get("key_deps", [])
                role = detail.get("role", "Microservice")
                svc_dbs = detail.get("databases", [])

                fw_str = f" · {', '.join(frameworks)}" if frameworks else ""
                port_chain = "  →  ".join([f":{p}" for p in ports]) if ports else "auto"

                print(f"  #{idx}  {svc}/  —  {role}")
                print(f"       Language    : {lang}{fw_str}")
                print(f"       Runtime     : {lang} {version}")
                print(f"       Base image  : {base_img}")
                print(f"       Port chain  : {port_chain}")
                if key_deps:
                    print(f"       Key deps    : {', '.join(key_deps)}")
                if svc_dbs:
                    print(f"       Uses DBs    : {', '.join(svc_dbs)}")
                print()

        has_db = rdbms_dict or cache_dict or nosql_dict or broker_dict
        if has_db:
            print("  ── DATABASES " + "─" * (W - 14))
            for db_name, svcs in rdbms_dict.items():
                print(f"  🗄️   RDBMS   {db_name:<22}{_db_tag(svcs)}")
            for db_name, svcs in cache_dict.items():
                print(f"  ⚡  Cache   {db_name:<22}{_db_tag(svcs)}")
            for db_name, svcs in nosql_dict.items():
                print(f"  🍃  NoSQL   {db_name:<22}{_db_tag(svcs)}")
            for db_name, svcs in broker_dict.items():
                print(f"  📨  Broker  {db_name:<22}{_db_tag(svcs)}")
            print()

        if context.env_vars:
            print("  ── CONFIGURATION " + "─" * (W - 18))
            shown = context.env_vars[:7]
            print(f"  🔐  Env vars      : {', '.join(shown)}{' ...' if len(context.env_vars) > 7 else ''}")
            print()

        print("=" * W + "\n")

    def _run_stage(
        self,
        stage_key: str,
        project_path: str,
        context: ProjectContext,
        plan: ArchitecturePlan,
        per_service_contexts: Dict[str, ProjectContext],
        target_service: str = None,
        no_heal: bool = False,
    ) -> List[ArtifactResult]:
        """Run a single stage for all applicable services."""
        display_name = stage_key.replace("_", " ").title()
        print(f"\n--- Stage: {display_name} ---")

        # Load prompt template
        template = self._load_stage_prompt(stage_key)

        # Build base prompt context
        base_context = self._build_prompt_context(context, plan)

        # Stage-specific template augmentations
        template = self._augment_template_for_stage(template, stage_key, context)

        results = []

        if stage_key in self.PER_SERVICE_STAGES:
            for svc in per_service_contexts:
                svc_ctx = per_service_contexts[svc]
                prompt_ctx = self._build_prompt_context(svc_ctx, plan, service_name=svc)
                artifacts = self._generate_and_validate(
                    stage_key, project_path, svc, template, prompt_ctx, no_heal
                )
                results.extend(artifacts)
        else:
            # Project-wide stage
            prompt_ctx = self._build_prompt_context(context, plan)
            artifacts = self._generate_and_validate(
                stage_key, project_path, context.project_name, template, prompt_ctx, no_heal
            )
            results.extend(artifacts)

        return results

    def _load_stage_prompt(self, stage_key: str) -> str:
        """Load prompt template for a stage."""
        prompt_map = {
            "dockerfile": ("docker", "docker_production"),
            "kubernetes": ("k8s", "k8s_production"),
            "github_actions": ("cicd", "github_actions"),
            "docker_compose": ("docker", "docker_compose"),
        }
        prompt_dir, prompt_name = prompt_map.get(stage_key, (stage_key, "writer_a"))
        try:
            from src.utils.prompt_loader import load_prompt
            return load_prompt(prompt_dir, prompt_name)
        except Exception as e:
            logger.warning(f"Failed to load prompt {prompt_dir}/{prompt_name}: {e}")
            raise FileNotFoundError(f"Could not find prompt for stage: {stage_key}")

    def _build_prompt_context(
        self,
        context: ProjectContext,
        plan: ArchitecturePlan,
        service_name: str = None
    ) -> Dict[str, Any]:
        """Build prompt context dictionary with safe serialization."""
        svc = service_name or getattr(context, "project_name", "unknown")
        return {
            "context": context.raw_context_summary,
            "plan_summary": str(plan),
            "svc_name": svc,
            "service_name": svc,
            "project_name": getattr(context, "project_name", svc),
            **context.model_dump(),
        }

    def _augment_template_for_stage(self, template: str, stage_key: str, context: ProjectContext) -> str:
        """Add stage-specific instructions to template."""
        if stage_key == "dockerfile" and context.microservice_dirs:
            dirs_str = "\n".join([f"- {d}" for d in context.microservice_dirs])
            template += f"\n\nCRITICAL: Generate a separate Dockerfile for EACH of these {len(context.microservice_dirs)} services:\n{dirs_str}\nUse FILENAME: <dir>/Dockerfile for each."

        if stage_key == "docker_compose" and context.microservice_dirs:
            svc_details = []
            for d in context.microservice_dirs:
                det = context.microservice_details.get(d, {})
                ports = det.get('ports', ['8080'])
                db_req = det.get('databases', [])
                svc_details.append(f"- {d}: ports {ports}, databases: {db_req}")
            svc_str = "\n".join(svc_details)
            template += f"\n\nCRITICAL: Generate docker-compose.yml listing ALL {len(context.microservice_dirs)} services explicitly:\n{svc_str}\nInclude postgres and redis if referenced. Each service MUST have its own block under `services:`. Use FILENAME: docker-compose.yml"

        if stage_key == "kubernetes" and context.microservice_dirs:
            svc_str = ", ".join(context.microservice_dirs)
            template += (
                f"\n\nCRITICAL: Generate K8s manifests for ALL services: {svc_str}.\n"
                "Include Namespace, Service, Deployment, HPA, PodDisruptionBudget, "
                "and NetworkPolicy as separate files.\n"
                "For HPA use apiVersion: autoscaling/v2 with spec.scaleTargetRef.name "
                "matching the Deployment name. DO NOT put 'selector' in spec root of HPA.\n"
                "Use FILENAME: k8s/<svc>/<file>.yaml format."
            )

        if stage_key == "github_actions" and context.microservice_dirs:
            template += (
                "\n\nCRITICAL: Generate GitHub Actions workflow for the project.\n"
                "Include matrix strategy for multi-service builds if applicable.\n"
                "Use FILENAME: .github/workflows/<service>-ci.yml format for per-service workflows."
            )

        if stage_key == "kubernetes" and getattr(context, "resources", None):
            template += (
                f"\n\nCRITICAL: Use these container resources exactly:\n"
                f"requests.cpu: {context.resources.get('cpu_req', '250m')}\n"
                f"requests.memory: {context.resources.get('mem_req', '256Mi')}\n"
                f"limits.cpu: {context.resources.get('cpu_lim', '500m')}\n"
                f"limits.memory: {context.resources.get('mem_lim', '512Mi')}\n"
            )

        return template

    def _generate_and_validate(
        self,
        stage_key: str,
        project_path: str,
        service_name: str,
        template: str,
        prompt_context: Dict[str, Any],
        no_heal: bool,
    ) -> List[ArtifactResult]:
        """Generate candidates, evaluate, validate, heal, and write artifacts."""
        # Generate candidates from all providers (only NVIDIA in practice)
        candidates = []
        for g in self.generators:
            try:
                candidates.append(g.generate(template, prompt_context, task_type=stage_key))
            except Exception as e:
                logger.error(f"Generator failed: {e}")

        # Filter out empty/trivial candidates
        candidates = [c for c in candidates if c.file_content and len(c.file_content.strip()) > 50]

        if not candidates:
            logger.error(f"Stage {stage_key} failed: all LLM providers returned empty output.")
            print(f"❌ Stage {stage_key} failed: all LLM providers returned empty output.")
            return []

        # Score and select best candidate
        best_spec, best_score = self.evaluator.evaluate_candidates(candidates, stage_key=stage_key)
        print(f"🏆 Selected Draft from {best_spec.model_name} (Score: {best_score:.1f})")

        final_content = best_spec.file_content

        # Parse multi-file output
        pattern = r"FILENAME: (.*?)\n```(?:\w+)?\n(.*?)```"
        matches = re.findall(pattern, final_content, re.DOTALL)

        if not matches:
            # Single file fallback
            filename = self._get_default_filename(stage_key, service_name)
            return self._process_single_file(
                stage_key, project_path, filename, final_content, service_name, no_heal
            )

        # Process multiple files
        results = []
        art_mgr = ArtifactManager(project_path, self.environment)

        for rel_path, f_content in matches:
            rel_path = rel_path.strip()
            rel_path = self._normalize_output_path(rel_path, stage_key, service_name)

            # Sanitize path - prevent traversal
            if len(rel_path) > 255 or "\n" in rel_path or ".." in rel_path:
                logger.warning(f"Skipping malformed FILENAME token: {rel_path}")
                continue

            gen_file = GeneratedFile(path=rel_path, content=f_content.strip())
            val_res = self.validator.validate(gen_file)

            # Policy checks
            policy_findings = self.policy_engine.validate_artifact(rel_path, f_content)
            if policy_findings:
                val_res.passed = False
                val_res.errors.extend([f"POLICY: {msg}" for _, msg in policy_findings])

            # Heal if needed
            if not no_heal and not val_res.passed:
                print(f"  [!] Validation failed for {rel_path}. Healing...")
                gen_file = self.healer.heal(gen_file, val_res.errors)
                val_res = self.validator.validate(gen_file)

            # Idempotency
            gen_file.content = IdempotencyEngine.stabilize(gen_file.path, gen_file.content)

            # Write gate
            sev = Severity.MEDIUM if not val_res.passed else Severity.LOW
            art_mgr.write_gate(gen_file.path, gen_file.content, sev)

            results.append(ArtifactResult(
                path=gen_file.path,
                content=gen_file.content,
                passed=val_res.passed,
                errors=val_res.errors
            ))

        # Save to memory
        self.memory.store_decision(
            stage=stage_key,
            content=final_content,
            reason=best_spec.reasoning,
            decision="APPROVED"
        )

        return results

    def _get_default_filename(self, stage_key: str, service_name: str) -> str:
        """Get default filename for stage when no FILENAME blocks found."""
        filename_map = {
            "dockerfile": f"{service_name}/Dockerfile" if service_name != "." else "Dockerfile",
            "docker_compose": "docker-compose.yml",
            "kubernetes": "k8s/manifests.yaml",
            "github_actions": f".github/workflows/{service_name}-ci.yml",
        }
        return filename_map.get(stage_key, "generated_file")

    def _normalize_output_path(self, rel_path: str, stage_key: str, service_name: str) -> str:
        """Normalize output path to standard structure."""
        if service_name and service_name != ".":
            return os.path.normpath(f"outputs/per-service/{service_name}/{rel_path}")
        elif stage_key == "docker_compose":
            return f"outputs/shared/{rel_path}"
        else:
            return f"outputs/shared/{rel_path}"

    def _process_single_file(
        self,
        stage_key: str,
        project_path: str,
        filename: str,
        content: str,
        service_name: str,
        no_heal: bool,
    ) -> List[ArtifactResult]:
        """Process a single-file artifact."""
        rel_path = self._normalize_output_path(filename, stage_key, service_name)

        gen_file = GeneratedFile(path=rel_path, content=content)
        val_res = self.validator.validate(gen_file)

        policy_findings = self.policy_engine.validate_artifact(rel_path, content)
        if policy_findings:
            val_res.passed = False
            val_res.errors.extend([f"POLICY: {msg}" for _, msg in policy_findings])

        if not no_heal and not val_res.passed:
            gen_file = self.healer.heal(gen_file, val_res.errors)

        gen_file.content = IdempotencyEngine.stabilize(gen_file.path, gen_file.content)

        art_mgr = ArtifactManager(project_path, self.environment)
        sev = Severity.MEDIUM if not val_res.passed else Severity.LOW
        art_mgr.write_gate(gen_file.path, gen_file.content, sev)

        return [ArtifactResult(
            path=gen_file.path,
            content=gen_file.content,
            passed=val_res.passed,
            errors=val_res.errors
        )]

    def _run_integrity_audit(
        self,
        project_path: str,
        context: ProjectContext,
        all_artifacts: Dict[str, str],
    ) -> None:
        """Run global integrity audit on all generated artifacts."""
        print("\n--- Stage 5: Global Integrity Audit ---")
        from src.engine.integrity import IntegrityAuditor
        from src.engine.graph import ArchitectureGraph

        graph = ArchitectureGraph()
        for svc_dir in context.microservice_dirs:
            p = context.microservice_details.get(svc_dir, {}).get("ports", ["8080"])[0]
            graph.add_node(svc_dir, p)

        auditor = IntegrityAuditor(graph)
        for path, content in all_artifacts.items():
            auditor.add_artifact(path, content)

        findings = auditor.run_audit()
        if findings:
            print("🔍 Audit Findings:")
            for sev, msg in findings:
                print(f"  [{sev.name}] {msg}")
        else:
            print("✅ Integrity Audit Passed.")

    def _cleanup_cache_files(self, project_path: str) -> None:
        """Clean up cache files on successful completion."""
        import os
        for f in [".devops_context.json", ".devops_memory.json"]:
            fpath = os.path.join(project_path, f)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    def _isolate_context(self, base_context: ProjectContext, service_name: str) -> ProjectContext:
        """Create a service-specific context with dedicated resource profiles."""
        import copy
        ctx = copy.deepcopy(base_context)

        svc_detail = base_context.microservice_details.get(service_name, {})

        # Isolate to single service
        ctx.microservice_dirs = [service_name]
        ctx.microservice_details = {service_name: svc_detail}

        svc_type = svc_detail.get("language", "unknown").lower()
        fw_lower = str(svc_detail.get("frameworks", [])).lower()
        base_img = str(svc_detail.get("base_image", "")).lower()

        if "spring boot" in fw_lower:
            svc_type = "java-spring-boot"
        elif "fastapi" in fw_lower:
            svc_type = "python-fastapi"
        elif "react" in fw_lower or "nginx" in base_img:
            svc_type = "react-nginx"
        elif "express" in fw_lower or "nestjs" in fw_lower or "node" in svc_type:
            svc_type = "node-express"

        RESOURCE_PROFILES = {
            'java-spring-boot': {'cpu_req': '250m', 'cpu_lim': '500m', 'mem_req': '512Mi', 'mem_lim': '1Gi'},
            'python-fastapi':   {'cpu_req': '100m', 'cpu_lim': '300m', 'mem_req': '256Mi', 'mem_lim': '512Mi'},
            'react-nginx':      {'cpu_req': '50m',  'cpu_lim': '250m', 'mem_req': '128Mi', 'mem_lim': '512Mi'},
            'node-express':     {'cpu_req': '100m', 'cpu_lim': '300m', 'mem_req': '256Mi', 'mem_lim': '512Mi'},
            'default':          {'cpu_req': '100m', 'cpu_lim': '200m', 'mem_req': '128Mi', 'mem_lim': '256Mi'},
        }

        profile = RESOURCE_PROFILES.get(svc_type, RESOURCE_PROFILES['default'])

        ctx.project_name = service_name
        ctx.language = svc_detail.get("language", "unknown")
        ctx.ports = svc_detail.get("ports", ["8080"])
        ctx.frameworks = svc_detail.get("frameworks", [])
        ctx.service_path = svc_detail.get("path", service_name)
        ctx.resources = profile

        # Truncate context to prevent overflow
        truncated = ctx.raw_context_summary[:12000]
        if len(ctx.raw_context_summary) > 12000:
            truncated += "\n...[TRUNCATED TO PREVENT CONTEXT OVERFLOW]..."

        ctx.raw_context_summary = f"Isolated Context for {service_name}\nResources: {profile}\nOriginal context follows:\n{truncated}"

        return ctx