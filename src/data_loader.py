"""Data loading from Google Sheets (primary) and CSV (fallback)."""

import csv
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from src.models import Consultant, WeeklySnapshot

# Google Sheet IDs
FORECAST_SHEET_ID = "1djfGYKxhKm5NlC5IzvamtlAaK28AAnoE13uVFI4H8Yg"
RAW_DATA_SHEET_ID = "1VUADIkOWsRkcgQSsiOkqBnTWZk7pH-2wm8tI4XZihGA"

# CSV fallback paths (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORECAST_CSV = os.path.join(PROJECT_ROOT, "Only Consultant Forecasts + Suggested  - Summary.csv")
RAW_DATA_CSV = os.path.join(PROJECT_ROOT, "Util Raw Data - Raw Data.csv")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_gspread_client(credentials_dict: Optional[dict] = None) -> Optional["gspread.Client"]:
    if not GSPREAD_AVAILABLE:
        return None
    if credentials_dict is None:
        return None
    try:
        creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None


def _read_sheet_as_rows(client: "gspread.Client", sheet_id: str, worksheet_index: int = 0) -> List[List[str]]:
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.get_worksheet(worksheet_index)
    return worksheet.get_all_values()


def _read_csv_as_rows(path: str) -> List[List[str]]:
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def _parse_date(date_str: str) -> Optional[date]:
    date_str = date_str.strip()
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(val: str) -> float:
    val = val.strip().replace("%", "").replace(",", "")
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def _find_row_by_label(rows: List[List[str]], label: str) -> Optional[int]:
    label_lower = label.lower()
    for i, row in enumerate(rows):
        if row and row[0].strip().lower().startswith(label_lower):
            return i
    return None


def parse_forecast_data(
    credentials_dict: Optional[dict] = None,
) -> Tuple[List[Consultant], List[WeeklySnapshot], List[date]]:
    """Parse the forecast sheet. Returns (consultants, weekly_snapshots, week_dates)."""
    rows = None
    client = _get_gspread_client(credentials_dict)
    if client:
        try:
            rows = _read_sheet_as_rows(client, FORECAST_SHEET_ID)
        except Exception:
            rows = None

    if rows is None and os.path.exists(FORECAST_CSV):
        rows = _read_csv_as_rows(FORECAST_CSV)

    if rows is None:
        return [], [], []

    # Find the header row with "Estimated Hours" to anchor everything
    header_idx = _find_row_by_label(rows, "Estimated Hours")
    if header_idx is None:
        header_idx = 2  # fallback to row 3 (0-indexed)

    # Parse week dates from header row
    header_row = rows[header_idx]
    week_dates: List[date] = []
    date_col_start = 1  # first column is label
    for col_idx in range(date_col_start, len(header_row)):
        d = _parse_date(header_row[col_idx])
        if d:
            week_dates.append(d)
        else:
            week_dates.append(None)

    # Parse holiday markers from row above header (or row 0)
    holiday_row_idx = max(0, header_idx - 2)
    holiday_weeks = set()
    if holiday_row_idx < len(rows):
        holiday_row = rows[holiday_row_idx]
        for col_idx in range(date_col_start, min(len(holiday_row), len(week_dates) + date_col_start)):
            cell = holiday_row[col_idx].strip().lower()
            if "holiday" in cell:
                wk_idx = col_idx - date_col_start
                if wk_idx < len(week_dates) and week_dates[wk_idx]:
                    holiday_weeks.add(week_dates[wk_idx])

    # Find key summary rows
    capacity_idx = _find_row_by_label(rows, "Total Team Capacity")
    ftes_idx = _find_row_by_label(rows, "FTE's Available")
    if ftes_idx is None:
        ftes_idx = _find_row_by_label(rows, "FTEs Available")
    demand_idx = _find_row_by_label(rows, "FTE Demand")
    delta_idx = _find_row_by_label(rows, "Delta Capacity")
    target_idx = _find_row_by_label(rows, "Run Rate")
    actual_rate_idx = _find_row_by_label(rows, "Actual Run Rate")
    util_target_idx = _find_row_by_label(rows, "Util to Target")
    actual_util_idx = _find_row_by_label(rows, "Actual Util")

    # Parse consultant rows: everything between header and first blank/summary row
    consultants: List[Consultant] = []
    consultant_start = header_idx + 1
    consultant_end = capacity_idx if capacity_idx else len(rows)

    for row_idx in range(consultant_start, consultant_end):
        row = rows[row_idx]
        name = row[0].strip() if row else ""
        if not name:
            continue

        forecast_hours = {}
        for col_idx in range(date_col_start, min(len(row), len(week_dates) + date_col_start)):
            wk_idx = col_idx - date_col_start
            if wk_idx < len(week_dates) and week_dates[wk_idx]:
                hours = _parse_float(row[col_idx])
                forecast_hours[week_dates[wk_idx]] = hours

        consultants.append(Consultant(name=name, forecast_hours=forecast_hours))

    # Build weekly snapshots
    valid_weeks = [d for d in week_dates if d is not None]
    snapshots: List[WeeklySnapshot] = []

    for wk_idx, wk_date in enumerate(week_dates):
        if wk_date is None:
            continue
        col = wk_idx + date_col_start

        def _get_val(row_index, col_index):
            if row_index is None or row_index >= len(rows):
                return 0.0
            r = rows[row_index]
            if col_index >= len(r):
                return 0.0
            return _parse_float(r[col_index])

        consultant_forecasts = {}
        for c in consultants:
            consultant_forecasts[c.name] = c.forecast_hours.get(wk_date, 0.0)

        snap = WeeklySnapshot(
            week_start=wk_date,
            is_holiday=wk_date in holiday_weeks,
            team_capacity_hours=_get_val(capacity_idx, col),
            ftes_available=_get_val(ftes_idx, col),
            fte_demand=_get_val(demand_idx, col),
            delta_capacity=_get_val(delta_idx, col),
            run_rate_target=_get_val(target_idx, col),
            actual_run_rate=_get_val(actual_rate_idx, col),
            util_to_target=_get_val(util_target_idx, col),
            actual_util=_get_val(actual_util_idx, col),
            consultant_forecasts=consultant_forecasts,
        )
        snapshots.append(snap)

    return consultants, snapshots, valid_weeks


def load_raw_data(
    credentials_dict: Optional[dict] = None,
) -> pd.DataFrame:
    """Load the raw utilization timecard data. Returns a DataFrame."""
    df = None
    client = _get_gspread_client(credentials_dict)
    if client:
        try:
            rows = _read_sheet_as_rows(client, RAW_DATA_SHEET_ID)
            if rows:
                df = pd.DataFrame(rows[1:], columns=rows[0])
        except Exception:
            df = None

    if df is None and os.path.exists(RAW_DATA_CSV):
        df = pd.read_csv(RAW_DATA_CSV)

    if df is None:
        return pd.DataFrame()

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Parse types
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], format="mixed", errors="coerce")
    for col in ["PSR Total Billable Hours", "Total Hours", "Billable", "Time Credited",
                 "Sunday Hours", "Monday Hours", "Tuesday Hours", "Wednesday Hours",
                 "Thursday Hours", "Friday Hours", "Saturday Hours"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def enrich_consultants_with_actuals(
    consultants: List[Consultant], raw_df: pd.DataFrame
) -> List[Consultant]:
    """Merge actual timecard data into consultant objects."""
    if raw_df.empty:
        return consultants

    consultant_names = {c.name for c in consultants}

    # Aggregate raw data by resource and week
    raw_df = raw_df.copy()
    raw_df["Week Start"] = raw_df["Start Date"].dt.to_period("W-SAT").apply(
        lambda p: p.start_time.date() if pd.notna(p) else None
    )

    weekly = raw_df.groupby(["Resource", "Week Start"]).agg(
        total_hours=("Total Hours", "sum"),
        billable_hours=("PSR Total Billable Hours", "sum"),
    ).reset_index()

    # Project history per resource
    billable_mask = raw_df["Billable"] == 1
    project_history = raw_df.groupby("Resource")["Project"].apply(
        lambda x: list(x.unique())
    ).to_dict()
    billable_project_history = raw_df[billable_mask].groupby("Resource")["Project"].apply(
        lambda x: list(x.unique())
    ).to_dict()

    for consultant in consultants:
        name = consultant.name
        if name not in consultant_names:
            continue

        person_data = weekly[weekly["Resource"] == name]
        for _, row in person_data.iterrows():
            wk = row["Week Start"]
            if wk:
                consultant.actual_total_hours[wk] = row["total_hours"]
                consultant.actual_billable_hours[wk] = row["billable_hours"]

        consultant.projects = project_history.get(name, [])
        consultant.billable_projects = billable_project_history.get(name, [])

    return consultants


def compute_weekly_utilization(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Compute weekly utilization per resource."""
    if raw_df.empty:
        return pd.DataFrame()

    raw_df = raw_df.copy()
    raw_df["Week Start"] = raw_df["Start Date"].dt.to_period("W-SAT").apply(
        lambda p: p.start_time.date() if pd.notna(p) else None
    )

    weekly = raw_df.groupby(["Resource", "Week Start"]).agg(
        total_hours=("Total Hours", "sum"),
        billable_hours=("PSR Total Billable Hours", "sum"),
    ).reset_index()

    weekly["util_rate"] = weekly["billable_hours"] / 40.0
    return weekly


def get_project_history(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Get project history with total hours per resource per project."""
    if raw_df.empty:
        return pd.DataFrame()

    return raw_df.groupby(["Resource", "Project"]).agg(
        total_hours=("Total Hours", "sum"),
        billable_hours=("PSR Total Billable Hours", "sum"),
        is_billable=("Billable", "max"),
        weeks_on_project=("Start Date", "nunique"),
    ).reset_index().sort_values(["Resource", "total_hours"], ascending=[True, False])
