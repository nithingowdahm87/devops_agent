"""Pipeline service — wraps the CLI pipeline for API usage."""
import asyncio
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.config.settings import settings


class PipelineService:
    """Non-interactive service wrapper for V2Orchestrator."""
    
    async def run(
        self,
        project_path: str,
        config: dict[str, Any] | None = None,
        no_heal: bool = False,
    ) -> dict[str, Any]:
        """Run the pipeline for a project and return structured results.
        
        Args:
            project_path: Absolute path to the project directory
            config: Optional overrides (env, strict, gitops, service, etc.)
            no_heal: Skip healer/validation retries
            
        Returns:
            {
                "status": "completed" | "failed",
                "artifacts": {"path": "content", ...},
                "logs": ["..."],
                "errors": ["..."],
            }
        """
        config = config or {}
        results = {
            "status": "pending",
            "artifacts": {},
            "logs": [],
            "errors": [],
        }
        
        # Capture stdout via contextlib (no monkey-patching)
        capturer = io.StringIO()

        try:
            with contextlib.redirect_stdout(capturer):
                logger.info("Starting pipeline for {path}", path=project_path)
                results["logs"].append(f"Starting pipeline for {project_path}")

                # Import here to avoid side-effects at module load time
                from src.agents.code_analysis_agent import CodeAnalysisAgent
                from src.decision_engine.orchestrator import V2Orchestrator
                from src.gitops.pr_creator import GitOpsPublisher
                from src.schemas import ProjectContext
                from src.utils.analysis_utils import load_or_run_analysis
                from src.utils.logger import set_correlation_id, configure_logging

                configure_logging(json_mode=False)
                run_id = set_correlation_id()

                # Set env vars from config
                if config.get("no_llm"):
                    os.environ["LLM_PROVIDER_MODE"] = "no-llm"
                if config.get("gitops"):
                    os.environ["LLM_PROVIDER_MODE"] = "gitops"
                if config.get("service"):
                    os.environ["TARGET_SERVICE"] = config["service"]

                # Load context
                context = load_or_run_analysis(project_path)
                logger.info("Context loaded: {lang}", lang=context.language)
                results["logs"].append(f"Context: {context.language} app, services: {len(context.microservice_dirs)}")

                # Run pipeline (non-interactive)
                orchestrator = V2Orchestrator(environment=config.get("environment", "dev"))

                # Set publisher if needed
                publisher = GitOpsPublisher()

                # Call the pipeline (it will write files to disk)
                orchestrator.run_pipeline(
                    project_path=project_path,
                    context=context,
                    environment=config.get("environment", "dev"),
                    no_llm=config.get("no_llm", False),
                    gitops=config.get("gitops", False),
                    gitops_repo=config.get("gitops_repo"),
                    target_service=config.get("service"),
                    publisher=publisher,
                    no_prompts=True,  # CRITICAL: skip interactive prompts
                    no_heal=no_heal,
                )

                # Collect artifacts from disk
                outputs_dir = Path(project_path) / "outputs"
                if outputs_dir.exists():
                    for f in outputs_dir.rglob("*"):
                        if f.is_file():
                            rel = str(f.relative_to(project_path))
                            try:
                                results["artifacts"][rel] = f.read_text(encoding="utf-8")
                            except Exception:
                                pass

                # Also scan gitops-repo
                gitops_dir = Path(project_path) / "gitops-repo"
                if gitops_dir.exists():
                    for f in gitops_dir.rglob("*"):
                        if f.is_file():
                            rel = str(f.relative_to(project_path))
                            try:
                                results["artifacts"][rel] = f.read_text(encoding="utf-8")
                            except Exception:
                                pass

                results["status"] = "completed"
                results["logs"].append("Pipeline completed successfully")

        except Exception as e:
            logger.exception("Pipeline failed")
            results["status"] = "failed"
            results["errors"].append(str(e))
            results["logs"].append(f"Error: {e}")

        finally:
            # Append captured stdout to logs
            captured_output = capturer.getvalue()
            if captured_output:
                results["logs"].append("--- Captured Output ---")
                results["logs"].extend(captured_output.strip().split("\n"))

        return results