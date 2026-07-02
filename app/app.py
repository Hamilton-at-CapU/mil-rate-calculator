from shiny import App, ui, render, reactive
import plotly.express as px
import pandas as pd
from shinywidgets import output_widget, render_widget

# ---------------------------------------------------------------------------
# Input data from 2026 Tax Numbers 
# ---------------------------------------------------------------------------

PROPERTY_CLASSES = [
    "1 - Residential",
    "6 - Business/Other",
    "5 - Light Industry",
    "8 - Rec/Non Profit",
    "7 - Managed Forest",
    "9 - Farm",
    "2 - Utilities",
    "4 - Port",
    "4 - Port Improvement",
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
DEFAULT_BASE_TAX_INCREASE = 11.58162


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_id(cls):
    return cls.replace(" ", "_").replace("/", "_").replace("-", "_")


def _fmt(n):
    """Format integer with thousands commas for default text input value."""
    return f"{int(n):,}"


def _num(val):
    """Coerce a comma-formatted string or number to int."""
    if val is None:
        return 0
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def make_class_row(cls):
    ntv, nmc, pyr = DEFAULT_DATA[cls]
    c = safe_id(cls)
    def _inp(id_, value):
        return ui.tags.div(
            ui.input_text(id_, None, value=_fmt(value), width="100%"),
            class_="comma-format",
        )
    return ui.tags.tr(
        ui.tags.td(cls, style="padding: 4px 8px; white-space: nowrap; font-size: 0.85rem; font-weight: 500;"),
        ui.tags.td(_inp(f"ntv_{c}", ntv)),
        ui.tags.td(_inp(f"nmc_{c}", nmc)),
        ui.tags.td(_inp(f"pyr_{c}", pyr)),
    )


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

CSS = """
body { font-family: sans-serif; }
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
/* CSS tooltip */
.col-tip {
    position: relative;
    cursor: help;
    border-bottom: 1px dotted #666;
}
.col-tip::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    background: #333;
    color: #fff;
    padding: 5px 9px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 400;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s;
    z-index: 9999;
}
.col-tip:hover::after { opacity: 1; }
.step-card > .card-header { font-size: 1.1rem; font-weight: 600; }
"""

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style(CSS),
        ui.tags.script("window.MathJax = { tex: { inlineMath: [['\\\\(','\\\\)']], displayMath: [['\\\\[','\\\\]']] }, startup: { typeset: true } };"),
        ui.tags.script(src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js", id="MathJax-script", **{"async": ""}),
        ui.tags.script("""
$(document).on('shiny:value', function() {
  setTimeout(function() {
    if (window.MathJax && window.MathJax.typesetPromise) {
      MathJax.typesetPromise();
    }
  }, 100);
});
"""),
        ui.tags.script("""
(function() {
  function applyCommas(input) {
    if (input._commaFormatted) return;
    input._commaFormatted = true;

    function fmt() {
      var raw = input.value.replace(/,/g, '');
      var n = parseFloat(raw);
      if (!isNaN(n)) input.value = Math.round(n).toLocaleString('en-CA');
    }

    function strip() {
      input.value = input.value.replace(/,/g, '');
    }

    // Format on blur; strip on focus so user can edit cleanly
    input.addEventListener('focus', strip);
    input.addEventListener('blur', function() {
      fmt();
      // Notify Shiny of the raw numeric value before we reformat
      $(input).trigger('change');
    });

    // Initial format
    fmt();
  }

  function initAll() {
    // Only target text inputs we control (class added below in Python)
    document.querySelectorAll('.comma-format input[type=text]').forEach(applyCommas);
  }

  document.addEventListener('DOMContentLoaded', initAll);
  $(document).on('shiny:value', function() { setTimeout(initAll, 80); });
  var tries = 0;
  var poll = setInterval(function() { initAll(); if (++tries > 20) clearInterval(poll); }, 200);
})();
"""),
    ),
    ui.h2("Revenue Distribution Method Mil Rate Calculator"),
    ui.hr(),
    ui.p("The foundational principles of the Revenue Distribution Method are:"),
    ui.tags.ul(
        ui.tags.li(ui.HTML(r"market changes (assessed values) should not change the relative tax burden between property classes")),
        ui.tags.li(ui.HTML(r"an increase in the number of properties (a non-market change) in a property class should increase the burden on that class ")),
        style="font-size: 0.85rem;",
    ),

    ui.p("To achieve this the Revenue Distribution Method applies the same percentage increase to the base tax revenue of each variable-rate property class. To unpack what that means, let's start with some definitions:"),
    ui.tags.ul(
        ui.tags.li(ui.HTML(r"<b>Net Taxable Value \((N_i)\)</b> — The total assessed value of all properties in a class that is subject to taxation, as determined by BC Assessment. This includes both the base value and any non-market change value.")),
        ui.tags.li(ui.HTML(r"<b>Non-Market Change Value \((G_i)\)</b> — The portion of the change in assessed value attributable to factors other than market fluctuations — for example, new construction, subdivisions, or rezoning. Also referred to as 'growth'.")),
        ui.tags.li(ui.HTML(r"<b>Base Value \((N_i - G_i)\)</b> — The net taxable value excluding non-market change, i.e. the portion of the assessment base that existed in the prior year, adjusted only for market changes.")),
        ui.tags.li(ui.HTML(r"<b>Prior Year Revenue \((P_i)\)</b> — The actual tax revenue collected from a property class in the preceding year, used as the base from which the current year's revenue target is derived.")),
        ui.tags.li(ui.HTML(r"<b>Total Required Revenue \((T_{\text{total}})\)</b> — The total amount of tax revenue the municipality must collect in the current year, as determined by the financial plan adopted by council.")),
        ui.tags.li(ui.HTML(r"<b>Mil Rate \((r_i)\)</b> — The tax rate expressed in dollars per \$1,000 of assessed value. A mil rate of 1.0 means a property assessed at \$500,000 pays \$500 in taxes.")),
        ui.tags.li(ui.HTML(r"<b>Variable-Rate Classes</b> — Property classes whose mil rates are set by the municipality each year through the Revenue Distribution Method, including Residential, Business, Light Industry, etc. ")),
        ui.tags.li(ui.HTML(r"<b>Capped (Fixed-Rate) Classes</b> — Property classes whose mil rates are set by provincial statute and cannot exceed a fixed cap. Their revenues are excluded from the Revenue Distribution calculation.")),
        ui.tags.li(ui.HTML(r"<b>Fractional Increase \((\alpha)\)</b> — The multiplier applied to each variable-rate class's prior year revenue to arrive at the current year base revenue target. An \(\alpha\) of 1.12 means each class contributes 12% more base revenue than the prior year.")),
        style="font-size: 0.85rem;",
    ),

    ui.p("There are five steps to apply the Revenue Distribution Method:"),

    ui.tags.div(
        ui.tags.b("Step 1:"), ui.span(" Collect required input data"),
        ui.tags.ul(
            ui.tags.li(ui.HTML(r"Total Revenue Required (\(T_{\text{total}}\))")),
            ui.tags.li(ui.HTML(r"Net Taxable Value for each property class (\(N_i\))")),
            ui.tags.li(ui.HTML(r"Non-Market Change Value for each property class (\(G_i\)).")),
            ui.tags.li(ui.HTML(r"Prior Year Revenue for each property class (\(P_i\)).")),
            style="margin-left: 2em; font-size: 0.85rem;"
        ),
        style="margin-left: 2em;",
    ),
    ui.tags.div(
        ui.tags.b("Step 2:"), ui.span(" Determine the fractional increase to the base revenue, "),
        ui.HTML(r"\(\alpha\)"), ui.span(", using"),
        ui.HTML(r"<div style='margin:0.5em 0 0.5em 2em;'>\[ \alpha = \frac{T_{\text{total}}}{\displaystyle\sum_i \frac{P_i}{1 - G_i / N_i}} \]</div>"),
        style="margin-left: 2em;",
    ),
    ui.tags.div(
        ui.tags.b("Step 3:"), ui.span(" Determine the mil rates for each property class using"),
        ui.HTML(r"<div style='margin:0.5em 0 0.5em 2em;'>\[ r_i = \alpha \frac{P_i}{N_i - G_i} \times 1000 \]</div>"),
        style="margin-left: 2em;",
    ),
    ui.tags.div(
        ui.tags.b("Step 4:"), ui.span(" If any capped-rate property classes have a rate that exceeds the cap, remove the total revenue of all capped classes, "), ui.HTML(r"\(T_{\text{cap}}\)"), ui.span(", from the total:"),
        ui.HTML(r"<div style='margin:0.5em 0 0.5em 2em;'>\[ T_{\text{uncap}} = T_{\text{total}} - T_{\text{cap}} \]</div>"),
        style="margin-left: 2em;",
    ),
    ui.tags.div(
        ui.tags.b("Step 5:"), ui.span(" Repeat Steps 2 and 3 using "),
        ui.HTML(r"\(T_{\text{uncap}}\)"), ui.span(" in place of "), ui.HTML(r"\(T_{\text{total}}\)"), ui.span("."),
        style="margin-left: 2em;",
    ),

    ui.hr(),
    ui.h3("Example Calculation: District of Squamish, 2026"),

    ui.HTML('The following is an example calculation using the District of Squamish data for 2026. The input data on Net Taxable Value and NMC per property class can be found in the 2026 Tax Rate Report to Council of the <a href="https://squamish.civicweb.net/filepro/documents/260992/?preview=264715" target="_blank">21 April 2026, Regular Council Meeting</a> (item 7.A.ii).'),
    ui.p(),

    ui.card(
        ui.card_header("Step 1 — Input Data"),
        ui.tags.div(
            ui.input_text(
                "total_required_revenue",
                "Total Required Revenue ($)",
                value=_fmt(TOTAL_REQUIRED_REVENUE),
                width="300px",
            ),
            class_="comma-format",
        ),
        ui.p("Input Net Taxable Value, NMC Value, and prior year revenue for each property class."),
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
        class_="step-card",
    ),

    ui.card(
        ui.card_header("Step 2 — Calculate α (fractional increase to base revenue)"),
        ui.output_ui("alpha_display"),
        class_="step-card",
    ),

    ui.card(
        ui.card_header("Step 3 — Calculate Mil Rates for Each Variable-Rate Property Class"),
        ui.output_ui("step3_display"),
        class_="step-card",
    ),

    ui.card(
        ui.card_header("Results"),
        ui.p("The table and charts below demonstrate that the goal of keeping the tax burden on the base is achieved.  Note that fixed rate classes and input data are in grey because they are not impacted by calculation.", style="font-size:0.78rem; color:#666; margin-bottom:6px;"),
        ui.output_ui("results_table"),

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
        class_="step-card",
    ),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def server(input, output, session):

    @reactive.calc
    def calc_alpha():
        total = _num(input.total_required_revenue())
        # Subtract revenue from capped (fixed-rate) classes to get T_uncap
        capped_revenue = 0.0
        for cls in FIXED_RATE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            nmc = _num(getattr(input, f"nmc_{c}")())
            tax_rate = FIXED_RATE_CLASSES[cls]
            capped_revenue += ntv * tax_rate / 1000
        t_uncap = total - capped_revenue
        denominator = 0.0
        for cls in VARIABLE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            nmc = _num(getattr(input, f"nmc_{c}")())
            pyr = _num(getattr(input, f"pyr_{c}")())
            if ntv > 0:
                denominator += pyr / (1 - nmc / ntv)
        return t_uncap / denominator if denominator else 0.0

    @reactive.calc
    def calc_capped_revenue():
        total = 0.0
        for cls in FIXED_RATE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            tax_rate = FIXED_RATE_CLASSES[cls]
            total += ntv * tax_rate / 1000
        return total

    @reactive.calc
    def calc_df():
        alpha = calc_alpha()
        rows = []
        for cls in VARIABLE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            nmc = _num(getattr(input, f"nmc_{c}")())
            pyr = _num(getattr(input, f"pyr_{c}")())

            base_value = ntv - nmc
            base_revenue = alpha * pyr
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
        df = pd.DataFrame(rows)
        total_base = df["Base Revenue"].sum()
        df["Tax Burden"] = df["Base Revenue"] / total_base if total_base else 0.0
        return df

    @render.ui
    def alpha_display():
        total = _num(input.total_required_revenue())
        capped_revenue = calc_capped_revenue()
        t_uncap = total - capped_revenue
        alpha = calc_alpha()

        # --- Capped class revenue table ---
        capped_rows = [
            ui.tags.tr(
                ui.tags.th("Property Class", style="text-align:left; padding:3px 8px;"),
                ui.tags.th("Fixed Rate ($/1000)", style="text-align:right; padding:3px 8px;"),
                ui.tags.th("Net Taxable Value ($)", style="text-align:right; padding:3px 8px;"),
                ui.tags.th("Revenue ($)", style="text-align:right; padding:3px 8px;"),
            )
        ]
        for cls, rate in FIXED_RATE_CLASSES.items():
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            rev = ntv * rate / 1000
            capped_rows.append(ui.tags.tr(
                ui.tags.td(cls, style="padding:3px 8px;"),
                ui.tags.td(f"{rate:.1f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"${ntv:,.0f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"${rev:,.0f}", style="text-align:right; padding:3px 8px;"),
            ))
        capped_rows.append(ui.tags.tr(
            ui.tags.td(ui.tags.b("Total Capped Revenue"), style="padding:3px 8px;"),
            ui.tags.td("", style="padding:3px 8px;"),
            ui.tags.td("", style="padding:3px 8px;"),
            ui.tags.td(ui.tags.b(f"${capped_revenue:,.0f}"), style="text-align:right; padding:3px 8px;"),
        ))

        # --- Variable class denominator table ---
        terms = []
        for cls in VARIABLE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            nmc = _num(getattr(input, f"nmc_{c}")())
            pyr = _num(getattr(input, f"pyr_{c}")())
            denom_i = 1 - nmc / ntv if ntv > 0 else 1
            term_val = pyr / denom_i if denom_i else 0
            terms.append((cls, pyr, nmc, ntv, denom_i, term_val))
        denom_total = sum(t[5] for t in terms)

        denom_rows = [
            ui.tags.tr(
                ui.tags.th("Property Class", style="text-align:left; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(P_i\) (Prior Year Revenue)"), style="text-align:right; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(1 - G_i/N_i\)"), style="text-align:right; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(P_i \;/\; (1 - G_i/N_i)\)"), style="text-align:right; padding:3px 8px;"),
            )
        ]
        for cls, pyr, nmc, ntv, denom_i, term_val in terms:
            denom_rows.append(ui.tags.tr(
                ui.tags.td(cls, style="padding:3px 8px;"),
                ui.tags.td(f"${pyr:,.0f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"{denom_i:.6f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"${term_val:,.0f}", style="text-align:right; padding:3px 8px;"),
            ))
        denom_rows.append(ui.tags.tr(
            ui.tags.td(ui.tags.b("Total"), style="padding:3px 8px;"),
            ui.tags.td("", style="padding:3px 8px;"),
            ui.tags.td("", style="padding:3px 8px;"),
            ui.tags.td(ui.tags.b(f"${denom_total:,.0f}"), style="text-align:right; padding:3px 8px;"),
        ))

        return ui.div(
            ui.tags.p("We already know that the capped classes; Utilities, Port, and Port Improvement would exceed their cap (see step 4), so we will subtract capped class revenues from total required revenue here (see step 5):"),
            ui.tags.table(
                ui.tags.tbody(*capped_rows),
                style="border-collapse:collapse; width:100%; font-size:0.87rem;",
                class_="input-table",
            ),
            ui.HTML(
                f"<p style='margin-top:8px; font-size:0.92rem;'>"
                f"\\[ T_{{\\text{{uncap}}}} = T_{{\\text{{total}}}} - T_{{\\text{{cap}}}} "
                f"= \\${total:,.0f} - \\${capped_revenue:,.0f} = \\${t_uncap:,.0f} \\]"
                f"</p>"
            ),
            ui.tags.p("Calculate α from variable-rate classes:"),
            ui.tags.table(
                ui.tags.tbody(*denom_rows),
                style="border-collapse:collapse; width:100%; font-size:0.87rem;",
                class_="input-table",
            ),
            ui.HTML(
                f"<p style='margin-top:8px; font-size:0.92rem;'>"
                f"\\[ \\alpha = \\frac{{T_{{\\text{{uncap}}}}}}{{\\sum_i P_i / (1 - G_i/N_i)}} "
                f"= \\frac{{\\${t_uncap:,.0f}}}{{\\${denom_total:,.0f}}} = {alpha:.6f} \\]"
                f"</p>"
            ),
        )

    @render.ui
    def step3_display():
        alpha = calc_alpha()
        rows = [
            ui.tags.tr(
                ui.tags.th("Property Class", style="text-align:left; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(\alpha\)"), style="text-align:right; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(P_i\) (Prior Year Revenue)"), style="text-align:right; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(N_i - G_i\) (Base Value)"), style="text-align:right; padding:3px 8px;"),
                ui.tags.th(ui.HTML(r"\(r_i\) (Mil Rate)"), style="text-align:right; padding:3px 8px;"),
            )
        ]
        for cls in VARIABLE_CLASSES:
            c = safe_id(cls)
            ntv = _num(getattr(input, f"ntv_{c}")())
            nmc = _num(getattr(input, f"nmc_{c}")())
            pyr = _num(getattr(input, f"pyr_{c}")())
            base_value = ntv - nmc
            base_revenue = alpha * pyr
            mil_rate = (1000 * base_revenue / base_value) if base_value else 0
            rows.append(ui.tags.tr(
                ui.tags.td(cls, style="padding:3px 8px;"),
                ui.tags.td(f"{alpha:.6f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"${pyr:,.0f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"${base_value:,.0f}", style="text-align:right; padding:3px 8px;"),
                ui.tags.td(f"{mil_rate:.4f}", style="text-align:right; padding:3px 8px;"),
            ))

        return ui.div(
            ui.HTML(
                r"\[ r_i = \alpha \frac{ P_i}{N_i - G_i} \times 1000 \]"
            ),
            ui.tags.table(
                ui.tags.tbody(*rows),
                style="border-collapse:collapse; width:100%; font-size:0.87rem;",
                class_="input-table",
            ),
        )

    @render.text
    def stat_required():
        return f"${_num(input.total_required_revenue()):,.0f}"

    @render.text
    def stat_total_rev():
        return f"${calc_df()['Revenue (incl. NMC)'].sum():,.0f}"

    @render.text
    def stat_diff():
        diff = calc_df()["Revenue (incl. NMC)"].sum() - _num(input.total_required_revenue())
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
            "Tax Burden": df["Tax Burden"].sum(),
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
        df["Tax Burden"] = df["Tax Burden"].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else ""
        )

        columns = ["Property Class", "Net Taxable Value", "NMC Value", "Base Value",
                   "Prior Year Revenue", "Base Revenue", "Tax Rate", "Tax Burden", "Revenue (incl. NMC)"]

        col_tooltips = {
            "Property Class":       "BC Assessment property class",
            "Net Taxable Value":    "Total assessed value subject to taxation, including NMC",
            "NMC Value":            "Non-Market Change Value",
            "Base Value":           "Net Taxable Value minus NMC Value",
            "Prior Year Revenue":   "Actual tax revenue collected from this class in the prior year",
            "Base Revenue":         "Revenue allocated to this class under the Revenue Distribution Model",
            "Tax Rate":             "Mil Rate = 1000 × Base Revenue / Base Value",
            "Tax Burden":           "Share of total base revenue borne by this property class",
            "Revenue (incl. NMC)":  "Tax Rate applied to the full Net Taxable Value, including NMC",
        }

        header_cells = [
            ui.tags.th(
                ui.tags.span(c, **{"data-tooltip": col_tooltips[c], "class": "col-tip"}),
                style="padding:6px 10px; background:#f0f0f0; border:1px solid #ccc; white-space:nowrap;",
            )
            for c in columns
        ]
        header = ui.tags.thead(ui.tags.tr(*header_cells))

        body_rows = []
        GREY_COLS = {"Net Taxable Value", "NMC Value", "Base Value", "Prior Year Revenue"}
        for _, row in df.iterrows():
            is_total = row["Property Class"] == "TOTAL"
            cells = []
            for c in columns:
                if is_total:
                    cell_style = "padding:4px 10px; border:1px solid #ddd; font-weight:700; border-top:2px solid #999;"
                elif c in GREY_COLS:
                    cell_style = "padding:4px 10px; border:1px solid #ddd; color:#999;"
                else:
                    cell_style = "padding:4px 10px; border:1px solid #ddd;"
                cells.append(ui.tags.td(str(row[c]), style=cell_style))
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
        return _make_pie(calc_df(), "Prior Year Revenue")

    @render_widget
    def pie_chart():
        return _make_pie(calc_df(), "Base Revenue")

    @render_widget
    def nmc_pie():
        return _make_pie(calc_df(), "Revenue (incl. NMC)", showlegend=True)


app = App(app_ui, server)
