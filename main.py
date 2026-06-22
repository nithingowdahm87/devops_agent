# -*- coding: utf-8 -*-
import os
import sys
import io
import argparse

# Enforce UTF-8 for stdout and stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.entrypoints.cli_main import run_cli
from src.entrypoints.server_main import run_server


def main():
    parser = argparse.ArgumentParser(description="DevOps AI Agent Pipeline v1.0.0")
    parser.add_argument("--mode", choices=["cli", "server"], default="cli",
                        help="Run mode")
    parser.add_argument("--env", type=str, default="dev", help="Environment")
    parser.add_argument("--strict", action="store_true", help="Enable strict policy mode")
    parser.add_argument("--no-llm", action="store_true", help="Force deterministic fallback mode")
    parser.add_argument("--gitops", action="store_true", help="Enable GitOps mode")
    parser.add_argument("--gitops-repo", type=str, help="GitOps repository URL or path")
    parser.add_argument("--service", type=str, help="Target a specific microservice only")
    parser.add_argument("--no-prompts", action="store_true", help="Run fully non-interactive")
    parser.add_argument("--no-heal", action="store_true", help="Skip automated healing/validation retries")
    parser.add_argument("--llm-mode", type=str, choices=["local", "kimchi", "remote"],
                        default=os.environ.get("LLM_PROVIDER_MODE", "kimchi"),
                        help="LLM provider mode")
    parser.add_argument("path", type=str, nargs="?", help="Project path")
    parser.add_argument("--port", type=int, help="Server port (server mode only)")

    args = parser.parse_args()

    if args.mode == "server":
        run_server(args)
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
