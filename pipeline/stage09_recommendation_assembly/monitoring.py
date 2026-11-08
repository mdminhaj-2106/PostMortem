"""Monitoring is derived from the one investigated KPI (design doc §44-45,
reduced per plan finding #5 -- no rich KPI DAG exists to propagate a multi-KPI
monitored set). expected_direction is always "UP" -- all 5 real KPIs are
higher-is-better in this dataset (Stage 8's own impact.KPI_DIRECTION finding,
reused here rather than re-derived). monitoring_horizon stays NOT_SPECIFIED --
no configured basis exists anywhere in this repo to invent a check-in date
(design doc §45's own instruction).
"""

from models import MonitoringPlan


def build_monitoring_plan(kpi_name):
    affected_kpis = [kpi_name] if kpi_name else []
    return MonitoringPlan(affected_kpis=affected_kpis, expected_direction="UP", monitoring_horizon="NOT_SPECIFIED")
