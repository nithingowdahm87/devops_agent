"""
Multi-provider consensus sampler.
Sends the same prompt to 3 different providers concurrently.
Scores each candidate by how many validation rules it passes.
Returns the candidate with the highest score (best answer wins).
"""
from __future__ import annotations
import re, logging, concurrent.futures
from src.engine.llm import call_llm

log = logging.getLogger(__name__)

# Providers to run in parallel for consensus sampling.
# These 3 are the fastest free-tier providers.
_CONSENSUS_PROVIDERS = ["groq", "gemini", "cerebras"]

# ── Scoring — count how many production rules the candidate satisfies ─────────
_DOCKER_SIGNALS  = ["FROM", "AS builder", "AS runtime", "USER ", "HEALTHCHECK",
                    "WORKDIR", "LABEL org.opencontainers", "CMD ["]
_K8S_SIGNALS     = ["kind: Deployment", "readinessProbe", "livenessProbe",
                    "securityContext", "resources:", "limits:", "NetworkPolicy"]
_CI_SIGNALS      = ["actions/checkout", "trivy-action", "gitleaks", "upload-sarif",
                    "docker/build-push-action", "concurrency:", "permissions:"]
_SIGNAL_MAP      = {"docker": _DOCKER_SIGNALS, "k8s": _K8S_SIGNALS, "ci": _CI_SIGNALS}

def _score(text: str, task_type: str) -> int:
    signals = _SIGNAL_MAP.get(task_type, [])
    return sum(1 for s in signals if s in text)


class Sampler:
    def __init__(self, llm_client=None):
        # llm_client kept for backward compatibility — not used internally anymore
        pass

    def sample(self, prompt: str, task_type: str = "default") -> list[str]:
        """
        Fire 3 providers in parallel. Return all successful responses,
        sorted best-first by production signal score.
        """
        results: dict[str, str] = {}

        def _call(provider: str) -> tuple[str, str]:
            try:
                log.info("Consensus sample → %s", provider)
                # Override the provider order so this specific call uses only one provider
                import os
                env_backup = os.environ.get("LLM_PRIMARY")
                os.environ["LLM_PRIMARY"] = provider
                # Also set fallback to empty so it doesn't cascade
                fallback_backup = os.environ.get("LLM_FALLBACK_ORDER", "")
                os.environ["LLM_FALLBACK_ORDER"] = ""
                try:
                    result = call_llm("", prompt, task_type=task_type)
                finally:
                    if env_backup is not None:
                        os.environ["LLM_PRIMARY"] = env_backup
                    else:
                        os.environ.pop("LLM_PRIMARY", None)
                    os.environ["LLM_FALLBACK_ORDER"] = fallback_backup
                return provider, result
            except Exception as e:
                log.warning("Consensus sample failed for %s: %s", provider, e)
                return provider, ""

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_call, p): p for p in _CONSENSUS_PROVIDERS}
            for future in concurrent.futures.as_completed(futures, timeout=60):
                provider, text = future.result()
                if text.strip():
                    results[provider] = text

        if not results:
            log.error("All consensus providers returned empty results.")
            return []

        # Sort by score descending — highest rule coverage wins
        scored = sorted(results.values(), key=lambda t: _score(t, task_type), reverse=True)
        log.info(
            "Consensus scores: %s",
            {p: _score(t, task_type) for p, t in results.items()}
        )
        return scored
