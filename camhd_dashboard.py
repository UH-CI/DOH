# camhd_dashboard.py — CAMHD Clients Served page

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
    make_filters_card,
    make_last_updated_block,
    compute_last_updated_value,
    compute_adaptive_horizontal_bar_height,
    dropdown_filter,
    format_count_display,
    make_left_sidebar,
    opts_list,
    sort_opts,
    apply_standard_bar_layout,
    apply_standard_single_series_bar_trace,
)

register_template()

def load_camhd_dataframe():
    sql = load_sql_query("load_camhd_clients_served")
    df = execute_query(sql)
    print(f"load_camhd_clients_served returned {len(df):,} rows")

    if df.empty:
        raise RuntimeError("CAMHD query returned 0 rows.")

    df["service_date"] = pd.to_datetime(df["service_date"], errors="coerce")
    df = df[df["service_date"].notna()].copy()

    df["year"] = df["service_date"].dt.year.astype("Int64")
    df["month_num"] = df["service_date"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)

    return df


df_raw = load_camhd_dataframe()
last_updated_value = compute_last_updated_value(df_raw)

year_opts = sort_opts(df_raw["year"])
min_date = df_raw["service_date"].min().date()
max_date = df_raw["service_date"].max().date()


kpi_card = make_kpi_card(
    label="Number of CAMHD Consumers",
    count_id="camhd-kpi-total",
)

reset_button = dbc.Button(
    "Reset All Filters",
    id="camhd-reset-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

view_toggle_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("View By", className="mb-2 text-center"),
            dbc.RadioItems(
                id="camhd-view-toggle",
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

filters_card = make_filters_card(
    card_id="camhd-filters",
    title="Filter Data",
    filters=[
        dropdown_filter(
            "Year",
            "camhd-year-filter",
            options=opts_list(year_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
        (
            "Custom Date Range",
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Start Date", className="form-label mb-1 text-muted small"),
                            dbc.Input(
                                id="camhd-start-date",
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
                                id="camhd-end-date",
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
camhd_sidebar_text = SECTION_TEXTS.get("camhd", [])

def layout():
    # Left column: KPI, reset button, and filters.
    left_col = make_left_sidebar(
        kpi_card,
        reset_button,
        filters_card,
        view_toggle_card=view_toggle_card,
        helper_text=camhd_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )  

    center_col = dbc.Col(
        [
            html.Div(
                [
                    html.H5("Number of Clients Served", id="camhd-bar-chart-title", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="camhd-bar-chart",
                        style={"width": "100%"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
        ],
        xs=12,
        md=9,
    )

    return dbc.Container(
        dbc.Row([left_col, center_col], className="g-3"),
        fluid=True,
    )


layout = layout()


@callback(
    Output("camhd-year-filter", "value"),
    Output("camhd-start-date", "value"),
    Output("camhd-end-date", "value"),
    Input("camhd-reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_camhd_filters(_n_clicks):
    return None, str(min_date), str(max_date)


@callback(
    Output("camhd-bar-chart", "figure"),
    Output("camhd-kpi-total", "children"),
    Input("camhd-view-toggle", "value"),
    Input("camhd-year-filter", "value"),
    Input("camhd-start-date", "value"),
    Input("camhd-end-date", "value"),
)
def update_dashboard(view, sel_years, start_date, end_date):
    dff = df_raw.copy()

    if sel_years:
        selected_years_numeric = (
            pd.to_numeric(pd.Series(sel_years), errors="coerce")
            .dropna()
            .astype("Int64")
            .tolist()
        )
        dff = dff[dff["year"].isin(selected_years_numeric)]

    if start_date:
        dff = dff[dff["service_date"] >= pd.to_datetime(start_date)]
    if end_date:
        dff = dff[dff["service_date"] <= pd.to_datetime(end_date)]

    total_clients = dff["client_id"].nunique()

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
    bar_fig.update_traces(hovertemplate="%{y}: %{text}<extra></extra>")
    bar_fig.update_layout(title="Number of Clients Served")

    return bar_fig, format_count_display(total_clients)