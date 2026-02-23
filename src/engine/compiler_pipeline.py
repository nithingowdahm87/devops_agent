# -*- coding: utf-8 -*-
import logging
from typing import List, Any
from src.engine.config import DEFAULT_ENVIRONMENT
from src.engine.severity import Severity, ExitCode, get_exit_code
from src.engine.artifact_manager import ArtifactManager
from src.engine.graph import ArchitectureGraph
from src.models.domain import ProjectModel

logger = logging.getLogger("devops-agent")

class CompilerPipeline:
    """
    The Locked Execution Order for the Infrastructure Compiler.
    Enforces a rigid pipeline to prevent architectural drift.
    """
    
    def __init__(self, project_path: str, environment: str = DEFAULT_ENVIRONMENT):
        self.project_path = project_path
        self.environment = environment
        self.artifact_mgr = ArtifactManager(project_path, environment)
        self.max_severity = Severity.LOW

    def run(self):
        """
        Locked sequence: 
        Analysis -> Model -> Graph -> Generate -> Validate -> Heal -> Policy -> Consistency -> Integrity -> Write
        """
        logger.info(f"🏗️ Starting Compiler Pipeline in [{self.environment}] mode.")
        
        try:
            # 1. Analysis
            from src.agents.code_analysis_agent import CodeAnalysisAgent
            analysis_agent = CodeAnalysisAgent(self.project_path)
            context = analysis_agent.analyze()
            
            # 2. Build Project Model & Architecture Graph (Immutable after this)
            model = self._build_model(context)
            graph = ArchitectureGraph(model)
            logger.info("📐 Architecture Graph locked as Immutable Source of Truth.")
            
            # 3. Generate Artifacts (Stages)
            # This is where we plug in the per-stage logic
            # For now, we use a placeholder loop that represents StageRegistry
            # In Phase 3, we will formalize per-stage validators/healers here.
            
            # 4. Final Integrity & Idempotency Audit
            self._run_integrity_audit(graph)
            
            # 5. Success Check
            logger.info("🏆 Compiler Pipeline completed successfully.")
            return ExitCode.SUCCESS
            
        except Exception as e:
            logger.critical(f"💥 Compiler Pipeline CRASHED: {e}")
            return ExitCode.CRITICAL_ERROR

    def _build_model(self, context) -> ProjectModel:
        # Converts ProjectContext (probabilistic) to ProjectModel (deterministic)
        from src.models.domain import Service
        from src.engine.lts_lookup import LTSLookup
        services = []
        
        if hasattr(context, 'microservice_details') and context.microservice_details:
            for name, d in context.microservice_details.items():
                runtime = d.get('language', 'unknown')
                lts_ver = LTSLookup.get_lts_version(runtime)
                services.append(Service(
                    name=name,
                    language=runtime,
                    runtime_version=lts_ver,
                    base_image=d.get('base_image', 'alpine'),
                    port=int(d.get('ports', [3000])[0]),
                    dependencies=[], # TODO: Derive from analysis
                    is_public=d.get('role') == 'API Gateway / Reverse Proxy'
                ))
        else:
            # Monolith fallback
            services.append(Service(
                name=context.project_name or "app",
                language=context.language,
                runtime_version="LTS",
                base_image="alpine",
                port=int(context.ports[0]) if context.ports else 3000,
                is_public=True
            ))
            
        return ProjectModel(
            project_name=context.project_name,
            services=services,
            environment=self.environment
        )

    def _run_integrity_audit(self, graph: ArchitectureGraph):
        # Implementation in Phase 3
        logger.info("🔍 Running Final Integrity Audit...")
        pass
