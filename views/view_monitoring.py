# =============================================================================
# views/view_monitoring.py
# Join key : df_overdue.Customer == df_avail.CUSTOMER_CODE
# =============================================================================

import streamlit as st
import math
import random
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
            "Credit Monitoring Dashboard",
            "Analytics Dashboard — joined credit health signal (Availability x Overdue)",
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

    # ==================================================================
    # SECTION 1 : Monitoring KPI Row
    # ==================================================================
    st.markdown(section_header("Monitoring Health — Key Signals"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 2 : Credit Health Matrix
    # ==================================================================
    st.markdown(
        section_header("Credit Health Matrix — Utilization vs Overdue Risk"),
        unsafe_allow_html=True,
    )
    col_bubble, col_tier = st.columns([3, 2], gap="medium")
    with col_bubble:
        _render_health_bubble(df_filtered)
    with col_tier:
        _render_risk_tier_donut(df_filtered)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 3 : Watchlist
    # ==================================================================
    st.markdown(
        section_header("Watchlist — Customers Needing Immediate Attention"),
        unsafe_allow_html=True,
    )
    _render_watchlist(df_filtered)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 4 : Collection Efficiency Trend
    # ==================================================================
    st.markdown(
        section_header("Collection Efficiency — On-Time vs Delayed Payment"),
        unsafe_allow_html=True,
    )
    gran_col, _ = st.columns([1, 4])
    with gran_col:
        granularity = st.selectbox(
            "Period Granularity",
            options=["Monthly", "Quarterly", "Yearly"],
            index=0,
            key="mon_gran",
        )

    _render_collection_trend(df_overdue_prep, selected_company, granularity)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div style='font-size:0.82rem;font-weight:600;color:#1B4F8A;"
        "letter-spacing:0.04em;margin-bottom:6px'>"
        "On-Time vs Delay Trend Analysis — Per Customer</div>",
        unsafe_allow_html=True,
    )
    _render_ontime_delay_trend(
        df_overdue=df_overdue_prep,
        selected_company=selected_company,
        granularity=granularity,
    )
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 5 : Overdue Breakdown Stats
    # ==================================================================
    st.markdown(section_header("Overdue Breakdown Statistics"), unsafe_allow_html=True)
    col_aging, col_top = st.columns([1, 1], gap="medium")
    with col_aging:
        _render_aging_bar(df_filtered)
    with col_top:
        _render_top_overdue(df_filtered)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 6 : Raw Joined Table
    # ==================================================================
    with st.expander("View Joined Records — Credit Availability x Overdue", expanded=False):
        _render_joined_table(df_filtered)
    st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 7 : Credit Risk Propagation + Community Detection
    # ==================================================================
    st.markdown(
        section_header("Credit Risk Propagation — Community Detection"),
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.78rem;color:#8A9BB0;margin-bottom:10px'>"
        "วิเคราะห์การกระจุกตัวของความเสี่ยง — ลูกค้าที่อยู่ใน cluster เดียวกัน"
        " (ประเภทสินค้าร่วม) มีแนวโน้มส่งผลกระทบต่อกัน"
        "</div>",
        unsafe_allow_html=True,
    )
    _render_risk_propagation(df_filtered)


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
    """
    OverdueAmount convention (validated จากข้อมูลจริง):
      > 0  : invoice ที่ลูกค้าต้องจ่าย
      = 0  : ไม่มียอด
      < 0  : Credit Note — ยกหนี้หรือลดหนี้
             (มักจะ |OverdueAmount| == InvoiceAmount = ยกทั้งก้อน
              หรือ |OverdueAmount| < InvoiceAmount = ลดบางส่วน/ส่วนลด)

    Row-level columns:
      IsOverdue    = OverdueAmount > 0
      IsCreditNote = OverdueAmount < 0
      OverdueAbs   = OverdueAmount.clip(lower=0)  → gross per row
                     (Credit Note = 0 ใน column นี้)

    Customer aggregate ต้องใช้ sum(OverdueAmount) ไม่ใช่ sum(OverdueAbs)
    เพื่อให้ได้ net = gross - credit note offset
    """
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]

    for col in ("OriginalDueDate", "CollectionDate"):
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

    df["IsOverdue"]    = df["OverdueAmount"] > 0
    df["IsCreditNote"] = df["OverdueAmount"] < 0
    df["OverdueAbs"]   = df["OverdueAmount"].clip(lower=0)

    if "CollectionDate" in df.columns:
        df["IsPaid"] = df["CollectionDate"].notna()
    else:
        df["IsPaid"] = False

    today = pd.Timestamp("today").normalize()

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

    if "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
        is_invoice = df["OverdueAmount"] > 0  

        df["PaidLate"] = (
            is_invoice
            & df["CollectionDate"].notna()
            & (df["CollectionDate"] > df["OriginalDueDate"])
        )
        df["PaidOnTime"] = (
            is_invoice
            & df["CollectionDate"].notna()
            & ~df["PaidLate"]
        )
        df["NotCollected"] = (
            is_invoice
            & df["CollectionDate"].isna()
        )
    else:
        df["PaidLate"]     = False
        df["PaidOnTime"]   = False
        df["NotCollected"] = False

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

    # Overdue Due Year จาก OriginalDueDate — เป็น filter หลัก
    overdue_due_years = []
    if "DueYear" in df_overdue.columns:
        overdue_due_years = sorted(
            df_overdue["DueYear"].dropna().astype(int).unique().tolist()
        )

    # Avail years ที่มีจริง — ใช้เทียบ map ภายใน ไม่ใช่ filter แยก
    avail_years_available = set()
    if "AVAIL_YEAR" in df_avail.columns:
        avail_years_available = set(
            df_avail["AVAIL_YEAR"].dropna().astype(str).unique().tolist()
        )

    COLS = [1.0, 1.0, 1.0, 1.0, 1.8]
    lc1, lc2, lc3, lc4, lc5 = st.columns(COLS, gap="small")
    with lc1: st.markdown(f"<span style='{LABEL_STYLE}'>Company Code</span>",       unsafe_allow_html=True)
    with lc2: st.markdown(f"<span style='{LABEL_STYLE}'>Overdue Due Year</span>",   unsafe_allow_html=True)
    with lc3: st.markdown(f"<span style='{LABEL_STYLE}'>Risk Tier</span>",          unsafe_allow_html=True)
    with lc4: st.markdown(f"<span style='{LABEL_STYLE}'>DPD Bucket</span>",         unsafe_allow_html=True)
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
        bucket_options = ["All", "1-30", "31-60", "61-90", "90+"]
        selected_bucket = st.selectbox(
            "DPD Bucket", options=bucket_options,
            index=0, key="mon_bucket",
            label_visibility="collapsed",
        )
    with wc5:
        customer_search = st.text_input(
            "Search Customer Name",
            placeholder="Type to filter...",
            key="mon_customer_search",
            label_visibility="collapsed",
        )

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    df = df_joined.copy()

    # 1. CompanyCode
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    # 2. Overdue Due Year — filter overdue transaction ตาม OriginalDueDate
    #    จากนั้น re-join avail ด้วย snapshot ที่ปีตรงกัน
    if selected_due_year != "All":
        try:
            due_year_int = int(selected_due_year)
        except (ValueError, TypeError):
            due_year_int = None

        if due_year_int and "DueYear" in df.columns:
            df = df[df["DueYear"] == due_year_int]

            # หา avail year ที่ match กับ due year นี้
            # ลำดับ: ตรงกันพอดี → ปีก่อนหน้าที่ใกล้สุด → ปีหลังที่ใกล้สุด → ล่าสุด
            due_year_str   = str(due_year_int)
            avail_year_int = sorted([int(y) for y in avail_years_available if y.isdigit()])

            if due_year_str in avail_years_available:
                matched_avail_year = due_year_str          # ตรงกันพอดี
            elif avail_year_int:
                # หาปีที่ใกล้ที่สุด (ไม่เกิน due year ก่อน เพื่อไม่ใช้อนาคต)
                before = [y for y in avail_year_int if y <= due_year_int]
                after  = [y for y in avail_year_int if y > due_year_int]
                if before:
                    matched_avail_year = str(max(before))  # ปีก่อนหน้าที่ใกล้สุด
                else:
                    matched_avail_year = str(min(after))   # ถ้าไม่มีก่อนหน้า ใช้หลังที่ใกล้สุด
            else:
                matched_avail_year = None

            # Re-join ด้วย avail snapshot ของปีที่ map ได้
            if matched_avail_year and not df_avail.empty:
                avail_for_year = df_avail[
                    df_avail["AVAIL_YEAR"].astype(str) == matched_avail_year
                ].copy()

                if not avail_for_year.empty:
                    # snapshot ล่าสุดของปีที่ map ได้
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

                    # drop avail columns เดิม + re-join
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

                    # recalculate UtilizationPct
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

                    # recalculate RiskTier
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

                # Info: บอก user ว่า map กับ avail ปีไหน
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
                        f"Credit metrics (Util%, Debt) reflect {matched_avail_year} snapshot.",
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

    # 4. DPD Bucket
    if selected_bucket != "All" and "AgingBucket" in df.columns:
        df = df[df["AgingBucket"].astype(str) == selected_bucket]

    # 5. Customer Name search
    if customer_search:
        for col_search in ("CustomerName", "AVAIL_CUSTOMER_NAME"):
            if col_search in df.columns:
                df = df[
                    df[col_search].astype(str)
                    .str.contains(customer_search, case=False, na=False)
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
def _render_collection_trend(df_overdue: pd.DataFrame, selected_company: str, granularity: str):
    """
    Stacked Bar: On-Time | Late | Not Collected — per period.
    Uses raw df_overdue (pre-join) filtered by CompanyCode.
    """
    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    if df.empty or "OriginalDueDate" not in df.columns:
        st.info("No collection data available for the selected company.")
        return

    if not all(col in df.columns for col in ("PaidOnTime", "PaidLate", "NotCollected")):
        st.info("Payment classification columns not found.")
        return

    # Period label
    if granularity == "Yearly":
        df["Period"] = df["DueYear"].astype(str)
        sort_col     = "DueYear"
    elif granularity == "Quarterly":
        df["Period"] = df["DueYear"].astype(str) + "-Q" + df["DueQuarter"].astype(str)
        sort_col     = ["DueYear", "DueQuarter"]
    else:  # Monthly
        df["Period"]    = df["DueYear"].astype(str) + "-" + df["DueMonthLabel"].fillna("")
        sort_col        = ["DueYear", "DueMonth"]

    grp = (
        df.groupby("Period")
        .agg(
            OnTime      =("PaidOnTime",    "sum"),
            Late        =("PaidLate",      "sum"),
            NotCollected=("NotCollected",  "sum"),
        )
        .reset_index()
    )

    # Sort periods correctly
    if granularity == "Monthly":
        grp = grp.merge(
            df[["Period", "DueYear", "DueMonth"]].drop_duplicates(),
            on="Period", how="left"
        ).sort_values(["DueYear", "DueMonth"]).drop_duplicates("Period")
    elif granularity == "Quarterly":
        grp = grp.merge(
            df[["Period", "DueYear", "DueQuarter"]].drop_duplicates(),
            on="Period", how="left"
        ).sort_values(["DueYear", "DueQuarter"]).drop_duplicates("Period")
    else:
        grp = grp.sort_values("Period")

    grp = grp.reset_index(drop=True)

    fig = go.Figure()
    bar_specs = [
        ("On-Time",       "OnTime",       PALETTE["jade_lt"]),
        ("Late",          "Late",         PALETTE["amber_lt"]),
        ("Not Collected", "NotCollected", PALETTE["crimson"]),
    ]
    for name, col, color in bar_specs:
        if col not in grp.columns:
            continue
        fig.add_trace(go.Bar(
            x            = grp["Period"].tolist(),
            y            = grp[col].tolist(),
            name         = name,
            marker_color = color,
            hovertemplate= f"<b>{name}</b><br>Period: %{{x}}<br>Count: %{{y:,}}<extra></extra>",
        ))

    apply_base_layout(fig, {
        "height":  360,
        "margin":  dict(l=0, r=20, t=30, b=10),
        "barmode": "stack",
        "title":   dict(
            text = f"Collection Efficiency — {granularity} View",
            font = dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            showgrid   = False,
            color      = FONT_COLOR,
            tickangle  = -35,
            tickfont   = dict(size=9),
        ),
        "yaxis": dict(
            title    = "Invoice Count",
            showgrid = True, gridcolor=GRID_COLOR,
            color    = FONT_COLOR, tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation = "h",
            yanchor     = "bottom", y=1.02,
            xanchor     = "right",  x=1,
            font        = dict(size=9),
        ),
        "showlegend": True,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_collection_trend")


def _render_ontime_delay_trend(
    df_overdue: pd.DataFrame,
    selected_company: str,
    granularity: str,
):
    df = df_overdue.copy()
    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    # กรองเฉพาะ invoice rows — Credit Note / zero ไม่เกี่ยวกับ on-time/delay
    df = df[df["OverdueAmount"] > 0].copy()

    required_base = {"PaidOnTime", "PaidLate", "NotCollected", "OriginalDueDate"}
    if not required_base.issubset(df.columns):
        st.info("Payment classification columns not found.")
        return
    if df.empty:
        st.info("No invoice data for this company.")
        return

    # ------------------------------------------------------------------
    # DisplayName: ใช้ CustomerName ถ้ามี fallback เป็น Customer code
    # ไม่บังคับ join avail → customer ครบทุกคน
    # ------------------------------------------------------------------
    if "CustomerName" in df.columns:
        df["_DisplayName"] = (
            df["CustomerName"].astype(str).str.strip()
            .replace({"": None, "nan": None, "None": None})
        )
        df["_DisplayName"] = df["_DisplayName"].fillna(
            df["Customer"].astype(str)
        )
    elif "Customer" in df.columns:
        df["_DisplayName"] = df["Customer"].astype(str)
    else:
        st.info("No customer identifier found.")
        return

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    LABEL_STYLE = (
        "font-size:0.72rem;font-weight:600;color:#1B4F8A;"
        "letter-spacing:0.01em;margin-bottom:1px;display:block;"
    )

    r1c1, r1c2, r1c3 = st.columns([1.2, 1.2, 1.6], gap="small")
    with r1c1:
        st.markdown(f"<span style='{LABEL_STYLE}'>Due Date From</span>",
                    unsafe_allow_html=True)
        date_from = st.date_input(
            "Due Date From", value=None,
            key="otd_date_from", label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with r1c2:
        st.markdown(f"<span style='{LABEL_STYLE}'>Due Date To</span>",
                    unsafe_allow_html=True)
        date_to = st.date_input(
            "Due Date To", value=None,
            key="otd_date_to", label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with r1c3:
        st.markdown(f"<span style='{LABEL_STYLE}'>Sort By</span>",
                    unsafe_allow_html=True)
        sort_by = st.selectbox(
            "Sort By",
            options=["On-Time (Highest)", "Delay (Highest)", "Not Collected (Highest)"],
            index=0, key="otd_sort_by",
            label_visibility="collapsed",
            help=(
                "On-Time (Highest)       — customers with best on-time rate first\n"
                "Delay (Highest)         — customers with most delays first\n"
                "Not Collected (Highest) — customers with most uncollected invoices first"
            ),
        )

    # Apply date filter
    df_dated = df.copy()
    if date_from:
        df_dated = df_dated[
            df_dated["OriginalDueDate"] >= pd.Timestamp(date_from)
        ]
    if date_to:
        df_dated = df_dated[
            df_dated["OriginalDueDate"] <= pd.Timestamp(date_to)
        ]

    if df_dated.empty:
        st.warning("No data in the selected date range.")
        return

    # ------------------------------------------------------------------
    # Customer summary
    # นับเฉพาะ invoice rows (OverdueAmount > 0) ซึ่ง filter แล้วข้างบน
    # ------------------------------------------------------------------
    cust_summary = (
        df_dated.groupby("_DisplayName")
        .agg(
            OnTimeCount  =("PaidOnTime",    "sum"),
            LateCount    =("PaidLate",      "sum"),
            NotCollCount =("NotCollected",  "sum"),
            TotalInvoices=("OverdueAmount", "count"),  # นับ invoice rows
        )
        .reset_index()
        .rename(columns={"_DisplayName": "CustomerName"})
    )

    cust_summary["OnTimePct"] = (
        cust_summary["OnTimeCount"]
        / cust_summary["TotalInvoices"].replace(0, np.nan) * 100
    ).fillna(0.0)
    cust_summary["LatePct"] = (
        cust_summary["LateCount"]
        / cust_summary["TotalInvoices"].replace(0, np.nan) * 100
    ).fillna(0.0)

    sort_col_map = {
        "On-Time (Highest)":       ("OnTimePct",    False),
        "Delay (Highest)":         ("LatePct",      False),
        "Not Collected (Highest)": ("NotCollCount", False),
    }
    sort_col_name, sort_asc = sort_col_map[sort_by]
    cust_summary = (
        cust_summary
        .sort_values(sort_col_name, ascending=sort_asc)
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # Search + Selectbox
    # ------------------------------------------------------------------
    lf1, lf2, _ = st.columns([2.5, 1.4, 2.1])
    with lf1:
        st.markdown(f"<span style='{LABEL_STYLE}'>Customer Search</span>",
                    unsafe_allow_html=True)
        search_query = st.text_input(
            "Customer Search",
            placeholder="Type name to search...",
            key="otd_search",
            label_visibility="collapsed",
        ).strip()
    with lf2:
        st.markdown(f"<span style='{LABEL_STYLE}'>Period (Trend)</span>",
                    unsafe_allow_html=True)
        gran_options  = ["Monthly", "Quarterly", "Yearly"]
        default_index = (
            gran_options.index(granularity)
            if granularity in gran_options else 0
        )
        local_gran = st.selectbox(
            "Period (Trend)", gran_options,
            index=default_index, key="otd_local_gran",
            label_visibility="collapsed",
        )

    if search_query:
        q = search_query.lower()
        filtered_names = [
            n for n in cust_summary["CustomerName"].tolist()
            if q in str(n).lower()
        ]
    else:
        filtered_names = cust_summary["CustomerName"].tolist()

    if not filtered_names:
        st.warning(f"No customer matched '{search_query}'.")
        return

    st.markdown(
        f"<div style='font-size:0.72rem;color:#8A9BB0;margin-bottom:4px'>"
        f"{len(filtered_names)} result(s)"
        + (f" — search: {search_query}" if search_query else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    prev_key   = st.session_state.get("otd_customer_select")
    default_ix = (
        filtered_names.index(prev_key)
        if prev_key and prev_key in filtered_names else 0
    )
    selected_customer = st.selectbox(
        "Select Customer", filtered_names,
        index=default_ix, key="otd_customer_select",
    )

    # ------------------------------------------------------------------
    # Filter for selected customer + Period
    # ------------------------------------------------------------------
    df_cust = df_dated[df_dated["_DisplayName"] == selected_customer].copy()
    if df_cust.empty:
        st.info(f"No data for {selected_customer}.")
        return

    if local_gran == "Yearly":
        df_cust["_Period"] = df_cust["DueYear"].astype(str)
        period_sort_cols   = ["DueYear"]
    elif local_gran == "Quarterly":
        df_cust["_Period"] = (
            df_cust["DueYear"].astype(str)
            + "-Q" + df_cust["DueQuarter"].astype(str)
        )
        period_sort_cols = ["DueYear", "DueQuarter"]
    else:
        df_cust["_Period"] = (
            df_cust["DueYear"].astype(str)
            + "-" + df_cust["DueMonthLabel"].fillna("")
        )
        period_sort_cols = ["DueYear", "DueMonth"]

    grp = (
        df_cust.groupby("_Period")
        .agg(
            OnTime =("PaidOnTime",    "sum"),
            Late   =("PaidLate",     "sum"),
            NotColl=("NotCollected", "sum"),
            Total  =("OverdueAmount","count"),
        )
        .reset_index()
    )
    sort_helper = (
        df_cust[["_Period"] + period_sort_cols]
        .drop_duplicates("_Period")
    )
    grp = (
        grp.merge(sort_helper, on="_Period", how="left")
        .sort_values(period_sort_cols)
        .drop_duplicates("_Period")
        .reset_index(drop=True)
    )

    if grp.empty:
        st.info("No period data for this customer.")
        return

    # ------------------------------------------------------------------
    # KPI values
    # ------------------------------------------------------------------
    cust_row     = cust_summary[cust_summary["CustomerName"] == selected_customer]
    total_inv    = int(cust_row["TotalInvoices"].iloc[0]) if not cust_row.empty else 0
    total_ontime = int(cust_row["OnTimeCount"].iloc[0])   if not cust_row.empty else 0
    total_late   = int(cust_row["LateCount"].iloc[0])     if not cust_row.empty else 0
    total_notcol = int(cust_row["NotCollCount"].iloc[0])  if not cust_row.empty else 0
    ontime_pct   = float(cust_row["OnTimePct"].iloc[0])   if not cust_row.empty else 0.0
    late_pct     = float(cust_row["LatePct"].iloc[0])     if not cust_row.empty else 0.0
    notcol_pct   = (total_notcol / total_inv * 100)       if total_inv else 0.0

    # KPI strip
    st.markdown(
        f"<div style='font-size:0.85rem;font-weight:600;color:#3a4a60;"
        f"margin-bottom:8px'>{selected_customer}</div>",
        unsafe_allow_html=True,
    )
    k1, k2, k3 = st.columns(3, gap="small")
    for col_kpi, label_kpi, pct_kpi, sub_kpi in [
        (k1, "On-Time Rate",
         ontime_pct, f"{total_ontime:,} of {total_inv:,} invoices"),
        (k2, "Late (Delay) Rate",
         late_pct,   f"{total_late:,} invoices delayed"),
        (k3, "Not Collected",
         notcol_pct, f"{total_notcol:,} invoices uncollected"),
    ]:
        with col_kpi:
            st.markdown(
                f"<div style='border:1px solid #d0dae6;"
                f"border-left:3px solid #2c3540;"
                f"border-radius:6px;padding:10px 14px;background:#ffffff'>"
                f"<div style='font-size:0.68rem;font-weight:600;color:#6b7685;"
                f"letter-spacing:0.05em;text-transform:uppercase;margin-bottom:4px'>"
                f"{label_kpi}</div>"
                f"<div style='font-size:1.25rem;font-weight:700;color:#2c3540;"
                f"line-height:1.3'>{pct_kpi:.1f}%</div>"
                f"<div style='font-size:0.70rem;color:#8A9BB0;margin-top:2px'>"
                f"{sub_kpi}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-bottom:0.75rem'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    col_line, col_pie = st.columns([3, 2], gap="medium")

    with col_line:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=grp["_Period"].tolist(), y=grp["OnTime"].tolist(),
            mode="none", fill="tozeroy",
            fillcolor="rgba(26,122,74,0.07)",
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=grp["_Period"].tolist(), y=grp["OnTime"].tolist(),
            mode="lines+markers", name="On-Time",
            line=dict(color=PALETTE["jade_lt"], width=2.5),
            marker=dict(
                size=7,
                color=[
                    PALETTE["jade"] if v >= grp["OnTime"].mean() else PALETTE["amber_lt"]
                    for v in grp["OnTime"]
                ],
                line=dict(color="white", width=1.5),
            ),
            customdata=list(zip(grp["OnTime"].tolist(), grp["Total"].tolist())),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "On-Time : %{customdata[0]:,} invoices<br>"
                "Total   : %{customdata[1]:,} invoices"
                "<extra></extra>"
            ),
        ))
        fig.add_trace(go.Scatter(
            x=grp["_Period"].tolist(), y=grp["Late"].tolist(),
            mode="lines+markers", name="Late (Delay)",
            line=dict(color=PALETTE["amber"], width=2.5, dash="dot"),
            marker=dict(
                symbol="diamond", size=7,
                color=[
                    PALETTE["crimson"] if v >= grp["Late"].mean() else PALETTE["amber"]
                    for v in grp["Late"]
                ],
                line=dict(color="white", width=1.5),
            ),
            customdata=list(zip(grp["Late"].tolist(), grp["Total"].tolist())),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Late    : %{customdata[0]:,} invoices<br>"
                "Total   : %{customdata[1]:,} invoices"
                "<extra></extra>"
            ),
        ))
        apply_base_layout(fig, {
            "height": 320,
            "margin": dict(l=0, r=12, t=40, b=64),
            "title": dict(
                text=f"{selected_customer} — On-Time vs Delay Trend ({local_gran})",
                font=dict(size=11, color=FONT_COLOR),
                x=0, xanchor="left",
            ),
            "xaxis": dict(
                showgrid=False, color=FONT_COLOR,
                tickangle=-35, tickfont=dict(size=8),
            ),
            "yaxis": dict(
                title="Invoice Count",
                showgrid=True, gridcolor=GRID_COLOR,
                color=FONT_COLOR, tickfont=dict(size=9),
                rangemode="tozero",
            ),
            "legend": dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                font=dict(size=9),
            ),
            "showlegend": True,
        })
        st.plotly_chart(fig, use_container_width=True, key="chart_ontime_trend")

    with col_pie:
        pie_data = [
            ("On-Time",      total_ontime, PALETTE["jade_lt"]),
            ("Late",         total_late,   PALETTE["amber"]),
            ("Not Collected",total_notcol, PALETTE["crimson"]),
        ]
        pie_data = [(l, v, c) for l, v, c in pie_data if v > 0]
        if pie_data:
            fig_pie = go.Figure(go.Pie(
                labels=[d[0] for d in pie_data],
                values=[d[1] for d in pie_data],
                marker=dict(
                    colors=[d[2] for d in pie_data],
                    line=dict(color="white", width=2),
                ),
                hole=0.45,
                textinfo="label+percent",
                textfont=dict(size=10),
                hovertemplate=(
                    "%{label}<br>%{value:,} invoices<br>%{percent}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
            fig_pie.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
                title=dict(
                    text=f"Payment Breakdown — {total_inv:,} invoices",
                    font=dict(size=10, color=FONT_COLOR), x=0,
                ),
            )
            st.plotly_chart(
                fig_pie, use_container_width=True, key="chart_ontime_pie"
            )


# =============================================================================
# SECTION 5A — Aging Bucket Bar
# =============================================================================
DPD_BUCKETS = ["Current", "1-30", "31-60", "61-90", "91-180", "181-365", "365+"]
BUCKET_COLORS = [
    PALETTE["jade_lt"], PALETTE["sapphire_lt"], PALETTE["sapphire"],
    PALETTE["amber_lt"], PALETTE["amber"], PALETTE["crimson"], "#6B0F1A",
]

def _render_aging_bar(df: pd.DataFrame):
    if "IsOverdue" not in df.columns or "OverdueAbs" not in df.columns:
        st.info("Aging data not available.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records for aging chart.")
        return

    def _bucket(dpd):
        if pd.isna(dpd) or dpd <= 0: return "Current"
        elif dpd <= 30:   return "1-30"
        elif dpd <= 60:   return "31-60"
        elif dpd <= 90:   return "61-90"
        elif dpd <= 180:  return "91-180"
        elif dpd <= 365:  return "181-365"
        else:             return "365+"

    if "DPD" in overdue_df.columns:
        overdue_df["_bucket"] = overdue_df["DPD"].apply(_bucket)
    else:
        overdue_df["_bucket"] = "Current"

    hist = (
        overdue_df.groupby("_bucket")
        .agg(TotalOverdue=("OverdueAbs", "sum"), CustCount=("Customer", "nunique"))
        .reindex(DPD_BUCKETS, fill_value=0)
        .reset_index()
        .rename(columns={"_bucket": "Bucket"})
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x            = hist["Bucket"].tolist(),
        y            = hist["TotalOverdue"].tolist(),
        marker_color = BUCKET_COLORS,
        text         = [f"{v:,.0f}" for v in hist["TotalOverdue"]],
        textposition = "outside",
        cliponaxis   = False,
        textfont     = dict(size=8, color=FONT_COLOR),
        customdata   = hist["CustCount"].tolist(),
        hovertemplate= (
            "<b>%{x}</b><br>"
            "Overdue Amount : %{y:,.0f} THB<br>"
            "Customers      : %{customdata}<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=20, t=30, b=10),
        "title":  dict(
            text = "Aging Distribution — Overdue by DPD Bucket",
            font = dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            showgrid      = False, color=FONT_COLOR,
            tickfont      = dict(size=9),
            categoryorder = "array", categoryarray=DPD_BUCKETS,
        ),
        "yaxis": dict(
            title    = "Overdue Amount (THB)",
            showgrid = True, gridcolor=GRID_COLOR,
            color    = FONT_COLOR, tickfont=dict(size=9),
        ),
        "showlegend": False,
        "bargap":     0.28,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_mon_aging")


# =============================================================================
# SECTION 5B — Top Overdue Customers Bar
# =============================================================================
def _render_top_overdue(df: pd.DataFrame, top_n: int = 12):
    if "IsOverdue" not in df.columns or "OverdueAbs" not in df.columns:
        st.info("Overdue data not available.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    name_col   = "CustomerName" if "CustomerName" in overdue_df.columns else "Customer"

    if overdue_df.empty:
        st.info("No overdue records to display.")
        return

    grouped = (
        overdue_df.groupby(name_col)
        .agg(TotalOverdue=("OverdueAbs", "sum"), DPD=("DPD", "max"))
        .reset_index()
        .sort_values("TotalOverdue", ascending=False)
        .head(top_n)
        .sort_values("TotalOverdue", ascending=True)
        .reset_index(drop=True)
    )

    q75 = grouped["TotalOverdue"].quantile(0.75)
    bar_colors = [
        PALETTE["crimson"] if v >= q75 else PALETTE["amber_lt"]
        for v in grouped["TotalOverdue"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y            = grouped[name_col].astype(str).tolist(),
        x            = grouped["TotalOverdue"].tolist(),
        orientation  = "h",
        marker_color = bar_colors,
        text         = [f"{v:,.0f}" for v in grouped["TotalOverdue"]],
        textposition = "outside",
        cliponaxis   = False,
        textfont     = dict(size=8, color=FONT_COLOR),
        customdata   = grouped["DPD"].tolist(),
        hovertemplate= (
            "<b>%{y}</b><br>"
            "Overdue : %{x:,.0f} THB<br>"
            "Max DPD : %{customdata} days<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=80, t=30, b=10),
        "title":  dict(
            text = f"Top {top_n} Overdue Customers",
            font = dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title    = "Overdue Amount (THB)",
            showgrid = True, gridcolor=GRID_COLOR,
            color    = FONT_COLOR, tickfont=dict(size=9),
        ),
        "yaxis": dict(
            showgrid = False, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_mon_top_overdue")


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


# =============================================================================
# SECTION 7 — Credit Risk Propagation + Community Detection
# =============================================================================
def _compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    RiskScore = 0.4×Util_norm + 0.3×DPD_norm + 0.3×OverdueRatio_norm

    Data handling standard (robust):
      1. Winsorize ที่ p95 ก่อน — ตัด extreme outlier
      2. log1p transform — จัดการ zero-inflated + right-skewed
      3. Percentile rank normalize — กระจาย 0-1 เสมอ ไม่ขึ้นกับ scale
      4. Fallback ทุกจุด — ไม่ crash เมื่อ all-zero หรือ n=1
    """
    cust = _agg_customer_overdue(df)
    if cust.empty:
        return pd.DataFrame()

    for col in ("UtilizationPct", "MaxDPD", "NetOverdue"):
        if col not in cust.columns:
            cust[col] = 0.0
        cust[col] = pd.to_numeric(cust[col], errors="coerce").fillna(0.0)

    n = len(cust)

    def _robust_norm(series: pd.Series) -> pd.Series:
        """
        Winsorize p95 → log1p → percentile rank → 0..1
        คืน Series เดิมถ้าทุกค่าเป็น 0 หรือ n <= 1
        """
        s = series.fillna(0.0).clip(lower=0.0)

        if n <= 1 or s.max() == 0:
            return pd.Series([0.0] * n, index=series.index)

        # Winsorize: cap ที่ p95 เพื่อตัด outlier ก่อน transform
        p95 = float(s.quantile(0.95))
        if p95 > 0:
            s = s.clip(upper=p95)

        # log1p: จัดการ zero-inflated distribution
        s = np.log1p(s)

        # Percentile rank: กระจาย 0-1 เสมอ ไม่ขึ้นกับ scale ของข้อมูล
        if s.max() == s.min():
            return pd.Series([0.0] * n, index=series.index)

        ranked = (s.rank(method="average", na_option="bottom") - 1) / max(n - 1, 1)
        return ranked.clip(0.0, 1.0)

    cust["Util_norm"]         = _robust_norm(cust["UtilizationPct"])
    cust["DPD_norm"]          = _robust_norm(cust["MaxDPD"])
    cust["OverdueRatio_norm"] = _robust_norm(cust["NetOverdue"])

    cust["RiskScore"] = (
        0.4 * cust["Util_norm"]
        + 0.3 * cust["DPD_norm"]
        + 0.3 * cust["OverdueRatio_norm"]
    ).clip(0.0, 1.0).round(4)

    # Re-rank RiskScore สุดท้ายอีกรอบ — ให้กระจายเต็ม 0-1 เสมอ
    if n > 1 and cust["RiskScore"].max() > cust["RiskScore"].min():
        cust["RiskScore"] = (
            (cust["RiskScore"].rank(method="average") - 1) / max(n - 1, 1)
        ).clip(0.0, 1.0).round(4)

    return cust.reset_index(drop=True)


def _louvain_approx(n: int, edges: list) -> list:
    """
    Louvain approximation (pure Python)
    คืน list ขนาด n: community[i] = community id ของ node i
    """
    community = list(range(n))
    adj = defaultdict(list)
    for i, j, _ in edges:
        adj[i].append(j)
        adj[j].append(i)

    for _ in range(20):
        changed = False
        order = list(range(n))
        random.shuffle(order)
        for node in order:
            neighbors = adj[node]
            if not neighbors:
                continue
            count = defaultdict(int)
            for nb in neighbors:
                count[community[nb]] += 1
            best = max(count, key=count.get)
            if community[node] != best:
                community[node] = best
                changed = True
        if not changed:
            break

    unique = sorted(set(community))
    remap = {old: new for new, old in enumerate(unique)}
    return [remap[c] for c in community]


def _leiden_approx(n: int, edges: list) -> list:
    """
    Leiden approximation (pure Python)
    เพิ่ม refinement step หลัง Louvain
    """
    community = _louvain_approx(n, edges)
    adj = defaultdict(list)
    for i, j, _ in edges:
        adj[i].append(j)
        adj[j].append(i)

    # Refinement: node ที่ community เดียวกันแต่ไม่ connected ให้แยก
    for node in range(n):
        same_comm = [
            nb for nb in adj[node]
            if community[nb] == community[node]
        ]
        if not same_comm and adj[node]:
            neighbor_comms = [community[nb] for nb in adj[node]]
            count = defaultdict(int)
            for c in neighbor_comms:
                count[c] += 1
            community[node] = max(count, key=count.get)

    unique = sorted(set(community))
    remap = {old: new for new, old in enumerate(unique)}
    return [remap[c] for c in community]


def _build_edges(cust: pd.DataFrame, threshold: float, max_edges: int = 500) -> list:
    """
    Edge condition: |RiskScore_i - RiskScore_j| <= threshold
    """
    scores = cust["RiskScore"].fillna(0.0).tolist()
    n      = len(scores)
    edges  = []

    for i in range(n):
        for j in range(i + 1, n):
            diff = abs(scores[i] - scores[j])
            if diff <= threshold:
                edges.append((i, j, round(diff, 4)))

    edges.sort(key=lambda x: x[2])
    return edges[:max_edges]


def _render_risk_propagation(df: pd.DataFrame):
    need = {"Customer", "OverdueAmount", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("ข้อมูลไม่เพียงพอสำหรับ Risk Propagation Analysis")
        return

    cust_risk = _compute_risk_score(df)
    if cust_risk.empty:
        st.info("ไม่มีข้อมูล overdue ในชุดข้อมูลที่เลือก")
        return

    LABEL_STYLE = (
        "font-size:0.75rem;font-weight:600;color:#3a4a60;"
        "letter-spacing:0.01em;margin-bottom:3px;display:block"
    )

    # ------------------------------------------------------------------
    # Controls row 1 — Top N / Threshold / Algorithm
    # ------------------------------------------------------------------
    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.8, 1.2], gap="medium")

    with ctrl1:
        st.markdown(f"<span style='{LABEL_STYLE}'>Top N Customers</span>",
                    unsafe_allow_html=True)
        top_n = st.slider(
            "Top N Customers",
            min_value=5, max_value=min(100, len(cust_risk)),
            value=min(40, len(cust_risk)),
            step=5, key="prop_top_n",
            label_visibility="collapsed",
        )

    with ctrl2:
        risk_std       = float(cust_risk["RiskScore"].std()) if len(cust_risk) > 1 else 0.1
        default_thresh = round(float(np.clip(risk_std, 0.05, 0.5)), 2)
        st.markdown(
            f"<span style='{LABEL_STYLE}'>"
            "Edge Threshold (RiskScore diff)"
            " <span style='font-weight:400;color:#8A9BB0;font-size:0.7rem'>"
            "| Edge = |RiskScore_i &minus; RiskScore_j| &le; threshold</span>"
            "</span>",
            unsafe_allow_html=True,
        )
        threshold = st.slider(
            "Edge Threshold",
            min_value=0.01, max_value=1.0,
            value=default_thresh,
            step=0.01, key="prop_threshold",
            label_visibility="collapsed",
        )

    with ctrl3:
        st.markdown(f"<span style='{LABEL_STYLE}'>Community Algorithm</span>",
                    unsafe_allow_html=True)
        algorithm = st.selectbox(
            "Community Algorithm",
            options=["Leiden", "Louvain"],
            index=0, key="prop_algo",
            label_visibility="collapsed",
        )

    st.markdown(
        "<div style='font-size:0.71rem;color:#8A9BB0;margin-bottom:8px'>"
        "X = RiskScore &nbsp;|&nbsp; Y = Credit Utilization (Debt %)"
        " &nbsp;|&nbsp; Node size = Net Overdue &nbsp;|&nbsp; Color = Community"
        "</div>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Filter Top N → edges → communities
    # ------------------------------------------------------------------
    cust_top = (
        cust_risk
        .sort_values("NetOverdue", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    n_top = len(cust_top)

    cust_top["UtilizationPct"] = cust_top["UtilizationPct"].fillna(0.0)
    cust_top["RiskScore"]      = cust_top["RiskScore"].fillna(0.0)

    edges         = _build_edges(cust_top, threshold, max_edges=500)
    n_edges       = len(edges)
    communities   = (
        _leiden_approx(n_top, edges)
        if algorithm == "Leiden"
        else _louvain_approx(n_top, edges)
    )
    cust_top["Community"] = communities
    n_communities         = len(set(communities))

    # ------------------------------------------------------------------
    # Controls row 2 — Community filter + Risk filter
    # ------------------------------------------------------------------
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1.5, 1.5, 1.5], gap="small")

    all_communities = sorted(cust_top["Community"].unique().tolist())
    with f1:
        st.markdown(f"<span style='{LABEL_STYLE}'>Filter Community</span>",
                    unsafe_allow_html=True)
        sel_communities = st.multiselect(
            "Filter Community",
            options=all_communities,
            default=all_communities,
            key="prop_comm_filter",
            label_visibility="collapsed",
            format_func=lambda x: f"Community {x}",
        )

    with f2:
        st.markdown(f"<span style='{LABEL_STYLE}'>Min RiskScore</span>",
                    unsafe_allow_html=True)
        min_risk = st.slider(
            "Min RiskScore",
            min_value=0.0, max_value=1.0,
            value=0.0, step=0.05,
            key="prop_min_risk",
            label_visibility="collapsed",
        )

    with f3:
        st.markdown(f"<span style='{LABEL_STYLE}'>Min Utilization %</span>",
                    unsafe_allow_html=True)
        min_util = st.slider(
            "Min Utilization %",
            min_value=0, max_value=100,
            value=0, step=5,
            key="prop_min_util",
            label_visibility="collapsed",
        )

    # Apply local filters
    mask = (
        cust_top["Community"].isin(sel_communities)
        & (cust_top["RiskScore"]      >= min_risk)
        & (cust_top["UtilizationPct"] >= min_util)
    )
    cust_plot = cust_top[mask].copy().reset_index(drop=True)
    n_plot    = len(cust_plot)

    # rebuild edges บน cust_plot ที่ filter แล้ว
    edges_plot = _build_edges(cust_plot, threshold, max_edges=500)
    n_edges_plot = len(edges_plot)

    # ------------------------------------------------------------------
    # KPI Row
    # ------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4, gap="small")
    avg_util = float(cust_plot["UtilizationPct"].mean()) if not cust_plot.empty else 0.0
    kpi_items = [
        ("Customers",      f"{n_plot}",          f"Top {top_n} → filtered {n_plot}"),
        ("Edges",          f"{n_edges_plot:,}",   f"Threshold = {threshold:.2f}"),
        ("Communities",    f"{n_communities}",    algorithm),
        ("Avg Utilization",f"{avg_util:.1f}%",
                           f"Max = {cust_plot['UtilizationPct'].max():.1f}%"
                           if not cust_plot.empty else "Max = 0%"),
    ]
    for col, (lbl, val, sub) in zip([k1, k2, k3, k4], kpi_items):
        with col:
            st.markdown(
                f"<div style='border:1px solid #d0dae6;border-radius:6px;"
                f"padding:10px 14px;background:#ffffff'>"
                f"<div style='font-size:0.68rem;font-weight:600;color:#8A9BB0;"
                f"letter-spacing:0.06em;text-transform:uppercase'>{lbl}</div>"
                f"<div style='font-size:1.35rem;font-weight:700;color:#3a4a60;"
                f"line-height:1.3;margin:2px 0'>{val}</div>"
                f"<div style='font-size:0.70rem;color:#8A9BB0'>{sub}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if cust_plot.empty:
        st.info("ไม่มีข้อมูลหลัง filter — ลองปรับ Min RiskScore หรือ Min Utilization")
        return

    if n_communities == 1 and min_risk == 0 and min_util == 0:
        st.warning(
            f"Community detection พบเพียง 1 cluster — "
            f"ลอง ลด Edge Threshold (ปัจจุบัน {threshold:.2f}) หรือ เพิ่ม Top N"
        )

    st.markdown("<div style='margin-bottom:0.8rem'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Jitter Y เพื่อป้องกัน label ทับซ้อน
    # node ที่ UtilizationPct ใกล้กัน → เพิ่ม small random offset
    # ------------------------------------------------------------------
    rng = np.random.default_rng(seed=42)  # seed คงที่ ผลลัพธ์ไม่เปลี่ยนทุก rerun

    util_vals  = cust_plot["UtilizationPct"].values.copy()
    util_range = float(util_vals.max() - util_vals.min()) if len(util_vals) > 1 else 1.0
    jitter_scale = max(util_range * 0.025, 0.5)  # 2.5% ของ range หรือ 0.5% ขั้นต่ำ

    cust_plot["Y_jitter"] = util_vals + rng.uniform(
        -jitter_scale, jitter_scale, size=len(cust_plot)
    )

    # textposition สลับตาม RiskScore quadrant เพื่อกระจาย label
    def _text_pos(risk: float) -> str:
        if risk < 0.33:
            return "top right"
        elif risk < 0.66:
            return "top center"
        else:
            return "top left"

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    COMM_COLORS = [
        "#1B4F8A", "#A01F2D", "#2A9D8F",
        "#B5620A", "#5C3D8F", "#3D5166",
        "#D7263D", "#1A7A4A", "#E8A838",
    ]

    label_col = "CustomerName" if "CustomerName" in cust_plot.columns else "Customer"
    max_ov    = float(cust_plot["NetOverdue"].max()) or 1.0
    util_max  = float(max(cust_plot["Y_jitter"].max() * 1.12, 110.0))

    fig = go.Figure()

    # Background zones
    for y0, y1, rgba in [
        (0,   50,       "rgba(42,157,143,0.05)"),
        (50,  80,       "rgba(232,168,56,0.05)"),
        (80,  util_max, "rgba(160,31,45,0.05)"),
    ]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=rgba, line_width=0)

    for y_ann, lbl_ann, clr_ann in [
        (25,  "Low Util",  PALETTE["jade_lt"]),
        (65,  "Med Util",  PALETTE["amber"]),
        (90,  "High Util", PALETTE["crimson"]),
    ]:
        fig.add_annotation(
            x=1.02, y=y_ann, xref="paper", yref="y",
            text=f"<b>{lbl_ann}</b>", showarrow=False,
            font=dict(size=8, color=clr_ann),
            xanchor="left", yanchor="middle",
        )

    # ------------------------------------------------------------------
    # Edges — ลด opacity 30% จากเดิม (0.15–0.55 → 0.10–0.38)
    # ------------------------------------------------------------------
    for i, j, diff in edges_plot:
        if i >= n_plot or j >= n_plot:
            continue
        xi = float(cust_plot.loc[i, "RiskScore"])
        xj = float(cust_plot.loc[j, "RiskScore"])
        yi = float(cust_plot.loc[i, "Y_jitter"])
        yj = float(cust_plot.loc[j, "Y_jitter"])
        norm_diff = diff / max(threshold, 0.01)
        # ลด 30%: 0.55 × 0.7 = 0.385, 0.15 × 0.7 = 0.105
        opacity = round(max(0.10, 0.385 * (1 - norm_diff)), 2)
        fig.add_trace(go.Scatter(
            x=[xi, xj, None], y=[yi, yj, None],
            mode="lines",
            line=dict(width=1.2, color=f"rgba(80,100,130,{opacity})"),
            hoverinfo="skip", showlegend=False,
        ))

    # ------------------------------------------------------------------
    # Nodes — label เฉพาะจุดสำคัญ
    # เกณฑ์เลือก:
    #   1. Top overdue (NetOverdue >= p75)
    #   2. Outlier ขอบ (RiskScore >= p90 หรือ UtilizationPct >= p90)
    #   3. จำกัดสูงสุด max_labels จุด เพื่อไม่รกจอ
    # ------------------------------------------------------------------
    MAX_LABEL_LEN = 15
    max_labels    = max(5, n_plot // 4)   # แสดงไม่เกิน 25% ของทั้งหมด

    if not cust_plot.empty:
        p75_ov   = float(cust_plot["NetOverdue"].quantile(0.75))
        p90_risk = float(cust_plot["RiskScore"].quantile(0.90))
        p90_util = float(cust_plot["UtilizationPct"].quantile(0.90))

        important_mask = (
            (cust_plot["NetOverdue"]    >= p75_ov)   |
            (cust_plot["RiskScore"]     >= p90_risk) |
            (cust_plot["UtilizationPct"]>= p90_util)
        )
        # เรียง overdue descending แล้วเลือก top max_labels
        important_idx = set(
            cust_plot[important_mask]
            .sort_values("NetOverdue", ascending=False)
            .head(max_labels)
            .index.tolist()
        )
    else:
        important_idx = set()

    for comm_id in sorted(cust_plot["Community"].unique()):
        grp = cust_plot[cust_plot["Community"] == comm_id].copy()
        if grp.empty:
            continue

        sizes = (
            8 + (grp["NetOverdue"] / max_ov) * 36
        ).clip(lower=8, upper=44).tolist()

        # label: แสดงเฉพาะ important nodes, ที่เหลือ empty string
        labels = []
        text_positions = []
        for idx, row in grp.iterrows():
            if idx in important_idx:
                raw = str(row[label_col])
                lbl = (raw[:MAX_LABEL_LEN] + "..") if len(raw) > MAX_LABEL_LEN else raw
                labels.append(lbl)
            else:
                labels.append("")
            text_positions.append(_text_pos(float(row["RiskScore"])))

        hover = []
        for _, row in grp.iterrows():
            hover.append(
                f"<b>{row[label_col]}</b><br>"
                f"RiskScore    : {row['RiskScore']:.3f}<br>"
                f"Utilization  : {row['UtilizationPct']:.1f}%<br>"
                f"Max DPD      : {row.get('MaxDPD', 0):.0f} days<br>"
                f"Net Overdue  : {row['NetOverdue']:,.0f} THB<br>"
                f"Gross Overdue: {row.get('GrossOverdue', 0):,.0f} THB<br>"
                f"Credit Note  : {row.get('CreditNoteOffset', 0):,.0f} THB<br>"
                f"Community    : {comm_id}"
            )

        fig.add_trace(go.Scatter(
            x=grp["RiskScore"].tolist(),
            y=grp["Y_jitter"].tolist(),
            mode="markers+text",
            name=f"Community {comm_id}",
            marker=dict(
                size=sizes,
                color=COMM_COLORS[comm_id % len(COMM_COLORS)],
                opacity=0.85,
                line=dict(width=1.5, color="white"),
                sizemode="diameter",
            ),
            text=labels,
            textposition=text_positions,
            textfont=dict(size=8, color="#3a4a60"),
            hovertext=hover,
            hoverinfo="text",
        ))

    for x_ref, lbl_ref, clr_ref in [
        (0.33, "Low|Med",  PALETTE["jade_lt"]),
        (0.66, "Med|High", PALETTE["crimson"]),
    ]:
        fig.add_vline(
            x=x_ref, line_dash="dot",
            line_color=clr_ref, line_width=1, opacity=0.5,
            annotation_text=lbl_ref,
            annotation_font=dict(size=8, color=clr_ref),
            annotation_position="top right",
        )

    for y_ref, clr_ref in [(50, PALETTE["amber"]), (80, PALETTE["crimson"])]:
        fig.add_hline(
            y=y_ref, line_dash="dot",
            line_color=clr_ref, line_width=1, opacity=0.5,
        )

    apply_base_layout(fig, {
        "height": 560,
        "margin": dict(l=20, r=90, t=50, b=60),
        "title": dict(
            text=(
                f"Credit Risk Propagation — {algorithm}"
                f" | Edges: {n_edges_plot:,}"
                f" | Communities: {n_communities}"
            ),
            font=dict(size=11, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title="RiskScore",
            range=[-0.02, 1.05],
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            zeroline=False,
        ),
        "yaxis": dict(
            title="Credit Utilization (Debt %)",
            ticksuffix="%",
            range=[-2, util_max],
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            zeroline=False,
        ),
        "legend": dict(
            orientation="h",
            yanchor="bottom", y=0.01,
            xanchor="right",  x=0.99,
            font=dict(size=9),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#d0dae6", borderwidth=1,
        ),
        "showlegend": True,
    })

    st.plotly_chart(fig, use_container_width=True, key="chart_risk_propagation")

    # ------------------------------------------------------------------
    # Community Detail Table
    # ------------------------------------------------------------------
    with st.expander("Community Detail Table", expanded=True):
        comm_rows = []
        for comm_id in sorted(cust_plot["Community"].unique()):
            grp = cust_plot[cust_plot["Community"] == comm_id]
            comm_rows.append({
                "Community":           comm_id,
                "Customers":           len(grp),
                "Avg RiskScore":       round(float(grp["RiskScore"].mean()), 3),
                "Max RiskScore":       round(float(grp["RiskScore"].max()), 3),
                "Avg Util %":          round(float(grp["UtilizationPct"].mean()), 1),
                "Max Util %":          round(float(grp["UtilizationPct"].max()), 1),
                "Net Overdue (THB)":   round(float(grp["NetOverdue"].sum()), 0),
                "Gross Overdue (THB)": round(float(grp["GrossOverdue"].sum()), 0)
                    if "GrossOverdue" in grp.columns else 0,
                "Credit Note (THB)":   round(float(grp["CreditNoteOffset"].sum()), 0)
                    if "CreditNoteOffset" in grp.columns else 0,
                "Max DPD (days)":      int(grp["MaxDPD"].max())
                    if "MaxDPD" in grp.columns else 0,
                "Top Members": ", ".join(
                    grp.sort_values("NetOverdue", ascending=False)
                    [label_col].astype(str).head(4).tolist()
                ) + ("..." if len(grp) > 4 else ""),
            })

        comm_df     = pd.DataFrame(comm_rows).sort_values("Avg RiskScore", ascending=False)
        max_score_v = float(comm_df["Max RiskScore"].max()) if not comm_df.empty else 1.0

        st.dataframe(
            comm_df,
            use_container_width=True,
            hide_index=True,
            height=min(380, 60 + len(comm_df) * 42),
            column_config={
                "Community":           st.column_config.NumberColumn("Cluster",      width="small"),
                "Customers":           st.column_config.NumberColumn("Customers",    width="small"),
                "Avg RiskScore":       st.column_config.ProgressColumn(
                                           "Avg RiskScore", min_value=0,
                                           max_value=max_score_v, width="medium"),
                "Max RiskScore":       st.column_config.NumberColumn("Max RiskScore", format="%.3f", width="small"),
                "Avg Util %":          st.column_config.NumberColumn("Avg Util %",   format="%.1f%%", width="small"),
                "Max Util %":          st.column_config.NumberColumn("Max Util %",   format="%.1f%%", width="small"),
                "Net Overdue (THB)":   st.column_config.NumberColumn("Net Overdue (THB)",   format="%,.0f", width="medium"),
                "Gross Overdue (THB)": st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f", width="medium"),
                "Credit Note (THB)":   st.column_config.NumberColumn("Credit Note (THB)",   format="%,.0f", width="medium"),
                "Max DPD (days)":      st.column_config.NumberColumn("Max DPD",      format="%d days", width="small"),
                "Top Members":         st.column_config.TextColumn("Top Members",    width="large"),
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