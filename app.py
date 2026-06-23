# app.py

import streamlit as st
import streamlit.components.v1 as components
from styles import DASHBOARD_CSS, SIDEBAR_TOGGLE_HTML
from views.view_loading   import render as render_loading
from views.view_transform import render as render_transform
from views.view_avail     import render as render_avail
from views.view_overdue import render as render_overdue  
from views.view_monitoring import render as render_monitoring

st.set_page_config(page_title="Credit Automate Dashboard", layout="wide")

# Inject global CSS (runs inside Streamlit main iframe)
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# Inject sidebar toggle button + JS
# height=0 makes the component invisible in the page flow.
# The button itself is position:fixed inside the parent window so it
# always appears at top-left regardless of scroll or page content.
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
        '<div style="font-size:14px;font-weight:700;color:#1a2540;padding:4px 0 1px 0;">'
        'Credit Monitor</div>'
        '<div style="font-size:9px;color:#4a6fa5;margin-bottom:4px;">'
        'SCG — ET Pipeline System</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)

    # --- Data Pipeline ---
    st.markdown(
        '<span class="nav-section-label">Data Pipeline</span>',
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

    st.markdown('<hr class="nav-divider">', unsafe_allow_html=True)

    # --- Analytics Dashboard ---
    st.markdown(
        '<span class="nav-section-label">Analytics Dashboard</span>',
        unsafe_allow_html=True,
    )
    if not processed:
        st.markdown(
            '<div style="font-size:9px;color:#b0bec5;padding:3px 6px;">'
            'Process data first to unlock dashboards.</div>',
            unsafe_allow_html=True,
        )
    else:
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