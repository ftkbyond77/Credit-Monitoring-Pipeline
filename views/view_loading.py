# views/view_loading.py

import streamlit as st
from et_pipeline import analyze_excel_sheets, run_pipeline
from components import dash_title_bar, section_header

_DEFAULTS = {
    'data_processed':       False,
    'df_avail':             None,
    'df_overdue':           None,
    'latest_overdue_name':  "",
    'debug_info_dict':      {},
    'selected_sheets':      [],
    'active_page':          'loading',
}


def _reset_state():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v


def render():
    st.markdown(
        dash_title_bar(
            "Loading and Processing Data",
            "Upload source files and run the ETL pipeline"
        ),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(section_header("Credit Availability Source"), unsafe_allow_html=True)
        avail_file = st.file_uploader(
            "Upload Availability Excel File",
            type=['xlsx', 'xls'],
            key="avail",
            on_change=_reset_state,
        )

        selected_sheets = []
        if avail_file:
            valid_sheets, invalid_sheets = analyze_excel_sheets(avail_file)
            if invalid_sheets:
                st.error(f"Invalid sheets (missing Customer Code): {', '.join(invalid_sheets)}")
            if valid_sheets:
                st.success(f"Valid sheets: {', '.join(valid_sheets)}")
            selected_sheets = st.multiselect(
                "Select sheets to process",
                options=valid_sheets + invalid_sheets,
                default=valid_sheets,
                on_change=_reset_state,
            )

    with col2:
        st.markdown(section_header("Credit Overdue Source"), unsafe_allow_html=True)
        overdue_files = st.file_uploader(
            "Upload Overdue Excel Files (Fiori Export)",
            type=['xlsx', 'xls'],
            accept_multiple_files=True,
            key="overdue",
            on_change=_reset_state,
        )
        if overdue_files:
            st.info(
                f"{len(overdue_files)} file(s) uploaded. "
                "Latest will be used automatically."
            )

    st.divider()

    if avail_file and selected_sheets and overdue_files:
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            if st.button("Run Pipeline", type="primary", use_container_width=True):
                with st.spinner("Processing and transforming data..."):
                    try:
                        df_a, df_o, latest_name, debug_info = run_pipeline(
                            avail_file, selected_sheets, overdue_files
                        )
                        st.session_state.df_avail             = df_a
                        st.session_state.df_overdue           = df_o
                        st.session_state.latest_overdue_name  = latest_name
                        st.session_state.debug_info_dict      = debug_info
                        st.session_state.selected_sheets      = selected_sheets
                        st.session_state.data_processed       = True
                        st.success(
                            "Pipeline completed. "
                            "Navigate to dashboards from the left sidebar."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Pipeline error: {e}")