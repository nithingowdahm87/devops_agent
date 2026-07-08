from src.engine.models import GeneratedFile
from src.engine.llm import call_llm

class Healer:
    def __init__(self):
        self.prompt = self._load_prompt("configs/prompts/debug/healer.md")

    def _load_prompt(self, filepath: str) -> str:
        try:
            with open(filepath, "r") as f:
                return f.read()
        except FileNotFoundError:
            return "Fix the code to resolve the error. Minimal diff."

    def heal(self, file: GeneratedFile, errors: list[str]) -> GeneratedFile:
        print(f"🚑 Healing {file.path}...")
        error_str = "\n".join(errors)

        full_prompt = f"""
You are a Senior Patch Engineer.
Fix the broken file based on the validation errors provided.

RULES:
- Minimal changes only.
- Preserve existing formatting/style.
- Return the ENTIRE file as raw text.
- NO markdown blocks. NO backticks. NO explanations.

BROKEN FILE:
{file.content}

VALIDATION ERRORS:
{error_str}
"""
        # Uses heal-optimised routing: Gemini → Groq → Cerebras
        response = call_llm(self.prompt, full_prompt, task_type="heal")

        healed_content = response.strip()
        if healed_content.startswith("```"):
            lines = healed_content.splitlines()
            if len(lines) > 2:
                healed_content = "\n".join(lines[1:-1])

        return GeneratedFile(path=file.path, content=healed_content)


def heal_file(file: GeneratedFile, errors: list[str]) -> GeneratedFile:
    return Healer().heal(file, errors)