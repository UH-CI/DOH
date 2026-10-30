# multi_dashboard.py
from dash import Dash, html, dcc, page_container, callback, Input, Output
import dash_bootstrap_components as dbc

TAB_PATHS = {
    "/": "Substance Use Dashboards",
    "/summary": "Summary Dashboard",
    "/adad": "ADAD Clients Served",
    "/adad-cooccurring": "ADAD Co-Occurring Clients Served",
    "/amhd": "AMHD Clients Served",
    "/amhd-cooccurring": "AMHD Co-Occurring Clients Served",
    "/camhd": "CAMHD",
    "/camhd-cooccurring": "CAMHD with Co-Occurring MH and SU",
    "/cares-call-volume": "Hawaiʻi CARES Crisis Center Volume",
    "/cares-statistics": "Hawaiʻi CARES 988 Statistics",
    "/crisis-mobile-outreach": "Referral Destinations for Crisis Mobile Outreach Clients",
    "/discharges-su": "Any Discharge Related to Substance Use",
    "/discharges-mh": "Any Discharge Related to Mental Health Disorders",
    "/discharges-su-polysubstance": "Related to Polysubstance Use",
    "/dose": "Drug Overdose Surveillance and Epidemiology (DOSE)",
    "/dose-polysubstance": "DOSE Polysubstance Co-occurrence",
    "/lcrs": "Licensed Crisis Residential Shelters",
    "/sicm": "Stabilization Bed Facilities Occupancy Rates",
    "/sudors": "SUDORS Overdose Deaths",
    "/sudors-polysubstance": "SUDORS Polysubstance Co-occurrence",
    "/wonder-overview": "CDC WONDER Overdose Deaths Overview",
    "/wonder-breakdown": "WONDER Overdose Deaths Breakdown",
}

DEFAULT_PATH = "/discharges-su"

NAV_GROUPS = {
    "substance": [
        ("/discharges-su", "Any Discharge Related to Substance Use"),
        ("/discharges-su-polysubstance", "Related to Polysubstance Use"),
        ("/discharges-cooccurring-su", "Related to co-occurring substance use and mental health disorders"),
    ],
    "mental_health_discharges": [
        ("/discharges-mh", "Any Discharge Related to Mental Health Disorders"),
        ("/discharges-cooccurring-mh", "Related to co-occurring mental health disorders and substance use"),
    ],
    "adad": [
        ("/adad", "ADAD Clients Served"),
        ("/adad-cooccurring", "ADAD Co-Occurring Clients Served"),
    ],
    "camhd": [
        ("/camhd", "CAMHD"),
        ("/camhd-cooccurring", "CAMHD Co-Occurring Clients Served"),
    ],
    "amhd": [
        ("/amhd", "AMHD Clients Served"),
        ("/amhd-cooccurring", "AMHD Co-Occurring Clients Served"),
    ],
    "lcrs": [
        ("/lcrs", "Licensed Crisis Residential Shelters"),
        ("/sicm", "Stabilization Bed Facilities"),
    ],
    # Example future group:
    # "new-visuals": [
    #     ("/new-overview", "New Visuals Overview"),
    #     ("/new-trends", "New Visuals Trends"),
    #     ("/new-details", "New Visuals Details"),
    # ],
}

ROUTE_TO_GROUP = {
    "/discharges-su": "substance",
    "/discharges-su-polysubstance": "substance",
    "/discharges-cooccurring-su": "substance",
    "/discharges-cooccurring-mh": "mental_health_discharges",
    "/discharges-su-co-sud-mh": "substance",
    "/discharges-su-co-mh-sud": "substance",
    "/discharges-mh": "mental_health_discharges",
    "/discharges-mh-co-sud-mh": "mental_health_discharges",
    "/discharges-mh-co-mh-sud": "mental_health_discharges",
    "/adad": "adad",
    "/adad-cooccurring": "adad",
    "/camhd": "camhd",
    "/camhd-cooccurring": "camhd",
    "/amhd": "amhd",
    "/amhd-cooccurring": "amhd",
    "/lcrs": "lcrs",
    "/sicm": "lcrs",
    # "/polysubstance-alt": "substance",
    # Example future route mapping:
    # "/new-overview": "new-visuals",
    # "/new-trends": "new-visuals",
    # "/new-details": "new-visuals",
}

SUDORS_NAV_GROUPS = {
    "substance": [
        ("/sudors", "SUDORS Overdose Deaths"),
        ("/sudors-polysubstance", "SUDORS with Polysubstance Use"),
        ("/wonder-overview", "CDC WONDER Overdose Deaths Overview"),
        ("/wonder-breakdown", "WONDER Breakdown"),
    ],
}

DOSE_NAV_GROUPS = {
    "dose": [
        ("/dose", "DOSE Discharges"),
        ("/dose-polysubstance", "DOSE Polysubstance Co-occurrence"),
    ],
}

SUDORS_ROUTE_TO_GROUP = {
    "/sudors": "substance",
    "/sudors-polysubstance": "substance",
    "/wonder-overview": "substance",
    "/wonder-breakdown": "substance",
}

DOSE_ROUTE_TO_GROUP = {
    "/dose": "dose",
    "/dose-polysubstance": "dose",
}

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    use_pages=True,
    pages_folder="pages",
    suppress_callback_exceptions=True,
)
server = app.server
app.title = "Substance Use Dashboards"

app.layout = dbc.Container(
    [
        html.A(
            "Skip to navigation",
            href="#top-nav",
            className="visually-hidden-focusable",
            tabIndex=0,
        ),

        dcc.Location(id="url", refresh=False),

        html.Div(
            html.Div(id="top-nav", className="tabs"),
            id="top-nav-wrapper",
            className="mb-2",
        ),

        html.Div(page_container, style={"marginTop": "12px"}),
    ],
    fluid=True,
)

@callback(
    Output("top-nav", "children"),
    Output("top-nav-wrapper", "style"),
    Input("url", "pathname"),
)
def update_active_tab(pathname):
    """Render the active tab group for the current route."""
    if not pathname:
        pathname = "/"

    group_name = ROUTE_TO_GROUP.get(pathname)
    sudors_group_name = SUDORS_ROUTE_TO_GROUP.get(pathname)
    dose_group_name = DOSE_ROUTE_TO_GROUP.get(pathname)
    tabs = []

    if group_name in NAV_GROUPS:
        tabs = [
            html.A(
                label,
                href=path,
                className=("tab tab--selected" if pathname == path else "tab"),
            )
            for path, label in NAV_GROUPS[group_name]
        ]
        nav_style = {}
    elif sudors_group_name in SUDORS_NAV_GROUPS:
        tabs = [
            html.A(
                label,
                href=path,
                className=("tab tab--selected" if pathname == path else "tab"),
            )
            for path, label in SUDORS_NAV_GROUPS[sudors_group_name]
        ]
        nav_style = {}
    elif dose_group_name in DOSE_NAV_GROUPS:
        tabs = [
            html.A(
                label,
                href=path,
                className=("tab tab--selected" if pathname == path else "tab"),
            )
            for path, label in DOSE_NAV_GROUPS[dose_group_name]
        ]
        nav_style = {}
    else:
        nav_style = {"display": "none"}

    return tabs, nav_style

#def update_output_div(input_value):
#    return f'Output: {input_value}'

if __name__ == "__main__":
    app.run(debug=True)
