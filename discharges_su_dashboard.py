# discharges_su_dashboard.py — Discharges (Alt Views) page

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
    statewide_first,
    apply_county_filter,
    county_output_should_include_statewide,
    append_statewide_aggregate_rows,
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
    add_stacked_bar_total_labels,
    apply_standard_line_layout,
    build_summary_count_table,
)

register_template()

# ----------------------------
# Data helpers
# ----------------------------

def load_discharge_dataframe_from_db():
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
    sql = load_sql_query("load_discharge_data_view_diag_su")
    
    # Execute query using db_utils (automatically uses correct database)
    df = execute_query(sql)
    print(f"load_discharge_data_view_diag_su returned {len(df):,} rows")

    # If there is no data, we stop early instead of showing a broken page
    if df.empty:
        raise RuntimeError("Query returned 0 rows.")

    # Make the year column numeric when possible so graphs treat it as numbers
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # For these columns, replace missing values with "Unknown"
    # so we don't get blank labels in filters and tables.
    for col in ["county", "city", "zip", "hawaii_residency", "age_group", "sex", "substance", "year"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")
    
    # Trim whitespace from text columns (fixes issue where trailing spaces prevent filter matches)
    for col in ["county", "city", "zip", "hawaii_residency", "age_group", "sex", "substance", "race_ethnicity"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    
    return df

# Load the full dataset once at startup.
# The callbacks will reuse this instead of hitting the database every time.
df_raw = load_discharge_dataframe_from_db()
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
total_unique = df_raw["record_id"].nunique()

# Build the lists of choices for each filter only if the column exists.
substance_opts = sort_opts(df_raw["substance"])                     if "substance"          in df_raw.columns else []
county_opts    = sort_opts(df_raw["county"])                        if "county"             in df_raw.columns else []
city_opts      = sort_opts(df_raw["city"])                          if "city"               in df_raw.columns else []
zip_opts       = sort_opts(df_raw["zip"])                           if "zip"                in df_raw.columns else []
year_opts      = sort_opts(df_raw["year"])                          if "year"               in df_raw.columns else []
hawaii_residency_opts = sort_opts(df_raw["hawaii_residency"])       if "hawaii_residency"   in df_raw.columns else []
age_opts       = sort_opts(df_raw["age_group"])                     if "age_group"          in df_raw.columns else []
sex_opts       = sort_opts(df_raw["sex"])                           if "sex"                in df_raw.columns else []
race_ethnicity_opts = sort_opts(df_raw["race_ethnicity"])           if "race_ethnicity"     in df_raw.columns else []

# ----------------------------
# UI Components
# ----------------------------

# This link helps keyboard and screen reader users jump straight to the filters.
skip_link = html.A(
    "Skip to filters",
    href="#discharges-filters",
    className="visually-hidden-focusable",
    tabIndex=0
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="discharges-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Big green card that shows the total number of discharges.
kpi_card = make_kpi_card(
    label="Number of Emergency Discharges Related to Substance Use",
    count_id="kpi-total-discharges",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="discharges-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Substance", "discharges-substance-filter", options=opts_list(substance_opts), multi=True, placeholder="All"),
        dropdown_filter("County", "discharges-county-filter", options=opts_list(county_opts), multi=True, placeholder="All"),
        dropdown_filter("City", "discharges-city-filter", options=opts_list(city_opts), multi=True, placeholder="All"),
        dropdown_filter("Year", "discharges-year-filter", options=opts_list(year_opts), multi=True, placeholder="All"),
        dropdown_filter("Age Group", "discharges-age-filter", options=opts_list(age_opts), multi=True, placeholder="All"),
        dropdown_filter("Sex", "discharges-sex-filter", options=opts_list(sex_opts), multi=True, placeholder="All"),
        dropdown_filter("Race/Ethnicity", "discharges-race-ethnicity-filter", options=opts_list(race_ethnicity_opts), multi=True, placeholder="All"),
        dropdown_filter("Hawaii Resident", "discharges-hawaii-residency-filter", options=opts_list(hawaii_residency_opts), multi=True, placeholder="All"),
    ],
)

from section_texts import SECTION_TEXTS
discharges_sidebar_text = SECTION_TEXTS.get("discharges-su", [])

# ----------------------------
# Layout
# ----------------------------

def layout():
    """
    Build the discharges dashboard layout.
    """
    # Adjust plot heights for desktop
    line_h = "400px"
    bar_h  = "360px"
    substance_bar_h = f"{compute_adaptive_horizontal_bar_height(len(substance_opts))}px"

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
    center_col = dbc.Col(
        [
            graph_block("bar-substances", "Discharges by Substance"),
            html.P("Bar chart showing discharges by substance.", className="visually-hidden"),
            graph_block("substance-year-lines", "Yearly Discharges by Substance", line_h),
            html.P("Line chart showing yearly discharges by substance.", className="visually-hidden"),
            graph_block("county-year-lines", "Yearly Discharges by County", line_h),
            html.P("Line chart showing yearly discharges by county.", className="visually-hidden"),
            graph_block("age-year-lines", "Yearly Discharges by Age Group", line_h),
            html.P("Line chart showing yearly discharges by age group.", className="visually-hidden"),
            graph_block("sex-year-stacked", "Yearly Discharges by Gender", bar_h),
            html.P("Stacked bar chart showing yearly discharges by gender.", className="visually-hidden"),
        ],
        xs=12, md=6
    )

    # Right column: summary tables (ordered by shared site-wide utility)
    right_col = make_right_summary_tables_col(
        [
            ("Calendar Year", "table-year"),
            ("County", "table-county"),
            ("Age Group", "table-age"),
            ("Sex", "table-sex"),
            ("Race/Ethnicity", "table-race-ethnicity"),
            ("Hawaii Resident", "table-hawaii-residency"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="discharges-section",
        ),
    ], fluid=True, className="p-2")


# ----------------------------
# Callbacks for discharges
# ----------------------------

@callback(
    Output("discharges-substance-filter", "value"),
    Output("discharges-county-filter", "value"),
    Output("discharges-city-filter", "value"),
    Output("discharges-year-filter", "value"),
    Output("discharges-age-filter", "value"),
    Output("discharges-sex-filter", "value"),
    Output("discharges-race-ethnicity-filter", "value"),
    Output("discharges-hawaii-residency-filter", "value"),
    Input("discharges-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_discharges_filters(_n_clicks):
    return None, None, None, None, None, None, None, None


@callback(
    Output("kpi-total-discharges", "children"),
    Output("bar-substances", "figure"),
    Output("substance-year-lines", "figure"),
    Output("county-year-lines", "figure"),
    Output("age-year-lines", "figure"),
    Output("sex-year-stacked", "figure"),
    Output("table-year", "children"),
    Output("table-county", "children"),
    Output("table-age", "children"),
    Output("table-sex", "children"),
    Output("table-race-ethnicity", "children"),
    Output("table-hawaii-residency", "children"),
    Input("discharges-substance-filter", "value"),
    Input("discharges-county-filter", "value"),
    Input("discharges-city-filter", "value"),
    Input("discharges-year-filter", "value"),
    Input("discharges-hawaii-residency-filter", "value"),
    Input("discharges-age-filter", "value"),
    Input("discharges-sex-filter", "value"),
    Input("discharges-race-ethnicity-filter", "value"),
)

def update_dashboard(substance, county, city, year, hawaii_residency, age, sex, race_ethnicity):
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
    if "substance" in dff.columns:          dff = apply_filter(dff, "substance", substance)
    if "county" in dff.columns:             dff = apply_county_filter(dff, county)
    if "city" in dff.columns:               dff = apply_filter(dff, "city", city)
    if "year" in dff.columns:               dff = apply_year_filter(dff, "year", year)
    if "hawaii_residency" in dff.columns:   dff = apply_filter(dff, "hawaii_residency", hawaii_residency)
    if "age_group" in dff.columns:          dff = apply_filter(dff, "age_group", age)
    if "sex" in dff.columns:                dff = apply_filter(dff, "sex", sex)
    if "race_ethnicity" in dff.columns:     dff = apply_filter(dff, "race_ethnicity", race_ethnicity)

    include_statewide_county_outputs = county_output_should_include_statewide(county)

    filter_total = dff["record_id"].nunique()

    # ---------- Bar chart: Discharges by Substance ----------
    if {"substance"}.issubset(dff.columns):
        by_sub = (
            dff.groupby("substance")["record_id"].nunique()
            .reset_index(name="count")
            .sort_values("count", ascending=True)
            .tail(10)
        )

        def wrap_substance_label(label: str, max_len: int = 22):
            """
            Break long labels into two lines so they don't stretch the chart.

            We look for the last space before `max_len` and insert a line break there.
            """
            s = str(label)
            if len(s) <= max_len:
                return s
            cut = s.rfind(" ", 0, max_len)
            if cut == -1:
                return s
            return s[:cut] + "<br>" + s[cut+1:]

        by_sub["substance_label"] = by_sub["substance"].apply(wrap_substance_label)
        by_sub["display_count"] = by_sub["count"].apply(format_count_display)

        sub_bar = px.bar(
            by_sub,
            x="count",
            y="substance_label",
            barmode="stack",
            text="display_count",
            labels={"count": "Number of Discharges", "substance_label": "Substance Type"},
        )

        apply_standard_single_series_bar_trace(
            sub_bar,
            customdata=by_sub["substance"],
            hovertemplate="%{customdata}:<br>%{text}<extra></extra>",
        )

        apply_standard_bar_layout(sub_bar)
        sub_bar.update_layout(title="Discharges by Substance")
    else:
        sub_bar = px.bar()

    # ---------- Line chart: Yearly Discharges by Substance ----------
    if {"year", "substance"}.issubset(dff.columns):
        by_ysub = (
            dff.groupby(["year", "substance"])["record_id"].nunique()
            .reset_index(name="count")
            .sort_values(["year", "substance"])
        )
        by_ysub["display_count"] = by_ysub["count"].apply(format_count_display)

        substances = sort_opts(by_ysub["substance"]) if "substance" in by_ysub.columns else []
        if substances:
            by_ysub["substance"] = pd.Categorical(
                by_ysub["substance"],
                categories=substances,
                ordered=True,
            )

        substance_line_fig = px.line(
            by_ysub,
            x="year",
            y="count",
            color="substance",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "substance": "Substance"},
            category_orders={"substance": substances} if substances else None,
        )
        substance_line_fig.update_traces(
            hovertemplate="Year %{x}<br>Substance: %{fullData.name}<br>Discharges: %{customdata[0]}<extra></extra>"
        )
        max_y = int(by_ysub["count"].max()) if not by_ysub.empty else 0
        
        apply_standard_line_layout(
            substance_line_fig,
        )
        substance_line_fig.update_layout(title="Yearly Discharges by Substance")

    
    else:
        substance_line_fig = px.line()

    # ---------- Line chart: Yearly Discharges by County ----------
    if {"county", "year"}.issubset(dff.columns):
        by_cy = (
            dff.groupby(["year", "county"])["record_id"].nunique()
            .reset_index(name="count")
        )
        if include_statewide_county_outputs:
            by_cy = append_statewide_aggregate_rows(by_cy, value_col="count", county_col="county")

        by_cy["display_count"] = by_cy["count"].apply(format_count_display)

        counties = statewide_first(sort_opts(by_cy["county"])) if "county" in by_cy.columns else []
        if counties:
            by_cy["county"] = pd.Categorical(by_cy["county"], categories=counties, ordered=True)

        line_fig = px.line(
            by_cy,
            x="year",
            y="count",
            color="county",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "county": "County"},
        )
        line_fig.update_traces(
            hovertemplate="Year %{x}<br>%{customdata[0]} discharges<extra></extra>"
        )
        max_y = int(by_cy["count"].max()) if not by_cy.empty else 0
        
        apply_standard_line_layout(
            line_fig,
        )
        line_fig.update_layout(title="Yearly Discharges by County")
        
    else:
        line_fig = px.line()

    # ---------- Line chart: Yearly Discharges by Age Group ----------
    if {"year", "age_group"}.issubset(dff.columns):
        by_ya = (
            dff.groupby(["year", "age_group"])["record_id"].nunique()
            .reset_index(name="count")
        )
        by_ya["display_count"] = by_ya["count"].apply(format_count_display)

        age_line_fig = px.line(
            by_ya,
            x="year",
            y="count",
            color="age_group",
            markers=True,
            custom_data=["display_count"],
            labels={"year": "Year", "count": "Discharges", "age_group": "Age Group"},
            category_orders={"age_group": age_opts} if age_opts else None,
        )
        age_line_fig.update_traces(
            hovertemplate="Year %{x}<br>Age Group: %{fullData.name}<br>Discharges: %{customdata[0]}<extra></extra>"
        )
        max_y = int(by_ya["count"].max()) if not by_ya.empty else 0
        
        apply_standard_line_layout(
            age_line_fig,
        )
        age_line_fig.update_layout(title="Yearly Discharges by Age Group")
        
    else:
        age_line_fig = px.line()

    # ---------- Stacked bar chart: Yearly Discharges by Sex at Birth ----------
    if {"year", "sex"}.issubset(dff.columns):
        by_ys = (
            dff.groupby(["year", "sex"])["record_id"].nunique()
            .reset_index(name="count")
            .sort_values(["year", "sex"])
        )
        sex_bar = px.bar(
            by_ys,
            x="year",
            y="count",
            color="sex",
            barmode="stack",
            labels={"year": "Year", "count": "Discharges", "sex": "Sex at Birth"},
            text=by_ys["count"].map(format_count_display)
        )
        sex_bar.update_traces(
            textposition="inside",
            insidetextanchor="middle",
            cliponaxis=False
        )

        totals = by_ys.groupby("year")["count"].sum().reset_index()
        add_stacked_bar_total_labels(sex_bar, totals, x_col="year", y_col="count")

        max_y = int(totals["count"].max()) if not totals.empty else 0
        apply_standard_bar_layout(
            sex_bar,
            xaxis=dict(dtick=1),
            yaxis=dict(range=[0, max_y * 1.25 if max_y else 1]),
        )
        sex_bar.update_layout(title="Yearly Discharges by Gender")
        # Keep segment labels inside stacked bars so top total annotations stay readable.
        sex_bar.update_traces(
            textposition="inside",
            insidetextanchor="middle",
            selector={"type": "bar"},
        )
    else:
        sex_bar = px.bar()

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
        sub_bar,
        substance_line_fig,
        line_fig,
        age_line_fig,
        sex_bar,
        summary_table("year", year_opts, filter_selection=year),
        summary_table("county", county_opts, filter_selection=county),
        summary_table("age_group", age_opts, filter_selection=age),
        summary_table("sex", sex_opts, filter_selection=sex),
        summary_table("race_ethnicity", race_ethnicity_opts, filter_selection=race_ethnicity),
        summary_table("hawaii_residency", hawaii_residency_opts, filter_selection=hawaii_residency),
    )
