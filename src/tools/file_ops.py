import os

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
