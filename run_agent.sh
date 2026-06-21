#!/bin/bash
# LOCAL DEVELOPMENT ONLY — not used inside Docker containers.
# For Docker, see docker-entrypoint.sh.

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# llama.cpp / llama-server defaults (override in .env or shell as needed)
export LLAMACPP_MODEL=${LLAMACPP_MODEL:-qwen-coder-1.5b.gguf}
export LLM_PROVIDER_MODE=${LLM_PROVIDER_MODE:-remote_first}

# Navigate to the script's directory (devops_agent root)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

# Source the Virtual Environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "⚠️  Virtual environment 'venv' not found. Please run 'python3 -m venv venv' and install requirements."
fi

# Source Environment Variables
if [ -f ".env" ]; then
    source .env
else
    echo "⚠️  '.env' file not found. System will run in Mock Mode. Copy '.env.example' to '.env' to configure keys."
fi

# Run the Agent
# Updated to use the v1.0.0 Sovereign Engine
python3 main.py "$@"
