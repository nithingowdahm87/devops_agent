"""
Prompt cache — hashes (system+user prompt) and stores results on disk.
Identical inputs return instantly without any API call.
Cache lives in .cache/llm/ — excluded from git via .gitignore.
"""
from __future__ import annotations
import hashlib, json, logging, os
from pathlib import Path

log = logging.getLogger(__name__)

_CACHE_DIR = Path(".cache") / "llm"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Max cache entries before oldest are evicted
_MAX_ENTRIES = 500


def _key(system: str, user: str, task_type: str) -> str:
    raw = f"{task_type}|{system}|{user}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(system: str, user: str, task_type: str) -> str | None:
    """Return cached result or None if not cached."""
    path = _CACHE_DIR / (_key(system, user, task_type) + ".json")
    if path.exists():
        try:
            data = json.loads(path.read_text())
            log.info("Cache HIT for task_type=%s", task_type)
            return data["result"]
        except Exception:
            path.unlink(missing_ok=True)
    return None


def set(system: str, user: str, task_type: str, result: str) -> None:
    """Write result to cache."""
    _evict_if_needed()
    path = _CACHE_DIR / (_key(system, user, task_type) + ".json")
    path.write_text(json.dumps({"task_type": task_type, "result": result}))
    log.debug("Cache WRITE for task_type=%s", task_type)


def _evict_if_needed() -> None:
    """Remove oldest entries when cache exceeds _MAX_ENTRIES."""
    entries = sorted(_CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    while len(entries) >= _MAX_ENTRIES:
        entries.pop(0).unlink(missing_ok=True)


def invalidate_all() -> int:
    """Wipe entire cache. Returns number of entries deleted."""
    count = 0
    for f in _CACHE_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
        count += 1
    log.info("Cache cleared: %d entries removed.", count)
    return count
