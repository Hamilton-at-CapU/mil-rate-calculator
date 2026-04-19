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

FIXED_RATE_CLASSES = {
    "2 - Utilities":        40.0,
    "4 - Port":             27.5,
    "4 - Port Improvement": 22.5,
}

VARIABLE_CLASSES = [c for c in PROPERTY_CLASSES if c not in FIXED_RATE_CLASSES]
PIE_COLORS = px.colors.qualitative.Plotly
CLASS_COLORS = {cls: PIE_COLORS[i % len(PIE_COLORS)] for i, cls in enumerate(VARIABLE_CLASSES)}

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
DEFAULT_BASE_TAX_INCREASE = 10.0


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
    ui.p("Revenue Distribution Method."),


    ui.br(),

    ui.card(
        ui.card_header(
            ui.layout_columns(
                "Step 1 — Input Data",
                ui.input_checkbox("show_step1", "Show", value=True),
                col_widths=[10, 2],
            )
        ),
        ui.panel_conditional(
            "input.show_step1",
            ui.card(
                ui.card_header("Step 1a — Total Required Revenue"),
                ui.input_numeric(
                    "total_required_revenue",
                    "Total Required Revenue ($)",
                    value=TOTAL_REQUIRED_REVENUE,
                    min=0,
                    step=1,
                    width="300px",
                ),
            ),
            ui.card(
                ui.card_header("Step 1b — Input data by property class from BC Assessment and last year's revenue"),
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
        ),
    ),

    ui.card(
        ui.card_header("Step 2 — Adjust Base Tax Increase until 'Difference to Required Revenue' is near $0"),
        ui.input_slider(
            "base_tax_increase",
            "Base Tax Increase (%)",
            min=10.0, max=14.0,
            value=DEFAULT_BASE_TAX_INCREASE,
            step=0.0001, post="%", width="100%",
        ),
    ),

    ui.card(
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
    ),

    ui.card(
        ui.card_header("Calculated Results"),
        ui.p("Fixed rate classes (grey) are not impacted by Base Tax Increase.", style="font-size:0.78rem; color:#666; margin-bottom:6px;"),
        ui.output_ui("results_table"),
    ),

    ui.card(
        ui.card_header("Revenue Distribution (variable-rate classes only)"),
        ui.layout_columns(
            ui.div(
                ui.tags.p("Prior Year Revenue", style="text-align:center; font-weight:600; margin-bottom:4px;"),
                output_widget("prior_year_pie"),
            ),
            ui.div(
                ui.tags.p("Current Year Revenue from Base", style="text-align:center; font-weight:600; margin-bottom:4px;"),
                output_widget("pie_chart"),
            ),
            ui.div(
                ui.tags.p("Current Year Revenue with NMC", style="text-align:center; font-weight:600; margin-bottom:4px;"),
                output_widget("nmc_pie"),
            ),
            col_widths=[4, 4, 4],
        ),
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

            rows.append({
                "Property Class": cls,
                "Net Taxable Value": ntv,
                "NMC Value": nmc,
                "Base Value": base_value,
                "Prior Year Revenue": pyr,
                "Base Revenue": base_revenue,
                "Tax Rate": tax_rate,
                "Revenue (incl. NMC)": revenue_incl_nmc,
            })
        return pd.DataFrame(rows)

    @render.text
    def stat_required():
        return f"${input.total_required_revenue():,.0f}"

    @render.text
    def stat_total_rev():
        return f"${calc_df()['Revenue (incl. NMC)'].sum():,.0f}"

    @render.text
    def stat_diff():
        diff = calc_df()["Revenue (incl. NMC)"].sum() - (input.total_required_revenue() or 0)
        sign = "+" if diff >= 0 else ""
        return f"{sign}${diff:,.0f}"

    @render.ui
    def results_table():
        df = calc_df().copy()
        totals = {
            "Property Class": "TOTAL",
            "Net Taxable Value": df["Net Taxable Value"].sum(),
            "NMC Value": df["NMC Value"].sum(),
            "Base Value": df["Base Value"].sum(),
            "Prior Year Revenue": df["Prior Year Revenue"].sum(),
            "Base Revenue": df["Base Revenue"].sum(),
            "Tax Rate": None,
            "Revenue (incl. NMC)": df["Revenue (incl. NMC)"].sum(),
        }
        df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)

        money_cols = [
            "Net Taxable Value", "NMC Value", "Base Value",
            "Prior Year Revenue", "Base Revenue", "Revenue (incl. NMC)",
        ]
        for col in money_cols:
            df[col] = df[col].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
        df["Tax Rate"] = df["Tax Rate"].apply(
            lambda x: f"{x:.4f}" if pd.notna(x) else "—"
        )

        columns = ["Property Class", "Net Taxable Value", "NMC Value", "Base Value",
                   "Prior Year Revenue", "Base Revenue", "Tax Rate", "Revenue (incl. NMC)"]

        header_cells = [
            ui.tags.th(c, style="padding:6px 10px; background:#f0f0f0; border:1px solid #ccc; white-space:nowrap;")
            for c in columns
        ]
        header = ui.tags.thead(ui.tags.tr(*header_cells))

        body_rows = []
        for _, row in df.iterrows():
            is_fixed = row["Property Class"] in FIXED_RATE_CLASSES
            is_total = row["Property Class"] == "TOTAL"
            if is_total:
                row_style = "font-weight:700; border-top:2px solid #999;"
            elif is_fixed:
                row_style = "color:#999;"
            else:
                row_style = ""
            cells = [
                ui.tags.td(str(row[c]), style=f"padding:4px 10px; border:1px solid #ddd; {row_style}")
                for c in columns
            ]
            body_rows.append(ui.tags.tr(*cells))

        body = ui.tags.tbody(*body_rows)
        return ui.tags.table(header, body, style="border-collapse:collapse; width:100%; font-size:0.85rem;")

    def _make_pie(df, value_col, showlegend=False):
        fig = px.pie(
            df, values=value_col, names="Property Class", hole=0.3,
            color="Property Class", color_discrete_map=CLASS_COLORS,
        )
        fig.update_traces(textposition="inside", textinfo="percent")
        fig.update_layout(
            height=380,
            showlegend=showlegend,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.05,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
            margin=dict(t=20, b=5),
        )
        return fig

    @render_widget
    def prior_year_pie():
        df = calc_df()
        df = df[~df["Property Class"].isin(FIXED_RATE_CLASSES)]
        return _make_pie(df, "Prior Year Revenue")

    @render_widget
    def pie_chart():
        df = calc_df()
        df = df[~df["Property Class"].isin(FIXED_RATE_CLASSES)]
        return _make_pie(df, "Base Revenue")

    @render_widget
    def nmc_pie():
        df = calc_df()
        df = df[~df["Property Class"].isin(FIXED_RATE_CLASSES)]
        return _make_pie(df, "Revenue (incl. NMC)", showlegend=True)


app = App(app_ui, server)
