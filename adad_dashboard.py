# adad_dashboard.py — ADAD Clients Served page

from db_utils import execute_query
import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback
import plotly.express as px
from theme import register_template
from dashboard_utils import (
    MONTH_NAMES,
    build_summary_count_table,
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
    apply_standard_line_layout,
)

register_template()

# ----------------------------
# Data load
# ----------------------------

def load_adad_dataframe():
    sql = load_sql_query("load_adad_clients_served")
    df = execute_query(sql)
    print(f"load_adad_clients_served returned {len(df):,} rows")

    if df.empty:
        raise RuntimeError("ADAD query returned 0 rows.")

    df["service_date"] = pd.to_datetime(df["service_date"], errors="coerce")
    df = df[df["service_date"].notna()].copy()

    df["year"] = df["service_date"].dt.year.astype("Int64")
    df["month_num"] = df["service_date"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)

    for col in ["county", "modality"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str)

    return df


def load_adad_kpi_total():
    try:
        sql = load_sql_query("load_adad_kpi_total")
        df = execute_query(sql)
        if df.empty:
            return 0
        value = pd.to_numeric(df.iloc[0, 0], errors="coerce")
        return int(0 if pd.isna(value) else value)
    except Exception as exc:
        print(f"load_adad_kpi_total failed; falling back to dataframe distinct count. Details: {exc}")
        return int(df_raw["client_id"].nunique())


df_raw = load_adad_dataframe()
adad_kpi_total = load_adad_kpi_total()
last_updated_value = compute_last_updated_value(df_raw)

# Filter option lists
year_opts = sort_opts(df_raw["year"])
month_nums_present = sorted(df_raw["month_num"].dropna().unique().tolist())
month_opts = [MONTH_NAMES[m] for m in month_nums_present]
modality_opts = sort_opts(df_raw["modality"])
county_opts = sort_opts(df_raw["county"])

min_date = df_raw["service_date"].min().date()
max_date = df_raw["service_date"].max().date()


# ----------------------------
# UI Components
# ----------------------------

reset_button = dbc.Button(
    "Reset All Filters",
    id="adad-reset-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

kpi_card = make_kpi_card(
    label="Number of Clients Served",
    count_id="adad-kpi-total",
)

view_toggle_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("View By", className="mb-2 text-center"),
            dbc.RadioItems(
                id="adad-view-toggle",
                options=[
                    {"label": "Year View", "value": "year"},
                    {"label": "Month View", "value": "month"},
                    {"label": "Day View", "value": "day"},
                ],
                value="year",
                class_name="spaced-radio-buttons d-flex justify-content-center gap-3",
                input_class_name="btn-check",
                label_class_name="btn btn-outline-success",
                label_checked_class_name="btn-success text-white active",
            ),
        ]
    ),
    className="mb-3",
)

# Card holding all the filter controls down the left side.
# Filter display order is managed centrally in dashboard_utils.make_filters_card.
filters_card = make_filters_card(
    card_id="adad-filters",
    title="Filter Data",
    filters=[
        dropdown_filter("Year", "adad-year-filter", options=opts_list(year_opts), multi=True, placeholder="All",),
        dropdown_filter("Month", "adad-month-filter", options=opts_list(month_opts), multi=True, placeholder="All",),
        dropdown_filter("Island", "adad-county-filter", options=opts_list(county_opts), multi=True, placeholder="All",),
        dropdown_filter("Service Modality", "adad-modality-filter", options=opts_list(modality_opts), multi=True, placeholder="All",),
        (
            "Custom Date Range",
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Start Date", className="form-label mb-1 text-muted small"),
                            dbc.Input(
                                id="adad-start-date",
                                type="date",
                                value=min_date,
                                min=min_date,
                                max=max_date,
                                persistence=True,
                                persistence_type="session",
                            ),
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            html.Label("End Date", className="form-label mb-1 text-muted small"),
                            dbc.Input(
                                id="adad-end-date",
                                type="date",
                                value=max_date,
                                min=min_date,
                                max=max_date,
                                persistence=True,
                                persistence_type="session",
                            ),
                        ],
                        width=6,
                    ),
                ],
                className="g-2",
            ),
        ),
    ],
)

from section_texts import SECTION_TEXTS
adad_sidebar_text = SECTION_TEXTS.get("adad", [])


# ----------------------------
# Layout
# ----------------------------

def layout():
    left_col = make_left_sidebar(
        kpi_card,
        reset_button,
        filters_card,
        view_toggle_card=view_toggle_card,
        helper_text=adad_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    center_col = dbc.Col(
        [
            html.Div(
                [
                    html.H5("Number of Clients Served", id="adad-bar-chart-title", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="adad-bar-chart",
                        style={"width": "100%"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
            html.Div(
                [
                    html.H5("Clients Served by Modality and Year (Top 10 Modalities)", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="adad-modality-line-chart",
                        style={"width": "100%", "height": "520px"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
            html.Div(
                [
                    html.H5("Clients Served by Island and Year", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="adad-county-line-chart",
                        style={"width": "100%", "height": "520px"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
            html.P(
                "Horizontal bar chart showing number of clients served by selected time period.",
                className="visually-hidden",
            ),
        ],
        xs=12,
        md=6,
    )

    right_col = make_right_summary_tables_col(
        [
            ("Modality", "adad-modality-table"),
            ("Year", "adad-year-table"),
            ("Island", "adad-county-table"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container(
        dbc.Row([left_col, center_col, right_col], className="g-3"),
        fluid=True,
    )


layout = layout()


# ----------------------------
# Callbacks
# ----------------------------

@callback(
    Output("adad-year-filter", "value"),
    Output("adad-month-filter", "value"),
    Output("adad-modality-filter", "value"),
    Output("adad-county-filter", "value"),
    Output("adad-start-date", "value"),
    Output("adad-end-date", "value"),
    Input("adad-reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_adad_filters(_n_clicks):
    return None, None, None, None, str(min_date), str(max_date)


@callback(
    Output("adad-bar-chart", "figure"),
    Output("adad-modality-line-chart", "figure"),
    Output("adad-county-line-chart", "figure"),
    Output("adad-kpi-total", "children"),
    Output("adad-modality-table", "children"),
    Output("adad-year-table", "children"),
    Output("adad-county-table", "children"),
    Input("adad-view-toggle", "value"),
    Input("adad-year-filter", "value"),
    Input("adad-month-filter", "value"),
    Input("adad-modality-filter", "value"),
    Input("adad-county-filter", "value"),
    Input("adad-start-date", "value"),
    Input("adad-end-date", "value"),
)
def update_dashboard(view, sel_years, sel_months, sel_modalities, sel_counties, start_date, end_date):
    dff = df_raw.copy()

    start_day = pd.to_datetime(start_date, errors="coerce").date() if start_date else None
    end_day = pd.to_datetime(end_date, errors="coerce").date() if end_date else None

    no_dim_filters = not sel_years and not sel_months and not sel_modalities and not sel_counties
    full_date_range = (start_day == min_date) and (end_day == max_date)

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
    if sel_modalities:
        dff = dff[dff["modality"].isin(sel_modalities)]
    if sel_counties:
        dff = dff[dff["county"].isin(sel_counties)]

    if start_date:
        dff = dff[dff["service_date"] >= pd.to_datetime(start_date)]
    if end_date:
        dff = dff[dff["service_date"] <= pd.to_datetime(end_date)]

    total_clients = adad_kpi_total if (no_dim_filters and full_date_range) else int(dff["client_id"].nunique())

    # Build time-based bar chart
    if view == "year":
        grouped = (
            dff.groupby("year", as_index=False)["client_id"]
            .nunique()
            .rename(columns={"client_id": "client_count"})
            .sort_values("year")
        )
        grouped["period"] = grouped["year"].astype(str)
        y_title = "Calendar Year of Service"
    elif view == "month":
        grouped = (
            dff.groupby(["year", "month_num", "month"], as_index=False)["client_id"]
            .nunique()
            .rename(columns={"client_id": "client_count"})
            .sort_values(["year", "month_num"])
        )
        grouped["period"] = grouped["year"].astype(str) + ", " + grouped["month"]
        y_title = "Month of Service"
    else:
        grouped = (
            dff.groupby("service_date", as_index=False)["client_id"]
            .nunique()
            .rename(columns={"client_id": "client_count"})
            .sort_values("service_date", ascending=True)
        )
        grouped["period"] = grouped["service_date"].dt.strftime("%Y-%m-%d")
        y_title = "Date of Service"

    grouped["label"] = grouped["client_count"].apply(format_count_display)
    chart_height = compute_adaptive_horizontal_bar_height(
        len(grouped),
    )
    y_order = grouped["period"].tolist()

    bar_fig = px.bar(
        grouped,
        x="client_count",
        y="period",
        orientation="h",
        text="label",
        labels={"client_count": "Number of Clients", "period": y_title},
    )
    apply_standard_bar_layout(
        bar_fig,
        xaxis=dict(title="Number of Clients"),
        yaxis=dict(
            title=y_title,
            type="category",
            categoryorder="array",
            categoryarray=y_order,
            autorange=True,
        ),
        height=chart_height,
    )
    apply_standard_single_series_bar_trace(bar_fig)
    bar_fig.update_traces(
        customdata=grouped[["label"]],
        hovertemplate="%{y}: %{customdata[0]}<extra></extra>",
    )
    bar_fig.update_layout(title="Number of Clients Served")

    top_modalities = (
        dff.dropna(subset=["modality"])
        .groupby("modality")["client_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )

    line_grouped = (
        dff[dff["modality"].isin(top_modalities)]
        .groupby(["year", "modality"], as_index=False)["client_id"]
        .nunique()
        .rename(columns={"client_id": "client_count"})
        .sort_values(["year", "modality"])
    )
    line_grouped = line_grouped.dropna(subset=["year", "modality"]).copy()
    if not line_grouped.empty:
        line_grouped["year"] = line_grouped["year"].astype(int)

    if line_grouped.empty:
        modality_line_fig = px.line()
    else:
        modality_line_fig = px.line(
            line_grouped,
            x="year",
            y="client_count",
            color="modality",
            markers=True,
            category_orders={"modality": top_modalities},
            labels={
                "year": "Year",
                "client_count": "Number of Clients",
                "modality": "Modality",
            },
        )
        modality_line_fig.update_traces(
            hovertemplate="%{fullData.name}<br>Year: %{x}<br>Clients: %{y:,}<extra></extra>"
        )

    apply_standard_line_layout(
        modality_line_fig,
        xaxis=dict(dtick=1),
    )
    modality_line_fig.update_layout(title="Clients Served by Modality and Year")
    modality_line_fig.update_traces(
        hovertemplate="%{fullData.name}<br>Year: %{x}<br>Clients: %{y:,}<extra></extra>"
    )

    county_line_grouped = (
        dff.groupby(["year", "county"], as_index=False)["client_id"]
        .nunique()
        .rename(columns={"client_id": "client_count"})
        .sort_values(["year", "county"])
    )
    county_line_grouped = county_line_grouped.dropna(subset=["year", "county"]).copy()
    if not county_line_grouped.empty:
        county_line_grouped["year"] = county_line_grouped["year"].astype(int)

    county_line_fig = px.line(
        county_line_grouped,
        x="year",
        y="client_count",
        color="county",
        markers=True,
        labels={
            "year": "Year",
            "client_count": "Number of Clients",
            "county": "Island",
        },
    )

    apply_standard_line_layout(
        county_line_fig,
        xaxis=dict(dtick=1),
    )
    county_line_fig.update_layout(title="Clients Served by Island and Year")

    # Tables
    # ---------- Helper for the summary tables ----------
    # Use shared build_summary_count_table for summary tables
    def summary_table(group_col, categories=None, filter_selection=None, header_labels=None):
        return build_summary_count_table(
            dff,
            group_col=group_col,
            id_col="client_id",
            categories=categories,
            filter_selection=filter_selection,
            header_labels=header_labels,
            count_label="Number of Clients",
        )

    modality_table = summary_table("modality", categories=modality_opts, filter_selection=sel_modalities)
    year_table = summary_table("year", categories=year_opts, filter_selection=sel_years)
    county_table = summary_table(
        "county",
        categories=county_opts,
        filter_selection=sel_counties,
        header_labels={"county": "Island"},
    )

    return bar_fig, modality_line_fig, county_line_fig, format_count_display(total_clients), modality_table, year_table, county_table
