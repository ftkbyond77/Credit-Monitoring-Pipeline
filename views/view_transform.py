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
    <div style="text-align:center;padding:60px 20px;">
        <div style="font-size:1.1rem;font-weight:700;color:#3a4a60;">No Data Available</div>
        <div style="font-size:0.88rem;color:#666;margin-top:6px;">
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

                dedup_df        = d.get('dedup_removed_df', None)
                dedup_count     = len(dedup_df) if dedup_df is not None and not dedup_df.empty else 0
                header_count    = len(d['header_dropped_df'])
                na_count        = d['na_dropped_count']
                total_removed   = header_count + na_count + dedup_count

                # ── Metrics row ──────────────────────────────────────────
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("Raw Rows",              d['raw_rows'])
                c2.metric("Header Rows Removed",   header_count,
                          delta="removed", delta_color="inverse")
                c3.metric("Null Rows Removed",     na_count,
                          delta="removed", delta_color="inverse")
                c4.metric("Duplicate Rows Removed",dedup_count,
                          delta="removed", delta_color="inverse")
                c5.metric("Total Rows Removed",    total_removed,
                          delta="removed", delta_color="inverse")
                c6.metric("Final Rows",            d['final_rows'],
                          delta="ready", delta_color="normal")

                st.markdown("---")

                # ── Sub-tabs per removal type ─────────────────────────────
                log_tab1, log_tab2, log_tab3, log_tab4 = st.tabs([
                    "Duplicate Header Rows",
                    "Null / Invalid Rows",
                    "Dedup Multi-Type Rows",
                    "Data Type Schema",
                ])

                with log_tab1:
                    st.caption(
                        "Rows removed because CUSTOMER_CODE / CUSTOMER_NAME / TYPE "
                        "matched the original column header text (embedded header rows in Excel)."
                    )
                    if not d['header_dropped_df'].empty:
                        st.dataframe(
                            d['header_dropped_df'],
                            height=200, use_container_width=True,
                        )
                    else:
                        st.success("No duplicate header rows found.")

                with log_tab2:
                    st.caption(
                        "Rows removed because CUSTOMER_CODE was null, empty, "
                        "or a non-parseable string after type casting."
                    )
                    if na_count > 0:
                        st.warning(f"{na_count} row(s) were removed. "
                                   "Raw snapshot not stored (rows were already invalid before column assignment).")
                    else:
                        st.success("No null / invalid rows found.")

                with log_tab3:
                    st.caption(
                        "Rows removed during deduplication: same CUSTOMER_CODE "
                        "appearing more than once within the same month. "
                        "The first occurrence is kept; subsequent rows (typically "
                        "duplicate credit limits across multiple product types) are removed here."
                    )
                    if dedup_df is not None and not dedup_df.empty:
                        show_cols = [
                            c for c in [
                                'DATE', 'CUSTOMER_CODE', 'CUSTOMER_NAME', 'TYPE',
                                'CLEAN_CREDIT_MB', 'CURRENT_DEBT_MILLION_THB',
                                '_DEDUP_REASON',
                            ]
                            if c in dedup_df.columns
                        ]
                        st.dataframe(
                            dedup_df[show_cols] if show_cols else dedup_df,
                            height=220, use_container_width=True,
                        )
                        csv_bytes = dedup_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download removed rows (.csv)",
                            data=csv_bytes,
                            file_name=f"dedup_removed_{sheet}.csv",
                            mime="text/csv",
                            key=f"dedup_dl_{sheet}",
                        )
                    else:
                        st.success("No duplicate rows removed for this sheet.")

                with log_tab4:
                    st.caption("Column data types after transformation.")
                    dtype_df         = df_avail.dtypes.astype(str).reset_index()
                    dtype_df.columns = ['Column', 'Type']
                    st.dataframe(dtype_df, height=200, use_container_width=True)


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