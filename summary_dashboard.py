# summary_dashboard.py — Summary Dashboard with 3x4 grid

from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback, clientside_callback, ALL
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    load_sql_query,
    sort_opts,
    opts_list,
    make_kpi_card,
    format_count_display,
    apply_standard_line_layout,
    MONTH_NAMES,
    compute_last_updated_value,
)

register_template()

# ----------------------------
# Data Loading
# ----------------------------

def load_wonder_overview_data():
    """Load wonder deaths overview data."""
    sql = load_sql_query("load_overview_wonder_deaths")
    df = execute_query(sql)
    print(f"load_overview_wonder_deaths returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    return df


def load_wonder_by_substance_data():
    """Load wonder deaths by substance data."""
    sql = load_sql_query("load_overview_wonder_deaths_by_substance")
    df = execute_query(sql)
    print(f"load_overview_wonder_deaths_by_substance returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if "substance" in df.columns:
        df["substance"] = df["substance"].astype(str).str.strip()
    return df


def load_discharges_su_data():
    """Load substance use discharges data."""
    sql = load_sql_query("load_overview_discharges_su_with_substance")
    df = execute_query(sql)
    print(f"load_overview_discharges_su_with_substance returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if "substance" in df.columns:
        df["substance"] = df["substance"].astype(str).str.strip()
    return df


def load_discharges_cooccurring_data():
    """Load co-occurring substance use and mental health discharges data."""
    sql = load_sql_query("load_overview_discharges_su_cooccurring_summary")
    df = execute_query(sql)
    print(f"load_overview_discharges_su_cooccurring_summary returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if "diagnosis" in df.columns:
        df["diagnosis"] = df["diagnosis"].astype(str).str.strip()
    return df


def load_cares_data():
    """Load crisis calls data."""
    sql = load_sql_query("load_cares_call_volume")
    df = execute_query(sql)
    print(f"load_cares_call_volume returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")
    
    # Normalize column names
    col_lookup = {c.lower(): c for c in df.columns}
    date_col = col_lookup.get("day") or col_lookup.get("date")
    if date_col and date_col != "day":
        df = df.rename(columns={date_col: "day"})
    
    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df = df[df["day"].notna()].copy()
    
    # Handle count column
    count_col = col_lookup.get("count_of_users")
    if count_col and count_col != "count_of_users":
        df = df.rename(columns={count_col: "count_of_users"})
    
    if "count_of_users" in df.columns:
        df["count_of_users"] = pd.to_numeric(df["count_of_users"], errors="coerce").fillna(0)
    else:
        df["count_of_users"] = 1
    
    df["year"] = df["day"].dt.year.astype("Int64")
    df["month_num"] = df["day"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)
    
    return df


# Load all datasets at startup
print("Loading summary dashboard data...")
df_wonder = load_wonder_overview_data()
df_wonder_substance = load_wonder_by_substance_data()
df_discharges_su = load_discharges_su_data()
df_cooccurring = load_discharges_cooccurring_data()
df_cares = load_cares_data()

# Get the most recent month/year from CARES data
cares_by_month = df_cares.groupby(["year", "month_num", "month"])["count_of_users"].sum().reset_index()
cares_by_month = cares_by_month.sort_values(["year", "month_num"], ascending=False)
if not cares_by_month.empty:
    most_recent_cares = cares_by_month.iloc[0]
    most_recent_month = most_recent_cares["month"]
    most_recent_year = most_recent_cares["year"]
    most_recent_calls = int(most_recent_cares["count_of_users"])
else:
    most_recent_month = "N/A"
    most_recent_year = "N/A"
    most_recent_calls = 0

# Calculate last updated from all datasets
last_updated_value = compute_last_updated_value(pd.concat([
    df_wonder, df_wonder_substance, df_discharges_su, df_cooccurring, df_cares
]))


# ----------------------------
# Reusable Components
# ----------------------------

def create_area_chart_card(
    card_id: str,
    title: str,
    data: pd.DataFrame,
    y_column: str,
    group_column: str = None,
    button_text: str = "Explore More",
    button_url: str = "/",
    fill_color: str = "#42a894",
    button_color: str = "#197781",
):
    """
    Create a reusable area chart card with a button at the bottom.
    
    Args:
        card_id: Unique identifier for the card
        title: Title to display
        data: DataFrame with 'year' column and y_column
        y_column: Name of column to plot on y-axis
        group_column: Optional column to group by (for multiple lines)
        button_text: Text for the explore button
        button_url: URL the button navigates to
        fill_color: Color for the area fill
        button_color: Background color for button
    """
    
    # Ensure data is sorted by year
    if "year" in data.columns:
        plot_data = data.sort_values("year").copy()
    else:
        plot_data = data.copy()
    
    # Calculate total sum for annotation
    total = plot_data[y_column].sum()
    total_display = format_count_display(total)
    
    # Create the area chart
    if group_column and group_column in plot_data.columns:
        fig = px.area(
            plot_data,
            x="year",
            y=y_column,
            color=group_column,
            labels={"year": "Year", y_column: "Count"},
        )
        fig.update_traces(fillcolor=fill_color, opacity=0.7)
    else:
        fig = px.area(
            plot_data,
            x="year",
            y=y_column,
            labels={"year": "Year", y_column: "Count"},
        )
        fig.update_traces(fillcolor=fill_color, opacity=0.7, line=dict(color=fill_color, width=3))
    
    # Apply standard styling
    apply_standard_line_layout(fig)
    fig.update_layout(
        height=300,
        hovermode="x unified",
        margin=dict(b=60, t=20, l=40, r=20),
    )
    
    # Remove legend for single-series charts
    if not group_column or group_column not in plot_data.columns:
        fig.update_layout(showlegend=False)
    
    # Add total sum annotation in the center of the chart
    fig.add_annotation(
        text=f"<b>{total_display}</b>",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=32, color="rgba(66, 168, 148, 0.8)"),
        bgcolor="rgba(255, 255, 255, 0.7)",
        bordercolor="#42a894",
        borderwidth=2,
        borderpad=10,
        align="center",
    )
    
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        html.H5(title, className="card-title mb-0"),
                        style={"height": "60px", "overflow": "hidden", "display": "flex", "alignItems": "center"},
                    ),
                    dcc.Graph(
                        id={"type": "summary-chart", "index": card_id},
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": "300px", "marginBottom": "10px"},
                    ),
                    dcc.Link(
                        html.Button(
                            button_text,
                            className="btn w-100",
                            style={
                                "backgroundColor": button_color,
                                "color": "white",
                                "border": "none",
                                "padding": "8px 12px",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontSize": "14px",
                            },
                            title="click for more details",
                        ),
                        href=button_url,
                        style={"textDecoration": "none", "display": "block"}
                    ),
                ]
            ),
        ],
        className="mb-3",
        style={"height": "460px"},
    )


def create_kpi_card(
    card_id: str,
    title: str,
    value: str,
    button_text: str = "Explore More",
    button_url: str = "/",
    button_color: str = "#197781",
):
    """
    Create a KPI card with a button at the bottom.
    
    Args:
        card_id: Unique identifier for the card
        title: Title to display
        value: KPI value to display
        button_text: Text for the explore button
        button_url: URL the button navigates to
        button_color: Background color for button
    """
    
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        html.H5(title, className="card-title mb-0"),
                        style={"height": "60px", "overflow": "hidden", "display": "flex", "alignItems": "center"},
                    ),
                    html.Div(
                        value,
                        className="h2 fw-bold mb-3",
                        style={"textAlign": "center", "color": "#42a894", "height": "200px", "display": "flex", "alignItems": "center", "justifyContent": "center"},
                    ),
                    dcc.Link(
                        html.Button(
                            button_text,
                            className="btn w-100",
                            style={
                                "backgroundColor": button_color,
                                "color": "white",
                                "border": "none",
                                "padding": "8px 12px",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontSize": "14px",
                            },
                            title="click for more details",
                        ),
                        href=button_url,
                        style={"textDecoration": "none", "display": "block"}
                    ),
                ]
            ),
        ],
        className="mb-3",
        style={"height": "460px"},
    )


# ----------------------------
# Grid Data Preparation
# ----------------------------

# Row 1: WONDER Overdose Deaths
row1_col1_data = df_wonder.copy()
# Handle potential column name variations
if "sum" in row1_col1_data.columns:
    row1_col1_data.rename(columns={"sum": "deaths"}, inplace=True)
elif "sum(deaths)" in row1_col1_data.columns:
    row1_col1_data.rename(columns={"sum(deaths)": "deaths"}, inplace=True)

row1_col2_data = df_wonder_substance[
    df_wonder_substance["substance"].str.contains(
        "Methamphetamine and other psychostimulants with abuse potential",
        case=False,
        na=False,
        regex=False
    )
].copy()
if "sum" in row1_col2_data.columns:
    row1_col2_data.rename(columns={"sum": "deaths"}, inplace=True)
elif "sum(deaths)" in row1_col2_data.columns:
    row1_col2_data.rename(columns={"sum(deaths)": "deaths"}, inplace=True)

row1_col3_data = df_wonder_substance[
    df_wonder_substance["substance"].str.contains(
        "Fentanyl and other synthetic narcotics",
        case=False,
        na=False,
        regex=False
    )
].copy()
if "sum" in row1_col3_data.columns:
    row1_col3_data.rename(columns={"sum": "deaths"}, inplace=True)
elif "sum(deaths)" in row1_col3_data.columns:
    row1_col3_data.rename(columns={"sum(deaths)": "deaths"}, inplace=True)

row1_col4_data = df_wonder_substance[
    df_wonder_substance["substance"].str.contains(
        "Heroin",
        case=False,
        na=False,
        regex=False
    )
].copy()
if "sum" in row1_col4_data.columns:
    row1_col4_data.rename(columns={"sum": "deaths"}, inplace=True)
elif "sum(deaths)" in row1_col4_data.columns:
    row1_col4_data.rename(columns={"sum(deaths)": "deaths"}, inplace=True)

# Row 2: Substance Use Discharges
row2_col1_data = df_discharges_su.groupby("year")["num_substance"].sum().reset_index()
row2_col1_data.columns = ["year", "discharges"]

row2_col2_data = df_discharges_su[
    df_discharges_su["substance"].str.contains(
        "Other Stimulant \\(includes Methamphetamine\\)",
        case=False,
        na=False,
        regex=True
    )
].copy()
row2_col2_data = row2_col2_data.groupby("year")["num_substance"].sum().reset_index()
row2_col2_data.columns = ["year", "discharges"]

row2_col3_data = df_discharges_su[
    df_discharges_su["substance"].str.contains(
        "Cocaine",
        case=False,
        na=False,
        regex=False
    )
].copy()
row2_col3_data = row2_col3_data.groupby("year")["num_substance"].sum().reset_index()
row2_col3_data.columns = ["year", "discharges"]

row2_col4_data = df_discharges_su[
    df_discharges_su["substance"].str.contains(
        "Opioid",
        case=False,
        na=False,
        regex=False
    )
].copy()
row2_col4_data = row2_col4_data.groupby("year")["num_substance"].sum().reset_index()
row2_col4_data.columns = ["year", "discharges"]

# Row 3: Co-occurring SU & MH Discharges
row3_col1_data = df_cooccurring.groupby("year")["diagnosis_count"].sum().reset_index()
row3_col1_data.columns = ["year", "count"]

row3_col2_data = df_cooccurring[
    df_cooccurring["diagnosis"].str.contains(
        "Schizophrenia, Schizotypal, Delusional, or Other Non-mood Psychotic Disorders",
        case=False,
        na=False,
        regex=False
    )
].copy()
row3_col2_data = row3_col2_data.groupby("year")["diagnosis_count"].sum().reset_index()
row3_col2_data.columns = ["year", "count"]

row3_col3_data = df_cooccurring[
    df_cooccurring["diagnosis"].str.contains(
        "Pervasive or Specific Developmental Disorders",
        case=False,
        na=False,
        regex=False
    )
].copy()
row3_col3_data = row3_col3_data.groupby("year")["diagnosis_count"].sum().reset_index()
row3_col3_data.columns = ["year", "count"]


# ----------------------------
# Layout
# ----------------------------

layout = dbc.Container(
    [
        html.Div(
            [
                html.H2("Summary Dashboard", className="mb-4 mt-4"),
                html.Hr(),
            ]
        ),
        
        # Row 1: WONDER Overdose Deaths
        dbc.Row(
            [
                dbc.Col(
                    create_area_chart_card(
                        "row1-col1",
                        "Overdose Deaths",
                        row1_col1_data,
                        y_column="deaths",
                        button_url="/wonder-overview",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row1-col2",
                        "Methamphetamine & other Psychostimulant Related Overdose Deaths",
                        row1_col2_data,
                        y_column="deaths",
                        button_url="/wonder-breakdown",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row1-col3",
                        "Fentanyl & Other Synthetic Narcotic Related Overdose Deaths",
                        row1_col3_data,
                        y_column="deaths",
                        button_url="/wonder-breakdown",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row1-col4",
                        "Heroin & Other Opioid Related Overdose Deaths",
                        row1_col4_data,
                        y_column="deaths",
                        button_url="/wonder-breakdown",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
            ],
            className="g-3 mb-4"
        ),
        
        # Row 2: Substance Use Discharges
        dbc.Row(
            [
                dbc.Col(
                    create_area_chart_card(
                        "row2-col1",
                        "Substance Use Discharges",
                        row2_col1_data,
                        y_column="discharges",
                        button_url="/discharges-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row2-col2",
                        "Methamphetamine & Other Stimulant Discharges",
                        row2_col2_data,
                        y_column="discharges",
                        button_url="/discharges-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row2-col3",
                        "Cocaine Related Discharges",
                        row2_col3_data,
                        y_column="discharges",
                        button_url="/discharges-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row2-col4",
                        "Opioid Related Discharges",
                        row2_col4_data,
                        y_column="discharges",
                        button_url="/discharges-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
            ],
            className="g-3 mb-4"
        ),
        
        # Row 3: Co-occurring and CARES
        dbc.Row(
            [
                dbc.Col(
                    create_area_chart_card(
                        "row3-col1",
                        "Co-occurring SU & MH Related Discharges",
                        row3_col1_data,
                        y_column="count",
                        button_url="/discharges-cooccurring-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row3-col2",
                        "Psychotic Related Discharges",
                        row3_col2_data,
                        y_column="count",
                        button_url="/discharges-cooccurring-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_area_chart_card(
                        "row3-col3",
                        "Developmental Related Discharges",
                        row3_col3_data,
                        y_column="count",
                        button_url="/discharges-cooccurring-su",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
                dbc.Col(
                    create_kpi_card(
                        "row3-col4",
                        f"Hawaiʻi CARES Crisis Calls for {most_recent_month}, {most_recent_year}",
                        format_count_display(most_recent_calls),
                        button_url="/cares-call-volume",
                    ),
                    xs=12, sm=6, lg=3, className="mb-3"
                ),
            ],
            className="g-3 mb-4"
        ),
    ],
    fluid=True,
    className="p-3",
)
