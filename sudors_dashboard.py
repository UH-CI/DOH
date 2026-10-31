from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
import re
from dashboard_utils import (
    apply_year_filter,
    load_sql_query,
    sort_opts,
    opts_list,
    graph_block,
    make_kpi_card,
    make_left_sidebar,
    make_right_summary_tables_col,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    make_filters_card,
    dropdown_filter,
    format_count_display,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
    apply_standard_line_layout,
    build_summary_count_table,
)

register_template()

# ----------------------------
# Data helpers
# ----------------------------

def load_sudors_dataframe_from_db():
    """
    This helper:
      1. Loads the main SQL query by name.
      2. Connects to the database and runs the query.
      3. Cleans up some columns so the rest of the app is easier to write.

    Why: having this in one place avoids repeating the same database
    logic in multiple callbacks.
    
    Note: Uses either SQLite or MSSQL automatically based on config.
    """
    # Grab the SQL for our main data
    sql = load_sql_query("load_sudors_data_view_diag_su$")
    
    # Execute query using db_utils (automatically uses correct database)
    df = execute_query(sql)
    df['substance'] = df['substance'].str.title()
    print(f"load_sudors_data_view_diag_su$ returned {len(df):,} rows")

    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")

    # Make the year column numeric when possible so graphs treat it as numbers
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # For these columns, replace missing values with "Unknown"
    # so we don't get blank labels in filters and tables.
    for col in ["substance", "homeless", "sex", "age_cat", "race_ethnicity", "year"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")
    return df

# Load the full dataset once at startup.
# The callbacks will reuse this instead of hitting the database every time.
df_raw = load_sudors_dataframe_from_db()
last_updated_value = compute_last_updated_value(df_raw)

# Count how many unique records we have to show on the KPI card.
total_unique = df_raw["incident_id"].nunique() if "incident_id" in df_raw.columns else 0

# Build the lists of choices for each filter only if the column exists.
substance_opts  = sort_opts(df_raw["substance"])                     if "substance"  in df_raw.columns else []
homeless_opts   = sort_opts(df_raw["homeless"])                      if "homeless"   in df_raw.columns else []
sex_opts        = sort_opts(df_raw["sex"])                           if "sex"        in df_raw.columns else []
age_opts        = sort_opts(df_raw["age_cat"])                       if "age_cat"    in df_raw.columns else []
race_opts       = sort_opts(df_raw["race_ethnicity"])                if "race_ethnicity"       in df_raw.columns else []
year_opts       = sort_opts(df_raw["year"])                          if "year"       in df_raw.columns else []

# ----------------------------
# UI Components
# ----------------------------

# This link helps keyboard and screen reader users jump straight to the filters.
skip_link = html.A(
   "Skip to filters",
   href="#sudors-filters",
   className="visually-hidden-focusable",
   tabIndex=0
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="sudors-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Big green card that shows the total number of discharges.
kpi_card = make_kpi_card(
    label="Number of Unintentional or Undetermined Overdose Deaths",
    count_id="sudors-kpi-total",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="sudors-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Substance", "sudors-substance-filter", options=opts_list(substance_opts), multi=True, placeholder="All"),
        dropdown_filter("Homeless", "sudors-homeless-filter", options=opts_list(homeless_opts), multi=True, placeholder="All"),
        dropdown_filter("Race/Ethnicity", "sudors-race-filter", options=opts_list(race_opts), multi=True, placeholder="All"),
        dropdown_filter("Sex", "sudors-sex-filter", options=opts_list(sex_opts), multi=True, placeholder="All"),
        dropdown_filter("Age Group", "sudors-age-filter", options=opts_list(age_opts), multi=True, placeholder="All"),
        dropdown_filter("Calendar Year", "sudors-year-filter", options=opts_list(year_opts), multi=True, placeholder="All"),
    ],
)

from section_texts import SECTION_TEXTS
sudors_sidebar_text = SECTION_TEXTS.get("sudors", [])

def layout():
    """
    Build the discharges dashboard layout.
    """
    # Adjust plot heights for desktop
    bar_h = f"{compute_adaptive_horizontal_bar_height(len(substance_opts))}px"
    line_h = "400px"
    pie_h  = "260px"
   
    # Left column: KPI, reset button, and filters.
    left_col = make_left_sidebar(
        kpi_card,
        reset_filters_button,
        filters_card,
        helper_text=sudors_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    # Center column: the main line, bar, and pie charts.
    center_col = dbc.Col(
        [
            graph_block("sudors-bar", ""),
            html.P("Bar chart showing deaths by substance.", className="visually-hidden"),

            graph_block("sudors-line", "", line_h),
            html.P("Line chart showing deaths by substance over time.", className="visually-hidden"),
        ],
        xs=12, md=6
    )

    # Right column: summary tables (ordered by shared site-wide utility)
    right_col = make_right_summary_tables_col(
        [
            ("Race/Ethnicity", "sudors-table-race"),
            ("Sex at Birth", "sudors-table-sex"),
            ("Homeless", "sudors-table-homeless"),
            ("Calendar Year", "sudors-table-year"),
            ("Age Group", "sudors-table-age"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="sudors-primary-section",
        ),
    ], fluid=True, className="p-2")

# This is the default layout used when the app imports this file.
layout = layout()

# ----------------------------
# Callbacks for discharges
# ----------------------------

@callback(
    # filters
    Output("sudors-substance-filter", "value"),
    Output("sudors-homeless-filter", "value"),
    Output("sudors-race-filter", "value"),
    Output("sudors-sex-filter", "value"),
    Output("sudors-age-filter", "value"),
    Output("sudors-year-filter", "value"),
    Input("sudors-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)

def reset_all_filters(_n_clicks):
    # Reset all multi-select dropdowns to their default empty state.
    return None, None, None, None, None, None

@callback(
    # kpi card
    Output("sudors-kpi-total", "children"),
    # graphs
    Output("sudors-bar", "figure"),
    # tables
    Output("sudors-table-race", "children"),
    Output("sudors-table-sex", "children"),
    Output("sudors-table-homeless", "children"),
    Output("sudors-table-year", "children"),
    Output("sudors-table-age", "children"),
    # graphs
    Output("sudors-line", "figure"),
    # filters
    Input("sudors-substance-filter", "value"),
    Input("sudors-homeless-filter", "value"),
    Input("sudors-sex-filter", "value"),
    Input("sudors-age-filter", "value"),
    Input("sudors-race-filter", "value"),
    Input("sudors-year-filter", "value"),
)

def update_dashboard(substance, homeless, sex, age, race, year):
    """
    This function runs every time the user changes a filter.
    It updates all the discharge visualizations and tables.
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
    if "substance" in dff.columns:      dff = apply_filter(dff, "substance", substance)
    if "homeless" in dff.columns:       dff = apply_filter(dff, "homeless", homeless)
    if "sex" in dff.columns:            dff = apply_filter(dff, "sex", sex)
    if "age_cat" in dff.columns:        dff = apply_filter(dff, "age_cat", age)
    if "race_ethnicity" in dff.columns: dff = apply_filter(dff, "race_ethnicity", race)
    if "year" in dff.columns:           dff = apply_year_filter(dff, "year", year)

    # Count unique discharges (each record_id represents one discharge).
    # Used to update the total on the KPI card when user selects the filter
    filter_total = dff["incident_id"].nunique()


    # ---------- Bar chart: Deaths by Substance ----------
    if {"substance"}.issubset(dff.columns):
        by_sub = (
            dff.groupby("substance")["incident_id"].nunique()
            .reset_index(name="count")
            .sort_values("count", ascending=True)
        )

        def ellipsize(text, max_len=25):
            if text is None:
                return text
            return text if len(text) <= max_len else text[:max_len] + "..."

        # Cuts off label length after 25 characters
        by_sub["substance_label"] = by_sub["substance"].apply(ellipsize)

        sud_bar = px.bar(
            by_sub,
            x="count",
            y="substance_label",
            barmode="stack",
            labels={"count": "Number of Deaths", "substance_label": "Cause of Death<br>(Not Mutually Exclusive)"},
        )

        apply_standard_single_series_bar_trace(sud_bar)
        apply_standard_bar_layout(sud_bar, xaxis=dict(rangemode="tozero"))
        sud_bar.update_layout(title="Deaths by Substance")
    else:
        sud_bar = px.bar()

    # ---------- Line chart: Deaths by Substance Over Time ----------
    if {"year", "substance"}.issubset(dff.columns):
        by_year_substance = (
            dff.groupby(["year", "substance"])["incident_id"].nunique()
            .reset_index(name="count")
            .sort_values(["year", "substance"])
        )

        line_fig = px.line(
            by_year_substance,
            x="year",
            y="count",
            color="substance",
            markers=True,
            labels={"year": "Year", "count": "Number of Deaths", "substance": "Substance"},
        )
        by_year_substance["display_count"] = by_year_substance["count"].apply(format_count_display)

        # To fix the hover issue, we need to iterate through each trace Plotly Express created
        # and assign the correct customdata for that specific substance.
        for trace in line_fig.data:
            substance_name = trace.name
            # Filter the dataframe to get data just for this trace's substance
            substance_df = by_year_substance[by_year_substance["substance"] == substance_name]
            # Sort it by year to ensure the data points line up
            substance_df = substance_df.sort_values("year")
            # Assign the correctly ordered customdata
            trace.customdata = substance_df[["display_count"]]
            trace.hovertemplate = "Year: %{x}<br>Substance: %{fullData.name}<br>Deaths: %{customdata[0]}<extra></extra>"

        apply_standard_line_layout(
            line_fig,
        )
        line_fig.update_layout(title="Yearly Deaths by Substance")
    else:
        line_fig = px.line()
        line_fig.update_layout(title="Yearly Deaths by Substance")

    
    # ---------- Helper for the summary tables ----------
    # Use shared build_summary_count_table for summary tables
    def summary_table(group_col, categories=None, filter_selection=None):
        return build_summary_count_table(
            dff,
            group_col=group_col,
            id_col="incident_id",
            categories=categories,
            filter_selection=filter_selection,
            count_label="Deaths",
        )

    # Return all the updated visuals and tables to Dash
    return (
        format_count_display(filter_total),
        sud_bar,
        summary_table("race_ethnicity", categories=race_opts, filter_selection=race),
        summary_table("sex", categories=sex_opts, filter_selection=sex),
        summary_table("homeless", categories=homeless_opts, filter_selection=homeless),
        summary_table("year", categories=year_opts, filter_selection=year),
        summary_table("age_cat", categories=age_opts, filter_selection=age),
        line_fig,
    )