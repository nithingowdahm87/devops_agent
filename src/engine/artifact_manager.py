# -*- coding: utf-8 -*-
import os
import re
import hashlib
from datetime import datetime
from src.tools.file_ops import write_file
from src.engine.models import GeneratedFile


class ArtifactManager:
    """
    Manages writing generated artifacts to disk and maintaining history.
    Keeps history paths SHORT — file content is NEVER embedded in path names.
    """

    def __init__(self, project_path: str, environment: str = "dev", run_id: str = ""):
        self.project_path = project_path
        self.environment = environment
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.history_base = os.path.join(
            project_path,
            ".artifacts_history",
            environment,
            self.run_id,
        )

    def write_gate(self, rel_path: str, content: str, severity: str = "info") -> str:
        """
        Write artifact to project path AND record a copy in history.
        rel_path must be a clean relative path (e.g. 'k8s/frontend/deployment.yaml').
        content is the file content string — NEVER mixed into the path.
        Returns the absolute path written.
        """
        # Sanitise rel_path
        rel_path = rel_path.strip().lstrip("/").replace("\\", "/")

        # Guard: path must not contain newlines or be impossibly long
        if "\n" in rel_path or len(rel_path) > 255:
            rel_path = self._safe_fallback_name(rel_path)

        # Primary output
        output_path = os.path.join(self.project_path, rel_path)
        write_file(output_path, content)

        # History copy — non-fatal
        history_path = os.path.join(self.history_base, rel_path)
        try:
            write_file(history_path, content)
        except Exception as e:
            print(f"  [warn] Could not write history for {rel_path}: {e}")

        return output_path

    def _safe_fallback_name(self, bad_path: str) -> str:
        digest = hashlib.md5(bad_path.encode()).hexdigest()[:8]
        return f"recovered_{digest}.txt"

    def write_multifile(self, content: str, default_filename: str = "output.txt") -> list:
        """
        Parse FILENAME: blocks from LLM output and write each file.
        Returns list of written absolute paths.
        """
        pattern = r"FILENAME:\s*([^\n\r]+)[\r\n]+```[\w.-]*[\r\n]+(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        if not matches:
            out = self.write_gate(default_filename, content)
            return [out]

        written = []
        for rel_path, file_content in matches:
            out = self.write_gate(rel_path.strip(), file_content.strip())
            print(f"  - Created {rel_path.strip()}")
            written.append(out)
        return written
