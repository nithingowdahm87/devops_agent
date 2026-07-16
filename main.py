# -*- coding: utf-8 -*-
import os
import sys
import io
import argparse
import shutil

# Enforce UTF-8 for stdout and stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.entrypoints.cli_main import run_cli


def main():
    parser = argparse.ArgumentParser(description="DevOps AI Agent Pipeline v2.0.0")
    parser.add_argument("--env", type=str, choices=["dev", "staging", "prod"], default="dev",
                        help="Target environment (dev/staging/prod). Controls resource profiles and policy strictness.")
    parser.add_argument("--strict", action="store_true", help="Enable strict policy mode")
    parser.add_argument("--service", type=str, help="Target a specific microservice only")
    parser.add_argument("--no-prompts", action="store_true", help="Run fully non-interactive")
    parser.add_argument("--no-heal", action="store_true", help="Skip automated healing/validation retries")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Render and validate artifacts; log to stdout but write nothing. "
                             "Exits non-zero on policy violations. Safe for CI preview runs.")
    parser.add_argument("--health", action="store_true",
                        help="Check all dependencies (hadolint, kubeconform, opa, NVIDIA API) and exit.")
    parser.add_argument("path", type=str, nargs="?", help="Project path")

    args = parser.parse_args()

    if args.health:
        sys.exit(_run_health_check())

    run_cli(args)


def _run_health_check() -> int:
    import requests

    checks: dict[str, bool] = {}

    for binary in ["hadolint", "kubeconform", "opa", "helm"]:
        checks[binary] = shutil.which(binary) is not None

    checks["configs/prompts"] = os.path.isdir("configs/prompts")
    checks["resource_profiles"] = os.path.exists("configs/resource_profiles.yaml")
    checks["nvidia_api_key_set"] = bool(os.getenv("NVIDIA_API_KEY"))

    try:
        r = requests.head("https://integrate.api.nvidia.com", timeout=5)
        checks["nvidia_api_reachable"] = r.status_code < 500
    except Exception:
        checks["nvidia_api_reachable"] = False

    all_ok = True
    for name, ok in checks.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon}  {name}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    main()
