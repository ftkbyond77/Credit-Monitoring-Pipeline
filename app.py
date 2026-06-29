# app.py
import base64
import os
import streamlit as st
from styles import DASHBOARD_CSS
from views.view_loading        import render as render_loading
from views.view_transform      import render as render_transform
from views.view_avail          import render as render_avail
from views.view_overdue        import render as render_overdue
from views.view_monitoring     import render as render_monitoring
from views.view_overdue_daily  import render as render_overdue_daily
from views.view_credit_summary import render as render_credit_summary

st.set_page_config(page_title="Credit Automate Dashboard", layout="wide")
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# =============================================================================
# Session State defaults
# =============================================================================
_DEFAULTS = {
    "data_processed":      False,
    "df_avail":            None,
    "df_overdue":          None,
    "latest_overdue_name": "",
    "debug_info_dict":     {},
    "selected_sheets":     [],
    "active_page":         "loading",
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def _navigate(key: str):
    st.session_state.active_page = key


# =============================================================================
# Logo
# =============================================================================
def _render_logo():
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "logo.png")
    if not os.path.exists(logo_path):
        return
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    st.markdown(
        f"""
        <div style="
            width:100%; padding:8px 14px 10px 14px;
            border-bottom:1px solid #c8cfc0;
            margin-bottom:0; background:transparent;
        ">
            <img src="data:image/png;base64,{b64}"
                 style="width:100%; height:auto; max-height:72px;
                        object-fit:contain; object-position:left center;
                        display:block; mix-blend-mode:multiply;">
        </div>
        """,
        unsafe_allow_html=True,
    )


def _nav_section(label: str):
    st.markdown(f'<p class="sidebar-section-label">{label}</p>', unsafe_allow_html=True)


# =============================================================================
# Nav label map — ใช้ label text เป็น selector เพราะ Streamlit ไม่ expose key ใน DOM
# =============================================================================
_PAGE_LABELS = {
    "loading":        "Loading and Processing Data",
    "transform":      "Transformed and Preview Data",
    "avail":          "Credit Availability",
    "overdue_dash":   "Credit Overdue",
    "monitoring":     "Credit Monitoring",
    "overdue_daily":  "Overdue Daily",
    "credit_summary": "Credit Summary",
}

def _inject_nav_highlight(active_page: str):
    label = _PAGE_LABELS.get(active_page, "")
    st.markdown(
        f"""
        <style>
        /* reset ทุกปุ่มใน sidebar กลับเป็น secondary */
        [data-testid="stSidebar"] button {{
            background-color: transparent !important;
            color: inherit !important;
            border-color: rgba(49,51,63,0.2) !important;
        }}
        /* active button */
        [data-testid="stSidebar"] button[data-active="true"] {{
            background-color: #129989 !important;
            color: white !important;
            border-color: #129989 !important;
        }}
        </style>
        <script>
        (function() {{
            const TARGET = {label!r};
            function applyHighlight() {{
                const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
                if (!sidebar) return;
                sidebar.querySelectorAll('button').forEach(btn => {{
                    if (btn.innerText.trim() === TARGET) {{
                        btn.setAttribute('data-active', 'true');
                    }} else {{
                        btn.removeAttribute('data-active');
                    }}
                }});
            }}
            applyHighlight();
            const obs = new MutationObserver(applyHighlight);
            obs.observe(
                window.parent.document.querySelector('[data-testid="stSidebar"]') || window.parent.document.body,
                {{childList: true, subtree: true}}
            );
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Sidebar — ทุกปุ่มใช้ type="secondary" เสมอ, highlight ผ่าน JS
# =============================================================================
with st.sidebar:
    _render_logo()

    _nav_section("Data Pipeline")
    if st.button("Loading and Processing Data", key="nav_loading",
                 use_container_width=True, type="secondary"):
        _navigate("loading")

    if st.button("Transformed and Preview Data", key="nav_transform",
                 use_container_width=True, type="secondary"):
        _navigate("transform")

    if st.session_state.data_processed:
        _nav_section("Analytics Dashboard")
        if st.button("Credit Availability", key="nav_avail",
                     use_container_width=True, type="secondary"):
            _navigate("avail")

        if st.button("Credit Overdue", key="nav_overdue_dash",
                     use_container_width=True, type="secondary"):
            _navigate("overdue_dash")

        if st.button("Credit Monitoring", key="nav_monitoring",
                     use_container_width=True, type="secondary"):
            _navigate("monitoring")

        _nav_section("Jelly Section")
        if st.button("Overdue Daily", key="nav_overdue_daily",
                     use_container_width=True, type="secondary"):
            _navigate("overdue_daily")

        _nav_section("PNONG Section")
        if st.button("Credit Summary", key="nav_credit_summary",
                     use_container_width=True, type="secondary"):
            _navigate("credit_summary")

# inject หลัง sidebar render เสร็จ — อ่านจาก active_page ที่ commit แล้ว
_inject_nav_highlight(st.session_state.active_page)


# =============================================================================
# Page Router
# =============================================================================
_ROUTER = {
    "loading":        render_loading,
    "transform":      render_transform,
    "avail":          render_avail,
    "overdue_dash":   render_overdue,
    "monitoring":     render_monitoring,
    "overdue_daily":  render_overdue_daily,
    "credit_summary": render_credit_summary,
}

_ROUTER.get(st.session_state.active_page, render_loading)()