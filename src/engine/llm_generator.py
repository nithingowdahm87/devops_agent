"""
LLMGenerator — top-level generation class.
Wires together: cache → multi-provider sampler → constitution critique.
Drop-in replacement for the LLMGenerator class in the old llm.py.
"""
from __future__ import annotations
import re, logging
from src.engine import cache as prompt_cache
from src.engine.sampler import Sampler
from src.engine.constitution import Constitution
from src.engine.models import GeneratedFile
from src.engine.llm import call_llm
from src.engine.rag import get_rag_context, save_to_rag

log = logging.getLogger(__name__)


class LLMGenerator:
    def __init__(self):
        self.sampler     = Sampler()
        self.constitution = Constitution(llm_client=None)
        self.system_prompt = self._load("configs/prompts/system/system_core.md")[:1200]

    def _load(self, path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _artifact_type_for_task(self, task_type: str) -> str:
        t = task_type.lower()
        if t in ("docker", "compose", "dockerfile"):
            return "docker"
        if t in ("k8s", "kubernetes", "manifest"):
            return "k8s"
        if t in ("ci", "cicd", "github_actions"):
            return "ci"
        return "docker"  # safe default

    def _task_prompt_core(self, task_type: str) -> str:
        """Very short, high-level instructions, not the entire long prompt."""
        return self._load({
            "docker": "configs/prompts/docker/docker_production.md",
            "k8s":    "configs/prompts/k8s/k8s_production.md",
            "ci":     "configs/prompts/cicd/cicd_production.md",
        }.get(task_type.lower(), ""))[:800]  # hard cap

    def _rag_best_practices(self, task_type: str, context: dict) -> str:
        artifact_type = self._artifact_type_for_task(task_type)
        # Build a natural language query using known fields from context
        lang  = context.get("language") or context.get("runtime") or "generic service"
        stack = context.get("stack") or context.get("deps") or ""
        query = f"Best practices for {artifact_type} targeting a {lang} service with stack {stack}"
        return get_rag_context(query=query, artifact_type=artifact_type)

    def generate(self, task_type: str, context: dict) -> list[GeneratedFile]:
        core_prompt = self._task_prompt_core(task_type)
        if not core_prompt:
            raise ValueError(f"Unknown task type: {task_type}")

        all_files: list[GeneratedFile] = []

        # ── Split context by service and call LLM once per service ───────────
        SECTION_KEYS = ["backend", "frontend", "database", "services"]
        service_chunks = [
            {k: context[k]} for k in SECTION_KEYS if k in context
        ]
        
        # If nested services list exists
        if "services" in context and isinstance(context["services"], list):
            service_chunks = context["services"]
            
        if not service_chunks:
            service_chunks = [context]  # single-pass fallback

        for svc in service_chunks:
            svc_name = svc.get("name", svc.get("service", "service"))
            if not isinstance(svc, dict):
                svc = {"data": svc}
                
            rag_tips = self._rag_best_practices(task_type, svc)
            context_str = "\n".join(f"{k}: {v}" for k, v in svc.items())

            user_prompt = (
                f"{core_prompt}\n\n"
                f"RAG BEST PRACTICES (retrieved knowledge):\n{rag_tips}\n\n"
                f"APPLICATION CONTEXT (service: {svc_name}):\n{context_str}"
            )

            cached = prompt_cache.get(self.system_prompt, user_prompt, task_type)
            if cached:
                log.info("Cache hit for service=%s task=%s", svc_name, task_type)
                all_files.extend(self._parse_files(cached))
                continue

            log.info("Generating for service=%s task=%s", svc_name, task_type)
            # ── Multi-provider consensus sampling for this service ────────────────────────
            candidates = self.sampler.sample(user_prompt, task_type=task_type)
            if not candidates:
                log.error("All providers failed for service=%s. Trying direct call fallback...", svc_name)
                # Fallback directly to call_llm if sampler fails (llama.cpp only has 1 provider)
                try:
                    res = call_llm(self.system_prompt, user_prompt, task_type=task_type)
                    candidates = [res]
                except Exception as e:
                    log.error("Fallback call_llm failed: %s", e)
                    continue

            if candidates:
                winner = candidates[0]
                files = self._parse_files(winner)
                
                critiqued_for_svc = []
                for f in files:
                    cf = self.constitution.critique(f, task_type)
                    all_files.append(cf)
                    critiqued_for_svc.append(cf)

                # RAG Self-improving feedback loop
                for f in critiqued_for_svc:
                    if f.path.endswith(("Dockerfile", ".yaml", ".yml", ".workflow")):
                        if "docker" in f.path.lower():
                            atype = "docker"
                        elif "k8s" in f.path.lower() or "deployment" in f.path.lower() or "manifest" in f.path.lower():
                            atype = "k8s"
                        else:
                            atype = "ci"
                        # Only index if it's reasonably long (means it's code, not error stub)
                        if len(f.content) > 50:
                            save_to_rag(artifact_type=atype, content=f.content, source=f"generated:{f.path}")

            final_text = "\n\n".join(
                f"FILENAME: {f.path}\n```\n{f.content}\n```" for f in all_files
            )
            prompt_cache.set(self.system_prompt, user_prompt, task_type, final_text)

        return all_files

    def _parse_files(self, response: str) -> list[GeneratedFile]:
        # Strip any leading reasoning text before the first FILENAME marker
        idx = response.find("FILENAME:")
        if idx > 0:
            response = response[idx:]

        files = []
        pattern = r"(?:###\s*)?FILENAME:\s*([^\s\n]+).*\n(?:```[\w]*\n)?(.*?)(?:```|$)"
        for m in re.finditer(pattern, response, re.DOTALL | re.IGNORECASE):
            path    = m.group(1).strip().replace("\\", "/").strip("/")
            content = m.group(2).strip().rstrip("`").strip()
            if path and content:
                files.append(GeneratedFile(path=path, content=content))

        if not files:
            for lang, block in re.findall(r"```(.*?)\n(.*?)```", response, re.DOTALL):
                name = lang.split(":")[-1].strip() if "." in lang else "generated_file"
                files.append(GeneratedFile(path=name, content=block.strip()))

        return files

# ── Module-level shortcut (backward compatible) ───────────────────────────────
def generate(task_type: str, context: dict) -> list[GeneratedFile]:
    return LLMGenerator().generate(task_type, context)
