# -*- coding: utf-8 -*-
import os
import sys
import io

# Enforce UTF-8 for stdout and stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import json
import time
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.code_analysis_agent import CodeAnalysisAgent
from src.agents.docker_agents import DockerWriterA, DockerWriterB, DockerWriterC, DockerReviewer, DockerExecutor
from src.agents.k8s_agents import K8sWriterA, K8sWriterB, K8sWriterC, K8sReviewer, K8sExecutor
from src.agents.deterministic_reviewer import DeterministicReviewer
from src.decision_engine.orchestrator import V2Orchestrator
from src.agents.guidelines_compliance_agent import GuidelinesComplianceAgent
from src.agents.docker_compose_agent import DockerComposeWriter, ComposeReviewer, DockerComposeExecutor
from src.agents.cicd_agent import CIWriterA, CIWriterB, CIWriterC, CIReviewer, CIExecutor
from src.agents.cost_agent import CostEstimator, CostExecutor
from src.agents.debugging_agent import DebugWriterA, DebugWriterB, DebugWriterC, DebugReviewer, DebugExecutor
from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.groq_client import GroqClient
from src.llm_clients.nvidia_client import NvidiaClient
from src.utils.resilience import safe_llm_call
from src.utils.sanitizer import sanitize_feedback
from src.utils.constants import GUIDELINES_DOCKER, GUIDELINES_K8S, GUIDELINES_CI
from src.utils.logger import get_logger, set_correlation_id, configure_logging
from src.utils.parallel import run_writers_parallel
from src.audit.decision_log import AuditLog
from src.policy.validator import PolicyValidator
from src.gitops.pr_creator import GitOpsPublisher
from src.schemas import ProjectContext, StageResult, Decision, Severity, PolicyViolation
from src.engine.llm_generator import LLMGenerator

logger = get_logger("devops-agent.pipeline")

# ================================================================
# SHARED UTILS
# ================================================================
def _to_repo_slug(url_or_slug: str) -> str:
    """
    Normalize a GitHub repo identifier to 'owner/repo' slug form.

    Accepts:
      - 'owner/repo'
      - 'https://github.com/owner/repo.git'
      - 'git@github.com:owner/repo.git'
    """
    url_or_slug = (url_or_slug or "").strip()
    if not url_or_slug:
        return ""

    # HTTPS/HTTP URL
    if url_or_slug.startswith(("http://", "https://")):
        from urllib.parse import urlparse

        path = urlparse(url_or_slug).path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path  # owner/repo

    # SSH URL
    if url_or_slug.startswith("git@"):
        # git@github.com:owner/repo.git
        try:
            _, path = url_or_slug.split(":", 1)
        except ValueError:
            return url_or_slug
        path = path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path

    # Already a slug
    return url_or_slug

def print_header(title):
    print("\n" + "="*60)
    print(f"🚀 {title}")
    print("="*60)

from src.utils.analysis_utils import load_or_run_analysis

def guidelines_check(reasoning, guidelines_path):
    """Run GuidelinesComplianceAgent and print results."""
    try:
        gate = GuidelinesComplianceAgent().analyze_and_update(reasoning, guidelines_path)
        if gate['new_practices_found']:
            print(f"🛡️  New Best Practices Learned: {gate['added_points']}")
        return gate
    except Exception as e:
        print(f"  (Guidelines check skipped: {e})")
        return {"new_practices_found": False, "added_points": []}

def human_decision() -> Decision:
    """Standard 3-option human decision gate."""
    while True:
        choice = input("\n✅ Approve (y) / 🔄 Refine (r) / ❌ Reject (n): ").strip().lower()
        
        if choice in ['y', 'yes']:
            return Decision.APPROVE
        elif choice in ['r', 'refine']:
            return Decision.REFINE
        elif choice in ['n', 'no', 'reject']:
            return Decision.REJECT
        
        print("Invalid choice. Please enter 'y', 'r', or 'n'.")

def stage_decision_loop(stage_name, reviewer, drafts, executor, run_executor_fn,
                        guidelines_path, audit, det_reviewer=None, det_fn=None,
                        publisher=None, output_files=None, project_path="", run_id="") -> StageResult:
    """
    Shared refine loop logic across all stages.
    """
    policy_validator = PolicyValidator()
    user_feedback = ""
    
    for i in range(3):
        logger.info("Review cycle %d/3", i + 1, extra={"stage": stage_name})
        print(f"\n--- Review Cycle {i+1}/3 ---")
        
        report = ""
        if det_reviewer and det_fn:
            report = "--- VALIDATION REPORT ---\n"
            labels = ["Draft A", "Draft B", "Draft C"]
            for idx, d in enumerate(drafts):
                if d:
                    report += f"{labels[idx]}: {det_fn(det_reviewer, d)[1]}\n"
        if user_feedback:
            report += f"\nUSER FEEDBACK (MUST ADDRESS): {user_feedback}\n"
        
        # AI Review
        logger.info("AI review starting", extra={"stage": stage_name})
        final, reasoning = reviewer.review_and_merge(drafts[0], drafts[1], drafts[2], validation_report=report)
        
        print(f"\n🧠 AI Reasoning:\n{reasoning}\n")
        print(f"📄 Proposed Output:\n{final}\n")
        
        # Policy Gate
        passed, violations = policy_validator.validate(final, stage_name)
        if violations:
            print(f"\n🛡️  Policy Check ({len(violations)} finding(s)):")
            for v in violations:
                icon = "❌" if v.severity == Severity.ERROR else "⚠️"
                print(f"  {icon} [{v.severity.value.upper()}] {v.rule}: {v.message}")
            if not passed:
                print("⛔ Critical policy violations found. Please refine.")
        else:
            print("✅ Policy check passed.")
        
        guidelines_check(reasoning, guidelines_path)
        
        decision = human_decision()
        audit.record(stage=stage_name, decision=decision.value, reasoning=reasoning,
                     user_feedback=user_feedback, cycle=i + 1, drafts_count=sum(1 for d in drafts if d))
        
        if decision == Decision.APPROVE:
            published_via = None
            if publisher and output_files:
                files = {fname: final for fname in output_files}
                result = publisher.publish(
                    files=files, stage=stage_name, run_id=run_id,
                    reasoning=reasoning, project_path=project_path,
                )
                if result["mode"] == "pr":
                    print(f"🚀 PR created: {result['url']}")
                    published_via = "github_pr"
                elif result["mode"] == "local":
                    print(f"✅ Written locally: {', '.join(result['paths'])}")
                    published_via = "local_write"
                else:
                    # Fallback failed — use executor directly
                    run_executor_fn(final)
                    published_via = "local_exec"
            else:
                run_executor_fn(final)
                published_via = "local_exec"
                
            logger.info("Stage approved", extra={"stage": stage_name, "decision": "approve"})
            return StageResult(
                stage_name=stage_name,
                status=Decision.APPROVE,
                content=final,
                reasoning=reasoning,
                policy_violations=violations,
                cycles=i+1,
                published_via=published_via
            )
            
        elif decision == Decision.REFINE:
            user_feedback = sanitize_feedback(input("💬 Your feedback: "))
            logger.info("Refine requested", extra={"stage": stage_name, "decision": "refine"})
        else:
            logger.info("Stage rejected", extra={"stage": stage_name, "decision": "reject"})
            return StageResult(
                stage_name=stage_name,
                status=Decision.REJECT,
                policy_violations=violations,
                cycles=i+1
            )
    
    logger.warning("Max refine cycles reached", extra={"stage": stage_name})
    print("⚠️  Max refine cycles reached.")
    return StageResult(
        stage_name=stage_name,
        status=Decision.REJECT,
        reasoning="Max cycles reached",
        cycles=3
    )


# ================================================================
# STAGE 3: Dockerfile
# ================================================================
def run_docker_stage(project_path, context: ProjectContext, audit, publisher=None, run_id="") -> StageResult:
    print_header("Stage 3: Docker Infrastructure Generation")
    context_str = context.model_dump_json(indent=2)
    
    # Initialize
    try:
        wa, wb, wc = DockerWriterA(), DockerWriterB(), DockerWriterC()
        reviewer = DockerReviewer()
    except Exception as e:
        logger.warning("API Keys missing, using mocks: %s", e)
        from src.llm_clients.mock_client import MockClient
        class MockWriter:
            def generate(self, context=""): return MockClient("MockDocker").call("draft dockerfile")
        wa, wb, wc = MockWriter(), MockWriter(), MockWriter()
        class MockDockerReviewer:
            def review_and_merge(self, a, b, c, validation_report=""):
                if "DOCKERFILE:" in a:
                    parts = a.split("DOCKERFILE:")
                    return (parts[1].strip(), parts[0].replace("REASONING:", "").strip())
                return (a, "Mock reasoning")
        reviewer = MockDockerReviewer()
        
    det_reviewer, executor = DeterministicReviewer(), DockerExecutor()
    
    # Generate in parallel
    logger.info("Generating drafts in parallel", extra={"stage": "Docker"})
    print("Drafting Dockerfiles in parallel (Gemini, Groq, NVIDIA)...")
    drafts = run_writers_parallel(
        writers=[(wa, "Gemini"), (wb, "Groq"), (wc, "NVIDIA")],
        generate_fn=lambda w, ctx: w.generate(context=ctx),
        context=context_str,
        stage="Docker",
    )
    
    return stage_decision_loop(
        stage_name="Docker", reviewer=reviewer, drafts=drafts,
        executor=executor, run_executor_fn=lambda final: executor.run(final, project_path),
        guidelines_path=GUIDELINES_DOCKER, audit=audit,
        det_reviewer=det_reviewer, det_fn=lambda r, d: r.review_dockerfile(d),
        publisher=publisher, output_files={"Dockerfile": None},
        project_path=project_path, run_id=run_id,
    )


# ================================================================
# STAGE 4: Docker Compose
# ================================================================
def run_compose_stage(project_path, context: ProjectContext, audit, publisher=None, run_id="") -> StageResult:
    print_header("Stage 4: Docker Compose Generation")
    ctx_str = context.model_dump_json(indent=2)
    
    # Initialize
    try:
        writers = [
            DockerComposeWriter(),
            DockerComposeWriter(),
            DockerComposeWriter()
        ]
        reviewer = ComposeReviewer()
    except Exception as e:
        logger.warning("API Keys missing, using mocks: %s", e)
        from src.llm_clients.mock_client import MockClient
        writers = [
            DockerComposeWriter(MockClient("GeminiMock")),
            DockerComposeWriter(MockClient("GroqMock")),
            DockerComposeWriter(MockClient("NvidiaMock"))
        ]
        class MockReviewer:
            def review_and_merge(self, a, b, c, validation_report=""):
                return (a, "Mock Compose reasoning.")
        reviewer = MockReviewer()
    executor = DockerComposeExecutor()
    
    # Generate in parallel
    logger.info("Generating drafts in parallel", extra={"stage": "Compose"})
    print("Drafting Compose Files in parallel (Gemini, Groq, NVIDIA)...")
    drafts = run_writers_parallel(
        writers=[(writers[0], "Gemini"), (writers[1], "Groq"), (writers[2], "NVIDIA")],
        generate_fn=lambda w, ctx: w.generate(ctx),
        context=ctx_str,
        stage="Compose",
    )
    
    return stage_decision_loop(
        stage_name="Compose", reviewer=reviewer, drafts=drafts,
        executor=executor, run_executor_fn=lambda final: executor.run(final, project_path),
        guidelines_path=GUIDELINES_DOCKER, audit=audit,
        publisher=publisher, output_files={"docker-compose.yml": None},
        project_path=project_path, run_id=run_id,
    )


# ================================================================
# STAGE 5: Kubernetes Manifests
# ================================================================
def run_k8s_stage(project_path, context: ProjectContext, audit, publisher=None, run_id="") -> StageResult:
    print_header("Stage 5: Kubernetes Manifests")
    ctx_str = context.model_dump_json(indent=2)
    service_name = context.project_name or 'myapp'
    
    # Initialize
    try:
        wa, wb, wc = K8sWriterA(), K8sWriterB(), K8sWriterC()
        reviewer = K8sReviewer()
    except Exception as e:
        logger.warning("API Keys missing, using mocks: %s", e)
        from src.llm_clients.mock_client import MockClient
        class MockK8sWriter:
            def generate(self, context=""): return MockClient("MockK8s").call("kubernetes")
        wa, wb, wc = MockK8sWriter(), MockK8sWriter(), MockK8sWriter()
        class MockK8sReviewer:
            def review_and_merge(self, a, b, c, validation_report=""):
                if "YAML:" in a:
                    parts = a.split("YAML:")
                    return (parts[1].replace("```yaml", "").replace("```", "").strip(), parts[0].replace("REASONING:", "").strip())
                return (a, "Mock reasoning")
        reviewer = MockK8sReviewer()
        
    det_reviewer = DeterministicReviewer()
    executor = K8sExecutor()
    
    # Generate in parallel
    logger.info("Generating drafts in parallel", extra={"stage": "K8s"})
    print("Drafting Manifests in parallel (Gemini, Groq, NVIDIA)...")
    drafts = run_writers_parallel(
        writers=[(wa, "Gemini"), (wb, "Groq"), (wc, "NVIDIA")],
        generate_fn=lambda w, ctx: w.generate(context=ctx),
        context=ctx_str,
        stage="K8s",
    )
    
    return stage_decision_loop(
        stage_name="K8s", reviewer=reviewer, drafts=drafts,
        executor=executor, run_executor_fn=lambda final: executor.run(final, os.path.join(project_path, "k8s", "manifest.yaml")),
        guidelines_path=GUIDELINES_K8S, audit=audit,
        det_reviewer=det_reviewer, det_fn=lambda r, d: r.review_k8s(d),
        publisher=publisher, output_files={"k8s/manifest.yaml": None},
        project_path=project_path, run_id=run_id,
    )


# ================================================================
# STAGE 6: CI (GitHub Actions)
# ================================================================
def run_cicd_stage(project_path, context: ProjectContext, audit, publisher=None, run_id="") -> StageResult:
    print_header("Stage 6: CI Generation (GitHub Actions)")
    ctx_str = context.model_dump_json(indent=2)
    
    # Initialize
    try:
        wa, wb, wc = CIWriterA(), CIWriterB(), CIWriterC()
        reviewer = CIReviewer()
    except Exception as e:
        logger.warning("API Keys missing, using mocks: %s", e)
        from src.llm_clients.mock_client import MockClient
        class MockCIWriter:
            def generate(self, ctx): return MockClient("MockCI").call("github actions")
        wa, wb, wc = MockCIWriter(), MockCIWriter(), MockCIWriter()
        class MockCIReviewer:
            def review_and_merge(self, a, b, c, validation_report=""):
                return (a, "Mock CI Review: Combined security and speed steps.")
        reviewer = MockCIReviewer()
        
    executor = CIExecutor()
    
    # Generate in parallel
    logger.info("Generating drafts in parallel", extra={"stage": "CI"})
    print("Drafting Workflows in parallel (Gemini, Groq, NVIDIA)...")
    drafts = run_writers_parallel(
        writers=[(wa, "Gemini"), (wb, "Groq"), (wc, "NVIDIA")],
        generate_fn=lambda w, ctx: w.generate(ctx),
        context=ctx_str,
        stage="CI",
    )
    
    return stage_decision_loop(
        stage_name="CI", reviewer=reviewer, drafts=drafts,
        executor=executor, run_executor_fn=lambda final: executor.run(final, project_path),
        guidelines_path=GUIDELINES_CI, audit=audit,
        publisher=publisher, output_files={".github/workflows/main.yml": None},
        project_path=project_path, run_id=run_id,
    )





# ================================================================
# STAGE 7: Debugging / Troubleshooting
# ================================================================
def run_debug_stage(project_path, context: ProjectContext, audit, publisher=None, run_id="") -> StageResult:
    print_header("Stage 7: Debugging & Troubleshooting")
    ctx_str = context.model_dump_json(indent=2)
    
    # Get error input
    print("Provide the error/log to analyze.")
    print("Options:")
    print("  1. Paste error text directly")
    print("  2. Provide path to a log file")
    input_choice = input("Choice (1/2): ").strip()
    
    error_input = ""
    if input_choice == '2':
        log_path = input("Log file path: ").strip()
        try:
            from src.tools.file_ops import read_file
            error_input = read_file(log_path)
        except Exception as e:
            logger.error("Could not read log file: %s", e)
            print(f"❌ Could not read log file: {e}")
            return StageResult(stage_name="Debug", status=Decision.REJECT, reasoning=f"File error: {e}")
    else:
        print("Paste error (type END on a new line when done):")
        lines = []
        while True:
            line = input()
            if line.strip() == 'END':
                break
            lines.append(line)
        error_input = '\n'.join(lines)
    
    if not error_input.strip():
        print("❌ No input provided.")
        return StageResult(stage_name="Debug", status=Decision.REJECT, reasoning="No input")
    
    # Initialize
    try:
        wa, wb, wc = DebugWriterA(), DebugWriterB(), DebugWriterC()
        reviewer = DebugReviewer()
    except Exception as e:
        logger.warning("API Keys missing, using mocks: %s", e)
        from src.llm_clients.mock_client import MockClient
        class MockDebugWriter:
            def analyze(self, e, c=""): return MockClient("MockDebug").call("debug analysis")
        wa, wb, wc = MockDebugWriter(), MockDebugWriter(), MockDebugWriter()
        class MockDebugReviewer:
            def review_and_merge(self, a, b, c, v=""): return ("Mock Incident Report", "Mock Reasoning")
        reviewer = MockDebugReviewer()
        
    executor = DebugExecutor()
    
    # Analyze
    print("Analyzing incident (RCA, Security, Performance)...")
    a1 = wa.analyze(error_input, ctx_str)
    a2 = wb.analyze(error_input, ctx_str)
    a3 = wc.analyze(error_input, ctx_str)
    
    logger.info("Generating debug analysis (3 variants)", extra={"stage": "Debug"})
    drafts = [a1, a2, a3]
    
    # Route through stage_decision_loop for policy/audit/approval
    return stage_decision_loop(
        stage_name="Debug",
        reviewer=reviewer,
        drafts=drafts,
        executor=executor,
        run_executor_fn=lambda report: executor.run(report, project_path),
        guidelines_path="",  # Guidelines N/A for raw debug analysis
        audit=audit,
        publisher=publisher,
        output_files={"INCIDENT_REPORT.md": None},
        project_path=project_path,
        run_id=run_id,
    )


def run_cost_stage(project_path, context: ProjectContext, run_id="") -> StageResult:
    print_header("Stage 8: Cloud Cost Estimation (FinOps)")
    
    # Check if K8s manifest exists (Traditional or GitOps layout)
    manifest_path = os.path.join(project_path, "k8s", "manifest.yaml")
    gitops_path = os.path.join(project_path, "outputs", "shared", "gitops")
    
    if not os.path.exists(manifest_path) and os.path.exists(gitops_path):
        # Scan for any manifest in the gitops folder
        import glob
        gitops_manifests = glob.glob(f"{gitops_path}/**/*.yaml", recursive=True)
        if gitops_manifests:
            manifest_path = gitops_manifests[0] # Use the first one for estimation
            print(f"💰 Analyzing GitOps manifests for cost estimation: {os.path.basename(manifest_path)}")

    if not os.path.exists(manifest_path):
        print(f"⚠️  No K8s manifest found at {manifest_path} or in GitOps area. Skipping cost estimation.")
        return StageResult(stage_name="Cost", status=Decision.REJECT, reasoning="No manifest found")
        
    try:
        from src.tools.file_ops import read_file
        manifest_content = read_file(manifest_path)
    except Exception as e:
        logger.error("Failed to read manifest: %s", e)
        return StageResult(stage_name="Cost", status=Decision.REJECT, reasoning=f"Read error: {e}")
        
    print("Estimating monthly cloud costs based on manifests...")
    try:
        estimator = CostEstimator()
        report = estimator.estimate(manifest_content)
        
        executor = CostExecutor()
        executor.run(report, project_path)
        
        print("\n" + "="*40)
        print("COST ESTIMATION REPORT")
        print("="*40)
        print(report)
        print("="*40 + "\n")
        
        return StageResult(stage_name="Cost", status=Decision.APPROVE, reasoning="Estimation complete")
    except Exception as e:
        logger.error("Cost estimation failed: %s", e)
        print(f"❌ Cost estimation failed: {e}")
        return StageResult(stage_name="Cost", status=Decision.REJECT, reasoning=f"Error: {e}")

    



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
# MAIN WIZARD
# ================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="DevOps AI Agent Pipeline v12.0")
    parser.add_argument("--env", type=str, default="dev", help="Environment (dev, staging, prod)")
    parser.add_argument("--strict", action="store_true", help="Enable strict policy mode")
    parser.add_argument("--no-llm", action="store_true", help="Force deterministic fallback mode")
    parser.add_argument("--gitops", action="store_true", help="Enable GitOps mode (per-service CI & manifests)")
    parser.add_argument("--gitops-repo", type=str, help="GitOps repository URL or path")
    parser.add_argument("--service", type=str, help="Target a specific microservice only")
    parser.add_argument("--no-prompts", action="store_true", help="Run fully non-interactive (skip extra customization questions)")
    parser.add_argument("--llm-mode", type=str, choices=["remote_first", "ollama_first", "ollama_only"],
                        default=os.environ.get("LLM_PROVIDER_MODE", "remote_first"),
                        help="LLM provider mode: remote_first, ollama_first, or ollama_only")
    parser.add_argument("path", type=str, nargs="?", help="Project path")
    args = parser.parse_args()

    # Set LLM provider mode from CLI
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
    
    print_header(f"DevOps AI Agent Pipeline v12.0 [run:{run_id}]")
    logger.info("Pipeline started | gitops_mode=%s", publisher.mode, extra={"stage": "init"})
    
    project_path = args.path or input("Enter project path: ").strip()
    if not project_path or not os.path.exists(project_path):
        print(f"❌ Path does not exist: {project_path}")
        return

    # STEP 1: ANALYSIS
    print_header(f"Stage 1: Code Analysis & Caching [{args.env.upper()} mode]")
    context = load_or_run_analysis(project_path)
    logger.info("Context loaded: %s app", context.language, extra={"stage": "Analysis"})
    print(f"✅ Context Loaded: {context.language} app, Ports: {context.ports}")
    
    while True:
        print("\n--- DevOps AI Agent (v12.0) ---")
        print("1. 🧠  Start Automated DevOps Generation (Auto-Pilot / V2)")
        print("2. 🛠️   Run Specific Stages Manually (Legacy)")
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
            )
        elif choice == '2':
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


if __name__ == "__main__":
    main()
