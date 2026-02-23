from src.schemas import ProjectContext
from src.decision_engine.contracts.architecture_plan import ArchitecturePlan
from .rules import detect_service_type, determine_scaling, needs_database, needs_cache

class ArchitecturePlanner:
    def create_plan(self, context: ProjectContext) -> ArchitecturePlan:
        """
        Analyze the project context and generate a high-level architecture plan.
        This plan will guide all subsequent generation steps.
        """
        service_type = detect_service_type(context)
        scaling = determine_scaling(service_type)
        has_db = needs_database(context)
        has_cache = needs_cache(context)
        
        # Determine public exposure
        # APIs usually need ingress, Workers do not.
        public_exposure = (service_type in ["api", "monolith"])
        
        # Deployment strategy
        # Postgres/Monoliths often need Recreate to avoid locking issues or simpler migration checks?
        # But Rolling is standard for stateless.
        deployment = "rolling" 
        
        return ArchitecturePlan(
            service_type=service_type,
            scaling_strategy=scaling,
            public_exposure=public_exposure,
            requires_cache=has_cache,
            requires_queue=(service_type == "worker"),
            requires_database=has_db,
            requires_reverse_proxy=public_exposure, # Default Nginx for public exposure
            deployment_strategy=deployment,
            observability_level="standard",
            detected_framework=context.frameworks[0] if context.frameworks else "unknown",
            suggested_base_image=f"{context.language}-slim" # simplistic default
        )
