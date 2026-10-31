# crisis_mobile_outreach_dashboard.py — Crisis Mobile Outreach referrals page

import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Output, Input, callback
import plotly.express as px

from config import USE_MSSQL
from db_utils import execute_query
from dashboard_utils import (
    load_sql_query,
    format_count_display,
    compute_adaptive_horizontal_bar_height,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
)
from section_texts import SECTION_TEXTS
from theme import register_template

register_template()


def load_cmo_referrals_dataframe():
    """
    Load pre-aggregated referral destinations for Crisis Mobile Outreach.
    The query now returns: referral_destination, cnt, pct.
    """
    sql = load_sql_query("load_crisis_mobile_outreach")
    df = execute_query(sql)
    print(f"load_crisis_mobile_outreach returned {len(df):,} rows")

    if df.empty:
        raise RuntimeError("load_crisis_mobile_outreach returned 0 rows.")

    return df


def load_cmo_last_updated_value():
    """Fetch the most recent DispatchDate from the source table for Last Updated."""
    query_name = (
        "load_crisis_mobile_outreach_last_updated"
        if USE_MSSQL
        else "load_crisis_mobile_outreach_last_updated_sqlite"
    )
    sql = load_sql_query(query_name)
    result = execute_query(sql)
    if result.empty or "last_updated" not in result.columns:
        return None

    parsed = pd.to_datetime(result.iloc[0]["last_updated"], errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


# --- Load Data ---
df_agg = load_cmo_referrals_dataframe()
last_updated_value = load_cmo_last_updated_value()
sidebar_text = SECTION_TEXTS.get("crisis-mobile-outreach", [])


# ----------------------------
# Layout
# ----------------------------

def layout():
    """
    Defines the simplified full-width layout for the report.
    The bar chart takes the full width, and the helper text and last updated
    date are moved underneath. The title is centered.
    """
    return dbc.Container(
        [
            html.Div(id="cmo-trigger", style={"display": "none"}),
            dbc.Row(
                dbc.Col(
                    [
                        # FIX: Replaced graph_block to allow for centering the title
                        html.H3(
                            "Referral Destinations for Crisis Mobile Outreach Clients (past 6 months)",
                            style={'textAlign': 'center', 'display': 'none'}
                        ),
                        dcc.Graph(id="cmo-referral-bar"),
                        html.P(
                            "Bar chart showing referral destinations for Crisis Mobile Outreach clients (past 6 months).",
                            className="visually-hidden",
                        ),
                    ],
                    width=12,
                )
            ),
            dbc.Row(
                dbc.Col(
                    [
                        html.Hr(className="my-4"),
                        # FIX: Use a flexbox container to align items on one line
                        html.Div(
                            [
                                html.Div(
                                    [html.P(paragraph, className="mb-0") for paragraph in sidebar_text],
                                    className="text-muted"
                                ),
                                html.P(
                                    f"Last Updated: {last_updated_value}",
                                    className="text-muted small mb-0"
                                ) if last_updated_value else None,
                            ],
                            className="d-flex justify-content-between align-items-center"
                        )
                    ],
                    width=12,
                )
            ),
        ],
        fluid=True,
    )


# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("cmo-referral-bar", "figure"),
    Input("cmo-trigger", "children"),
)
def update_dashboard(_):
    """
    Simplified callback that generates the bar chart from pre-aggregated data,
    using the new column names from the query (referral_destination, cnt, pct).
    """
    dff = df_agg.copy()

    dff = dff.sort_values("cnt", ascending=False).copy()
    dff["cnt_display"] = dff["cnt"].apply(format_count_display)
    
    dff["bar_label"] = dff.apply(
        lambda row: f"{row['pct']:.1f}% ({row['cnt_display']})",
        axis=1,
    )

    y_order = dff["referral_destination"].tolist()[::-1]

    fig = px.bar(
        dff,
        x="pct",
        y="referral_destination",
        orientation="h",
        text="bar_label",
        labels={
            "pct": "Percent of Total",
            "referral_destination": "Referral Destination",
        },
    )
    apply_standard_bar_layout(
        fig,
        xaxis=dict(title="Percent of Total", ticksuffix="%", rangemode="tozero"),
        yaxis=dict(title="Referral Destination", categoryorder="array", categoryarray=y_order),
        height=compute_adaptive_horizontal_bar_height(len(dff)),
    )
    apply_standard_single_series_bar_trace(
        fig,
        customdata=dff[["cnt_display"]],
        hovertemplate="%{y}: %{x:.1f}% (%{customdata[0]} clients)<extra></extra>",
    )
    fig.update_layout(title="Referral Destinations for Crisis Mobile Outreach")

    return fig