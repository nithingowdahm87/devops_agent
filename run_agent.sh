#!/bin/bash

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# Ollama tuning for 8 GB RAM machines
export OLLAMA_NUM_PARALLEL=1        # prevent concurrent model loading
export OLLAMA_MAX_LOADED_MODELS=1   # only keep 1 model in VRAM/RAM
export OLLAMA_KEEP_ALIVE=10m        # keep model warm, avoid reload delays

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
