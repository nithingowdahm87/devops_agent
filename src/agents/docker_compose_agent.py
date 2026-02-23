from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.nvidia_client import NvidiaClient
from src.tools.file_ops import read_file, write_file

class DockerComposeWriter:
    def __init__(self, client):
        self.llm = client
        self.ROLE = "DevOps Engineer"

    def generate(self, context_json: str) -> str:
        try:
            task = read_file("configs/prompts/compose/writer.md")
        except Exception:
            task = "Generate a docker-compose.yml."
            
        prompt = f"{task}\n\nAPPLICATION CONTEXT:\n{context_json}"
        return self.llm.call(prompt)

class ComposeReviewer:
    def __init__(self):
        self.llm = GeminiClient()
    def review_and_merge(self, yaml_a: str, yaml_b: str, yaml_c: str, validation_report: str = "") -> tuple[str, str]:
        feedback_section = ""
        if validation_report:
            feedback_section = f"""
        VALIDATION/USER FEEDBACK (MUST ADDRESS):
        {validation_report}
        """
        prompt = f"""
        You are a Senior DevOps Architect. Review 3 Docker Compose drafts.
        
        Draft A:
        {yaml_a}
        
        Draft B:
        {yaml_b}
        
        Draft C:
        {yaml_c}
        {feedback_section}
        TASK:
        1. Synthesize the BEST `docker-compose.yml`.
        2. Ensure all services (app + db/cache) are connected.
        3. Ensure ports match the application context.
        4. Address all feedback points if any.
        5. Explain reasoning.
        
        OUTPUT FORMAT:
        REASONING:
        - point 1
        - point 2
        
        YAML:
        ```yaml
        ...
        ```
        """
        response = self.llm.call(prompt)
        
        # Parse
        try:
            if "YAML:" in response:
                parts = response.split("YAML:")
                reasoning = parts[0].replace("REASONING:", "").strip()
                code = parts[1].replace("```yaml", "").replace("```", "").strip()
                return code, reasoning
            return response, "Parsing failed, return raw"
        except Exception: return yaml_a, "Error parsing"

class DockerComposeExecutor:
    def run(self, content: str, project_path: str):
        write_file(f"{project_path}/docker-compose.yml", content)
        print(f"✅ Wrote docker-compose.yml to {project_path}")
