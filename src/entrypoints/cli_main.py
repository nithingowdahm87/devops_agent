import os
import signal
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import settings
from src.utils.logger import configure_logging, set_correlation_id, get_logger
from src.analysis.code_analysis_agent import CodeAnalysisAgent

logger = get_logger("devops-agent.pipeline")
from src.decision_engine.orchestrator import V2Orchestrator


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"🚀 {title}")
    print("=" * 60)


def run_cli(args) -> None:
    """Execute the CLI pipeline (NVIDIA-only, auto-pilot only)."""
    os.environ["LLM_PRIMARY"] = "nvidia"
    os.environ["LLM_PROVIDER_MODE"] = "nvidia"

    configure_logging(json_mode=os.environ.get("LOG_JSON", "").lower() == "true")
    run_id = set_correlation_id()
    t_start = time.perf_counter()

    project_path = args.path or input("Enter project path: ").strip()
    project_path = os.path.abspath(os.path.expanduser(project_path))

    # SIGTERM handler for clean K8s Job shutdown
    def _handle_sigterm(sig, frame):
        logger.warning("sigterm_received", extra={"run_id": run_id})
        sys.exit(130)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    print_header(f"DevOps AI Agent Pipeline v2.0.0 [run:{run_id}]")
    logger.info("pipeline_started", extra={"stage": "init", "run_id": run_id})

    if not os.path.exists(project_path):
        print(f"Path does not exist: {project_path}")
        sys.exit(1)

    # STEP 1: ANALYSIS
    print_header(f"Stage 1: Code Analysis & Caching [{args.env.upper()} mode]")
    agent = CodeAnalysisAgent(project_path)
    context = agent.get_cached_analysis()
    logger.info("context_loaded", extra={"stage": "Analysis", "language": context.language})
    print(f"✅ Context Loaded: {context.language} app, Ports: {context.ports}")

    # STEP 2: PIPELINE
    orchestrator = V2Orchestrator(environment=args.env)
    orchestrator.run_pipeline(
        project_path=project_path,
        context=context,
        environment=args.env,
        gitops=False,
        gitops_repo=None,
        target_service=args.service,
        publisher=None,
        no_prompts=args.no_prompts,
        no_heal=args.no_heal,
    )

    elapsed = round(time.perf_counter() - t_start, 1)
    print(f"\n✓ devops-agent complete in {elapsed}s")
    logger.info("pipeline_completed", extra={"stage": "exit", "duration_s": elapsed})
    sys.exit(0)
