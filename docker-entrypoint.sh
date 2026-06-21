#!/bin/sh
set -e

# Docker entrypoint for devops-agent server
# tini is used in the Dockerfile for signal handling; see Dockerfile ENTRYPOINT/CMD.
# This script ensures any pre-start setup can be added here later.

exec python3 main.py "$@"
