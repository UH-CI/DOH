from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    apply_year_filter,
    load_sql_query,
    sort_opts,
    opts_list,
    apply_county_filter,
    county_output_should_include_statewide,
    build_summary_count_table,
    graph_block,
    make_kpi_card,
    make_left_sidebar,
    make_right_summary_tables_col,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    make_filters_card,
    dropdown_filter,
    format_count_display,
    wrap_axis_label,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
    apply_standard_line_layout,
)

register_template()

# ----------------------------
# Data helpers
# ----------------------------

def load_diagnosis_dataframe_from_db():
   """
   This helper:
     1. Loads the main SQL query by name.
     2. Connects to the database and runs the query.
     3. Cleans up some columns so the rest of the app is easier to write.

   Why: having this in one place avoids repeating the same database
   logic in multiple callbacks.
  
   Note: Uses either SQLite or MSSQL automatically based on config.
   """
  
   sql = load_sql_query("load_discharges_su_co_mh_sud")
  
   # Execute query using db_utils (automatically uses correct database)
   df = execute_query(sql)
   print(f"load_discharges_su_co_mh_sud returned {len(df):,} rows")

   # If there is no data, we stop early instead of showing a broken page
   if df.empty:
       raise RuntimeError("Query returned 0 rows.")

   # Make the year column numeric when possible so graphs treat it as numbers
   if "year" in df.columns:
       df["year"] = pd.to_numeric(df["year"], errors="coerce")

   # For these columns, replace missing values with "Unknown"
   # so we don't get blank labels in filters and tables.
   for col in ["substance", "diagnosis_type", "is_primary", "county", "city", "zip", "hawaii_residency", "age_group", "sex", "race_ethnicity", "year"]:
       if col in df.columns:
           df[col] = df[col].fillna("Unknown")
   
   # Trim whitespace from text columns (fixes issue where trailing spaces prevent filter matches)
   for col in ["substance", "diagnosis_type", "is_primary", "county", "city", "zip", "hawaii_residency", "age_group", "sex", "race_ethnicity"]:
       if col in df.columns:
           df[col] = df[col].astype(str).str.strip()
   
   return df

# Load the full dataset once at startup.
# The callbacks will reuse this instead of hitting the database every time.
df_raw = load_diagnosis_dataframe_from_db()
last_updated_value = compute_last_updated_value(df_raw)

# Normalize ZIP values (5-digit strings) so they look cleaner in the filters and tables.
if "zip" in df_raw.columns:
    df_raw["zip"] = (
        df_raw["zip"]
        .astype(str)
        .str.extract(r"(\d{5})", expand=False)
        .fillna("")
    )

# Count how many unique records we have to show on the KPI card.
total_unique = df_raw["record_id"].nunique() if "record_id" in df_raw.columns else 0

# Build the lists of choices for each filter only if the column exists.
su_opts     = sort_opts(df_raw.loc[df_raw["diagnosis_type"] == "su", "diagnosis"])      if "diagnosis"      in df_raw.columns else []
mh_opts     = sort_opts(df_raw.loc[df_raw["diagnosis_type"] == "mh", "diagnosis"])      if "diagnosis"      in df_raw.columns else []
county_opts = sort_opts(df_raw["county"])                                               if "county"         in df_raw.columns else []
city_opts               = sort_opts(df_raw["city"])                                             if "city"               in df_raw.columns else []
year_opts   = sort_opts(df_raw["year"])                                                 if "year"           in df_raw.columns else []
age_opts    = sort_opts(df_raw["age_group"])                                            if "age_group"      in df_raw.columns else []
sex_opts    = sort_opts(df_raw["sex"])                                                  if "sex"            in df_raw.columns else []
race_ethnicity_opts     = sort_opts(df_raw["race_ethnicity"])                                   if "race_ethnicity"     in df_raw.columns else []
hawaii_residency_opts   = sort_opts(df_raw["hawaii_residency"])                                 if "hawaii_residency"   in df_raw.columns else []

# ----------------------------
# UI Components
# ----------------------------

# This link helps keyboard and screen reader users jump straight to the filters.
skip_link = html.A(
   "Skip to filters",
   href="#mh-primary-filters",
   className="visually-hidden-focusable",
   tabIndex=0
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="mh-primary-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Big green card that shows the total number of discharges.
kpi_card = make_kpi_card(
    label="Number of Discharges Related to Co-Occurring MH disorder (primary) and SUD (secondary)",
    count_id="mh-primary-kpi-total",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="mh-primary-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Substance", "mh-primary-su-filter", options=opts_list(su_opts), multi=True, placeholder="All"),
        dropdown_filter("Mental Health Diagnosis", "mh-primary-mh-filter", options=opts_list(mh_opts), multi=True, placeholder="All"),
        dropdown_filter("County", "mh-primary-county-filter", options=opts_list(county_opts), multi=True, placeholder="All"),
        dropdown_filter("City", "mh-primary-city-filter", options=opts_list(city_opts), multi=True, placeholder="All"),
        dropdown_filter("Year", "mh-primary-year-filter", options=opts_list(year_opts), multi=True, placeholder="All"),
        dropdown_filter("Age Group", "mh-primary-age-filter", options=opts_list(age_opts), multi=True, placeholder="All"),
        dropdown_filter("Sex", "mh-primary-sex-filter", options=opts_list(sex_opts), multi=True, placeholder="All"),
        dropdown_filter("Race/Ethnicity", "mh-primary-race-ethnicity-filter", options=opts_list(race_ethnicity_opts), multi=True, placeholder="All"),
        dropdown_filter("Hawaii Resident", "mh-primary-hawaii-residency-filter", options=opts_list(hawaii_residency_opts), multi=True, placeholder="All"),
    ],
)

from section_texts import SECTION_TEXTS
discharges_sidebar_text = SECTION_TEXTS.get("discharges-su-co-mh-sud", [])

def layout():
    """
    Build the discharges dashboard layout.
    """
    # Adjust plot heights for desktop
    line_h = "400px"
    bar_h = f"{compute_adaptive_horizontal_bar_height(len(mh_opts))}px"
   
    # Left column: KPI, reset button, and filters.
    left_col = make_left_sidebar(
        kpi_card,
        reset_filters_button,
        filters_card,
        helper_text=discharges_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    # Center column: the main line and bar charts.
    center_col = dbc.Col([
        graph_block("mh-primary-bar", "Discharges by Mental Health Diagnosis"),
        html.P("Bar chart showing discharges by mental health diagnosis.", className="visually-hidden"),
        graph_block("mh-primary-line", "Yearly Discharges by Mental Health Diagnosis", line_h),
        html.P("Line chart showing yearly discharges by mental health diagnosis.", className="visually-hidden"),
    ], xs=12, md=6)

    # Right column: summary tables (ordered by shared site-wide utility)
    right_col = make_right_summary_tables_col(
        [
            ("County", "mh-primary-table-county"),
            ("Age Group", "mh-primary-table-age"),
            ("Sex", "mh-primary-table-sex"),
            ("Race/Ethnicity", "mh-primary-table-race-ethnicity"),
            ("Hawaii Residency", "mh-primary-table-hawaii-residency"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="mh-primary-section",
        ),
    ], fluid=True, className="p-2")


# This is the default layout used when the app imports this file.
layout = layout()

# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("mh-primary-su-filter", "value"),
    Output("mh-primary-mh-filter", "value"),
    Output("mh-primary-county-filter", "value"),
    Output("mh-primary-city-filter", "value"),
    Output("mh-primary-year-filter", "value"),
    Output("mh-primary-age-filter", "value"),
    Output("mh-primary-sex-filter", "value"),
    Output("mh-primary-race-ethnicity-filter", "value"),
    Output("mh-primary-hawaii-residency-filter", "value"),
    Input("mh-primary-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)

def reset_discharges_filters(_n_clicks):
    # Reset all multi-select dropdowns to their default empty state.
    return None, None, None, None, None, None, None, None, None

@callback(
    # kpi card
    Output("mh-primary-kpi-total", "children"),
    # graphs
    Output("mh-primary-bar", "figure"),
    Output("mh-primary-line", "figure"),
    # tables 
    Output("mh-primary-table-county", "children"),
    Output("mh-primary-table-age", "children"),
    Output("mh-primary-table-sex", "children"),
    Output("mh-primary-table-race-ethnicity", "children"),
    Output("mh-primary-table-hawaii-residency", "children"),   
    # filters
    Input("mh-primary-su-filter", "value"),
    Input("mh-primary-mh-filter", "value"),
    Input("mh-primary-county-filter", "value"),
    Input("mh-primary-city-filter", "value"),
    Input("mh-primary-year-filter", "value"),
    Input("mh-primary-age-filter", "value"),
    Input("mh-primary-sex-filter", "value"),
    Input("mh-primary-race-ethnicity-filter", "value"),
    Input("mh-primary-hawaii-residency-filter", "value"),
)

def update_dashboard(su, mh, county, city, year, age, sex, race_ethnicity, hawaii_residency):
    """
    This function runs every time the user changes a filter.
    It updates all the discharge visualizations and tables.
    """

    def apply_filter(frame, col, val):
        """Small helper for filter logic."""
        if val is None or (isinstance(val, (list, tuple)) and len(val) == 0):
            return frame

        if isinstance(val, (list, tuple)):
            return frame[frame[col].isin(val)]
        return frame[frame[col] == val]

    # Start from the full dataset each time.
    dff = df_raw.copy()

    # Only apply filters for columns that actually exist.
    if su:
        su_ids_filtered = set(dff.loc[(dff["diagnosis_type"] == "su") & (dff["diagnosis"].isin(su)), "record_id"])
        dff = dff[dff["record_id"].isin(su_ids_filtered)]
    if mh:
        mh_ids_filtered = set(dff.loc[(dff["diagnosis_type"] == "mh") & (dff["diagnosis"].isin(mh)), "record_id"])
        dff = dff[dff["record_id"].isin(mh_ids_filtered)]
    if "county" in dff.columns:                 dff = apply_county_filter(dff, county)
    if "city" in dff.columns:                   dff = apply_filter(dff, "city", city)
    if "year" in dff.columns:                   dff = apply_year_filter(dff, "year", year)
    if "age_group" in dff.columns:              dff = apply_filter(dff, "age_group", age)
    if "sex" in dff.columns:                    dff = apply_filter(dff, "sex", sex)
    if "race_ethnicity" in dff.columns:         dff = apply_filter(dff, "race_ethnicity", race_ethnicity)
    if "hawaii_residency" in dff.columns:       dff = apply_filter(dff, "hawaii_residency", hawaii_residency)

    all_su_ids = set(dff.loc[dff["diagnosis_type"] == "su", "record_id"])
    primary_mh_ids = set(dff.loc[(dff["diagnosis_type"] == "mh") & (dff["is_primary"] == 1), "record_id"])

    cooccuring_ids = all_su_ids.intersection(primary_mh_ids)

    #dff = dff[dff["record_id"].isin(cooccuring_ids)]

    include_statewide_county_outputs = county_output_should_include_statewide(county)

    filter_total = dff["record_id"].nunique()


    # ---------- Bar chart: Discharges by Mental Health Diagnosis ----------
    if {"record_id", "diagnosis", "diagnosis_type"}.issubset(dff.columns):
        
        mh_df = dff[dff["diagnosis_type"] == "mh"]

        by_mh = (
            mh_df.groupby("diagnosis")["record_id"]
            .nunique()
            .reset_index().rename(columns={"record_id": "count"})
            .sort_values("count", ascending=True)
        )

        by_mh["diagnosis_label"] = by_mh["diagnosis"].apply(wrap_axis_label)
        by_mh["display_count"] = by_mh["count"].apply(format_count_display)

        mh_bar = px.bar(
            by_mh,
            x="count",
            y="diagnosis_label",
            barmode="stack",
            text="display_count",
            labels={"count": "Number of Discharges", "diagnosis_label": "Mental Health Diagnosis"},
        )

        apply_standard_single_series_bar_trace(
            mh_bar,
            customdata=by_mh["diagnosis"],
            hovertemplate="%{customdata}:<br>%{text}<extra></extra>",
        )

        apply_standard_bar_layout(mh_bar)
        mh_bar.update_layout(title="Discharges by Mental Health Diagnosis")
    else:
        mh_bar = px.bar()


    # ---------- Line chart: Yearly Discharges by Mental Health Diagnosis ----------
    if {"record_id", "diagnosis", "diagnosis_type", "year"}.issubset(dff.columns):

        mh_df = dff[dff["diagnosis_type"] == "mh"]

        by_mh = (
            mh_df.groupby(["year", "diagnosis"])["record_id"].nunique()
            .reset_index().rename(columns={"record_id": "count"})
        )

        by_mh["display_count"] = by_mh["count"].apply(format_count_display)

        # Order substances in a consistent way for the legend
        substances = sort_opts(dff["diagnosis"]) if "diagnosis" in dff.columns else []
        if substances:
            by_mh["diagnosis"] = pd.Categorical(by_mh["diagnosis"], categories=substances, ordered=True)

        mh_line = px.line(
            by_mh,
            x="year",
            y="count",
            color="diagnosis",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "diagnosis": "Mental Health Diagnosis"},
            category_orders={"diagnosis": substances} if substances else None,
        )

        mh_line.update_traces(
            hovertemplate="Year: %{x}<br>Mental Health Diagnosis: %{fullData.name}<br>Discharges: %{customdata[0]}<extra></extra>"
        )

        max_y = int(by_mh["count"].max()) if not by_mh.empty else 0

        apply_standard_line_layout(
            mh_line,
            yaxis=dict(range=[0, max_y * 1.05 if max_y else 1], autorange=False),
            legend=dict(
                title_text="Mental Health Diagnosis",
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="left",
                x=0,
            ),
        )
        mh_line.update_layout(title="Yearly Discharges by Mental Health Diagnosis")
    else:
        mh_line = px.line()


    county_categories = sort_opts(county_opts) if county_opts else None

    # ---------- Helper for the summary tables ----------
    # Use shared build_summary_count_table for summary tables
    def summary_table(group_col, categories=None, filter_selection=None):
        return build_summary_count_table(
            dff,
            group_col=group_col,
            id_col="record_id",
            categories=categories,
            filter_selection=filter_selection,
            include_statewide_county=(group_col == "county" and include_statewide_county_outputs),
        )

    # Return all the updated visuals and tables to Dash
    return (
        format_count_display(filter_total),
        mh_bar,
        mh_line,
        summary_table("county", county_categories, filter_selection=county),
        summary_table("age_group", age_opts, filter_selection=age),
        summary_table("sex", sex_opts, filter_selection=sex),
        summary_table("race_ethnicity", race_ethnicity_opts, filter_selection=race_ethnicity),
        summary_table("hawaii_residency", hawaii_residency_opts, filter_selection=hawaii_residency),
    )