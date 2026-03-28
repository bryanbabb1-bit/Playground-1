"""Page 4: FTE Report — Demand vs capacity, quarterly summaries, hiring projections."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

from src.metrics import (
    build_demand_capacity_df,
    build_quarterly_fte_summary,
    current_week_start,
)
from src.charts import fte_demand_capacity_chart

st.title("FTE Report")

consultants = st.session_state.get("consultants", [])
snapshots = st.session_state.get("snapshots", [])
date_start = st.session_state.get("date_start", date(2024, 1, 1))
date_end = st.session_state.get("date_end", date(2027, 1, 1))

if not snapshots:
    st.warning("No data loaded.")
    st.stop()

# Filter snapshots
filtered_snapshots = [s for s in snapshots if date_start <= s.week_start <= date_end]

# --- FTE Demand vs Capacity Chart ---
dc_df = build_demand_capacity_df(filtered_snapshots)
if not dc_df.empty:
    st.plotly_chart(fte_demand_capacity_chart(dc_df), use_container_width=True)

st.markdown("---")

# --- Quarterly FTE Summary ---
st.subheader("Quarterly FTE Summary")
quarterly = build_quarterly_fte_summary(filtered_snapshots)
if not quarterly.empty:
    display_q = quarterly[["Quarter", "avg_ftes_available", "avg_fte_demand", "avg_delta", "min_delta"]].copy()
    display_q.columns = ["Quarter", "Avg FTEs Available", "Avg FTE Demand", "Avg Delta", "Min Delta Week"]
    display_q = display_q.round(1)

    # Highlight negative delta quarters
    def highlight_negative(row):
        if row["Min Delta Week"] < 0:
            return ["background-color: #FFCCCC"] * len(row)
        return [""] * len(row)

    styled = display_q.style.apply(highlight_negative, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No quarterly data available.")

st.markdown("---")

# --- Hiring Need Projection ---
st.subheader("Hiring Need Projection")

if not dc_df.empty and dc_df["FTE Demand"].sum() > 0:
    # Filter to weeks with actual demand data
    demand_data = dc_df[dc_df["FTE Demand"] > 0].copy()

    if len(demand_data) >= 2:
        demand_data["Week_Num"] = (demand_data["Week"] - demand_data["Week"].min()).dt.days / 7

        # Linear regression on FTE demand trend
        x = demand_data["Week_Num"].values
        y = demand_data["FTE Demand"].values
        if len(x) >= 2:
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]

            st.metric("FTE Demand Trend", f"{slope:+.2f} FTEs/week")

            if slope > 0:
                # Project when demand exceeds current capacity
                current_capacity = dc_df["FTEs Available"].iloc[-1] if len(dc_df) > 0 else 14
                current_demand = y[-1] if len(y) > 0 else 0
                weeks_to_exceed = (current_capacity - current_demand) / slope if slope > 0 else float("inf")

                if weeks_to_exceed > 0 and weeks_to_exceed < 52:
                    st.warning(f"At the current trend, demand will exceed capacity in approximately **{weeks_to_exceed:.0f} weeks**.")
                elif weeks_to_exceed <= 0:
                    st.error("Demand already exceeds available capacity!")
                else:
                    st.success("Demand is not projected to exceed capacity within the next year.")
            else:
                st.success("FTE demand is trending downward — no immediate hiring need projected.")
    else:
        st.info("Insufficient demand data for projection (need at least 2 weeks with demand).")
else:
    st.info("No FTE demand data available for projection.")

st.markdown("---")

# --- Capacity Sensitivity Analysis ---
st.subheader("What-If: Add Consultants")

additional_ftes = st.slider("Additional consultants to add", min_value=0, max_value=10, value=0)

if additional_ftes > 0 and not dc_df.empty:
    adjusted_df = dc_df.copy()
    adjusted_df["FTEs Available (Adjusted)"] = adjusted_df["FTEs Available"] + additional_ftes
    adjusted_df["Delta (Adjusted)"] = adjusted_df["FTEs Available (Adjusted)"] - adjusted_df["FTE Demand"]

    import plotly.graph_objects as go
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=adjusted_df["Week"], y=adjusted_df["FTEs Available"],
        name="Current Capacity", line=dict(color="#6C757D", dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=adjusted_df["Week"], y=adjusted_df["FTEs Available (Adjusted)"],
        name=f"With +{additional_ftes} FTEs", line=dict(color="#28A745", width=2),
        fill="tozeroy", fillcolor="rgba(40,167,69,0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=adjusted_df["Week"], y=adjusted_df["FTE Demand"],
        name="FTE Demand", line=dict(color="#DC3545", width=2),
    ))

    fig.add_hline(y=0, line_color="black", line_width=1)

    fig.update_layout(
        title=f"Capacity with {additional_ftes} Additional Consultant(s)",
        xaxis_title="Week", yaxis_title="FTEs",
        hovermode="x unified", height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary
    weeks_deficit = len(adjusted_df[adjusted_df["Delta (Adjusted)"] < 0])
    st.metric(
        "Weeks with Capacity Deficit (Adjusted)",
        f"{weeks_deficit}",
        delta=f"{len(dc_df[dc_df['Delta Capacity'] < 0]) - weeks_deficit} fewer" if weeks_deficit < len(dc_df[dc_df['Delta Capacity'] < 0]) else None,
    )
elif additional_ftes == 0:
    st.info("Slide to add consultants and see the impact on capacity.")
