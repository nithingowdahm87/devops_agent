# -*- coding: utf-8 -*-
import logging
from src.engine.models import GeneratedFile
from src.engine.config import MAX_HEAL_RETRIES
from src.engine.llm import call_llm
from src.engine.extractor import Extractor

logger = logging.getLogger("devops-agent")


class Healer:
    """
    Implements the OODA (Observe-Orient-Decide-Act) repair loop.
    Feeds precise validator errors back to the LLM for surgical fixes.
    Uses task_type='heal' routing: Gemini → Groq → Cerebras.
    """

    def __init__(self):
        # No client needed — call_llm handles routing
        pass

    def heal(self, file: GeneratedFile, errors: list[str], attempt: int = 1) -> GeneratedFile:
        if attempt > MAX_HEAL_RETRIES:
            logger.error("Healer exhausted retries (%d) for %s", MAX_HEAL_RETRIES, file.path)
            return file

        logger.info("🚑 Healing %s (Attempt %d/%d)...", file.path, attempt, MAX_HEAL_RETRIES)
        heal_prompt = self._build_heal_prompt(file, errors, attempt)

        try:
            response = call_llm("", heal_prompt, task_type="heal")

            if file.path.endswith((".yaml", ".yml")) or "docker-compose" in file.path:
                healed_content = Extractor.extract_yaml(response)
            else:
                healed_content = Extractor.extract_code_block(response)

            if healed_content:
                return GeneratedFile(path=file.path, content=healed_content)
            else:
                logger.warning("Healer returned empty content for %s", file.path)
                return file

        except Exception as e:
            logger.error("Healer LLM call failed: %s", e)
            return file

    def _build_heal_prompt(self, file: GeneratedFile, errors: list[str], attempt: int) -> str:
        error_str = "\n".join(f"- {e}" for e in errors)
        return f"""
You are a Senior DevOps Engineer. The following file has VALIDATION ERRORS.
Fix ONLY the lines causing these errors. Do not add unnecessary comments or prose.

FILE: {file.path}
ERRORS DETECTED:
{error_str}

CURRENT CONTENT:
{file.content}

text

Instructions:
1. Provide the FULL corrected file content.
2. Use the exact FILENAME: {file.path} header.
3. Ensure syntax is 100% correct according to standard schemas.
"""
