# -*- coding: utf-8 -*-

# LLM Constants
MAX_LLM_RETRIES = 3
MAX_HEAL_RETRIES = 3

# HTTP & API Constants
HTTP_TIMEOUT_SECONDS = 15
END_OF_LIFE_API_URL = "https://endoflife.date/api"

# Compiler Settings
STRICT_MODE = False
DEFAULT_ENVIRONMENT = "dev"

# Formatting
JSON_SORT_KEYS = True
YAML_INDENT = 2
DOCKER_INSTRUCTION_ORDER = [
    "FROM", "ARG", "ENV", "WORKDIR", "COPY", "RUN", "EXPOSE", "USER", "HEALTHCHECK", "ENTRYPOINT", "CMD"
]
