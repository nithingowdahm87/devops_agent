#!/usr/bin/env python3
"""Run pipeline on a single app - simpler for debugging."""

import os
import sys
import argparse

# Set environment for NVIDIA only
os.environ['LLM_PRIMARY'] = 'nvidia'
os.environ['LLM_FALLBACK_ORDER'] = ''
os.environ['LLM_MAX_TOKENS'] = '16384'
os.environ['LLM_TIMEOUT_SECONDS'] = '180'
os.environ['LLM_MAX_RETRIES'] = '3'
os.environ['NVIDIA_API_KEY'] = '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'

sys.path.insert(0, '/home/nithin/repos/devops_agent/src')

from src.entrypoints.cli_main import run_cli

apps = [
    'demo-app-python', 'demo-app-node', 'demo-app-go', 'demo-app-java',
    'demo-app-rust', 'demo-app-ruby', 'demo-app-php', 'demo-app-dotnet',
    'demo-app-django', 'demo-app-elixir'
]

def run_app(app_name):
    app_path = f'/home/nithin/repos/{app_name}'
    print(f"\n{'='*60}")
    print(f"PROCESSING: {app_name}")
    print(f"{'='*60}")

    args = argparse.Namespace(
        mode='cli', env='dev', strict=False, gitops=False, gitops_repo=None,
        service=None, no_prompts=True, no_heal=True, llm_mode='nvidia',
        path=app_path, port=None, legacy=False
    )

    try:
        run_cli(args)
        print(f"✅ COMPLETED: {app_name}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {app_name} - {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('app', nargs='?', help='App name or index (0-9)')
    parser.add_argument('--all', action='store_true', help='Run all apps')
    args = parser.parse_args()

    if args.all:
        results = {}
        for app in apps:
            results[app] = run_app(app)
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for app, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {app}")
    elif args.app:
        if args.app.isdigit() and int(args.app) < len(apps):
            run_app(apps[int(args.app)])
        elif args.app in apps:
            run_app(args.app)
        else:
            print(f"Unknown app: {args.app}")
    else:
        print("Usage:")
        print("  python3 run_one.py <app_name|index>    # Run single app")
        print("  python3 run_one.py --all               # Run all apps")
        print(f"\nAvailable apps: {', '.join(apps)}")