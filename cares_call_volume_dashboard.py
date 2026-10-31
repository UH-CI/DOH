# cares_call_volume_dashboard.py — Hawaiʻi CARES Crisis Center Volume page

from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    MONTH_NAMES,
    load_sql_query,
    make_kpi_card,
    make_left_sidebar,
    make_right_summary_tables_col,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    make_filters_card,
    dropdown_filter,
    format_count_display,
    opts_list,
    sort_opts,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
    create_styled_table,
)

register_template()

# ----------------------------
# Data load
# ----------------------------

def load_cares_dataframe():
    sql = load_sql_query("load_cares_call_volume")
    df = execute_query(sql)
    print(f"load_cares_call_volume returned {len(df):,} rows")
    if df.empty:
        raise RuntimeError("load_cares_call_volume query returned 0 rows.")

    # Normalize column names so the dashboard works with either raw or pre-aggregated SQL.
    col_lookup = {c.lower(): c for c in df.columns}

    date_col = col_lookup.get("day") or col_lookup.get("date")
    if not date_col:
        raise RuntimeError("load_cares_call_volume must return a Date/day column.")
    if date_col != "day":
        df = df.rename(columns={date_col: "day"})

    line_col = col_lookup.get("origin_of_call") or col_lookup.get("line")
    if line_col:
        if line_col != "origin_of_call":
            df = df.rename(columns={line_col: "origin_of_call"})
    else:
        df["origin_of_call"] = "Unknown"

    count_col = col_lookup.get("count_of_users")
    if count_col and count_col != "count_of_users":
        df = df.rename(columns={count_col: "count_of_users"})

    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df = df[df["day"].notna()].copy()

    if "count_of_users" in df.columns:
        df["count_of_users"] = pd.to_numeric(df["count_of_users"], errors="coerce").fillna(0)
    else:
        # Raw call-level rows: each row is one contact.
        df["count_of_users"] = 1

    df["origin_of_call"] = (
        df["origin_of_call"]
        .astype(str)
        .str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )

    df["year"] = df["day"].dt.year.astype("Int64")
    df["month_num"] = df["day"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)
    return df


df_raw = load_cares_dataframe()
last_updated_value = compute_last_updated_value(df_raw)

year_opts = sort_opts(df_raw["year"])
month_nums_present = sorted(df_raw["month_num"].dropna().unique().tolist())
month_opts = [MONTH_NAMES[m] for m in month_nums_present]
crisis_line_opts = sort_opts(df_raw["origin_of_call"])

# ----------------------------
# UI Components
# ----------------------------

reset_button = dbc.Button(
    "Reset All Filters",
    id="cares-reset-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

kpi_card = make_kpi_card(
    label="Total Crisis Center Contacts",
    count_id="cares-kpi-total",
)

# "Year View / Month View" toggle rendered as a pill button group.
view_toggle_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("View By", className="mb-2 text-center"),
            dbc.RadioItems(
                id="cares-view-toggle",
                options=[
                    {"label": "Year", "value": "year"},
                    {"label": "Month", "value": "month"},
                ],
                value="month",
                class_name="spaced-radio-buttons d-flex justify-content-center gap-3",
                input_class_name="btn-check",
                label_class_name="btn btn-outline-success",
                label_checked_class_name="btn-success text-white active",
            ),
        ]
    ),
    className="mb-3",
)

filters_card = make_filters_card(
    card_id="cares-filters",
    title="Filter Data",
    filters=[
        dropdown_filter(
            "Calendar Year",
            "cares-year-filter",
            options=opts_list(year_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
        dropdown_filter(
            "Month",
            "cares-month-filter",
            options=opts_list(month_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
        dropdown_filter(
            "Crisis Line",
            "cares-crisis-line-filter",
            options=opts_list(crisis_line_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
    ],
)

from section_texts import SECTION_TEXTS
cares_sidebar_text = SECTION_TEXTS.get("cares-call-volume", [])

# ----------------------------
# Layout
# ----------------------------

def layout():
    left_col = make_left_sidebar(
        kpi_card,
        reset_button,
        filters_card,
        view_toggle_card=view_toggle_card,
        helper_text=cares_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    center_col = dbc.Col(
        [
            html.Div(
                [
                    html.H5("Number of Calls", id="cares-bar-chart-title", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="cares-bar-chart",
                        style={"width": "100%"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
            html.P(
                "Horizontal bar chart showing total crisis center contacts.",
                className="visually-hidden",
            ),
        ],
        xs=12, md=6,
    )

    right_col = make_right_summary_tables_col(
        [
            ("Crisis Line", "cares-crisis-table"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container(
        dbc.Row([left_col, center_col, right_col]),
        fluid=True,
    )

# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("cares-year-filter", "value"),
    Output("cares-month-filter", "value"),
    Output("cares-crisis-line-filter", "value"),
    Input("cares-reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_cares_filters(_n_clicks):
    return None, None, None


@callback(
    Output("cares-bar-chart", "figure"),
    Output("cares-kpi-total", "children"),
    Output("cares-crisis-table", "children"),
    Input("cares-view-toggle", "value"),
    Input("cares-year-filter", "value"),
    Input("cares-month-filter", "value"),
    Input("cares-crisis-line-filter", "value"),
)
def update_dashboard(view, sel_years, sel_months, sel_crisis):
    dff = df_raw.copy()

    # Apply filters (None / empty → show all)
    if sel_years:
        selected_years_numeric = (
            pd.to_numeric(pd.Series(sel_years), errors="coerce")
            .dropna()
            .astype("Int64")
            .tolist()
        )
        dff = dff[dff["year"].isin(selected_years_numeric)]
    if sel_months:
        dff = dff[dff["month"].isin(sel_months)]
    if sel_crisis:
        dff = dff[dff["origin_of_call"].isin(sel_crisis)]

    total = int(dff["count_of_users"].sum())

    # --- Bar chart ---
    if view == "year":
        grouped = (
            dff.groupby("year", as_index=False)["count_of_users"]
            .sum()
            .sort_values("year", ascending=True)
        )
        grouped["y_label"] = grouped["year"].astype(str)
        y_col = "y_label"
        y_title = "Year"
    else:
        grouped = (
            dff.groupby(["year", "month_num", "month"], as_index=False)["count_of_users"]
            .sum()
            .sort_values(["year", "month_num"], ascending=True)
        )
        grouped["y_label"] = grouped["year"].astype(str) + ", " + grouped["month"]
        y_col = "y_label"
        y_title = "Year, Month"

    n_bars = len(grouped)
    chart_height = compute_adaptive_horizontal_bar_height(
        n_bars,
    )

    # Build the display order: categoryarray[0] = bottom, last = top.
    # Ascending order means oldest at bottom, newest at top.
    y_order = grouped[y_col].tolist()

    fig = px.bar(
        grouped,
        x="count_of_users",
        y=y_col,
        orientation="h",
        text="count_of_users",
        labels={"count_of_users": "Number of Calls", y_col: y_title},
    )
    apply_standard_bar_layout(
        fig,
        xaxis=dict(title="Number of Calls"),
        yaxis=dict(
            title=y_title,
            categoryorder="array",
            categoryarray=y_order,
            tickmode="array",
            tickvals=y_order,
            ticktext=y_order,
        ),
        height=chart_height,
    )
    apply_standard_single_series_bar_trace(fig)
    fig.update_layout(title="Number of Calls")
    crisis_totals = (
        dff.groupby("origin_of_call", as_index=False)["count_of_users"]
        .sum()
        .rename(columns={"origin_of_call": "Crisis Line", "count_of_users": "Total Calls"})
    )
    
    # Determine which crisis lines to show based on filter
    categories_to_show = crisis_line_opts
    if sel_crisis:
        categories_to_show = sel_crisis
    
    # Ensure all selected crisis lines show, even if zero
    full_categories = pd.DataFrame({"Crisis Line": categories_to_show})
    crisis_totals = full_categories.merge(crisis_totals, on="Crisis Line", how="left")
    crisis_totals["Total Calls"] = crisis_totals["Total Calls"].fillna(0).astype(int)
    
    # Sort by count descending
    crisis_totals = crisis_totals.sort_values("Total Calls", ascending=False)
    
    crisis_totals["Total Calls"] = crisis_totals["Total Calls"].apply(format_count_display)

    table = create_styled_table(crisis_totals)

    return fig, format_count_display(total), table
