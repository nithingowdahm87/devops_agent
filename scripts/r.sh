#!/bin/bash

# 0. Cleanup Conflicts (Remove hidden .venv if standard venv exists)
if [ -d "venv" ] && [ -d ".venv" ]; then
    echo "Found both 'venv' and '.venv'. Removing conflict (.venv)..."
    rm -rf .venv
fi

# Ensure directory structure exists
mkdir -p src/llm_clients src/tools src/agents configs/guidelines

echo "--- Writing fixed Python files ---"

# 1. Fix Gemini Client
cat > src/llm_clients/gemini_client.py <<'EOF'
import os
from langchain_google_genai import ChatGoogleGenerativeAI

class GeminiClient:
    def __init__(self, model: str = "gemini-1.5-pro", temperature: float = 0.1):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable is not set")
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
        )

    def call(self, prompt: str) -> str:
        resp = self.llm.invoke(prompt)
        return resp.content if hasattr(resp, "content") else str(resp)
EOF

import os
import requests

    def __init__(self, model: str = "sonar", temperature: float = 0.1):
        if not token:
        self.token = token
        self.model = model
        self.temperature = temperature

    def call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"]
EOF

# 3. Fix GitHub Models Client
cat > src/llm_clients/github_models_client.py <<'EOF'
import os
import requests

class GitHubModelsClient:
    def __init__(self, model: str = "gpt-4o", temperature: float = 0.1):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN environment variable is not set")
        self.token = token
        self.model = model
        self.temperature = temperature
        self.base_url = "https://models.inference.ai.azure.com/openai/deployments/" + self.model + "/chat/completions?api-version=2024-02-01"

    def call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"]
EOF

# 4. Fix File Ops Tool
cat > src/tools/file_ops.py <<'EOF'
import os

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def scan_directory(path: str) -> str:
    entries = []
    for root, files in os.walk(path):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), path)
            entries.append(rel)
    entries.sort()
    return "\n".join(entries)
EOF

# 5. Fix Shell Tools
cat > src/tools/shell_tools.py <<'EOF'
import subprocess

def run_shell_command(cmd: str, cwd: str = ".") -> str:
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout
EOF

# 6. Fix Docker Agents
cat > src/agents/docker_agents.py <<'EOF'
from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.github_models_client import GitHubModelsClient
from src.tools.file_ops import read_file, scan_directory, write_file

class DockerWriterA:
    def __init__(self):
        self.llm = GeminiClient()
    
    def generate(self, app_path: str) -> str:
        tree = scan_directory(app_path)
        try:
            guidelines = read_file("configs/guidelines/docker-guidelines.md")
        except:
            guidelines = "No specific guidelines found."

        prompt = f"""
You are a senior DevOps engineer.
App directory tree:
{tree}
Guidelines:
{guidelines}
Write a production-ready Dockerfile for this app.
- Use multi-stage builds.
- Pin all image versions.
- Use non-root user.
- Set WORKDIR.
Return ONLY the Dockerfile text.
""".strip()
        return self.llm.call(prompt)

class DockerWriterB:
    def __init__(self):
        self.llm = GitHubModelsClient()
        
    def generate(self, app_path: str) -> str:
        tree = scan_directory(app_path)
        try:
            guidelines = read_file("configs/guidelines/docker-guidelines.md")
        except:
            guidelines = "No specific guidelines found."
            
        prompt = f"""
You are a security-focused DevOps engineer.
App directory tree:
{tree}
Guidelines:
{guidelines}
Write an alternative Dockerfile with:
- Minimal base image.
- Hardened runtime.
- No unnecessary packages.
Return ONLY the Dockerfile text.
""".strip()
        return self.llm.call(prompt)

class DockerReviewer:
    def review_and_merge(self, docker_a: str, docker_b: str) -> str:
        # Minimal deterministic reviewer logic
        a_ok = "FROM" in docker_a
        b_ok = "FROM" in docker_b
        
        if a_ok and not b_ok: return docker_a.strip() + "\n"
        if b_ok and not a_ok: return docker_b.strip() + "\n"
        # If both valid, prefer B (Security focused) or longer one
        return (docker_b if len(docker_b) > len(docker_a) else docker_a).strip() + "\n"

class DockerExecutor:
    def run(self, final_dockerfile: str, project_path: str, output_path: str = "Dockerfile") -> None:
        write_file(f"{project_path}/{output_path}", final_dockerfile)
        print(f"Wrote {output_path}. Next manual step:")
        print(f"  docker build -t myapp:local -f {project_path}/{output_path} {project_path}")
EOF

# 7. Fix K8s Agents
cat > src/agents/k8s_agents.py <<'EOF'
from src.llm_clients.gemini_client import GeminiClient
from src.llm_clients.github_models_client import GitHubModelsClient
from src.tools.file_ops import read_file, write_file

class K8sWriterA:
    def __init__(self):
        self.llm = GeminiClient()
        
    def generate(self, service_name: str) -> str:
        try:
            guidelines = read_file("configs/guidelines/k8s-guidelines.md")
        except:
            guidelines = "No specific guidelines."
            
        prompt = f"""
You are a Kubernetes expert.
Service name: {service_name}
Guidelines:
{guidelines}
Write Kubernetes manifests (Deployment + Service) for this service.
Return ONLY YAML (one or more documents), no explanation.
""".strip()
        return self.llm.call(prompt)

class K8sWriterB:
    def __init__(self):
        self.llm = GitHubModelsClient()
        
    def generate(self, service_name: str) -> str:
        try:
            guidelines = read_file("configs/guidelines/k8s-guidelines.md")
        except:
            guidelines = "No specific guidelines."
            
        prompt = f"""
You are a security-focused Kubernetes engineer.
Service name: {service_name}
Guidelines:
{guidelines}
Write alternative manifests with:
- Strong Pod security.
- Explicit requests and limits.
Return ONLY YAML.
""".strip()
        return self.llm.call(prompt)

class K8sReviewer:
    def review_and_merge(self, yaml_a: str, yaml_b: str) -> str:
        a_ok = "apiVersion" in yaml_a
        b_ok = "apiVersion" in yaml_b
        
        if a_ok and not b_ok: return yaml_a.strip() + "\n"
        if b_ok and not a_ok: return yaml_b.strip() + "\n"
        return (yaml_b if len(yaml_b) > len(yaml_a) else yaml_a).strip() + "\n"

class K8sExecutor:
    def run(self, final_yaml: str, output_path: str) -> None:
        write_file(output_path, final_yaml)
        print(f"Wrote {output_path}. Next manual step:")
        print(f"  kubectl apply -f {output_path}")
EOF

# 8. Fix Prompt Improvement Agent
cat > src/agents/prompt_improvement_agent.py <<'EOF'
from src.tools.file_ops import read_file

class PromptImprover:
    def __init__(self):
        
    def improve(self, original: str, domain: str) -> str:
        guidelines_path = f"configs/guidelines/{domain}-guidelines.md"
        try:
            guidelines = read_file(guidelines_path)
        except FileNotFoundError:
            guidelines = ""
            
        prompt = f"""
You are an expert prompt engineer for DevOps.
Domain: {domain}
Guidelines:
{guidelines}
Original prompt:
{original}
Rewrite the prompt to:
- Be more explicit and precise.
- Include relevant DevOps best practices.
Return ONLY the improved prompt.
""".strip()
        return self.llm.call(prompt)
EOF

# 9. Fix Main CLI
cat > main.py <<'EOF'
from src.agents.docker_agents import DockerWriterA, DockerWriterB, DockerReviewer, DockerExecutor
from src.agents.k8s_agents import K8sWriterA, K8sWriterB, K8sReviewer, K8sExecutor
from src.agents.prompt_improvement_agent import PromptImprover

def run_docker_flow() -> None:
    project_path = input("Enter app project path (absolute or relative): ").strip()
    output_path = input("Enter output filename (default: Dockerfile): ").strip() or "Dockerfile"
    
    writer_a = DockerWriterA()
    writer_b = DockerWriterB()
    reviewer = DockerReviewer()
    executor = DockerExecutor()
    
    print("Generating Dockerfile A (Gemini)...")
    docker_a = writer_a.generate(project_path)
    
    print("Generating Dockerfile B (GitHub Models)...")
    docker_b = writer_b.generate(project_path)
    
    print("Reviewing + selecting final Dockerfile...")
    final_docker = reviewer.review_and_merge(docker_a, docker_b)
    
    executor.run(final_docker, project_path, output_path=output_path)

def run_k8s_flow() -> None:
    service_name = input("Enter Kubernetes service name: ").strip()
    output_path = input("Enter output YAML path (e.g., k8s-all.yaml): ").strip() or "k8s-manifests.yaml"
    
    writer_a = K8sWriterA()
    writer_b = K8sWriterB()
    reviewer = K8sReviewer()
    executor = K8sExecutor()
    
    print("Generating YAML A (Gemini)...")
    yaml_a = writer_a.generate(service_name)
    
    print("Generating YAML B (GitHub Models)...")
    yaml_b = writer_b.generate(service_name)
    
    print("Reviewing + selecting final YAML...")
    final_yaml = reviewer.review_and_merge(yaml_a, yaml_b)
    
    executor.run(final_yaml, output_path)

def run_prompt_improve() -> None:
    domain = input("Enter domain (docker/k8s/ci/terraform/shell/test): ").strip()
    print("Paste original prompt. End with a blank line:")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    original = "\n".join(lines)
    
    improver = PromptImprover()
    improved = improver.improve(original, domain)
    
    print("\n--- Improved prompt ---\n")
    print(improved)

def main() -> None:
    while True:
        print("\nChoose action:")
        print("1) Docker flow (2 writers + reviewer + executor)")
        print("2) K8s flow (2 writers + reviewer + executor)")
        print("4) Exit")
        choice = input("Enter choice: ").strip()
        
        if choice == "1":
            run_docker_flow()
        elif choice == "2":
            run_k8s_flow()
        elif choice == "3":
            run_prompt_improve()
        elif choice == "4":
            return
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
EOF

echo "--- All files fixed successfully! ---"
echo "Run: python3 main.py"
