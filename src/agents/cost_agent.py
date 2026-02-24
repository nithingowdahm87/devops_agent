from src.engine.llm import call_llm
from src.tools.file_ops import read_file, write_file
import os
import logging

logger = logging.getLogger(__name__)

class CostEstimator:
    def __init__(self):
        pass
        
    def estimate(self, manifest_content: str) -> str:
        """
        Generates a cost estimate report based on the provided K8s manifests.
        """
        try:
            task = read_file("configs/prompts/cost/writer.md")
        except Exception:
            task = "Analyze these K8s manifests and estimate monthly cloud costs."
            
        prompt = f"{task}\n\nKUBERNETES MANIFESTS:\n{manifest_content}"
        return call_llm("", prompt, task_type="cost")

class CostExecutor:
    def run(self, content: str, project_path: str):
        directory = os.path.join(project_path, "cost")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "cost_estimate.md")
        write_file(path, content)
        print(f"💰 Wrote Cost Estimate to {path}")
