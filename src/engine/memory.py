# -*- coding: utf-8 -*-
import json
import os
import logging

logger = logging.getLogger("devops-agent")

class Memory:
    """
    Persistent user preferences and learned patterns across runs.
    """
    
    def __init__(self, project_path: str):
        self.memory_file = os.path.join(project_path, ".devops_memory.json")
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
        return {
            "preferences": {},
            "learned_patterns": []
        }

    def save_preference(self, key: str, value: str):
        self.data["preferences"][key] = value
        self._save()

    def add_pattern(self, pattern: str):
        if pattern not in self.data["learned_patterns"]:
            self.data["learned_patterns"].append(pattern)
            self._save()

    def _save(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    @property
    def preferences(self) -> dict:
        return self.data["preferences"]
