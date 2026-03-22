# src/engine/chunker.py
from __future__ import annotations
from typing import List

def simple_markdown_chunks(text: str, max_chars: int = 1200) -> List[str]:
    """
    Naive chunker: split by headings / blank lines and then merge
    until each chunk is under max_chars.
    """
    raw_sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    chunks: List[str] = []
    current: list[str] = []

    for sec in raw_sections:
        if sum(len(x) + 2 for x in current) + len(sec) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [sec]
        else:
            current.append(sec)

    if current:
        chunks.append("\n\n".join(current))
    return chunks
