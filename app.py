"""Resource Staffing Optimizer — Main Streamlit App."""

import streamlit as st

st.set_page_config(
    page_title="Resource Staffing Optimizer",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

import pandas as pd
from datetime import date

from src.data_loader import (
    parse_forecast_data,
    load_raw_data,
    enrich_consultants_with_actuals,
    compute_weekly_utilization,
)
from src.metrics import (
    build_demand_capacity_df,
    build_consultant_forecast_df,
    build_utilization_heatmap_data,
    current_week_start,
)


def get_google_credentials():
    """Try to load Google credentials from Streamlit secrets."""
    try:
        return dict(st.secrets["google_service_account"])
    except Exception:
        return None


@st.cache_data(ttl=300)
def load_all_data():
    creds = get_google_credentials()
    consultants, snapshots, week_dates = parse_forecast_data(creds)
    raw_df = load_raw_data(creds)
    consultants = enrich_consultants_with_actuals(consultants, raw_df)
    weekly_util = compute_weekly_utilization(raw_df)
    return consultants, snapshots, week_dates, raw_df, weekly_util


# --- Sidebar ---
st.sidebar.title("Staffing Optimizer")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Load data
consultants, snapshots, week_dates, raw_df, weekly_util = load_all_data()

# Store in session state for pages to access
st.session_state["consultants"] = consultants
st.session_state["snapshots"] = snapshots
st.session_state["week_dates"] = week_dates
st.session_state["raw_df"] = raw_df
st.session_state["weekly_util"] = weekly_util

# Date range filter
if week_dates:
    min_date = min(week_dates)
    max_date = max(week_dates)

    # Default to showing from 6 months ago onward
    default_start = max(min_date, date(date.today().year, max(1, date.today().month - 6), 1))

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if len(date_range) == 2:
        st.session_state["date_start"] = date_range[0]
        st.session_state["date_end"] = date_range[1]
    else:
        st.session_state["date_start"] = default_start
        st.session_state["date_end"] = max_date

# Consultant filter
real_consultants = [c for c in consultants if c.name.lower() != "consultant"]
consultant_names = sorted([c.name for c in real_consultants])

selected_consultants = st.sidebar.multiselect(
    "Filter Consultants",
    options=consultant_names,
    default=consultant_names,
)
st.session_state["selected_consultants"] = selected_consultants

# Data status
st.sidebar.markdown("---")
st.sidebar.caption(f"**Data loaded:** {len(real_consultants)} consultants, {len(snapshots)} weeks")
st.sidebar.caption(f"**Timecards:** {len(raw_df):,} entries")
creds = get_google_credentials()
if creds:
    st.sidebar.caption("**Source:** Google Sheets (live)")
else:
    st.sidebar.caption("**Source:** Local CSV files")


# --- Main Page ---
st.title("Resource Staffing Optimizer")
st.markdown("Navigate to pages using the sidebar to view the Dashboard, Resource Details, Optimizer, or FTE Report.")

# Quick summary
if consultants and snapshots:
    from src.metrics import (
        team_utilization_current,
        ftes_available_current,
        open_demand_hours,
        weeks_until_overcapacity,
    )

    col1, col2, col3, col4 = st.columns(4)

    util = team_utilization_current(snapshots)
    ftes = ftes_available_current(snapshots)
    demand = open_demand_hours(consultants, snapshots)
    overcap = weeks_until_overcapacity(snapshots)

    col1.metric("Team Utilization", f"{util * 100:.1f}%" if util else "N/A")
    col2.metric("FTEs Available", f"{ftes:.1f}")
    col3.metric("Open Demand (hrs)", f"{demand:.0f}")
    col4.metric("Weeks to Over-Capacity", f"{overcap}" if overcap is not None else "None in view")

    st.markdown("---")
    st.markdown("### Quick Start")
    st.markdown("""
    - **Dashboard** — Demand vs capacity charts, utilization heatmap
    - **Resource View** — Drill into individual consultant utilization and project history
    - **Optimizer** — Enter resource requests and get AI-powered staffing recommendations
    - **FTE Report** — FTE demand vs capacity trends, quarterly summaries, hiring projections
    """)
else:
    st.warning("No data loaded. Check your CSV files or Google Sheets configuration.")
    st.markdown("""
    ### Setup Instructions

    **Option 1: Google Sheets (recommended)**
    1. Create a Google Cloud project and enable the Sheets API
    2. Create a service account and download the JSON key
    3. Share both Google Sheets with the service account email (Viewer access)
    4. Create `.streamlit/secrets.toml` with your credentials

    **Option 2: CSV files**
    Place your CSV exports in the project root:
    - `Only Consultant Forecasts + Suggested  - Summary.csv`
    - `Util Raw Data - Raw Data.csv`
    """)
