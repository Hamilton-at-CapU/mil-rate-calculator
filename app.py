from shiny import App, ui, render, reactive
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from shinywidgets import output_widget, render_widget

# The 10 property classes used in municipal taxation
PROPERTY_CLASSES = [
    "Residential",
    "Utilities",
    "Port",
    "Port Improvement",
    "Light Industry",
    "Business",
    "Forest",
    "Recreation",
    "Farm",
    "Major Industry",
]

# Helper to create a safe input ID from a class name
def class_id(name):
    return name.lower().replace(" ", "_")

# Default assessed values (in dollars) and mil rates for each class
DEFAULT_ASSESSMENTS = {
    "Residential":       500_000_000,
    "Utilities":          50_000_000,
    "Port":               30_000_000,
    "Port Improvement":   20_000_000,
    "Light Industry":     80_000_000,
    "Business":          120_000_000,
    "Forest":             15_000_000,
    "Recreation":         10_000_000,
    "Farm":               25_000_000,
    "Major Industry":     60_000_000,
}

DEFAULT_MIL_RATES = {
    "Residential":       3.50,
    "Utilities":        25.00,
    "Port":             18.00,
    "Port Improvement": 15.00,
    "Light Industry":   12.00,
    "Business":         10.00,
    "Forest":            8.00,
    "Recreation":        5.00,
    "Farm":              4.50,
    "Major Industry":   15.00,
}

# Build input panels for all property classes
def class_input_panel(cls):
    cid = class_id(cls)
    return ui.accordion_panel(
        cls,
        ui.input_numeric(
            f"assessment_{cid}",
            "Assessed Value ($)",
            value=DEFAULT_ASSESSMENTS[cls],
            min=0,
            step=1_000_000,
        ),
        ui.input_numeric(
            f"milrate_{cid}",
            "Mil Rate (per $1,000)",
            value=DEFAULT_MIL_RATES[cls],
            min=0,
            step=0.01,
        ),
    )


app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style(
            """
            body { font-family: sans-serif; }
            .card { margin-bottom: 1rem; }
            """
        )
    ),
    ui.h2("Municipal Tax Revenue Distribution Calculator"),
    ui.p(
        "Enter the assessed property values and mil rates for each property class. "
        "Revenue is calculated as: Assessed Value × Mil Rate ÷ 1,000."
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.h4("Property Class Inputs"),
            ui.accordion(
                *[class_input_panel(cls) for cls in PROPERTY_CLASSES],
                id="inputs_accordion",
                multiple=True,
            ),
            width=350,
        ),
        ui.card(
            ui.card_header("Revenue Distribution — Pie Chart"),
            output_widget("pie_chart"),
        ),
        ui.card(
            ui.card_header("Revenue by Property Class — Bar Chart"),
            output_widget("bar_chart"),
        ),
        ui.card(
            ui.card_header("Revenue Summary"),
            ui.output_table("revenue_table"),
        ),
    ),
)


def server(input, output, session):

    @reactive.calc
    def revenue_df():
        rows = []
        for cls in PROPERTY_CLASSES:
            cid = class_id(cls)
            assessment = getattr(input, f"assessment_{cid}")() or 0
            milrate = getattr(input, f"milrate_{cid}")() or 0
            revenue = assessment * milrate / 1_000
            rows.append({"Property Class": cls, "Assessed Value": assessment,
                         "Mil Rate": milrate, "Revenue": revenue})
        return pd.DataFrame(rows)

    @render_widget
    def pie_chart():
        df = revenue_df()
        total = df["Revenue"].sum()
        if total <= 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No revenue to display — enter values in the sidebar.",
                showarrow=False,
                font=dict(size=14),
            )
            fig.update_layout(height=400)
            return fig

        fig = px.pie(
            df,
            values="Revenue",
            names="Property Class",
            title="Tax Revenue Distribution by Property Class",
            hole=0.3,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=480, showlegend=True)
        return fig

    @render_widget
    def bar_chart():
        df = revenue_df().sort_values("Revenue", ascending=True)
        fig = px.bar(
            df,
            x="Revenue",
            y="Property Class",
            orientation="h",
            title="Tax Revenue by Property Class",
            text_auto=".3s",
            color="Revenue",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            height=420,
            xaxis_title="Revenue ($)",
            yaxis_title="",
            coloraxis_showscale=False,
        )
        return fig

    @render.table
    def revenue_table():
        df = revenue_df().copy()
        total = df["Revenue"].sum()
        df["Share (%)"] = df["Revenue"].apply(
            lambda x: f"{x / total * 100:.2f}%" if total > 0 else "0.00%"
        )
        df["Assessed Value"] = df["Assessed Value"].apply(lambda x: f"${x:,.0f}")
        df["Mil Rate"] = df["Mil Rate"].apply(lambda x: f"{x:.2f}")
        df["Revenue"] = df["Revenue"].apply(lambda x: f"${x:,.0f}")
        return df[["Property Class", "Assessed Value", "Mil Rate", "Revenue", "Share (%)"]]


app = App(app_ui, server)
