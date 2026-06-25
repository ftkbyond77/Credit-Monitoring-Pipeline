# app.py

import streamlit as st
import streamlit.components.v1 as components
from styles import DASHBOARD_CSS, SIDEBAR_TOGGLE_HTML
from views.view_loading       import render as render_loading
from views.view_transform     import render as render_transform
from views.view_avail         import render as render_avail
from views.view_overdue       import render as render_overdue
from views.view_monitoring    import render as render_monitoring
from views.view_overdue_daily import render as render_overdue_daily
from views.view_credit_summary import render as render_credit_summary   

st.set_page_config(page_title="Credit Automate Dashboard", layout="wide")

st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
components.html(SIDEBAR_TOGGLE_HTML, height=0, scrolling=False)

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
# Sidebar Navigation
# =============================================================================
processed = st.session_state.data_processed
active    = st.session_state.active_page

with st.sidebar:
    st.markdown(
        'Credit Monitor'
        'SCG - ET Pipeline System',
        unsafe_allow_html=True,
    )
    st.markdown('', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Data Pipeline — แสดงเสมอ ไม่ต้อง process ก่อน
    # -------------------------------------------------------------------------
    st.markdown(
        'Data Pipeline',
        unsafe_allow_html=True,
    )

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
    # Analytics Dashboard + Jelly Section + PNONG Section
    # ซ่อนทั้งหมด (ทั้ง label และ content) จนกว่าจะ process เสร็จ
    # -------------------------------------------------------------------------
    if processed:
        st.markdown('', unsafe_allow_html=True)

        st.markdown(
            'Analytics Dashboard',
            unsafe_allow_html=True,
        )

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

        st.markdown('', unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # Jelly Section
        # ---------------------------------------------------------------------
        st.markdown(
            'Jelly Section',
            unsafe_allow_html=True,
        )

        if st.button(
            "Overdue Daily",
            key="nav_overdue_daily",
            use_container_width=True,
            type="primary" if active == 'overdue_daily' else "secondary",
        ):
            _set_page('overdue_daily')
            st.rerun()

        st.markdown('', unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # PNONG Section  (ใหม่ — ต่อจาก Jelly Section)
        # ---------------------------------------------------------------------
        st.markdown(
            'PNONG Section',
            unsafe_allow_html=True,
        )

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