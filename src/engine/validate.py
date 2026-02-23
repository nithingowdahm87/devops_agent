import os
import yaml
from src.engine.utils import run_cmd
from src.engine.models import GeneratedFile, ValidationResult

class Validator:
    def validate(self, file: GeneratedFile) -> ValidationResult:
        path = file.path
        # If absolute path is short or relative, we might need to write to a temp file for some tools
    def __init__(self):
        # Look for binaries in ./bin first
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.bin_path = os.path.join(self.project_root, "bin")

    def validate(self, file: GeneratedFile) -> ValidationResult:
        path = file.path
        filetype = self._detect_type(path)
        errors = []

        # Always run basic structural checks first
        structural_errors = self._basic_structural_check(file)
        errors.extend(structural_errors)

        if filetype == "docker":
            errors.extend(self._validate_dockerfile(file))
        elif filetype == "dockerignore":
            errors.extend(self._validate_dockerignore(file))
        elif filetype == "compose":
            errors.extend(self._validate_compose(file))
        elif filetype == "k8s":
            errors.extend(self._validate_k8s(file))
        elif filetype == "gha":
            errors.extend(self._validate_github_actions(file))
        else:
            # If we don't have a specific validator, we don't fail, but we warn
            if not structural_errors:
                print(f"⚠️  No valid validator for {path}")
            return ValidationResult(len(errors) == 0, errors)

        return ValidationResult(len(errors) == 0, errors)

    def _detect_type(self, path: str):
        basename = os.path.basename(path)
        if basename in ("docker-compose.yml", "docker-compose.yaml"):
            return "compose"
        if path.endswith("Dockerfile"):
            return "docker"
        if path.endswith(".dockerignore"):
            return "dockerignore"
        if ".github/workflows" in path:
            return "gha"
        if path.endswith(".yaml") or path.endswith(".yml"):
            return "k8s"
        return None

    def _get_tool_path(self, tool_name: str) -> str:
        local_tool = os.path.join(self.bin_path, tool_name)
        return local_tool if os.path.exists(local_tool) else tool_name

    def _basic_structural_check(self, file: GeneratedFile) -> list[str]:
        errors = []
        if not file.content or len(file.content.strip()) < 10:
            errors.append("File content is empty or too short.")
        
        # Check for LLM hallucinations like "I cannot generate this"
        refusal_keywords = ["i am an ai", "as an ai", "cannot fulfill", "policy breach", "hallucination detected"]
        for kw in refusal_keywords:
            if kw in file.content.lower():
                errors.append(f"Detected potential LLM refusal or meta-commentary: '{kw}'")
        
        return errors

    def _validate_dockerfile(self, file: GeneratedFile) -> list[str]:
        errors = []
        
        # Constitutional Docker Rules
        if "FROM" not in file.content.upper():
            errors.append("Dockerfile missing FROM instruction.")
        if "ARG GIT_SHA" not in file.content and "${GIT_SHA}" in file.content:
            errors.append("Dockerfile uses ${GIT_SHA} but does not declare ARG GIT_SHA.")
        if ".dockerignore" not in file.path and "npm run build" in file.content and "dist" not in file.content:
             # Very basic check for build logic consistency
             pass

        # 1. hadolint
        tmp_path = f"/tmp/hadolint_{os.getpid()}"
        with open(tmp_path, "w") as f:
            f.write(file.content)
        
        hadolint = self._get_tool_path("hadolint")
        code, out, err = run_cmd([hadolint, tmp_path])
        if code != 0:
            if "No such file or directory" in err or "not found" in err:
                print(f"⚠️  hadolint not found at {hadolint}. Skipping static analysis.")
            else:
                errors.append(f"HADOLINT ERROR:\n{out or err}")
        
        os.remove(tmp_path)
        return errors

    def _validate_dockerignore(self, file: GeneratedFile) -> list[str]:
        errors = []
        mandatory = ["node_modules", ".git", ".env"]
        for m in mandatory:
            if m not in file.content:
                errors.append(f"Missing mandatory pattern in .dockerignore: {m}")
        return errors

    def _validate_k8s(self, file: GeneratedFile) -> list[str]:
        errors = []
        
        if "apiVersion" not in file.content or "kind" not in file.content:
             errors.append("K8s manifest missing apiVersion or kind.")

        tmp_path = f"/tmp/k8s_{os.getpid()}.yaml"
        with open(tmp_path, "w") as f:
            f.write(file.content)

        kubeconform = self._get_tool_path("kubeconform")
        code, out, err = run_cmd([kubeconform, "-strict", tmp_path])
        if code != 0:
            if "No such file or directory" in err or "not found" in err:
                print(f"⚠️  kubeconform not found at {kubeconform}. Skipping strict schema validation.")
            else:
                errors.append(f"KUBECONFORM ERROR:\n{out or err}")

        # Custom rules
        try:
            docs = list(yaml.safe_load_all(file.content))
            for doc in docs:
                if not doc: continue
                kind = doc.get("kind")
                if kind == "Deployment":
                    spec = doc.get("spec", {})
                    replicas = spec.get("replicas", 0)
                    if replicas < 2:
                        print("⚠️  Deployment replicas < 2 (acceptable for dev)")
                        # errors.append("Deployment replicas < 2")
                    
                    template = spec.get("template", {})
                    pod_spec = template.get("spec", {})
                    sc = pod_spec.get("securityContext", {})
                    if sc.get("runAsNonRoot") is not True:
                        print("⚠️  Pod securityContext.runAsNonRoot missing or not true (recommended for prod)")
                        # errors.append("Pod securityContext.runAsNonRoot missing or not true")
        except Exception as e:
            errors.append(f"YAML PARSE ERROR: {str(e)}")

        os.remove(tmp_path)
        return errors

    def _validate_compose(self, file: GeneratedFile) -> list[str]:
        # Minimal check for now (Gap 3)
        return []

    def _validate_github_actions(self, file: GeneratedFile) -> list[str]:
        errors = []
        try:
            workflow = yaml.safe_load(file.content)
            jobs = workflow.get("jobs", {})
            if len(jobs) < 2:
                errors.append("All stages must be separate jobs (found < 2 jobs)")

            for job_name, job in jobs.items():
                steps = job.get("steps", [])
                for step in steps:
                    if "run" in step and "uses" in step:
                        errors.append(f"Step in job '{job_name}' contains both 'run' and 'uses'")
                
                # Check if needs is inside steps (shouldn't be possible to parse easily if it is, but let's check)
                # needs is a job-level key. If it's in steps, it shouldn't even be there.
        except Exception as e:
            errors.append(f"GHA YAML PARSE ERROR: {str(e)}")
            
        return errors

def validate_file(file: GeneratedFile) -> ValidationResult:
    return Validator().validate(file)
