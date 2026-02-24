from typing import Any, Dict
from src.decision_engine.contracts.infra_spec import InfraSpec
from src.utils.prompt_loader import render_prompt

class LLMGenerator:
    def __init__(self, client: Any, model_name: str):
        self.client = client
        self.model_name = model_name
        
    def generate(self, prompt_template: str, context: Dict[str, Any]) -> InfraSpec:
        """
        Render prompt with context, call LLM, and return InfraSpec.
        """
        # 1. Render Prompt
        full_prompt = render_prompt(prompt_template, context)
        
        # 2. Call LLM
        try:
            raw_response = self.client.call(full_prompt)
        except Exception as e:
            # If call fails even after retries, return empty or error spec
            return InfraSpec(
                file_content="", 
                model_name=self.model_name,
                violations=[f"Generation failed: {str(e)}"]
            )
            
        # 3. Clean Output (Strip Markdown)
        cleaned_content = self._clean_markdown(raw_response)
        
        # 4. Return Spec
        return InfraSpec(
            file_content=cleaned_content,
            model_name=self.model_name
            # Scores are 0 by default, to be filled by Scorer
        )
        
    def _clean_markdown(self, info: str) -> str:
        # P0: if this is a multi-file response, do NOT strip code blocks
        if isinstance(info, list):
            info = "\n".join([str(i) for i in info])
        if "FILENAME:" in info:
            return info.strip()


        # Remove code blocks
        if "```" in info:
            lines = info.split("\n")
            cleaned_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block # Toggle
                    continue
                # If we assume the WHOLE response is the code inside block:
                # But sometimes there is text before/after.
                # Heuristic: If we are in a block, keep it. 
                # If NOT in a block, discard? 
                # Or output everything inside the FIRST block found?
                pass
            
            # Simple approach: Regex or just split
            # Many LLMs output: "Here is the code:\n```yaml\n...\n```"
            import re
            match = re.search(r"```(?:\w+)?\n(.*?)```", info, re.DOTALL)
            if match:
                return match.group(1).strip()
                
            # Fallback: remove all ```
            return info.replace("```yaml", "").replace("```dockerfile", "").replace("```json", "").replace("```", "").strip()
            
        return info.strip()
