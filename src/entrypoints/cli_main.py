import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.cli.stages import (
    run_docker_stage, run_compose_stage, run_k8s_stage,
    run_cicd_stage, run_debug_stage, run_cost_stage, print_header,
    _to_repo_slug
)
from src.config.settings import settings
from src.utils.logger import configure_logging, set_correlation_id, get_logger
from src.utils.analysis_utils import load_or_run_analysis

logger = get_logger("devops-agent.pipeline")
from src.decision_engine.orchestrator import V2Orchestrator
from src.gitops.pr_creator import GitOpsPublisher
from src.audit.decision_log import AuditLog
from src.schemas import ProjectContext, Decision, StageResult


# ================================================================
# MANUAL MENU
# ================================================================
def run_manual_menu(project_path, context, audit, publisher, run_id):
    while True:
        print("\n--- Manual Tools (Legacy) ---")
        print("2. [Scan]          Generate Security Configs (Sonar/OTel) [NEW]")
        print("3. [Docker]        Generate Dockerfile")
        print("4. [Compose]       Generate Docker Compose")
        print("5. [K8s]           Generate Kubernetes Manifests")
        print("6. [CI]            Generate GitHub Actions")
        print("7. [Debug]         Troubleshoot Errors")
        print("8. [Cost]          Cloud Cost Estimation")
        print("b. Back to Main Menu")

        choice = input("Run Stage: ").strip()

        result = None
        if choice == 'b':
            return
        elif choice == '2':
            # Temporary manual runner for Scan
            from src.engine.llm_generator import LLMGenerator
            from src.llm_clients.gemini_client import GeminiClient
            try:
                # Reuse V2 generator for manual run
                try:
                    from src.llm_clients.gemini_client import GeminiClient
                    client = GeminiClient()
                    client_name = "Gemini"
                except Exception:
                    print("⚠️  Gemini not available. Using Mock Client for Scan.")
                    from src.llm_clients.mock_client import MockClient
                    client = MockClient("MockScan")
                    client_name = "MockScan"

                gen = LLMGenerator(client, client_name)
                from src.utils.prompt_loader import load_prompt
                tmpl = load_prompt("security", "scan_config")

                # Mock plan
                class MockPlan:
                    observability_level = "strict"
                    service_type = "microservices"

                spec = gen.generate(tmpl, {"context": context.raw_context_summary, "plan_summary": "Manual Scan Run"})

                # Parse output
                import os, re
                params = re.findall(r"FILENAME: (.*?)\n```(?:\w+)?\n(.*?)```", spec.file_content, re.DOTALL)
                print("\n📦 Generating Configs:")
                for rel, content in params:
                    fp = os.path.join(project_path, rel.strip())
                    os.makedirs(os.path.dirname(fp), exist_ok=True)
                    with open(fp, "w") as f: f.write(content.strip())
                    print(f"  - {rel.strip()}")

                result = StageResult(stage_name="Scan", status=Decision.APPROVE, cycles=1)
            except Exception as e:
                print(f"❌ Scan generation failed: {e}")
        elif choice == '3':
            result = run_docker_stage(project_path, context, audit, publisher, run_id)
        elif choice == '4':
            result = run_compose_stage(project_path, context, audit, publisher, run_id)
        elif choice == '5':
            result = run_k8s_stage(project_path, context, audit, publisher, run_id)
        elif choice == '6':
            result = run_cicd_stage(project_path, context, audit, publisher, run_id)
        elif choice == '8':
            result = run_cost_stage(project_path, context, run_id)
        elif choice == '7':
            result = run_debug_stage(project_path, context, audit, publisher, run_id)
        else:
            print("⏳ Invalid option.")
            continue

        if result and result.status == Decision.APPROVE:
            print(f"🎉 Stage {result.stage_name} completed successfully.")

# ================================================================
# MAIN WIZARD (CLI MODE)
# ================================================================
def run_cli(args):
    """Execute the CLI pipeline (existing behavior)."""
    # Map --llm-mode to LLM_PRIMARY env var
    mode_to_primary = {
        "local":   "llamacpp",
        "kimchi":  "kimchi",
        "remote":  "groq",
    }
    os.environ["LLM_PRIMARY"] = mode_to_primary.get(args.llm_mode, args.llm_mode)
    os.environ["LLM_PROVIDER_MODE"] = args.llm_mode

    # Configure based on args
    from src.engine import config
    config.STRICT_MODE = args.strict

    gitops_repo_url = None
    if args.gitops_repo:
        # Derive slug for GitHub API (GitOpsPublisher)
        slug = _to_repo_slug(args.gitops_repo)
        if slug:
            os.environ["GITHUB_REPO"] = slug

        # Derive a clone URL for V2Orchestrator._setup_gitops_repo
        if args.gitops_repo.startswith(("http://", "https://", "git@")):
            gitops_repo_url = args.gitops_repo
        elif slug:
            gitops_repo_url = f"https://github.com/{slug}.git"

    configure_logging(json_mode=os.environ.get("LOG_JSON", "").lower() == "true")
    run_id = set_correlation_id()
    audit = AuditLog(run_id=run_id)
    publisher = GitOpsPublisher()

    print_header(f"DevOps AI Agent Pipeline v1.0.0 [run:{run_id}]")
    logger.info("Pipeline started | gitops_mode=%s", publisher.mode, extra={"stage": "init"})

    project_path = args.path or input("Enter project path: ").strip()
    project_path = os.path.abspath(os.path.expanduser(project_path))
    if not os.path.exists(project_path):
        print(f"Path does not exist: {project_path}")
        return

    # STEP 1: ANALYSIS
    print_header(f"Stage 1: Code Analysis & Caching [{args.env.upper()} mode]")
    context = load_or_run_analysis(project_path)
    logger.info("Context loaded: %s app", context.language, extra={"stage": "Analysis"})
    print(f"✅ Context Loaded: {context.language} app, Ports: {context.ports}")

    # Auto-select V2 Auto-Pilot if no prompt mode is enabled
    auto_select = getattr(args, "no_prompts", False)
    legacy_mode = getattr(args, "legacy", False)

    while True:
        if auto_select:
            choice = '1'
        else:
            print("\n--- DevOps AI Agent (v12.0) ---")
            print("1. 🧠  Start Automated DevOps Generation (Auto-Pilot / v1.0.0)")
            if legacy_mode:
                print("2. 🛠️   Run Specific Stages Manually (Legacy)")
                print("q. Exit")
            else:
                print("q. Exit")
            choice = input("Select: ").strip().lower()

        if choice == '1':
            orchestrator = V2Orchestrator()
            orchestrator.run_pipeline(
                project_path,
                context,
                environment=args.env,
                no_llm=args.no_llm,
                gitops=args.gitops,
                gitops_repo=gitops_repo_url or args.gitops_repo,
                target_service=args.service,
                publisher=publisher,
                no_prompts=getattr(args, "no_prompts", False),
                no_heal=args.no_heal,
            )
        elif choice == '2' and legacy_mode:
            run_manual_menu(project_path, context, audit, publisher, run_id)
        elif choice == 'q':
            break
        else:
            print("Invalid selection.")
            continue

    # Save audit trail on exit
    audit_path = audit.save()
    print(f"\n📝 Audit log saved: {audit_path}")
    print(audit.summary())
    logger.info("Pipeline completed", extra={"stage": "exit"})

    # Clean up DevOps context caching footprint on graceful exit
    for f in [".devops_context.json", ".devops_memory.json"]:
        fpath = os.path.join(project_path, f)
        if os.path.exists(fpath):
            try: os.remove(fpath)
            except Exception: pass
