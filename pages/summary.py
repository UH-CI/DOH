from dash import register_page

import summary_dashboard

register_page(
    __name__,
    path="/summary",
    name="Summary Dashboard",
    title="Summary Dashboard",
)

layout = summary_dashboard.layout
