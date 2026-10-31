from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    apply_year_filter,
    build_pre_aggregated_table,
    make_kpi_card,
    make_left_sidebar,
    make_right_summary_tables_col,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    make_filters_card,
    radio_filter,
    STATEWIDE_COUNTY,
    format_count_display,
    apply_standard_bar_layout,
    apply_standard_line_layout,
    apply_standard_single_series_bar_trace,
    create_styled_table,
    wrap_axis_label,
    load_sql_query,
    sort_opts,
)
import re

register_template()

# ----------------------------
# Data helpers
# ----------------------------

sql_substance = load_sql_query("load_wonder_substance")
df_raw_substance = execute_query(sql_substance)

sql_overview = load_sql_query("load_wonder_overview")
df_raw_overview = execute_query(sql_overview)

sql_race = load_sql_query("load_wonder_race")
df_raw_race = execute_query(sql_race)

sql_age_group = load_sql_query("load_wonder_age_group")
df_raw_age_group = execute_query(sql_age_group)

sql_gender = load_sql_query("load_wonder_gender")
df_raw_gender = execute_query(sql_gender)

last_updated_value = max(
    (
        value
        for value in [
            compute_last_updated_value(df_raw_overview),
            compute_last_updated_value(df_raw_substance),
            compute_last_updated_value(df_raw_race),
            compute_last_updated_value(df_raw_age_group),
            compute_last_updated_value(df_raw_gender),
        ]
        if value
    ),
    default=None,
)

# Count number of deaths in wonder_gender.csv "deaths" column
total_unique = df_raw_gender["deaths"].count()

# Build the lists of choices for each filter only if the column exists.
# Why: this makes the code more flexible if the data shape changes later.
wonder_county_opts  = sort_opts(df_raw_gender["county"])                           if "county"  in df_raw_gender.columns else []
wonder_year_opts    = sort_opts(df_raw_gender["year"])                              if "year"    in df_raw_gender.columns else []

# Extract all unique categories for each dimension to show in tables
wonder_gender_opts = sort_opts(df_raw_gender["gender"]) if "gender" in df_raw_gender.columns else []
wonder_race_opts = sort_opts(df_raw_race["race"]) if "race" in df_raw_race.columns else []
wonder_age_group_opts = sort_opts(df_raw_age_group["age_group"]) if "age_group" in df_raw_age_group.columns else []
wonder_substance_opts = sort_opts(df_raw_substance["substance"]) if "substance" in df_raw_substance.columns else []

DEFAULT_COUNTY = "Statewide" if "Statewide" in wonder_county_opts else (wonder_county_opts[0] if wonder_county_opts else None)
DEFAULT_YEAR = wonder_year_opts[-1] if wonder_year_opts else None

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

            # The actual graph. Modebar (tools) is always on now.
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
    href="#wonder-breakdown-filters",
    className="visually-hidden-focusable",
    tabIndex=0
)

# Big green card that shows the total number of discharges.
# Why: gives users a quick "at a glance" number when they open the page.
kpi_card = make_kpi_card(
    label="Number of Unintentional or Undetermined Overdose Deaths",
    count_id="wonder-breakdown-kpi-deaths",
)

reset_filters_button = dbc.Button(
    "Reset All Filters",
    id="wonder-breakdown-reset-filters-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

# Card holding all the filter controls down the left side.
# Each filter uses the options we built from the data above.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="wonder-breakdown-filters",
    title="Filter Data",
    filters=[
        radio_filter(
            "County",
            "wonder-breakdown-county-filter",
            options=opts_list(wonder_county_opts),
            value=DEFAULT_COUNTY,
            labelStyle={"display": "block", "marginBottom": "0.25rem"},
            inputStyle={"marginRight": "0.4rem"},
            persistence="wonder-breakdown-county-filter",
            persistence_type="session",
        ),
        radio_filter(
            "Calendar Year",
            "wonder-breakdown-year-filter",
            options=opts_list(wonder_year_opts),
            value=DEFAULT_YEAR,
            labelStyle={"display": "block", "marginBottom": "0.25rem"},
            inputStyle={"marginRight": "0.4rem"},
            persistence="wonder-breakdown-year-filter",
            persistence_type="session",
        ),
    ],
)

from section_texts import SECTION_TEXTS
wonder_breakdown_sidebar_text = SECTION_TEXTS.get("wonder-breakdown", [])

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
    substance_category_count = (
        df_raw_substance["substance"].dropna().astype(str).nunique()
        if "substance" in df_raw_substance.columns
        else 0
    )
    race_category_count = (
        df_raw_race["race"].dropna().astype(str).nunique()
        if "race" in df_raw_race.columns
        else 0
    )
    age_category_count = (
        df_raw_age_group["age_group"].dropna().astype(str).nunique()
        if "age_group" in df_raw_age_group.columns
        else 0
    )

    def adaptive_bar_height(category_count: int) -> str:
        # Use one shared formula so bar thickness is consistent across charts.
        return f"{compute_adaptive_horizontal_bar_height(category_count)}px"

    substance_bar_h = adaptive_bar_height(substance_category_count)
    race_bar_h = adaptive_bar_height(race_category_count)
    age_bar_h = adaptive_bar_height(age_category_count)
    # Left column: KPI, reset button, and filters.
    left_col = make_left_sidebar(
        kpi_card,
        reset_filters_button,
        filters_card,
        helper_text=wonder_breakdown_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    # Center column: the main line and bar charts.
    center_col = dbc.Col(
        [
            dbc.Row([
                graph_block("wonder-year-substance-line", ""),
                html.P("Line chart showing yearly deaths by substance across all years for the selected county.", className="visually-hidden"),
            ]),
            dbc.Row([
                graph_block("wonder-substance-deaths", ""),
                html.P("Bar chart showing deaths by substance.", className="visually-hidden"),
            ]),
            dbc.Row([
                graph_block("wonder-race-deaths", ""),
                html.P("Bar chart showing deaths by race.", className="visually-hidden"),
            ]),
            dbc.Row([
                graph_block("wonder-age-group-deaths", ""),
                html.P("Bar chart showing deaths by age group.", className="visually-hidden"),
            ]),
        ],
        xs=12, md=6
    )

    right_col = make_right_summary_tables_col(
        [
            ("Sex at Birth", "wonder-gender-table"),
            ("Race/Ethnicity", "wonder-race-table"),
            ("Age Group", "wonder-age-group-table"),
            ("Substance", "wonder-substance-table")

        ],
        xs=12,
        md=3,
    )

    # Wrap everything in a fluid container so it stretches with the screen.
    return dbc.Container([
        skip_link,
        html.Div(
            dbc.Row([left_col, center_col, right_col], className="g-3"),
            id="wonder-breakdown-section",
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
    Output("wonder-breakdown-county-filter", "value"),
    Output("wonder-breakdown-year-filter", "value"),
    Input("wonder-breakdown-reset-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_all_filters(_n_clicks):
    # Reset both filters to default values.
    return DEFAULT_COUNTY, DEFAULT_YEAR

@callback(
    Output("wonder-breakdown-kpi-deaths", "children"),
    Output("wonder-year-substance-line", "figure"),
    Output("wonder-substance-deaths", "figure"),
    Output("wonder-race-deaths", "figure"),
    Output("wonder-age-group-deaths", "figure"),
    Output("wonder-gender-table", "children"),
    Output("wonder-race-table", "children"),
    Output("wonder-age-group-table", "children"),
    Output("wonder-substance-table", "children"),
    Input("wonder-breakdown-county-filter", "value"),
    Input("wonder-breakdown-year-filter", "value"),
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

    def apply_county_only_filter(df):
        """Apply only county logic (no year filter), with per-year statewide fallback."""
        if "county" in df.columns and county is not None:
            county_text = str(county).strip().lower()
            statewide_text = STATEWIDE_COUNTY.lower()
            statewide_rows = df[
                df["county"].astype(str).str.strip().str.lower() == statewide_text
            ]
            non_statewide_rows = df[
                df["county"].astype(str).str.strip().str.lower() != statewide_text
            ]

            if county_text == statewide_text:
                # Statewide: prefer explicit statewide rows; otherwise aggregate source county rows.
                df = statewide_rows if not statewide_rows.empty else non_statewide_rows
            else:
                # Specific county: use county rows and fill any missing years with statewide rows.
                county_rows = apply_filter(non_statewide_rows, "county", county)
                if county_rows.empty:
                    df = statewide_rows
                elif statewide_rows.empty or "year" not in county_rows.columns or "year" not in statewide_rows.columns:
                    df = county_rows
                else:
                    county_years = set(county_rows["year"].astype(str))
                    statewide_fallback = statewide_rows[
                        ~statewide_rows["year"].astype(str).isin(county_years)
                    ]
                    df = pd.concat([county_rows, statewide_fallback], ignore_index=True)

        return df

    def filter_df(df):
        if "year" in df.columns:
            df = apply_year_filter(df, "year", year)
            # Do NOT use apply_county_filter here. The custom logic is correct for the WONDER dashboard's 
            # unique data structure and the tables would fail if we used the generic county filter. 
            # See the comments in apply_county_filter for details.
        if "county" in df.columns and county is not None:
            county_text = str(county).strip().lower()
            statewide_text = STATEWIDE_COUNTY.lower()
            statewide_rows = df[
                df["county"].astype(str).str.strip().str.lower() == statewide_text
            ]
            non_statewide_rows = df[
                df["county"].astype(str).str.strip().str.lower() != statewide_text
            ]

            if county_text == statewide_text:
                # Statewide: prefer the literal "Statewide" row when it exists
                # to get accurate totals. Fall back to aggregating county rows
                # only for years that lack a "Statewide" row.
                df = statewide_rows if not statewide_rows.empty else non_statewide_rows
            else:
                # Specific county: use that county's rows; fall back to the
                # Statewide rows when the source only provides statewide-level
                # data for this year (e.g. gender/race in 2023).
                county_rows = apply_filter(non_statewide_rows, "county", county)
                df = county_rows if not county_rows.empty else statewide_rows

        return df

    def kpi_filter_df(df):
        if "year" in df.columns:
            df = apply_year_filter(df, "year", year)
        # Do NOT use apply_county_filter here. The custom logic is correct for the WONDER dashboard's 
        # unique data structure and the tables would fail if we used the generic county filter. 
        # See the comments in apply_county_filter for details.
        if "county" in df.columns and county is not None:
            county_text = str(county).strip().lower()
            statewide_text = STATEWIDE_COUNTY.lower()

            if county_text == statewide_text:
                statewide_rows = df[
                    df["county"].astype(str).str.strip().str.lower() == statewide_text
                ]
                if not statewide_rows.empty:
                    df = statewide_rows
                else:
                    df = df[
                        df["county"].astype(str).str.strip().str.lower() != statewide_text
                    ]
            else:
                df = apply_filter(df, "county", county)

        return df

    filter_total = pd.to_numeric(
        kpi_filter_df(df_raw_overview.copy())["deaths"],
        errors="coerce",
    ).fillna(0).sum()

    dff_substance = filter_df(df_raw_substance.copy())
    dff_race = filter_df(df_raw_race.copy())
    dff_age_group = filter_df(df_raw_age_group.copy())
    dff_gender = filter_df(df_raw_gender.copy())
    dff_substance_county_only = apply_county_only_filter(df_raw_substance.copy())

    # ---------- Line chart: Number of Deaths per Year by Substance ----------
    if {"county", "year", "substance"}.issubset(dff_substance_county_only.columns):
        by_year_substance = (
            dff_substance_county_only.groupby(["year", "substance"], as_index=False)["deaths"]
            .sum()
            .sort_values(by=["year", "substance"])  # type: ignore[arg-type]
        )

        # Normalize year to numeric so x-axis sorts chronologically, not lexicographically.
        by_year_substance["year"] = pd.to_numeric(by_year_substance["year"], errors="coerce")
        by_year_substance = by_year_substance.dropna(subset=["year"])
        by_year_substance["year"] = by_year_substance["year"].astype(int)
        by_year_substance = by_year_substance.sort_values(by=["year", "substance"])  # type: ignore[arg-type]

        year_substance_line = px.line(
            by_year_substance,
            x="year",
            y="deaths",
            color="substance",
            markers=True,
            labels={
                "year": "Calendar Year",
                "deaths": "Number of Deaths",
                "substance": "Substance",
            },
        )

        apply_standard_line_layout(
            year_substance_line,
            xaxis=dict(type="linear", tickmode="linear", dtick=1),
            yaxis=dict(rangemode="tozero"),
        )
        year_substance_line.update_layout(title="Yearly Deaths by Substance (All Years)")

    # ---------- Bar chart: Deaths by Substance ----------
    if {"county", "year", "substance"}.issubset(dff_substance.columns):
        by_sub = (
            dff_substance.groupby("substance", as_index=False)["deaths"]
            .sum()
            .sort_values(by="deaths", ascending=False)  # type: ignore[arg-type]
        )

        by_sub["substance_label"] = by_sub["substance"].apply(wrap_axis_label)

        sub_bar = px.bar(
            by_sub,
            x="deaths",
            y="substance_label",
            barmode="stack",
            labels={"deaths": "Number of Deaths", "substance_label": "Substance"},
        )

        apply_standard_single_series_bar_trace(sub_bar)

        apply_standard_bar_layout(
            sub_bar,
            xaxis=dict(rangemode="tozero"),
            yaxis=dict(autorange="reversed"),
        )
        sub_bar.update_layout(title="Deaths by Substance")


    # ---------- Bar chart: Deaths by Race ----------
    if {"county", "year", "race"}.issubset(dff_race.columns):
        by_race = (
            dff_race.groupby("race", as_index=False)["deaths"]
            .sum()
            .sort_values(by="deaths", ascending=False)  # type: ignore[arg-type]
        )

        by_race["race_label"] = by_race["race"].apply(wrap_axis_label)

        race_bar = px.bar(
            by_race,
            x="deaths",
            y="race_label",
            barmode="stack",
            labels={"deaths": "Number of Deaths", "race_label": "Race"},
        )

        apply_standard_single_series_bar_trace(race_bar)

        apply_standard_bar_layout(race_bar, yaxis=dict(autorange="reversed"))
        race_bar.update_layout(title="Deaths by Race")

    # ---------- Bar chart: Deaths by Age Group ----------
    if {"county", "year", "age_group"}.issubset(dff_age_group.columns):
        by_age_group = (
            dff_age_group.groupby("age_group", as_index=False)["deaths"]
            .sum()
        )

        # Use the shared sorter to ensure consistent age group ordering
        sorted_age_groups = sort_opts(by_age_group["age_group"])
        by_age_group["age_group"] = pd.Categorical(by_age_group["age_group"], categories=sorted_age_groups, ordered=True)
        by_age_group = by_age_group.sort_values(by="age_group")  # type: ignore[arg-type]

        age_group_bar = px.bar(
            by_age_group,
            x="deaths",
            y="age_group",
            barmode="stack",
            labels={"deaths": "Number of Deaths", "age_group": "Age Group"},
        )

        apply_standard_single_series_bar_trace(age_group_bar)

        apply_standard_bar_layout(age_group_bar, yaxis=dict(autorange="reversed"))
        age_group_bar.update_layout(title="Deaths by Age Group")


    # ---------- Helper for the summary tables ----------
    # Use shared build_summary_count_table for summary tables
    def summary_table(frame, group_col, categories=None):
        return build_pre_aggregated_table(
            frame,
            category_col=group_col,
            count_col="deaths",
            count_label="Deaths",
            categories=categories,
            header_labels=None,
        )

    # Return all the updated visuals and tables to Dash
    return (
        format_count_display(filter_total),
        year_substance_line,
        sub_bar,
        race_bar,
        age_group_bar,
        summary_table(dff_gender[["gender", "deaths"]], "gender", categories=wonder_gender_opts),
        summary_table(dff_race[["race", "deaths"]], "race", categories=wonder_race_opts),
        summary_table(dff_age_group[["age_group", "deaths"]], "age_group", categories=wonder_age_group_opts),
        summary_table(dff_substance[["substance", "deaths"]], "substance", categories=wonder_substance_opts),

    )
