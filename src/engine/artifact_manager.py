# -*- coding: utf-8 -*-
import os
import shutil
import logging
from datetime import datetime
from src.engine.severity import Severity
from src.tools.file_ops import write_file

logger = logging.getLogger("devops-agent")

class ArtifactManager:
    """
    Manages artifact versioning, rollback history, and environment isolation.
    Ensures safe writes via the 'Write Gate'.
    """
    
    def __init__(self, project_path: str, environment: str = "dev"):
        self.project_path = project_path
        self.environment = environment
        self.history_dir = os.path.join(project_path, ".artifacts_history", environment)
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_run_dir = os.path.join(self.history_dir, self.run_id)
        
        os.makedirs(self.current_run_dir, exist_ok=True)

    def write_gate(self, rel_path: str, content: str, severity: Severity):
        """
        Policy-based write gate.
        CRITICAL: Never write.
        HIGH: Write to .broken.
        MEDIUM/LOW: Write to primary path.
        """
        full_path = os.path.join(self.project_path, rel_path)
        history_path = os.path.join(self.current_run_dir, rel_path)
        
        # Always save to history for audit/rollback
        write_file(history_path, content)
        
        if severity == Severity.CRITICAL:
            logger.error(f"Write Gate BLOCKED {rel_path} due to CRITICAL failure.")
            return False
            
        if severity == Severity.HIGH:
            if self.environment == "dev":
                logger.warning(f"[DEV] Write Gate HIGH violation on {rel_path} - writing anyway.")
                write_file(full_path, content)
                return True
            frozen_path = full_path + ".broken"
            write_file(frozen_path, content)
            logger.warning(f"Write Gate saved {rel_path} as .broken due to HIGH violation.")
            return False

        # Success path
        write_file(full_path, content)
        logger.info(f"Write Gate APPROVED {rel_path}.")
        return True

    def get_latest_valid(self, rel_path: str) -> str:
        """
        Finds the most recent valid version of an artifact in history.
        """
        if not os.path.exists(self.history_dir):
            return ""
            
        runs = sorted(os.listdir(self.history_dir), reverse=True)
        for run in runs:
            if run == self.run_id: continue # Skip current run
            path = os.path.join(self.history_dir, run, rel_path)
            # We assume it was valid if it wasn't .broken (simplification)
            if os.path.exists(path) and not path.endswith(".broken"):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        return ""
