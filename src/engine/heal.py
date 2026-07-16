from src.engine.models import GeneratedFile
from src.llm_clients.nvidia_client import NvidiaClient


class Healer:
    def __init__(self, client: NvidiaClient | None = None) -> None:
        self._client = client or NvidiaClient()
        self._system_prompt = self._load_prompt("configs/prompts/debug/healer.md")

    def _load_prompt(self, filepath: str) -> str:
        try:
            with open(filepath, "r") as f:
                return f.read()
        except FileNotFoundError:
            return "Fix the code to resolve the error. Minimal diff."

    def heal(self, file: GeneratedFile, errors: list[str]) -> GeneratedFile:
        print(f"🚑 Healing {file.path}...")
        error_str = "\n".join(errors)

        user_prompt = (
            "You are a Senior Patch Engineer.\n"
            "Fix the broken file based on the validation errors provided.\n\n"
            "RULES:\n"
            "- Minimal changes only.\n"
            "- Preserve existing formatting/style.\n"
            "- Return the ENTIRE file as raw text.\n"
            "- NO markdown blocks. NO backticks. NO explanations.\n\n"
            f"BROKEN FILE:\n{file.content}\n\n"
            f"VALIDATION ERRORS:\n{error_str}\n"
        )

        response = self._client.call(
            user_prompt,
            system_prompt=self._system_prompt,
            temperature=0.1,
        )

        healed_content = response.strip()
        if healed_content.startswith("```"):
            lines = healed_content.splitlines()
            if len(lines) > 2:
                healed_content = "\n".join(lines[1:-1])

        return GeneratedFile(path=file.path, content=healed_content)


def heal_file(file: GeneratedFile, errors: list[str]) -> GeneratedFile:
    return Healer().heal(file, errors)