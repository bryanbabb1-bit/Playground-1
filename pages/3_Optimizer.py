"""Page 3: Staffing Optimizer — Resource request input and assignment recommendations."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from src.models import ResourceRequest
from src.optimizer import optimize_assignments
from src.metrics import current_week_start
from src.charts import before_after_util_chart, assignment_gantt

st.title("Staffing Optimizer")

consultants = st.session_state.get("consultants", [])
week_dates = st.session_state.get("week_dates", [])

if not consultants:
    st.warning("No data loaded.")
    st.stop()

real_consultants = [c for c in consultants if c.name.lower() != "consultant"]
consultant_names = sorted([c.name for c in real_consultants])

# Initialize requests in session state
if "resource_requests" not in st.session_state:
    st.session_state["resource_requests"] = []

# --- Auto-detect unassigned demand ---
st.subheader("Unassigned Demand")
unassigned = next((c for c in consultants if c.name.lower() == "consultant"), None)
if unassigned:
    cw = current_week_start()
    future_demand = {wk: hrs for wk, hrs in unassigned.forecast_hours.items() if wk >= cw and hrs > 0}
    if future_demand:
        st.info(f"Found **{sum(future_demand.values()):.0f} hours** of unassigned demand across **{len(future_demand)} weeks**.")
        if st.button("Auto-create request from unassigned demand"):
            start_wk = min(future_demand.keys())
            end_wk = max(future_demand.keys())
            avg_hrs = sum(future_demand.values()) / len(future_demand)
            auto_req = ResourceRequest(
                project_name="Unassigned Demand",
                hours_per_week=round(avg_hrs, 1),
                start_week=start_wk,
                end_week=end_wk,
                notes="Auto-detected from forecast 'Consultant' row",
            )
            st.session_state["resource_requests"].append(auto_req)
            st.rerun()
    else:
        st.success("No unassigned demand in the forecast.")
else:
    st.info("No 'Consultant' row found in forecast data.")

st.markdown("---")

# --- Manual Request Entry ---
st.subheader("Add Resource Request")

# Get unique client names from raw data for suggestions
raw_df = st.session_state.get("raw_df", pd.DataFrame())
if not raw_df.empty and "Project" in raw_df.columns:
    projects = sorted(raw_df["Project"].dropna().unique().tolist())
else:
    projects = []

with st.form("add_request"):
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input("Project / Client Name", placeholder="e.g., AmeriCU - SF Optimization")
        hours_per_week = st.slider("Hours per Week", min_value=5, max_value=40, value=20, step=5)
        preferred = st.selectbox("Preferred Consultant (optional)", options=["None"] + consultant_names)
    with col2:
        min_date = current_week_start()
        max_date = max(week_dates) if week_dates else min_date + timedelta(weeks=52)
        start_date = st.date_input("Start Week", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.date_input("End Week", value=min_date + timedelta(weeks=8), min_value=min_date, max_value=max_date)
        notes = st.text_input("Notes", placeholder="Optional notes")

    submitted = st.form_submit_button("Add Request")
    if submitted and project_name:
        req = ResourceRequest(
            project_name=project_name,
            hours_per_week=float(hours_per_week),
            start_week=start_date,
            end_week=end_date,
            preferred_consultant=preferred if preferred != "None" else None,
            notes=notes,
        )
        st.session_state["resource_requests"].append(req)
        st.rerun()

# --- Current Requests ---
requests = st.session_state["resource_requests"]
if requests:
    st.subheader(f"Current Requests ({len(requests)})")
    req_data = []
    for i, r in enumerate(requests):
        req_data.append({
            "#": i + 1,
            "Project": r.project_name,
            "Hrs/Week": r.hours_per_week,
            "Start": r.start_week,
            "End": r.end_week,
            "Total Weeks": r.total_weeks,
            "Total Hours": r.total_hours,
            "Preferred": r.preferred_consultant or "-",
        })
    st.dataframe(pd.DataFrame(req_data), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear All Requests"):
            st.session_state["resource_requests"] = []
            st.rerun()
    with col2:
        run_optimizer = st.button("Run Optimizer", type="primary")

    if run_optimizer:
        with st.spinner("Running optimizer..."):
            assignments, status_info = optimize_assignments(real_consultants, requests)

        st.markdown("---")
        st.subheader("Optimization Results")

        if status_info["status"] == "Optimal":
            st.success(status_info["message"])
        else:
            st.warning(status_info["message"])

        if assignments:
            # --- Assignment Results Table ---
            assign_data = []
            for a in assignments:
                assign_data.append({
                    "Project": a.request.project_name,
                    "Consultant": a.consultant_name,
                    "Hours/Week": a.hours_per_week,
                    "Fraction": f"{a.fraction * 100:.0f}%",
                    "Total Hours": a.total_hours,
                    "Affinity Score": f"{a.affinity_score:.2f}",
                })
            assign_df = pd.DataFrame(assign_data)
            st.dataframe(assign_df, use_container_width=True, hide_index=True)

            # --- Before/After Utilization ---
            st.subheader("Utilization Impact")
            cw = current_week_start()
            current_utils = []
            proposed_utils = []
            names = []

            for c in real_consultants:
                existing = c.forecast_hours.get(cw, 0) / 40.0
                added = sum(
                    a.hours_per_week for a in assignments
                    if a.consultant_name == c.name
                ) / 40.0
                current_utils.append(existing)
                proposed_utils.append(existing + added)
                names.append(c.name)

            fig = before_after_util_chart(names, current_utils, proposed_utils)
            st.plotly_chart(fig, use_container_width=True)

            # --- Gantt Timeline ---
            st.subheader("Assignment Timeline")
            gantt_data = []
            for a in assignments:
                gantt_data.append({
                    "Consultant": a.consultant_name,
                    "Project": a.request.project_name,
                    "Start": pd.Timestamp(a.request.start_week),
                    "End": pd.Timestamp(a.request.end_week),
                    "Hours/Week": a.hours_per_week,
                    "Fraction": f"{a.fraction * 100:.0f}%",
                })
            gantt_df = pd.DataFrame(gantt_data)
            fig = assignment_gantt(gantt_df)
            st.plotly_chart(fig, use_container_width=True)

            # --- Export ---
            st.subheader("Export")
            csv = assign_df.to_csv(index=False)
            st.download_button(
                "Download Assignments as CSV",
                csv,
                file_name="staffing_assignments.csv",
                mime="text/csv",
            )
        else:
            st.info("No feasible assignments found. Try adjusting request parameters or date ranges.")
else:
    st.info("Add resource requests above, or auto-detect from unassigned demand, then click 'Run Optimizer'.")
