import os
import json
from src.tools.file_ops import read_file, write_file
from src.llm_clients.gemini_client import GeminiClient

class GuidelinesComplianceAgent:
    def __init__(self):
        self.llm = GeminiClient()

    def analyze_and_update(self, reasoning: str, guidelines_path: str) -> dict:
        """
        Analyzes reasoning against existing guidelines and updates the file
        ONLY if 'UNIVERSAL' best practices are found.
        """
        
        # 1. Read existing guidelines
        if os.path.exists(guidelines_path):
            current_guidelines = read_file(guidelines_path)
        else:
            current_guidelines = "No guidelines yet."

        # 2. Extract potential rules and classify them (The Quality Gate)
        prompt = f"""
        You are a DevOps Governance Architect.
        
        Analyze the following reasoning from a recent code generation task.
        Extract distinct "Best Practices" and CLASSIFY them.
        
        Input Reasoning:
        {reasoning}
        
        Current Guidelines:
        {current_guidelines}
        
        TASK:
        1. Identify new best practices not currently in the guidelines.
        2. Classify each as:
           - "UNIVERSAL": A rule that applies to 99% of projects (e.g., "Use multi-stage builds").
           - "CONTEXT": A rule specific to this specific app/framework (e.g., "Install libpng for this image").
        
        OUTPUT JSON ONLY:
        {{
            "new_practices": [
                {{ "rule": "Use npm ci for deterministic installs", "type": "UNIVERSAL" }},
                {{ "rule": "Install curl for healthcheck", "type": "CONTEXT" }}
            ]
        }}
        """
        
        try:
            response = self.llm.call(prompt)
            # Find JSON block if wrapped
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
                
            data = json.loads(response)
            
            new_practices = data.get("new_practices", [])
            
            # 3. Filter for UNIVERSAL rules only (The Gate)
            universal_rules = [p['rule'] for p in new_practices if p['type'] == 'UNIVERSAL']
            
            # 4. Update file if needed
            if universal_rules:
                updated_content = current_guidelines.strip() + "\n"
                for rule in universal_rules:
                    updated_content += f"- {rule}\n"
                
                write_file(guidelines_path, updated_content)
                
                return {
                    "new_practices_found": True,
                    "added_points": universal_rules,
                    "all_extracted": new_practices # Return all for debug visibility
                }
            
            return {
                "new_practices_found": False,
                "added_points": [],
                "all_extracted": new_practices
            }

        except Exception as e:
            print(f"Compliance Agent Error: {e}")
            return {"new_practices_found": False, "added_points": []}
