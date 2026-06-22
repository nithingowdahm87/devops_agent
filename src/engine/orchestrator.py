import warnings
from src.engine.orchestrator_legacy import Orchestrator

warnings.warn(
    "src.engine.orchestrator is deprecated. Use src.decision_engine.orchestrator.V2Orchestrator instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Orchestrator"]
