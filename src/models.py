"""Data models for the Resource Staffing Optimizer."""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class Consultant:
    name: str
    forecast_hours: Dict[date, float] = field(default_factory=dict)  # week_start -> forecasted hours
    actual_total_hours: Dict[date, float] = field(default_factory=dict)  # week_start -> actual total hours
    actual_billable_hours: Dict[date, float] = field(default_factory=dict)  # week_start -> actual billable hours
    projects: List[str] = field(default_factory=list)  # unique project names from history
    billable_projects: List[str] = field(default_factory=list)  # unique billable project names

    def available_hours(self, week: date, capacity: float = 40.0) -> float:
        forecasted = self.forecast_hours.get(week, 0.0)
        return max(0.0, capacity - forecasted)

    def utilization_rate(self, week: date, capacity: float = 40.0) -> float:
        billable = self.actual_billable_hours.get(week, 0.0)
        if capacity == 0:
            return 0.0
        return billable / capacity


@dataclass
class WeeklySnapshot:
    week_start: date
    is_holiday: bool = False
    team_capacity_hours: float = 0.0
    ftes_available: float = 0.0
    fte_demand: float = 0.0
    delta_capacity: float = 0.0
    run_rate_target: float = 0.0
    actual_run_rate: float = 0.0
    util_to_target: float = 0.0
    actual_util: float = 0.0
    consultant_forecasts: Dict[str, float] = field(default_factory=dict)


@dataclass
class ResourceRequest:
    project_name: str
    hours_per_week: float
    start_week: date
    end_week: date
    preferred_consultant: Optional[str] = None
    notes: str = ""

    @property
    def total_weeks(self) -> int:
        return max(1, ((self.end_week - self.start_week).days // 7) + 1)

    @property
    def total_hours(self) -> float:
        return self.hours_per_week * self.total_weeks


@dataclass
class Assignment:
    request: ResourceRequest
    consultant_name: str
    hours_per_week: float
    fraction: float  # 0-1, portion of the request assigned to this consultant
    affinity_score: float = 0.0

    @property
    def total_hours(self) -> float:
        return self.hours_per_week * self.request.total_weeks
