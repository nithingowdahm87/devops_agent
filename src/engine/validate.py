import os
import yaml
from src.engine.utils import run_cmd
from src.engine.models import GeneratedFile, ValidationResult


class Validator:
    def __init__(self):
        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.bin_path = os.path.join(self.project_root, "bin")

    def validate(self, file: GeneratedFile) -> ValidationResult:
        path = file.path
        filetype = self._detect_type(path)
        errors = []

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

    def _basic_structural_check(self, file: GeneratedFile) -> list:
        errors = []
        if not file.content or len(file.content.strip()) < 10:
            errors.append("File content is empty or too short.")
        refusal_keywords = [
            "i am an ai", "as an ai", "cannot fulfill",
            "policy breach", "hallucination detected",
        ]
        for kw in refusal_keywords:
            if kw in file.content.lower():
                errors.append(f"Detected potential LLM refusal: '{kw}'")
        return errors

    def _validate_dockerfile(self, file: GeneratedFile) -> list:
        errors = []
        if "FROM" not in file.content.upper():
            errors.append("Dockerfile missing FROM instruction.")
        if "ARG GIT_SHA" not in file.content and "${GIT_SHA}" in file.content:
            errors.append("Dockerfile uses ${GIT_SHA} but does not declare ARG GIT_SHA.")

        tmp_path = f"/tmp/hadolint_{os.getpid()}"
        with open(tmp_path, "w") as f:
            f.write(file.content)

        hadolint = self._get_tool_path("hadolint")
        code, out, err = run_cmd([hadolint, tmp_path])
        if code != 0:
            if "No such file or directory" in err or "not found" in err:
                print(f"⚠️  hadolint not found at {hadolint}. Skipping.")
            else:
                errors.append(f"HADOLINT ERROR:\n{out or err}")
        os.remove(tmp_path)
        return errors

    def _validate_dockerignore(self, file: GeneratedFile) -> list:
        errors = []
        for m in ["node_modules", ".git", ".env"]:
            if m not in file.content:
                errors.append(f"Missing mandatory pattern in .dockerignore: {m}")
        return errors

    def _validate_k8s(self, file: GeneratedFile) -> list:
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
                print(f"⚠️  kubeconform not found. Skipping strict schema validation.")
            else:
                errors.append(f"KUBECONFORM ERROR:\n{out or err}")

        # internal schema validation for Argo and GitOps
        try:
            import json
            from jsonschema import validate as json_validate
            docs = list(yaml.safe_load_all(file.content))
            for doc in docs:
                if not doc: continue
                schema_name = None
                kind = doc.get("kind")

                # Check path & kind for ArgoCD
                if kind == "ApplicationSet" or "argocd/applicationset.yaml" in file.path.lower():
                    schema_name = "argocd-appset.schema.json"
                elif kind == "Application":
                    schema_name = "argocd-app.schema.json"

                if schema_name:
                    schema_path = os.path.join(self.project_root, "configs", "schemas", schema_name)
                    if os.path.exists(schema_path):
                        with open(schema_path, "r") as sf:
                            schema = json.load(sf)
                        try:
                            json_validate(instance=doc, schema=schema)
                        except Exception as ve:
                            errors.append(f"Argo {kind or 'GitOps'} Schema Violation: {str(ve)}")
        except ImportError:
            pass # jsonschema not installed
        except Exception as e:
            logger.warning(f"Internal Argo validation failed: {e}")

        try:
            docs = list(yaml.safe_load_all(file.content))
            for doc in docs:
                if not doc:
                    continue
                kind = doc.get("kind")
                if kind == "Deployment":
                    spec = doc.get("spec", {})
                    if spec.get("replicas", 0) < 2:
                        print("⚠️  Deployment replicas < 2 (acceptable for dev)")
                    sc = spec.get("template", {}).get("spec", {}).get("securityContext", {})
                    if sc.get("runAsNonRoot") is not True:
                        print("⚠️  Pod securityContext.runAsNonRoot not set (recommended for prod)")

                if kind == "HorizontalPodAutoscaler":
                    hpa_spec = doc.get("spec", {})
                    if "scaleTargetRef" not in hpa_spec:
                        errors.append(
                            f"HPA '{doc.get('metadata', {}).get('name', '?')}' "
                            "missing spec.scaleTargetRef."
                        )
                    if "selector" in hpa_spec:
                        errors.append(
                            f"HPA '{doc.get('metadata', {}).get('name', '?')}' "
                            "has invalid 'selector' in spec root — use scaleTargetRef instead."
                        )
        except Exception as e:
            errors.append(f"YAML PARSE ERROR: {str(e)}")

        os.remove(tmp_path)
        return errors

    def _validate_compose(self, file: GeneratedFile) -> list:
        errors = []
        try:
            doc = yaml.safe_load(file.content)
            if not doc:
                errors.append("docker-compose.yml is empty.")
                return errors
            services = doc.get("services", {})
            if not services:
                errors.append("docker-compose.yml has no services defined.")
            for svc_name, svc in (services or {}).items():
                if not svc:
                    continue
                if "image" not in svc and "build" not in svc:
                    errors.append(
                        f"Service '{svc_name}' has neither 'image' nor 'build' key."
                    )
        except Exception as e:
            errors.append(f"docker-compose YAML PARSE ERROR: {str(e)}")
        return errors

    def _validate_github_actions(self, file: GeneratedFile) -> list:
        errors = []
        try:
            workflow = yaml.safe_load(file.content)
            if not workflow:
                errors.append("GitHub Actions workflow is empty.")
                return errors

            # Optional JSON schema validation (keeps it aligned with configs/schemas/github-actions.schema.json)
            import json
            from jsonschema import validate as json_validate  # type: ignore[import]

            schema_path = os.path.join(
                self.project_root,
                "configs",
                "schemas",
                "github-actions.schema.json",
            )
            if os.path.exists(schema_path):
                with open(schema_path, "r") as sf:
                    schema = json.load(sf)
                try:
                    json_validate(instance=workflow, schema=schema)
                except Exception as ve:
                    errors.append(f"GHA Schema Violation: {str(ve)}")

            # Lightweight structural checks
            jobs = workflow.get("jobs", {})
            if not jobs:
                errors.append("Workflow must define at least one job under 'jobs'.")
                return errors

            for job_name, job in jobs.items():
                if not job:
                    continue
                steps = job.get("steps", [])
                if not steps:
                    errors.append(f"Job '{job_name}' has no steps defined.")
                    continue
                for step in steps:
                    # Hard rule: a single step cannot have both 'run' and 'uses'
                    if "run" in step and "uses" in step:
                        errors.append(
                            f"Step in job '{job_name}' contains both 'run' and 'uses'."
                        )

        except Exception as e:
            errors.append(f"GHA YAML PARSE ERROR: {str(e)}")

        return errors


def validate_file(file: GeneratedFile) -> ValidationResult:
    return Validator().validate(file)