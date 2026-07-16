# -*- coding: utf-8 -*-
import os
import re
import logging
from datetime import datetime
from src.engine.severity import Severity
from src.tools.file_ops import write_file

logger = logging.getLogger("devops-agent")

_MAX_PATH_SEGMENT = 200


def _sanitize_rel_path(rel_path: str) -> str:
    rel_path = rel_path.strip().lstrip("/")
    rel_path = rel_path.split("\n")[0].split("\r")[0].strip()
    parts = re.split(r"[/\\]+", rel_path)
    clean_parts = []
    for part in parts:
        if len(part.encode("utf-8")) > _MAX_PATH_SEGMENT:
            logger.error(
                f"Path component too long ({len(part)} chars) — "
                f"LLM likely embedded content in FILENAME token. "
                f"Truncating path to: {'/'.join(clean_parts) or '<root>'}"
            )
            break
        clean_parts.append(part)
    return "/".join(clean_parts)


class ArtifactManager:
    """
    Manages artifact versioning, rollback history, and environment isolation.
    Ensures safe writes via the 'Write Gate'.
    """

    def __init__(self, project_path: str, environment: str = "dev", dry_run: bool = False):
        self.project_path = os.path.realpath(os.path.abspath(project_path))
        self.environment = re.sub(r'[^a-zA-Z0-9._\-]', '_', environment)
        self.dry_run = dry_run
        self.history_dir = os.path.join(
            self.project_path, ".artifacts_history", self.environment
        )
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_run_dir = os.path.join(self.history_dir, self.run_id)
        os.makedirs(self.current_run_dir, exist_ok=True)

    def write_gate(self, rel_path: str, content: str, severity: Severity):
        """
        Policy-based write gate.
        CRITICAL : Never write.
        HIGH      : Write to .broken (or straight-through in dev).
        MEDIUM/LOW: Write to primary path.
        dry_run   : Always skip primary write; still writes to history for audit.
        """
        rel_path = _sanitize_rel_path(rel_path)
        if not rel_path:
            logger.error("write_gate: empty rel_path after sanitisation — skipping.")
            return False

        full_path = os.path.join(self.project_path, rel_path)
        history_path = os.path.join(self.current_run_dir, rel_path)

        write_file(history_path, content)

        if severity == Severity.CRITICAL:
            logger.error("Write Gate BLOCKED %s due to CRITICAL failure.", rel_path)
            return False

        if self.dry_run:
            logger.info(
                "dry_run_skip_write",
                extra={"path": rel_path, "content_bytes": len(content), "preview": content[:200]},
            )
            return False

        if severity == Severity.HIGH:
            if self.environment == "dev":
                logger.warning(
                    f"[DEV] Write Gate HIGH violation on {rel_path} - writing anyway."
                )
                write_file(full_path, content)
                return True
            frozen_path = full_path + ".broken"
            write_file(frozen_path, content)
            logger.warning(
                f"Write Gate saved {rel_path} as .broken due to HIGH violation."
            )
            return False

        write_file(full_path, content)
        logger.info("Write Gate APPROVED %s.", rel_path)
        return True

    def get_latest_valid(self, rel_path: str) -> str:
        """Finds the most recent valid version of an artifact in history."""
        if not os.path.exists(self.history_dir):
            return ""
        runs = sorted(os.listdir(self.history_dir), reverse=True)
        for run in runs:
            if run == self.run_id:
                continue
            path = os.path.join(self.history_dir, run, rel_path)
            if os.path.exists(path) and not path.endswith(".broken"):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        return ""
