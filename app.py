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
    'data_processed':       False,
    'df_avail':             None,
    'df_overdue':           None,
    'latest_overdue_name':  "",
    'debug_info_dict':      {},
    'selected_sheets':      [],
    'active_page':          'loading',
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _set_page(key: str):
    st.session_state.active_page = key


# =============================================================================
# Logo helper
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
            width: 100%;
            padding: 8px 14px 10px 14px;
            border-bottom: 1px solid #c8cfc0;
            margin-bottom: 0;
            background: transparent;
        ">
            <img src="data:image/png;base64,{b64}"
                 style="width:100%; height:auto; max-height:72px;
                        object-fit:contain; object-position:left center;
                        display:block;
                        mix-blend-mode: multiply;">
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Sidebar section label helper
# =============================================================================
def _nav_section(label: str):
    """Render a ——— LABEL ——— divider in the sidebar."""
    st.markdown(
        f'<p class="sidebar-section-label">{label}</p>',
        unsafe_allow_html=True,
    )


# =============================================================================
# Sidebar Navigation
# =============================================================================
processed = st.session_state.data_processed
active    = st.session_state.active_page

with st.sidebar:

    # Logo (ถ้ามีไฟล์)
    _render_logo()

    # -------------------------------------------------------------------------
    # Data Pipeline — แสดงเสมอ
    # -------------------------------------------------------------------------
    _nav_section("Data Pipeline")

    if st.button(
        "Loading and Processing Data",
        key="nav_loading",
        use_container_width=True,
        type="primary" if active == 'loading' else "secondary",
    ):
        _set_page('loading')
        st.rerun()

    if st.button(
        "Transformed and Preview Data",
        key="nav_transform",
        use_container_width=True,
        type="primary" if active == 'transform' else "secondary",
    ):
        _set_page('transform')
        st.rerun()

    # -------------------------------------------------------------------------
    # Analytics + Jelly + PNONG — ซ่อนจนกว่าจะ process เสร็จ
    # -------------------------------------------------------------------------
    if processed:

        _nav_section("Analytics Dashboard")

        if st.button(
            "Credit Availability",
            key="nav_avail",
            use_container_width=True,
            type="primary" if active == 'avail' else "secondary",
        ):
            _set_page('avail')
            st.rerun()

        if st.button(
            "Credit Overdue",
            key="nav_overdue_dash",
            use_container_width=True,
            type="primary" if active == 'overdue_dash' else "secondary",
        ):
            _set_page('overdue_dash')
            st.rerun()

        if st.button(
            "Credit Monitoring",
            key="nav_monitoring",
            use_container_width=True,
            type="primary" if active == 'monitoring' else "secondary",
        ):
            _set_page('monitoring')
            st.rerun()

        _nav_section("Jelly Section")

        if st.button(
            "Overdue Daily",
            key="nav_overdue_daily",
            use_container_width=True,
            type="primary" if active == 'overdue_daily' else "secondary",
        ):
            _set_page('overdue_daily')
            st.rerun()

        _nav_section("PNONG Section")

        if st.button(
            "Credit Summary",
            key="nav_credit_summary",
            use_container_width=True,
            type="primary" if active == 'credit_summary' else "secondary",
        ):
            _set_page('credit_summary')
            st.rerun()


# =============================================================================
# Page Router
# =============================================================================
if active == 'loading':
    render_loading()
elif active == 'transform':
    render_transform()
elif active == 'avail':
    render_avail()
elif active == 'overdue_dash':
    render_overdue()
elif active == 'monitoring':
    render_monitoring()
elif active == 'overdue_daily':
    render_overdue_daily()
elif active == 'credit_summary':
    render_credit_summary()