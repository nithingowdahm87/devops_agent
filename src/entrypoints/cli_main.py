import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import settings
from src.utils.logger import configure_logging, set_correlation_id, get_logger
from src.utils.analysis_utils import load_or_run_analysis

logger = get_logger("devops-agent.pipeline")
from src.decision_engine.orchestrator import V2Orchestrator


def print_header(title):
    print("\n" + "="*60)
    print(f"🚀 {title}")
    print("="*60)


def run_cli(args):
    """Execute the CLI pipeline (NVIDIA-only, auto-pilot only)."""
    # Only NVIDIA provider is supported
    os.environ["LLM_PRIMARY"] = "nvidia"
    os.environ["LLM_PROVIDER_MODE"] = "nvidia"

    configure_logging(json_mode=os.environ.get("LOG_JSON", "").lower() == "true")
    run_id = set_correlation_id()

    print_header(f"DevOps AI Agent Pipeline v2.0.0 [run:{run_id}]")
    logger.info("Pipeline started", extra={"stage": "init"})

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

    # Run V2 Orchestrator (auto-pilot only)
    orchestrator = V2Orchestrator(environment=args.env)
    orchestrator.run_pipeline(
        project_path=project_path,
        context=context,
        environment=args.env,
        gitops=False,  # GitOps removed
        gitops_repo=None,
        target_service=args.service,
        publisher=None,  # No publisher - local writes only
        no_prompts=True,  # Auto-pilot only
        no_heal=args.no_heal,
    )

    print("\n✅ Pipeline completed successfully!")
    logger.info("Pipeline completed", extra={"stage": "exit"})