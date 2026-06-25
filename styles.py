# styles.py

DASHBOARD_CSS = """
<style>
/* ============================================================
   Hide Streamlit auto-generated page navigation
   ============================================================ */
[data-testid="stSidebarNav"] { display: none !important; }

/* ============================================================
   Sidebar — background + padding reset
   ============================================================ */
[data-testid="stSidebar"] {
    background-color: #f4f5ef !important;
    border-right: 1px solid #c8cfc0 !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
}
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

/* ============================================================
   Native sidebar collapse button — style ให้สวยแทนซ่อน
   ============================================================ */
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 9999 !important;
}
[data-testid="stSidebarCollapseButton"] button {
    width: 32px !important;
    height: 32px !important;
    background: #f4f5ef !important;
    border: 1px solid #c8cfc0 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.10) !important;
    color: #3d4f3a !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 0.12s, box-shadow 0.12s !important;
    cursor: pointer !important;
}
[data-testid="stSidebarCollapseButton"] button:hover {
    background: #e8e9e2 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}
[data-testid="stSidebarCollapseButton"] button svg {
    width: 16px !important;
    height: 16px !important;
    stroke: #3d4f3a !important;
    fill: none !important;
}
/* collapsed state — button moves to left edge */
[data-testid="collapsedControl"] {
    display: flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 9999 !important;
}
[data-testid="collapsedControl"] button {
    width: 32px !important;
    height: 32px !important;
    background: #f4f5ef !important;
    border: 1px solid #c8cfc0 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.10) !important;
    color: #3d4f3a !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 0.12s, box-shadow 0.12s !important;
    cursor: pointer !important;
}
[data-testid="collapsedControl"] button:hover {
    background: #e8e9e2 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}
[data-testid="collapsedControl"] button svg {
    width: 16px !important;
    height: 16px !important;
    stroke: #3d4f3a !important;
    fill: none !important;
}

/* ลด gap ระหว่าง element ใน sidebar */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
    gap: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ============================================================
   Sidebar — Logo area: remove white box, transparent bg
   ============================================================ */
[data-testid="stSidebar"] > div > div > div > [data-testid="stImage"]:first-of-type {
    background: transparent !important;
    border-bottom: 1px solid #c8cfc0 !important;
    padding: 8px 14px 10px 14px !important;
    margin-top: 0 !important;
    display: block !important;
}

/* ============================================================
   Sidebar — ซ่อน empty markdown
   ============================================================ */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p:empty {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ============================================================
   Sidebar — section label  (.sidebar-section-label)
   style: ——— LABEL ——— black, darker lines
   ============================================================ */
.sidebar-section-label {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: #1a202c;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    padding: 20px 14px 7px 14px;
    margin: 0;
    line-height: 1;
}
.sidebar-section-label::before,
.sidebar-section-label::after {
    content: "";
    flex: 1;
    height: 1.5px;
    background: #9aa390;
    display: block;
    min-width: 10px;
}

/* wrapper reset */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.sidebar-section-label) {
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p.sidebar-section-label {
    padding: 20px 14px 7px 14px !important;
    margin: 0 !important;
}

/* ============================================================
   Sidebar — st.button รูปแบบ nav item
   ============================================================ */
[data-testid="stSidebar"] [data-testid="stButton"] {
    margin: 2px 10px !important;
    width: calc(100% - 20px) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 8px 12px !important;
    border-radius: 5px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    text-align: left !important;
    text-transform: none !important;
    letter-spacing: 0.1px !important;
    white-space: normal !important;
    word-break: break-word !important;
    line-height: 1.4 !important;
    border: 1px solid #d0daea !important;
    background: #ffffff !important;
    color: #3d4f6a !important;
    box-shadow: 0 1px 3px rgba(30, 50, 90, 0.07) !important;
    transition: background 0.12s, color 0.12s, border-color 0.12s, box-shadow 0.12s !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
    background: #f0faf9 !important;
    color: #047a6e !important;
    border: 1px solid #9dd4cc !important;
    box-shadow: 0 2px 6px rgba(4, 154, 138, 0.12) !important;
}

/* primary = active page */
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    background: #ffffff !important;
    color: #047a6e !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    text-transform: none !important;
    letter-spacing: 0.1px !important;
    border: 1px solid #9dd4cc !important;
    border-left: 3px solid #049a8a !important;
    box-shadow: 0 2px 8px rgba(4, 154, 138, 0.14) !important;
    border-radius: 0 5px 5px 0 !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover {
    background: #f0faf9 !important;
    box-shadow: 0 3px 10px rgba(4, 154, 138, 0.20) !important;
}

/* ============================================================
   KPI Card
   ============================================================ */
.kpi-card {
    background: #ffffff;
    border: 1px solid #dde5ef;
    border-radius: 6px;
    padding: 10px 13px;
    text-align: left;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    margin-bottom: 2px;
}
.kpi-card.danger  { border-left: 3px solid #e74c3c; background: #fff8f8; }
.kpi-card.warning { border-left: 3px solid #e67e22; background: #fffbf0; }
.kpi-card.safe    { border-left: 3px solid #27ae60; background: #f5fff8; }
.kpi-card.info    { border-left: 3px solid #049a8a; background: #f0faf9; }
.kpi-label {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 3px;
}
.kpi-value         { font-size: 19px; font-weight: 700; color: #1a2540; line-height: 1.1; }
.kpi-value.danger  { color: #e74c3c; }
.kpi-value.warning { color: #e67e22; }
.kpi-value.safe    { color: #27ae60; }
.kpi-sub           { font-size: 9px; color: #9aabbf; margin-top: 2px; }

/* ============================================================
   Section header
   ============================================================ */
.section-header {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #049a8a;
    margin: 0 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #dde5ef;
}

/* ============================================================
   Filter bar
   ============================================================ */
.filter-bar {
    background: #f4f6fa;
    border: 1px solid #dde5ef;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 10px;
}

/* ============================================================
   Dashboard title bar
   ============================================================ */
.dash-title-bar {
    background: #ffffff;
    border: 1px solid #dde5ef;
    border-radius: 6px;
    padding: 12px 18px;
    margin-top: 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    display: block;
    border-left: 3px solid #049a8a;
}
.dash-title    { font-size: 14px; font-weight: 700; color: #1a2540; margin: 0; }
.dash-subtitle { font-size: 9px; color: #94a3b8; margin-top: 2px; font-style: italic; }

/* ============================================================
   Sidebar nav labels (st.markdown)
   ============================================================ */
.nav-section-label {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    color: #94a3b8;
    padding: 14px 0 4px 0;
    display: block;
}
.nav-divider {
    border: none;
    border-top: 1px solid #e8edf3;
    margin: 4px 0;
}

/* ============================================================
   Selectbox / Multiselect label
   ============================================================ */
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label {
    font-size: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    color: #049a8a !important;
}

/* ============================================================
   Table compact
   ============================================================ */
.stDataFrame { border-radius: 6px; overflow: hidden; }

/* ============================================================
   Global spacing
   ============================================================ */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 0.5rem !important;
    overflow: visible !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }
div[data-testid="stVerticalBlock"] { overflow: visible !important; }
</style>
"""