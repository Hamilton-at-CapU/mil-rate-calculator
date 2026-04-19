from shiny import App, ui, render, reactive
import plotly.express as px
import pandas as pd
from shinywidgets import output_widget, render_widget

# ---------------------------------------------------------------------------
# Static data from 2026 Tax Numbers (Hamilton).xlsx
# ---------------------------------------------------------------------------

PROPERTY_CLASSES = [
    "1 - Residential",
    "2 - Utilities",
    "4 - Port",
    "4 - Port Improvement",
    "5 - Light Industry",
    "6 - Business/Other",
    "7 - Managed Forest",
    "8 - Rec/Non Profit",
    "9 - Farm",
]

# Classes whose tax rate is fixed (not driven by Base Tax Increase)
FIXED_RATE_CLASSES = {
    "2 - Utilities":        40.0,
    "4 - Port":             27.5,
    "4 - Port Improvement": 22.5,
}

# Default values from spreadsheet: (Net Taxable Value, NMC Value, Prior Year Revenue)
DEFAULT_DATA = {
    "1 - Residential":      (11_746_534_110, 217_878_600, 29_698_249),
    "2 - Utilities":        (    66_078_050,     555_900,  2_531_178),
    "4 - Port":             (    24_576_780,           0,    652_744),
    "4 - Port Improvement": (     4_177_220,           0,     95_644),
    "5 - Light Industry":   (   152_099_600,     802_000,  1_844_152),
    "6 - Business/Other":   ( 1_957_079_917,  56_721_100, 13_257_409),
    "7 - Managed Forest":   (     1_897_900,           0,     43_923),
    "8 - Rec/Non Profit":   (    28_380_900,   1_379_900,     85_855),
    "9 - Farm":             (        44_568,           0,        118),
}

TOTAL_REQUIRED_REVENUE = 54_629_865
DEFAULT_BASE_TAX_INCREASE = 11.58  # percent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_id(cls):
    return cls.replace(" ", "_").replace("/", "_").replace("-", "_")


def make_class_row(cls):
    ntv, nmc, pyr = DEFAULT_DATA[cls]
    c = safe_id(cls)
    return ui.tags.tr(
        ui.tags.td(cls, style="padding: 4px 8px; white-space: nowrap; font-size: 0.85rem; font-weight: 500;"),
        ui.tags.td(ui.input_numeric(f"ntv_{c}", None, value=ntv, min=0, step=1_000_000, width="100%")),
        ui.tags.td(ui.input_numeric(f"nmc_{c}", None, value=nmc, min=0, step=100_000, width="100%")),
        ui.tags.td(ui.input_numeric(f"pyr_{c}", None, value=pyr, min=0, step=10_000, width="100%")),
    )


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

CSS = """
body { font-family: sans-serif; }
.card { margin-bottom: 1rem; }
.input-table { border-collapse: collapse; width: 100%; }
.input-table th {
    background: #f0f0f0; border: 1px solid #ccc;
    padding: 6px 8px; text-align: center; font-size: 0.85rem;
}
.input-table td { border: 1px solid #ddd; padding: 2px 4px; vertical-align: middle; }
.shiny-input-container { margin-bottom: 0 !important; }
.stat-box {
    background: #f8f9fa; border: 1px solid #dee2e6;
    border-radius: 6px; padding: 12px 18px; text-align: center;
}
.stat-value { font-size: 1.4rem; font-weight: 700; color: #0d6efd; }
.stat-label { font-size: 0.8rem; color: #666; margin-top: 4px; }
"""

app_ui = ui.page_fluid(
    ui.tags.head(ui.tags.style(CSS)),
    ui.h2("Hamilton 2026 Tax Rate Calculator"),
    ui.p(
        "Revenue Distribution Method. "
        "Edit the property class table, then adjust the Base Tax Increase slider "
        "until the Difference to Required Revenue approaches zero."
    ),

    ui.layout_columns(
        ui.div(
            ui.div(ui.output_text("stat_required"), class_="stat-value"),
            ui.div("Total Required Revenue", class_="stat-label"),
            class_="stat-box",
        ),
        ui.div(
            ui.div(ui.output_text("stat_total_rev"), class_="stat-value"),
            ui.div("Total Revenue (incl. NMC)", class_="stat-label"),
            class_="stat-box",
        ),
        ui.div(
            ui.div(ui.output_text("stat_diff"), class_="stat-value"),
            ui.div("Difference to Required Revenue", class_="stat-label"),
            class_="stat-box",
        ),
        col_widths=[4, 4, 4],
    ),

    ui.br(),

    ui.card(
        ui.card_header("Base Tax Increase — adjust until Difference is near $0"),
        ui.input_slider(
            "base_tax_increase",
            "Base Tax Increase (%)",
            min=0.0, max=30.0,
            value=DEFAULT_BASE_TAX_INCREASE,
            step=0.01, post="%", width="100%",
        ),
    ),

    ui.card(
        ui.card_header("Step 1 — Input Data by Property Class"),
        ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Property Class"),
                    ui.tags.th("Net Taxable Value ($)"),
                    ui.tags.th("NMC Value ($)"),
                    ui.tags.th("Prior Year Revenue ($)"),
                )
            ),
            ui.tags.tbody(*[make_class_row(cls) for cls in PROPERTY_CLASSES]),
            class_="input-table",
        ),
    ),

    ui.card(
        ui.card_header("Calculated Results"),
        ui.output_table("results_table"),
    ),

    ui.layout_columns(
        ui.card(ui.card_header("Revenue Distribution"), output_widget("pie_chart")),
        ui.card(ui.card_header("Revenue by Property Class"), output_widget("bar_chart")),
        col_widths=[6, 6],
    ),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def server(input, output, session):

    @reactive.calc
    def calc_df():
        base_pct = input.base_tax_increase() / 100.0
        rows = []
        for cls in PROPERTY_CLASSES:
            c = safe_id(cls)
            ntv = getattr(input, f"ntv_{c}")() or 0
            nmc = getattr(input, f"nmc_{c}")() or 0
            pyr = getattr(input, f"pyr_{c}")() or 0

            base_value = ntv - nmc

            if cls in FIXED_RATE_CLASSES:
                tax_rate = FIXED_RATE_CLASSES[cls]
                base_revenue = base_value * tax_rate / 1000
            else:
                base_revenue = pyr * (1 + base_pct)
                tax_rate = (1000 * base_revenue / base_value) if base_value else 0

            revenue_incl_nmc = ntv * tax_rate / 1000
            nmc_revenue = nmc * tax_rate / 1000

            rows.append({
                "Property Class": cls,
                "Net Taxable Value": ntv,
                "NMC Value": nmc,
                "Base Value": base_value,
                "Prior Year Revenue": pyr,
                "Base Revenue": base_revenue,
                "Tax Rate (per $1k)": tax_rate,
                "Revenue (incl. NMC)": revenue_incl_nmc,
                "NMC Revenue": nmc_revenue,
            })
        return pd.DataFrame(rows)

    @render.text
    def stat_required():
        return f"${TOTAL_REQUIRED_REVENUE:,.0f}"

    @render.text
    def stat_total_rev():
        return f"${calc_df()['Revenue (incl. NMC)'].sum():,.0f}"

    @render.text
    def stat_diff():
        diff = calc_df()["Revenue (incl. NMC)"].sum() - TOTAL_REQUIRED_REVENUE
        sign = "+" if diff >= 0 else ""
        return f"{sign}${diff:,.0f}"

    @render.table
    def results_table():
        df = calc_df().copy()
        totals = {
            "Property Class": "TOTAL",
            "Net Taxable Value": df["Net Taxable Value"].sum(),
            "NMC Value": df["NMC Value"].sum(),
            "Base Value": df["Base Value"].sum(),
            "Prior Year Revenue": df["Prior Year Revenue"].sum(),
            "Base Revenue": df["Base Revenue"].sum(),
            "Tax Rate (per $1k)": None,
            "Revenue (incl. NMC)": df["Revenue (incl. NMC)"].sum(),
            "NMC Revenue": df["NMC Revenue"].sum(),
        }
        df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
        money_cols = [
            "Net Taxable Value", "NMC Value", "Base Value",
            "Prior Year Revenue", "Base Revenue", "Revenue (incl. NMC)", "NMC Revenue",
        ]
        for col in money_cols:
            df[col] = df[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
        df["Tax Rate (per $1k)"] = df["Tax Rate (per $1k)"].apply(
            lambda x: f"{x:.4f}" if pd.notna(x) else "—"
        )
        return df

    @render_widget
    def pie_chart():
        df = calc_df()
        fig = px.pie(df, values="Revenue (incl. NMC)", names="Property Class", hole=0.3)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=420, showlegend=False, margin=dict(t=20))
        return fig

    @render_widget
    def bar_chart():
        df = calc_df().sort_values("Revenue (incl. NMC)", ascending=True)
        fig = px.bar(
            df, x="Revenue (incl. NMC)", y="Property Class",
            orientation="h", text_auto=".3s",
            color="Revenue (incl. NMC)", color_continuous_scale="Blues",
        )
        fig.update_layout(
            height=420, xaxis_title="Revenue ($)", yaxis_title="",
            coloraxis_showscale=False, margin=dict(t=20),
        )
        return fig


app = App(app_ui, server)
