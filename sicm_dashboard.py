# sicm_dashboard.py — Stabilization Bed Facilities Occupancy Rates

from pathlib import Path
from functools import lru_cache
from time import perf_counter

from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    MONTH_NAMES,
    load_sql_query,
    apply_standard_line_layout,
)

register_template()

def _clean_column_name(value) -> str:
    return str(value).strip().strip("'").strip('"').lower()


def _load_sicm_raw():
    sql = load_sql_query("load_sicm_occupancy")
    df = execute_query(sql)
    print(f"load_sicm_occupancy returned {len(df):,} rows")
    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("SICM query returned 0 rows.")

    df.columns = [_clean_column_name(c) for c in df.columns]
    #print(f"sicm data: {df}")

    required_cols = ["date", "facility", "occupancy_rate"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise RuntimeError(f"SICM data missing required columns: {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()

    # Strip the '%' symbol, convert to numeric, and convert to a decimal (e.g. 79.91 -> 0.7991)
    df["occupancy_rate"] = df["occupancy_rate"].astype(str).str.replace("%", "", regex=False)
    df["occupancy_rate"] = pd.to_numeric(df["occupancy_rate"], errors="coerce") / 100.0
    df["facility"] = df["facility"].astype(str).str.strip()
    df["county"] = df["facility"]
    df["year"] = df["date"].dt.year.astype("Int64")
    df["month_num"] = df["date"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)

    return df


@lru_cache(maxsize=1)
def _load_sicm_dataframe_cached():
    return _load_sicm_raw()


def load_sicm_dataframe():
    return _load_sicm_dataframe_cached().copy()

def _build_period_frame(dff, view):
    # Data is already monthly, just need to create the period label
    dff = dff.copy()
    dff["period"] = dff["year"].astype(int).astype(str) + ", " + dff["month"]
    dff = dff.sort_values(["year", "month_num", "facility"])
    period_title = "Month of Service"
    return dff, period_title

def _line_chart(grouped, period_title, chart_title="Occupancy Rate"):
    occupancy_values = pd.to_numeric(grouped["occupancy_rate"], errors="coerce").dropna()
    y_min = float(occupancy_values.min()) if not occupancy_values.empty else 0.0
    y_min = max(0.0, y_min - 0.02)

    fig = px.line(
        grouped,
        x="date",  # Native date column
        y="occupancy_rate",
        color="facility",
        markers=True,
        labels={"date": period_title, "occupancy_rate": "Occupancy Rate", "facility": "Facility"},
    )
    fig.update_layout(legend_title_text="Facility")
    fig.update_traces(hovertemplate="%{y:.1%}<extra></extra>")

    # 1. Apply your company's standard layout FIRST
    apply_standard_line_layout(
        fig,
        yaxis=dict(title="Occupancy Rate", tickformat=".0%", range=[y_min, 1.05],
            tickmode="array"
        ),
        legend=dict(x=0.5, xanchor="center"),
    )
    fig.update_layout(title="Stabilization Bed Facility Occupancy Rates")

    # 2. Force our X-Axis and Hover settings SECOND (so they can't be overwritten)
    if period_title == "Date of Service":
        fig.update_xaxes(
            type="date",
            tickmode="linear",
            dtick=5 * 24 * 60 * 60 * 1000,
            tickformat="%Y-%m-%d",
            tickangle=-45,
            tickfont={"size": 10},
        )
        fig.update_layout(margin=dict(b=100), legend=dict(x=0.5, xanchor="center", y=-0.22))
        
    elif period_title == "Month of Service":
        unique_dates = grouped["date"].drop_duplicates().sort_values().tolist()
        tickvals = []
        ticktext = []
        
        for i, d in enumerate(unique_dates):
            tickvals.append(d)
            short_month = d.strftime("%b")
            year = d.strftime("%Y")
            
            if i == 0 or i == len(unique_dates) - 1:
                ticktext.append(f"{short_month}<br>{year}")
            else:
                ticktext.append(f"{short_month}")
                
        fig.update_xaxes(
            type="date",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=0,
            hoverformat="%B, %Y"
        )

    # Force the unified hovermode
    fig.update_layout(hovermode="x unified")

    return fig


def build_layout():
    # 1. Load the data
    df_raw = load_sicm_dataframe()
    
    # 2. Process the data and generate the figure
    dff = df_raw.copy()
    facility_grouped, period_title = _build_period_frame(dff, "month")
    facility_fig = _line_chart(facility_grouped, period_title)

    # 3. Build and return the layout, passing the figure directly
    return dbc.Container(
        [
            html.Div(
                [
                    html.H5("Stabilization Bed Facility Occupancy Rates", id="sicm-facility-chart-title", className="plot-card-header mb-2 text-center", style={"display": "none"}),
                    html.H6("Occupancy Rate = Average of Daily Occupancy Rates.  These facilities only host adults", id="sicm-facility-chart-subtitle", className="plot-card-header mb-2 text-center"),

                    dcc.Graph(
                        id="sicm-facility-line-chart",
                        figure=facility_fig,  # Passing the generated figure here
                        style={"width": "100%"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
        ],
        fluid=True,
    )

# Instantiate the layout
layout = build_layout()
