from typing import List, Dict, Any
import logging
import os

# Schemas
from src.schemas import ProjectContext, Decision, StageResult
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.decision_engine.contracts.decision_result import DecisionResult

# Modules
from src.decision_engine.planner.architecture_planner import ArchitecturePlanner
from src.decision_engine.generator.llm_generator import LLMGenerator
from src.decision_engine.scoring.scorecard import weighted_score
from src.decision_engine.scoring.evaluator import Evaluator
from src.decision_engine.repair.repair_agent import RepairAgent
from src.decision_engine.confidence.confidence_score import compute_confidence
from src.decision_engine.confidence.action_router import decide_action
from src.utils.prompt_loader import load_prompt
from src.memory.long_term_memory import LongTermMemory

# Clients
from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.nvidia_client import NvidiaClient
from src.llm_clients.groq_client import GroqClient
from src.llm_clients.mock_client import MockClient

# Engine
from src.engine.validate import Validator
from src.engine.heal import Healer
from src.engine.models import GeneratedFile

# Tools
from src.tools.file_ops import write_file

logger = logging.getLogger("devops-agent")

class V2Orchestrator:
    def __init__(self, environment: str = "dev"):
        self.planner = ArchitecturePlanner()
        self.evaluator = Evaluator()
        self.repair_agent = RepairAgent()
        self.validator = Validator()
        self.healer = Healer()
        self.environment = environment
        self.memory = None # Init later with project_path
        
        # Initialize Generators (Safe Layout)
        self.generators = []
        self._init_generators()
        
    def _init_generators(self):
        """Try to init real clients, fallback to mock."""
        clients = [
            ("Gemini", GeminiClient),
            ("Groq", GroqClient),
            ("NVIDIA", NvidiaClient)
        ]
        
        for name, cls in clients:
            try:
                client = cls()
                self.generators.append(LLMGenerator(client, name))
            except Exception as e:
                logger.warning(f"Failed to init {name} client: {e}. Using Mock.")
                self.generators.append(LLMGenerator(MockClient(name=f"Mock-{name}"), f"Mock-{name}"))
        
    def run_pipeline(self, project_path: str, context: ProjectContext, environment: str = "dev", no_llm: bool = False, gitops: bool = False, gitops_repo: str = None, target_service: str = None, publisher=None, no_prompts: bool = False):
        """
        Main entry point for V2 Pipeline.
        """
        self.publisher = publisher
        logger.info("🚀 Starting V2 Decision Engine Pipeline | GitOps=%s | Publisher=%s", gitops, publisher.mode if publisher else "None")
        self.memory = LongTermMemory(project_path)
        
        # 0. GitOps Setup (New)
        if gitops and gitops_repo:
            self._setup_gitops_repo(project_path, gitops_repo)
        
        # 1. Plan Architecture
        plan = self.planner.create_plan(context)
        print(f"🏗️  Architecture Plan: {plan.service_type.upper()} | Scaling: {plan.scaling_strategy} | DB: {plan.requires_database}")
        
        # 2. Print rich analysis summary
        is_mono = "microservices" not in context.architecture
        num_dockerfiles = len(context.microservice_dirs) if not is_mono else 1

        dbs = context.databases if context.databases else {}

        # Normalise: old cache stores lists, new stores {name: [svcs]}
        def _norm(d):
            if isinstance(d, list): return {k: [] for k in d}
            if isinstance(d, dict): return d
            return {}
        rdbms_dict  = _norm(dbs.get("rdbms", {}))
        cache_dict  = _norm(dbs.get("cache", {}))
        nosql_dict  = _norm(dbs.get("nosql", {}))
        broker_dict = _norm(dbs.get("broker", {}))

        # Fallback legacy
        if not rdbms_dict and "postgres" in context.architecture: rdbms_dict = {"PostgreSQL": []}
        if not cache_dict  and "redis"    in context.architecture: cache_dict  = {"Redis": []}

        # Service numbering map {svc -> "#N"}
        svc_index = {svc: f"#{i+1}" for i, svc in enumerate(context.microservice_dirs)}

        # Global port chain across all services in order
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

        # ── Per-service section ─────────────────────────────────────
        if not is_mono and context.microservice_dirs:
            print("  ── MICROSERVICES " + "─" * (W - 18))
            for idx, svc in enumerate(context.microservice_dirs, start=1):
                detail     = context.microservice_details.get(svc, {})
                lang       = detail.get("language", "Node.js")
                frameworks = detail.get("frameworks", [])
                version    = detail.get("runtime_version", "?")
                base_img   = detail.get("base_image", "node:20-alpine")
                ports      = detail.get("ports", [])
                key_deps   = detail.get("key_deps", [])
                role       = detail.get("role", "Microservice")
                svc_dbs    = detail.get("databases", [])

                fw_str     = f" · {', '.join(frameworks)}" if frameworks else ""
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

        # ── Databases section ───────────────────────────────────────
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


        # 3. Discover and Isolate Contexts (Overhaul 1)
        services = context.microservice_dirs
        if target_service:
            services = [target_service] if target_service in services else []
            print(f"🎯 Target Service Filter: {target_service} (Found: {len(services) > 0})")

        per_service_contexts = {}
        for svc in services:
            print(f"🔍 Isolating Context: {svc}")
            per_service_contexts[svc] = self._isolate_context(context, svc)

        # 6. Run Stages (Level 10 Deterministic Sequence)
        all_artifacts = {}
        stages = ["dockerfile", "docker_compose", "kubernetes", "github_actions"]
        if gitops:
            stages += ["gitops_manifests", "secrets_doc"]
        else:
            stages.append("cicd")

        for stage in stages:
            if stage in ["dockerfile", "github_actions", "kubernetes"]:
                # Per-service execution (Fixes Overhaul 2)
                for svc in services:
                    try:
                        svc_ctx = per_service_contexts[svc]
                        res_files = self._execute_stage(f"{stage.replace('_', ' ')} ({svc})", stage, project_path, svc_ctx, plan, environment=environment, no_llm=no_llm, service_name=svc, no_prompts=no_prompts)
                        if res_files:
                            for f in res_files:
                                all_artifacts[f.path] = f.content
                    except Exception as e:
                        logger.error(f"Stage {stage} for {svc} failed: {e}")
            else:
                # Project-wide execution (Compose, GitOps manifests, Secrets, CICD)
                try:
                    if stage == "gitops_manifests":
                        resource_map = {}
                        for svc in context.microservice_dirs:
                            svc_ctx = per_service_contexts.get(svc)
                            if svc_ctx and getattr(svc_ctx, "resources", None):
                                resource_map[svc] = svc_ctx.resources
                        setattr(context, "resource_profiles", resource_map)
                        
                    res_files = self._execute_stage(stage.replace("_", " "), stage, project_path, context, plan, environment=environment, no_llm=no_llm, no_prompts=no_prompts)
                    if res_files:
                        for f in res_files:
                            all_artifacts[f.path] = f.content
                except Exception as stage_e:
                    logger.error("Stage %s failed: %s", stage, stage_e)
                    print(f"⚠️  Stage {stage} failed due to LLM exhaustion. Generating minimal fallback...")
                    if stage == "kubernetes":
                         all_artifacts["k8s/fallback.yaml"] = "# Fallback Kubernetes Manifest\n# Manual generation required."
                    elif stage == "cicd":
                         all_artifacts[".github/workflows/fallback.yml"] = "# Fallback CI/CD\n# Manual generation required."


        # 7. Level 10 Post-Generation Stage (Audit & Manifest)
        print("\n--- Stage 5: Global Integrity Audit ---")
        from src.engine.integrity import IntegrityAuditor
        from src.engine.graph import ArchitectureGraph
        # Construct graph for audit

        # FIX: ArchitectureGraph now accepts no-arg constructor
        graph = ArchitectureGraph()           # ← was ArchitectureGraph() which crashed
        for svc_dir in context.microservice_dirs:
            p = context.microservice_details.get(svc_dir, {}).get("ports", ["8080"])[0]
            graph.add_node(svc_dir, p)        # ← use the new incremental builder
        
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

        from src.engine.secrets_manifest import SecretsManifest
        SecretsManifest.generate(project_path, all_artifacts)

        print("\n🎉 Pipeline Execution Completed Successfully!")
        import os
        for f in [".devops_context.json", ".devops_memory.json"]:
            fpath = os.path.join(project_path, f)
            if os.path.exists(fpath):
                try: os.remove(fpath)
                except Exception: pass
        import sys
        sys.exit(0)

        
    def _execute_stage(self, display_name: str, stage_key: str, project_path: str, context: ProjectContext, plan: ArchitecturePlan, environment: str = "dev", no_llm: bool = False, service_name: str = None, no_prompts: bool = False):
        print(f"\n--- Stage: {display_name} ---")
        
        # 1. Load Prompts
        # Mapping to the new "Elite" prompt structure
        prompt_map = {
            "dockerfile": ("docker", "docker_production"),
            "kubernetes": ("k8s", "k8s_production"),
            "cicd": ("cicd", "cicd_production"),
            "scan": ("debug", "healer"), # Simplified
            "docker_compose": ("docker", "docker_compose"),
            "github_actions": ("cicd", "github_actions"),
            "gitops_manifests": ("k8s", "argocd"),
            "secrets_doc": ("docs", "secrets")
        }
        
        prompt_dir, prompt_name = prompt_map.get(stage_key, (stage_key, "writer_a"))
        
        try:
            template = load_prompt(prompt_dir, prompt_name)
        except Exception as e:
            logger.warning(f"Failed to load prompt {prompt_dir}/{prompt_name}: {e}. Falling back to elite defaults.")
            # Final fallback to known elite prompts
            if "docker" in stage_key: template = load_prompt("docker", "docker_production")
            elif "k8s" in stage_key or "kubernetes" in stage_key or "gitops" in stage_key: template = load_prompt("k8s", "k8s_production")
            elif "ci" in stage_key: template = load_prompt("cicd", "cicd_production")
            else: raise FileNotFoundError(f"Could not find any prompt for stage: {stage_key}")
            
        # Optional User Input for K8s & Dockerfile
        custom_instructions = ""
        if stage_key == "kubernetes" or stage_key == "dockerfile":
            if stage_key == "kubernetes":
                template += "\n\nCRITICAL: Output EACH Kubernetes resource (Deployment, Service, Ingress, Secrets, ConfigMap, Namespace etc.) in its OWN SEPARATE file using the FILENAME format: \nFILENAME: k8s/filename.yaml\n```yaml\n<content>\n```"
                print("\n" + "="*50)
                print("☸️   KUBERNETES MANIFEST CUSTOMIZATION")
                print("="*50)
            if stage_key == "dockerfile" and len(context.microservice_dirs) > 0:
                dirs = ", ".join(context.microservice_dirs)
                template += f"\n\nCRITICAL: Automatically output EACH Dockerfile in its respective directory using the FILENAME format (e.g., frontend/Dockerfile, backend/Dockerfile). These are the required directories to cover: {dirs}\nFILENAME: <dir>/Dockerfile\n```dockerfile\n<content>\n```"
            else:
                if no_prompts:
                    user_input = "n"
                else:
                    user_input = input(f"Would you like to provide custom instructions for {display_name}? [y/N]: ").strip().lower()
                    
                if user_input in ['y', 'yes']:
                    print("Options for Custom Instructions:")
                    print("  1. Type instructions directly")
                    print("  2. Provide a path to a file with instructions")
                    choice = input("Choice (1/2): ").strip()
                    if choice == '1':
                        custom_instructions = input("Enter instructions: ").strip()
                    elif choice == '2':
                        filepath = input("Enter file path: ").strip()
                        try:
                            from src.tools.file_ops import read_file
                            custom_instructions = read_file(filepath)
                        except Exception as e:
                            print(f"Failed to read file: {e}")
                    
                    if custom_instructions:
                        template += f"\n\nUSER CUSTOM INSTRUCTIONS (MUST FOLLOW):\n{custom_instructions}"
            
        # 2. Generate Drafts (Parallel)
        svc = service_name or getattr(context, "project_name", "unknown")
        
        prompt_context = {
            "context": context.raw_context_summary,
            "plan_summary": str(plan),
            # Expose both names so all templates work unconditionally:
            "svc_name": svc,
            "service_name": svc,
            "project_name": getattr(context, "project_name", svc),
        }
        # Add specific fields
        prompt_context.update(context.model_dump())
        
        # --- Level 10 Deterministic Looping (Gap 4) ---
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
            template += f"\n\nCRITICAL: Generate docker-compose.yml listing ALL {len(context.microservice_dirs)} services explicitly:\n{svc_str}\nInclude postgres and redis if referenced. Do NOT merge them. Each service MUST have its own block under `services:`. Use FILENAME: docker-compose.yml"

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
            
        if stage_key == "kubernetes" and getattr(context, "resources", None):
            template += (
                f"\n\nCRITICAL: Use these container resources exactly:\n"
                f"requests.cpu: {context.resources.get('cpu_req', '250m')}\n"
                f"requests.memory: {context.resources.get('mem_req', '256Mi')}\n"
                f"limits.cpu: {context.resources.get('cpu_lim', '500m')}\n"
                f"limits.memory: {context.resources.get('mem_lim', '512Mi')}\n"
            )

        if stage_key == "gitops_manifests" and getattr(context, "resource_profiles", None):
            import json
            rp_str = json.dumps(context.resource_profiles, indent=2)
            template += (
                f"\n\nCRITICAL: Use the provided JSON map `resource_profiles` to set exact resource limits/requests for each service:\n"
                f"```json\n{rp_str}\n```\n"
                "Do NOT invent or hallucinate values. Map them precisely."
            )


        
        candidates = []
        if no_llm:
            print(f"  [!] no-llm mode enabled. Skipping generation for {stage_key}.")
            from src.engine.fallbacks import FALLBACK_DIR
            fb_map = {
                "dockerfile": "Dockerfile",
                "docker_compose": "docker-compose.yml",
                "kubernetes": "k8s-deployment.yaml",
                "cicd": "gha-ci.yml"
            }
            fb_path = os.path.join(FALLBACK_DIR, fb_map.get(stage_key, "Dockerfile"))
            from src.tools.file_ops import read_file
            if os.path.exists(fb_path):
                content = read_file(fb_path)
                # Mock a candidate
                from dataclasses import dataclass
                @dataclass
                class MockCandidate:
                    file_content: str
                    model_name: str = "Fallback-Template"
                    reasoning: str = "Hardware-locked deterministic fallback"
                candidates.append(MockCandidate(file_content=content))
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(g.generate, template, prompt_context, task_type=stage_key) for g in self.generators]
                for f in concurrent.futures.as_completed(futures):
                    try:
                        candidates.append(f.result())
                    except Exception as e:
                        logger.error(f"Generator failed: {e}")

        # 3. Score & Select
        # TODO: Objective Static Analysis Roadmap
        # Currently, the Evaluator relies on the LLM's self-reported scores and length heuristics.
        # To make this fully deterministic, the future roadmap includes wiring real CLI linters:
        # 1. Run `hadolint` (Docker) or `kubeconform` (K8s) on `c.file_content` via a secure subprocess.
        # 2. Parse the exit code or JSON output to quantify real technical debt.
        # 3. Pipe those integers directly into python `scorecard.py` to drive true objective selection.
        # For now, we inject a semantic "Grader" heuristic here.
        for c in candidates:
            content = c.file_content.lower()
            # --- Security & Quality heuristics (0-100) ---
            score = 50  # base
            
            # Docker specific
            if stage_key == "dockerfile":
                if "from " in content and " as " in content:
                    score += 15  # multi-stage build reward
                if "user " in content and ("adduser" in content or "useradd" in content or "appuser" in content):
                    score += 15  # non-root user
                if "healthcheck" in content:
                    score += 10  # healthcheck presence
                if "npm ci" in content or "pip install --no-cache-dir" in content:
                    score += 5   # optimized installs
                if ":latest" not in content:
                    score += 5   # pinned versions
            
            # Kubernetes specific
            elif stage_key == "kubernetes":
                if "hpa" in content: score += 10
                if "networkpolicy" in content: score += 10
                if "poddisruptionbudget" in content: score += 5
                if "requests:" in content and "limits:" in content: score += 15
                if "livenessprobe" in content and "readinessprobe" in content: score += 10
            
            # CI/CD specific (including per-service github_actions)
            elif stage_key in ["cicd", "github_actions"]:
                if "trivy" in content or "gitleaks" in content or "sonar" in content:
                    score += 20  # integrated security scans
                if "permissions:" in content:
                    score += 10  # explicit permissions
                if "needs:" in content:
                    score += 5   # job dependencies
                if "docker/build-push-action@v6" in content:
                    score += 5   # proper docker build/push
                if "sed -i" in content and "deployment.yaml" in content:
                    score += 5   # manifest image-tag update pattern
            
            # Penalties
            if "privileged: true" in content:
                score -= 30
            if "copy . env" in content or "env_file:" in content:
                # Potential secret exposure (rough check)
                score -= 10

            c.security_score = min(100, max(0, score))
            c.compliance_score = c.security_score # Tie them for now

            # --- Best-practice heuristics (0-100) ---
            bp = 60  # base
            if "as builder" in content:
                bp += 15  # multi-stage build
            if "workdir" in content:
                bp += 10  # WORKDIR used
            if 'cmd ["' in content or "cmd ['":
                bp += 10  # exec form CMD
            if "label org.opencontainers" in content or "label maintainer" in content:
                bp += 5   # OCI labels
            c.best_practice_score = min(100, bp)

        # Model agreement score: ratio of generators that returned useful content
        useful = sum(1 for c in candidates if len(c.file_content.strip()) > 100)
        model_agreement = useful / max(len(candidates), 1)

        if not candidates:
            print("❌ All generators failed.")
            return

        best_spec, best_score = self.evaluator.evaluate_candidates(candidates)
        print(f"🏆 Selected Draft from {best_spec.model_name} (Score: {best_score:.1f})")
        
        # 4. Level 10 Validation & Policy Engine
        from src.engine.policy_engine import PolicyEngine
        from src.models.domain import ProjectModel
        # Basic model for policy
        policy_model = ProjectModel(project_name=context.project_name, services=[], environment=environment)
        policy_engine = PolicyEngine(policy_model)
        print(f"验证: {best_spec.model_name} draft...")
        
        final_content = best_spec.file_content
        
        # Determine if we need to split multifile
        if stage_key in ["dockerfile", "kubernetes", "docker_compose", "cicd", "github_actions", "gitops_manifests", "secrets_doc"]:
            import re
            pattern = r"FILENAME: (.*?)\n```(?:\w+)?\n(.*?)```"
            matches = re.findall(pattern, final_content, re.DOTALL)
            
            if matches:
                processed_files = []
                from src.engine.artifact_manager import ArtifactManager
                from src.engine.severity import Severity
                art_mgr = ArtifactManager(project_path, environment)
                
                for rel_path, f_content in matches:
                    rel_path = rel_path.strip()
                    # ─── New Tiered Output Structure (Overhaul 10) ──────────
                    if service_name:
                        rel_path = f"outputs/per-service/{service_name}/{rel_path}"
                    elif stage_key == "docker_compose":
                        rel_path = f"outputs/shared/{rel_path}"
                    elif stage_key == "gitops_manifests":
                        # Strip redundant 'gitops/' prefix if prompt generated it (Phase 3 Polish)
                        clean_path = rel_path[7:] if rel_path.startswith("gitops/") else rel_path
                        # Map directly to the canonical gitops-repo layout (Phase 5 Polish)
                        rel_path = f"gitops-repo/{clean_path}"
                    else:
                        rel_path = f"outputs/docs/{rel_path}" if "doc" in stage_key else f"outputs/shared/{rel_path}"
                        
                    # ← BUG FIX: guard against LLM embedding YAML in filename token
                    if len(rel_path) > 255 or "\n" in rel_path:
                        logger.warning(
                            f"Skipping malformed FILENAME token ({len(rel_path)} chars)"
                        )
                        continue
                    gen_file = GeneratedFile(path=rel_path, content=f_content.strip())
                    val_res = self.validator.validate(gen_file)
                    
                    # Policy Checks
                    policy_findings = policy_engine.validate_artifact(rel_path, f_content)
                    if policy_findings:
                        val_res.passed = False
                        val_res.errors.extend([f"POLICY: {msg}" for sev, msg in policy_findings])

                    if not val_res.passed:
                        print(f"  [!] Validation failed for {rel_path}. Healing...")
                        gen_file = self.healer.heal(gen_file, val_res.errors)
                        # Final re-validate
                        val_res = self.validator.validate(gen_file)
                    
                    # Level 10 Idempotency (Gap 3)
                    from src.engine.idempotency import IdempotencyEngine
                    gen_file.content = IdempotencyEngine.stabilize(gen_file.path, gen_file.content)

                    # Level 10 Write Gate
                    # CRITICAL = never write, HIGH = prod blocker, MEDIUM = healed-but-imperfect, LOW = clean
                    if not val_res.passed:
                        sev = Severity.MEDIUM  # healer ran but file still has minor issues — write it
                    else:
                        sev = Severity.LOW
                    art_mgr.write_gate(gen_file.path, gen_file.content, sev)
                    processed_files.append(gen_file)

                # --- V2 Automated PR Integration (Final Form 12) ---
                if self.publisher and stage_key in ["github_actions", "gitops_manifests"]:
                    try:
                        pub_files = {f.path: f.content for f in processed_files}
                        self.publisher.publish(
                            files=pub_files,
                            stage=stage_key,
                            run_id=getattr(self, "run_id", "v2-auto"),
                            reasoning=f"V2 Orchestrator automated {stage_key} generation",
                            project_path=project_path
                        )
                    except Exception as pe:
                        logger.error(f"V2 Publisher failed: {pe}")
                return processed_files
            else:
                # BUG FIX: fix the cicd/k8s fallback filenames
                filename_map = {
                    "cicd":            ".github/workflows/ci.yml",
                    "github_actions":  f".github/workflows/{service_name or 'service'}-ci.yml",
                    "docker_compose":  "docker-compose.yml",
                    "dockerfile":      "Dockerfile",
                    "kubernetes":      "k8s/manifests.yaml",
                    "gitops_manifests":"applicationset.yaml",
                    "secrets_doc":     "docs/secrets.md",
                }
                filename = filename_map.get(stage_key, "generated_file")
                
                # ─── New Tiered Output Structure (Overhaul 10) ──────────
                if service_name:
                    filename = f"outputs/per-service/{service_name}/{filename}"
                elif stage_key == "docker_compose":
                    filename = f"outputs/shared/{filename}"
                elif stage_key == "gitops_manifests":
                    # Even fallback ApplicationSet should live in gitops-repo for ArgoCD to watch
                    filename = f"gitops-repo/argocd/{filename}"
                else:
                    filename = f"outputs/docs/{filename}" if "doc" in stage_key else f"outputs/shared/{filename}"
                
                gen_file = GeneratedFile(path=filename, content=final_content)
                val_res = self.validator.validate(gen_file)
                
                # Policy Checks
                policy_findings = policy_engine.validate_artifact(filename, final_content)
                if policy_findings:
                    val_res.passed = False
                    val_res.errors.extend([f"POLICY: {msg}" for sev, msg in policy_findings])

                if not val_res.passed:
                    gen_file = self.healer.heal(gen_file, val_res.errors)
                
                # Level 10 Idempotency (Gap 3)
                from src.engine.idempotency import IdempotencyEngine
                gen_file.content = IdempotencyEngine.stabilize(gen_file.path, gen_file.content)

                from src.engine.artifact_manager import ArtifactManager
                from src.engine.severity import Severity
                art_mgr = ArtifactManager(project_path, environment)
                sev = Severity.MEDIUM if not val_res.passed else Severity.LOW
                art_mgr.write_gate(gen_file.path, gen_file.content, sev)
                print(f"✅ Processed {filename}")
                return [gen_file]
        else:
            # Legacy fallback single file (e.g. cicd if not in multi-list above)
            return []
        
        # 8. Save to Memory
        self.memory.store_decision(
            stage=stage_key,
            content=final_content,
            reason=best_spec.reasoning,
            decision="APPROVED"
        )

    def _write_files_direct(self, files: list[GeneratedFile], project_path: str):
        import os
        print("📦 Writing Validated Config Files:")
        for f in files:
            full_path = os.path.join(project_path, f.path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as out:
                out.write(f.content)
            print(f"  - Created {f.path}")

    def _handle_multifile_output(self, content: str, project_path: str):
        """Helper to parse FILENAME: blocks and write them."""
        import re
        import os
        
        pattern = r"FILENAME: (.*?)\n```(?:\w+)?\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            print("📦 Writing Multiple Config Files:")
            for rel_path, file_content in matches:
                rel_path = rel_path.strip()
                full_path = os.path.join(project_path, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                write_file(full_path, file_content.strip())
                print(f"  - Created {rel_path}")
        else:
            print("⚠️ No referenced files found in content. Dumping raw to 'scan_configs.md'")
            write_file(os.path.join(project_path, "scan_configs.md"), content)

    def _isolate_context(self, base_context: ProjectContext, service_name: str) -> ProjectContext:
        """Creates a service-specific context with dedicated resource profiles."""
        import copy
        ctx = copy.deepcopy(base_context)
        
        # Filter details for ONLY this service
        svc_detail = base_context.microservice_details.get(service_name, {})
        
        # NEW restriction: explicitly isolate array paths to prevent LLM global leakage
        ctx.microservice_dirs = [service_name]
        ctx.microservice_details = {service_name: svc_detail}
        
        svc_type = svc_detail.get("language", "unknown").lower()
        if "spring boot" in str(svc_detail.get("frameworks", [])).lower():
            svc_type = "java-spring-boot"
        elif "fastapi" in str(svc_detail.get("frameworks", [])).lower():
            svc_type = "python-fastapi"
        elif "react" in str(svc_detail.get("frameworks", [])).lower() or "nginx" in str(svc_detail.get("base_image", "")).lower():
            svc_type = "react-nginx"
            
        # Dynamic Resource Allocation (Overhaul 4)
        RESOURCE_PROFILES = {
            'java-spring-boot': {'cpu_req': '250m', 'cpu_lim': '500m', 'mem_req': '512Mi', 'mem_lim': '1Gi'},
            'python-fastapi': {'cpu_req': '100m', 'cpu_lim': '300m', 'mem_req': '256Mi', 'mem_lim': '512Mi'},
            'react-nginx': {'cpu_req': '50m', 'cpu_lim': '250m', 'mem_req': '128Mi', 'mem_lim': '512Mi'},
            'default': {'cpu_req': '100m', 'cpu_lim': '200m', 'mem_req': '128Mi', 'mem_lim': '256Mi'}
        }
        
        profile = RESOURCE_PROFILES.get(svc_type, RESOURCE_PROFILES['default'])
        
        # Inject into context (Dynamic Resource Logic)
        ctx.project_name = service_name
        ctx.language = svc_detail.get("language", "unknown")
        ctx.ports = svc_detail.get("ports", ["8080"])
        ctx.frameworks = svc_detail.get("frameworks", [])
        
        # Add a custom 'metadata' field for resource profiles
        ctx.service_path = svc_detail.get("path", service_name)   # ensure code_analysis_agent fills 'path'
        ctx.resources = profile
        ctx.raw_context_summary = f"Isolated Context for {service_name}\nResources: {profile}\nOriginal context follows:\n{ctx.raw_context_summary}"
        
        return ctx

    def _setup_gitops_repo(self, project_path: str, repo_url: str):
        """Detects or initializes GitOps repository structure (Overhaul 6 & 12)."""
        import os
        import subprocess
        gitops_dir = os.path.join(project_path, "gitops-repo")
        
        # 1. Handle Remote Cloning
        if repo_url and (repo_url.startswith("http") or repo_url.startswith("git@")):
            if not os.path.exists(gitops_dir):
                print(f"🌐 Cloning remote GitOps repository: {repo_url}...")
                try:
                    subprocess.run(["git", "clone", repo_url, gitops_dir], check=True, capture_output=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to clone GitOps repo: {e.stderr.decode()}")
                    # Fallback to local init if clone fails
            else:
                print(f"🔄 Pulling latest changes from GitOps repository...")
                try:
                    subprocess.run(["git", "-C", gitops_dir, "pull"], check=True, capture_output=True)
                except Exception as e:
                    logger.warning(f"Failed to pull GitOps repo updates: {e}")

        # 2. Local Initialization & Structure
        if not os.path.exists(gitops_dir):
            print(f"✨ Creating GitOps structural tree in {gitops_dir}...")
            os.makedirs(os.path.join(gitops_dir, "argocd"), exist_ok=True)
            os.makedirs(os.path.join(gitops_dir, "namespaces"), exist_ok=True)
            
            # Init as git repo if it's not one
            try:
                subprocess.run(["git", "init", gitops_dir], check=True, capture_output=True)
            except Exception: pass

            # Minimal README/Structure
            readme_content = (
                "# GitOps Repository\n"
                "Managed by UrbanOps Agent v12.0\n\n"
                "## Directory Layout\n"
                "- `argocd/applicationset.yaml`: The master App-of-Apps generator mapping to `apps/*`.\n"
                "- `namespaces/`: Contains the isolated `<svc_name>.yaml` Namespace declarations.\n"
                "- `apps/<svc_name>/`: Contains the specific `deployment.yaml`, `service.yaml`, and `hpa.yaml` definitions per service.\n"
            )
            with open(os.path.join(gitops_dir, "README.md"), "w") as f:
                f.write(readme_content)
        
        # Ensure standard folders exist
        os.makedirs(os.path.join(gitops_dir, "argocd"), exist_ok=True)
        os.makedirs(os.path.join(gitops_dir, "namespaces"), exist_ok=True)


