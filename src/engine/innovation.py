import concurrent.futures
from src.engine.llm import call_llm
from src.engine.rag import save_to_rag


class InnovationFlywheel:
    def _ask_advisory(self, persona: str, prompt: str) -> str:
        try:
            print(f"  [>] Innovation Layer ({persona}): Analyzing...")
            # Uses default routing — Groq/Cerebras handle this fast
            return call_llm("", prompt, task_type="default")
        except Exception as e:
            print(f"  [!] Innovation Layer failed for {persona}: {e}")
            return ""

    def run_async(self, artifact_content: str, artifact_type: str, original_prompt: str):
        print(f"  [>] Starting Async Innovation Flywheel for {artifact_type}...")

        prompts = [
            ("Modernization", f"You are a DevOps architect. Review this {artifact_type} and suggest modern API replacements or patterns for 2026. Be concise. File:\n{artifact_content}"),
            ("Performance",   f"You are a DevOps architect. Review this {artifact_type} and suggest performance improvements or caching strategies. Be concise. File:\n{artifact_content}"),
            ("Security",      f"You are a DevOps architect. Review this {artifact_type} and identify subtle security gaps or hardening opportunities. Be concise. File:\n{artifact_content}"),
        ]

        suggestions = []
        for persona, p in prompts:
            res = self._ask_advisory(persona, p)
            if res.strip():
                suggestions.append(f"[{persona} Advisory]:\n{res}")

        if suggestions:
            combined = "\n\n".join(suggestions)
            save_to_rag(artifact_type, combined, source=f"innovation_flywheel_{artifact_type}")
            print(f"  [+] Saved {len(suggestions)} innovation advisories to RAG.")


def run_innovation_async(artifact_content: str, artifact_type: str, original_prompt: str):
    flywheel = InnovationFlywheel()
    flywheel.run_async(artifact_content, artifact_type, original_prompt)
