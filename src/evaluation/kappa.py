from collections import Counter
from typing import List


def cohens_kappa(y1: List, y2: List) -> float:
    if len(y1) != len(y2):
        raise ValueError("Lists must have the same length")
    n = len(y1)
    if n == 0:
        return 0.0
    # Observed agreement
    agreements = sum(1 for a, b in zip(y1, y2) if a == b)
    p_o = agreements / n
    if p_o == 1.0:
        return 1.0
    # Expected agreement
    c1 = Counter(y1)
    c2 = Counter(y2)
    p_e = sum(c1[k] * c2[k] for k in c1) / (n * n)
    if p_e == 1.0:
        return 0.0
    return (p_o - p_e) / (1 - p_e)