"""Domain exception hierarchy for devops_agent.

Maps cleanly to ExitCode values in src/engine/severity.py.
"""
from __future__ import annotations


class DevopsAgentError(Exception):
    """Base exception for all devops_agent errors."""


class ConfigError(DevopsAgentError):
    """Invalid configuration, missing files, bad env vars."""


class LLMError(DevopsAgentError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ValidationError(DevopsAgentError):
    def __init__(self, message: str, stage: str, violations: list[str]) -> None:
        super().__init__(message)
        self.stage = stage
        self.violations = violations


class PolicyViolationError(DevopsAgentError):
    def __init__(self, message: str, policies: list[str], severity: str) -> None:
        super().__init__(message)
        self.policies = policies
        self.severity = severity


class PathTraversalError(DevopsAgentError):
    """Attempted write outside allowed output directories."""


class PromptInjectionError(DevopsAgentError):
    """Template context contains disallowed variables."""
