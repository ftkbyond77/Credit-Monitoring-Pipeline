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
    variant_styles = {
        "danger":  ("rgba(215,38,61,0.07)",  "#A01F2D"),
        "warning": ("rgba(181,98,10,0.07)",  "#B5620A"),
        "safe":    ("rgba(26,122,74,0.07)",  "#1A7A4A"),
        "info":    ("rgba(27,79,138,0.07)",  "#1B4F8A"),
    }
    bg, accent = variant_styles.get(variant, variant_styles["info"])
    sub_html = (
        f'<div style="font-size:0.70rem;color:#888;margin-top:4px;'
        f'line-height:1.3;word-break:break-word;">{sub}</div>'
        if sub else '<div></div>'
    )
    return (
        f'<div style="background:{bg};border-left:3px solid {accent};'
        f'border-radius:8px;padding:14px 16px;'
        f'display:grid;grid-template-rows:auto 1fr auto;'
        f'height:110px;box-sizing:border-box;width:100%;">'
        f'<div style="font-size:0.72rem;font-weight:700;color:{accent};'
        f'letter-spacing:0.06em;text-transform:uppercase;margin-bottom:4px;">'
        f'{label}</div>'
        f'<div style="font-size:1.25rem;font-weight:800;color:#1a2a3a;'
        f'line-height:1.15;word-break:break-word;align-self:center;">{value}</div>'
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


# ---------------------------------------------------------------------------
# Sidebar nav helpers (used by app.py)
# ---------------------------------------------------------------------------
import base64
import os


def load_logo_b64(logo_path: str = "logo/logo.png") -> str:
    """
    อ่าน logo จาก path ที่ระบุ → encode base64 → คืน data URI
    หากไม่พบไฟล์ → คืน empty string (app.py จะ fallback เป็น text brand)
    """
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), logo_path)
    if not os.path.exists(abs_path):
        return ""
    with open(abs_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def sidebar_icon(name: str) -> str:
    """SVG icons สำหรับ sidebar nav items"""
    icons = {
        "upload":   '<svg viewBox="0 0 24 24"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>',
        "table":    '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/></svg>',
        "bar":      '<svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
        "alert":    '<svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        "monitor":  '<svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
        "calendar": '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="9 16 11 18 15 14"/></svg>',
        "clip":     '<svg viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/></svg>',
    }
    return icons.get(name, "")


def sidebar_nav_item(label: str, icon_name: str,
                     page_key: str, btn_key: str, active: str) -> str:
    """HTML สำหรับ nav item 1 รายการ"""
    cls = "scg-nav-item active" if active == page_key else "scg-nav-item"
    return (
        f'<button class="{cls}" onclick="clickNav(\'{btn_key}\')">'
        f'{sidebar_icon(icon_name)}'
        f'<span>{label}</span>'
        f'</button>'
    )


def sidebar_section(text: str) -> str:
    """HTML สำหรับ section divider label"""
    return f'<div class="scg-nav-section">{text}</div>'


def build_sidebar_html(active: str, processed: bool, logo_uri: str) -> str:
    """
    Build HTML ทั้งหมดของ sidebar nav
    รวม logo, pipeline items, analytics items (เมื่อ processed), footer
    """
    # Logo หรือ fallback text brand
    if logo_uri:
        logo_html = f"""
        <div class="scg-nav-logo">
            <img src="{logo_uri}" alt="Logo"
                 style="width:100%; height:auto; max-height:80px;
                        object-fit:contain; object-position:left center;
                        display:block;">
        </div>"""
    else:
        logo_html = """
        <div class="scg-nav-brand">
            <div class="scg-nav-brand-icon">&#8801;</div>
            <div>
                <div class="scg-nav-brand-text">Credit Monitor</div>
                <div class="scg-nav-brand-sub">SCG &mdash; ET Pipeline System</div>
            </div>
        </div>"""

    # Pipeline (แสดงเสมอ)
    pipeline_html = (
        sidebar_section("Data Pipeline")
        + sidebar_nav_item("Loading and Processing Data", "upload",
                           "loading",   "nav_loading",   active)
        + sidebar_nav_item("Transformed and Preview Data", "table",
                           "transform", "nav_transform", active)
    )

    # Analytics + Jelly + PNONG (แสดงเมื่อ processed)
    analytics_html = ""
    if processed:
        analytics_html = (
            sidebar_section("Analytics Dashboard")
            + sidebar_nav_item("Credit Availability", "bar",
                               "avail",          "nav_avail",          active)
            + sidebar_nav_item("Credit Overdue",      "alert",
                               "overdue_dash",   "nav_overdue_dash",   active)
            + sidebar_nav_item("Credit Monitoring",   "monitor",
                               "monitoring",     "nav_monitoring",     active)
            + sidebar_section("Jelly Section")
            + sidebar_nav_item("Overdue Daily",       "calendar",
                               "overdue_daily",  "nav_overdue_daily",  active)
            + sidebar_section("PNONG Section")
            + sidebar_nav_item("Credit Summary",      "clip",
                               "credit_summary", "nav_credit_summary", active)
        )

    return f"""
    <div class="scg-nav">
        {logo_html}
        <div style="padding: 6px 0;">
            {pipeline_html}
            {analytics_html}
        </div>
        <div class="scg-nav-footer">Internal Use Only</div>
    </div>
    """