"""Plotly chart builders for the staffing dashboard."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def demand_vs_capacity_chart(df: pd.DataFrame) -> go.Figure:
    """Stacked area of forecasted hours vs capacity line."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["Week"], y=df["Total Forecasted Hours"],
        fill="tozeroy", name="Forecasted Demand",
        line=dict(color="#636EFA"), fillcolor="rgba(99,110,250,0.3)",
    ))

    fig.add_trace(go.Scatter(
        x=df["Week"], y=df["Team Capacity"],
        name="Team Capacity",
        line=dict(color="#EF553B", width=2, dash="dash"),
    ))

    if df["Run Rate Target"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["Week"], y=df["Run Rate Target"],
            name="80% Target",
            line=dict(color="#00CC96", width=2, dash="dot"),
        ))

    if df["Actual Run Rate"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["Week"], y=df["Actual Run Rate"],
            name="Actual Run Rate",
            line=dict(color="#AB63FA", width=2),
        ))

    # Mark holiday weeks
    holidays = df[df["Holiday"] == True]
    for _, h in holidays.iterrows():
        fig.add_vline(x=h["Week"], line_dash="dot", line_color="gray", opacity=0.3)

    fig.update_layout(
        title="Demand vs Capacity (Weekly Hours)",
        xaxis_title="Week",
        yaxis_title="Hours",
        hovermode="x unified",
        height=450,
    )
    return fig


def utilization_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap of consultant utilization by week."""
    if df.empty:
        return go.Figure()

    pivot = df.pivot_table(index="Consultant", columns="Week", values="Utilization %", aggfunc="first")
    pivot = pivot.fillna(0)

    # Custom colorscale: low=red, target=green, over=orange
    colorscale = [
        [0.0, "#FFFFFF"],      # 0% white
        [0.25, "#FFF3CD"],     # 25% light yellow
        [0.5, "#D4EDDA"],      # 50% light green
        [0.8, "#28A745"],      # 80% green (target)
        [1.0, "#DC3545"],      # 100%+ red (overloaded)
    ]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[d.strftime("%m/%d") for d in pivot.columns],
        y=pivot.index,
        colorscale=colorscale,
        zmin=0, zmax=120,
        colorbar=dict(title="Util %"),
        hovertemplate="Consultant: %{y}<br>Week: %{x}<br>Utilization: %{z:.0f}%<extra></extra>",
    ))

    fig.update_layout(
        title="Consultant Utilization Heatmap",
        xaxis_title="Week",
        yaxis_title="",
        height=max(300, len(pivot.index) * 35),
    )
    return fig


def team_util_trend_chart(df: pd.DataFrame) -> go.Figure:
    """Line chart of team utilization over time vs 80% target."""
    fig = go.Figure()

    if df["Actual Util"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["Week"], y=df["Actual Util"] * 100,
            name="Actual Utilization",
            line=dict(color="#636EFA", width=2),
        ))

    if df["Util to Target"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=df["Week"], y=df["Util to Target"] * 100,
            name="Util to 80% Target",
            line=dict(color="#AB63FA", width=2),
        ))

    fig.add_hline(y=80, line_dash="dash", line_color="green",
                  annotation_text="80% Target", annotation_position="top right")

    fig.update_layout(
        title="Team Utilization Trend",
        xaxis_title="Week",
        yaxis_title="Utilization %",
        hovermode="x unified",
        height=350,
    )
    return fig


def consultant_weekly_breakdown(consultant_name: str, raw_weekly: pd.DataFrame) -> go.Figure:
    """Stacked bar: billable vs internal vs available per week for one consultant."""
    person = raw_weekly[raw_weekly["Resource"] == consultant_name].copy()
    if person.empty:
        return go.Figure().update_layout(title=f"No timecard data for {consultant_name}")

    person = person.sort_values("Week Start")
    person["Internal Hours"] = person["total_hours"] - person["billable_hours"]
    person["Available Hours"] = (40 - person["total_hours"]).clip(lower=0)
    person["Week"] = pd.to_datetime(person["Week Start"])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=person["Week"], y=person["billable_hours"],
                         name="Billable", marker_color="#28A745"))
    fig.add_trace(go.Bar(x=person["Week"], y=person["Internal Hours"],
                         name="Internal", marker_color="#6C757D"))
    fig.add_trace(go.Bar(x=person["Week"], y=person["Available Hours"],
                         name="Available", marker_color="#E9ECEF"))

    fig.update_layout(
        barmode="stack",
        title=f"Weekly Hours: {consultant_name}",
        xaxis_title="Week",
        yaxis_title="Hours",
        height=400,
    )
    return fig


def fte_demand_capacity_chart(df: pd.DataFrame) -> go.Figure:
    """FTE demand vs capacity over time with delta shading."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["Week"], y=df["FTEs Available"],
        name="FTEs Available",
        line=dict(color="#28A745", width=2),
        fill="tozeroy", fillcolor="rgba(40,167,69,0.1)",
    ))

    fig.add_trace(go.Scatter(
        x=df["Week"], y=df["FTE Demand"],
        name="FTE Demand (75%+ Opps)",
        line=dict(color="#DC3545", width=2),
        fill="tozeroy", fillcolor="rgba(220,53,69,0.1)",
    ))

    fig.add_trace(go.Scatter(
        x=df["Week"], y=df["Delta Capacity"],
        name="Delta (Surplus/Deficit)",
        line=dict(color="#FFC107", width=2, dash="dash"),
    ))

    fig.add_hline(y=0, line_color="black", line_width=1)

    fig.update_layout(
        title="FTE Demand vs Capacity Over Time",
        xaxis_title="Week",
        yaxis_title="FTEs",
        hovermode="x unified",
        height=450,
    )
    return fig


def before_after_util_chart(
    consultant_names: list,
    current_utils: list,
    proposed_utils: list,
) -> go.Figure:
    """Grouped bar chart comparing utilization before and after optimizer assignments."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=consultant_names, y=[u * 100 for u in current_utils],
        name="Current", marker_color="#636EFA",
    ))
    fig.add_trace(go.Bar(
        x=consultant_names, y=[u * 100 for u in proposed_utils],
        name="After Assignment", marker_color="#00CC96",
    ))

    fig.add_hline(y=80, line_dash="dash", line_color="red",
                  annotation_text="80% Target")

    fig.update_layout(
        barmode="group",
        title="Utilization Impact: Before vs After",
        xaxis_title="Consultant",
        yaxis_title="Utilization %",
        height=400,
    )
    return fig


def assignment_gantt(assignments_df: pd.DataFrame) -> go.Figure:
    """Gantt-style chart showing consultant assignments over time."""
    if assignments_df.empty:
        return go.Figure()

    fig = px.timeline(
        assignments_df,
        x_start="Start",
        x_end="End",
        y="Consultant",
        color="Project",
        hover_data=["Hours/Week", "Fraction"],
        title="Proposed Assignments Timeline",
        height=max(300, len(assignments_df["Consultant"].unique()) * 50),
    )
    fig.update_yaxes(autorange="reversed")
    return fig
