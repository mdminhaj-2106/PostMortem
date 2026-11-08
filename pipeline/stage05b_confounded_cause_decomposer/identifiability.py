"""Design report §7.3: declared dependent-pair merge (Stage 3 design report §6's
shared-node rule) runs BEFORE the empirical collinearity gate, in that order. Only the
surviving, mutually-separable groups go to NNLS (attribution.py).
"""

import numpy as np

from cause_config import COSINE_MERGE_THRESHOLD, DEPENDENT_PAIRS


def _cosine(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def assess(candidates, bases, onsets=None):
    """candidates: list of cause names. bases: {cause: np.ndarray}. onsets: {cause: day}
    (needed only to check a declared pair's real chain lag). Returns (groups, verdict)
    where groups is a list of lists of cause names."""
    onsets = onsets or {}
    parent = {c: c for c in candidates}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (a, b), (lag_min, lag_max) in DEPENDENT_PAIRS.items():
        if a in candidates and b in candidates and a in onsets and b in onsets:
            lag = onsets[b] - onsets[a]
            if lag_min <= lag <= lag_max:
                union(a, b)

    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if find(a) == find(b):
                continue
            if abs(_cosine(bases[a], bases[b])) > COSINE_MERGE_THRESHOLD:
                union(a, b)

    groups_by_root = {}
    for c in candidates:
        groups_by_root.setdefault(find(c), []).append(c)
    groups = list(groups_by_root.values())

    if len(candidates) <= 1 or all(len(g) == 1 for g in groups):
        verdict = "CLEAN_SPLIT"
    elif len(groups) == 1:
        verdict = "FULLY_MERGED"
    else:
        verdict = "PARTIAL_MERGE"
    return groups, verdict
