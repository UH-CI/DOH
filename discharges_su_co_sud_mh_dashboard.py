# substance_use_primary_dashboard.py — Related to co-occuring SUD (primary) and MH disorder (secondary) page

from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    apply_filter,
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
    # Grab the SQL for our main data
    sql = load_sql_query("load_discharges_su_co_sud_mh")
    
    # Execute query using db_utils (automatically uses correct database)
    df = execute_query(sql)
    print(f"load_discharges_su_co_sud_mh returned {len(df):,} rows")

    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")

    # Make the year column numeric when possible so graphs treat it as numbers
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # For these columns, replace missing values with "Unknown"
    # so we don't get blank labels in filters and tables.
    for col in ["diagnosis", "diagnosis_type", "is_primary", "county", "city", "zip", "hawaii_residency", "age_group", "sex", "race_ethnicity", "year"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")
    
    # Trim whitespace from text columns (fixes issue where trailing spaces prevent filter matches)
    for col in ["diagnosis", "diagnosis_type", "is_primary", "county", "city", "zip", "hawaii_residency", "age_group", "sex", "race_ethnicity"]:
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
su_opts                 = sort_opts(df_raw.loc[df_raw["diagnosis_type"] == "su", "diagnosis"])  if "diagnosis"          in df_raw.columns else []
mh_opts                 = sort_opts(df_raw.loc[df_raw["diagnosis_type"] == "mh", "diagnosis"])  if "diagnosis"          in df_raw.columns else []
county_opts             = sort_opts(df_raw["county"])                                           if "county"             in df_raw.columns else []
city_opts               = sort_opts(df_raw["city"])                                             if "city"               in df_raw.columns else []
year_opts               = sort_opts(df_raw["year"])                                             if "year"               in df_raw.columns else []
age_opts                = sort_opts(df_raw["age_group"])                                        if "age_group"          in df_raw.columns else []
sex_opts                = sort_opts(df_raw["sex"])                                              if "sex"                in df_raw.columns else []
race_ethnicity_opts     = sort_opts(df_raw["race_ethnicity"])                                   if "race_ethnicity"     in df_raw.columns else []
hawaii_residency_opts   = sort_opts(df_raw["hawaii_residency"])                                 if "hawaii_residency"   in df_raw.columns else []

# ----------------------------
# UI Components
# ----------------------------

# This link helps keyboard and screen reader users jump straight to the filters.
skip_link = html.A(
   "Skip to filters",
   href="#su-primary-filters",
   className="visually-hidden-focusable",
   tabIndex=0
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="su-primary-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Big green card that shows the total number of discharges.
kpi_card = make_kpi_card(
    label="Number of Discharges Related to Co-Occurring SUD (primary) and MH Disorder (secondary)",
    count_id="su-primary-kpi-total",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="su-primary-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Substance", "su-primary-su-filter", options=opts_list(su_opts), multi=True, placeholder="All"),
        dropdown_filter("Mental Health Diagnosis", "su-primary-mh-filter", options=opts_list(mh_opts), multi=True, placeholder="All"),
        dropdown_filter("County", "su-primary-county-filter", options=opts_list(county_opts), multi=True, placeholder="All"),
        dropdown_filter("City", "su-primary-city-filter", options=opts_list(city_opts), multi=True, placeholder="All"),
        dropdown_filter("Year", "su-primary-year-filter", options=opts_list(year_opts), multi=True, placeholder="All"),
        dropdown_filter("Age Group", "su-primary-age-filter", options=opts_list(age_opts), multi=True, placeholder="All"),
        dropdown_filter("Sex", "su-primary-sex-filter", options=opts_list(sex_opts), multi=True, placeholder="All"),
        dropdown_filter("Race/Ethnicity", "su-primary-race-ethnicity-filter", options=opts_list(race_ethnicity_opts), multi=True, placeholder="All"),
        dropdown_filter("Hawaii Resident", "su-primary-hawaii-residency-filter", options=opts_list(hawaii_residency_opts), multi=True, placeholder="All"),
    ],
)

from section_texts import SECTION_TEXTS
discharges_sidebar_text = SECTION_TEXTS.get("discharges-su-co-sud-mh", [])

def layout():
    """
    Build the discharges dashboard layout.
    """
    # Adjust plot heights for desktop
    bar_h = f"{compute_adaptive_horizontal_bar_height(len(su_opts))}px"
    line_h = "400px"
   
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
        graph_block("su-primary-bar", ""),
        html.P("Bar chart showing discharges by substance.", className="visually-hidden"),
        graph_block("sud-mh-primary-bar", ""),
        html.P("Bar chart showing discharges by mental health diagnosis.", className="visually-hidden"),
        graph_block("su-primary-line", "", line_h),
        html.P("Line chart showing yearly discharges by substance.", className="visually-hidden"),
    ], xs=12, md=6)

    # Right column: summary tables (ordered by shared site-wide utility)
    right_col = make_right_summary_tables_col(
        [
            ("County", "su-primary-table-county"),
            ("Age Group", "su-primary-table-age"),
            ("Sex", "su-primary-table-sex"),
            ("Race/Ethnicity", "su-primary-table-race-ethnicity"),
            ("Hawaii Residency", "su-primary-table-hawaii-residency"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="su-primary-section",
        ),
    ], fluid=True, className="p-2")


# This is the default layout used when the app imports this file.
layout = layout()

# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("su-primary-su-filter", "value"),
    Output("su-primary-mh-filter", "value"),
    Output("su-primary-county-filter", "value"),
    Output("su-primary-city-filter", "value"),
    Output("su-primary-year-filter", "value"),
    Output("su-primary-age-filter", "value"),
    Output("su-primary-sex-filter", "value"),
    Output("su-primary-race-ethnicity-filter", "value"),
    Output("su-primary-hawaii-residency-filter", "value"),
    Input("su-primary-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)

def reset_discharges_filters(_n_clicks):
    # Reset all multi-select dropdowns to their default empty state.
    return None, None, None, None, None, None, None, None, None

@callback(
    # kpi card
    Output("su-primary-kpi-total", "children"),
    # graphs
    Output("su-primary-bar", "figure"),
    Output("sud-mh-primary-bar", "figure"),
    Output("su-primary-line", "figure"),
    # tables 
    Output("su-primary-table-county", "children"),
    Output("su-primary-table-age", "children"),
    Output("su-primary-table-sex", "children"),
    Output("su-primary-table-race-ethnicity", "children"),
    Output("su-primary-table-hawaii-residency", "children"),   
    # filters
    Input("su-primary-su-filter", "value"),
    Input("su-primary-mh-filter", "value"),
    Input("su-primary-county-filter", "value"),
    Input("su-primary-city-filter", "value"),
    Input("su-primary-year-filter", "value"),
    Input("su-primary-age-filter", "value"),
    Input("su-primary-sex-filter", "value"),
    Input("su-primary-race-ethnicity-filter", "value"),
    Input("su-primary-hawaii-residency-filter", "value"),
)
def update_dashboard(su, mh, county, city, year, age, sex, race_ethnicity, hawaii_residency):
    """
    This function runs every time the user changes a filter.
    It updates all the discharge visualizations and tables with corrected logic.
    """

    # Start from the full dataset each time.
    dff = df_raw.copy()

    # If a substance filter is applied, it defines the primary cohort for the analysis.
    if su:
        primary_su_ids_cohort = set(dff.loc[
            (dff["diagnosis_type"] == "su") & 
            (dff["diagnosis"].isin(su)) & 
            (dff["is_primary"] == '1'),
            "record_id"
        ])
        dff = dff[dff["record_id"].isin(primary_su_ids_cohort)]
    
    # The rest of the filters are applied sequentially.
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
    include_statewide_county_outputs = county_output_should_include_statewide(county)

    filter_total = dff["record_id"].nunique()

    # ---------- Bar chart: Discharges by Substance ----------
    if {"record_id", "diagnosis", "diagnosis_type"}.issubset(dff.columns):
        
        # Show all substances in the filtered data
        su_df = dff[dff["diagnosis_type"] == "su"]

        by_sub = (
            su_df.groupby("diagnosis")["record_id"]
            .nunique()
            .reset_index().rename(columns={"record_id": "count"})
            .sort_values("count", ascending=True)
        )

        by_sub["diagnosis_label"] = by_sub["diagnosis"].apply(wrap_axis_label)
        by_sub["display_count"] = by_sub["count"].apply(format_count_display)

        sub_bar = px.bar(
            by_sub,
            x="count",
            y="diagnosis_label",
            barmode="stack",
            text="display_count",
            labels={"count": "Number of Discharges", "diagnosis_label": "Substance Use Diagnosis"},
        )
        
        apply_standard_single_series_bar_trace(
            sub_bar,
            customdata=by_sub["diagnosis"],
            hovertemplate="%{customdata}:<br>%{text}<extra></extra>",
        )

        apply_standard_bar_layout(sub_bar)
    else:
        sub_bar = px.bar()


    # (The rest of the function for the other charts and tables remains the same)
    # ...
    # [The rest of your function code would go here, unchanged]
    # ...
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
    else:
        mh_bar = px.bar()

    # ---------- Line chart: Yearly Discharges by Substance ----------
    if {"record_id", "diagnosis", "diagnosis_type", "year"}.issubset(dff.columns):

        su_df = dff[dff["diagnosis_type"] == "su"]

        by_ysub = (
            su_df.groupby(["year", "diagnosis"])["record_id"].nunique()
            .reset_index().rename(columns={"record_id": "count"})
        )

        by_ysub["display_count"] = by_ysub["count"].apply(format_count_display)

        substances = sort_opts(dff["diagnosis"]) if "diagnosis" in dff.columns else []
        if substances:
            by_ysub["diagnosis"] = pd.Categorical(by_ysub["diagnosis"], categories=substances, ordered=True)

        sub_line = px.line(
            by_ysub,
            x="year",
            y="count",
            color="diagnosis",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "diagnosis": "Substance"},
            category_orders={"diagnosis": substances} if substances else None,
        )

        sub_line.update_traces(
            hovertemplate="Year: %{x}<br>Substance: %{fullData.name}<br>Discharges: %{customdata[0]}<extra></extra>"
        )

        max_y = int(by_ysub["count"].max()) if not by_ysub.empty else 0

        apply_standard_line_layout(
            sub_line,
            yaxis=dict(range=[0, max_y * 1.05 if max_y else 1], autorange=False),
            legend=dict(
                title_text="Substance",
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="left",
                x=0,
            ),
        )
    else:
        sub_line = px.line()


    county_categories = sort_opts(county_opts) if county_opts else None

    def summary_table(group_col, categories=None, filter_selection=None):
        if dff.empty:
            return build_summary_count_table(
                pd.DataFrame(columns=df_raw.columns),
                group_col=group_col,
                id_col="record_id",
                categories=categories,
                filter_selection=filter_selection,
                include_statewide_county=(group_col == "county" and include_statewide_county_outputs),
            )
        return build_summary_count_table(
            dff,
            group_col=group_col,
            id_col="record_id",
            categories=categories,
            filter_selection=filter_selection,
            include_statewide_county=(group_col == "county" and include_statewide_county_outputs),
        )

    return (
        format_count_display(filter_total),
        sub_bar,
        mh_bar,
        sub_line,
        summary_table("county", categories=county_categories, filter_selection=county),
        summary_table("age_group", categories=age_opts, filter_selection=age),
        summary_table("sex", categories=sex_opts, filter_selection=sex),
        summary_table("race_ethnicity", categories=race_ethnicity_opts, filter_selection=race_ethnicity),
        summary_table("hawaii_residency", categories=hawaii_residency_opts, filter_selection=hawaii_residency),
    )
