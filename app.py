# app.py
import base64
import os
import streamlit as st
from PIL import Image
from styles import DASHBOARD_CSS
from views.view_loading        import render as render_loading
from views.view_transform      import render as render_transform
from views.view_avail          import render as render_avail
from views.view_overdue        import render as render_overdue
from views.view_monitoring     import render as render_monitoring
from views.view_overdue_daily  import render as render_overdue_daily
from views.view_credit_summary import render as render_credit_summary

_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "logo-rm.png")
_page_icon = Image.open(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else "💳"

st.set_page_config(page_title="Ciredit Management", page_icon=_page_icon, layout="wide")
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
        [data-testid="stSidebar"] button {{
            background-color: transparent !important;
            color: #31333F !important;
            border-color: rgba(49,51,63,0.2) !important;
            transition: background-color 0.15s ease, color 0.15s ease;
        }}
        [data-testid="stSidebar"] button.nav-active {{
            background-color: #4A9EAF !important;   /* teal-blue ไม่เข้มเกิน */
            color: #ffffff !important;
            border-color: #4A9EAF !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 8px rgba(74,158,175,0.35) !important;
        }}
        </style>
        <script>
        (function() {{
            const TARGET = {label!r};

            function applyHighlight() {{
                const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
                if (!sidebar) return;
                sidebar.querySelectorAll('button').forEach(btn => {{
                    const txt = btn.innerText.trim();
                    if (txt === TARGET) {{
                        btn.classList.add('nav-active');
                    }} else {{
                        btn.classList.remove('nav-active');
                    }}
                }});
            }}

            /* รัน immediately + รอ DOM settle */
            applyHighlight();
            setTimeout(applyHighlight, 80);
            setTimeout(applyHighlight, 300);

            /* watch DOM mutation (Streamlit re-renders) */
            const root = window.parent.document.querySelector('[data-testid="stSidebar"]')
                      || window.parent.document.body;
            const obs = new MutationObserver(() => applyHighlight());
            obs.observe(root, {{childList: true, subtree: true}});
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Sidebar — ทุกปุ่มใช้ type="secondary" เสมอ, highlight ผ่าน JS
# =============================================================================
# sidebar buttons — active page ใช้ type="primary", ที่เหลือ "secondary"
with st.sidebar:
    _render_logo()

    _nav_section("Data Pipeline")
    st.button("Loading and Processing Data", key="nav_loading",
              use_container_width=True,
              type="primary" if st.session_state.active_page == "loading" else "secondary",
              on_click=_navigate, args=("loading",))

    st.button("Transformed and Preview Data", key="nav_transform",
              use_container_width=True,
              type="primary" if st.session_state.active_page == "transform" else "secondary",
              on_click=_navigate, args=("transform",))

    if st.session_state.data_processed:
        _nav_section("Analytics Dashboard")
        st.button("Credit Availability", key="nav_avail",
                  use_container_width=True,
                  type="primary" if st.session_state.active_page == "avail" else "secondary",
                  on_click=_navigate, args=("avail",))

        st.button("Credit Overdue", key="nav_overdue_dash",
                  use_container_width=True,
                  type="primary" if st.session_state.active_page == "overdue_dash" else "secondary",
                  on_click=_navigate, args=("overdue_dash",))

        st.button("Credit Monitoring", key="nav_monitoring",
                  use_container_width=True,
                  type="primary" if st.session_state.active_page == "monitoring" else "secondary",
                  on_click=_navigate, args=("monitoring",))

        _nav_section("Jelly Section")
        st.button("Overdue Daily", key="nav_overdue_daily",
                  use_container_width=True,
                  type="primary" if st.session_state.active_page == "overdue_daily" else "secondary",
                  on_click=_navigate, args=("overdue_daily",))

        _nav_section("PNONG Section")
        st.button("Credit Summary", key="nav_credit_summary",
                  use_container_width=True,
                  type="primary" if st.session_state.active_page == "credit_summary" else "secondary",
                  on_click=_navigate, args=("credit_summary",))


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