# =============================================================================
# views/view_monitoring.py
# Join key : df_overdue.Customer == df_avail.CUSTOMER_CODE
# =============================================================================

import streamlit as st
from collections import defaultdict
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from components import (
    apply_base_layout,
    kpi_card,
    section_header,
    dash_title_bar,
    FONT_COLOR,
    GRID_COLOR,
)

# ---------------------------------------------------------------------------
# Design tokens — consistent with view_avail / view_overdue
# ---------------------------------------------------------------------------
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
    "threshold":   "#C0392B",
}

MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Risk tier thresholds
UTIL_HIGH   = 0.80   # Debt % >= 80% → danger
UTIL_MED    = 0.50   # Debt % >= 50% → warning
DPD_HIGH    = 60     # DPD >= 60 → serious
DPD_MED     = 30     # DPD >= 30 → watch


# =============================================================================
# KPI card HTML — same pattern as view_overdue._overdue_kpi_card
# =============================================================================
def _mon_kpi_card(label: str, value: str, sub: str, variant: str) -> str:
    variant_styles = {
        "danger":  ("rgba(215,38,61,0.07)",  "#A01F2D"),
        "warning": ("rgba(181,98,10,0.07)",  "#B5620A"),
        "safe":    ("rgba(26,122,74,0.07)",  "#1A7A4A"),
        "info":    ("rgba(27,79,138,0.07)",  "#1B4F8A"),
    }
    bg, accent = variant_styles.get(variant, variant_styles["info"])
    vlen = len(str(value))
    if vlen <= 8:    v_font = "1.45rem"
    elif vlen <= 14: v_font = "1.15rem"
    elif vlen <= 22: v_font = "0.95rem"
    else:            v_font = "0.80rem"

    sub_html = f"<p style='margin:0;font-size:0.70rem;color:#5a6a7a;'>{sub}</p>" if sub else ""

    return (
        f"<div style='background:{bg};border-left:3px solid {accent};"
        f"border-radius:8px;padding:12px 14px;height:110px;"
        f"display:flex;flex-direction:column;justify-content:space-between;'>"
        f"<p style='margin:0;font-size:0.68rem;font-weight:600;"
        f"color:{accent};text-transform:uppercase;letter-spacing:0.04em;'>{label}</p>"
        f"<p style='margin:4px 0 2px;font-size:{v_font};font-weight:700;"
        f"color:{accent};line-height:1.1;'>{value}</p>"
        f"{sub_html}"
        f"</div>"
    )


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================
def render():
    if not st.session_state.get("data_processed", False):
        _no_data_banner()
        return

    df_avail   = st.session_state.get("df_avail")
    df_overdue = st.session_state.get("df_overdue")

    if df_avail is None or (hasattr(df_avail, "empty") and df_avail.empty):
        st.warning("df_avail is empty. Please re-process the data pipeline.")
        return
    if df_overdue is None or (hasattr(df_overdue, "empty") and df_overdue.empty):
        st.warning("df_overdue is empty. Please re-process the data pipeline.")
        return

    st.markdown(
        dash_title_bar(
            "Credit Planning Dashboard",
            "Credit Planning — collection forecast, pipeline, and action board",
        ),
        unsafe_allow_html=True,
    )

    df_avail_prep   = _prepare_avail(df_avail.copy())
    df_overdue_prep = _prepare_overdue(df_overdue.copy())
    df_joined       = _build_joined(df_avail_prep, df_overdue_prep)

    df_filtered, selected_company, year_filter = _render_filters(
        df_avail_prep, df_overdue_prep, df_joined
    )

    if df_filtered is None or df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    run_credit_moni_logging(df_overdue_prep, df_filtered, selected_company)

    # ==================================================================
    # ZONE 1 — HEALTH SNAPSHOT
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px'>"
        "ZONE 1 — HEALTH SNAPSHOT</div>",
        unsafe_allow_html=True,
    )

    st.markdown(section_header("Monitoring Health — Key Signals"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(
        section_header("Credit Health Matrix — Utilization vs Overdue Risk"),
        unsafe_allow_html=True,
    )
    col_bubble, col_tier = st.columns([3, 2], gap="medium")
    with col_bubble:
        _render_health_bubble(df_filtered)
    with col_tier:
        _render_risk_tier_donut(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(
        section_header("Watchlist — Customers Needing Immediate Attention"),
        unsafe_allow_html=True,
    )
    _render_watchlist(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    # ==================================================================
    # ZONE 2 — PLANNING
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px'>"
        "ZONE 2 — PLANNING</div>",
        unsafe_allow_html=True,
    )

    st.markdown(section_header("Collection Pipeline"), unsafe_allow_html=True)
    _render_collection_pipeline(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Cash Inflow Planning"), unsafe_allow_html=True)
    _render_cash_inflow_forecast(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Collection Planning"), unsafe_allow_html=True)
    _render_future_collection_forecast(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Credit Planner — Action Board"), unsafe_allow_html=True)
    _render_credit_planner_board(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    # ==================================================================
    # ZONE 3 — HISTORICAL ANALYSIS
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px'>"
        "ZONE 3 — HISTORICAL ANALYSIS</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        section_header("Credit Journey — Invoice Extension Sankey"),
        unsafe_allow_html=True,
    )
    _render_credit_journey_sankey(df_filtered)
    st.markdown("", unsafe_allow_html=True)

    with st.expander("View Joined Records — Credit Availability x Overdue", expanded=False):
        _render_joined_table(df_filtered)
    st.markdown("", unsafe_allow_html=True)


# =============================================================================
# Data Preparation
# =============================================================================
def _prepare_avail(df: pd.DataFrame) -> pd.DataFrame:
    """Clean & type-cast df_avail — mirrors et_pipeline output."""
    if "CUSTOMER_CODE" in df.columns:
        df["CUSTOMER_CODE"] = (
            pd.to_numeric(df["CUSTOMER_CODE"], errors="coerce")
            .fillna(0).astype(int)
        )
    if "CURRENT_DEBT_MILLION_THB_PERCENT" in df.columns:
        df["CURRENT_DEBT_MILLION_THB_PERCENT"] = pd.to_numeric(
            df["CURRENT_DEBT_MILLION_THB_PERCENT"], errors="coerce"
        ).fillna(0.0)
    for col in ("CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB", "EST_DEBT"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    if "SOURCE_SHEET" in df.columns:
        df["AVAIL_YEAR"] = df["SOURCE_SHEET"].astype(str).str.strip()
    return df


def _prepare_overdue(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]

    def _parse_date_flexible(series: pd.Series) -> pd.Series:
        s = (
            series.astype(str)
            .str.strip()
            .replace({"nan": None, "": None, "NaT": None, "#": None,
                      "None": None, "NA": None, "N/A": None})
        )
        result = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        nat_mask = result.isna() & s.notna()
        if nat_mask.any():
            result[nat_mask] = pd.to_datetime(
                s[nat_mask], format="mixed", errors="coerce"
            )
        return result

    for col in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
        if col in df.columns:
            df[col] = _parse_date_flexible(df[col])

    for col in ("OverdueAmount", "InvoiceAmount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "CompanyCode" in df.columns:
        df["CompanyCode"] = df["CompanyCode"].astype(str).str.strip()

    if "Customer" in df.columns:
        df["Customer"] = (
            pd.to_numeric(df["Customer"], errors="coerce").fillna(0).astype(int)
        )

    # --- Classify OverdueAmount ---
    # > 0 = ยังค้างอยู่ (ยังไม่จ่าย)
    # = 0 = จ่ายแล้ว
    # < 0 = Credit Note (monitor แยกกลุ่ม)
    df["IsOverdue"]    = df["OverdueAmount"] > 0
    df["IsCreditNote"] = df["OverdueAmount"] < 0
    df["OverdueAbs"]   = df["OverdueAmount"].clip(lower=0)
    df["IsPaid"]       = df["OverdueAmount"] == 0

    today = pd.Timestamp("today").normalize()

    # --- DPD: นับจาก OriginalDueDate ถึงวันนี้ เฉพาะ row ที่ยังไม่จ่าย ---
    if "OriginalDueDate" in df.columns:
        df["DPD"] = np.where(
            df["IsPaid"],
            0,
            np.where(
                df["OriginalDueDate"].notna(),
                (today - df["OriginalDueDate"]).dt.days.clip(lower=0),
                np.nan,
            ),
        )
        df["DueYear"]       = df["OriginalDueDate"].dt.year.astype("Int64")
        df["DueMonth"]      = df["OriginalDueDate"].dt.month.astype("Int64")
        df["DueQuarter"]    = df["OriginalDueDate"].dt.quarter.astype("Int64")
        df["DueMonthLabel"] = df["DueMonth"].map(MONTH_MAP)

        df["AgingBucket"] = pd.cut(
            df["DPD"].fillna(0).clip(lower=0),
            bins=[-1, 30, 60, 90, float("inf")],
            labels=["1-30", "31-60", "61-90", "90+"],
        )

    # --- Extension: CollectionDate คือด่านสุดท้าย (ขอบเขต extension) ---
    if "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
        df["HasExtension"] = (
            df["CollectionDate"].notna()
            & df["OriginalDueDate"].notna()
            & (df["CollectionDate"] > df["OriginalDueDate"])
        )
        df["ExtensionDays"] = np.where(
            df["HasExtension"],
            (df["CollectionDate"] - df["OriginalDueDate"]).dt.days.clip(lower=0),
            0,
        )
    else:
        df["HasExtension"]  = False
        df["ExtensionDays"] = 0

    # --- CustomerExtDays: วันที่ลูกค้า confirm ว่าจะจ่าย ห่างจากกำหนดเดิม ---
    if "CustomerDueDate" in df.columns and "OriginalDueDate" in df.columns:
        df["CustomerExtDays"] = np.where(
            df["CustomerDueDate"].notna() & df["OriginalDueDate"].notna(),
            (df["CustomerDueDate"] - df["OriginalDueDate"]).dt.days.clip(lower=0),
            0,
        )
    else:
        df["CustomerExtDays"] = 0

    # --- PaidOnTime / PaidLate / NotCollected ---
    # ใช้ CollectionDate เป็นด่านสุดท้าย (fallback จาก CustomerDueDate)
    # PaidOnTime   = IsPaid & CollectionDate <= OriginalDueDate (ไม่ขยาย หรือขยายน้อยมาก)
    # PaidLate     = IsPaid & CollectionDate > OriginalDueDate  (จ่ายแล้วแต่ขยายออกไป)
    # NotCollected = OverdueAmount > 0 (ยังไม่จ่าย)
    if "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
        is_invoice = df["OverdueAmount"] >= 0

        df["PaidOnTime"] = (
            df["IsPaid"]
            & is_invoice
            & df["CollectionDate"].notna()
            & df["OriginalDueDate"].notna()
            & (df["CollectionDate"] <= df["OriginalDueDate"])
        )
        df["PaidLate"] = (
            df["IsPaid"]
            & is_invoice
            & df["CollectionDate"].notna()
            & df["OriginalDueDate"].notna()
            & (df["CollectionDate"] > df["OriginalDueDate"])
        )
        # IsPaid แต่ไม่มี date ครบ → Unknown (ไม่ classify ทั้งคู่)
        # OriginalDueDate หรือ CustomerDueDate เป็น # → OverdueAmount = 0 → IsPaid = True
        df["PaidUnknown"] = (
            df["IsPaid"]
            & is_invoice
            & (df["OriginalDueDate"].isna() | df["CollectionDate"].isna())
        )
        df["NotCollected"] = df["OverdueAmount"] > 0

    else:
        df["PaidOnTime"]   = df["IsPaid"]
        df["PaidLate"]     = False
        df["PaidUnknown"]  = False
        df["NotCollected"] = df["OverdueAmount"] > 0

    return df


def _agg_customer_overdue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate overdue data ระดับ customer
    NetOverdue    = sum(OverdueAmount)  → gross - credit note
    GrossOverdue  = sum(OverdueAbs)     → gross เท่านั้น
    CreditNote    = sum(|negative rows|)
    """
    if df.empty or "OverdueAmount" not in df.columns:
        return pd.DataFrame()

    working = df[df["OverdueAmount"] != 0].copy()
    if working.empty:
        return pd.DataFrame()

    name_col = "CustomerName" if "CustomerName" in working.columns else None

    agg_dict = {
        "NetOverdue":       ("OverdueAmount", "sum"),
        "GrossOverdue":     ("OverdueAbs",    "sum"),
        "CreditNoteOffset": ("OverdueAmount", lambda x: x[x < 0].abs().sum()),
        "OverdueInvoices":  ("IsOverdue",     "sum"),
        "CreditNoteCount":  ("IsCreditNote",  "sum"),
    }

    if "DPD" in working.columns:
        agg_dict["MaxDPD"] = ("DPD", "max")
        agg_dict["AvgDPD"] = ("DPD", "mean")

    if name_col:
        agg_dict["CustomerName"] = ("CustomerName", "first")

    if "RiskTier" in working.columns:
        agg_dict["RiskTier"] = (
            "RiskTier",
            lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown",
        )

    # ใช้ mean แทน first — ค่าเหล่านี้มาจาก avail join ซึ่งเหมือนกันทุก row
    # mean ป้องกัน NaN จาก row แรกที่อาจยังไม่ join
    for col in ("CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB"):
        if col in working.columns:
            agg_dict[col] = (col, "mean")

    # UtilizationPct: mean และกรองเฉพาะค่า > 0 ก่อน mean
    # เพราะ row ที่ join ไม่สำเร็จจะเป็น 0 ซึ่งดึงค่าเฉลี่ยลงผิดจริง
    if "UtilizationPct" in working.columns:
        agg_dict["UtilizationPct"] = (
            "UtilizationPct",
            lambda x: x[x > 0].mean() if (x > 0).any() else 0.0,
        )

    if "TYPE" in working.columns:
        agg_dict["TYPE"] = ("TYPE", "first")

    result = working.groupby("Customer").agg(**agg_dict).reset_index()

    result["NetOverdue"] = result["NetOverdue"].clip(lower=0)

    if name_col is None:
        result["CustomerName"] = result["Customer"].astype(str)

    for col in ("MaxDPD", "AvgDPD", "NetOverdue", "GrossOverdue",
                "CreditNoteOffset", "UtilizationPct",
                "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB"):
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0.0)

    return result

def _build_joined(df_avail: pd.DataFrame, df_overdue: pd.DataFrame) -> pd.DataFrame:
    """
    Join overdue × avail on Customer == CUSTOMER_CODE.
    Uses latest DATE snapshot per CUSTOMER_CODE from avail.
    Result rows = overdue rows enriched with avail columns.
    """
    if df_avail.empty or df_overdue.empty:
        return df_overdue.copy()

    # Latest snapshot per customer from avail
    if "DATE" in df_avail.columns:
        snap = (
            df_avail.sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE"])
        )
    else:
        snap = df_avail.drop_duplicates(subset=["CUSTOMER_CODE"])

    avail_cols = [
        "CUSTOMER_CODE", "CUSTOMER_NAME", "TYPE",
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT",
        "AVAIL_YEAR",
    ]
    keep_cols = [c for c in avail_cols if c in snap.columns]
    snap = snap[keep_cols].copy().reset_index(drop=True)

    # Suffix avail CUSTOMER_NAME to avoid collision
    if "CUSTOMER_NAME" in snap.columns:
        snap = snap.rename(columns={"CUSTOMER_NAME": "AVAIL_CUSTOMER_NAME"})

    joined = df_overdue.merge(
        snap,
        left_on="Customer",
        right_on="CUSTOMER_CODE",
        how="left",
    ).reset_index(drop=True)

    # Utilization %
    if "CURRENT_DEBT_MILLION_THB_PERCENT" in joined.columns:
        joined["UtilizationPct"] = joined["CURRENT_DEBT_MILLION_THB_PERCENT"] * 100
    else:
        joined["UtilizationPct"] = np.nan

    # Risk Tier (per row, for bubble & donut)
    def _tier(row):
        util = row.get("UtilizationPct", np.nan)
        dpd  = row.get("DPD", 0)
        if pd.isna(util):
            return "Unknown"
        if util >= 80 and dpd >= DPD_HIGH:
            return "Critical"
        elif util >= 80 or dpd >= DPD_HIGH:
            return "High Risk"
        elif util >= 50 or dpd >= DPD_MED:
            return "Watch"
        else:
            return "Healthy"

    joined["RiskTier"] = joined.apply(_tier, axis=1)
    return joined


# =============================================================================
# Filters
# =============================================================================
def _render_filters(df_avail, df_overdue, df_joined):
    LABEL_STYLE = (
        "font-size:0.75rem;font-weight:600;color:#1B4F8A;"
        "letter-spacing:0.01em;margin-bottom:2px;display:block;line-height:1.4;"
    )

    available_companies = (
        sorted(df_overdue["CompanyCode"].dropna().unique().tolist())
        if "CompanyCode" in df_overdue.columns else ["All"]
    )
    default_idx = 0
    if "1190" in available_companies:
        default_idx = available_companies.index("1190")

    overdue_due_years = []
    if "DueYear" in df_overdue.columns:
        overdue_due_years = sorted(
            df_overdue["DueYear"].dropna().astype(int).unique().tolist()
        )

    avail_years_available = set()
    if "AVAIL_YEAR" in df_avail.columns:
        avail_years_available = set(
            df_avail["AVAIL_YEAR"].dropna().astype(str).unique().tolist()
        )

    # Customer Name list
    all_customer_names = []
    for col in ("CustomerName", "AVAIL_CUSTOMER_NAME"):
        if col in df_joined.columns:
            names = (
                df_joined[col]
                .dropna()
                .astype(str)
                .str.strip()
                .replace({"": None, "nan": None, "None": None})
                .dropna()
                .unique()
                .tolist()
            )
            all_customer_names = sorted(names)
            break

    # Customer Code list
    all_customer_codes = []
    if "Customer" in df_joined.columns:
        all_customer_codes = sorted(
            df_joined["Customer"].dropna().astype(int).unique().tolist()
        )

    COLS = [1.0, 1.0, 1.0, 1.4, 1.4]
    lc1, lc2, lc3, lc4, lc5 = st.columns(COLS, gap="small")
    with lc1: st.markdown(f"<span style='{LABEL_STYLE}'>Company Code</span>",         unsafe_allow_html=True)
    with lc2: st.markdown(f"<span style='{LABEL_STYLE}'>Overdue Due Year</span>",     unsafe_allow_html=True)
    with lc3: st.markdown(f"<span style='{LABEL_STYLE}'>Risk Tier</span>",            unsafe_allow_html=True)
    with lc4: st.markdown(f"<span style='{LABEL_STYLE}'>Search Customer Code</span>", unsafe_allow_html=True)
    with lc5: st.markdown(f"<span style='{LABEL_STYLE}'>Search Customer Name</span>", unsafe_allow_html=True)

    wc1, wc2, wc3, wc4, wc5 = st.columns(COLS, gap="small")

    with wc1:
        selected_company = st.selectbox(
            "Company Code", options=available_companies,
            index=default_idx, key="mon_company",
            label_visibility="collapsed",
        )

    with wc2:
        due_year_opts = ["All"] + [str(y) for y in overdue_due_years]
        selected_due_year = st.selectbox(
            "Overdue Due Year", options=due_year_opts,
            index=0, key="mon_due_year",
            label_visibility="collapsed",
            help=(
                "กรอง overdue transaction ตาม OriginalDueDate\n"
                "All = ทุกปี\n"
                "Credit Availability จะ map ปีที่ตรงกัน "
                "ถ้าไม่มีข้อมูลปีนั้นจะใช้ snapshot ล่าสุดที่มี"
            ),
        )

    with wc3:
        tier_options = ["All", "Critical", "High Risk", "Watch", "Healthy", "Unknown"]
        selected_tier = st.selectbox(
            "Risk Tier", options=tier_options,
            index=0, key="mon_tier",
            label_visibility="collapsed",
        )

    with wc4:
        code_search_query = st.text_input(
            "Search Customer Code",
            placeholder="Type code to filter...",
            key="mon_code_search",
            label_visibility="collapsed",
        ).strip()

        if code_search_query:
            filtered_codes = [
                c for c in all_customer_codes
                if code_search_query in str(c)
            ]
        else:
            filtered_codes = all_customer_codes

        code_options = ["All codes"] + [str(c) for c in filtered_codes]

        prev_code  = st.session_state.get("_mon_selected_code", "All codes")
        default_code_ix = (
            code_options.index(prev_code)
            if prev_code in code_options else 0
        )

        selected_code_option = st.selectbox(
            "Customer Code Recommend",
            options=code_options,
            index=default_code_ix,
            key="mon_code_recommend",
            label_visibility="collapsed",
        )
        st.session_state["_mon_selected_code"] = selected_code_option

        if filtered_codes and code_search_query:
            st.markdown(
                f"<span style='font-size:0.72rem;color:#3D5166;'>"
                f"{len(filtered_codes)} result(s) — code: {code_search_query}</span>",
                unsafe_allow_html=True,
            )

    with wc5:
        search_query = st.text_input(
            "Search Customer Name",
            placeholder="Type name to filter...",
            key="mon_customer_search",
            label_visibility="collapsed",
        ).strip()

        if search_query:
            q = search_query.lower()
            filtered_names = [n for n in all_customer_names if q in n.lower()]
        else:
            filtered_names = all_customer_names

        recommend_options = ["All customers"] + filtered_names

        prev_sel   = st.session_state.get("_mon_selected_customer", "All customers")
        default_ix = (
            recommend_options.index(prev_sel)
            if prev_sel in recommend_options else 0
        )

        selected_name_option = st.selectbox(
            "Customer Recommend",
            options=recommend_options,
            index=default_ix,
            key="mon_customer_recommend",
            label_visibility="collapsed",
        )
        st.session_state["_mon_selected_customer"] = selected_name_option

        if filtered_names and search_query:
            st.markdown(
                f"<span style='font-size:0.72rem;color:#3D5166;'>"
                f"{len(filtered_names)} result(s) — search: {search_query}</span>",
                unsafe_allow_html=True,
            )

    # ==========================================================
    # Apply filters
    # ==========================================================
    df = df_joined.copy()

    # 1. CompanyCode
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    # 2. Overdue Due Year
    if selected_due_year != "All":
        try:
            due_year_int = int(selected_due_year)
        except (ValueError, TypeError):
            due_year_int = None

        if due_year_int and "DueYear" in df.columns:
            df = df[df["DueYear"] == due_year_int]

            due_year_str   = str(due_year_int)
            avail_year_int = sorted([int(y) for y in avail_years_available if y.isdigit()])

            if due_year_str in avail_years_available:
                matched_avail_year = due_year_str
            elif avail_year_int:
                before = [y for y in avail_year_int if y <= due_year_int]
                after  = [y for y in avail_year_int if y > due_year_int]
                if before:
                    matched_avail_year = str(max(before))
                else:
                    matched_avail_year = str(min(after))
            else:
                matched_avail_year = None

            if matched_avail_year and not df_avail.empty:
                avail_for_year = df_avail[
                    df_avail["AVAIL_YEAR"].astype(str) == matched_avail_year
                ].copy()

                if not avail_for_year.empty:
                    if "DATE" in avail_for_year.columns:
                        snap = (
                            avail_for_year
                            .sort_values("DATE", ascending=False)
                            .drop_duplicates(subset=["CUSTOMER_CODE"])
                        )
                    else:
                        snap = avail_for_year.drop_duplicates(subset=["CUSTOMER_CODE"])

                    avail_keep = [
                        "CUSTOMER_CODE", "CUSTOMER_NAME", "TYPE",
                        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
                        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT", "AVAIL_YEAR",
                    ]
                    snap = snap[[c for c in avail_keep if c in snap.columns]].copy()
                    if "CUSTOMER_NAME" in snap.columns:
                        snap = snap.rename(columns={"CUSTOMER_NAME": "AVAIL_CUSTOMER_NAME"})

                    drop_cols = [
                        c for c in df.columns if c in {
                            "CUSTOMER_CODE", "AVAIL_CUSTOMER_NAME", "TYPE",
                            "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
                            "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT",
                            "AVAIL_YEAR", "UtilizationPct", "RiskTier",
                        }
                    ]
                    df = df.drop(columns=drop_cols, errors="ignore")
                    df = df.merge(
                        snap,
                        left_on="Customer", right_on="CUSTOMER_CODE",
                        how="left",
                    )

                    if "CURRENT_DEBT_MILLION_THB_PERCENT" in df.columns:
                        pct = df["CURRENT_DEBT_MILLION_THB_PERCENT"].fillna(0.0)
                        if pct.eq(0).all() and \
                                "CURRENT_DEBT_MILLION_THB" in df.columns and \
                                "CLEAN_CREDIT_MB" in df.columns:
                            df["UtilizationPct"] = (
                                df["CURRENT_DEBT_MILLION_THB"]
                                / df["CLEAN_CREDIT_MB"].replace(0, np.nan) * 100
                            ).fillna(0.0)
                        else:
                            df["UtilizationPct"] = pct * 100
                    else:
                        df["UtilizationPct"] = np.nan

                    def _tier(row):
                        util = row.get("UtilizationPct", np.nan)
                        dpd  = row.get("DPD", 0) or 0
                        if pd.isna(util):
                            return "Unknown"
                        if util >= 80 and dpd >= DPD_HIGH:
                            return "Critical"
                        elif util >= 80 or dpd >= DPD_HIGH:
                            return "High Risk"
                        elif util >= 50 or dpd >= DPD_MED:
                            return "Watch"
                        else:
                            return "Healthy"

                    df["RiskTier"] = df.apply(_tier, axis=1)

                if matched_avail_year == due_year_str:
                    st.info(
                        f"Overdue {due_year_int} — "
                        f"mapped with Availability {matched_avail_year} (exact match)",
                        icon="✅",
                    )
                else:
                    st.warning(
                        f"Overdue {due_year_int} — "
                        f"no exact Availability data, "
                        f"using nearest year: {matched_avail_year}. "
                        f"Credit metrics reflect {matched_avail_year} snapshot.",
                    )
            else:
                st.warning(
                    f"Overdue {due_year_int} — "
                    f"no Availability data available to map. "
                    f"Credit metrics will show as N/A.",
                )

    # 3. Risk Tier
    if selected_tier != "All" and "RiskTier" in df.columns:
        df = df[df["RiskTier"] == selected_tier]

    # 4. Customer Code filter
    if selected_code_option != "All codes":
        try:
            code_int = int(selected_code_option)
            if "Customer" in df.columns:
                df = df[df["Customer"] == code_int]
        except ValueError:
            pass

    # 5. Customer Name filter
    if selected_name_option != "All customers":
        for col_search in ("CustomerName", "AVAIL_CUSTOMER_NAME"):
            if col_search in df.columns:
                df = df[df[col_search].astype(str) == selected_name_option]
                break
    elif search_query:
        for col_search in ("CustomerName", "AVAIL_CUSTOMER_NAME"):
            if col_search in df.columns:
                df = df[
                    df[col_search].astype(str)
                    .str.contains(search_query, case=False, na=False)
                ]
                break

    return df, selected_company, selected_due_year


# =============================================================================
# SECTION 1 — Monitoring KPI Row
# =============================================================================
def _render_kpi_row(df: pd.DataFrame):
    total_customers = (
        int(df["Customer"].nunique()) if "Customer" in df.columns else 0
    )
    critical_count = (
        int(df[df["RiskTier"] == "Critical"]["Customer"].nunique())
        if "RiskTier" in df.columns else 0
    )
    avg_util = (
        float(df["UtilizationPct"].dropna().mean())
        if "UtilizationPct" in df.columns else 0.0
    )

    # aggregate customer-level ที่ถูกต้อง
    cust_agg = _agg_customer_overdue(df)

    gross_overdue      = float(cust_agg["GrossOverdue"].sum())      if not cust_agg.empty else 0.0
    credit_note_offset = float(cust_agg["CreditNoteOffset"].sum())  if not cust_agg.empty else 0.0
    net_overdue        = float(cust_agg["NetOverdue"].sum())        if not cust_agg.empty else 0.0
    overdue_customers  = int((cust_agg["NetOverdue"] > 0).sum())    if not cust_agg.empty else 0

    pct_overdue = (overdue_customers / total_customers * 100) if total_customers > 0 else 0.0

    cards = [
        (
            "Monitored Customers",
            f"{total_customers:,}",
            "Unique in joined view",
            "info",
        ),
        (
            "Critical Risk",
            f"{critical_count:,}",
            "Util >= 80% & DPD >= 60",
            "danger" if critical_count > 0 else "safe",
        ),
        (
            "Net Overdue Exposure",
            f"{net_overdue:,.0f}",
            f"THB  |  Gross {gross_overdue:,.0f}  -  CN {credit_note_offset:,.0f}",
            "danger" if net_overdue > 0 else "safe",
        ),
        (
            "Avg Utilization",
            f"{avg_util:.1f}%",
            "Current Debt / Credit Limit",
            "danger" if avg_util >= 80 else ("warning" if avg_util >= 50 else "info"),
        ),
        (
            "% Customers Overdue",
            f"{pct_overdue:.1f}%",
            f"{overdue_customers:,} of {total_customers:,} customers",
            "danger" if pct_overdue >= 30 else ("warning" if pct_overdue >= 10 else "safe"),
        ),
    ]

    cols = st.columns(5, gap="small")
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(_mon_kpi_card(label, value, sub, variant), unsafe_allow_html=True)

# =============================================================================
# SECTION 2A — Credit Health Bubble Scatter
# X = Utilization %, Y = OverdueAbs, Size = CLEAN_CREDIT_MB, Color = RiskTier
# =============================================================================
TIER_COLOR = {
    "Critical":  PALETTE["crimson"],
    "High Risk": PALETTE["amber"],
    "Watch":     PALETTE["amber_lt"],
    "Healthy":   PALETTE["jade_lt"],
    "Unknown":   PALETTE["nodata"],
}
TIER_ORDER = ["Critical", "High Risk", "Watch", "Healthy", "Unknown"]


def _render_health_bubble(df: pd.DataFrame):
    """
    Bubble Scatter: X = Utilization%, Y = Net Overdue (THB)
    Bubble size = CLEAN_CREDIT_MB
    Color = Risk Tier
    Each point = 1 unique customer (aggregated via _agg_customer_overdue)
    """
    need = {"Customer", "UtilizationPct", "OverdueAmount", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("Insufficient columns for Health Matrix.")
        return

    agg = _agg_customer_overdue(df)

    if agg.empty:
        st.info("No overdue data to display.")
        return

    agg = agg.rename(columns={"NetOverdue": "TotalOverdue"})
    agg = agg[agg["TotalOverdue"] > 0].copy()

    if agg.empty:
        st.info("No customers with net overdue > 0.")
        return

    # BubbleSize จาก CLEAN_CREDIT_MB
    FALLBACK_SIZE = 18.0

    if "CLEAN_CREDIT_MB" in agg.columns:
        raw_credit = agg["CLEAN_CREDIT_MB"].fillna(0.0)
        if raw_credit.sum() == 0:
            agg["BubbleSize"] = FALLBACK_SIZE
        else:
            credit_vals  = raw_credit.clip(lower=1.0)
            credit_min   = float(credit_vals.min())
            credit_max   = float(credit_vals.max())
            credit_range = max(credit_max - credit_min, 1.0)
            agg["BubbleSize"] = 8.0 + ((credit_vals - credit_min) / credit_range) * 42.0
    else:
        agg["BubbleSize"] = FALLBACK_SIZE

    agg["BubbleSize"] = (
        agg["BubbleSize"]
        .fillna(FALLBACK_SIZE)
        .clip(lower=6.0, upper=60.0)
        .astype(float)
    )

    agg["UtilizationPct"] = agg["UtilizationPct"].fillna(0.0).astype(float)
    agg["TotalOverdue"]   = agg["TotalOverdue"].fillna(0.0).astype(float)

    label_col = "CustomerName" if "CustomerName" in agg.columns else "Customer"

    fig = go.Figure()

    for tier in TIER_ORDER:
        grp = agg[agg["RiskTier"] == tier].copy()
        if grp.empty:
            continue

        gross_col = "GrossOverdue" if "GrossOverdue" in grp.columns else "TotalOverdue"
        cn_col    = "CreditNoteOffset" if "CreditNoteOffset" in grp.columns else None
        credit_col = "CLEAN_CREDIT_MB" if "CLEAN_CREDIT_MB" in grp.columns else None

        custom = list(zip(
            grp["TotalOverdue"].tolist(),
            grp[gross_col].tolist(),
            grp[cn_col].tolist()    if cn_col    else [0.0] * len(grp),
            grp[credit_col].fillna(0.0).tolist() if credit_col else [0.0] * len(grp),
        ))

        fig.add_trace(go.Scatter(
            x    = grp["UtilizationPct"].tolist(),
            y    = grp["TotalOverdue"].tolist(),
            mode = "markers",
            name = tier,
            marker = dict(
                size     = grp["BubbleSize"].tolist(),
                color    = TIER_COLOR.get(tier, PALETTE["nodata"]),
                opacity  = 0.80,
                line     = dict(width=1, color="white"),
                sizemode = "diameter",
            ),
            text       = grp[label_col].astype(str).tolist(),
            customdata = custom,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Utilization : %{x:.1f}%<br>"
                "Net Overdue : %{customdata[0]:,.0f} THB<br>"
                "Gross Overdue: %{customdata[1]:,.0f} THB<br>"
                "Credit Note : %{customdata[2]:,.0f} THB<br>"
                "Credit Limit: %{customdata[3]:,.1f} MB"
                "<extra></extra>"
            ),
        ))

    if not agg.empty:
        median_overdue = float(agg["TotalOverdue"].median())
        max_util       = float(agg["UtilizationPct"].max()) * 1.1
    else:
        median_overdue = 0.0
        max_util       = 120.0

    fig.add_vline(
        x=80,
        line_dash="dash", line_color=PALETTE["threshold"], line_width=1,
        annotation_text="80% Util",
        annotation_font=dict(size=8, color=PALETTE["threshold"]),
    )
    fig.add_hline(
        y=median_overdue,
        line_dash="dot", line_color="#aaaaaa", line_width=1,
        annotation_text="Median Overdue",
        annotation_font=dict(size=8, color="#777777"),
    )

    apply_base_layout(fig, {
        "height": 380,
        "margin": dict(l=0, r=20, t=30, b=10),
        "title": dict(
            text="Credit Health Matrix — Utilization % vs Net Overdue",
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title      = "Credit Utilization %",
            ticksuffix = "%",
            showgrid   = True, gridcolor=GRID_COLOR,
            color      = FONT_COLOR, tickfont=dict(size=9),
            range      = [0, max(120.0, max_util)],
        ),
        "yaxis": dict(
            title    = "Net Overdue (THB)",
            showgrid = True, gridcolor=GRID_COLOR,
            color    = FONT_COLOR, tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation = "v",
            yanchor="top", y=1,
            xanchor="left", x=1.01,
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#d0dae6", borderwidth=1,
        ),
        "showlegend": True,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_health_bubble")

# =============================================================================
# SECTION 2B — Risk Tier Donut
# =============================================================================
def _render_risk_tier_donut(df: pd.DataFrame):
    if "RiskTier" not in df.columns or "Customer" not in df.columns:
        st.info("Risk Tier data not available.")
        return

    tier_counts = (
        df.groupby("RiskTier")["Customer"]
        .nunique()
        .reindex(TIER_ORDER, fill_value=0)
        .reset_index()
    )
    tier_counts.columns = ["Tier", "Count"]
    tier_counts = tier_counts[tier_counts["Count"] > 0]

    if tier_counts.empty:
        st.info("No risk tier data.")
        return

    fig = go.Figure(go.Pie(
        labels   = tier_counts["Tier"].tolist(),
        values   = tier_counts["Count"].tolist(),
        marker   = dict(
            colors=[TIER_COLOR.get(t, PALETTE["nodata"]) for t in tier_counts["Tier"]],
            line=dict(color="white", width=2),
        ),
        hole        = 0.48,
        textinfo    = "label+percent",
        textfont    = dict(size=10),
        hovertemplate = "%{label}<br>Customers: %{value}<br>Share: %{percent}<extra></extra>",
        showlegend  = False,
    ))

    total_custs = int(tier_counts["Count"].sum())
    critical_n  = int(tier_counts.loc[tier_counts["Tier"] == "Critical", "Count"].sum())
    fig.add_annotation(
        text      = f"{critical_n}<br>Critical",
        x=0.5, y=0.5,
        font      = dict(size=14, color=PALETTE["crimson"]),
        showarrow = False,
    )

    fig.update_layout(
        height        = 380,
        margin        = dict(l=0, r=0, t=40, b=0),
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
        font          = dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
        title         = dict(
            text = f"Risk Tier Distribution — {total_custs:,} Customers",
            font = dict(size=10, color=FONT_COLOR), x=0,
        ),
    )
    st.plotly_chart(fig, use_container_width=True, key="chart_risk_donut")


# =============================================================================
# SECTION 3 — Watchlist Heatmap Table
# Columns: Customer | Util% | DPD | Overdue Amount | Risk Tier | Signal
# Sorted by RiskTier severity then OverdueAbs desc
# =============================================================================
def _render_watchlist(df: pd.DataFrame, top_n: int = 20):
    """
    Watchlist table — customers with highest combined risk signal.
    ใช้ _agg_customer_overdue() เป็น aggregate เพื่อให้ได้ net overdue
    (gross overdue หัก Credit Note) ที่ถูกต้อง
    """
    need = {"Customer", "UtilizationPct", "OverdueAmount", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("Watchlist requires joined data.")
        return

    agg = _agg_customer_overdue(df)

    if agg.empty:
        st.success("No overdue customers match the current filters.")
        return

    # เฉพาะ customer ที่ net overdue > 0 จริงๆ
    watchlist = agg[agg["NetOverdue"] > 0].copy()

    if watchlist.empty:
        st.success("No customers with net overdue > 0 after Credit Note offset.")
        return

    # Sort: Critical first → OverdueAbs desc
    tier_rank = {"Critical": 0, "High Risk": 1, "Watch": 2, "Healthy": 3, "Unknown": 4}
    watchlist["_rank"] = watchlist["RiskTier"].map(tier_rank).fillna(9)
    watchlist = (
        watchlist
        .sort_values(["_rank", "NetOverdue"], ascending=[True, False])
        .head(top_n)
        .reset_index(drop=True)
    )

    # Alert signal
    def _alert(row):
        tier = row["RiskTier"]
        dpd  = row.get("MaxDPD", 0) or 0
        util = row.get("UtilizationPct", 0) or 0
        if tier == "Critical":
            return "CRITICAL"
        elif tier == "High Risk" and dpd >= DPD_HIGH:
            return "HIGH DPD"
        elif tier == "High Risk" and util >= 80:
            return "HIGH UTIL"
        elif tier == "Watch":
            return "WATCH"
        else:
            return "MONITOR"

    watchlist["Alert"] = watchlist.apply(_alert, axis=1)

    # Rename columns สำหรับแสดงผล
    rename_map = {
        "NetOverdue":              "Net Overdue (THB)",
        "GrossOverdue":            "Gross Overdue (THB)",
        "CreditNoteOffset":        "Credit Note (THB)",
        "OverdueInvoices":         "Invoices",
        "MaxDPD":                  "Max DPD",
        "UtilizationPct":          "Util %",
        "RiskTier":                "Risk Tier",
        "CustomerName":            "Customer Name",
        "CLEAN_CREDIT_MB":         "Credit Limit (MB)",
        "CURRENT_DEBT_MILLION_THB":"Current Debt (MB)",
        "TYPE":                    "Type",
        "Alert":                   "Alert Signal",
    }

    display_order = [
        "Customer", "CustomerName",
        "TYPE", "UtilizationPct", "MaxDPD",
        "NetOverdue", "GrossOverdue", "CreditNoteOffset",
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "OverdueInvoices", "RiskTier", "Alert",
    ]
    show_cols = [c for c in display_order if c in watchlist.columns]
    tbl = watchlist[show_cols].rename(columns=rename_map)

    for col in ("Net Overdue (THB)", "Gross Overdue (THB)",
                "Credit Note (THB)", "Util %",
                "Credit Limit (MB)", "Current Debt (MB)"):
        if col in tbl.columns:
            tbl[col] = pd.to_numeric(tbl[col], errors="coerce")

    col_config = {
        "Customer":             st.column_config.NumberColumn("Cust. Code", width="small"),
        "Customer Name":        st.column_config.TextColumn("Customer Name", width="large"),
        "Type":                 st.column_config.TextColumn("Type", width="small"),
        "Util %":               st.column_config.NumberColumn("Util %", format="%.1f%%", width="small"),
        "Max DPD":              st.column_config.NumberColumn("Max DPD", format="%d days", width="small"),
        "Net Overdue (THB)":    st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f", width="medium"),
        "Gross Overdue (THB)":  st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f", width="medium"),
        "Credit Note (THB)":    st.column_config.NumberColumn("Credit Note (THB)", format="%,.0f", width="medium"),
        "Credit Limit (MB)":    st.column_config.NumberColumn("Credit Limit (MB)", format="%.1f", width="small"),
        "Current Debt (MB)":    st.column_config.NumberColumn("Current Debt (MB)", format="%.1f", width="small"),
        "Invoices":             st.column_config.NumberColumn("Invoices", width="small"),
        "Risk Tier":            st.column_config.TextColumn("Risk Tier", width="small"),
        "Alert Signal":         st.column_config.TextColumn("Alert Signal", width="medium"),
    }

    st.dataframe(
        tbl,
        use_container_width=True,
        height=380,
        hide_index=True,
        column_config=col_config,
    )
    m1, m2, m3, m4, m5 = st.columns(5, gap="small")

    n_critical = int((watchlist["RiskTier"] == "Critical").sum())
    n_highrisk = int((watchlist["RiskTier"] == "High Risk").sum())
    n_watch    = int((watchlist["RiskTier"] == "Watch").sum())
    total_net  = float(watchlist["NetOverdue"].sum())
    total_cn   = float(watchlist["CreditNoteOffset"].sum()) \
                 if "CreditNoteOffset" in watchlist.columns else 0.0

    card_items = [
        ("Critical",           f"{n_critical:,}",  PALETTE["crimson"]),
        ("High Risk",          f"{n_highrisk:,}",  PALETTE["amber"]),
        ("Watch",              f"{n_watch:,}",      PALETTE["amber_lt"]),
        ("Net Exposure (THB)", f"{total_net:,.0f}", PALETTE["jade"]),
        ("Credit Note Offset", f"{total_cn:,.0f}",  PALETTE["sapphire"]),
    ]

    cols = st.columns(5, gap="small")
    for col, (label, value, accent) in zip(cols, card_items):
        with col:
            st.markdown(
                f"<div style='"
                f"border:1px solid #c8d0da;"
                f"border-left:3px solid #2c3540"
                f"border-radius:6px;"
                f"padding:12px 14px;"
                f"background:#ffffff;"
                f"min-height:72px;"
                f"'>"
                f"<div style='"
                f"font-size:0.70rem;"
                f"font-weight:600;"
                f"color:#6b7685;"
                f"letter-spacing:0.05em;"
                f"text-transform:uppercase;"
                f"margin-bottom:6px;"
                f"'>{label}</div>"
                f"<div style='"
                f"font-size:1.05rem;"
                f"font-weight:700;"
                f"color:#2c3540;"
                f"line-height:1.4;"
                f"word-break:break-all;"
                f"'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# =============================================================================
# SECTION 4 — Collection Efficiency Trend (On-time vs Late vs Not Collected)
# =============================================================================
def _render_collection_pipeline(df_filtered: pd.DataFrame):
    df = df_filtered.copy()

    total_raw = len(df)

    with st.expander("Pipeline Debug Info", expanded=False):
        st.markdown(f"- Filtered rows: **{total_raw:,}**")
        st.markdown(f"- OverdueAmount > 0 (ยังไม่จ่าย): **{int((df['OverdueAmount'] > 0).sum()):,}**")
        st.markdown(f"- OverdueAmount = 0 (จ่ายแล้ว): **{int((df['OverdueAmount'] == 0).sum()):,}**")
        st.markdown(f"- OverdueAmount < 0 (Credit Note): **{int((df['OverdueAmount'] < 0).sum()):,}**")
        if "OriginalDueDate" in df.columns:
            n_ok = int(df["OriginalDueDate"].notna().sum())
            st.markdown(f"- OriginalDueDate parsed OK: **{n_ok:,}** | NaT: **{total_raw - n_ok:,}**")

    if "OriginalDueDate" not in df.columns:
        st.info("No invoice data available for pipeline.")
        return

    today      = pd.Timestamp("today").normalize()
    amount_col = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"

    paid_mask        = df["OverdueAmount"] == 0
    overdue_mask     = df["OverdueAmount"] > 0
    credit_note_mask = df["OverdueAmount"] < 0
    pastdue_mask     = overdue_mask & df["OriginalDueDate"].notna() & (df["OriginalDueDate"] < today)
    upcoming_mask    = overdue_mask & df["OriginalDueDate"].notna() & (df["OriginalDueDate"] >= today)

    amt_total       = float(df.loc[df["OverdueAmount"] >= 0, amount_col].sum())
    amt_paid        = float(df.loc[paid_mask,        amount_col].sum())
    amt_overdue     = float(df.loc[overdue_mask,     amount_col].sum())
    amt_pastdue     = float(df.loc[pastdue_mask,     amount_col].sum())
    amt_upcoming    = float(df.loc[upcoming_mask,    amount_col].sum())
    amt_credit_note = float(df.loc[credit_note_mask, "OverdueAmount"].abs().sum())

    cnt_paid        = int(paid_mask.sum())
    cnt_overdue     = int(overdue_mask.sum())
    cnt_pastdue     = int(pastdue_mask.sum())
    cnt_upcoming    = int(upcoming_mask.sum())
    cnt_credit_note = int(credit_note_mask.sum())
    cnt_total       = int((df["OverdueAmount"] >= 0).sum())

    col_kpis = st.columns(4, gap="small")
    kpi_data = [
        ("Total Invoices",      f"{amt_total:,.0f}",       f"{cnt_total:,} invoices",                   "info"),
        ("Paid",                f"{amt_paid:,.0f}",        f"{cnt_paid:,} invoices — OverdueAmount = 0", "safe"),
        ("Credit Note",         f"{amt_credit_note:,.0f}", f"{cnt_credit_note:,} invoices — Amt < 0",   "warning"),
        ("Net Overdue (Unpaid)",f"{amt_overdue:,.0f}",     f"{cnt_overdue:,} invoices — Amt > 0",        "danger" if amt_overdue > 0 else "safe"),
    ]
    for col, (lbl, val, sub, variant) in zip(col_kpis, kpi_data):
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, variant), unsafe_allow_html=True)

    st.markdown(
        "<div style='font-size:0.72rem;color:#8A9BB0;margin-top:6px;margin-bottom:12px'>"
        "Paid = OverdueAmount = 0 | Credit Note = OverdueAmount &lt; 0 | Net Overdue = OverdueAmount > 0"
        "</div>",
        unsafe_allow_html=True,
    )

    floor_pct = 0.03
    floor_val = amt_total * floor_pct

    def _floored(val: float) -> float:
        return max(val, floor_val) if val > 0 else 0.0

    paid_display        = _floored(amt_paid)
    overdue_display     = _floored(amt_overdue)
    credit_note_display = _floored(amt_credit_note)
    pastdue_display     = _floored(amt_pastdue)
    upcoming_display    = _floored(amt_upcoming)

    labels  = ["Invoice Total", "Paid", "Net Overdue", "Past Original Due", "Upcoming Due", "Credit Note"]
    parents = ["", "Invoice Total", "Invoice Total", "Net Overdue", "Net Overdue", "Invoice Total"]
    values  = [0, paid_display, overdue_display, pastdue_display, upcoming_display, credit_note_display]
    real_values = [
        amt_paid + amt_overdue + amt_credit_note,
        amt_paid, amt_overdue, amt_pastdue, amt_upcoming, amt_credit_note,
    ]
    counts = [
        cnt_paid + cnt_overdue + cnt_credit_note,
        cnt_paid, cnt_overdue, cnt_pastdue, cnt_upcoming, cnt_credit_note,
    ]
    colors = [
        PALETTE["sapphire"], PALETTE["jade_lt"], PALETTE["crimson_lt"],
        PALETTE["crimson"],  PALETTE["amber_lt"], PALETTE["amber"],
    ]
    pct_of_total = [
        100.0,
        (amt_paid / amt_total * 100)        if amt_total > 0 else 0.0,
        (amt_overdue / amt_total * 100)      if amt_total > 0 else 0.0,
        (amt_pastdue / amt_overdue * 100)    if amt_overdue > 0 else 0.0,
        (amt_upcoming / amt_overdue * 100)   if amt_overdue > 0 else 0.0,
        (amt_credit_note / amt_total * 100)  if amt_total > 0 else 0.0,
    ]

    customdata = list(zip(real_values, counts, pct_of_total))

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values, customdata=customdata,
        texttemplate=(
            "<b>%{label}</b><br>"
            "%{customdata[0]:,.0f} THB<br>"
            "%{customdata[2]:.1f}%"
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Amount  : %{customdata[0]:,.0f} THB<br>"
            "Invoices: %{customdata[1]:,}<br>"
            "Share   : %{customdata[2]:.1f}%"
            "<extra></extra>"
        ),
        marker=dict(colors=colors, line=dict(width=2, color="white")),
        textfont=dict(size=11, color="white", family="Inter, sans-serif"),
        tiling=dict(packing="squarify", pad=4),
    ))

    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
        title=dict(
            text=(
                "Collection Pipeline — Invoice Status Treemap<br>"
                "<sup style='font-size:9px;color:#8A9BB0'>"
                "Segment เล็กถูก scale ขึ้น 3% floor เพื่อให้มองเห็น — hover ดูตัวเลขจริง"
                "</sup>"
            ),
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
    )

    col_chart, col_info = st.columns([7, 3], gap="medium")

    with col_chart:
        st.plotly_chart(fig, use_container_width=True, key="chart_collection_pipeline")

    with col_info:
        paid_pct     = (amt_paid / amt_total * 100)        if amt_total > 0 else 0.0
        cn_pct       = (amt_credit_note / amt_total * 100)  if amt_total > 0 else 0.0
        ov_pct       = (amt_overdue / amt_total * 100)      if amt_total > 0 else 0.0
        past_pct     = (amt_pastdue / amt_overdue * 100)    if amt_overdue > 0 else 0.0
        upcoming_pct = (amt_upcoming / amt_overdue * 100)   if amt_overdue > 0 else 0.0

        st.markdown(
            "<div style='padding:12px 14px;background:#f7f9fc;"
            "border-radius:8px;border:1px solid #d0dae6'>"

            "<div style='font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px'>"
            "How to Read</div>"

            "<div style='font-size:0.73rem;color:#3D5166;margin-bottom:10px'>"
            "พื้นที่ = สัดส่วนของยอด<br>"
            "segment เล็กถูก scale ขึ้นเล็กน้อย<br>"
            "เพื่อให้มองเห็น — ดูตัวเลขจริงจาก hover</div>"

            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.73rem;color:#3D5166;margin-bottom:6px'>"
            "<b>Breakdown (ตัวเลขจริง)</b></div>"

            f"<div style='font-size:0.72rem;color:#1A7A4A;margin-bottom:4px'>"
            f"Paid<br>"
            f"{amt_paid:,.0f} THB ({paid_pct:.1f}%)<br>"
            f"{cnt_paid:,} invoices</div>"

            f"<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:2px'>"
            f"Net Overdue<br>"
            f"{amt_overdue:,.0f} THB ({ov_pct:.1f}%)<br>"
            f"{cnt_overdue:,} invoices</div>"

            f"<div style='font-size:0.72rem;color:#E8A838;margin-bottom:2px;padding-left:8px'>"
            f"— Upcoming Due (ยังไม่เกินกำหนด)<br>"
            f"&nbsp;&nbsp;{amt_upcoming:,.0f} THB ({upcoming_pct:.1f}%) | {cnt_upcoming:,} inv</div>"

            f"<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:6px;padding-left:8px'>"
            f"— Past Due (เกินกำหนดแล้ว)<br>"
            f"&nbsp;&nbsp;{amt_pastdue:,.0f} THB ({past_pct:.1f}%) | {cnt_pastdue:,} inv</div>"

            f"<div style='font-size:0.72rem;color:#B5620A;margin-bottom:10px'>"
            f"Credit Note<br>"
            f"{amt_credit_note:,.0f} THB ({cn_pct:.1f}%) | {cnt_credit_note:,} invoices</div>"

            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;color:#3D5166'>"
            "<b>Variables</b><br>"
            "OverdueAmount, OriginalDueDate,<br>"
            "InvoiceAmount"
            "</div>"

            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='font-size:0.72rem;color:#8A9BB0;margin-top:4px'>"
        "Treemap: พื้นที่สะท้อนสัดส่วนยอดเงิน | "
        "Credit Note และ segment เล็กถูก scale ขึ้น 3% floor เพื่อให้มองเห็น | "
        "hover เพื่อดูตัวเลขจริง"
        "</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# SECTION 6 — Raw Joined Table
# =============================================================================
def _render_joined_table(df: pd.DataFrame):
    display_cols_priority = [
        "Customer", "CustomerName", "CompanyCode", "TYPE",
        "UtilizationPct", "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "OverdueAbs", "DPD", "AgingBucket", "OriginalDueDate",
        "CollectionDate", "RiskTier",
    ]
    show_cols = [c for c in display_cols_priority if c in df.columns]
    tbl = df[show_cols].copy().reset_index(drop=True)

    col_config = {
        "Customer":                  st.column_config.NumberColumn("Cust. Code"),
        "CustomerName":              st.column_config.TextColumn("Customer Name", width="large"),
        "CompanyCode":               st.column_config.TextColumn("Company"),
        "TYPE":                      st.column_config.TextColumn("Type"),
        "UtilizationPct":            st.column_config.NumberColumn("Util %",   format="%.1f%%"),
        "CLEAN_CREDIT_MB":           st.column_config.NumberColumn("Credit (MB)", format="%.2f"),
        "CURRENT_DEBT_MILLION_THB":  st.column_config.NumberColumn("Debt (MB)",   format="%.2f"),
        "OverdueAbs":                st.column_config.NumberColumn("Overdue (THB)", format="%,.0f"),
        "DPD":                       st.column_config.NumberColumn("DPD", format="%d days"),
        "AgingBucket":               st.column_config.TextColumn("Aging Bucket"),
        "OriginalDueDate":           st.column_config.DateColumn("Due Date"),
        "CollectionDate":            st.column_config.DateColumn("Collected"),
        "RiskTier":                  st.column_config.TextColumn("Risk Tier"),
    }
    st.dataframe(tbl, use_container_width=True, height=400,
                 hide_index=True, column_config=col_config)


def _render_cash_inflow_forecast(df_filtered: pd.DataFrame):
    df = df_filtered.copy()

    with st.expander("Cash Inflow Debug Info", expanded=False):
        st.markdown(f"- Filtered rows: **{len(df):,}**")
        for dc in ("CollectionDate", "OriginalDueDate", "CustomerDueDate"):
            if dc in df.columns:
                n = int(df[dc].notna().sum())
                st.markdown(f"- {dc} not-null: **{n:,}**")
        amount_col_d = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"
        st.markdown(f"- Amount column: **{amount_col_d}**")

    amount_col = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"
    today      = pd.Timestamp("today").normalize()

    c1, c2 = st.columns([1, 1])
    with c1:
        horizon = st.selectbox(
            "Forecast Horizon",
            options=["7 days", "14 days", "30 days", "60 days", "90 days", "120 days"],
            index=2,
            key="cif_horizon",
            label_visibility="visible",
        )
    with c2:
        date_col_options = []
        date_col_labels  = []
        for dc, lbl in [
            ("CollectionDate",  "CollectionDate (planned extension)"),
            ("OriginalDueDate", "OriginalDueDate (original due)"),
            ("CustomerDueDate", "CustomerDueDate (customer confirm)"),
        ]:
            if dc in df.columns:
                date_col_options.append(dc)
                date_col_labels.append(lbl)

        selected_date_col = st.selectbox(
            "Based on",
            options=date_col_options,
            format_func=lambda x: dict(zip(date_col_options, date_col_labels)).get(x, x),
            index=0,
            key="cif_date_col",
            label_visibility="visible",
        )

    horizon_days = int(horizon.split()[0])
    cutoff = today + pd.Timedelta(days=horizon_days)

    if selected_date_col not in df.columns:
        st.info(f"{selected_date_col} not available.")
        return

    df_future = df[
        df[selected_date_col].notna()
        & (df[selected_date_col] >= today)
        & (df[selected_date_col] <= cutoff)
        & (df[amount_col] > 0)
    ].copy()

    if df_future.empty:
        st.info(
            f"No data for {selected_date_col} within next {horizon_days} days "
            f"(up to {cutoff.strftime('%d %b %Y')})."
        )
        return

    df_future["WeekNum"] = df_future[selected_date_col].apply(
        lambda d: int((d - today).days // 7) + 1 if pd.notna(d) else None
    )
    df_future["WeekStart"] = df_future[selected_date_col].apply(
        lambda d: today + pd.Timedelta(days=(int((d - today).days // 7)) * 7)
        if pd.notna(d) else pd.NaT
    )
    df_future["WeekEnd"]   = df_future["WeekStart"] + pd.Timedelta(days=6)
    df_future["WeekLabel"] = df_future["WeekNum"].apply(
        lambda w: f"Week {w}" if pd.notna(w) else "Unknown"
    )

    weekly = (
        df_future.groupby(["WeekNum", "WeekStart", "WeekEnd", "WeekLabel"])
        .agg(Amount=(amount_col, "sum"), Invoices=(amount_col, "count"))
        .reset_index()
        .sort_values("WeekNum")
    )

    if weekly.empty:
        st.info("No weekly data.")
        return

    total_forecast = float(weekly["Amount"].sum())
    peak_week      = weekly.loc[weekly["Amount"].idxmax(), "WeekLabel"]
    trough_week    = weekly.loc[weekly["Amount"].idxmin(), "WeekLabel"]

    k1, k2, k3 = st.columns(3, gap="small")
    for col, lbl, val, sub, variant in [
        (k1, "Total Planned Inflow", f"{total_forecast:,.0f}", f"Next {horizon_days} days — Invoice Amount (THB)", "info"),
        (k2, "Peak Week",             peak_week,               "Highest planned inflow",                           "safe"),
        (k3, "Trough Week",           trough_week,             "Lowest planned inflow",                            "warning"),
    ]:
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, variant), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    weekly["MonthYear"] = weekly["WeekStart"].dt.strftime("%b %Y")
    weekly["WeekIdx"]   = range(len(weekly))

    month_bands   = []
    current_month = None
    band_start    = 0
    for _, row in weekly.iterrows():
        m = row["MonthYear"]
        i = row["WeekIdx"]
        if m != current_month:
            if current_month is not None:
                month_bands.append({"month": current_month, "start": band_start, "end": i - 1})
            current_month = m
            band_start    = i
    if current_month is not None:
        month_bands.append({"month": current_month, "start": band_start, "end": len(weekly) - 1})

    x_labels        = weekly["WeekLabel"].tolist()
    band_colors_alt = ["rgba(27,79,138,0.07)", "rgba(27,79,138,0.02)"]

    fig = go.Figure()

    for i, band in enumerate(month_bands):
        x0 = x_labels[band["start"]]
        x1 = x_labels[band["end"]]
        fig.add_vrect(x0=x0, x1=x1, fillcolor=band_colors_alt[i % 2], line_width=0, layer="below")
        mid_label = x_labels[(band["start"] + band["end"]) // 2]
        fig.add_annotation(
            x=mid_label, y=1.02, yref="paper",
            text=f"<b>{band['month']}</b>",
            showarrow=False,
            font=dict(size=8, color="#5a6a7a"),
            xanchor="center", yanchor="bottom",
        )

    fig.add_trace(go.Scatter(
        x=x_labels, y=weekly["Amount"].tolist(),
        mode="none", fill="tozeroy",
        fillcolor="rgba(58,123,213,0.07)",
        showlegend=False, hoverinfo="skip",
    ))

    avg_val = float(weekly["Amount"].mean())
    point_colors = [
        PALETTE["jade_lt"] if v >= avg_val else PALETTE["sapphire_lt"]
        for v in weekly["Amount"]
    ]
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=weekly["Amount"].tolist(),
        mode="lines+markers",
        name="Planned Cash Inflow",
        line=dict(color=PALETTE["sapphire_lt"], width=2.5, shape="spline", smoothing=0.7),
        marker=dict(size=8, color=point_colors, line=dict(color="white", width=2)),
        customdata=list(zip(
            weekly["Amount"].tolist(),
            weekly["Invoices"].tolist(),
            weekly["WeekStart"].dt.strftime("%d %b %Y").tolist(),
            weekly["WeekEnd"].dt.strftime("%d %b %Y").tolist(),
            weekly["MonthYear"].tolist(),
        )),
        hovertemplate=(
            "<b>%{x}</b> — %{customdata[4]}<br>"
            "%{customdata[2]} to %{customdata[3]}<br>"
            "Planned Inflow : %{customdata[0]:,.0f} THB<br>"
            "Invoices       : %{customdata[1]:,}"
            "<extra></extra>"
        ),
    ))

    fig.add_hline(
        y=avg_val,
        line_dash="dot", line_color="#cccccc", line_width=1,
        annotation_text=f"Avg {avg_val:,.0f}",
        annotation_font=dict(size=8, color="#999999"),
        annotation_position="bottom right",
    )

    apply_base_layout(fig, {
        "height": 400,
        "margin": dict(l=0, r=20, t=50, b=20),
        "title": dict(
            text=(
                f"Cash Inflow Planning — Invoice Amount (THB) | "
                f"Next {horizon_days} days "
                f"({today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')})"
            ),
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            showgrid=False, color=FONT_COLOR,
            tickfont=dict(size=9), tickangle=-35,
            type="category",
        ),
        "yaxis": dict(
            title="Invoice Amount (THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            rangemode="tozero",
        ),
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_cash_inflow")

    st.markdown(
        f"<div style='font-size:0.75rem;color:#8A9BB0;margin-top:2px'>"
        f"Based on {selected_date_col} | "
        f"Amount = Invoice Amount | "
        f"Horizon: {today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')}"
        f"</div>",
        unsafe_allow_html=True,
    )

def _render_future_collection_forecast(df_overdue: pd.DataFrame):
    df = df_overdue.copy()

    with st.expander("Collection Planning Debug Info", expanded=False):
        st.markdown(f"- Rows after CompanyCode filter: **{len(df):,}**")
        st.markdown(f"- OverdueAmount > 0: **{int((df['OverdueAmount'] > 0).sum()):,}** rows")
        for dc in ("CollectionDate", "OriginalDueDate", "CustomerDueDate"):
            if dc in df.columns:
                n = int(df[dc].notna().sum())
                st.markdown(f"- {dc} not-null: **{n:,}**")

    if "OverdueAmount" not in df.columns:
        st.info("OverdueAmount not found.")
        return

    today = pd.Timestamp("today").normalize()

    c1, c2 = st.columns([1, 1])
    with c1:
        horizon = st.selectbox(
            "Horizon (days)",
            options=["7", "14", "30", "60", "90", "120"],
            index=2,
            key="fcf_horizon",
            label_visibility="visible",
        )
    with c2:
        date_col_options = []
        date_col_labels  = []
        for dc, lbl in [
            ("CollectionDate",  "CollectionDate (planned extension)"),
            ("OriginalDueDate", "OriginalDueDate (original due)"),
            ("CustomerDueDate", "CustomerDueDate (customer confirm)"),
        ]:
            if dc in df.columns:
                date_col_options.append(dc)
                date_col_labels.append(lbl)

        selected_date_col = st.selectbox(
            "Based on",
            options=date_col_options,
            format_func=lambda x: dict(zip(date_col_options, date_col_labels)).get(x, x),
            index=0,
            key="fcf_date_col",
            label_visibility="visible",
        )

    horizon_days = int(horizon)
    cutoff = today + pd.Timedelta(days=horizon_days)

    if selected_date_col not in df.columns:
        st.info(f"{selected_date_col} not available.")
        return

    df_plan = df[
        df[selected_date_col].notna()
        & (df[selected_date_col] >= today)
        & (df[selected_date_col] <= cutoff)
        & (df["OverdueAmount"] > 0)
    ].copy()

    if df_plan.empty:
        st.info(
            f"No unpaid invoices (OverdueAmount > 0) with {selected_date_col} "
            f"within next {horizon_days} days "
            f"(up to {cutoff.strftime('%d %b %Y')})."
        )
        return

    daily = (
        df_plan.groupby(selected_date_col)
        .agg(Amount=("OverdueAmount", "sum"), Invoices=("OverdueAmount", "count"))
        .reset_index()
        .sort_values(selected_date_col)
    )
    daily["Cumulative"] = daily["Amount"].cumsum()

    def _sum_horizon(d):
        return float(daily[daily[selected_date_col] <= today + pd.Timedelta(days=d)]["Amount"].sum())

    next7  = _sum_horizon(7)
    next14 = _sum_horizon(14)
    next30 = _sum_horizon(30)
    total  = float(daily["Amount"].sum())

    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, lbl, val, sub in [
        (k1, "Next 7 Days",         f"{next7:,.0f}",  "Overdue Amount (THB)"),
        (k2, "Next 14 Days",        f"{next14:,.0f}", "Overdue Amount (THB)"),
        (k3, "Next 30 Days",        f"{next30:,.0f}", "Overdue Amount (THB)"),
        (k4, f"Total ({horizon}d)", f"{total:,.0f}",  "Overdue Amount (THB)"),
    ]:
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, "info"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily[selected_date_col].dt.strftime("%b %d").tolist(),
        y=daily["Amount"].tolist(),
        name="Daily Overdue Amount",
        marker_color=PALETTE["sapphire_lt"],
        opacity=0.6,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Planned Collect : %{y:,.0f} THB<br>"
            "<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=daily[selected_date_col].dt.strftime("%b %d").tolist(),
        y=daily["Cumulative"].tolist(),
        name="Cumulative",
        mode="lines+markers",
        yaxis="y2",
        line=dict(color=PALETTE["jade_lt"], width=2),
        marker=dict(size=5, color=PALETTE["jade_lt"]),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Cumulative : %{y:,.0f} THB"
            "<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=60, t=30, b=10),
        "barmode": "overlay",
        "title": dict(
            text=(
                f"Collection Planning — Overdue Amount (THB) | "
                f"Next {horizon_days} days "
                f"({today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')})"
            ),
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            showgrid=False, color=FONT_COLOR,
            tickangle=-35, tickfont=dict(size=8),
        ),
        "yaxis": dict(
            title="Overdue Amount (THB) — Daily",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "yaxis2": dict(
            title="Cumulative (THB)",
            overlaying="y", side="right",
            showgrid=False,
            color=PALETTE["jade_lt"], tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=9),
        ),
        "showlegend": True,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_future_forecast")

    st.markdown(
        f"<div style='font-size:0.75rem;color:#8A9BB0;margin-top:2px'>"
        f"Based on {selected_date_col} (planned extension) | "
        f"Only unpaid invoices (OverdueAmount > 0) | "
        f"Horizon: {today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_credit_planner_board(df: pd.DataFrame):
    if df.empty:
        st.info("No data for action board.")
        return

    today      = pd.Timestamp("today").normalize()
    today_str  = today.strftime("%d %b %Y")
    due_min    = df["OriginalDueDate"].min()
    due_max    = df["OriginalDueDate"].max()
    due_range  = ""
    if pd.notna(due_min) and pd.notna(due_max):
        due_range = f"{due_min.strftime('%d %b %Y')} — {due_max.strftime('%d %b %Y')}"

    st.markdown(
        f"<div style='display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap'>"
        f"<div style='font-size:0.78rem;color:#3D5166'>"
        f"<span style='font-weight:600;color:#1B4F8A'>As of</span> {today_str}</div>"
        f"<div style='font-size:0.78rem;color:#3D5166'>"
        f"<span style='font-weight:600;color:#1B4F8A'>Invoice Due Range</span> {due_range}</div>"
        f"<div style='font-size:0.78rem;color:#3D5166'>"
        f"<span style='font-weight:600;color:#1B4F8A'>Data Snapshot</span> "
        f"OriginalDueDate {due_range}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    cust_agg = _agg_customer_overdue(df)
    if cust_agg.empty:
        st.info("No overdue data for action board.")
        return

    has_customer_due = "CustomerDueDate" in df.columns
    has_original_due = "OriginalDueDate" in df.columns

    if has_customer_due and has_original_due:
        ext_df = df[df["OverdueAmount"] > 0].copy()
        ext_df["_ExtDays"] = (
            (ext_df["CustomerDueDate"] - ext_df["OriginalDueDate"])
            .dt.days.fillna(0).clip(lower=0)
        )
        ext_agg = (
            ext_df.groupby("Customer")["_ExtDays"]
            .max().reset_index()
        )
        ext_agg.columns = ["Customer", "MaxExtension"]
        cust_agg = cust_agg.merge(ext_agg, on="Customer", how="left")
        cust_agg["MaxExtension"] = cust_agg["MaxExtension"].fillna(0)
    else:
        cust_agg["MaxExtension"] = 0

    CALL_THRESHOLD        = 5_000_000
    REVIEW_UTIL_THRESHOLD = 90.0
    ESCALATE_EXT_DAYS     = 30

    cust_agg["Action_Review"]   = cust_agg["NetOverdue"] > CALL_THRESHOLD
    cust_agg["Action_CreditRv"] = cust_agg["UtilizationPct"] > REVIEW_UTIL_THRESHOLD
    cust_agg["Action_Escalate"] = cust_agg["MaxExtension"] > ESCALATE_EXT_DAYS

    n_review   = int(cust_agg["Action_Review"].sum())
    n_creditrv = int(cust_agg["Action_CreditRv"].sum())

    st.markdown(
        f"<div style='font-size:0.78rem;color:#3D5166;margin-bottom:12px'>"
        f"Rules: Overdue > {CALL_THRESHOLD/1e6:.0f}M THB = Review Customer | "
        f"Utilization > {REVIEW_UTIL_THRESHOLD:.0f}% = Review Credit Limit | "
        f"Extension > {ESCALATE_EXT_DAYS} days = Escalate"
        f"</div>",
        unsafe_allow_html=True,
    )

    k1, k2 = st.columns(2, gap="small")
    for col, lbl, val, sub, variant in [
        (k1, "Review Customer",     f"{n_review:,}",   f"Overdue > {CALL_THRESHOLD/1e6:.0f}M THB",    "danger"),
        (k2, "Review Credit Limit", f"{n_creditrv:,}", f"Utilization > {REVIEW_UTIL_THRESHOLD:.0f}%", "warning"),
    ]:
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, variant), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    label_col = "CustomerName" if "CustomerName" in cust_agg.columns else "Customer"

    action_tabs = st.tabs(["Review Customer", "Review Credit Limit"])

    # --- Tab 1: Review Customer ---
    with action_tabs[0]:
        tbl_review = (
            cust_agg[cust_agg["Action_Review"]]
            [["Customer", label_col, "NetOverdue", "GrossOverdue",
              "UtilizationPct", "MaxDPD", "MaxExtension"]]
            .sort_values("NetOverdue", ascending=False)
            .reset_index(drop=True)
        )

        # InvoiceDocument breakdown per customer
        if "InvoiceDocument" in df.columns:
            inv_breakdown = (
                df[df["OverdueAmount"] > 0]
                .groupby(["Customer", "InvoiceDocument"])["OverdueAmount"]
                .sum()
                .reset_index()
                .rename(columns={"OverdueAmount": "InvAmount"})
            )
            inv_summary = (
                inv_breakdown.groupby("Customer")
                .apply(lambda x: ", ".join(
                    f"{int(row['InvoiceDocument'])}:{row['InvAmount']:,.0f}"
                    for _, row in x.sort_values("InvAmount", ascending=False).head(3).iterrows()
                ))
                .reset_index()
                .rename(columns={0: "Top Invoices"})
            )
            tbl_review = tbl_review.merge(inv_summary, on="Customer", how="left")

        st.dataframe(
            tbl_review,
            use_container_width=True, height=320, hide_index=True,
            column_config={
                "Customer":       st.column_config.NumberColumn("Cust. Code", width="small"),
                label_col:        st.column_config.TextColumn("Customer Name", width="large"),
                "NetOverdue":     st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                "GrossOverdue":   st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f"),
                "UtilizationPct": st.column_config.NumberColumn("Util %", format="%.1f%%"),
                "MaxDPD":         st.column_config.NumberColumn("Max DPD", format="%d days"),
                "MaxExtension":   st.column_config.NumberColumn("Max Extension (days)", format="%d days"),
                "Top Invoices":   st.column_config.TextColumn("Top 3 Invoices (InvDoc:THB)", width="large"),
            },
        )

        st.markdown(
            "<div style='font-size:0.72rem;color:#8A9BB0;margin-top:4px'>"
            "Net Overdue = Gross Overdue - Credit Note offset | "
            "Top Invoices แสดง InvoiceDocument:Amount สูงสุด 3 อันดับต่อ customer"
            "</div>",
            unsafe_allow_html=True,
        )

    # --- Tab 2: Review Credit Limit ---
    with action_tabs[1]:
        tbl_creditrv = (
            cust_agg[cust_agg["Action_CreditRv"]]
            [["Customer", label_col, "UtilizationPct", "NetOverdue",
              "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB", "MaxExtension"]]
            .sort_values("UtilizationPct", ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(
            tbl_creditrv,
            use_container_width=True, height=320, hide_index=True,
            column_config={
                "Customer":                 st.column_config.NumberColumn("Cust. Code", width="small"),
                label_col:                  st.column_config.TextColumn("Customer Name", width="large"),
                "UtilizationPct":           st.column_config.NumberColumn("Util %", format="%.1f%%"),
                "NetOverdue":               st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                "CLEAN_CREDIT_MB":          st.column_config.NumberColumn("Credit Limit (MB)", format="%.1f"),
                "CURRENT_DEBT_MILLION_THB": st.column_config.NumberColumn("Current Debt (MB)", format="%.1f"),
                "MaxExtension":             st.column_config.NumberColumn("Max Extension (days)", format="%d days"),
            },
        )


def _render_credit_journey_sankey(df_filtered: pd.DataFrame):
    df = df_filtered.copy()

    total_raw = len(df)
    df        = df[df["OverdueAmount"] >= 0].copy()
    total_inv = len(df)

    with st.expander("Sankey Debug Info", expanded=False):
        st.markdown(f"- Filtered rows: **{total_raw:,}**")
        st.markdown(f"- Invoice rows (OverdueAmount >= 0): **{total_inv:,}**")
        st.markdown(f"- Paid (OverdueAmount = 0): **{int((df['OverdueAmount'] == 0).sum()):,}**")
        st.markdown(f"- Unpaid (OverdueAmount > 0): **{int((df['OverdueAmount'] > 0).sum()):,}**")
        if "CustomerDueDate" in df.columns:
            st.markdown(f"- CustomerDueDate not-null: **{int(df['CustomerDueDate'].notna().sum()):,}**")
        if "CollectionDate" in df.columns:
            st.markdown(f"- CollectionDate not-null: **{int(df['CollectionDate'].notna().sum()):,}**")
        amount_col_debug = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"
        st.markdown(f"- Amount column: **{amount_col_debug}**")

    if "OriginalDueDate" not in df.columns:
        st.info("OriginalDueDate not found.")
        return
    if df.empty:
        st.info("No invoice rows for selected filters.")
        return

    has_customer_due = "CustomerDueDate" in df.columns
    has_collection   = "CollectionDate" in df.columns
    amount_col       = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"

    if has_customer_due:
        df["_ExtDays"] = (
            (df["CustomerDueDate"] - df["OriginalDueDate"])
            .dt.days.fillna(0).clip(lower=0)
        )
        n_ext_valid = int(df["CustomerDueDate"].notna().sum())
        if n_ext_valid == 0:
            st.warning(
                "CustomerDueDate not available for any row — "
                "all invoices assigned to Ext 0-7d."
            )
    else:
        df["_ExtDays"] = 0
        st.warning("CustomerDueDate not available — all invoices assigned to Ext 0-7d.")

    def _ext_bucket(d):
        if d <= 7:    return "Ext 0-7d"
        elif d <= 30: return "Ext 8-30d"
        else:         return "Ext 30+d"

    LARGE_OVERDUE_THB = 1_000_000

    def _outcome(row):
        if row["OverdueAmount"] == 0:
            if has_customer_due and pd.notna(row.get("CustomerDueDate")) and pd.notna(row.get("OriginalDueDate")):
                if row["CustomerDueDate"] <= row["OriginalDueDate"]:
                    return "Paid On-Time"
                else:
                    return "Paid with Extension"
            return "Paid On-Time"
        if row[amount_col] >= LARGE_OVERDUE_THB:
            return "Overdue (Large)"
        return "Overdue (Small)"

    df["_ExtBucket"] = df["_ExtDays"].apply(_ext_bucket)
    df["_Outcome"]   = df.apply(_outcome, axis=1)

    flow = (
        df.groupby(["_ExtBucket", "_Outcome"])[amount_col]
        .sum()
        .reset_index()
        .rename(columns={amount_col: "Amount"})
    )
    flow = flow[flow["Amount"] > 0]

    if flow.empty:
        st.info("No flow data to display.")
        return

    unique_outcomes = flow["_Outcome"].unique().tolist()
    if len(unique_outcomes) == 1:
        st.info(
            f"All invoices have a single outcome: '{unique_outcomes[0]}'. "
            "Sankey displays current data distribution."
        )

    source_nodes = ["Ext 0-7d", "Ext 8-30d", "Ext 30+d"]
    target_nodes = ["Paid On-Time", "Paid with Extension", "Overdue (Large)", "Overdue (Small)"]
    all_nodes    = source_nodes + target_nodes
    node_idx     = {n: i for i, n in enumerate(all_nodes)}

    node_colors = [
        PALETTE["jade_lt"], PALETTE["amber"], PALETTE["crimson"],
        PALETTE["sapphire_lt"], PALETTE["amber_lt"], PALETTE["crimson"], PALETTE["nodata"],
    ]

    outcome_color_map = {
        "Paid On-Time":        "rgba(42,157,143,0.35)",
        "Paid with Extension": "rgba(232,168,56,0.35)",
        "Overdue (Large)":     "rgba(160,31,45,0.35)",
        "Overdue (Small)":     "rgba(138,155,176,0.35)",
    }

    sources, targets, values, link_colors = [], [], [], []
    for _, row in flow.iterrows():
        s = row["_ExtBucket"]
        t = row["_Outcome"]
        if s not in node_idx or t not in node_idx:
            continue
        sources.append(node_idx[s])
        targets.append(node_idx[t])
        values.append(float(row["Amount"]))
        link_colors.append(outcome_color_map.get(t, "rgba(100,100,100,0.2)"))

    if not sources:
        st.info("No valid flow combinations to render Sankey.")
        return

    col_chart, col_info = st.columns([7, 3], gap="medium")

    with col_chart:
        fig = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18, thickness=22,
                line=dict(color="#d0dae6", width=0.5),
                label=all_nodes,
                color=node_colors[:len(all_nodes)],
                hovertemplate="%{label}<br>Total: %{value:,.0f} THB<extra></extra>",
            ),
            link=dict(
                source=sources, target=targets, value=values, color=link_colors,
                hovertemplate=(
                    "%{source.label} → %{target.label}<br>"
                    "Amount: %{value:,.0f} THB<extra></extra>"
                ),
            ),
        ))
        fig.update_traces(
            textfont=dict(size=12, color="#1B2A3B", family="Inter, sans-serif")
        )
        fig.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1B2A3B", family="Inter, sans-serif", size=12),
            title=dict(
                text="Credit Journey — Extension Bucket → Payment Outcome",
                font=dict(size=10, color=FONT_COLOR), x=0,
            ),
        )
        st.plotly_chart(fig, use_container_width=True, key="chart_sankey")

    with col_info:
        total_paid   = float(df.loc[df["OverdueAmount"] == 0, amount_col].sum())
        total_unpaid = float(df.loc[df["OverdueAmount"] > 0,  amount_col].sum())
        total_all    = total_paid + total_unpaid
        paid_pct     = (total_paid / total_all * 100)   if total_all > 0 else 0.0
        unpaid_pct   = (total_unpaid / total_all * 100) if total_all > 0 else 0.0
        n_ext_invoices = int((df["_ExtDays"] > 0).sum())
        avg_ext        = float(df.loc[df["_ExtDays"] > 0, "_ExtDays"].mean()) if n_ext_invoices > 0 else 0.0
        max_ext        = float(df["_ExtDays"].max())

        st.markdown(
            "<div style='padding:12px 14px;background:#f7f9fc;"
            "border-radius:8px;border:1px solid #d0dae6'>"

            "<div style='font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px'>"
            "How to Read</div>"

            "<div style='font-size:0.74rem;color:#3D5166;margin-bottom:10px'>"
            "<b>ExtDays</b> = CustomerDueDate &minus; OriginalDueDate<br>"
            "จำนวนวันที่ลูกค้าขอขยายจากวันครบกำหนดเดิม</div>"

            "<div style='font-size:0.73rem;font-weight:600;color:#3D5166;margin-bottom:4px'>"
            "Extension Buckets (Left)</div>"
            "<div style='font-size:0.72rem;color:#3D5166;margin-bottom:2px'>"
            "Ext 0-7d &nbsp;— ขยาย 0-7 วัน</div>"
            "<div style='font-size:0.72rem;color:#3D5166;margin-bottom:2px'>"
            "Ext 8-30d — ขยาย 8-30 วัน</div>"
            "<div style='font-size:0.72rem;color:#3D5166;margin-bottom:10px'>"
            "Ext 30+d &nbsp;— ขยายมากกว่า 30 วัน</div>"

            "<div style='font-size:0.73rem;font-weight:600;color:#3D5166;margin-bottom:4px'>"
            "Outcomes (Right)</div>"
            "<div style='font-size:0.72rem;color:#1A7A4A;margin-bottom:2px'>"
            "Paid On-Time — จ่ายแล้ว (OverdueAmt=0) ไม่ขยาย</div>"
            "<div style='font-size:0.72rem;color:#B5620A;margin-bottom:2px'>"
            "Paid with Extension — จ่ายแล้ว แต่ขยายวัน</div>"
            "<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:2px'>"
            f"Overdue (Large) — ยังค้าง ≥ {LARGE_OVERDUE_THB/1e6:.0f}M THB</div>"
            "<div style='font-size:0.72rem;color:#8A9BB0;margin-bottom:10px'>"
            f"Overdue (Small) — ยังค้าง < {LARGE_OVERDUE_THB/1e6:.0f}M THB</div>"

            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;color:#3D5166;margin-bottom:8px'>"
            "<b>Summary</b></div>"
            f"<div style='font-size:0.72rem;color:#1A7A4A;margin-bottom:2px'>"
            f"Paid &nbsp;&nbsp;&nbsp;: {total_paid:,.0f} THB ({paid_pct:.1f}%)</div>"
            f"<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:2px'>"
            f"Unpaid : {total_unpaid:,.0f} THB ({unpaid_pct:.1f}%)</div>"
            f"<div style='font-size:0.72rem;color:#3D5166;margin-bottom:2px'>"
            f"Invoices with Extension: {n_ext_invoices:,}</div>"
            f"<div style='font-size:0.72rem;color:#3D5166;margin-bottom:8px'>"
            f"Avg Ext: {avg_ext:.1f}d | Max Ext: {max_ext:.0f}d</div>"

            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;color:#3D5166'>"
            "<b>Key Question</b><br>"
            "การขยายวัน (Extension) ช่วยให้ลูกค้าจ่ายได้จริงหรือไม่?<br><br>"
            "<b>Variables</b><br>"
            "CustomerDueDate, OriginalDueDate,<br>"
            "CollectionDate, OverdueAmount"
            "</div>"

            "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Flow Detail Table", expanded=False):
        flow_disp = flow.rename(columns={
            "_ExtBucket": "Extension Bucket",
            "_Outcome":   "Outcome",
            "Amount":     "Amount (THB)",
        })
        flow_disp["Amount (THB)"] = flow_disp["Amount (THB)"].round(0)
        flow_disp = flow_disp.sort_values("Amount (THB)", ascending=False).reset_index(drop=True)
        st.dataframe(
            flow_disp, use_container_width=True, hide_index=True,
            column_config={
                "Extension Bucket": st.column_config.TextColumn("Extension Bucket"),
                "Outcome":          st.column_config.TextColumn("Outcome"),
                "Amount (THB)":     st.column_config.NumberColumn("Amount (THB)", format="%,.0f"),
            },
        )

# =============================================================================
# Utility
# =============================================================================
def _no_data_banner():
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
        <h3 style="color:#1B4F8A;">No Data Available</h3>
        <p style="color:#5a6a7a;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
        </p>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# EDA Logging for Debug
# =============================================================================
import logging
import os

def _setup_credit_moni_logger() -> logging.Logger:
    logger = logging.getLogger("credit_moni")
    if logger.handlers:
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("credit_moni.log", mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    return logger

def _log_collection_pipeline(logger: logging.Logger, df_overdue: pd.DataFrame, selected_company: str):
    logger.info("=" * 70)
    logger.info("SECTION: Collection Pipeline")
    logger.info("=" * 70)

    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]
        logger.info(f"CompanyCode filter: {selected_company} → {len(df)} rows")
    else:
        logger.warning("CompanyCode column not found — no company filter applied")

    df = df[df["OverdueAmount"] > 0].copy()
    logger.info(f"After OverdueAmount > 0 filter: {len(df)} rows")

    if df.empty:
        logger.warning("No invoice rows — pipeline logging skipped")
        return

    today = pd.Timestamp("today").normalize()
    logger.info(f"Today reference: {today.date()}")

    has_customer_due = "CustomerDueDate" in df.columns
    has_collection   = "CollectionDate" in df.columns
    has_invoice_amt  = "InvoiceAmount" in df.columns
    logger.info(f"CustomerDueDate present : {has_customer_due}")
    logger.info(f"CollectionDate present  : {has_collection}")
    logger.info(f"InvoiceAmount present   : {has_invoice_amt}")

    amount_col = "InvoiceAmount" if has_invoice_amt else "OverdueAmount"
    logger.info(f"Amount column used: {amount_col}")

    # --- OriginalDueDate — อ่านจาก datetime ที่ prepare แล้ว ---
    if "OriginalDueDate" in df.columns:
        n_total      = len(df)
        n_parsed_ok  = int(df["OriginalDueDate"].notna().sum())
        n_parse_fail = n_total - n_parsed_ok
        logger.info(f"OriginalDueDate — total: {n_total} | parsed OK: {n_parsed_ok} | failed: {n_parse_fail}")
        if n_parse_fail > 0:
            logger.warning(f"  {n_parse_fail} rows have NaT OriginalDueDate — excluded from pipeline buckets")
    else:
        logger.error("OriginalDueDate column NOT found")
        return

    # --- CollectionDate ---
    if has_collection:
        n_coll_ok   = int(df["CollectionDate"].notna().sum())
        n_coll_null = len(df) - n_coll_ok
        logger.info(f"CollectionDate — not-null: {n_coll_ok} | null: {n_coll_null}")
        paid_mask = df["CollectionDate"].notna()
    else:
        paid_mask = pd.Series(False, index=df.index)
        logger.warning("CollectionDate not present — all rows treated as unpaid")

    upcoming_mask = (~paid_mask) & (df["OriginalDueDate"] >= today)
    overdue_mask  = (~paid_mask) & (df["OriginalDueDate"] < today)

    amt_upcoming = float(df.loc[upcoming_mask, amount_col].sum())
    amt_overdue  = float(df.loc[overdue_mask,  amount_col].sum())
    amt_paid     = float(df.loc[paid_mask,     amount_col].sum())
    cnt_upcoming = int(upcoming_mask.sum())
    cnt_overdue  = int(overdue_mask.sum())
    cnt_paid     = int(paid_mask.sum())

    logger.info(f"Pipeline buckets:")
    logger.info(f"  Upcoming (due >= today, unpaid) : {cnt_upcoming:>6} invoices | {amt_upcoming:>18,.2f} THB")
    logger.info(f"  Overdue  (due < today,  unpaid) : {cnt_overdue:>6} invoices | {amt_overdue:>18,.2f} THB")
    logger.info(f"  Paid (CollectionDate notna)     : {cnt_paid:>6} invoices | {amt_paid:>18,.2f} THB")

    # --- CustomerDueDate — อ่านจาก datetime ที่ prepare แล้ว ไม่ parse ซ้ำ ---
    if has_customer_due:
        n_cust_ok  = int(df["CustomerDueDate"].notna().sum())
        n_cust_nat = len(df) - n_cust_ok
        logger.info(f"CustomerDueDate — parsed OK: {n_cust_ok} | failed: {n_cust_nat}")

        if n_cust_ok > 0:
            logger.info(f"  CustomerDueDate range: {df['CustomerDueDate'].min()} → {df['CustomerDueDate'].max()}")
            ext_mask = (
                (~paid_mask)
                & df["CustomerDueDate"].notna()
                & df["OriginalDueDate"].notna()
                & (df["CustomerDueDate"] > df["OriginalDueDate"])
            )
            amt_extended = float(df.loc[ext_mask, amount_col].sum())
            cnt_extended = int(ext_mask.sum())
            logger.info(f"  Extended (CustomerDue > OriginalDue, unpaid): {cnt_extended:>6} invoices | {amt_extended:>18,.2f} THB")

            ext_days = (df["CustomerDueDate"] - df["OriginalDueDate"]).dt.days
            ext_pos  = ext_days[ext_days > 0]
            if not ext_pos.empty:
                logger.info(f"  ExtensionDays (>0) — min: {ext_pos.min():.0f} | mean: {ext_pos.mean():.1f} | max: {ext_pos.max():.0f} | count: {len(ext_pos)}")
        else:
            logger.warning("  CustomerDueDate all NaT in invoice rows — Extension analysis unavailable")
    else:
        logger.warning("CustomerDueDate not present — Extension bucket will show 0")

    # --- Bottleneck ---
    amt_extended_val = amt_extended if has_customer_due and n_cust_ok > 0 else 0.0
    bottleneck_label = "Overdue" if amt_overdue >= amt_extended_val else "Extended"
    logger.info(f"Bottleneck identified: {bottleneck_label}")

    # --- Amount sanity ---
    logger.info(f"{amount_col} stats — min: {df[amount_col].min():,.2f} | mean: {df[amount_col].mean():,.2f} | max: {df[amount_col].max():,.2f}")
    n_zero_amt = int((df[amount_col] == 0).sum())
    n_neg_amt  = int((df[amount_col] < 0).sum())
    logger.info(f"{amount_col} zero values: {n_zero_amt} | negative values: {n_neg_amt}")

def _log_cash_inflow_forecast(logger: logging.Logger, df_overdue: pd.DataFrame, selected_company: str):
    logger.info("=" * 70)
    logger.info("SECTION: Future Cash Inflow Forecast")
    logger.info("=" * 70)

    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]
        logger.info(f"CompanyCode filter: {selected_company} → {len(df)} rows")

    if "CollectionDate" not in df.columns:
        logger.error("CollectionDate column NOT found — section cannot render")
        return

    amount_col = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"
    logger.info(f"Amount column used: {amount_col}")

    today  = pd.Timestamp("today").normalize()
    logger.info(f"Today reference: {today.date()}")

    n_coll_notna = int(df["CollectionDate"].notna().sum())
    n_coll_null  = len(df) - n_coll_notna
    logger.info(f"CollectionDate — not-null: {n_coll_notna} | null: {n_coll_null}")

    for horizon_days in [7, 14, 30, 60, 90, 120]:
        cutoff = today + pd.Timedelta(days=horizon_days)
        df_h = df[
            df["CollectionDate"].notna()
            & (df["CollectionDate"] >= today)
            & (df["CollectionDate"] <= cutoff)
            & (df[amount_col] > 0)
        ]
        amt = float(df_h[amount_col].sum())
        cnt = len(df_h)
        logger.info(f"  Horizon {horizon_days:>3}d (up to {cutoff.date()}) : {cnt:>5} invoices | {amt:>18,.2f} THB")

    # --- CollectionDate range check ---
    df_future = df[df["CollectionDate"].notna() & (df["CollectionDate"] >= today)].copy()
    if not df_future.empty:
        logger.info(f"Future CollectionDate range: {df_future['CollectionDate'].min().date()} → {df_future['CollectionDate'].max().date()}")
        weekly_counts = df_future.groupby(
            df_future["CollectionDate"].dt.to_period("W")
        )[amount_col].sum()
        logger.info(f"Weekly distribution (future):")
        for period, amt in weekly_counts.items():
            logger.info(f"    {period} : {amt:>18,.2f} THB")
    else:
        logger.warning("No future CollectionDate found — chart will show empty")

    # --- Past CollectionDate (already collected) ---
    df_past = df[df["CollectionDate"].notna() & (df["CollectionDate"] < today)].copy()
    logger.info(f"Past CollectionDate rows (already collected): {len(df_past)}")
    if not df_past.empty:
        logger.info(f"  Past range: {df_past['CollectionDate'].min().date()} → {df_past['CollectionDate'].max().date()}")
        logger.info(f"  Past total amount: {float(df_past[amount_col].sum()):,.2f} THB")

    # --- Null CollectionDate with OverdueAmount > 0 (uncollected) ---
    df_uncoll = df[df["CollectionDate"].isna() & (df["OverdueAmount"] > 0)]
    logger.info(f"Uncollected (CollectionDate=null, OverdueAmount>0): {len(df_uncoll)} rows | {float(df_uncoll['OverdueAmount'].sum()):,.2f} THB")


def _log_future_collection_forecast(logger: logging.Logger, df_overdue: pd.DataFrame, selected_company: str):
    logger.info("=" * 70)
    logger.info("SECTION: Future Collection Forecast (groupby CollectionDate)")
    logger.info("=" * 70)

    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]
        logger.info(f"CompanyCode filter: {selected_company} → {len(df)} rows")

    if "CollectionDate" not in df.columns or "OverdueAmount" not in df.columns:
        logger.error("CollectionDate or OverdueAmount column NOT found")
        return

    today = pd.Timestamp("today").normalize()
    logger.info(f"Today reference: {today.date()}")

    logger.info(f"OverdueAmount stats (all rows) — min: {df['OverdueAmount'].min():,.2f} | mean: {df['OverdueAmount'].mean():,.2f} | max: {df['OverdueAmount'].max():,.2f}")
    logger.info(f"OverdueAmount > 0 rows: {int((df['OverdueAmount'] > 0).sum())} | <= 0 rows: {int((df['OverdueAmount'] <= 0).sum())}")

    for horizon_days in [7, 14, 30, 60, 90, 120]:
        cutoff  = today + pd.Timedelta(days=horizon_days)
        df_h = df[
            df["CollectionDate"].notna()
            & (df["CollectionDate"] >= today)
            & (df["CollectionDate"] <= cutoff)
            & (df["OverdueAmount"] > 0)
        ]
        daily = (
            df_h.groupby("CollectionDate")["OverdueAmount"].sum()
            if not df_h.empty else pd.Series(dtype=float)
        )
        amt_total = float(daily.sum())
        cnt_days  = len(daily)
        cnt_inv   = len(df_h)
        logger.info(f"  Horizon {horizon_days:>3}d : {cnt_inv:>5} invoices | {cnt_days:>3} collection days | {amt_total:>18,.2f} THB")

    # --- groupby CollectionDate detail (30d) ---
    cutoff30 = today + pd.Timedelta(days=30)
    df_30 = df[
        df["CollectionDate"].notna()
        & (df["CollectionDate"] >= today)
        & (df["CollectionDate"] <= cutoff30)
        & (df["OverdueAmount"] > 0)
    ].copy()

    if not df_30.empty:
        daily_30 = (
            df_30.groupby("CollectionDate")["OverdueAmount"]
            .sum()
            .sort_index()
        )
        logger.info(f"Daily breakdown (next 30d) — {len(daily_30)} collection dates:")
        cumulative = 0.0
        for dt, amt in daily_30.items():
            cumulative += amt
            logger.info(f"    {dt.date()} : {amt:>14,.2f} THB  | cumulative: {cumulative:>14,.2f} THB")
    else:
        logger.warning("No data for 30-day daily breakdown")

    # --- Customer distribution ---
    if "Customer" in df_30.columns and not df_30.empty:
        cust_dist = df_30.groupby("Customer")["OverdueAmount"].sum().sort_values(ascending=False)
        logger.info(f"Customer distribution (top 10 by OverdueAmount, next 30d):")
        for cust, amt in cust_dist.head(10).items():
            logger.info(f"    Customer {cust} : {amt:>14,.2f} THB")
        logger.info(f"  Total customers contributing: {len(cust_dist)}")


def _log_credit_planner_board(logger: logging.Logger, df_filtered: pd.DataFrame):
    logger.info("=" * 70)
    logger.info("SECTION: Credit Planner — Action Board")
    logger.info("=" * 70)

    if df_filtered.empty:
        logger.warning("df_filtered is empty — action board logging skipped")
        return

    cust_agg = _agg_customer_overdue(df_filtered)
    if cust_agg.empty:
        logger.warning("_agg_customer_overdue returned empty — no action board data")
        return

    logger.info(f"Customers in aggregation: {len(cust_agg)}")

    net = cust_agg["NetOverdue"]
    logger.info(f"NetOverdue — min: {net.min():,.2f} | mean: {net.mean():,.2f} | max: {net.max():,.2f} | sum: {net.sum():,.2f}")
    logger.info(f"NetOverdue > 0      : {int((net > 0).sum())} customers")
    logger.info(f"NetOverdue > 1M THB : {int((net > 1_000_000).sum())} customers")
    logger.info(f"NetOverdue > 5M THB : {int((net > 5_000_000).sum())} customers")

    if "UtilizationPct" in cust_agg.columns:
        util = cust_agg["UtilizationPct"]
        logger.info(f"UtilizationPct — min: {util.min():.2f}% | mean: {util.mean():.2f}% | max: {util.max():.2f}%")
        logger.info(f"Util > 80%  : {int((util > 80).sum())} customers")
        logger.info(f"Util > 90%  : {int((util > 90).sum())} customers")
        logger.info(f"Util > 100% : {int((util > 100).sum())} customers")
    else:
        logger.warning("UtilizationPct not found in aggregation")

    if "MaxDPD" in cust_agg.columns:
        dpd = cust_agg["MaxDPD"]
        logger.info(f"MaxDPD — min: {dpd.min():.0f} | mean: {dpd.mean():.1f} | max: {dpd.max():.0f}")
        logger.info(f"MaxDPD > 30  : {int((dpd > 30).sum())} customers")
        logger.info(f"MaxDPD > 60  : {int((dpd > 60).sum())} customers")
        logger.info(f"MaxDPD > 90  : {int((dpd > 90).sum())} customers")
    else:
        logger.warning("MaxDPD not found in aggregation")

    # --- Extension days — อ่านจาก datetime ที่ prepare แล้ว ไม่ parse ซ้ำ ---
    has_customer_due = "CustomerDueDate" in df_filtered.columns
    has_original_due = "OriginalDueDate" in df_filtered.columns
    logger.info(f"CustomerDueDate available for ExtensionDays: {has_customer_due}")

    if has_customer_due and has_original_due:
        ext_df = df_filtered[df_filtered["OverdueAmount"] > 0].copy()

        n_cust_ok = int(ext_df["CustomerDueDate"].notna().sum())
        n_cust_nat = len(ext_df) - n_cust_ok
        logger.info(f"CustomerDueDate (invoice rows) — notna: {n_cust_ok} | NaT: {n_cust_nat}")

        if n_cust_ok > 0:
            # อ่านจาก datetime column โดยตรง — ไม่ parse ซ้ำ
            ext_df["_ExtDays"] = (
                (ext_df["CustomerDueDate"] - ext_df["OriginalDueDate"])
                .dt.days
                .fillna(0)
                .clip(lower=0)
            )
            ext_agg = (
                ext_df.groupby("Customer")["_ExtDays"]
                .max()
                .reset_index()
            )
            ext_agg.columns = ["Customer", "MaxExtension"]

            logger.info(f"MaxExtension stats — min: {ext_agg['MaxExtension'].min():.0f} | mean: {ext_agg['MaxExtension'].mean():.1f} | max: {ext_agg['MaxExtension'].max():.0f}")
            logger.info(f"MaxExtension > 0  days : {int((ext_agg['MaxExtension'] > 0).sum())} customers")
            logger.info(f"MaxExtension > 30 days : {int((ext_agg['MaxExtension'] > 30).sum())} customers")
            logger.info(f"MaxExtension > 60 days : {int((ext_agg['MaxExtension'] > 60).sum())} customers")

            # sample top extension customers
            top_ext = ext_agg.sort_values("MaxExtension", ascending=False).head(5)
            logger.info(f"Top 5 customers by MaxExtension:")
            for _, row in top_ext.iterrows():
                logger.info(f"    Customer {int(row['Customer'])} : {int(row['MaxExtension'])} days")
        else:
            logger.warning("CustomerDueDate all NaT in invoice rows — ExtensionDays = 0 for all")
            ext_agg = pd.DataFrame(columns=["Customer", "MaxExtension"])
    else:
        ext_agg = pd.DataFrame(columns=["Customer", "MaxExtension"])
        if not has_customer_due:
            logger.warning("CustomerDueDate column not present")
        if not has_original_due:
            logger.warning("OriginalDueDate column not present")

    # --- Action rule results ---
    CALL_THRESHOLD        = 5_000_000
    REVIEW_UTIL_THRESHOLD = 90.0
    ESCALATE_EXT_DAYS     = 30

    n_call   = int((cust_agg["NetOverdue"] > CALL_THRESHOLD).sum())
    n_review = int((cust_agg["UtilizationPct"] > REVIEW_UTIL_THRESHOLD).sum()) if "UtilizationPct" in cust_agg.columns else 0

    logger.info(f"Action — Call Customer (NetOverdue > {CALL_THRESHOLD:,.0f})   : {n_call} customers")
    logger.info(f"Action — Review Credit (Util > {REVIEW_UTIL_THRESHOLD:.0f}%)               : {n_review} customers")

    if not ext_agg.empty:
        merged = cust_agg.merge(ext_agg, on="Customer", how="left")
        merged["MaxExtension"] = merged["MaxExtension"].fillna(0)
        n_escalate = int((merged["MaxExtension"] > ESCALATE_EXT_DAYS).sum())
        logger.info(f"Action — Escalate (Extension > {ESCALATE_EXT_DAYS} days)            : {n_escalate} customers")
    else:
        logger.info(f"Action — Escalate (Extension > {ESCALATE_EXT_DAYS} days)            : 0 customers (no extension data)")

    # --- Top 5 call list ---
    call_list = (
        cust_agg[cust_agg["NetOverdue"] > CALL_THRESHOLD]
        .sort_values("NetOverdue", ascending=False)
        .head(5)
    )
    label_col = "CustomerName" if "CustomerName" in call_list.columns else "Customer"
    logger.info(f"Top 5 Call Customer list:")
    for _, row in call_list.iterrows():
        logger.info(
            f"    {row[label_col]} | "
            f"NetOverdue: {row['NetOverdue']:,.2f} THB | "
            f"Util: {row.get('UtilizationPct', 0):.1f}%"
        )



def _log_credit_journey_sankey(logger: logging.Logger, df_overdue: pd.DataFrame, selected_company: str):
    logger.info("=" * 70)
    logger.info("SECTION: Credit Journey — Invoice Extension Sankey")
    logger.info("=" * 70)

    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]
        logger.info(f"CompanyCode filter: {selected_company} → {len(df)} rows")

    df = df[df["OverdueAmount"] > 0].copy()
    logger.info(f"After OverdueAmount > 0 filter: {len(df)} rows")

    if df.empty:
        logger.warning("No invoice rows — Sankey logging skipped")
        return

    has_customer_due = "CustomerDueDate" in df.columns
    has_collection   = "CollectionDate" in df.columns
    has_original_due = "OriginalDueDate" in df.columns
    amount_col       = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"

    logger.info(f"OriginalDueDate present : {has_original_due}")
    logger.info(f"CustomerDueDate present : {has_customer_due}")
    logger.info(f"CollectionDate present  : {has_collection}")
    logger.info(f"Amount column used      : {amount_col}")

    if not has_original_due:
        logger.error("OriginalDueDate missing — Sankey cannot be built")
        return

    # --- CustomerDueDate: อ่านจาก datetime column ที่ _prepare_overdue parse แล้ว ---
    if has_customer_due:
        # ณ จุดนี้ CustomerDueDate เป็น datetime แล้ว (parse โดย _prepare_overdue)
        # ไม่ต้อง parse ซ้ำ — ลบตรงได้เลย
        n_cust_notna = int(df["CustomerDueDate"].notna().sum())
        n_cust_nat   = len(df) - n_cust_notna
        logger.info(f"CustomerDueDate (post-prepare) — notna: {n_cust_notna} | NaT: {n_cust_nat}")

        if n_cust_notna > 0:
            logger.info(f"CustomerDueDate range: {df['CustomerDueDate'].min()} → {df['CustomerDueDate'].max()}")
            # sample datetime values
            sample_vals = df["CustomerDueDate"].dropna().head(5).dt.strftime("%Y-%m-%d").tolist()
            logger.info(f"CustomerDueDate sample (parsed): {sample_vals}")

        df["_ExtDays"] = (
            (df["CustomerDueDate"] - df["OriginalDueDate"])
            .dt.days
            .fillna(0)
            .clip(lower=0)
        )
        logger.info(f"ExtensionDays — min: {df['_ExtDays'].min():.0f} | mean: {df['_ExtDays'].mean():.1f} | max: {df['_ExtDays'].max():.0f}")
        logger.info(f"ExtensionDays > 0 rows: {int((df['_ExtDays'] > 0).sum())}")
    else:
        df["_ExtDays"] = 0
        logger.warning("CustomerDueDate not present — all rows assigned to Ext 0-7d")

    # --- Extension bucket distribution ---
    LARGE_OVERDUE_THB = 1_000_000
    logger.info(f"Large Overdue threshold: {LARGE_OVERDUE_THB:,.0f} THB")
    logger.info(f"Extension bucket distribution:")
    logger.info(f"  Ext 0-7d   : {int((df['_ExtDays'] <= 7).sum()):>6} rows | {float(df.loc[df['_ExtDays'] <= 7, amount_col].sum()):>18,.2f} THB")
    logger.info(f"  Ext 8-30d  : {int(((df['_ExtDays'] > 7) & (df['_ExtDays'] <= 30)).sum()):>6} rows | {float(df.loc[(df['_ExtDays'] > 7) & (df['_ExtDays'] <= 30), amount_col].sum()):>18,.2f} THB")
    logger.info(f"  Ext 30+d   : {int((df['_ExtDays'] > 30).sum()):>6} rows | {float(df.loc[df['_ExtDays'] > 30, amount_col].sum()):>18,.2f} THB")

    # --- Outcome ---
    if has_collection:
        paid_mask  = df["CollectionDate"].notna()
        n_paid     = int(paid_mask.sum())
        logger.info(f"Outcome — Paid total: {n_paid} rows | {float(df.loc[paid_mask, amount_col].sum()):,.2f} THB")

        if has_original_due:
            paid_late_mask   = paid_mask & df["CollectionDate"].notna() & df["OriginalDueDate"].notna() & (df["CollectionDate"] > df["OriginalDueDate"])
            paid_ontime_mask = paid_mask & ~paid_late_mask
            logger.info(f"Outcome — Paid On-Time : {int(paid_ontime_mask.sum()):>6} rows | {float(df.loc[paid_ontime_mask, amount_col].sum()):>18,.2f} THB")
            logger.info(f"Outcome — Paid Late    : {int(paid_late_mask.sum()):>6} rows | {float(df.loc[paid_late_mask, amount_col].sum()):>18,.2f} THB")

        unpaid_mask  = ~paid_mask
        large_mask   = unpaid_mask & (df[amount_col] >= LARGE_OVERDUE_THB)
        small_mask   = unpaid_mask & (df[amount_col] <  LARGE_OVERDUE_THB)
        logger.info(f"Outcome — Large Overdue: {int(large_mask.sum()):>6} rows | {float(df.loc[large_mask, amount_col].sum()):>18,.2f} THB")
        logger.info(f"Outcome — Small Overdue: {int(small_mask.sum()):>6} rows | {float(df.loc[small_mask, amount_col].sum()):>18,.2f} THB")
    else:
        logger.warning("CollectionDate not present")

    # --- Flow matrix ---
    def _ext_bucket(d):
        if d <= 7:    return "Ext 0-7d"
        elif d <= 30: return "Ext 8-30d"
        else:         return "Ext 30+d"

    def _outcome(row):
        if has_collection and pd.notna(row.get("CollectionDate")):
            if has_original_due and pd.notna(row.get("OriginalDueDate")) and row["CollectionDate"] > row["OriginalDueDate"]:
                return "Paid Late"
            return "Paid On-Time"
        if row[amount_col] >= LARGE_OVERDUE_THB:
            return "Large Overdue"
        return "Small Overdue"

    df["_ExtBucket"] = df["_ExtDays"].apply(_ext_bucket)
    df["_Outcome"]   = df.apply(_outcome, axis=1)

    flow = (
        df.groupby(["_ExtBucket", "_Outcome"])[amount_col]
        .agg(Amount="sum", Count="count")
        .reset_index()
    )
    logger.info(f"Sankey flow matrix ({len(flow)} combinations):")
    for _, row in flow.iterrows():
        logger.info(f"  {row['_ExtBucket']:>12} → {row['_Outcome']:<16} : {int(row['Count']):>5} rows | {float(row['Amount']):>18,.2f} THB")

    missing_buckets  = {"Ext 0-7d", "Ext 8-30d", "Ext 30+d"}  - set(flow["_ExtBucket"].unique())
    missing_outcomes = {"Paid On-Time", "Paid Late", "Large Overdue", "Small Overdue"} - set(flow["_Outcome"].unique())
    if missing_buckets:
        logger.warning(f"Extension buckets with zero flow: {missing_buckets}")
    if missing_outcomes:
        logger.warning(f"Outcomes with zero flow: {missing_outcomes}")

    logger.info(f"Total Sankey amount: {float(flow['Amount'].sum()):,.2f} THB")
    logger.info(f"Total Sankey rows  : {int(flow['Count'].sum())}")


def run_credit_moni_logging(
    df_overdue: pd.DataFrame,
    df_filtered: pd.DataFrame,
    selected_company: str,
):
    logger = _setup_credit_moni_logger()
    logger.info("START — Credit Planning EDA/Validation Log")
    logger.info(f"selected_company : {selected_company}")
    logger.info("")

    # =========================================================
    # BLOCK 0 — Raw session_state df_overdue (before prepare)
    # =========================================================
    logger.info("=" * 70)
    logger.info("BLOCK 0 — Raw df_overdue from session_state (pre-prepare)")
    logger.info("=" * 70)

    df_raw_ss = st.session_state.get("df_overdue")
    if df_raw_ss is not None:
        logger.info(f"session_state df_overdue shape : {df_raw_ss.shape}")
        logger.info(f"session_state df_overdue columns: {list(df_raw_ss.columns)}")
        if "CompanyCode" in df_raw_ss.columns:
            cc_counts = df_raw_ss["CompanyCode"].astype(str).value_counts()
            logger.info(f"CompanyCode distribution (all rows):")
            for cc, cnt in cc_counts.items():
                logger.info(f"  {cc:>10} : {cnt:>6} rows")
        if "OverdueAmount" in df_raw_ss.columns:
            ov = pd.to_numeric(df_raw_ss["OverdueAmount"], errors="coerce")
            logger.info(f"OverdueAmount (raw) — >0: {int((ov > 0).sum())} | =0: {int((ov == 0).sum())} | <0: {int((ov < 0).sum())} | NaN: {int(ov.isna().sum())}")
        for date_col in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
            if date_col in df_raw_ss.columns:
                sample_vals = df_raw_ss[date_col].dropna().astype(str).unique()[:5].tolist()
                logger.info(f"{date_col} raw sample values: {sample_vals}")
    else:
        logger.error("session_state df_overdue is None")

    logger.info("")

    # =========================================================
    # BLOCK 1 — df_overdue after _prepare_overdue
    # =========================================================
    logger.info("=" * 70)
    logger.info("BLOCK 1 — df_overdue after _prepare_overdue()")
    logger.info("=" * 70)
    logger.info(f"Shape : {df_overdue.shape}")
    logger.info(f"Columns: {list(df_overdue.columns)}")

    if df_raw_ss is not None:
        row_diff = df_raw_ss.shape[0] - df_overdue.shape[0]
        logger.info(f"Row diff vs raw session_state: {row_diff} rows {'LOST' if row_diff > 0 else 'OK'}")

    if "CompanyCode" in df_overdue.columns:
        cc_after = df_overdue["CompanyCode"].astype(str).value_counts()
        logger.info(f"CompanyCode distribution (after prepare):")
        for cc, cnt in cc_after.items():
            logger.info(f"  {cc:>10} : {cnt:>6} rows")
        df_company = df_overdue[df_overdue["CompanyCode"] == selected_company]
        logger.info(f"Rows for CompanyCode={selected_company}: {len(df_company)}")
    else:
        df_company = df_overdue.copy()
        logger.warning("CompanyCode column not found")

    if "OverdueAmount" in df_overdue.columns:
        ov = df_overdue["OverdueAmount"]
        logger.info(f"OverdueAmount (prepared, all companies) — >0: {int((ov > 0).sum())} | =0: {int((ov == 0).sum())} | <0: {int((ov < 0).sum())}")
        ov_co = df_company["OverdueAmount"] if not df_company.empty else pd.Series(dtype=float)
        logger.info(f"OverdueAmount (CompanyCode={selected_company}) — >0: {int((ov_co > 0).sum())} | =0: {int((ov_co == 0).sum())} | <0: {int((ov_co < 0).sum())}")

    for date_col in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
        if date_col in df_overdue.columns:
            n_ok   = int(df_overdue[date_col].notna().sum())
            n_fail = len(df_overdue) - n_ok
            logger.info(f"{date_col} — parsed OK: {n_ok} | NaT: {n_fail}")
            if n_fail > 0 and df_raw_ss is not None and date_col in df_raw_ss.columns:
                fail_idx  = df_overdue[df_overdue[date_col].isna()].index
                raw_fails = df_raw_ss.loc[df_raw_ss.index.isin(fail_idx), date_col].dropna().astype(str).unique()[:5].tolist()
                logger.warning(f"  {date_col} parse-fail raw samples: {raw_fails}")
            if n_ok > 0:
                logger.info(f"  {date_col} range: {df_overdue[date_col].min()} → {df_overdue[date_col].max()}")

    logger.info("")

    # =========================================================
    # BLOCK 2 — df_filtered (joined + all filters applied)
    # =========================================================
    logger.info("=" * 70)
    logger.info("BLOCK 2 — df_filtered (after _render_filters)")
    logger.info("=" * 70)
    logger.info(f"Shape : {df_filtered.shape}")
    logger.info(f"Columns: {list(df_filtered.columns)}")

    if "OverdueAmount" in df_filtered.columns:
        ov_f = df_filtered["OverdueAmount"]
        logger.info(f"OverdueAmount (filtered) — >0: {int((ov_f > 0).sum())} | =0: {int((ov_f == 0).sum())} | <0: {int((ov_f < 0).sum())}")

    join_cols = ["CUSTOMER_CODE", "AVAIL_CUSTOMER_NAME", "UtilizationPct", "RiskTier"]
    for jc in join_cols:
        present = jc in df_filtered.columns
        logger.info(f"Join column '{jc}' present: {present}")
        if present and jc == "CUSTOMER_CODE":
            n_joined   = int(df_filtered[jc].notna().sum())
            n_unjoined = len(df_filtered) - n_joined
            logger.info(f"  Joined rows (CUSTOMER_CODE notna): {n_joined} | Unjoined: {n_unjoined}")

    if "RiskTier" in df_filtered.columns:
        tier_dist = df_filtered["RiskTier"].value_counts().to_dict()
        logger.info(f"RiskTier distribution: {tier_dist}")

    if "UtilizationPct" in df_filtered.columns:
        util = df_filtered["UtilizationPct"].dropna()
        logger.info(f"UtilizationPct — mean: {util.mean():.2f}% | max: {util.max():.2f}% | zero count: {int((util == 0).sum())}")

    logger.info("")

    try:
        _log_paid_classification(logger, df_overdue, selected_company)
    except Exception as e:
        logger.error(f"_log_paid_classification error: {e}")

    # =========================================================
    # Sections
    # =========================================================
    try:
        _log_collection_pipeline(logger, df_overdue, selected_company)
    except Exception as e:
        logger.error(f"_log_collection_pipeline error: {e}")

    logger.info("")

    try:
        _log_cash_inflow_forecast(logger, df_overdue, selected_company)
    except Exception as e:
        logger.error(f"_log_cash_inflow_forecast error: {e}")

    logger.info("")

    try:
        _log_future_collection_forecast(logger, df_overdue, selected_company)
    except Exception as e:
        logger.error(f"_log_future_collection_forecast error: {e}")

    logger.info("")

    try:
        _log_credit_planner_board(logger, df_filtered)
    except Exception as e:
        logger.error(f"_log_credit_planner_board error: {e}")

    logger.info("")

    try:
        _log_credit_journey_sankey(logger, df_overdue, selected_company)
    except Exception as e:
        logger.error(f"_log_credit_journey_sankey error: {e}")

    logger.info("")
    logger.info("END — Credit Planning EDA/Validation Log")

    for h in logger.handlers:
        h.flush()
        h.close()


def _log_paid_classification(logger: logging.Logger, df_overdue: pd.DataFrame, selected_company: str):
    logger.info("=" * 70)
    logger.info("SECTION: PaidOnTime / PaidLate / NotCollected Classification Debug")
    logger.info("=" * 70)

    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]
        logger.info(f"CompanyCode filter: {selected_company} → {len(df)} rows")

    # --- column availability ---
    for col in ("OverdueAmount", "OriginalDueDate", "CollectionDate",
                "CustomerDueDate", "IsPaid", "PaidOnTime", "PaidLate", "NotCollected"):
        present = col in df.columns
        logger.info(f"Column '{col}' present: {present}")

    logger.info("")

    # --- IsPaid breakdown ---
    if "IsPaid" in df.columns:
        n_paid   = int(df["IsPaid"].sum())
        n_unpaid = len(df) - n_paid
        logger.info(f"IsPaid = True  (OverdueAmount == 0): {n_paid:,} rows")
        logger.info(f"IsPaid = False (OverdueAmount != 0): {n_unpaid:,} rows")
    logger.info("")

    # --- PaidOnTime ---
    if "PaidOnTime" in df.columns:
        n_ontime = int(df["PaidOnTime"].sum())
        logger.info(f"PaidOnTime = True: {n_ontime:,} rows")

        if n_ontime > 0 and "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
            sample = df[df["PaidOnTime"]].head(5)
            logger.info("Sample PaidOnTime rows:")
            for _, row in sample.iterrows():
                logger.info(
                    f"  Customer={row.get('Customer')} | "
                    f"OriginalDueDate={row.get('OriginalDueDate')} | "
                    f"CollectionDate={row.get('CollectionDate')} | "
                    f"CustomerDueDate={row.get('CustomerDueDate')} | "
                    f"OverdueAmount={row.get('OverdueAmount')}"
                )
        elif n_ontime == 0:
            logger.warning("PaidOnTime = 0 rows — ไม่มี invoice ที่จ่ายตรงเวลาเลย")
    logger.info("")

    # --- PaidLate ---
    if "PaidLate" in df.columns:
        n_late = int(df["PaidLate"].sum())
        logger.info(f"PaidLate = True: {n_late:,} rows")

        if n_late > 0 and "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
            sample = df[df["PaidLate"]].head(5)
            logger.info("Sample PaidLate rows:")
            for _, row in sample.iterrows():
                coll = row.get("CollectionDate")
                orig = row.get("OriginalDueDate")
                diff = (coll - orig).days if pd.notna(coll) and pd.notna(orig) else "N/A"
                logger.info(
                    f"  Customer={row.get('Customer')} | "
                    f"OriginalDueDate={orig} | "
                    f"CollectionDate={coll} | "
                    f"Diff={diff} days | "
                    f"OverdueAmount={row.get('OverdueAmount')}"
                )
    logger.info("")

    # --- NotCollected ---
    if "NotCollected" in df.columns:
        n_notcoll = int(df["NotCollected"].sum())
        logger.info(f"NotCollected = True (OverdueAmount > 0): {n_notcoll:,} rows")

        if n_notcoll > 0:
            sample = df[df["NotCollected"]].head(5)
            logger.info("Sample NotCollected rows:")
            for _, row in sample.iterrows():
                logger.info(
                    f"  Customer={row.get('Customer')} | "
                    f"OriginalDueDate={row.get('OriginalDueDate')} | "
                    f"CollectionDate={row.get('CollectionDate')} | "
                    f"OverdueAmount={row.get('OverdueAmount')}"
                )
    logger.info("")

    # --- Cross-check: IsPaid แต่ไม่ได้ถูก classify เป็น OnTime หรือ Late ---
    if all(c in df.columns for c in ("IsPaid", "PaidOnTime", "PaidLate")):
        paid_rows       = df[df["IsPaid"]].copy()
        unclassified    = paid_rows[~paid_rows["PaidOnTime"] & ~paid_rows["PaidLate"]]
        n_unclassified  = len(unclassified)
        logger.info(f"IsPaid=True แต่ไม่ถูก classify เป็น OnTime หรือ Late: {n_unclassified:,} rows")
        if n_unclassified > 0:
            logger.warning("rows เหล่านี้น่าจะมี CollectionDate หรือ OriginalDueDate เป็น NaT")
            sample = unclassified.head(5)
            for _, row in sample.iterrows():
                logger.info(
                    f"  Customer={row.get('Customer')} | "
                    f"OriginalDueDate={row.get('OriginalDueDate')} | "
                    f"CollectionDate={row.get('CollectionDate')} | "
                    f"OverdueAmount={row.get('OverdueAmount')}"
                )
    logger.info("")

    # --- CollectionDate vs OriginalDueDate distribution (IsPaid rows เท่านั้น) ---
    if all(c in df.columns for c in ("IsPaid", "CollectionDate", "OriginalDueDate")):
        paid_df = df[df["IsPaid"] & df["CollectionDate"].notna() & df["OriginalDueDate"].notna()].copy()
        if not paid_df.empty:
            paid_df["_diff"] = (paid_df["CollectionDate"] - paid_df["OriginalDueDate"]).dt.days
            n_eq   = int((paid_df["_diff"] == 0).sum())
            n_lt   = int((paid_df["_diff"] < 0).sum())
            n_gt   = int((paid_df["_diff"] > 0).sum())
            logger.info("CollectionDate vs OriginalDueDate (IsPaid rows ที่มีทั้งคู่):")
            logger.info(f"  CollectionDate == OriginalDueDate : {n_eq:,} rows (On-Time exact)")
            logger.info(f"  CollectionDate <  OriginalDueDate : {n_lt:,} rows (Early / On-Time)")
            logger.info(f"  CollectionDate >  OriginalDueDate : {n_gt:,} rows (Late)")
            logger.info(f"  diff stats — min: {paid_df['_diff'].min():.0f} | mean: {paid_df['_diff'].mean():.1f} | max: {paid_df['_diff'].max():.0f} days")
        else:
            logger.warning("IsPaid rows ที่มีทั้ง CollectionDate และ OriginalDueDate: 0 rows")