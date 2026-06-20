# components.py
#
# Reusable UI components and Plotly base layout factory.
# All chart-specific margin/title must be passed at call-site,
# NOT inside PLOTLY_BASE, to prevent duplicate-keyword errors.

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Plotly base layout
# IMPORTANT: margin is intentionally excluded here.
# Each chart passes its own margin= directly to update_layout()
# to avoid: "got multiple values for keyword argument 'margin'"
# ---------------------------------------------------------------------------
FONT_COLOR  = '#3a4a60'
GRID_COLOR  = 'rgba(200,210,220,0.5)'
PLOT_BG     = 'rgba(0,0,0,0)'

PLOTLY_BASE = dict(
    plot_bgcolor=PLOT_BG,
    paper_bgcolor=PLOT_BG,
    font=dict(color=FONT_COLOR, family='Inter, sans-serif', size=10),
    legend=dict(
        bgcolor='rgba(255,255,255,0.8)',
        bordercolor='#d0dae6',
        borderwidth=1,
        font=dict(size=9),
    ),
)


def apply_base_layout(fig: go.Figure, extra: dict) -> go.Figure:
    """
    Merge PLOTLY_BASE with chart-specific overrides and call update_layout once.
    'extra' must contain 'margin' if needed. Never put margin in PLOTLY_BASE.
    """
    layout = {**PLOTLY_BASE, **extra}
    fig.update_layout(**layout)
    return fig


def kpi_card(label: str, value: str, sub: str = "", variant: str = "info") -> str:
    """Return an HTML string for a styled KPI card."""
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ''
    return (
        f'<div class="kpi-card {variant}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value {variant}">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def section_header(text: str) -> str:
    return f'<p class="section-header">{text}</p>'


def dash_title_bar(title: str, subtitle: str = "") -> str:
    return (
        f'<div class="dash-title-bar">'
        f'<div class="dash-title">{title}</div>'
        f'<div class="dash-subtitle">{subtitle}</div>'
        f'</div>'
    )