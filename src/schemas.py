"""
Pydantic schemas for DevOps Agent pipeline data.

Provides type-safe validation for:
- ProjectContext: codebase analysis results (.devops_context.json)
- StageResult: output from every pipeline stage
- PolicyViolation: policy engine findings
- AuditEntry: audit trail log entries
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ──────────────────────────────────────────────────────────


class Decision(str, Enum):
    """Human decision at the approval gate."""
    APPROVE = "approve"
    REFINE = "refine"
    REJECT = "reject"


class Severity(str, Enum):
    """Policy violation severity."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ─── Project Context ───────────────────────────────────────────────


class ProjectContext(BaseModel):
    """
    Validated representation of .devops_context.json.
    Created by CodeAnalysisAgent, read by all subsequent stages.
    """
    project_name: str = Field(..., min_length=1)
    language: str = Field(default="unknown")
    frameworks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)
    file_structure: str = Field(default="")
    raw_context_summary: str = Field(default="")
    existing_files: dict[str, str] = Field(default_factory=dict, description="Map of found DevOps files to their paths")
    architecture: list[str] = Field(default_factory=list, description="Detected architectural patterns (e.g. microservices)")
    microservice_dirs: list[str] = Field(default_factory=list, description="Subdirectories that contain independent microservices (e.g. backend, frontend)")
    microservice_details: dict[str, Any] = Field(default_factory=dict, description="Per-service metadata: language, frameworks, ports, base_image")
    databases: dict[str, Any] = Field(default_factory=dict, description="Categorized databases: {rdbms: {name: [svcs]}, cache: {name: [svcs]}, nosql: {name: [svcs]}, broker: {name: [svcs]}}")
    service_path: str = Field(default="")
    resources: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ports", mode="before")
    @classmethod
    def coerce_ports_to_strings(cls, v: Any) -> list[str]:
        """Ensure ports are always strings (e.g. 3000 -> '3000')."""
        if isinstance(v, list):
            return [str(p) for p in v]
        return v

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v: Any) -> str:
        """Normalize empty/None language to 'unknown'."""
        if not v:
            return "unknown"
        return str(v).strip().lower()


# ─── Policy Violation ──────────────────────────────────────────────


class PolicyViolation(BaseModel):
    """A single policy check finding."""
    rule: str = Field(..., description="Rule identifier, e.g. 'docker-no-latest'")
    message: str = Field(..., description="Human-readable description")
    severity: Severity = Field(default=Severity.WARNING)


# ─── Stage Result ──────────────────────────────────────────────────


class StageResult(BaseModel):
    """
    Standardized output from every pipeline stage.
    Replaces the previous raw bool return from stage functions.
    """
    stage_name: str
    status: Decision
    content: str = Field(default="", description="Final approved content (empty if rejected)")
    reasoning: str = Field(default="", description="AI reviewer reasoning")
    policy_violations: list[PolicyViolation] = Field(default_factory=list)
    cycles: int = Field(default=1, ge=1, description="Number of review cycles")
    published_via: Optional[str] = Field(
        default=None,
        description="'github_pr' | 'local_write' | None",
    )


# ─── Audit Entry ──────────────────────────────────────────────────


class AuditEntry(BaseModel):
    """Typed version of a single audit log entry."""
    timestamp: float
    run_id: str
    stage: str
    decision: Decision
    reasoning: str = ""
    user_feedback: str = ""
    cycle: int = 1
    drafts_count: int = 0
