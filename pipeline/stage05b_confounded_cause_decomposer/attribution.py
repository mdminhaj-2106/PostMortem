"""Design report §7.4: minimise ||M*x_obs - sum_k c_k*b_k||, c_k >= 0. c is in the same
units as M (KPI units when M is the observed window's total |deviation|).

No scipy (Risk #5's accepted fallback -- CONSTITUTION.md requires checking new
dependencies first, and this project runs on psycopg2+numpy only so far). A ~20-line
active-set NNLS: solve unconstrained least squares, drop the most-negative coefficient's
column, repeat -- exact for the well-conditioned, <=6-variable problems this stage ever
sees (5-6 causes, at most).
# ponytail: simplified active-set NNLS, not the full Lawson-Hanson algorithm. Swap for
# scipy.optimize.nnls if a harder-conditioned problem ever needs it.
"""

import numpy as np


def _nnls(A, y, max_iter=20):
    n = A.shape[1]
    active = np.ones(n, dtype=bool)
    coef = np.zeros(n)
    for _ in range(max_iter):
        idx = np.where(active)[0]
        if len(idx) == 0:
            break
        sol, *_ = np.linalg.lstsq(A[:, idx], y, rcond=None)
        if np.all(sol >= -1e-9):
            coef = np.zeros(n)
            coef[idx] = np.clip(sol, 0, None)
            return coef
        active[idx[np.argmin(sol)]] = False
    coef = np.zeros(n)
    idx = np.where(active)[0]
    if len(idx):
        sol, *_ = np.linalg.lstsq(A[:, idx], y, rcond=None)
        coef[idx] = np.clip(sol, 0, None)
    return coef


def fit(x_obs, bases_by_cause, magnitude):
    """x_obs: unit shape vector. bases_by_cause: {cause: unit shape vector}.
    magnitude: observed window's total |deviation|, KPI units.

    Returns (contributions: {cause: KPI units}, unexplained: KPI units, fit_quality)."""
    causes = list(bases_by_cause)
    A = np.stack([bases_by_cause[c] for c in causes], axis=1)
    y = magnitude * np.asarray(x_obs, dtype=float)

    coef = _nnls(A, y)
    fitted = A @ coef
    residual_norm = float(np.linalg.norm(y - fitted))
    y_norm = float(np.linalg.norm(y))
    fit_quality = 1.0 - residual_norm / y_norm if y_norm > 0 else 0.0

    contributions = {c: float(coef[i]) for i, c in enumerate(causes)}
    return contributions, residual_norm, fit_quality
