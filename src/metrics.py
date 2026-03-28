"""Utilization, FTE, and capacity metric calculations."""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.models import Consultant, WeeklySnapshot


def current_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())  # Monday


def get_current_snapshot(snapshots: List[WeeklySnapshot]) -> Optional[WeeklySnapshot]:
    cw = current_week_start()
    # Find the closest snapshot to current week
    closest = None
    min_diff = float("inf")
    for s in snapshots:
        diff = abs((s.week_start - cw).days)
        if diff < min_diff:
            min_diff = diff
            closest = s
    return closest


def team_utilization_current(snapshots: List[WeeklySnapshot]) -> float:
    snap = get_current_snapshot(snapshots)
    if snap and snap.actual_util:
        return snap.actual_util
    if snap and snap.util_to_target:
        return snap.util_to_target
    return 0.0


def ftes_available_current(snapshots: List[WeeklySnapshot]) -> float:
    snap = get_current_snapshot(snapshots)
    return snap.ftes_available if snap else 0.0


def open_demand_hours(consultants: List[Consultant], snapshots: List[WeeklySnapshot]) -> float:
    """Sum of hours in the 'Consultant' (unassigned) row for upcoming weeks."""
    cw = current_week_start()
    for c in consultants:
        if c.name.lower() == "consultant":
            return sum(h for wk, h in c.forecast_hours.items() if wk >= cw)
    return 0.0


def weeks_until_overcapacity(snapshots: List[WeeklySnapshot]) -> Optional[int]:
    cw = current_week_start()
    future = sorted([s for s in snapshots if s.week_start >= cw], key=lambda s: s.week_start)
    for i, s in enumerate(future):
        if s.delta_capacity < 0:
            return i
    return None


def trailing_avg_utilization(consultant: Consultant, weeks: int = 4) -> float:
    cw = current_week_start()
    recent_weeks = sorted(
        [wk for wk in consultant.actual_billable_hours if wk <= cw],
        reverse=True,
    )[:weeks]
    if not recent_weeks:
        return 0.0
    total_billable = sum(consultant.actual_billable_hours.get(wk, 0) for wk in recent_weeks)
    return total_billable / (40.0 * len(recent_weeks))


def build_demand_capacity_df(snapshots: List[WeeklySnapshot]) -> pd.DataFrame:
    """Build a DataFrame for demand vs capacity charting."""
    records = []
    for s in snapshots:
        total_forecast = sum(s.consultant_forecasts.values())
        records.append({
            "Week": s.week_start,
            "Holiday": s.is_holiday,
            "Team Capacity": s.team_capacity_hours,
            "Total Forecasted Hours": total_forecast,
            "FTEs Available": s.ftes_available,
            "FTE Demand": s.fte_demand,
            "Delta Capacity": s.delta_capacity,
            "Run Rate Target": s.run_rate_target,
            "Actual Run Rate": s.actual_run_rate,
            "Util to Target": s.util_to_target,
            "Actual Util": s.actual_util,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df["Week"] = pd.to_datetime(df["Week"])
    return df


def build_consultant_forecast_df(consultants: List[Consultant], week_dates: List[date]) -> pd.DataFrame:
    """Build a pivot DataFrame: consultants x weeks with forecasted hours."""
    records = []
    for c in consultants:
        if c.name.lower() == "consultant":
            continue
        for wk in week_dates:
            records.append({
                "Consultant": c.name,
                "Week": wk,
                "Forecasted Hours": c.forecast_hours.get(wk, 0.0),
                "Available Hours": c.available_hours(wk),
            })
    df = pd.DataFrame(records)
    if not df.empty:
        df["Week"] = pd.to_datetime(df["Week"])
    return df


def build_utilization_heatmap_data(
    consultants: List[Consultant], week_dates: List[date]
) -> pd.DataFrame:
    """Build data for utilization heatmap: consultants x weeks."""
    records = []
    for c in consultants:
        if c.name.lower() == "consultant":
            continue
        for wk in week_dates:
            forecasted = c.forecast_hours.get(wk, 0.0)
            util_pct = (forecasted / 40.0) * 100 if forecasted else 0.0
            records.append({
                "Consultant": c.name,
                "Week": wk,
                "Forecasted Hours": forecasted,
                "Utilization %": util_pct,
            })
    df = pd.DataFrame(records)
    if not df.empty:
        df["Week"] = pd.to_datetime(df["Week"])
    return df


def build_quarterly_fte_summary(snapshots: List[WeeklySnapshot]) -> pd.DataFrame:
    """Build quarterly summary of FTE metrics."""
    records = []
    for s in snapshots:
        q = (s.week_start.month - 1) // 3 + 1
        fy = s.week_start.year
        if s.week_start.month >= 2:  # Adjust if fiscal year differs
            fy_label = f"FY{fy}"
        else:
            fy_label = f"FY{fy}"
        records.append({
            "Quarter": f"Q{q} {fy_label}",
            "Year": fy,
            "Q": q,
            "FTEs Available": s.ftes_available,
            "FTE Demand": s.fte_demand,
            "Delta": s.delta_capacity,
        })
    df = pd.DataFrame(records)
    if df.empty:
        return df

    summary = df.groupby(["Quarter", "Year", "Q"]).agg(
        avg_ftes_available=("FTEs Available", "mean"),
        avg_fte_demand=("FTE Demand", "mean"),
        avg_delta=("Delta", "mean"),
        min_delta=("Delta", "min"),
    ).reset_index().sort_values(["Year", "Q"])

    return summary
