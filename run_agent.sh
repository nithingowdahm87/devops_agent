#!/bin/bash

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8

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
# Updated to use the new v15.0 Sovereign Engine (agent.py)
python3 main.py "$@"
