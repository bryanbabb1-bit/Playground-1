"""PuLP-based resource staffing optimizer."""

from datetime import date, timedelta
from typing import Dict, List, Tuple

import pulp

from src.models import Assignment, Consultant, ResourceRequest

MIN_ASSIGNMENT_HOURS = 5.0  # Minimum 5 hours/week per assignment


def compute_affinity_score(
    consultant: Consultant,
    request: ResourceRequest,
    all_weeks: List[date],
) -> float:
    """Score how well a consultant fits a request (0 to 1)."""
    # Project history match (0.4 weight)
    project_score = 0.0
    client_name = request.project_name.split(" - ")[0].split(" | ")[0].strip().lower()
    for proj in consultant.billable_projects:
        if client_name in proj.lower():
            project_score = 1.0
            break
    if project_score == 0.0:
        for proj in consultant.projects:
            if client_name in proj.lower():
                project_score = 0.5
                break

    # Availability fit (0.4 weight)
    request_weeks = _get_request_weeks(request)
    if request_weeks:
        available_fractions = []
        for wk in request_weeks:
            avail = consultant.available_hours(wk)
            needed = request.hours_per_week
            available_fractions.append(min(1.0, avail / needed) if needed > 0 else 1.0)
        availability_score = sum(available_fractions) / len(available_fractions)
    else:
        availability_score = 0.5

    # Utilization balance (0.2 weight) - prefer underutilized consultants
    if request_weeks:
        avg_forecast = sum(
            consultant.forecast_hours.get(wk, 0) for wk in request_weeks
        ) / len(request_weeks)
        util_pct = avg_forecast / 40.0
        # Score higher when consultant is below 80% target
        balance_score = max(0.0, 1.0 - (util_pct / 0.8))
    else:
        balance_score = 0.5

    # Preferred consultant bonus
    preference_bonus = 0.0
    if request.preferred_consultant and request.preferred_consultant == consultant.name:
        preference_bonus = 0.3

    score = (0.4 * project_score + 0.4 * availability_score + 0.2 * balance_score + preference_bonus)
    return min(1.0, score)


def _get_request_weeks(request: ResourceRequest) -> List[date]:
    weeks = []
    current = request.start_week
    while current <= request.end_week:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks


def optimize_assignments(
    consultants: List[Consultant],
    requests: List[ResourceRequest],
) -> Tuple[List[Assignment], dict]:
    """
    Run the LP optimizer to assign consultants to requests.
    Returns (assignments, status_info).
    """
    # Filter out the generic "Consultant" placeholder
    real_consultants = [c for c in consultants if c.name.lower() != "consultant"]

    if not real_consultants or not requests:
        return [], {"status": "No data", "message": "No consultants or requests to optimize."}

    # Create the LP problem
    prob = pulp.LpProblem("StaffingOptimizer", pulp.LpMaximize)

    # Decision variables: fraction of request r assigned to consultant c
    x = {}
    for c in real_consultants:
        for r_idx, req in enumerate(requests):
            var_name = f"x_{c.name.replace(' ', '_')}_{r_idx}"
            x[(c.name, r_idx)] = pulp.LpVariable(var_name, lowBound=0, upBound=1)

    # Binary variables for minimum assignment threshold
    y = {}
    for c in real_consultants:
        for r_idx, req in enumerate(requests):
            var_name = f"y_{c.name.replace(' ', '_')}_{r_idx}"
            y[(c.name, r_idx)] = pulp.LpVariable(var_name, cat="Binary")

    # Compute affinity scores
    all_weeks = set()
    for req in requests:
        all_weeks.update(_get_request_weeks(req))
    all_weeks_list = sorted(all_weeks)

    affinities = {}
    for c in real_consultants:
        for r_idx, req in enumerate(requests):
            affinities[(c.name, r_idx)] = compute_affinity_score(c, req, all_weeks_list)

    # Objective: maximize total weighted assigned hours
    prob += pulp.lpSum(
        x[(c.name, r_idx)] * req.hours_per_week * req.total_weeks * affinities[(c.name, r_idx)]
        for c in real_consultants
        for r_idx, req in enumerate(requests)
    )

    # Constraint 1: each request assigned up to 100% (soft — allows partial if capacity insufficient)
    for r_idx, req in enumerate(requests):
        prob += (
            pulp.lpSum(x[(c.name, r_idx)] for c in real_consultants) <= 1,
            f"max_assignment_{r_idx}",
        )

    # Penalty for under-assignment to encourage full coverage
    under_assignment_penalty = 1000
    for r_idx, req in enumerate(requests):
        total_assigned = pulp.lpSum(x[(c.name, r_idx)] for c in real_consultants)
        prob.objective += under_assignment_penalty * total_assigned

    # Constraint 2: weekly capacity per consultant
    # Only constrain weeks where the consultant has room (existing < 40)
    for c in real_consultants:
        for wk in all_weeks_list:
            existing_forecast = c.forecast_hours.get(wk, 0.0)
            remaining = max(0.0, 40.0 - existing_forecast)
            new_load = pulp.lpSum(
                x[(c.name, r_idx)] * req.hours_per_week
                for r_idx, req in enumerate(requests)
                if wk in _get_request_weeks(req)
            )
            prob += (
                new_load <= remaining,
                f"capacity_{c.name.replace(' ', '_')}_{wk}",
            )

    # Constraint 3: minimum 5 hours/week if assigned (linked to binary)
    M = 1.0  # big-M (fraction is 0-1)
    for c in real_consultants:
        for r_idx, req in enumerate(requests):
            # x <= y (if not assigned, fraction must be 0)
            prob += x[(c.name, r_idx)] <= y[(c.name, r_idx)]
            # If assigned, minimum fraction = 5 / hours_per_week
            if req.hours_per_week > 0:
                min_fraction = min(1.0, MIN_ASSIGNMENT_HOURS / req.hours_per_week)
                prob += x[(c.name, r_idx)] >= min_fraction * y[(c.name, r_idx)]

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=30)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]

    # Extract assignments
    assignments = []
    for c in real_consultants:
        for r_idx, req in enumerate(requests):
            frac = x[(c.name, r_idx)].varValue
            if frac and frac > 0.01:
                assignments.append(Assignment(
                    request=req,
                    consultant_name=c.name,
                    hours_per_week=round(frac * req.hours_per_week, 1),
                    fraction=round(frac, 3),
                    affinity_score=round(affinities[(c.name, r_idx)], 3),
                ))

    status_info = {
        "status": status,
        "objective_value": pulp.value(prob.objective) if prob.objective else 0,
        "message": f"Optimizer found {'optimal' if status == 'Optimal' else status} solution.",
    }

    return assignments, status_info
