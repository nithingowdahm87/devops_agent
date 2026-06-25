import os

def _safe_path(project_root: str, path: str) -> str:
    """
    Resolve `path` to an absolute path and verify it is within `project_root`.

    Raises ValueError if the resolved path escapes `project_root`.
    """
    if "\x00" in path:
        raise ValueError("Path escape attempt detected: null byte in path")
    abs_root = os.path.abspath(project_root)
    # Join path to the root BEFORE resolving to absolute, so relative paths
    # are interpreted relative to project_root, not the current directory.
    if path == "":
        abs_path = abs_root
    else:
        abs_path = os.path.abspath(os.path.join(abs_root, os.path.expanduser(path)))
    # Normalize the root to always have a trailing separator to ensure prefix check is strict
    if not abs_root.endswith(os.sep):
        abs_root += os.sep
    if not abs_path.startswith(abs_root) and abs_path != abs_root.rstrip(os.sep):
        raise ValueError(f"Path escape attempt detected: {abs_path} is not under {abs_root}")
    return abs_path

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def scan_directory(path: str) -> str:
    entries = []
    for root, dirs, files in os.walk(path):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), path)
            entries.append(rel)
    entries.sort()
    return "\n".join(entries)