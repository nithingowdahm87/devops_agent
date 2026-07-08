"""Engine data models."""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class GeneratedFile:
    path: str
    content: str

@dataclass
class ValidationResult:
    passed: bool
    errors: List[str]

    def __init__(self, passed: bool = True, errors: List[str] = None):
        self.passed = passed
        self.errors = errors or []

@dataclass
class ArtifactSpec:
    path: str
    content: str
    artifact_type: str = "dockerfile"