from src.tools.file_ops import read_file, write_file
from src.engine.llm import call_llm
import os

class ObservabilityWriterA:
    def __init__(self):
        pass
        
    def generate(self, context: str) -> str:
        prompt = f"""
        You are a Site Reliability Engineer (SRE).
        PROJECT CONTEXT:
        {context}
        
        Task: Create a Helm Chart.yaml for specialized observability.
        Requirements:
        - Include Prometheus for metrics.
        - Include Loki for logs.
        - Include Grafana for visualization.
        - Set appropriate versions.
        
        Return ONLY the YAML content for Chart.yaml.
        """.strip()
        return call_llm("", prompt, task_type="observability")

    def generate_dashboard(self, context: str) -> str:
        try:
            task = read_file("configs/prompts/observability/writer.md")
        except Exception:
            task = "Generate a Grafana Dashboard JSON."
            
        prompt = f"{task}\n\nCONTEXT:\n{context}\n\nGenerate DASHBOARD JSON."
        return call_llm("", prompt, task_type="observability")

class ObservabilityWriterB:
    def __init__(self):
        pass
    def generate(self, context: str) -> str:
        prompt = f"""
        You are a SecOps Engineer.
        PROJECT CONTEXT:
        {context}
        
        Task: Create a secure Helm Chart.yaml for monitoring.
        Requirements:
        - Use hardened images for Prometheus/Grafana.
        - Enable persistence.
        - Add dependency on kube-state-metrics.
        
        Return ONLY the YAML content for Chart.yaml.
        """.strip()
        return call_llm("", prompt, task_type="observability")

    def generate_dashboard(self, context: str) -> str:
        try:
            task = read_file("configs/prompts/observability/writer.md")
        except Exception:
            task = "Generate a Grafana Dashboard JSON."
            
        prompt = f"{task}\n\nCONTEXT:\n{context}\n\nGenerate DASHBOARD JSON."
        return call_llm("", prompt, task_type="observability")

class ObservabilityWriterC:
    def __init__(self):
        pass
        
    def generate(self, context: str) -> str:
        prompt = f"""
        You are a Performance Engineer.
        PROJECT CONTEXT:
        {context}
        
        Task: Create a lightweight Helm Chart.yaml for monitoring.
        Requirements:
        - Minimal resource footprint.
        - Use VictoriaMetrics instead of Prometheus if possible (or optimized Prometheus).
        - Essential metrics only.
        
        Return ONLY the YAML content for Chart.yaml.
        """.strip()
        return call_llm("", prompt, task_type="observability")

    def generate_dashboard(self, context: str = "") -> str:
        prompt = f"""
        You are a Full Stack Engineer.
        PROJECT CONTEXT:
        {context}
        
        Generate a Grafana Dashboard JSON model.
        - Include Frontend metrics (Core Web Vitals) if frontend detected.
        - Include Backend metrics (Throughput, P99 Latency).
        
        Return ONLY valid JSON.
        """.strip()
        resp = call_llm("", prompt, task_type="observability")
        return resp.replace("```json", "").replace("```", "").strip()

class ObservabilityReviewer:
    def __init__(self):
        pass
    def review_and_merge(self, a: str, b: str, c: str, validation_report: str = "") -> tuple[str, str]:
        # Simple heuristic: if input looks like JSON, assume Dashboard review.
        is_dashboard = a.strip().startswith("{") or b.strip().startswith("{")
        
        item_type = "Grafana Dashboard JSON" if is_dashboard else "Helm Chart definition"
        
        feedback_section = ""
        if validation_report:
            feedback_section = f"""
    VALIDATION/USER FEEDBACK (MUST ADDRESS):
    {validation_report}
    """
        prompt = f"""
        You are a Lead SRE Architect. Review 3 {item_type}s.
        
        Draft A:
        {a}
        
        Draft B:
        {b}
        
        Draft C:
        {c}
        {feedback_section}
        TASK:
        1. Synthesize the BEST {item_type}.
        2. Ensure high quality and correctness.
        3. Address all feedback points if any.
        4. Explain reasoning.
        
        OUTPUT FORMAT:
        REASONING:
        - point 1
        - point 2
        
        CONTENT:
        {'{' if is_dashboard else '```yaml'}
        ...
        {'}' if is_dashboard else '```'}
        """.strip()
        
        response = call_llm("", prompt, task_type="observability")
        try:
            if "CONTENT:" in response:
                parts = response.split("CONTENT:")
                return (parts[1].replace("```yaml", "").replace("```json", "").replace("```", "").strip(), parts[0].replace("REASONING:", "").strip())
            return (response, "AI Review Completed")
        except Exception: return (a, "Fallback to Draft A (Review Failed)")

class ObservabilityExecutor:
    def run(self, content: str, project_path: str):
        # Determine if it's JSON (Dashboard) or YAML (Helm)
        if content.strip().startswith("{"):
            directory = os.path.join(project_path, "k8s", "dashboards")
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "dashboard.json")
            write_file(path, content)
            print(f"✅ Wrote Grafana Dashboard to {path}")
        else:
            directory = os.path.join(project_path, "helm", "monitoring")
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "Chart.yaml")
            write_file(path, content)
            print(f"✅ Wrote Helm Chart to {path}")
