# views/view_transform.py

import streamlit as st
from components import dash_title_bar


def render():
    st.markdown(
        dash_title_bar(
            "Transformed and Preview Data",
            "Inspect cleansed data and transformation results"
        ),
        unsafe_allow_html=True,
    )

    if not st.session_state.get('data_processed', False):
        _no_data_banner()
        return

    df_avail        = st.session_state.df_avail
    df_overdue      = st.session_state.df_overdue
    latest_name     = st.session_state.latest_overdue_name
    debug_info_dict = st.session_state.debug_info_dict
    selected_sheets = st.session_state.selected_sheets

    tab_avail, tab_overdue = st.tabs([
        "Credit Availability (Transform)",
        "Credit Overdue (Transform)",
    ])

    with tab_avail:
        _render_avail_tab(df_avail, debug_info_dict, selected_sheets)

    with tab_overdue:
        _render_overdue_tab(df_overdue, latest_name)


def _no_data_banner():
    st.markdown("""
    <div style="background:#f8f9fc;border:1.5px solid #d0dae6;border-radius:10px;
    padding:28px;text-align:center;margin-top:32px;">
        <div style="font-size:13px;font-weight:600;color:#1a2540;margin-bottom:6px;">
            No Data Available
        </div>
        <div style="font-size:11px;color:#7a90a8;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_avail_tab(df_avail, debug_info_dict, selected_sheets):
    filtered = df_avail.copy()

    if 'SOURCE_SHEET' in filtered.columns:
        sheets = filtered['SOURCE_SHEET'].unique().tolist()
        if len(sheets) > 1:
            sel = st.selectbox("View Sheet:", sheets, key="view_sheet_selector")
            filtered = filtered[filtered['SOURCE_SHEET'] == sel]

    if 'DATE' in filtered.columns:
        date_list = sorted(filtered['DATE'].dropna().unique().tolist(), reverse=True)
        if date_list:
            fmt      = {d: d.strftime('%d/%m/%Y') for d in date_list}
            sel_date = st.selectbox(
                "Snapshot Date:", options=date_list,
                format_func=lambda x: fmt[x], index=0,
            )
            filtered = filtered[filtered['DATE'] == sel_date]

    view_mode  = st.radio(
        "Display:", ["Preview (30 rows)", "Show All"],
        horizontal=True, key="view_avail",
    )
    display_df = filtered.head(30) if "Preview" in view_mode else filtered

    st.dataframe(
        display_df,
        column_config={
            "CURRENT_DEBT_MILLION_THB_PERCENT": st.column_config.NumberColumn(
                "Debt %", format="%.2f"
            ),
            "DATE": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
        },
        use_container_width=True,
        height=360,
    )

    with st.expander("Data Governance & Debug Log", expanded=False):
        active_debug = [s for s in selected_sheets if s in debug_info_dict]
        if not active_debug:
            st.info("No debug data available.")
            return

        dbg_tabs = st.tabs(active_debug)
        for idx, sheet in enumerate(active_debug):
            with dbg_tabs[idx]:
                d = debug_info_dict[sheet]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Raw Rows",            d['raw_rows'])
                c2.metric("Header Rows Dropped", len(d['header_dropped_df']),
                          delta="removed", delta_color="inverse")
                c3.metric("Null Rows Dropped",   d['na_dropped_count'],
                          delta="removed", delta_color="inverse")
                c4.metric("Final Rows",          d['final_rows'],
                          delta="ready",   delta_color="normal")

                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**Duplicate Headers Removed:**")
                    if not d['header_dropped_df'].empty:
                        st.dataframe(d['header_dropped_df'], height=150, use_container_width=True)
                    else:
                        st.info("None found.")
                with dc2:
                    st.markdown("**Data Type Schema:**")
                    dtype_df            = df_avail.dtypes.astype(str).reset_index()
                    dtype_df.columns    = ['Column', 'Type']
                    st.dataframe(dtype_df, height=150, use_container_width=True)


def _render_overdue_tab(df_overdue, latest_name):
    with st.expander("Raw Overdue Data (first 10 rows)", expanded=False):
        st.caption(f"Source: {latest_name}")
        st.dataframe(df_overdue.head(10), use_container_width=True)

    st.divider()
    st.subheader("Dynamic Filter")

    with st.form("overdue_filter_form"):
        filter_cols  = st.columns(4)
        user_filters = {}
        for idx, col_name in enumerate(df_overdue.columns):
            with filter_cols[idx % 4]:
                unique_vals = df_overdue[col_name].dropna().unique()
                try:
                    unique_vals = sorted(unique_vals)
                except TypeError:
                    unique_vals = sorted(unique_vals, key=str)
                sel = st.multiselect(col_name, unique_vals, key=f"form_filter_{col_name}")
                if sel:
                    user_filters[col_name] = sel

        _, btn_col = st.columns([5, 1])
        with btn_col:
            st.form_submit_button("Apply", type="primary", use_container_width=True)

    filtered_od = df_overdue.copy()
    for fc, fv in user_filters.items():
        filtered_od = filtered_od[filtered_od[fc].isin(fv)]

    view_od    = st.radio(
        "Display:", ["Preview (30 rows)", "Show All"],
        horizontal=True, key="view_overdue",
    )
    display_od = filtered_od.head(30) if "Preview" in view_od else filtered_od

    st.dataframe(display_od, use_container_width=True, height=400)
    st.caption(
        f"Filtered: {filtered_od.shape[1]} cols x {filtered_od.shape[0]} rows"
        f" (from {df_overdue.shape[0]} total)"
    )