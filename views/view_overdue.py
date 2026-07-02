# =============================================================================
# views/view_overdue.py
# Dashboard : Credit Overdue
# Entry point : render()  — matches existing project pattern (view_avail.py)
# Data sources:
#   - st.session_state.df_overdue  (uploaded overdue Excel)
#   - st.session_state.df_avail    (credit availability, multi-sheet by year)
# Date format  : YYYYMMDD integer/string  e.g. 20210530, 20260617
# Join key     : overdue.CustomerNo  <->  avail.CUSTOMER_CODE  (numeric)
# Year match   : overdue.DueYear     <->  avail.SOURCE_SHEET
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from components import (
    apply_base_layout,
    kpi_card,
    section_header,
    dash_title_bar,
    FONT_COLOR,
    GRID_COLOR,
)

PALETTE = {
    "crimson":     "#A01F2D",
    "crimson_lt":  "#D7263D",
    "amber":       "#B5620A",
    "amber_lt":    "#E8A838",
    "sapphire":    "#1B4F8A",
    "sapphire_lt": "#3A7BD5",
    "jade":        "#1A7A4A",
    "jade_lt":     "#2A9D8F",
    "violet":      "#5C3D8F",
    "violet_lt":   "#8E6DC0",
    "steel":       "#3D5166",
    "nodata":      "#8A9BB0",
}

DEFAULT_COMPANY = "1190"

MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

LABEL_STYLE = (
    "font-size:0.75rem;font-weight:600;color:#1B4F8A;"
    "letter-spacing:0.01em;margin-bottom:2px;display:block;line-height:1.4;"
)


def _fmt_thb(value: float, view_type: str) -> str:
    """
    Rounded : detect magnitude → floor 1 decimal → หน่วยเต็ม (ไม่ปัดขึ้น)
    Detail  : เลขดิบทุกหลัก .2f + หน่วย Baht (ไม่ scale ไม่มี Billion/Million)
    Auto-scale ทุก magnitude — future-proof
    """
    import math
    abs_val = abs(value)

    if view_type == "Rounded Number":
        if abs_val >= 1_000_000_000_000:            # Trillion+
            floored = math.floor(value / 1_000_000_000_000 * 10) / 10
            return f"{floored:,.1f} Trillion Baht"
        if abs_val >= 1_000_000_000:                # Billion
            floored = math.floor(value / 1_000_000_000 * 10) / 10
            return f"{floored:,.1f} Billion Baht"
        if abs_val >= 1_000_000:                    # Million
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:,.1f} Million Baht"
        if abs_val >= 1_000:                        # Thousand
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:,.1f} Thousand Baht"
        return f"{math.floor(value * 10) / 10:,.1f} Baht"
    else:
        # Detail: เลขดิบทุกหลัก .2f + "Baht" — ไม่ scale ไม่ว่าเลขจะมากแค่ไหน
        return f"{value:,.2f} Baht"


def _fmt_bar(value: float, view_type: str) -> str:
    """
    Bar/chart label — input unit = THB (raw)
    Rounded : detect magnitude → floor 1 decimal → suffix สั้น
    Detail  : เลขดิบ .2f + THB
    Auto-scale ทุก magnitude
    """
    import math
    abs_val = abs(value)

    if view_type == "Rounded Number":
        if abs_val >= 1_000_000_000_000:
            floored = math.floor(value / 1_000_000_000_000 * 10) / 10
            return f"{floored:,.1f}T"
        if abs_val >= 1_000_000_000:
            floored = math.floor(value / 1_000_000_000 * 10) / 10
            return f"{floored:,.1f}B"
        if abs_val >= 1_000_000:
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:,.1f}M"
        if abs_val >= 1_000:
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:,.1f}K"
        return f"{math.floor(value * 10) / 10:,.1f}"
    else:
        return f"{value:,.2f} THB"


def _fmt_count(value: int, view_type: str) -> str:
    return f"{value:,}"

# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================
def render():
    if not st.session_state.get("data_processed", False):
        _no_data_banner()
        return

    raw_overdue = st.session_state.get("df_overdue")
    if raw_overdue is None or (hasattr(raw_overdue, "empty") and raw_overdue.empty):
        st.warning("df_overdue is empty. Please re-process the data pipeline.")
        return

    df_avail_full = st.session_state.get("df_avail")
    df_all        = _prepare_overdue(raw_overdue.copy())

    st.markdown(
        dash_title_bar(
            "Credit Overdue Dashboard",
            "Analytics Dashboard - Credit Overdue Exposure Monitoring",
        ),
        unsafe_allow_html=True,
    )

    df_filtered, selected_company, period_label_str, view_type = _render_filters(df_all)

    if df_filtered is None or df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(
        section_header(f"Overdue Priority & Overdue Distribution — {period_label_str}"),
        unsafe_allow_html=True,
    )
    col_priority, col_risk = st.columns([3, 2], gap="medium")
    with col_priority:
        _render_top_overdue_bar(df_filtered, view_type)
    with col_risk:
        _render_risk_matrix(df_filtered, df_avail_full)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(
        section_header("Aging Distribution — Overdue Amount by DPD Bucket"),
        unsafe_allow_html=True,
    )
    _render_exposure_utilization(df_filtered, df_avail_full, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(
        section_header("Invoice Date Segmentation — Payment Status by Stage"),
        unsafe_allow_html=True,
    )
    _render_invoice_date_segmentation(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(section_header("Upcoming Overdue Trend — Current & Forward View"), unsafe_allow_html=True)
    with st.expander("Portfolio Classification Guide", expanded=False):
        guide_cls = [
            {"Classification": "Escalating",   "Criteria": "slope > 0, active ratio >= 50%",  "Risk": "High"},
            {"Classification": "Improving",    "Criteria": "slope < 0, active ratio >= 30%",  "Risk": "Medium — recovering"},
            {"Classification": "Persistent",   "Criteria": "slope >= 0, active ratio >= 50%", "Risk": "Medium — chronic"},
            {"Classification": "Intermittent", "Criteria": "any slope, active ratio < 50%",   "Risk": "Low"},
        ]
        st.dataframe(
            pd.DataFrame(guide_cls), use_container_width=True, hide_index=True,
            column_config={
                "Classification": st.column_config.TextColumn("Classification", width="medium"),
                "Criteria":       st.column_config.TextColumn("Criteria",       width="large"),
                "Risk":           st.column_config.TextColumn("Risk Level",     width="medium"),
            },
        )
        st.caption(
            "Slope = linear regression of overdue amount per period (polyfit deg=1)  |  "
            "Active Ratio = periods with overdue > 0 / total periods in filter range"
        )

    gran_col, _ = st.columns([1, 4])
    with gran_col:
        granularity_vel = st.selectbox(
            "Period Granularity",
            options=["Monthly", "Weekly", "Daily", "Yearly"],
            index=0, key="od_gran_vel",
        )

    # Section 5 : Aging Analysis & Trend
    col_trend, col_panel = st.columns([3, 2], gap="medium")
    with col_trend:
        cust_meta = _render_overdue_trend(df_filtered, granularity_vel, view_type)
    with col_panel:
        _render_trend_summary_panel(cust_meta or {})
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # Section 6 : Overdue Share by Customer
    st.markdown(section_header("Overdue Share by Customer"), unsafe_allow_html=True)
    _render_treemap(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    with st.expander("View All Overdue Records — Selected Period", expanded=False):
        _render_priority_table(df_filtered)


# =============================================================================
# Data preparation
# =============================================================================
def _prepare_overdue(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]

    for col in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col].astype(str).str.strip().replace({"nan": None, "": None}),
                format="%Y%m%d",
                errors="coerce",
            )

    for col in ("OverdueAmount", "InvoiceAmount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "CompanyCode" in df.columns:
        df["CompanyCode"] = df["CompanyCode"].astype(str).str.strip()

    if "Customer" in df.columns:
        df["Customer"] = (
            pd.to_numeric(df["Customer"], errors="coerce").fillna(0).astype(int)
        )
    else:
        candidate_cols = [
            c for c in df.columns
            if "customer" in c.lower() and "name" not in c.lower()
        ]
        if candidate_cols:
            src_col = candidate_cols[0]
            df["Customer"] = (
                pd.to_numeric(df[src_col], errors="coerce").fillna(0).astype(int)
            )

    today = pd.Timestamp("today").normalize()

    df["IsOverdue"]    = df["OverdueAmount"] > 0
    df["IsCreditNote"] = df["OverdueAmount"] < 0
    df["IsZeroDebt"]   = df["OverdueAmount"] == 0
    df["OverdueAbs"]   = df["OverdueAmount"].where(df["IsOverdue"], 0.0)

    if "OriginalDueDate" in df.columns:
        df["DPD"] = (today - df["OriginalDueDate"]).dt.days.clip(lower=0)
        df["DueYear"]       = df["OriginalDueDate"].dt.year.astype("Int64")
        df["DueMonth"]      = df["OriginalDueDate"].dt.month.astype("Int64")
        df["DueWeek"]       = df["OriginalDueDate"].dt.isocalendar().week.astype("Int64")
        df["DueMonthLabel"] = df["DueMonth"].map(MONTH_MAP)
        df["AgingBucket"]   = pd.cut(
            df["DPD"],
            bins=[-1, 30, 60, 90, float("inf")],
            labels=["1-30", "31-60", "61-90", "90+"],
        )

    return df


# =============================================================================
# Period helpers
# =============================================================================
def _period_label_series(df: pd.DataFrame, granularity: str) -> pd.Series:
    if granularity == "Yearly":
        return df["DueYear"].astype(str)
    elif granularity == "Monthly":
        return df["DueYear"].astype(str) + "-" + df["DueMonthLabel"].fillna("")
    elif granularity == "Weekly":
        return (
            df["DueYear"].astype(str)
            + "-W"
            + df["DueWeek"].astype(str).str.zfill(2)
        )
    else:  # Daily
        return df["OriginalDueDate"].dt.strftime("%Y-%m-%d")


def _sort_key_series(df: pd.DataFrame, granularity: str) -> pd.Series:
    if granularity == "Yearly":
        return df["DueYear"]
    elif granularity == "Monthly":
        return df["DueYear"] * 100 + df["DueMonth"]
    elif granularity == "Weekly":
        return df["DueYear"] * 100 + df["DueWeek"]
    else:
        return df["OriginalDueDate"]
    

# Stage classification per invoice record
# ใช้ today เป็น reference — ตรวจแต่ละ date ว่าเลยหรือยัง
def _classify_invoice_stage(row, today: pd.Timestamp) -> str:
    orig = row.get("OriginalDueDate")
    cust = row.get("CustomerDueDate")
    coll = row.get("CollectionDate")

    over_orig = pd.notna(orig) and today > orig
    over_cust = pd.notna(cust) and today > cust
    over_coll = pd.notna(coll) and today > coll

    if over_orig and over_cust and over_coll:
        return "4. Critical"
    elif over_orig and over_cust and not over_coll:
        return "3. Late Warning"
    elif over_orig and not over_cust and not over_coll:
        return "2. Grace Period"
    else:
        return "1. Normal"


import logging
import pathlib

_FILTER_LOG = pathlib.Path("filter_group.log")

def _setup_filter_logger() -> logging.Logger:
    logger = logging.getLogger("filter_group")
    if not logger.handlers:
        handler = logging.FileHandler(_FILTER_LOG, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger

def _get_parsed_dt(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    cleaned = series.astype(str).str.strip().replace({"nan": None, "NaT": None, "": None, "None": None})
    dt = pd.to_datetime(cleaned, format="%Y%m%d", errors="coerce")
    nat_mask = dt.isna() & series.notna()
    if nat_mask.any():
        dt[nat_mask] = pd.to_datetime(cleaned[nat_mask], errors="coerce")
    return dt


def _render_period_value_selector(
    df: pd.DataFrame,
    date_col: str,
    period: str,
    key: str,
) -> str:
    PLACEHOLDER = (
        '<div style="border:1px solid #d0dae6;border-radius:6px;'
        'padding:6px 10px;background:rgba(208,218,230,0.15);'
        'font-size:0.72rem;color:#aab4c0;line-height:1.4;margin-top:1px;">'
        '— select period first —</div>'
    )

    if period == "All" or date_col not in df.columns:
        st.markdown(PLACEHOLDER, unsafe_allow_html=True)
        return ""

    dt       = _get_parsed_dt(df[date_col])
    dt_valid = dt.dropna()

    if dt_valid.empty:
        st.markdown(PLACEHOLDER.replace("select period first", "No data"), unsafe_allow_html=True)
        return ""

    label_map = {
        "Yearly":    "Year",
        "Quarterly": "Quarter",
        "Monthly":   "Month",
        "Weekly":    "Week",
        "Daily":     "Date",
    }

    if period == "Yearly":
        pairs = sorted(dt_valid.dt.year.unique().tolist(), reverse=True)
        opts  = [str(y) for y in pairs]

    elif period == "Quarterly":
        pairs = sorted(
            {(int(y), int(q)) for y, q in zip(dt_valid.dt.year, dt_valid.dt.quarter)},
            reverse=True,
        )
        opts = [f"{y}-Q{q}" for y, q in pairs]

    elif period == "Monthly":
        pairs = sorted(
            {(int(y), int(m)) for y, m in zip(dt_valid.dt.year, dt_valid.dt.month)},
            reverse=True,
        )
        opts = [f"{y}-{MONTH_MAP[m]}" for y, m in pairs]

    elif period == "Weekly":
        iso   = dt_valid.dt.isocalendar()
        pairs = sorted(
            {(int(y), int(w)) for y, w in zip(iso.year, iso.week)},
            reverse=True,
        )
        opts = [f"{y}-W{w:02d}" for y, w in pairs]

    else:  # Daily
        days = sorted(dt_valid.dt.date.unique().tolist(), reverse=True)
        opts = [d.strftime("%Y-%m-%d") for d in days]

    opts_with_all = ["All"] + opts
    prev          = st.session_state.get(f"_pval_{key}", "All")
    default_ix    = opts_with_all.index(prev) if prev in opts_with_all else 0

    selected = st.selectbox(
        label_map.get(period, "Select"),
        options=opts_with_all,
        index=default_ix,
        key=key,
        label_visibility="collapsed",
    )
    st.session_state[f"_pval_{key}"] = selected

    if selected != "All":
        st.markdown(
            f'<span style="background:#1B4F8A;color:white;padding:1px 7px;'
            f'border-radius:8px;font-size:0.68rem;font-weight:600;'
            f'display:inline-block;margin-top:2px;">{selected}</span>',
            unsafe_allow_html=True,
        )

    return selected if selected != "All" else ""

def _apply_period_filter(
    df: pd.DataFrame,
    date_col: str,
    period: str,
    value: str,
) -> pd.DataFrame:
    if period == "All" or not value or date_col not in df.columns:
        return df

    dt = _get_parsed_dt(df[date_col])

    if period == "Yearly":
        return df[dt.dt.year.astype("Int64").astype(str) == str(value)]

    elif period == "Quarterly":
        try:
            year_str, q_str = value.split("-Q")
            mask = (
                (dt.dt.year.astype("Int64").astype(str) == year_str) &
                (dt.dt.quarter.astype("Int64").astype(str) == q_str)
            )
            return df[mask]
        except ValueError:
            return df

    elif period == "Monthly":
        try:
            year_str, mon_label = value.split("-", 1)
            MONTH_INV = {v: k for k, v in MONTH_MAP.items()}
            month_num = MONTH_INV.get(mon_label)
            if month_num is None:
                return df
            mask = (
                (dt.dt.year.astype("Int64").astype(str) == year_str) &
                (dt.dt.month == month_num)
            )
            return df[mask]
        except ValueError:
            return df

    elif period == "Weekly":
        try:
            year_str, wk_str = value.split("-W")
            iso  = dt.dt.isocalendar()
            mask = (
                (iso.year.astype(str) == year_str) &
                (iso.week.astype(str).str.zfill(2) == wk_str.zfill(2))
            )
            return df[mask]
        except ValueError:
            return df

    elif period == "Daily":
        return df[dt.dt.strftime("%Y-%m-%d") == value]

    return df


# =============================================================================
# FILTER BAR
# =============================================================================
def _render_filters(df_all: pd.DataFrame):
    available_companies = (
        sorted(df_all["CompanyCode"].dropna().unique().tolist())
        if "CompanyCode" in df_all.columns else [DEFAULT_COMPANY]
    )
    default_idx = (
        available_companies.index(DEFAULT_COMPANY)
        if DEFAULT_COMPANY in available_companies else 0
    )

    # -------------------------------------------------------------------------
    # Row 1 : Company Code | Due From | Due To | Coll From | Coll To | Search
    # -------------------------------------------------------------------------
    R1_COLS   = [1.0, 1.0, 1.0, 1.0, 1.0, 1.8]
    r1_labels = [
        "Company Code", "Due Date From", "Due Date To",
        "Collection From", "Collection To", "Search Customer",
    ]

    lc = st.columns(R1_COLS, gap="small")
    for col, lbl in zip(lc, r1_labels):
        with col:
            st.markdown(f'<span style="{LABEL_STYLE}">{lbl}</span>', unsafe_allow_html=True)

    wc = st.columns(R1_COLS, gap="small")

    with wc[0]:
        selected_company = st.selectbox(
            "Company Code", options=available_companies,
            index=default_idx, key="od_company",
            label_visibility="collapsed",
        )
    with wc[1]:
        due_start = st.date_input(
            "Due From", value=None, key="od_due_start",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc[2]:
        due_end = st.date_input(
            "Due To", value=None, key="od_due_end",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc[3]:
        coll_start = st.date_input(
            "Coll From", value=None, key="od_coll_start",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc[4]:
        coll_end = st.date_input(
            "Coll To", value=None, key="od_coll_end",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )

    df_scope = df_all[df_all["CompanyCode"] == selected_company]

    all_customer_names: list = []
    if "CustomerName" in df_scope.columns:
        all_customer_names = sorted(
            df_scope["CustomerName"].dropna().unique().tolist(),
            key=lambda x: str(x).lower(),
        )

    with wc[5]:
        search_query = st.text_input(
            "Search Customer",
            placeholder="Name or Customer Code...",
            key="od_customer_search",
            label_visibility="collapsed",
        ).strip()

    # -------------------------------------------------------------------------
    # Build recommend list ก่อน render Row 2
    # เพราะ Row 2 col สุดท้ายต้องการ found_n เพื่อแสดงใน label
    # -------------------------------------------------------------------------
    if search_query:
        q_lower       = search_query.lower()
        name_hits     = [n for n in all_customer_names if q_lower in str(n).lower()]
        code_hits_names: list = []
        if "Customer" in df_scope.columns and "CustomerName" in df_scope.columns:
            code_match = (
                df_scope[
                    df_scope["Customer"].astype(str)
                    .str.lower().str.contains(q_lower, na=False)
                ]["CustomerName"].dropna().unique().tolist()
            )
            code_hits_names = [n for n in code_match if n not in name_hits]
        recommend_list = list(dict.fromkeys(name_hits + code_hits_names))
    else:
        recommend_list = all_customer_names

    OPTION_ALL       = "All customers"
    options_with_all = [OPTION_ALL] + recommend_list
    prev_sel         = st.session_state.get("od_customer_select", OPTION_ALL)
    default_sel_ix   = (
        options_with_all.index(prev_sel)
        if prev_sel in options_with_all else 0
    )

    # -------------------------------------------------------------------------
    # Row 2 labels — ทุก column render label ใน lc2 เท่านั้น
    # ไม่มี label ซ้ำใน wc2 เพื่อให้ทุก column เริ่ม widget ที่ระดับเดียวกัน
    # -------------------------------------------------------------------------
    R2_COLS   = [0.85, 0.85, 1.1, 0.85, 1.1, 1.8]
    r2_labels = [
        "View Type",
        "Due Date Group",
        "",
        "Collection Group",
        "",
        f"Select Customer ({len(recommend_list)} found)",
    ]

    lc2 = st.columns(R2_COLS, gap="small")
    for col, lbl in zip(lc2, r2_labels):
        with col:
            if lbl:
                st.markdown(
                    f'<span style="{LABEL_STYLE}">{lbl}</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<span style="display:block;min-height:1.2rem;"></span>',
                    unsafe_allow_html=True,
                )

    # -------------------------------------------------------------------------
    # Row 2 widgets — ทุก column มีแค่ widget ไม่มี label ซ้ำ
    # -------------------------------------------------------------------------
    wc2 = st.columns(R2_COLS, gap="small")

    with wc2[0]:
        view_type = st.selectbox(
            "View Type",
            ["Rounded Number", "Detail Number"],
            index=0, key="od_view_type",
            label_visibility="collapsed",
        )
        vt_color = "#1A7A4A" if view_type == "Rounded Number" else "#1B4F8A"
        vt_short = "Rounded" if view_type == "Rounded Number" else "Detail"
        st.markdown(
            f'<span style="background:{vt_color};color:white;padding:1px 7px;'
            f'border-radius:8px;font-size:0.68rem;font-weight:600;'
            f'display:inline-block;margin-top:2px;">{vt_short}</span>',
            unsafe_allow_html=True,
        )

    PERIOD_OPTIONS = ["All", "Yearly", "Quarterly", "Monthly", "Weekly", "Daily"]

    with wc2[1]:
        od_period = st.selectbox(
            "OD Period", PERIOD_OPTIONS, index=0,
            key="od_grp_od_period", label_visibility="collapsed",
        )
    with wc2[2]:
        _od_period_value = _render_period_value_selector(
            df_scope, "OriginalDueDate", od_period, "od_grp_od_val"
        )
    with wc2[3]:
        coll_period = st.selectbox(
            "Coll Period", PERIOD_OPTIONS, index=0,
            key="od_grp_coll_period", label_visibility="collapsed",
        )
    with wc2[4]:
        _coll_period_value = _render_period_value_selector(
            df_scope, "CollectionDate", coll_period, "od_grp_coll_val"
        )

    with wc2[5]:
        if recommend_list or not search_query:
            selected_customer_name = st.selectbox(
                "Select Customer",
                options=options_with_all,
                index=default_sel_ix,
                key="od_customer_select",
                label_visibility="collapsed",
            )
        else:
            st.markdown(
                f'<div style="border:1px solid #d0dae6;border-radius:6px;'
                f'padding:6px 10px;background:rgba(208,218,230,0.15);'
                f'font-size:0.72rem;color:#aab4c0;line-height:1.4;">'
                f"No match for '{search_query}'.</div>",
                unsafe_allow_html=True,
            )
            selected_customer_name = OPTION_ALL

    # -------------------------------------------------------------------------
    # Apply filters
    # -------------------------------------------------------------------------
    df_company = df_scope.copy()
    if df_company.empty:
        st.warning("No data for selected company.")
        return None, selected_company, "", view_type

    df_filtered = df_company.copy()

    if due_start and "OriginalDueDate" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["OriginalDueDate"] >= pd.Timestamp(due_start)]
    if due_end and "OriginalDueDate" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["OriginalDueDate"] <= pd.Timestamp(due_end)]
    if coll_start and "CollectionDate" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["CollectionDate"] >= pd.Timestamp(coll_start)]
    if coll_end and "CollectionDate" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["CollectionDate"] <= pd.Timestamp(coll_end)]

    if selected_customer_name != OPTION_ALL and "CustomerName" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["CustomerName"] == selected_customer_name]

    df_filtered = _apply_period_filter(
        df_filtered, "OriginalDueDate", od_period, _od_period_value
    )
    df_filtered = _apply_period_filter(
        df_filtered, "CollectionDate", coll_period, _coll_period_value
    )

    if df_filtered.empty and _od_period_value and _coll_period_value:
        df_od_only   = _apply_period_filter(df_company.copy(), "OriginalDueDate", od_period, _od_period_value)
        df_coll_only = _apply_period_filter(df_company.copy(), "CollectionDate",  coll_period, _coll_period_value)
        st.warning(
            f"No data matches both period filters simultaneously.  "
            f"Due {od_period} '{_od_period_value}' → **{len(df_od_only):,}** rows  |  "
            f"Coll {coll_period} '{_coll_period_value}' → **{len(df_coll_only):,}** rows  "
            f"— intersection is empty."
        )

    # -------------------------------------------------------------------------
    # Period label string
    # -------------------------------------------------------------------------
    parts = []
    if due_start or due_end:
        parts.append("Due: " + " → ".join(filter(None, [
            str(due_start) if due_start else None,
            str(due_end)   if due_end   else None,
        ])))
    if coll_start or coll_end:
        parts.append("Collected: " + " → ".join(filter(None, [
            str(coll_start) if coll_start else None,
            str(coll_end)   if coll_end   else None,
        ])))
    if selected_customer_name != OPTION_ALL:
        parts.append(f"Customer: {selected_customer_name}")
    if od_period != "All" and _od_period_value:
        parts.append(f"Due {od_period}: {_od_period_value}")
    if coll_period != "All" and _coll_period_value:
        parts.append(f"Coll {coll_period}: {_coll_period_value}")

    period_label_str = "  |  ".join(parts) if parts else "All Dates"
    return df_filtered, selected_company, period_label_str, view_type


# ---------------------------------------------------------------------------
# KPI card HTML builder สำหรับ overdue dashboard
# ---------------------------------------------------------------------------
def _overdue_kpi_card(label: str, value: str, sub: str, variant: str) -> str:
    variant_styles = {
        "danger":  ("rgba(215,38,61,0.07)",  "#A01F2D"),
        "warning": ("rgba(181,98,10,0.07)",  "#B5620A"),
        "safe":    ("rgba(26,122,74,0.07)",  "#1A7A4A"),
        "info":    ("rgba(27,79,138,0.07)",  "#1B4F8A"),
    }
    bg, accent = variant_styles.get(variant, variant_styles["info"])
    vlen = len(str(value))
    if vlen <= 8:       v_font = "1.25rem"
    elif vlen <= 14:    v_font = "1.05rem"
    elif vlen <= 22:    v_font = "0.88rem"
    else:               v_font = "0.75rem"

    sub_html = (
        f'<div style="'
        f'font-size:0.68rem;color:#888;'
        f'margin-top:4px;line-height:1.3;'
        f'word-break:break-word;'
        f'overflow:hidden;'
        f'display:-webkit-box;'
        f'-webkit-line-clamp:2;'
        f'-webkit-box-orient:vertical;'
        f'">{sub}</div>'
        if sub else '<div style="min-height:1rem;"></div>'
    )
    return (
        f'<div style="'
        f'background:{bg};border-left:3px solid {accent};'
        f'border-radius:8px;'
        f'padding:12px 14px 10px 14px;'
        f'display:grid;grid-template-rows:auto 1fr auto;'
        f'min-height:110px;height:100%;box-sizing:border-box;width:100%;">'
        f'<div style="'
        f'font-size:0.68rem;font-weight:700;color:{accent};'
        f'letter-spacing:0.05em;text-transform:uppercase;'
        f'margin-bottom:4px;line-height:1.2;">'
        f'{label}</div>'
        f'<div style="'
        f'font-size:{v_font};font-weight:800;color:#1a2a3a;'
        f'line-height:1.15;word-break:break-word;align-self:center;">'
        f'{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _render_kpi_detail_tabs(
    df: pd.DataFrame,
    overdue_df: pd.DataFrame,
    today: pd.Timestamp,
    largest_customer_full: str,
):
    DETAIL_COLS = [
        c for c in [
            "Customer", "CustomerName", "InvoiceNo",
            "OriginalDueDate", "CollectionDate", "CustomerDueDate",
            "OverdueAmount", "InvoiceAmount",
        ]
        if c in df.columns
    ]

    DATE_COLS = ["OriginalDueDate", "CollectionDate", "CustomerDueDate"]

    def _fmt_dates(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        for dc in DATE_COLS:
            if dc in frame.columns:
                frame[dc] = pd.to_datetime(frame[dc], errors="coerce").dt.strftime("%Y-%m-%d")
        return frame

    COL_CFG = {
        "Customer":        st.column_config.NumberColumn("Customer Code", format="%d"),
        "CustomerName":    st.column_config.TextColumn("Customer Name",   width="large"),
        "InvoiceNo":       st.column_config.TextColumn("Invoice No.",     width="medium"),
        "OriginalDueDate": st.column_config.TextColumn("Original Due",    width="medium"),
        "CollectionDate":  st.column_config.TextColumn("Collection Date", width="medium"),
        "CustomerDueDate": st.column_config.TextColumn("Customer Due",    width="medium"),
        "OverdueAmount":   st.column_config.NumberColumn("Overdue Amt (THB)",  format="%.2f", width="medium"),
        "InvoiceAmount":   st.column_config.NumberColumn("Invoice Amt (THB)",  format="%.2f", width="medium"),
    }

    with st.expander("Detail View — KPI Breakdown", expanded=False):
        tab_total, tab_orig, tab_coll, tab_largest = st.tabs([
            "Total Customers",
            "Overdue — Original Due",
            "Overdue — Collection Due",
            "Largest Debtor — Detail",
        ])

        # ------------------------------------------------------------------
        # Tab 1 : Total Customers
        # ------------------------------------------------------------------
        with tab_total:
            st.caption("All distinct customers under current filter — all invoice records included.")

            if "CustomerName" not in df.columns:
                st.info("CustomerName column not available.")
            else:
                tab_cols = [c for c in DETAIL_COLS if c in df.columns]
                sort_c1, sort_c2 = st.columns([2, 2])
                with sort_c1:
                    sort_by_total = st.selectbox(
                        "Sort By",
                        ["Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                         "Invoice Amount (High to Low)", "Invoice Amount (Low to High)",
                         "Customer Name (A–Z)"],
                        index=0, key="kpi_tab_total_sort",
                    )

                total_df = df[tab_cols].copy()
                total_df = _fmt_dates(total_df)

                sort_map = {
                    "Overdue Amount (High to Low)": ("OverdueAmount", False),
                    "Overdue Amount (Low to High)": ("OverdueAmount", True),
                    "Invoice Amount (High to Low)":  ("InvoiceAmount", False),
                    "Invoice Amount (Low to High)":  ("InvoiceAmount", True),
                    "Customer Name (A–Z)":           ("CustomerName",  True),
                }
                sc, sa = sort_map.get(sort_by_total, ("OverdueAmount", False))
                if sc in total_df.columns:
                    total_df = total_df.sort_values(sc, ascending=sa)

                st.caption(f"{len(total_df):,} record(s) | {df['CustomerName'].nunique():,} distinct customer(s)")
                st.dataframe(
                    total_df.reset_index(drop=True),
                    use_container_width=True, hide_index=True,
                    height=400, column_config=COL_CFG,
                )

        # ------------------------------------------------------------------
        # Tab 2 : Overdue — Original Due
        # ------------------------------------------------------------------
        with tab_orig:
            st.caption("Customers with OverdueAmount > 0 AND OriginalDueDate < today.")

            if "OriginalDueDate" not in overdue_df.columns or "CustomerName" not in overdue_df.columns:
                st.info("Required columns not available.")
            else:
                orig_mask = (
                    overdue_df["OriginalDueDate"].notna() &
                    (overdue_df["OriginalDueDate"] < today)
                )
                orig_df = overdue_df[orig_mask].copy()

                sort_c1, sort_c2 = st.columns([2, 2])
                with sort_c1:
                    sort_by_orig = st.selectbox(
                        "Sort By",
                        ["Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                         "Invoice Amount (High to Low)", "Invoice Amount (Low to High)",
                         "Original Due Date (Oldest First)", "Customer Name (A–Z)"],
                        index=0, key="kpi_tab_orig_sort",
                    )

                tab_cols = [c for c in DETAIL_COLS if c in orig_df.columns]
                orig_df  = orig_df[tab_cols].copy()
                orig_df  = _fmt_dates(orig_df)

                sort_map_orig = {
                    "Overdue Amount (High to Low)":      ("OverdueAmount",    False),
                    "Overdue Amount (Low to High)":      ("OverdueAmount",    True),
                    "Invoice Amount (High to Low)":      ("InvoiceAmount",    False),
                    "Invoice Amount (Low to High)":      ("InvoiceAmount",    True),
                    "Original Due Date (Oldest First)":  ("OriginalDueDate",  True),
                    "Customer Name (A–Z)":               ("CustomerName",     True),
                }
                sc, sa = sort_map_orig.get(sort_by_orig, ("OverdueAmount", False))
                if sc in orig_df.columns:
                    orig_df = orig_df.sort_values(sc, ascending=sa)

                n_custs = overdue_df[orig_mask]["CustomerName"].nunique()
                st.caption(f"{len(orig_df):,} invoice(s) | {n_custs:,} distinct customer(s) past original due")
                st.dataframe(
                    orig_df.reset_index(drop=True),
                    use_container_width=True, hide_index=True,
                    height=400, column_config=COL_CFG,
                )

        # ------------------------------------------------------------------
        # Tab 3 : Overdue — Collection Due
        # ------------------------------------------------------------------
        with tab_coll:
            st.caption("Customers with OverdueAmount > 0 AND CollectionDate < today.")

            if "CollectionDate" not in overdue_df.columns or "CustomerName" not in overdue_df.columns:
                st.info("Required columns not available.")
            else:
                coll_mask = (
                    overdue_df["CollectionDate"].notna() &
                    (overdue_df["CollectionDate"] < today)
                )
                coll_df = overdue_df[coll_mask].copy()

                sort_c1, sort_c2 = st.columns([2, 2])
                with sort_c1:
                    sort_by_coll = st.selectbox(
                        "Sort By",
                        ["Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                         "Invoice Amount (High to Low)", "Invoice Amount (Low to High)",
                         "Collection Date (Oldest First)", "Customer Name (A–Z)"],
                        index=0, key="kpi_tab_coll_sort",
                    )

                tab_cols = [c for c in DETAIL_COLS if c in coll_df.columns]
                coll_df  = coll_df[tab_cols].copy()
                coll_df  = _fmt_dates(coll_df)

                sort_map_coll = {
                    "Overdue Amount (High to Low)":      ("OverdueAmount",   False),
                    "Overdue Amount (Low to High)":      ("OverdueAmount",   True),
                    "Invoice Amount (High to Low)":      ("InvoiceAmount",   False),
                    "Invoice Amount (Low to High)":      ("InvoiceAmount",   True),
                    "Collection Date (Oldest First)":    ("CollectionDate",  True),
                    "Customer Name (A–Z)":               ("CustomerName",    True),
                }
                sc, sa = sort_map_coll.get(sort_by_coll, ("OverdueAmount", False))
                if sc in coll_df.columns:
                    coll_df = coll_df.sort_values(sc, ascending=sa)

                n_custs = overdue_df[coll_mask]["CustomerName"].nunique()
                st.caption(f"{len(coll_df):,} invoice(s) | {n_custs:,} distinct customer(s) past collection date")
                st.dataframe(
                    coll_df.reset_index(drop=True),
                    use_container_width=True, hide_index=True,
                    height=400, column_config=COL_CFG,
                )

        # ------------------------------------------------------------------
        # Tab 4 : Largest Debtor — all invoices
        # ------------------------------------------------------------------
        with tab_largest:
            if largest_customer_full == "N/A" or "CustomerName" not in overdue_df.columns:
                st.info("No largest debtor data available.")
            else:
                st.caption(
                    f"All overdue invoice records for: **{largest_customer_full}**"
                )

                largest_df = overdue_df[
                    overdue_df["CustomerName"] == largest_customer_full
                ].copy()

                sort_c1, sort_c2 = st.columns([2, 2])
                with sort_c1:
                    sort_by_lg = st.selectbox(
                        "Sort By",
                        ["Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                         "Invoice Amount (High to Low)", "Invoice Amount (Low to High)",
                         "Original Due Date (Oldest First)"],
                        index=0, key="kpi_tab_largest_sort",
                    )

                tab_cols   = [c for c in DETAIL_COLS if c in largest_df.columns]
                largest_df = largest_df[tab_cols].copy()
                largest_df = _fmt_dates(largest_df)

                sort_map_lg = {
                    "Overdue Amount (High to Low)":     ("OverdueAmount",   False),
                    "Overdue Amount (Low to High)":     ("OverdueAmount",   True),
                    "Invoice Amount (High to Low)":     ("InvoiceAmount",   False),
                    "Invoice Amount (Low to High)":     ("InvoiceAmount",   True),
                    "Original Due Date (Oldest First)": ("OriginalDueDate", True),
                }
                sc, sa = sort_map_lg.get(sort_by_lg, ("OverdueAmount", False))
                if sc in largest_df.columns:
                    largest_df = largest_df.sort_values(sc, ascending=sa)

                total_ov = float(
                    overdue_df[overdue_df["CustomerName"] == largest_customer_full]["OverdueAbs"].sum()
                )
                st.caption(
                    f"{len(largest_df):,} invoice(s) | "
                    f"Total Overdue: {total_ov:,.2f} THB"
                )
                st.dataframe(
                    largest_df.reset_index(drop=True),
                    use_container_width=True, hide_index=True,
                    height=400, column_config=COL_CFG,
                )

# =============================================================================
# KPI Row — 5 cards
# =============================================================================
def _render_kpi_row(df: pd.DataFrame, view_type: str):
    today         = pd.Timestamp("today").normalize()
    overdue_df    = df[df["IsOverdue"]].copy()

    total_customers = (
        int(df["CustomerName"].nunique())
        if "CustomerName" in df.columns else 0
    )

    total_amount = (
        float(overdue_df["OverdueAbs"].sum())
        if "OverdueAbs" in overdue_df.columns else 0.0
    )

    # ── Unique invoice documents (not raw row count) ──────────────────────────
    total_invoices = (
        int(overdue_df["InvoiceDocument"].nunique())
        if "InvoiceDocument" in overdue_df.columns
        else int(len(overdue_df))
    )

    orig_overdue_custs = 0
    if "OriginalDueDate" in overdue_df.columns and "CustomerName" in overdue_df.columns:
        orig_overdue_custs = int(
            overdue_df[
                overdue_df["OriginalDueDate"].notna() &
                (overdue_df["OriginalDueDate"] < today)
            ]["CustomerName"].nunique()
        )

    coll_overdue_custs = 0
    if "CollectionDate" in overdue_df.columns and "CustomerName" in overdue_df.columns:
        coll_overdue_custs = int(
            overdue_df[
                overdue_df["CollectionDate"].notna() &
                (overdue_df["CollectionDate"] < today)
            ]["CustomerName"].nunique()
        )

    largest_customer      = "N/A"
    largest_customer_full = "N/A"
    if "CustomerName" in overdue_df.columns and not overdue_df.empty:
        agg = overdue_df.groupby("CustomerName")["OverdueAbs"].sum()
        if not agg.empty:
            largest_customer_full = str(agg.idxmax())
            largest_customer = (
                largest_customer_full[:20] + "…"
                if len(largest_customer_full) > 20
                else largest_customer_full
            )

    amount_fmt = _fmt_thb(total_amount, view_type)

    cards = [
        (
            "Total Customers",
            f"{total_customers:,}",
            "Unique customers",
            "info",
        ),
        (
            "Overdue — Original Due",
            _fmt_count(orig_overdue_custs, view_type),
            "Past original due date",
            "danger" if orig_overdue_custs > 0 else "safe",
        ),
        (
            "Overdue — Collection Due",
            _fmt_count(coll_overdue_custs, view_type),
            "Past collection date",
            "danger" if coll_overdue_custs > 0 else "safe",
        ),
        (
            "Total Overdue Amount",
            amount_fmt,
            "Sum of outstanding overdue",
            "danger" if total_amount > 0 else "safe",
        ),
        (
            "Overdue Invoices",
            _fmt_count(total_invoices, view_type),
            "Unique invoice documents",          # ← updated
            "warning" if total_invoices > 0 else "safe",
        ),
        (
            "Largest Debtor",
            largest_customer,
            largest_customer_full,
            "danger" if largest_customer_full != "N/A" else "info",
        ),
    ]

    cols = st.columns(6, gap="small")
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(
                _overdue_kpi_card(label, value, sub, variant),
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    _render_kpi_detail_tabs(df, overdue_df, today, largest_customer_full)


# =============================================================================
# Row 1 Left (60%) : Top Overdue Customers — Horizontal Bar
# =============================================================================
def _render_top_overdue_bar(df: pd.DataFrame, view_type: str = "Detail Number"):
    if "CustomerName" not in df.columns:
        st.info("CustomerName column not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records in the selected period.")
        return

    distinct_n = overdue_df["CustomerName"].nunique()
    max_n      = max(distinct_n, 5)

    ctrl1, ctrl2 = st.columns([2, 2])
    with ctrl1:
        top_n = st.select_slider(
            "Top N Customers",
            options=sorted(set(list(range(5, min(max_n + 1, 51))) + [10, 12])),
            value=min(12, max_n),
            key="od_priority_topn",
        )
    with ctrl2:
        sort_dir = st.selectbox(
            "Sort", options=["High to Low", "Low to High"],
            index=0, key="od_priority_sort",
        )

    grouped = (
        overdue_df.groupby("CustomerName")
        .agg(
            TotalOverdue=("OverdueAbs", "sum"),
            InvoiceCount=("OverdueAbs", "count"),
            AvgDPD=("DPD", "mean"),
        )
        .reset_index()
        .sort_values("TotalOverdue", ascending=(sort_dir == "Low to High"))
        .head(int(top_n))
        .sort_values("TotalOverdue", ascending=(sort_dir == "High to Low"))
        .reset_index(drop=True)
    )

    q75 = grouped["TotalOverdue"].quantile(0.75)
    q50 = grouped["TotalOverdue"].quantile(0.50)
    bar_colors = [
        PALETTE["crimson"]     if v >= q75 else
        PALETTE["amber"]       if v >= q50 else
        PALETTE["sapphire_lt"]
        for v in grouped["TotalOverdue"]
    ]

    bar_labels = [_fmt_bar(v, view_type) for v in grouped["TotalOverdue"]]
    text_size  = 10 if view_type == "Rounded Number" else 9

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=grouped["CustomerName"],
        x=grouped["TotalOverdue"],
        orientation="h",
        marker_color=bar_colors,
        text=bar_labels,
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=text_size, color=FONT_COLOR),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Overdue Amount : %{x:,.2f} THB<br>"
            "Invoices       : %{customdata[0]}<br>"
            "Avg DPD        : %{customdata[1]:.1f} days"
            "<extra></extra>"
        ),
        customdata=list(zip(grouped["InvoiceCount"], grouped["AvgDPD"])),
    ))

    x_max = float(grouped["TotalOverdue"].max()) * 1.35

    apply_base_layout(fig, {
        "height": max(320, int(top_n) * 30),
        "margin": dict(l=0, r=160 if view_type == "Rounded Number" else 120, t=10, b=4),
        "xaxis": dict(
            title="Overdue Amount (THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            range=[0, x_max],
        ),
        "yaxis": dict(
            title="Customer",
            showgrid=False, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_priority_bar")


def _join_avail(
    agg: pd.DataFrame,
    df_avail: pd.DataFrame,
    extra_cols: list = None,
) -> pd.DataFrame:
    """
    Join overdue agg กับ credit avail แบบ simple exact match
      - overdue.Customer (int) == avail.CUSTOMER_CODE (int)
      - ถ้า year match ได้ก็ดี ถ้าไม่ match ใช้ latest snapshot
      - ถ้า Customer ไม่มีใน avail เลย → NaN (ปล่อยไว้ ไม่ต้อง force)
    """
    if df_avail is None or df_avail.empty:
        return agg

    # columns ที่ต้องการจาก avail
    want_data = ["CURRENT_DEBT_MILLION_THB"]
    if extra_cols:
        want_data += [c for c in extra_cols if c not in want_data]

    # ------------------------------------------------------------------
    # Prepare avail — cast types ให้ตรง
    # ------------------------------------------------------------------
    avail = df_avail.copy()
    avail["SOURCE_SHEET"]  = avail["SOURCE_SHEET"].astype(str).str.strip()
    avail["CUSTOMER_CODE"] = (
        pd.to_numeric(avail["CUSTOMER_CODE"], errors="coerce")
        .fillna(0).astype(int)
    )

    # latest snapshot per (CUSTOMER_CODE, SOURCE_SHEET)
    if "DATE" in avail.columns:
        avail = (
            avail.sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE", "SOURCE_SHEET"])
        )
    else:
        avail = avail.drop_duplicates(subset=["CUSTOMER_CODE", "SOURCE_SHEET"])

    # เลือกเฉพาะ column ที่ต้องการ
    keep = ["CUSTOMER_CODE", "SOURCE_SHEET"] + [
        c for c in want_data if c in avail.columns
    ]
    avail = avail[keep].copy().reset_index(drop=True)

    # ------------------------------------------------------------------
    # Prepare agg — cast Customer → int
    # ------------------------------------------------------------------
    agg = agg.reset_index(drop=True).copy()
    agg["Customer"] = (
        pd.to_numeric(agg["Customer"], errors="coerce")
        .fillna(0).astype(int)
    )
    agg["_year"] = agg["DueYear"].astype(str).str.strip()

    # ------------------------------------------------------------------
    # Step 1 : Year-matched join
    # ------------------------------------------------------------------
    result = agg.merge(
        avail,
        left_on=["Customer", "_year"],
        right_on=["CUSTOMER_CODE", "SOURCE_SHEET"],
        how="left",
    ).reset_index(drop=True)

    # drop avail key columns
    result = result.drop(
        columns=[c for c in ["CUSTOMER_CODE", "SOURCE_SHEET"]
                 if c in result.columns],
        errors="ignore",
    )

    # ------------------------------------------------------------------
    # Step 2 : Fallback — latest snapshot สำหรับ row ที่ year ไม่ match
    # ใช้ CUSTOMER_CODE ล่าสุดของ customer นั้น
    # ------------------------------------------------------------------
    avail_latest = (
        avail.sort_values("SOURCE_SHEET", ascending=False)
        .drop_duplicates(subset=["CUSTOMER_CODE"])
        .reset_index(drop=True)
    )

    need_fb = result["CURRENT_DEBT_MILLION_THB"].isna()

    if need_fb.any():
        fb = (
            result.loc[need_fb, ["Customer"]]
            .reset_index(drop=True)
            .merge(
                avail_latest,
                left_on="Customer",
                right_on="CUSTOMER_CODE",
                how="left",
            )
            .reset_index(drop=True)
        )

        for col in want_data:
            if col in fb.columns:
                result.loc[need_fb, col] = fb[col].values

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    result = result.drop(
        columns=[c for c in ["_year", "CUSTOMER_CODE", "SOURCE_SHEET"]
                 if c in result.columns],
        errors="ignore",
    ).reset_index(drop=True)

    return result


# =============================================================================
# Row 1 Right (40%) : OverdueAmount Distribution — Pie Chart
# =============================================================================
def _render_risk_matrix(df: pd.DataFrame, df_avail: pd.DataFrame = None):
    if "OverdueAmount" not in df.columns:
        st.info("OverdueAmount column not found.")
        return

    COLOR_NEG  = "#3A7BD5"
    COLOR_ZERO = "#2A6496"
    COLOR_POS  = "#8B1A2A"

    s = df["OverdueAmount"]
    neg_count  = int((s < 0).sum())
    zero_count = int((s == 0).sum())
    pos_count  = int((s > 0).sum())
    neg_sum    = float(s[s < 0].sum())
    pos_sum    = float(s[s > 0].sum())
    total_records = neg_count + zero_count + pos_count

    if total_records == 0:
        st.info("No OverdueAmount data in selected period.")
        return

    # ข้อมูลดิบต่อ slice — ลำดับคงที่
    raw_data = [
        ("Credit Note (Negative)", neg_count,  neg_sum,  COLOR_NEG),
        ("No Debt (Zero)",         zero_count, 0.0,      COLOR_ZERO),
        ("Debit Note (Positive)",  pos_count,  pos_sum,  COLOR_POS),
    ]
    raw_data = [(t, c, sm, col) for t, c, sm, col in raw_data if c > 0]

    if not raw_data:
        st.info("No records to display.")
        return

    labels      = [r[0] for r in raw_data]
    raw_counts  = [r[1] for r in raw_data]
    sum_amounts = [r[2] for r in raw_data]
    colors      = [r[3] for r in raw_data]
    total_raw   = sum(raw_counts)
    pct_real    = [round(c / total_raw * 100, 2) for c in raw_counts]

    # MIN_SHARE_PCT boost สำหรับ slice เล็กให้เห็นสี
    MIN_SHARE_PCT = 4.0
    visual_counts = []
    for i, c in enumerate(raw_counts):
        if pct_real[i] < MIN_SHARE_PCT:
            sum_others = total_raw - c
            needed = (MIN_SHARE_PCT / (100.0 - MIN_SHARE_PCT)) * max(sum_others, 1.0)
            visual_counts.append(max(float(c), needed))
        else:
            visual_counts.append(float(c))

    # ------------------------------------------------------------------
    # hovertext — static f-string ต่อ slice
    # ดึงข้อมูลตรงจาก raw_counts / sum_amounts / pct_real
    # ชุดเดียวกับที่ KPI summary row ใช้ → ไม่มี NaN
    # ------------------------------------------------------------------
    hover_texts = [
        (
            f"<b>{labels[i]}</b><br>"
            f"Records    : {raw_counts[i]:,}<br>"
            f"Sum Amount : {sum_amounts[i]:,.0f} THB<br>"
            f"Share      : {pct_real[i]:.2f}%"
        )
        for i in range(len(labels))
    ]

    fig = go.Figure(go.Pie(
        labels    = labels,
        values    = visual_counts,
        hole      = 0.44,
        marker    = dict(
            colors = colors,
            line   = dict(color="white", width=2),
        ),
        text      = [f"{p:.2f}%" for p in pct_real],
        textinfo  = "text",
        textfont  = dict(size=10),
        # ใช้ hovertext แทน hovertemplate + customdata
        hovertext      = hover_texts,
        hovertemplate  = "%{hovertext}<extra></extra>",
        sort      = False,
        direction = "clockwise",
    ))

    fig.add_annotation(
        text      = f"{total_records:,}<br>records",
        x=0.5, y=0.5,
        font      = dict(size=13, color=FONT_COLOR),
        showarrow = False,
    )

    fig.update_layout(
        height        = 360,
        margin        = dict(l=0, r=0, t=30, b=0),
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
        font          = dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
        title         = dict(
            text = "OverdueAmount Distribution — by Type",
            font = dict(size=11, color=FONT_COLOR),
            x    = 0,
        ),
        legend = dict(
            orientation = "h",
            yanchor     = "top",
            y           = -0.06,
            xanchor     = "center",
            x           = 0.5,
            font        = dict(size=10),
            itemwidth   = 80,
        ),
        showlegend = True,
        hoverlabel = dict(
            bgcolor     = "white",
            bordercolor = "#d0dae6",
            font        = dict(size=11, color="#1B2A3B"),
            align       = "left",
        ),
    )

    st.plotly_chart(fig, use_container_width=True, key="chart_overdue_pie")

    # Summary row — ข้อมูลชุดเดียวกับ hover ทุกตัว
    raw_lookup = {t: (c, sm) for t, c, sm, _ in raw_data}
    pct_lookup = {lbl: p for lbl, p in zip(labels, pct_real)}

    def _rc(key):  return raw_lookup.get(key, (0, 0.0))[0]
    def _rs(key):  return raw_lookup.get(key, (0, 0.0))[1]
    def _rp(key):  return pct_lookup.get(key, 0.0)

    summary_html = f"""
    <div style="display:flex;gap:8px;margin-top:6px;">
      <div style="flex:1;background:rgba(58,123,213,0.07);border-radius:8px;
                  padding:8px 12px;border-left:3px solid #3A7BD5;">
        <div style="font-size:0.68rem;color:#3A7BD5;font-weight:700;">Credit Note (Neg)</div>
        <div style="font-size:1.1rem;font-weight:700;color:#1B2A3B;">{_rc("Credit Note (Negative)"):,}</div>
        <div style="font-size:0.70rem;color:#5a6880;">records ({_rp("Credit Note (Negative)"):.2f}%)</div>
        <div style="font-size:0.70rem;color:#5a6880;">Sum: {_rs("Credit Note (Negative)"):,.0f} THB</div>
      </div>
      <div style="flex:1;background:rgba(42,100,150,0.07);border-radius:8px;
                  padding:8px 12px;border-left:3px solid #2A6496;">
        <div style="font-size:0.68rem;color:#2A6496;font-weight:700;">No Debt (Zero)</div>
        <div style="font-size:1.1rem;font-weight:700;color:#1B2A3B;">{_rc("No Debt (Zero)"):,}</div>
        <div style="font-size:0.70rem;color:#5a6880;">records ({_rp("No Debt (Zero)"):.2f}%)</div>
        <div style="font-size:0.70rem;color:#5a6880;">Amount = 0</div>
      </div>
      <div style="flex:1;background:rgba(139,26,42,0.07);border-radius:8px;
                  padding:8px 12px;border-left:3px solid #8B1A2A;">
        <div style="font-size:0.68rem;color:#8B1A2A;font-weight:700;">Debit Note (Pos)</div>
        <div style="font-size:1.1rem;font-weight:700;color:#1B2A3B;">{_rc("Debit Note (Positive)"):,}</div>
        <div style="font-size:0.70rem;color:#5a6880;">records ({_rp("Debit Note (Positive)"):.2f}%)</div>
        <div style="font-size:0.70rem;color:#5a6880;">Sum: {_rs("Debit Note (Positive)"):,.0f} THB</div>
      </div>
    </div>
    """
    st.markdown(summary_html, unsafe_allow_html=True)

# =============================================================================
# Row 2 : AGING DISTRIBUTION
# =============================================================================
def _render_exposure_utilization(df_overdue_filtered: pd.DataFrame, df_avail: pd.DataFrame,
                                  view_type: str = "Detail Number"):
    if "DPD" not in df_overdue_filtered.columns:
        st.error("DPD column not found. Check _prepare_overdue().")
        return

    overdue_df = df_overdue_filtered[df_overdue_filtered["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records for aging distribution.")
        return

    if (overdue_df["OverdueAbs"] < 0).any():
        overdue_df["OverdueAbs"] = overdue_df["OverdueAbs"].abs()

    DPD_BUCKETS = ["Unknown", "Current", "1-30", "31-60", "61-90", "91-180", "181-365", "365+"]
    BUCKET_COLORS = [
        "#B0BEC5",          # Unknown — neutral grey
        PALETTE["jade_lt"],
        PALETTE["sapphire_lt"],
        PALETTE["sapphire"],
        PALETTE["amber_lt"],
        PALETTE["amber"],
        PALETTE["crimson"],
        "#6B0F1A",
    ]

    def _bucket(row) -> str:
        # OriginalDueDate เป็น NaT → Unknown
        if pd.isna(row.get("OriginalDueDate")):
            return "Unknown"
        dpd = row.get("DPD")
        if pd.isna(dpd) or dpd <= 0: return "Current"
        elif dpd <= 30:   return "1-30"
        elif dpd <= 60:   return "31-60"
        elif dpd <= 90:   return "61-90"
        elif dpd <= 180:  return "91-180"
        elif dpd <= 365:  return "181-365"
        else:             return "365+"

    overdue_df["DPD_Bucket"] = overdue_df.apply(_bucket, axis=1)

    cust_count_col = "CustomerName" if "CustomerName" in overdue_df.columns else "Customer"
    hist = (
        overdue_df.groupby("DPD_Bucket")
        .agg(
            SumOverdue=(   "OverdueAbs",      "sum"),
            RecordCount=(  "OverdueAbs",      "count"),
            CustomerCount=(cust_count_col,    "nunique"),
        )
        .reindex(DPD_BUCKETS, fill_value=0)
        .reset_index()
    )
    hist["SumOverdueMB"] = hist["SumOverdue"] / 1_000_000

    bar_colors = [BUCKET_COLORS[DPD_BUCKETS.index(b)] for b in hist["DPD_Bucket"]]
    text_size  = 10 if view_type == "Rounded Number" else 9

    bar_labels = [
        _fmt_bar(v * 1_000_000, view_type) if v >= 0.00001 else ""
        for v in hist["SumOverdueMB"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hist["DPD_Bucket"],
        y=hist["SumOverdueMB"],
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=bar_labels,
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=text_size, color=FONT_COLOR),
        customdata=list(zip(hist["CustomerCount"].values, hist["RecordCount"].values)),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Overdue Amount : %{y:.3f} MB<br>"
            "Customers      : %{customdata[0]}<br>"
            "Invoices       : %{customdata[1]}"
            "<extra></extra>"
        ),
        name="Overdue Amount (MB)",
    ))

    y_max = float(hist["SumOverdueMB"].max()) * 1.3 if hist["SumOverdueMB"].max() > 0 else 1.0
    apply_base_layout(fig, {
        "height": 380,
        "margin": dict(l=0, r=20, t=20, b=4),
        "xaxis": dict(
            title="DPD Bucket",
            showgrid=False, color=FONT_COLOR, tickfont=dict(size=10),
            categoryorder="array", categoryarray=DPD_BUCKETS,
        ),
        "yaxis": dict(
            title="Overdue Amount (Million THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9), range=[0, y_max],
        ),
        "showlegend": False,
        "bargap": 0.28,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_aging_dist_bucket")

    total_rec  = int(hist["RecordCount"].sum())
    total_cust = overdue_df[cust_count_col].nunique()
    unknown_n  = int(hist.loc[hist["DPD_Bucket"] == "Unknown", "RecordCount"].iloc[0])
    caption    = (
        f"{total_rec:,} overdue invoice(s) from {total_cust:,} customer(s) "
        f"— DPD computed per invoice."
    )
    if unknown_n > 0:
        caption += f"  |  **Unknown**: {unknown_n:,} invoice(s) with no OriginalDueDate."
    st.caption(caption)

    # --- Detail table ---
    st.markdown(
        f'<div style="font-size:0.75rem;font-weight:700;color:{PALETTE["sapphire"]};'
        f'letter-spacing:0.05em;text-transform:uppercase;margin:14px 0 6px 0;">'
        f'Overdue Detail by DPD Bucket</div>',
        unsafe_allow_html=True,
    )

    bucket_opts = ["All"] + [b for b in DPD_BUCKETS if b in overdue_df["DPD_Bucket"].values]
    dt_col1, dt_col2 = st.columns([2, 2])
    with dt_col1:
        selected_bucket = st.selectbox(
            "Filter DPD Bucket", options=bucket_opts,
            index=0, key="od_aging_bucket_filter",
        )
    with dt_col2:
        sort_col_opt = st.selectbox(
            "Sort By",
            options=["Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                     "Invoice Amount (High to Low)", "Invoice Amount (Low to High)"],
            index=0, key="od_aging_sort",
        )

    detail_cols = [c for c in [
        "Customer", "CustomerName", "DPD_Bucket", "DPD",
        "OriginalDueDate", "CollectionDate", "CustomerDueDate",
        "OverdueAbs", "InvoiceAmount",
    ] if c in overdue_df.columns]

    detail_df = overdue_df[detail_cols].copy()
    if selected_bucket != "All":
        detail_df = detail_df[detail_df["DPD_Bucket"] == selected_bucket]

    sort_map = {
        "Overdue Amount (High to Low)": ("OverdueAbs",    False),
        "Overdue Amount (Low to High)": ("OverdueAbs",    True),
        "Invoice Amount (High to Low)": ("InvoiceAmount", False),
        "Invoice Amount (Low to High)": ("InvoiceAmount", True),
    }
    sc, sa = sort_map.get(sort_col_opt, ("OverdueAbs", False))
    if sc in detail_df.columns:
        detail_df = detail_df.sort_values(sc, ascending=sa)

    detail_df = detail_df.reset_index(drop=True)
    for dc in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
        if dc in detail_df.columns:
            detail_df[dc] = pd.to_datetime(detail_df[dc], errors="coerce").dt.strftime("%Y-%m-%d")

    st.dataframe(
        detail_df,
        use_container_width=True, hide_index=True, height=360,
        column_config={
            "Customer":        st.column_config.NumberColumn("Customer Code", format="%d"),
            "CustomerName":    st.column_config.TextColumn("Customer Name",   width="large"),
            "DPD_Bucket":      st.column_config.TextColumn("DPD Bucket",      width="small"),
            "DPD":             st.column_config.NumberColumn("DPD (days)",     format="%d"),
            "OriginalDueDate": st.column_config.TextColumn("Original Due",    width="medium"),
            "CollectionDate":  st.column_config.TextColumn("Collection Date", width="medium"),
            "CustomerDueDate": st.column_config.TextColumn("Customer Due",    width="medium"),
            "OverdueAbs":      st.column_config.NumberColumn("Overdue Amount (THB)", format="%.2f"),
            "InvoiceAmount":   st.column_config.NumberColumn("Invoice Amount (THB)", format="%.2f"),
        },
    )
    st.caption(f"{len(detail_df):,} record(s) shown")


# =============================================================================
# Invoice Date Segmentation — Payment Status by Stage
# =============================================================================
def _render_invoice_date_segmentation(df: pd.DataFrame):
    today         = pd.Timestamp("today").normalize()
    has_cust_due  = "CustomerDueDate" in df.columns
    has_coll      = "CollectionDate"  in df.columns
    has_orig      = "OriginalDueDate" in df.columns
    has_cust_name = "CustomerName"    in df.columns

    if not has_orig:
        st.info("OriginalDueDate column not found.")
        return
    if not has_cust_due:
        st.warning("CustomerDueDate not found — Stage 3 (Late Warning) cannot be distinguished from Stage 2.")
    if not has_coll:
        st.warning("CollectionDate not found — Stage 4 (Critical) cannot be distinguished.")

    work = df[df["IsOverdue"]].copy()
    if work.empty:
        st.info("No overdue records (Debit Note) in selected period.")
        return

    if not has_cust_due:
        work["CustomerDueDate"] = pd.NaT
    if not has_coll:
        work["CollectionDate"] = pd.NaT

    work["Stage"] = work.apply(lambda r: _classify_invoice_stage(r, today), axis=1)

    STAGE_ORDER = ["1. Normal", "2. Grace Period", "3. Late Warning", "4. Critical"]
    STAGE_COLOR = {
        "1. Normal":       "#1A7A4A",
        "2. Grace Period": "#E8A838",
        "3. Late Warning": "#B5620A",
        "4. Critical":     "#A01F2D",
    }
    STAGE_RISK = {
        "1. Normal":       "LOW",
        "2. Grace Period": "MEDIUM",
        "3. Late Warning": "HIGH",
        "4. Critical":     "CRITICAL",
    }

    with st.expander("Stage Guideline — Credit Management Logic Matrix", expanded=False):
        guide_rows = [
            {"Stage": "1. Normal",       "OriginalDueDate": "Not exceeded", "CustomerDueDate": "Not exceeded", "CollectionDate": "Not exceeded", "Risk": "LOW"},
            {"Stage": "2. Grace Period", "OriginalDueDate": "Exceeded",     "CustomerDueDate": "Not exceeded", "CollectionDate": "Not exceeded", "Risk": "MEDIUM"},
            {"Stage": "3. Late Warning", "OriginalDueDate": "Exceeded",     "CustomerDueDate": "Exceeded",     "CollectionDate": "Not exceeded", "Risk": "HIGH"},
            {"Stage": "4. Critical",     "OriginalDueDate": "Exceeded",     "CustomerDueDate": "Exceeded",     "CollectionDate": "Exceeded",     "Risk": "CRITICAL"},
        ]
        st.dataframe(
            pd.DataFrame(guide_rows), use_container_width=True, hide_index=True,
            column_config={
                "Stage":           st.column_config.TextColumn("Stage",            width="medium"),
                "OriginalDueDate": st.column_config.TextColumn("Original Due",     width="small"),
                "CustomerDueDate": st.column_config.TextColumn("Customer Due",     width="small"),
                "CollectionDate":  st.column_config.TextColumn("Collection Date",  width="small"),
                "Risk":            st.column_config.TextColumn("Risk Level",       width="small"),
            },
        )

    mode_col, _ = st.columns([2, 5])
    with mode_col:
        count_mode = st.radio(
            "Count mode",
            options=["Per Invoice", "Per Customer"],
            index=0, horizontal=True, key="seg_count_mode",
        )

    cust_col = "CustomerName" if has_cust_name else "Customer"

    if count_mode == "Per Invoice":
        plot_df      = work[[cust_col, "Stage", "OverdueAbs"]].copy()
        funnel_label = "invoices"
    else:
        stage_rank = {s: i for i, s in enumerate(STAGE_ORDER)}
        cust_agg   = (
            work.groupby(cust_col)
            .agg(
                Stage=("Stage", lambda x: max(x, key=lambda s: stage_rank[s])),
                _val =("OverdueAbs", "sum"),
            )
            .reset_index()
        )
        plot_df      = cust_agg.rename(columns={"_val": "OverdueAbs"})
        funnel_label = "customers"

    stage_sum = (
        plot_df.groupby("Stage")
        .agg(Count=("OverdueAbs", "count"), TotalOverdue=("OverdueAbs", "sum"))
        .reindex(STAGE_ORDER, fill_value=0)
        .reset_index()
    )
    total_count      = int(stage_sum["Count"].sum())
    stage_sum["Pct"] = (stage_sum["Count"] / max(total_count, 1) * 100).round(1)
    stage_sum_active = stage_sum[stage_sum["Count"] > 0].reset_index(drop=True)

    # =========================================================================
    # Layout: Pie บน row แยก (full width col_pie) | table แยกด้านล่าง
    # เหตุผล: columns([35,65]) ทำให้ pie ได้พื้นที่น้อยเกิน
    #         แยก pie ออกมาเป็น row ของตัวเอง แล้ว table อยู่ด้านล่าง
    # =========================================================================
    col_pie, col_strip = st.columns([1, 1], gap="medium")

    with col_pie:
        if stage_sum_active.empty:
            st.info("No stage data to display.")
        else:
            pie_labels = stage_sum_active["Stage"].tolist()
            pie_counts = stage_sum_active["Count"].tolist()
            pie_totals = stage_sum_active["TotalOverdue"].tolist()
            pie_pcts   = stage_sum_active["Pct"].tolist()
            pie_colors = [STAGE_COLOR[s] for s in pie_labels]
            pie_risks  = [STAGE_RISK[s]  for s in pie_labels]

            hover_texts = [
                (
                    f"<b>{pie_labels[i]}</b><br>"
                    f"Risk    : {pie_risks[i]}<br>"
                    f"Count   : {pie_counts[i]:,} {funnel_label}<br>"
                    f"Share   : {pie_pcts[i]:.1f}%<br>"
                    f"Overdue : {pie_totals[i]:,.0f} THB"
                )
                for i in range(len(pie_labels))
            ]

            fig_pie = go.Figure(go.Pie(
                labels        = pie_labels,
                values        = pie_counts,
                hole          = 0.38,
                marker        = dict(colors=pie_colors, line=dict(color="white", width=2)),
                textinfo      = "none",
                hovertext     = hover_texts,
                hovertemplate = "%{hovertext}<extra></extra>",
                sort          = False,
                direction     = "clockwise",
                # pie ใช้พื้นที่เต็ม column — ไม่จอง space ให้ legend
                domain        = dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            ))

            fig_pie.add_annotation(
                text      = f"<b>{total_count:,}</b><br>{funnel_label}",
                x=0.5, y=0.5,
                font      = dict(size=14, color=FONT_COLOR),
                showarrow = False,
            )

            fig_pie.update_layout(
                height        = 380,
                # margin แคบ — ให้ pie วาดเต็ม canvas
                margin        = dict(l=8, r=8, t=36, b=8),
                paper_bgcolor = "rgba(0,0,0,0)",
                plot_bgcolor  = "rgba(0,0,0,0)",
                font          = dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
                title         = dict(
                    text = f"Stage Distribution ({count_mode})",
                    font = dict(size=11, color=FONT_COLOR), x=0,
                ),
                # legend วางใต้ pie ไม่ขวา — ไม่กินพื้นที่ pie
                legend = dict(
                    orientation = "h",
                    yanchor     = "top",
                    y           = -0.04,
                    xanchor     = "center",
                    x           = 0.5,
                    font        = dict(size=11),
                ),
                showlegend = True,
                hoverlabel = dict(
                    bgcolor     = "white",
                    bordercolor = "#d0dae6",
                    font        = dict(size=11, color="#1B2A3B"),
                    align       = "left",
                ),
            )
            st.plotly_chart(fig_pie, use_container_width=True, key="chart_stage_pie")

    with col_strip:
        st.markdown(
            '<div style="font-size:0.75rem;font-weight:700;color:#1B4F8A;'
            'letter-spacing:0.05em;text-transform:uppercase;margin-bottom:10px;">'
            'Stage Summary</div>',
            unsafe_allow_html=True,
        )
        for _, sr in stage_sum_active.iterrows():
            stage = sr["Stage"]
            cnt   = int(sr["Count"])
            pct   = float(sr["Pct"])
            tot   = float(sr["TotalOverdue"])
            risk  = STAGE_RISK[stage]
            color = STAGE_COLOR[stage]
            st.markdown(
                f"<div style='border-left:4px solid {color};"
                f"background:rgba(0,0,0,0.025);border-radius:0 6px 6px 0;"
                f"padding:8px 12px;margin-bottom:8px;'>"
                f"<div style='font-size:0.72rem;font-weight:700;color:{color};'>"
                f"{stage} — {risk}</div>"
                f"<div style='font-size:0.82rem;font-weight:600;color:{FONT_COLOR};'>"
                f"{cnt:,} {funnel_label} ({pct:.1f}%)</div>"
                f"<div style='font-size:0.70rem;color:#6b7a8d;margin-top:2px;'>"
                f"Overdue: {tot:,.0f} THB</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # =========================================================================
    # Detailed Debtor Registry 
    # =========================================================================
    st.markdown(
        f'<div style="font-size:0.75rem;font-weight:700;color:{PALETTE["sapphire"]};'
        f'letter-spacing:0.05em;text-transform:uppercase;margin:16px 0 8px 0;">'
        f'Detailed Debtor By Stage</div>',
        unsafe_allow_html=True,
    )

    fc1, fc2 = st.columns([2, 2])
    with fc1:
        stage_filter = st.multiselect(
            "Filter by Stage", options=STAGE_ORDER,
            default=STAGE_ORDER, key="seg_stage_filter",
        )
    with fc2:
        sort_opt = st.selectbox(
            "Sort By",
            options=[
                "Overdue Amount (High to Low)", "Overdue Amount (Low to High)",
                "Invoice Amount (High to Low)", "Invoice Amount (Low to High)",
            ],
            index=0, key="seg_sort",
        )

    if count_mode == "Per Invoice":
        desired_cols = [
            cust_col, "Stage", "OverdueAbs", "InvoiceAmount",
            "OriginalDueDate", "CustomerDueDate", "CollectionDate", "DPD",
        ]
        avail_cols = [c for c in desired_cols if c in work.columns]
        table_df   = work[avail_cols].copy().rename(columns={
            cust_col:        "Customer Name",
            "OverdueAbs":    "Overdue Amount",
            "InvoiceAmount": "Invoice Amount",
            "Stage":         "Risk Stage",
        })
    else:
        agg_dict = {
            "Stage":        ("Stage",      lambda x: max(x, key=lambda s: {s: i for i, s in enumerate(STAGE_ORDER)}[s])),
            "TotalOverdue": ("OverdueAbs", "sum"),
            "InvoiceCount": ("OverdueAbs", "count"),
        }
        if "InvoiceAmount" in work.columns:
            agg_dict["TotalInvoice"] = ("InvoiceAmount", "sum")
        table_df = (
            work.groupby(cust_col).agg(**agg_dict).reset_index()
            .rename(columns={
                cust_col:       "Customer Name",
                "Stage":        "Risk Stage",
                "TotalOverdue": "Overdue Amount",
                "InvoiceCount": "Invoices",
                "TotalInvoice": "Invoice Amount",
            })
        )

    table_df.insert(
        table_df.columns.tolist().index("Risk Stage") + 1,
        "Risk Level",
        table_df["Risk Stage"].map(STAGE_RISK),
    )

    sort_col_map = {
        "Overdue Amount (High to Low)": ("Overdue Amount", False),
        "Overdue Amount (Low to High)": ("Overdue Amount", True),
        "Invoice Amount (High to Low)": ("Invoice Amount", False),
        "Invoice Amount (Low to High)": ("Invoice Amount", True),
    }
    s_col, s_asc = sort_col_map.get(sort_opt, ("Overdue Amount", False))

    filtered_table = (
        table_df[table_df["Risk Stage"].isin(stage_filter)]
        .copy()
        .sort_values(s_col if s_col in table_df.columns else "Overdue Amount", ascending=s_asc)
        .reset_index(drop=True)
    )

    if filtered_table.empty:
        st.info("No records for selected stage(s).")
    else:
        for dc in ("OriginalDueDate", "CustomerDueDate", "CollectionDate"):
            if dc in filtered_table.columns:
                filtered_table[dc] = pd.to_datetime(
                    filtered_table[dc], errors="coerce"
                ).dt.strftime("%Y-%m-%d")

        col_cfg = {
            "Overdue Amount":  st.column_config.NumberColumn("Overdue Amt (THB)", format="%.2f"),
            "Invoice Amount":  st.column_config.NumberColumn("Invoice Amt (THB)", format="%.2f"),
            "Risk Stage":      st.column_config.TextColumn("Risk Stage"),
            "Risk Level":      st.column_config.TextColumn("Risk Level"),
            "DPD":             st.column_config.NumberColumn("DPD (days)", format="%d"),
        }
        if "Invoices" in filtered_table.columns:
            col_cfg["Invoices"] = st.column_config.NumberColumn("Invoices", format="%d")

        st.dataframe(
            filtered_table, use_container_width=True,
            hide_index=True, height=460, column_config=col_cfg,
        )
        st.caption(
            f"{len(filtered_table):,} record(s) — "
            f"Total Overdue: {float(filtered_table['Overdue Amount'].sum()):,.2f} THB"
        )

# =============================================================================
# Section 5 Left (60%) : Overdue Trend
# =============================================================================
def _render_overdue_trend(df: pd.DataFrame, granularity: str,
                          view_type: str = "Detail Number") -> dict:
    import plotly.express as px
    import numpy as _np

    if "OriginalDueDate" not in df.columns:
        st.info("OriginalDueDate column not found.")
        return {}

    overdue_df = df[df["IsOverdue"] & (df["OverdueAbs"] > 0)].copy()
    if overdue_df.empty:
        st.info("No overdue records with amount > 0.")
        return {}

    if "CustomerName" not in overdue_df.columns:
        st.info("CustomerName column not found.")
        return {}

    overdue_df["_PeriodLabel"] = _period_label_series(overdue_df, granularity)
    overdue_df["_SortKey"]     = _sort_key_series(overdue_df, granularity)

    all_customer_names = sorted(
        overdue_df["CustomerName"].dropna().unique().tolist(),
        key=lambda x: str(x).lower(),
    )

    ctl1, ctl2, ctl3 = st.columns([2, 1, 1])
    with ctl1:
        search_text = st.text_input(
            "Search customer name",
            placeholder="Type to filter list (leave blank for Top N)",
            key="od_trend_search",
            label_visibility="collapsed",
        )
    with ctl2:
        top_n = st.number_input(
            "Top N", min_value=1, max_value=50, value=10, step=1,
            key="od_trend_topn",
            label_visibility="collapsed",
            help="Top N customers by total overdue (used when search is blank)",
        )
    with ctl3:
        trend_mode = st.selectbox(
            "Mode", options=["Per-Period", "Cumulative"],
            index=0, key="od_trend_mode",
            label_visibility="collapsed",
        )

    if search_text.strip():
        terms     = [t.strip().lower() for t in search_text.split(",") if t.strip()]
        recommend = [c for c in all_customer_names if any(t in c.lower() for t in terms)]
    else:
        recommend = all_customer_names

    OPTION_ALL       = "__top_n__"
    LABEL_ALL        = f"Top {int(top_n)} by total overdue"
    options_display  = [LABEL_ALL] + recommend
    options_internal = [OPTION_ALL] + recommend

    prev_sel   = st.session_state.get("od_trend_customer_select", OPTION_ALL)
    default_ix = options_internal.index(prev_sel) if prev_sel in options_internal else 0

    if recommend:
        selected_display = st.selectbox(
            f"Select customer ({len(recommend)} found)",
            options=options_display, index=default_ix,
            key="od_trend_customer_select_label",
        )
        selected_internal = options_internal[options_display.index(selected_display)]
        st.session_state["od_trend_customer_select"] = selected_internal
    else:
        if search_text.strip():
            st.warning(f"No customers match: {search_text}")
        selected_internal = OPTION_ALL

    grp = (
        overdue_df
        .groupby(["CustomerName", "_PeriodLabel", "_SortKey"])
        .agg(OverdueAbs=("OverdueAbs", "sum"))
        .reset_index()
        .sort_values("_SortKey")
    )

    cust_totals   = grp.groupby("CustomerName")["OverdueAbs"].sum().sort_values(ascending=False)
    all_customers = cust_totals.index.tolist()
    sel_customers = (
        all_customers[:int(top_n)]
        if selected_internal == OPTION_ALL
        else [selected_internal]
    )

    if not sel_customers:
        st.info("No customers to display.")
        return {}

    grp_sel     = grp[grp["CustomerName"].isin(sel_customers)]
    all_periods = (
        grp_sel[["_PeriodLabel", "_SortKey"]]
        .drop_duplicates()
        .sort_values("_SortKey")["_PeriodLabel"]
        .tolist()
    )

    if not all_periods:
        st.info("No period data found.")
        return {}

    pivot_raw = (
        grp_sel.pivot_table(
            index="CustomerName", columns="_PeriodLabel",
            values="OverdueAbs", aggfunc="sum",
        )
        .reindex(columns=all_periods, fill_value=0)
        .fillna(0)
    )

    if trend_mode == "Cumulative":
        pivot_plot = pivot_raw.cumsum(axis=1)
        y_title    = "Outstanding Overdue Amount (THB)"
    else:
        pivot_plot = pivot_raw.copy()
        y_title    = "Overdue Amount (THB)"

    COLOR_PALETTE = (
        px.colors.qualitative.Plotly
        + px.colors.qualitative.D3
        + px.colors.qualitative.Set1
    )

    cust_meta = {}
    for i, cust in enumerate(sel_customers):
        if cust not in pivot_raw.index:
            continue

        color      = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        y_raw_full = pivot_raw.loc[cust].tolist()

        # ── Trim both leading AND trailing zeros ─────────────────────────────
        # เหลือเฉพาะ "active window" จริงของ customer
        # กัน leading 0 (period ก่อน customer เริ่ม overdue) บิด slope
        first_nonzero_idx = next(
            (i for i, v in enumerate(y_raw_full) if v > 0), None
        )

        if first_nonzero_idx is None:
            # ไม่มี overdue เลยในทุก period
            y_raw = y_raw_full
        else:
            last_nonzero_idx = max(
                i for i, v in enumerate(y_raw_full) if v > 0
            )
            y_raw = y_raw_full[first_nonzero_idx : last_nonzero_idx + 1]
        # ─────────────────────────────────────────────────────────────────────

        x_idx  = list(range(len(y_raw)))
        slope  = (
            float(_np.polyfit(x_idx, y_raw, 1)[0])
            if len(y_raw) >= 2 and sum(y_raw) > 0
            else 0.0
        )
        active_periods = int(sum(1 for v in y_raw if v > 0))
        total_periods  = len(y_raw)
        total_ov       = sum(y_raw)
        last_ov        = y_raw[-1]
        first_ov       = next((v for v in y_raw if v > 0), 0.0)
        delta_ov       = last_ov - first_ov
        max_ov         = max(y_raw) if y_raw else 0.0
        ratio          = active_periods / max(total_periods, 1)

        if   slope > 0 and ratio >= 0.5:   classification = "Escalating"
        elif slope < 0 and ratio >= 0.3:   classification = "Improving"
        elif ratio >= 0.5:                 classification = "Persistent"
        else:                              classification = "Intermittent"

        cust_meta[cust] = {
            "color":          color,
            "total_ov":       total_ov,
            "last_ov":        last_ov,
            "delta_ov":       delta_ov,
            "max_ov":         max_ov,
            "slope":          slope,
            "active_periods": active_periods,
            "total_periods":  total_periods,
            "classification": classification,
        }

    fig = go.Figure()
    for i, cust in enumerate(sel_customers):
        if cust not in pivot_plot.index:
            continue

        color      = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        y_plot     = pivot_plot.loc[cust].tolist()
        y_raw      = pivot_raw.loc[cust].tolist()
        cls        = cust_meta.get(cust, {}).get("classification", "")
        n          = len(y_raw)

        prev_amounts = [0.0] + y_raw[:-1]
        prev_labels  = ["—"] + all_periods[:-1]
        customdata   = list(zip(prev_amounts, y_raw, [cls] * n, prev_labels))

        if trend_mode == "Per-Period":
            hover = (
                f"<b>{cust}</b><br>"
                "Period         : %{x}<br>"
                "Overdue        : <b>%{customdata[1]:,.2f} THB</b><br>"
                "Prev Period    : %{customdata[0]:,.2f} THB  (%{customdata[3]})<br>"
                "Classification : %{customdata[2]}<br>"
                "<extra></extra>"
            )
        else:
            hover = (
                f"<b>{cust}</b><br>"
                "Period            : %{x}<br>"
                "Outstanding Total : <b>%{y:,.2f} THB</b><br>"
                "New This Period   : %{customdata[1]:,.2f} THB<br>"
                "Classification    : %{customdata[2]}<br>"
                "<extra></extra>"
            )

        fig.add_trace(go.Scatter(
            x=all_periods, y=y_plot,
            mode="lines+markers", name=cust,
            line=dict(width=2.5, color=color),
            marker=dict(size=8, color=color, line=dict(width=1.5, color="white")),
            customdata=customdata, hovertemplate=hover,
        ))

    if len(sel_customers) > 1:
        avg_y = pivot_plot.mean(axis=0).tolist()
        fig.add_trace(go.Scatter(
            x=all_periods, y=avg_y, mode="lines",
            name="Portfolio Average",
            line=dict(width=2, dash="dot", color="rgba(0,0,0,0.45)"),
            hovertemplate=(
                "Portfolio Average<br>Period : %{x}<br>"
                "Overdue : <b>%{y:,.2f} THB</b><extra></extra>"
            ),
        ))

    # ── Y axis ────────────────────────────────────────────────────────────────
    if view_type == "Rounded Number":
        max_val = max(
            max(
                (pivot_plot.loc[c].max() for c in sel_customers if c in pivot_plot.index),
                default=1,
            ),
            1,
        )
        if max_val >= 1_000_000_000:
            tick_div, tick_suffix, tick_fmt = 1_000_000_000, " B THB", ".1f"
        elif max_val >= 1_000_000:
            tick_div, tick_suffix, tick_fmt = 1_000_000,     " M THB", ".0f"
        else:
            tick_div, tick_suffix, tick_fmt = 1_000,         " K THB", ".0f"

        y_vals_scaled = [
            [v / tick_div for v in pivot_plot.loc[c].tolist()]
            for c in sel_customers if c in pivot_plot.index
        ]
        for trace, scaled in zip(fig.data[:len(sel_customers)], y_vals_scaled):
            trace.y = scaled

        if len(sel_customers) > 1:
            fig.data[-1].y = [v / tick_div for v in avg_y]

        y_axis_cfg = dict(
            title=f"Overdue Amount ({tick_suffix.strip()})",
            ticksuffix=tick_suffix, tickformat=tick_fmt,
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            rangemode="tozero",
        )
    else:
        y_axis_cfg = dict(
            title=y_title,
            tickformat=",.0f", ticksuffix=" THB",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            rangemode="tozero",
        )

    apply_base_layout(fig, {
        "height": 420,
        "margin": dict(l=0, r=20, t=36, b=40),
        "title": dict(
            text=(
                f"Overdue Trend — {sel_customers[0]}"
                if len(sel_customers) == 1 else
                f"Overdue Trend — Top {len(sel_customers)} Companies ({trend_mode})"
            ),
            font=dict(size=11, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title=f"Period ({granularity})",
            tickangle=-35, tickfont=dict(size=8),
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, type="category",
            categoryorder="array", categoryarray=all_periods,
        ),
        "yaxis": y_axis_cfg,
        "legend": dict(
            orientation="v", x=1.01, y=1, font=dict(size=8),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#d0dae6", borderwidth=1,
        ),
        "hovermode": "closest",
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=10, color="#1B2A3B"), align="left",
        ),
    })

    st.plotly_chart(fig, use_container_width=True, key="chart_overdue_trend")
    return cust_meta


# =============================================================================
# Section 5 Right (40%) : Trend Summary Panel — ทุก card อยู่ใน scroll เดียว
# =============================================================================
def _render_trend_summary_panel(cust_meta: dict):
    if not cust_meta:
        st.info("No trend data to summarize.")
        return

    CLASS_STYLE = {
        "Escalating":   (PALETTE["crimson"],  "rgba(215,38,61,0.07)"),
        "Persistent":   (PALETTE["amber"],    "rgba(181,98,10,0.07)"),
        "Improving":    (PALETTE["jade"],     "rgba(26,122,74,0.07)"),
        "Intermittent": (PALETTE["nodata"],   "rgba(138,155,176,0.07)"),
    }

    # ── Classification strip ─────────────────────────────────────────────────
    from collections import Counter
    class_counts    = Counter(m["classification"] for m in cust_meta.values())
    total_companies = len(cust_meta)

    strip_parts = []
    for cls in ["Escalating", "Persistent", "Improving", "Intermittent"]:
        cnt = class_counts.get(cls, 0)
        if cnt == 0:
            continue
        accent, bg = CLASS_STYLE[cls]
        pct = cnt / total_companies * 100
        strip_parts.append(
            f"<div style='background:{bg};border:1px solid {accent}33;"
            f"border-radius:6px;padding:3px 9px;'>"
            f"<span style='font-size:0.67rem;font-weight:700;color:{accent};'>"
            f"{cls}</span>"
            f"<span style='font-size:0.67rem;color:#6b7a8d;margin-left:5px;'>"
            f"{cnt} ({pct:.0f}%)</span></div>"
        )

    strip_html = (
        "<div style='background:rgba(27,79,138,0.05);"
        "border:1px solid rgba(27,79,138,0.15);"
        "border-radius:8px;padding:10px 14px 8px 14px;margin-bottom:10px;'>"
        "<div style='font-size:0.68rem;font-weight:700;"
        f"color:{PALETTE['sapphire']};letter-spacing:0.06em;"
        "text-transform:uppercase;margin-bottom:6px;'>Portfolio Classification</div>"
        "<div style='display:flex;gap:8px;flex-wrap:wrap;'>"
        + "".join(strip_parts)
        + "</div></div>"
    )
    st.markdown(strip_html, unsafe_allow_html=True)

    # ── Build all cards HTML ──────────────────────────────────────────────────
    def _build_card(cust: str, meta: dict) -> str:
        accent, bg  = CLASS_STYLE.get(meta["classification"], ("#555", "#f5f5f5"))
        color       = meta["color"]
        delta_val   = meta["delta_ov"]
        delta_str   = f"+{delta_val:,.0f}" if delta_val > 0 else f"{delta_val:,.0f}"
        delta_color = (
            PALETTE["crimson"] if delta_val > 0 else
            PALETTE["jade"]    if delta_val < 0 else
            PALETTE["nodata"]
        )
        slope_dir = (
            "Increasing" if meta["slope"] > 0 else
            "Decreasing" if meta["slope"] < 0 else "Flat"
        )
        return (
            f"<div style='border-left:4px solid {color};background:{bg};"
            f"border-radius:0 8px 8px 0;padding:8px 12px;margin-bottom:7px;'>"
            f"<div style='display:flex;justify-content:space-between;"
            f"align-items:flex-start;margin-bottom:5px;'>"
            f"<div style='font-size:0.71rem;font-weight:700;color:{FONT_COLOR};"
            f"line-height:1.3;max-width:62%;word-break:break-word;'>{cust}</div>"
            f"<div style='font-size:0.61rem;font-weight:700;color:{accent};"
            f"background:rgba(255,255,255,0.72);border:1px solid {accent}55;"
            f"border-radius:4px;padding:2px 7px;white-space:nowrap;'>"
            f"{meta['classification']}</div></div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;'>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>Total Overdue</div>"
            f"<div style='font-size:0.69rem;font-weight:700;color:{FONT_COLOR};'>"
            f"{meta['total_ov']:,.0f}</div></div>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>Latest Period</div>"
            f"<div style='font-size:0.69rem;font-weight:700;color:{FONT_COLOR};'>"
            f"{meta['last_ov']:,.0f}</div></div>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>First to Last</div>"
            f"<div style='font-size:0.69rem;font-weight:700;color:{delta_color};'>"
            f"{delta_str}</div></div>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>Direction</div>"
            f"<div style='font-size:0.69rem;font-weight:700;color:{accent};'>"
            f"{slope_dir}</div></div>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>Active / Total Pd</div>"
            f"<div style='font-size:0.69rem;color:{FONT_COLOR};'>"
            f"{meta['active_periods']} / {meta['total_periods']}</div></div>"
            f"<div><div style='font-size:0.59rem;color:#6b7a8d;'>Peak Period</div>"
            f"<div style='font-size:0.69rem;color:{FONT_COLOR};'>"
            f"{meta['max_ov']:,.0f}</div></div>"
            f"</div></div>"
        )

    sorted_custs = sorted(
        cust_meta.items(), key=lambda x: x[1]["total_ov"], reverse=True
    )

    # ── ทุก card อยู่ใน scroll container เดียว ───────────────────────────────
    # max-height = ประมาณ 3.5 card เพื่อให้เห็นว่ามีอะไรด้านล่าง
    CARD_H_PX    = 112
    VISIBLE_N    = 3
    SCROLL_MAX_H = int(CARD_H_PX * VISIBLE_N + CARD_H_PX * 0.4)  # ~392px

    all_cards_html = "".join(
        _build_card(cust, meta) for cust, meta in sorted_custs
    )

    scroll_html = (
        f"<div style='"
        f"max-height:{SCROLL_MAX_H}px;"
        f"overflow-y:auto;"
        f"padding-right:6px;"
        f"scrollbar-width:thin;"
        f"scrollbar-color:{PALETTE['sapphire_lt']} #f0f4f8;"
        f"'>"
        + all_cards_html +
        f"</div>"
    )

    if len(sorted_custs) > VISIBLE_N:
        st.markdown(
            f"<div style='font-size:0.65rem;color:#6b7a8d;"
            f"margin-bottom:4px;'>"
            f"{len(sorted_custs)} companies — scroll to view all</div>",
            unsafe_allow_html=True,
        )

    st.markdown(scroll_html, unsafe_allow_html=True)




# =============================================================================
# Row 4 Left : Portfolio Concentration — Pareto Chart
# =============================================================================
def _render_pareto(df: pd.DataFrame, top_n: int = 20):
    if "CustomerName" not in df.columns:
        st.info("CustomerName column not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue data for Pareto chart.")
        return

    grouped = (
        overdue_df.groupby("CustomerName")["OverdueAbs"]
        .sum()
        .reset_index()
        .sort_values("OverdueAbs", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    total_overdue   = grouped["OverdueAbs"].sum()
    grouped["CumPct"] = (grouped["OverdueAbs"].cumsum() / total_overdue * 100).round(2)

    # Top 10 share annotation
    top10_pct = grouped.head(10)["OverdueAbs"].sum() / total_overdue * 100

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=grouped["CustomerName"],
            y=grouped["OverdueAbs"],
            name="Overdue Amount",
            marker_color=PALETTE["crimson"],
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Overdue : %{y:,.2f} THB<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=grouped["CustomerName"],
            y=grouped["CumPct"],
            name="Cumulative %",
            mode="lines+markers",
            line=dict(color=PALETTE["amber_lt"], width=2),
            marker=dict(size=5),
            hovertemplate="%{x}<br>Cumulative : %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    # 80% reference line
    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="#aaaaaa",
        line_width=1,
        secondary_y=True,
        annotation_text="80%",
        annotation_font=dict(size=8, color="#aaaaaa"),
        annotation_position="top right",
    )

    # Top-10 annotation
    fig.add_annotation(
        x=grouped["CustomerName"].iloc[min(9, len(grouped) - 1)],
        y=top10_pct,
        text=f"Top 10 = {top10_pct:.1f}% of overdue",
        showarrow=True,
        arrowhead=2,
        arrowcolor=PALETTE["crimson"],
        font=dict(size=9, color=PALETTE["crimson"]),
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=PALETTE["crimson"],
        borderwidth=1,
        ax=0, ay=-30,
    )

    fig.update_layout(
        height=340,
        margin=dict(l=0, r=40, t=30, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
        title=dict(
            text="Portfolio Concentration — Pareto",
            font=dict(size=11, color=FONT_COLOR), x=0,
        ),
        xaxis=dict(
            tickangle=-35, tickfont=dict(size=8),
            showgrid=False, color=FONT_COLOR,
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=9),
        ),
        barmode="group",
    )
    fig.update_yaxes(
        title_text="Overdue Amount (THB)",
        secondary_y=False,
        showgrid=True, gridcolor=GRID_COLOR,
        tickfont=dict(size=8),
    )
    fig.update_yaxes(
        title_text="Cumulative %",
        secondary_y=True,
        range=[0, 110],
        ticksuffix="%",
        tickfont=dict(size=8),
        showgrid=False,
    )

    st.plotly_chart(fig, use_container_width=True, key="chart_pareto")


# =============================================================================
# Row 4 Right : Concentration Treemap
# =============================================================================
def _render_treemap(df: pd.DataFrame, view_type: str = "Detail Number"):
    if "CustomerName" not in df.columns:
        st.info("CustomerName column not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue data for treemap.")
        return

    grouped = (
        overdue_df.groupby("CustomerName")["OverdueAbs"]
        .sum().reset_index()
        .sort_values("OverdueAbs", ascending=False)
        .head(30).reset_index(drop=True)
    )
    total          = grouped["OverdueAbs"].sum()
    grouped["Pct"] = (grouped["OverdueAbs"] / total * 100).round(2)

    # label บน tile — Rounded: scaled + unit, Detail: raw with commas
    def _tile_label(row) -> str:
        amt_str = _fmt_bar(row["OverdueAbs"], view_type)
        return f"{row['CustomerName']}<br>{row['Pct']:.1f}%<br>{amt_str}"

    grouped["Label"] = grouped.apply(_tile_label, axis=1)

    # hover — Detail mode แสดง raw THB ชัดเจน
    hover_fmt = (
        "<b>%{label}</b><br>"
        "Overdue : %{value:,.2f} THB<extra></extra>"
    )

    fig = go.Figure(go.Treemap(
        labels=grouped["Label"],
        parents=[""] * len(grouped),
        values=grouped["OverdueAbs"],
        textinfo="label",
        textfont=dict(size=12),
        marker=dict(
            colors=grouped["OverdueAbs"],
            colorscale=[
                [0.0,  "#FFDDD2"],
                [0.4,  PALETTE["amber_lt"]],
                [0.75, PALETTE["amber"]],
                [1.0,  PALETTE["crimson"]],
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="Overdue (THB)", font=dict(size=10)),
                thickness=14, len=0.8, tickfont=dict(size=9),
            ),
            line=dict(width=1.5, color="white"),
        ),
        hovertemplate=hover_fmt,
    ))

    apply_base_layout(fig, {
        "height": 520,
        "margin": dict(l=0, r=0, t=40, b=4),
        "title": dict(
            text="Overdue Share by Customer — Top 30",
            font=dict(size=12, color=FONT_COLOR), x=0,
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_treemap")


# =============================================================================
# Raw table (expandable)
# =============================================================================
def _render_priority_table(df: pd.DataFrame):
    desired = [
        "CustomerName", "CustomerNo", "InvoiceNo",
        "OriginalDueDate", "CollectionDate",
        "OverdueAmount", "InvoiceAmount", "DPD",
    ]
    available = [c for c in desired if c in df.columns]
    overdue_df = df[df["IsOverdue"]][available].copy().sort_values(
        "OverdueAmount", ascending=True
    )

    if overdue_df.empty:
        st.info("No overdue records.")
        return

    for col in ("OriginalDueDate", "CollectionDate"):
        if col in overdue_df.columns:
            overdue_df[col] = pd.to_datetime(
                overdue_df[col], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

    st.dataframe(
        overdue_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "OverdueAmount": st.column_config.NumberColumn("Overdue Amount (THB)", format="%.2f"),
            "InvoiceAmount": st.column_config.NumberColumn("Invoice Amount (THB)", format="%.2f"),
            "DPD":           st.column_config.NumberColumn("DPD (days)",           format="%d"),
        },
    )


# =============================================================================
# Utility
# =============================================================================
def _no_data_banner():
    st.markdown(
        """
        <div style="text-align:center;padding:60px 20px;">
          <h3 style="color:#8A9BB0;">No Data Available</h3>
          <p style="color:#8A9BB0;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )