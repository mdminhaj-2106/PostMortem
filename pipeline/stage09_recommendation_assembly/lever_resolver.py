"""mechanism -> the one declared lever (design doc §14, reduced per plan finding
#5/#8: no structural-applicability filtering step -- nothing real to filter
against, Stage 3's DAG is a single 2-KPI edge).
"""

from config import MECHANISM_LEVERS


def resolve_lever(mechanism):
    if mechanism not in MECHANISM_LEVERS:
        raise ValueError(f"undeclared mechanism: {mechanism!r}")
    return MECHANISM_LEVERS[mechanism]
