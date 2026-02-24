"""
Constitutional Critique — rewrites generated artifacts to comply with production rules.
Uses task_type='critique' routing so Claude/Gemini handle this (better at reasoning).
"""
from __future__ import annotations
import re, logging
from src.engine.models import GeneratedFile

log = logging.getLogger(__name__)

_RULES = {
    "docker": """
- Non-root user (UID >= 10001) in runtime stage
- No :latest tags — pin exact versions
- Multi-stage build (AS builder / AS runtime)
- No COPY . . — explicit paths only
- No secrets in ENV or COPY
- HEALTHCHECK present
- Exec-form CMD (JSON array)
- OCI LABEL block with ARG-injected values
""",
    "k8s": """
- resources.requests and resources.limits set on all containers
- securityContext: runAsNonRoot, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true
- All 3 probes: startupProbe, livenessProbe, readinessProbe
- No default ServiceAccount — dedicated SA with automountServiceAccountToken: false
- NetworkPolicy present with DNS egress (UDP+TCP 53)
- PDB with minAvailable: 1
- HPA using autoscaling/v2
- No NodePort, no hostNetwork, no privileged: true
""",
    "ci": """
- on: key is literally 'on:' — not 'true:'
- Every job starts with actions/checkout@v4
- No echo stubs — real tools: gitleaks, trivy-action, sonarcloud
- SARIF uploaded after every Trivy scan
- docker/login-action before docker/build-push-action
- concurrency: and permissions: at workflow level
- needs: at job level only — never inside steps
- Secrets table as YAML comments at bottom
""",
}


class Constitution:
    def __init__(self, llm_client=None):
        # llm_client kept for backward compat — routing now via call_llm()
        pass

    def critique(self, file: GeneratedFile, task_type: str) -> GeneratedFile:
        from src.engine.llm import call_llm

        rules = _RULES.get(task_type, "- Follow production-grade infrastructure best practices.")
        log.info("Constitutional critique → %s [task=%s]", file.path, task_type)

        system = (
            "You are a Senior DevSecOps Architect. "
            "Review the provided configuration strictly against the rules given. "
            "If it violates any rule, rewrite it to fully comply. "
            "If compliant, return it unchanged. "
            "Output ONLY the raw file content — no markdown, no backticks, no explanations."
        )
        user = f"""TASK TYPE: {task_type.upper()}

RULES TO ENFORCE:
{rules}

FILE TO REVIEW ({file.path}):
{file.content}
"""
        response = call_llm(system, user, task_type="critique")
        cleaned  = self._clean(response)
        return GeneratedFile(path=file.path, content=cleaned)

    @staticmethod
    def _clean(text: str) -> str:
        text = text.strip()
        if "```" in text:
            m = re.search(r"```(?:[\w]*)?\n(.*?)\n```", text, re.DOTALL)
            if m:
                return m.group(1).strip()
            lines = text.splitlines()
            if len(lines) > 0 and lines[0].startswith("```"):
                text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
        for noise in ["Explanation:", "Note:", "Review Result:", "Corporate Standards:"]:
            if noise in text:
                text = text.split(noise)[0]
        return text.strip()


def critique_file(file: GeneratedFile, task_type: str, llm_client=None) -> GeneratedFile:
    return Constitution().critique(file, task_type)
