# amhd_dashboard.py — AMHD Clients Served page

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

def _load_amhd_series(query_name):
    df = execute_query(load_sql_query(query_name))
    print(f"{query_name} returned {len(df):,} rows")

    if df.empty:
        return pd.DataFrame(columns=["service_date", "service_category", "client_count", "year", "month_num", "month"])

    df.columns = [str(c).strip().lower() for c in df.columns]

    # amhd_aggregate_reporting uses `date`; normalize to service_date for dashboard code.
    if "date" in df.columns and "service_date" not in df.columns:
        df = df.rename(columns={"date": "service_date"})

    required_cols = {"service_date", "service_category", "client_count"}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"{query_name} missing required columns: {missing}")

    df["service_date"] = pd.to_datetime(df["service_date"], errors="coerce")
    df = df[df["service_date"].notna()].copy()

    df["client_count"] = pd.to_numeric(df["client_count"], errors="coerce").fillna(0)
    df["service_category"] = df["service_category"].fillna("Unknown").astype(str).str.strip()

    df["year"] = df["service_date"].dt.year.astype("Int64")
    df["month_num"] = df["service_date"].dt.month.astype("Int64")
    df["month"] = df["month_num"].map(MONTH_NAMES)

    return df


def _load_amhd_kpi_data():
    fallback_total = int(pd.to_numeric(df_day_all["client_count"], errors="coerce").fillna(0).sum())

    try:
        df = execute_query(load_sql_query("load_amhd_kpi_total"))
        print(f"load_amhd_kpi_total returned {len(df):,} rows")
        if df.empty:
            return fallback_total, pd.DataFrame(columns=["service_category", "client_count"])

        df.columns = [str(c).strip().lower() for c in df.columns]

        if "client_count" in df.columns:
            df["client_count"] = pd.to_numeric(df["client_count"], errors="coerce").fillna(0)

        # Most recent query shape: date_type, date, service_category, client_count.
        if {"service_category", "client_count"}.issubset(df.columns):
            service_category_raw = df["service_category"]
            all_rows = df[
                service_category_raw.isna()
                | (service_category_raw.astype(str).str.strip() == "")
                | (service_category_raw.astype(str).str.strip().str.lower() == "all")
            ]
            total = int(all_rows.iloc[0]["client_count"] if not all_rows.empty else df["client_count"].sum())

            df["service_category"] = service_category_raw.fillna("Unknown").astype(str).str.strip()

            category_rows = (
                df[~df["service_category"].str.lower().isin(["all", "unknown"])][['service_category', 'client_count']]
                .copy()
                .sort_values("client_count", ascending=False)
            )
            return total, category_rows

        # Backward-compatible fallback if KPI query returns a single numeric cell.
        value = pd.to_numeric(df.iloc[0, 0], errors="coerce")
        if pd.isna(value):
            return fallback_total, pd.DataFrame(columns=["service_category", "client_count"])
        return int(value), pd.DataFrame(columns=["service_category", "client_count"])

    except Exception as exc:
        print(f"load_amhd_kpi_total failed; falling back to day-all aggregate sum. Details: {exc}")
        return fallback_total, pd.DataFrame(columns=["service_category", "client_count"])


# Pre-aggregated AMHD series from amhd_aggregate_reporting.
df_year_all = _load_amhd_series("load_amhd_year_all")
df_month_all = _load_amhd_series("load_amhd_month_all")
df_day_all = _load_amhd_series("load_amhd_day_all")
df_year_categories = _load_amhd_series("load_amhd_year_categories")
df_month_categories = _load_amhd_series("load_amhd_month_categories")
df_day_categories = _load_amhd_series("load_amhd_day_categories")

# KPI total is kept as a dedicated query supplied by data team.
amhd_kpi_total, amhd_kpi_category_rows = _load_amhd_kpi_data()

# Use day-all as the source for global date bounds/last updated.
df_raw = df_day_all.copy()
last_updated_value = compute_last_updated_value(df_raw)

year_opts = sort_opts(df_raw["year"])
service_category_opts = sort_opts(df_day_categories["service_category"])


reset_button = dbc.Button(
    "Reset All Filters",
    id="amhd-reset-btn",
    color="secondary",
    outline=True,
    className="w-100 mb-3",
    n_clicks=0,
)

kpi_card = make_kpi_card(
    label="Number of AMHD Consumers",
    count_id="amhd-kpi-total",
)

view_toggle_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("View By", className="mb-2 text-center"),
            dbc.RadioItems(
                id="amhd-view-toggle",
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
    card_id="amhd-filters",
    title="Filter Data",
    filters=[
        dropdown_filter(
            "Year",
            "amhd-year-filter",
            options=opts_list(year_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
        dropdown_filter(
            "Service Category",
            "amhd-service-category-filter",
            options=opts_list(service_category_opts),
            multi=True,
            placeholder="All",
            value=None,
        ),
    ],
)

from section_texts import SECTION_TEXTS

amhd_sidebar_text = SECTION_TEXTS.get("amhd", [])


def layout():
    left_col = make_left_sidebar(
        kpi_card,
        reset_button,
        filters_card,
        view_toggle_card=view_toggle_card,
        helper_text=amhd_sidebar_text,
        last_updated_value=last_updated_value,
        xs=12,
        md=3,
    )

    center_col = dbc.Col(
        [
            html.Div(
                [
                    html.H5("Number of AMHD Consumers", id="amhd-bar-chart-title", className="plot-card-header mb-2", style={"display": "none"}),
                    dcc.Graph(
                        id="amhd-bar-chart",
                        style={"width": "100%"},
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                ],
                className="mb-4",
                style={"overflow": "visible"},
            ),
        ],
        xs=12,
        md=6,
    )

    right_col = make_right_summary_tables_col(
        [
            ("Service Category", "amhd-service-category-table"),
        ],
        xs=12,
        md=3,
    )

    return dbc.Container(
        dbc.Row([left_col, center_col, right_col], className="g-3"),
        fluid=True,
    )


layout = layout()


def _select_amhd_frames(view):
    if view == "year":
        return df_year_all.copy(), df_year_categories.copy(), "Calendar Year of Service"
    if view == "month":
        return df_month_all.copy(), df_month_categories.copy(), "Month of Service"
    return df_day_all.copy(), df_day_categories.copy(), "Date of Service"


def _filter_amhd_series(df, sel_years, sel_service_categories=None):
    dff = df.copy()

    if sel_years:
        selected_years_numeric = (
            pd.to_numeric(pd.Series(sel_years), errors="coerce")
            .dropna()
            .astype("Int64")
            .tolist()
        )
        dff = dff[dff["year"].isin(selected_years_numeric)]

    if sel_service_categories:
        dff = dff[dff["service_category"].isin(sel_service_categories)]

    return dff


@callback(
    Output("amhd-year-filter", "value"),
    Output("amhd-service-category-filter", "value"),
    Input("amhd-reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_amhd_filters(_n_clicks):
    return None, None


@callback(
    Output("amhd-kpi-total", "children"),
    Output("amhd-bar-chart", "figure"),
    Output("amhd-service-category-table", "children"),
    Input("amhd-view-toggle", "value"),
    Input("amhd-year-filter", "value"),
    Input("amhd-service-category-filter", "value"),
)
def update_dashboard(view, sel_years, sel_service_categories):
    """
    This single callback updates all components on the AMHD dashboard.
    It ensures the KPI and Table are consistent regardless of the time view.
    """
    # --- 1. Data Filtering ---
    # Bar chart data depends on the view (Year, Month, Day)
    df_all_view, df_categories_view, period_title = _select_amhd_frames(view)
    if sel_service_categories:
        dff_for_bar_chart = _filter_amhd_series(df_categories_view, sel_years, sel_service_categories)
    else:
        dff_for_bar_chart = _filter_amhd_series(df_all_view, sel_years)

    # --- 2. KPI Calculation (Independent of View) ---
    no_filters = not sel_years and not sel_service_categories
    if no_filters:
        kpi_value = format_count_display(amhd_kpi_total)
    else:
        # Always use the yearly data for a stable total, regardless of view
        if sel_service_categories:
            kpi_source_df = _filter_amhd_series(df_year_categories, sel_years, sel_service_categories)
        else:
            kpi_source_df = _filter_amhd_series(df_year_all, sel_years)
        kpi_value = format_count_display(int(kpi_source_df["client_count"].sum()))

    # --- 3. Bar Chart Figure Generation ---
    if sel_service_categories:
        bar_grouped = (
            dff_for_bar_chart.groupby("service_date", as_index=False)["client_count"]
            .sum()
            .sort_values("service_date")
            .rename(columns={"client_count": "consumer_count"})
        )
    else:
        bar_grouped = dff_for_bar_chart.rename(columns={"client_count": "consumer_count"}).sort_values("service_date")

    if view == "year":
        bar_grouped["period"] = bar_grouped["service_date"].dt.year.astype("Int64").astype(str)
    elif view == "month":
        bar_grouped["period"] = (
            bar_grouped["service_date"].dt.year.astype("Int64").astype(str)
            + ", "
            + bar_grouped["service_date"].dt.month.map(MONTH_NAMES)
        )
    else:
        bar_grouped["period"] = bar_grouped["service_date"].dt.strftime("%Y-%m-%d")

    bar_grouped["label"] = bar_grouped["consumer_count"].apply(format_count_display)
    bar_height = compute_adaptive_horizontal_bar_height(len(bar_grouped))
    y_order = bar_grouped["period"].tolist()

    bar_fig = px.bar(
        bar_grouped,
        x="consumer_count",
        y="period",
        orientation="h",
        text="label",
        labels={"consumer_count": "Number of AMHD Consumers", "period": period_title},
    )
    apply_standard_bar_layout(
        bar_fig,
        xaxis=dict(title="Number of AMHD Consumers"),
        yaxis=dict(
            title=period_title,
            type="category",
            categoryorder="array",
            categoryarray=y_order,
            autorange=True,
        ),
        height=bar_height,
    )
    apply_standard_single_series_bar_trace(bar_fig)
    bar_fig.update_traces(hovertemplate="%{y}: %{text}<extra></extra>")
    bar_fig.update_layout(title="Number of AMHD Consumers")    # --- 4. Summary Table Generation (Independent of View) ---
    if no_filters and not amhd_kpi_category_rows.empty:
        table_df = amhd_kpi_category_rows.rename(
            columns={
                "service_category": "Service Category",
                "client_count": "Number of AMHD Consumers",
            }
        ).copy()
    else:
        # Always use the yearly aggregated data for the table to ensure consistency
        dff_for_table = _filter_amhd_series(df_year_categories, sel_years, None)
        
        table_df = (
            dff_for_table.groupby("service_category", as_index=False)["client_count"]
            .sum()
            .rename(columns={
                "service_category": "Service Category",
                "client_count": "Number of AMHD Consumers",
            })
        )

    # Determine which categories to show based on filter
    categories_to_show = service_category_opts
    if sel_service_categories:
        categories_to_show = sel_service_categories
    
    # Ensure all selected categories show, even if zero
    full_categories = pd.DataFrame({"Service Category": categories_to_show})
    table_df = full_categories.merge(table_df, on="Service Category", how="left")
    table_df["Number of AMHD Consumers"] = table_df["Number of AMHD Consumers"].fillna(0).astype(int)
    
    # Sort by count descending
    table_df = table_df.sort_values("Number of AMHD Consumers", ascending=False)
    
    table_df["Number of AMHD Consumers"] = table_df["Number of AMHD Consumers"].apply(format_count_display)
    service_category_table = create_styled_table(table_df)

    # --- 5. Return All Outputs ---
    return kpi_value, bar_fig, service_category_table
