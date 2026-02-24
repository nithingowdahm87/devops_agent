from typing import List, Dict, Any, Optional
import logging
import os
import re
import concurrent.futures

from src.schemas import ProjectContext, Decision, StageResult
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.decision_engine.contracts.decision_result import DecisionResult

from src.decision_engine.planner.architecture_planner import ArchitecturePlanner
from src.decision_engine.generator.llm_generator import LLMGenerator
from src.decision_engine.scoring.scorecard import weighted_score
from src.decision_engine.scoring.evaluator import Evaluator
from src.decision_engine.repair.repair_agent import RepairAgent
from src.decision_engine.confidence.confidence_score import compute_confidence
from src.decision_engine.confidence.action_router import decide_action
from src.utils.prompt_loader import load_prompt
from src.memory.long_term_memory import LongTermMemory

from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.groq_client import GroqClient
from src.llm_clients.nvidia_client import NvidiaClient
from src.llm_clients.mock_client import MockClient

from src.tools.file_ops import write_file

logger = logging.getLogger("devops-agent")


class V2Orchestrator:
    def __init__(self):
        self.planner = ArchitecturePlanner()
        self.evaluator = Evaluator()
        self.repair_agent = RepairAgent()
        self.memory = None
        self.generators = []
        self._init_generators()

    def _init_generators(self):
        clients = [
            ("Gemini", GeminiClient),
            ("Groq",   GroqClient),
            ("NVIDIA", NvidiaClient),
        ]
        for name, cls in clients:
            try:
                client = cls()
                self.generators.append(LLMGenerator(client, name))
            except Exception as e:
                logger.warning(f"Failed to init {name} client: {e}. Using Mock.")
                self.generators.append(
                    LLMGenerator(MockClient(name=f"Mock-{name}"), f"Mock-{name}")
                )

    # ------------------------------------------------------------------ #
    # PUBLIC ENTRY POINT                                                   #
    # ------------------------------------------------------------------ #
    def run_pipeline(
        self,
        project_path: str,
        context: ProjectContext,
        environment: str = "prod",   # FIX: accepts environment kwarg from main.py
        no_llm: bool = False,        # FIX: accepts no_llm kwarg from main.py
    ):
        logger.info("Starting V2 Decision Engine Pipeline")
        self.memory = LongTermMemory(project_path)
        self.environment = environment
        self.no_llm = no_llm

        plan = self.planner.create_plan(context)
        print(
            f"🏗️  Architecture Plan: {plan.service_type.upper()} "
            f"| Scaling: {plan.scaling_strategy} | DB: {plan.requires_database}"
        )

        # ── Summary banner ──────────────────────────────────────────
        is_mono = "microservices" not in context.architecture
        num_dockerfiles = len(context.microservice_dirs) if not is_mono else 1
        dbs = context.databases if context.databases else {}

        def _norm(d):
            if isinstance(d, list): return {k: [] for k in d}
            if isinstance(d, dict): return d
            return {}

        rdbms_dict  = _norm(dbs.get("rdbms", {}))
        cache_dict  = _norm(dbs.get("cache", {}))
        nosql_dict  = _norm(dbs.get("nosql", {}))
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

        def _db_tag(svcs):
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
                detail     = context.microservice_details.get(svc, {})
                lang       = detail.get("language", "Node.js")
                frameworks = detail.get("frameworks", [])
                version    = detail.get("node_version", "?")
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
            print(
                f"  🔐  Env vars      : {', '.join(shown)}"
                f"{'  ...' if len(context.env_vars) > 7 else ''}"
            )
            print()

        print("=" * W + "\n")

        # ── Execute stages ─────────────────────────────────────────
        self._execute_stage("Dockerfile",           "dockerfile",     project_path, context, plan)
        self._execute_stage("Docker Compose",       "docker_compose", project_path, context, plan)
        self._execute_stage("Kubernetes Manifests", "kubernetes",     project_path, context, plan)
        self._execute_stage("CI Pipeline",          "cicd",           project_path, context, plan)

        print("\n🎉 Pipeline Execution Completed Successfully!")

        for f in [".devops_context.json", ".devops_memory.json"]:
            fpath = os.path.join(project_path, f)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

        import sys
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # STAGE EXECUTOR                                                       #
    # ------------------------------------------------------------------ #
    def _execute_stage(
        self,
        display_name: str,
        stage_key: str,
        project_path: str,
        context: ProjectContext,
        plan: ArchitecturePlan,
    ):
        print(f"\n--- Stage: {display_name} ---")

        # 1. Load prompt template
        prompt_map = {
            "dockerfile":     ("docker", "docker_production"),
            "kubernetes":     ("k8s",    "k8s_production"),
            "cicd":           ("cicd",   "cicd_production"),
            "scan":           ("debug",  "healer"),
            "docker_compose": ("docker", "docker_production"),
        }
        prompt_dir, prompt_name = prompt_map.get(stage_key, (stage_key, "writer_a"))

        try:
            template = load_prompt(prompt_dir, prompt_name)
        except Exception as e:
            logger.warning(f"Failed to load prompt {prompt_dir}/{prompt_name}: {e}")
            if "docker" in stage_key:
                template = load_prompt("docker", "docker_production")
            elif "k8s" in stage_key or "kubernetes" in stage_key:
                template = load_prompt("k8s", "k8s_production")
            elif "ci" in stage_key:
                template = load_prompt("cicd", "cicd_production")
            else:
                raise FileNotFoundError(f"No prompt found for stage: {stage_key}")

        # 2. Append FILENAME: format instruction per stage
        if stage_key == "dockerfile":
            if context.microservice_dirs:
                dirs = ", ".join(context.microservice_dirs)
                template += (
                    f"\n\nCRITICAL: Output EACH Dockerfile in its respective service "
                    f"directory using EXACTLY this format for every service:\n"
                    f"FILENAME: <service_dir>/Dockerfile\n"
                    f"```dockerfile\n<content>\n```\n"
                    f"Required service directories: {dirs}"
                )
            else:
                template += (
                    "\n\nCRITICAL: Output the Dockerfile using EXACTLY this format:\n"
                    "FILENAME: Dockerfile\n"
                    "```dockerfile\n<content>\n```"
                )

        elif stage_key == "docker_compose":
            # FIX: docker_compose also needs FILENAME: blocks so nginx.conf is not lost
            template += (
                "\n\nCRITICAL: Output ALL files (docker-compose.yml AND any nginx.conf "
                "or other referenced config files) each using EXACTLY this format:\n"
                "FILENAME: <filepath>\n"
                "```yaml\n<content>\n```"
            )

        elif stage_key == "kubernetes":
            dirs = ", ".join(context.microservice_dirs) if context.microservice_dirs else "app"
            template += (
                "\n\nCRITICAL: Output EACH Kubernetes resource "
                "(Deployment, Service, Ingress, HPA, ConfigMap, Namespace, ServiceAccount) "
                "in its OWN SEPARATE file using EXACTLY this format:\n"
                "FILENAME: k8s/<service>/deployment.yaml\n"
                "```yaml\n<content>\n```\n"
                f"Services to cover: {dirs}"
            )
            print("\n" + "=" * 50)
            print("☸️   KUBERNETES MANIFEST CUSTOMIZATION")
            print("=" * 50)
            user_input = input(
                "Would you like to provide custom instructions for kubernetes? [y/N]: "
            ).strip().lower()
            if user_input in ["y", "yes"]:
                custom = input("Enter instructions: ").strip()
                if custom:
                    template += f"\n\nUSER CUSTOM INSTRUCTIONS (MUST FOLLOW):\n{custom}"

        elif stage_key == "cicd":
            template += (
                "\n\nCRITICAL: Output the CI workflow using EXACTLY this format:\n"
                "FILENAME: .github/workflows/ci.yml\n"
                "```yaml\n<content>\n```"
            )

        # 3. Build prompt context
        prompt_context = {
            "context": context.raw_context_summary,
            "plan_summary": str(plan),
        }
        prompt_context.update(context.model_dump())

        # 4. Generate drafts in parallel
        candidates = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(self.generators)
        ) as executor:
            futures = [
                executor.submit(g.generate, template, prompt_context)
                for g in self.generators
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    candidates.append(future.result())
                except Exception as e:
                    logger.error(f"Generator failed: {e}")

        if not candidates:
            print("❌ All generators failed for this stage.")
            return

        # 5. Heuristic scoring
        for c in candidates:
            content_lower = c.file_content.lower()
            sec = 60
            if "user " in content_lower and any(
                x in content_lower for x in ("adduser", "useradd", "nonroot")
            ):
                sec += 15
            if ":latest" not in content_lower:
                sec += 10
            if any(
                x in content_lower
                for x in ("no-cache", "--no-cache-dir", "rm -rf /var/lib")
            ):
                sec += 10
            if "copy .env" not in content_lower and "env password" not in content_lower:
                sec += 5
            c.security_score = min(100, sec)

            bp = 60
            if "as builder" in content_lower:
                bp += 15
            if "workdir" in content_lower:
                bp += 10
            if 'cmd ["' in content_lower or "cmd ['" in content_lower:
                bp += 10
            if (
                "label org.opencontainers" in content_lower
                or "label maintainer" in content_lower
            ):
                bp += 5
            c.best_practice_score = min(100, bp)

        useful = sum(1 for c in candidates if len(c.file_content.strip()) > 100)
        model_agreement = useful / max(len(candidates), 1)

        # 6. Select best draft
        best_spec, best_score = self.evaluator.evaluate_candidates(candidates)
        print(f"🏆 Selected Draft from {best_spec.model_name} (Score: {best_score:.1f})")

        final_content = best_spec.file_content
        if not final_content.strip():
            print("⚠️  Selected draft is empty. Skipping write.")
            return

        # 7. Confidence gate
        confidence_val = compute_confidence(
            best_spec, repair_attempts=0, model_agreement_score=model_agreement
        )
        decision = decide_action(confidence_val)

        if decision.requires_human_gate:
            print(f"\n🤖 Confidence: {confidence_val:.1f}% → Action: {decision.action.upper()}")
            print(f"   Reason: {decision.reason}")
            user_input = input(f"Proceed with {display_name}? [y/n]: ").lower()
            if user_input != "y":
                print("Skipping write.")
                return

        # 8. Write output — ALL stages go through multifile handler
        self._handle_multifile_output(final_content, project_path, stage_key)

        # 9. Store in memory
        self.memory.store_decision(
            stage=stage_key,
            content=final_content,
            reason=decision.reason,
            decision="APPROVED",
        )

    # ------------------------------------------------------------------ #
    # MULTIFILE OUTPUT HANDLER                                             #
    # ------------------------------------------------------------------ #
    def _handle_multifile_output(
        self, content: str, project_path: str, stage_key: str = ""
    ):
        """
        Parse FILENAME: blocks from LLM output and write each to disk.
        - Handles \\r\\n line endings
        - Handles optional blank lines between FILENAME: and fence
        - Guards against corrupt paths (content embedded in path name)
        - Falls back to a sensible default filename per stage
        """
        # Flexible: optional CR, optional blank lines, optional fence lang tag
        pattern = r"FILENAME:\s*([^\r\n]+)[\r\n]+```[\w.-]*[\r\n]+(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            print("📦 Writing Multiple Config Files:")
            for rel_path, file_content in matches:
                rel_path = rel_path.strip().lstrip("/")

                # Guard: path must not contain newlines or be a huge blob
                if "\n" in rel_path or len(rel_path) > 255:
                    import hashlib
                    digest = hashlib.md5(rel_path.encode()).hexdigest()[:8]
                    rel_path = f"recovered_{digest}.txt"
                    print(f"  ⚠️  Corrupt path detected, saving as {rel_path}")

                full_path = os.path.join(project_path, rel_path)
                # FIX: always derive dir from abspath to avoid makedirs("")
                dir_path = os.path.dirname(os.path.abspath(full_path))
                os.makedirs(dir_path, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as fh:
                    fh.write(file_content.strip())
                print(f"  - Created {rel_path}")
        else:
            fallback_map = {
                "dockerfile":     "Dockerfile",
                "docker_compose": "docker-compose.yml",
                "kubernetes":     "k8s/manifest.yaml",
                "cicd":           ".github/workflows/ci.yml",
                "scan":           "scan_configs.md",
            }
            fallback = fallback_map.get(stage_key, "generated_output.txt")
            print(
                f"⚠️  No FILENAME: blocks found in LLM output. "
                f"Writing raw output to '{fallback}'"
            )
            full_path = os.path.join(project_path, fallback)
            dir_path = os.path.dirname(os.path.abspath(full_path))
            os.makedirs(dir_path, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as fh:
                fh.write(content)
