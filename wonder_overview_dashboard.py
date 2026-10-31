from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    apply_year_filter,
    make_kpi_card,
    make_left_sidebar,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    make_filters_card,
    checklist_filter,
    statewide_first,
    format_count_display,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
    apply_standard_line_layout,
    load_sql_query,
    sort_opts,
)
import json

register_template()

# ----------------------------
# Data helpers
# ----------------------------

def load_wonder_overview_df_from_db():
    """
    This helper:
      1. Loads the main SQL query by name.
      2. Connects to the database and runs the query.
      3. Cleans up some columns so the rest of the app is easier to write.

    Why: having this in one place avoids repeating the same database
    logic in multiple callbacks.
    
    Note: Uses either SQLite or MSSQL automatically based on config.
    """
    
    sql = load_sql_query("load_wonder_overview")
    
    # Execute query using db_utils (automatically uses correct database)
    df = execute_query(sql)
    print(f"load_wonder_overview returned {len(df):,} rows")

    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")

    # Make the year column numeric when possible so graphs treat it as numbers
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # For these columns, replace missing values with "Unknown"
    # so we don't get blank labels in filters and tables.
    for col in ["county", "year"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")
    return df

# Load the full dataset once at startup.
# The callbacks will reuse this instead of hitting the database every time.
df_raw = load_wonder_overview_df_from_db()
last_updated_value = compute_last_updated_value(df_raw)

# Count number of deaths in wonder_overview.csv "deaths" column
total_unique = df_raw["deaths"].count()

# Build the lists of choices for each filter only if the column exists.
# Why: this makes the code more flexible if the data shape changes later.
wonder_county_opts  = sort_opts(df_raw["county"])                           if "county"  in df_raw.columns else []
wonder_year_opts    = sort_opts(df_raw["year"])                              if "year"    in df_raw.columns else []

def opts_list(values):
    """
    Turn a simple list of values into the format Dash expects for
    drop-down choices (label + value).
    """
    return [{"label": v, "value": v} for v in values]


# ----------------------------
# Reusable graph block (Tools toggle + title + graph)
# ----------------------------

def graph_block(base_id: str, title_text: str, height_px: str | None = None):
    """
    Make a standard "card" that holds:
      - a hidden store that remembers if the tools are on/off
      - a small Tools button that the user clicks
      - a title for the plot
      - the actual graph area

    Why: we use this pattern for several plots, so this function keeps
    the layout consistent and avoids repeating the same code over and over.
    """
    return html.Div(
        [
            *([html.H5(title_text, id=f"{base_id}-title", className="plot-card-header mb-2")] if title_text else []),
            dcc.Graph(
                id=base_id,
                style=({"height": height_px, "width": "100%"} if height_px else {"width": "100%"}),
                config={"displayModeBar": True, "displaylogo": False},
            ),
        ],
        className="mb-4",
        # This makes sure the tools bar is never cut off visually.
        style={"overflow": "visible"}
    )

# ----------------------------
# UI
# ----------------------------

# This link helps keyboard and screen reader users jump straight to the filters.
skip_link = html.A(
    "Skip to filters",
    href="#wonder-overview-filters",
    className="visually-hidden-focusable",
    tabIndex=0
)

# Big green card that shows the total number of discharges.
# Why: gives users a quick "at a glance" number when they open the page.
kpi_card = make_kpi_card(
    label="Number of Unintentional or Undetermined Overdose Deaths",
    count_id="wonder-kpi-deaths",
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="wonder-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Card holding all the filter controls down the left side.
# Each filter uses the options we built from the data above.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="wonder-overview-filters",
    title="Filter Data",
    filters=[
        checklist_filter(
            "County",
            "wonder-county-filter",
            options=opts_list(wonder_county_opts),
            value=[],
            labelStyle={"display": "block", "marginBottom": "0.25rem"},
            inputStyle={"marginRight": "0.4rem"},
            persistence="wonder-overview-county-filter",
            persistence_type="session",
        ),
        checklist_filter(
            "Calendar Year",
            "wonder-year-filter",
            options=opts_list(wonder_year_opts),
            value=[],
            labelStyle={"display": "block", "marginBottom": "0.25rem"},
            inputStyle={"marginRight": "0.4rem"},
            persistence="wonder-overview-year-filter",
            persistence_type="session",
        ),
    ],
)

from section_texts import SECTION_TEXTS
wonder_overview_sidebar_text = SECTION_TEXTS.get("wonder-overview", [])

def layout_for(
    is_mobile: bool = False,
    show_deaths: bool = True,
):
    """
    Build the full page layout, with slightly different heights if we
    are on a phone vs a larger screen.

    Why: on small screens we want taller plots so they are easier to read,
    but on desktops shorter plots look better side-by-side.
    """
    # Adjust plot heights depending on screen size.
    line_h  = "55vh" if is_mobile else "360px"
    bar_h = (
        "55vh"
        if is_mobile
        else f"{compute_adaptive_horizontal_bar_height(len(wonder_county_opts))}px"
    )

    # Left column: KPI, reset button, and filters.
    left_col = make_left_sidebar(
        kpi_card,
        reset_filters_button,
        filters_card,
        helper_text=wonder_overview_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    # Center column: the main line and bar charts.
    center_col = dbc.Col(
        [
            dbc.Row([
                graph_block("wonder-line-deaths", "", line_h),
                html.P("Line chart showing deaths by calendar year.", className="visually-hidden"),
            ]),
            dbc.Row([
                graph_block("wonder-bar-deaths", ""),
                html.P("Bar chart showing deaths by county.", className="visually-hidden"),
            ]),
        ],
        xs=12, md=8
    )

    # Wrap everything in a fluid container so it stretches with the screen.
    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col], className="g-3"),
            id="wonder-overview-section",
            style={} if show_deaths else {"display": "none"}
        ),

        html.Hr(
            className="my-5",
            style={} if (show_deaths) else {"display": "none"}
        ),

    ], fluid=True, className="p-2")


# This is the default layout used when the app imports this file.
# We pass False here since desktop is the standard case.
layout = layout_for(is_mobile=False)

# ----------------------------
# Figures + tables (no plotly titles)
# ----------------------------

@callback(
    Output("wonder-county-filter", "value"),
    Output("wonder-year-filter", "value"),
    Input("wonder-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_all_filters(_n_clicks):
    # Reset both filters to default empty state.
    return [], []

@callback(
    Output("wonder-kpi-deaths", "children"),
    Output("wonder-line-deaths", "figure"),
    Output("wonder-bar-deaths", "figure"),
    Input("wonder-county-filter", "value"),
    Input("wonder-year-filter", "value"),
)

def update_dashboard(county, year):
    """
    This function runs every time the user changes a filter.

    It:
      - Applies all the filters to the data,
      - Builds two graphs (line + stacked bar)
    """

    def apply_filter(frame, col, val):
        """
        Small helper so we don't repeat the same filter logic.

        If the user did not pick anything, we leave the data alone.
        If they picked one or more values, we only keep matching rows.
        """
        if val is None or (isinstance(val, (list, tuple)) and len(val) == 0):
            return frame
        if isinstance(val, (list, tuple)):
            return frame[frame[col].isin(val)]
        return frame[frame[col] == val]

    # Start from the full dataset each time.
    dff = df_raw.copy()

    # Only apply filters for columns that actually exist.
    if "county" in dff.columns:    dff = apply_filter(dff, "county", county)
    if "year" in dff.columns:      dff = apply_year_filter(dff, "year", year)

    # KPI should honor selected filters.
    # When no county is selected, default to statewide rows when available
    # so we avoid summing statewide + county rows together.
    kpi_df = df_raw.copy()
    if "year" in kpi_df.columns:
        kpi_df = apply_year_filter(kpi_df, "year", year)
    if "county" in kpi_df.columns:
        if county is not None and isinstance(county, (list, tuple)) and len(county) > 0:
            kpi_df = apply_filter(kpi_df, "county", county)
        else:
            statewide_mask = kpi_df["county"].astype(str).str.strip().str.lower() == "statewide"
            if statewide_mask.any():
                kpi_df = kpi_df[statewide_mask]

    filter_total = kpi_df["deaths"].sum()

    # ---------- Line chart: Deaths by Calendar Year (by county) ----------
    if {"county", "year"}.issubset(dff.columns):
        by_year = (
            dff.groupby(["year", "county"], as_index=False)["deaths"]
            .sum()
            .sort_values(["year", "county"])
        )
        county_order = statewide_first(sort_opts(by_year["county"]))
        by_year["county"] = pd.Categorical(by_year["county"], categories=county_order, ordered=True)
        by_year = by_year.sort_values(["year", "county"])
        by_year["display_count"] = by_year["deaths"].apply(format_count_display)

        year_line = px.line(
            by_year,
            x="year",
            y="deaths",
            color="county",
            markers=True,
            text="display_count",
            category_orders={"county": county_order},
            labels={"year": "Calendar Year", "deaths": "Number of Deaths", "county": "County"},
        )

        year_line.update_traces(
            textposition="top center",
            hovertemplate="Year %{x}<br>County: %{fullData.name}<br>Deaths: %{text}<extra></extra>",
        )

        apply_standard_line_layout(year_line)
        year_line.update_layout(title="Deaths by Calendar Year")

    # ---------- Bar chart: Deaths by Substance ----------
    if {"county", "year"}.issubset(dff.columns):
        by_county = (
            dff.groupby("county", as_index=False)["deaths"]
            .sum()
            .sort_values("deaths", ascending=False)
        )

        if "county" in by_county.columns:
            statewide_rows = by_county[by_county["county"].astype(str).str.strip().str.lower() == "statewide"]
            other_rows = by_county[by_county["county"].astype(str).str.strip().str.lower() != "statewide"]
            by_county = pd.concat([statewide_rows, other_rows], ignore_index=True)

        by_county["display_count"] = by_county["deaths"].apply(format_count_display)
        county_bar = px.bar(
            by_county,
            x="deaths",
            y="county",
            barmode="stack",
            text="display_count",
            labels={"deaths": "Number of Deaths", "county": "County of Death"},
        )

        apply_standard_single_series_bar_trace(county_bar)

        apply_standard_bar_layout(county_bar, yaxis=dict(autorange="reversed"))
        county_bar.update_layout(title="Deaths by County")

    # Return all the updated visuals and tables to Dash
    return (
        format_count_display(filter_total),
        year_line,
        county_bar
    )
