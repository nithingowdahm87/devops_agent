# -*- coding: utf-8 -*-
import hashlib
from dataclasses import dataclass
from typing import List, Dict
from src.engine.severity import Severity

@dataclass
class ArtifactReport:
    """
    Production Readiness Index for an artifact.
    """
    path: str
    score: float
    confidence: float
    security_score: float
    violations: List[str]
    model_version: str
    prompt_hash: str
    use_fallback: bool = False

    def to_markdown(self) -> str:
        status_icon = "✅" if self.score >= 80 else "⚠️" if self.score >= 60 else "❌"
        md = f"### {status_icon} Artifact: `{self.path}`\n\n"
        md += f"- **Readiness Score**: {self.score}/100\n"
        md += f"- **Security Score**: {self.security_score}/100\n"
        md += f"- **Confidence**: {self.confidence:.2%}\n"
        md += f"- **Model**: `{self.model_version}`\n"
        md += f"- **Prompt Hash**: `{self.prompt_hash[:8]}`\n"
        
        if self.violations:
            md += "\n#### Violations:\n"
            for v in self.violations:
                md += f"- {v}\n"
                
        if self.use_fallback:
            md += "\n> [!CAUTION]\n> This artifact was generated via a **Deterministic Fallback Template** due to healing failure.\n"
            
        return md

def get_prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()
