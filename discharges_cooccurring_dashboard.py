# discharges_cooccurring_dashboard.py — Related to co-occurring substance use and mental health disorders

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
    sql = load_sql_query("load_discharges_cooccuring_su_and_mh")
    
    # Execute query using db_utils (automatically uses correct database)
    df = execute_query(sql)
    print(df["county"].unique())
    print(f"load_discharges_cooccuring_su_and_mh returned {len(df):,} rows")

    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")

    # Make the year column numeric when possible so graphs treat it as numbers
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # Clean up text columns by catching true nulls, stripping whitespace, and catching empty strings
    text_cols = ["diagnosis", "diagnosis_type", "county", "city", "zip", "hawaii_residency", "age_group", "sex", "race_ethnicity"]
    for col in text_cols:
        if col in df.columns:
            # Handle true nulls, convert to string, and strip whitespace
            df[col] = df[col].fillna("Unknown").astype(str).str.strip()
            # Explicitly catch empty strings, pandas artifacts, and SQL artifacts
            df[col] = df[col].replace({
                "": "Unknown", 
                "nan": "Unknown", 
                "NaN": "Unknown", 
                "None": "Unknown", 
                "<NA>": "Unknown",
                "NULL": "Unknown",
                "null": "Unknown",
                "N/A": "Unknown",
                "n/a": "Unknown",
                "-": "Unknown"
            })
            
    # Handle the year column separately since it shouldn't be cast to a string right away
    if "year" in df.columns:
        df["year"] = df["year"].fillna("Unknown")
    
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
   href="#discharges-cooccur-filters",
   className="visually-hidden-focusable",
   tabIndex=0
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="discharges-cooccur-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Big green card that shows the total number of discharges.
kpi_card = make_kpi_card(
    label="Number of Discharges Related to Co-Occurring Substance Use and Mental Health Disorders",
    count_id="discharges-cooccur-kpi-total",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="discharges-cooccur-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Substance", "discharges-cooccur-su-filter", options=opts_list(su_opts), multi=True, placeholder="All"),
        dropdown_filter("Mental Health Diagnosis", "discharges-cooccur-mh-filter", options=opts_list(mh_opts), multi=True, placeholder="All"),
        dropdown_filter("County", "discharges-cooccur-county-filter", options=opts_list(county_opts), multi=True, placeholder="All"),
        dropdown_filter("City", "discharges-cooccur-city-filter", options=opts_list(city_opts), multi=True, placeholder="All"),
        dropdown_filter("Year", "discharges-cooccur-year-filter", options=opts_list(year_opts), multi=True, placeholder="All"),
        dropdown_filter("Age Group", "discharges-cooccur-age-filter", options=opts_list(age_opts), multi=True, placeholder="All"),
        dropdown_filter("Sex", "discharges-cooccur-sex-filter", options=opts_list(sex_opts), multi=True, placeholder="All"),
        dropdown_filter("Race/Ethnicity", "discharges-cooccur-race-ethnicity-filter", options=opts_list(race_ethnicity_opts), multi=True, placeholder="All"),
        dropdown_filter("Hawaii Resident", "discharges-cooccur-hawaii-residency-filter", options=opts_list(hawaii_residency_opts), multi=True, placeholder="All"),
    ],
)

from section_texts import SECTION_TEXTS
discharges_sidebar_text = SECTION_TEXTS.get("discharges-cooccurring-su-and-mh", [])

def layout():
    """
    Build the discharges dashboard layout.
    """
    # Adjust plot heights for desktop
    bar_h = f"{compute_adaptive_horizontal_bar_height(max(len(su_opts), len(mh_opts)))}px"
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
        graph_block("discharges-cooccur-su-bar", ""),
        html.P("Bar chart showing discharges by substance.", className="visually-hidden"),
        graph_block("discharges-cooccur-mh-bar", ""),
        html.P("Bar chart showing discharges by mental health diagnosis.", className="visually-hidden"),
        graph_block("discharges-cooccur-line", "", line_h),
        html.P("Line chart showing yearly discharges by substance.", className="visually-hidden"),
        graph_block("discharges-cooccur-mh-line", "", line_h),
        html.P("Line chart showing yearly discharges by mental health diagnosis.", className="visually-hidden"),
    ], xs=12, md=6)

    # Right column: summary tables (ordered by shared site-wide utility)
    right_col = make_right_summary_tables_col(
        [
            ("Calendar Year", "discharges-cooccur-table-year"),
            ("County", "discharges-cooccur-table-county"),
            ("Age Group", "discharges-cooccur-table-age"),
            ("Sex", "discharges-cooccur-table-sex"),
            ("Race/Ethnicity", "discharges-cooccur-table-race-ethnicity"),
            ("Hawaii Residency", "discharges-cooccur-table-hawaii-residency"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="discharges-cooccur-section",
        ),
    ], fluid=True, className="p-2")


# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("discharges-cooccur-su-filter", "value"),
    Output("discharges-cooccur-mh-filter", "value"),
    Output("discharges-cooccur-county-filter", "value"),
    Output("discharges-cooccur-city-filter", "value"),
    Output("discharges-cooccur-year-filter", "value"),
    Output("discharges-cooccur-age-filter", "value"),
    Output("discharges-cooccur-sex-filter", "value"),
    Output("discharges-cooccur-race-ethnicity-filter", "value"),
    Output("discharges-cooccur-hawaii-residency-filter", "value"),
    Input("discharges-cooccur-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)

def reset_discharges_filters(_n_clicks):
    # Reset all multi-select dropdowns to their default empty state.
    return None, None, None, None, None, None, None, None, None

@callback(
    # kpi card
    Output("discharges-cooccur-kpi-total", "children"),
    # graphs
    Output("discharges-cooccur-su-bar", "figure"),
    Output("discharges-cooccur-mh-bar", "figure"),
    Output("discharges-cooccur-line", "figure"),
    Output("discharges-cooccur-mh-line", "figure"),
    # tables 
    Output("discharges-cooccur-table-year", "children"),
    Output("discharges-cooccur-table-county", "children"),
    Output("discharges-cooccur-table-age", "children"),
    Output("discharges-cooccur-table-sex", "children"),
    Output("discharges-cooccur-table-race-ethnicity", "children"),
    Output("discharges-cooccur-table-hawaii-residency", "children"),   
    # filters
    Input("discharges-cooccur-su-filter", "value"),
    Input("discharges-cooccur-mh-filter", "value"),
    Input("discharges-cooccur-county-filter", "value"),
    Input("discharges-cooccur-city-filter", "value"),
    Input("discharges-cooccur-year-filter", "value"),
    Input("discharges-cooccur-age-filter", "value"),
    Input("discharges-cooccur-sex-filter", "value"),
    Input("discharges-cooccur-race-ethnicity-filter", "value"),
    Input("discharges-cooccur-hawaii-residency-filter", "value"),
)
def update_dashboard(su, mh, county, city, year, age, sex, race_ethnicity, hawaii_residency):
    """
    This function runs every time the user changes a filter.
    It updates all the discharge visualizations and tables.
    """

    # Start from the full dataset each time.
    dff = df_raw.copy()

    # Apply filters for substance and mental health diagnoses
    if su:
        su_ids_filtered = set(dff.loc[(dff["diagnosis_type"] == "su") & (dff["diagnosis"].isin(su)), "record_id"])
        dff = dff[dff["record_id"].isin(su_ids_filtered)]
    
    if mh:
        mh_ids_filtered = set(dff.loc[(dff["diagnosis_type"] == "mh") & (dff["diagnosis"].isin(mh)), "record_id"])
        dff = dff[dff["record_id"].isin(mh_ids_filtered)]
    
    # Apply the remaining filters
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
        sub_bar.update_layout(title="Discharges by Substance")
    else:
        sub_bar = px.bar()

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

    # ---------- Line chart: Yearly Discharges by Substance ----------
    if {"record_id", "diagnosis", "diagnosis_type", "year"}.issubset(dff.columns):

        su_df = dff[dff["diagnosis_type"] == "su"]

        by_ysub = (
            su_df.groupby(["year", "diagnosis"])["record_id"].nunique()
            .reset_index().rename(columns={"record_id": "count"})
        )

        by_ysub["display_count"] = by_ysub["count"].apply(format_count_display)

        substances = sort_opts(dff.loc[dff["diagnosis_type"] == "su", "diagnosis"]) if "diagnosis" in dff.columns else []
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
        sub_line.update_layout(title="Yearly Discharges by Substance")
    else:
        sub_line = px.line()

    # ---------- Line chart: Yearly Discharges by Mental Health Diagnosis ----------
    if {"record_id", "diagnosis", "diagnosis_type", "year"}.issubset(dff.columns):

        mh_df = dff[dff["diagnosis_type"] == "mh"]

        by_ymh = (
            mh_df.groupby(["year", "diagnosis"])["record_id"].nunique()
            .reset_index().rename(columns={"record_id": "count"})
        )

        by_ymh["display_count"] = by_ymh["count"].apply(format_count_display)

        mh_diagnoses = sort_opts(dff.loc[dff["diagnosis_type"] == "mh", "diagnosis"]) if "diagnosis" in dff.columns else []
        if mh_diagnoses:
            by_ymh["diagnosis"] = pd.Categorical(by_ymh["diagnosis"], categories=mh_diagnoses, ordered=True)

        mh_line = px.line(
            by_ymh,
            x="year",
            y="count",
            color="diagnosis",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "diagnosis": "Mental Health Diagnosis"},
            category_orders={"diagnosis": mh_diagnoses} if mh_diagnoses else None,
        )

        mh_line.update_traces(
            hovertemplate="Year: %{x}<br>Mental Health Diagnosis: %{fullData.name}<br>Discharges: %{customdata[0]}<extra></extra>"
        )

        max_y_mh = int(by_ymh["count"].max()) if not by_ymh.empty else 0

        apply_standard_line_layout(
            mh_line,
            yaxis=dict(range=[0, max_y_mh * 1.05 if max_y_mh else 1], autorange=False),
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
        mh_line,
        summary_table("year", categories=year_opts, filter_selection=year),
        summary_table("county", categories=county_categories, filter_selection=county),
        summary_table("age_group", categories=age_opts, filter_selection=age),
        summary_table("sex", categories=sex_opts, filter_selection=sex),
        summary_table("race_ethnicity", categories=race_ethnicity_opts, filter_selection=race_ethnicity),
        summary_table("hawaii_residency", categories=hawaii_residency_opts, filter_selection=hawaii_residency),
    )
