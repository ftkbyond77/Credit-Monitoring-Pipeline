# =============================================================================
# views/view_monitoring.py
# Join key : df_overdue.Customer == df_avail.CUSTOMER_CODE
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict
from components import (
    apply_base_layout,
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
    "threshold":   "#C0392B",
}

MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

UTIL_HIGH = 0.80
UTIL_MED  = 0.50
DPD_HIGH  = 60
DPD_MED   = 30

TIER_COLOR = {
    "Critical":  "#A01F2D",
    "High Risk": "#B5620A",
    "Watch":     "#E8A838",
    "Healthy":   "#2A9D8F",
    "Unknown":   "#8A9BB0",
}
TIER_ORDER = ["Critical", "High Risk", "Watch", "Healthy", "Unknown"]

LABEL_STYLE = (
    "font-size:0.75rem;font-weight:600;color:#1B4F8A;"
    "letter-spacing:0.01em;margin-bottom:2px;display:block;line-height:1.4;"
)

def _scale_thb(value: float):
    """
    Return (scaled_value, unit_label) โดย detect จาก magnitude จริงก่อน
    ไม่ trunc ก่อนรู้หน่วย
    """
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return value / 1_000_000_000, "Billion Baht"
    if abs_val >= 1_000_000:
        return value / 1_000_000, "Million Baht"
    if abs_val >= 1_000:
        return value / 1_000, "Thousand Baht"
    return value, "Baht"


def _fmt_thb(value: float, view_type: str) -> str:
    """
    Rounded : scale ลง + floor 1 decimal + หน่วย
              23,118,892,135 → 23.1 Billion Baht
    Detail  : เลขเต็มทุกหลัก .2f + หน่วยบอก magnitude (ไม่ scale)
              23,118,892,135 → 23,118,892,135.00 Baht
              (ไม่เขียนว่า Billion เพราะเลขไม่ได้ scale)
    """
    import math
    abs_val = abs(value)

    if view_type == "Rounded Number":
        if abs_val >= 1_000_000_000:
            floored = math.floor(value / 1_000_000_000 * 10) / 10
            return f"{floored:,.1f} Billion Baht"
        if abs_val >= 1_000_000:
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:,.1f} Million Baht"
        if abs_val >= 1_000:
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:,.1f} Thousand Baht"
        return f"{math.floor(value * 10) / 10:,.1f} Baht"
    else:
        # Detail: เลขเต็ม .2f + "Baht" เท่านั้น ไม่ scale ไม่เขียน Billion/Million
        return f"{value:,.2f} Baht"


def _fmt_pct(value: float, view_type: str) -> str:
    """
    Rounded : floor ที่ 1 decimal — 53.99% → 53.9%
    Detail  : 2 decimal — 53.99%
    """
    import math
    if view_type == "Rounded Number":
        floored = math.floor(value * 10) / 10
        return f"{floored:.1f}%"
    return f"{value:.2f}%"


def _fmt_count(value: int, view_type: str) -> str:
    return f"{value:,}"


def _fmt_bar_mon(value: float, view_type: str) -> str:
    """
    สำหรับ chart bar/axis label — ไม่มี unit suffix ยาว
    Rounded : detect magnitude → 1 decimal + suffix สั้น (B/M/K)
    Detail  : comma + .2f ไม่ scale
    """
    import math
    if view_type == "Rounded Number":
        abs_val = abs(value)
        if abs_val >= 1_000_000_000:
            floored = math.floor(value / 1_000_000_000 * 10) / 10
            return f"{floored:.1f}B"
        if abs_val >= 1_000_000:
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:.1f}M"
        if abs_val >= 1_000:
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:.1f}K"
        return f"{math.floor(value * 10) / 10:.1f}"
    return f"{value:,.2f}"


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
    if vlen <= 8:       v_font = "1.30rem"
    elif vlen <= 14:    v_font = "1.10rem"
    elif vlen <= 22:    v_font = "0.92rem"
    else:               v_font = "0.78rem"

    sub_html = (
        f'<div style="'
        f'font-size:0.68rem;color:#888;margin-top:4px;line-height:1.3;'
        f'overflow:hidden;display:-webkit-box;'
        f'-webkit-line-clamp:2;-webkit-box-orient:vertical;'
        f'word-break:break-word;">{sub}</div>'
        if sub else '<div style="min-height:0.9rem;"></div>'
    )
    return (
        f'<div style="background:{bg};border-left:3px solid {accent};'
        f'border-radius:8px;padding:14px 16px;'
        f'display:grid;grid-template-rows:auto 1fr auto;'
        f'height:110px;box-sizing:border-box;width:100%;">'
        f'<div style="font-size:0.72rem;font-weight:700;color:{accent};'
        f'letter-spacing:0.06em;text-transform:uppercase;margin-bottom:4px;">'
        f'{label}</div>'
        f'<div style="font-size:{v_font};font-weight:800;color:#1a2a3a;'
        f'line-height:1.15;word-break:break-word;align-self:center;">{value}</div>'
        f'{sub_html}'
        f'</div>'
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
            "Credit Monitoring — health snapshot, planning, and historical analysis",
        ),
        unsafe_allow_html=True,
    )

    df_avail_prep   = _prepare_avail(df_avail.copy())
    df_overdue_prep = _prepare_overdue(df_overdue.copy())
    df_joined       = _build_joined(df_avail_prep, df_overdue_prep)

    df_filtered, selected_company, year_filter, view_type = _render_filters(
        df_avail_prep, df_overdue_prep, df_joined
    )

    if df_filtered is None or df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    # ==================================================================
    # ZONE 1 — HEALTH SNAPSHOT
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px;'>"
        "ZONE 1 — HEALTH SNAPSHOT</div>",
        unsafe_allow_html=True,
    )

    st.markdown(section_header("Monitoring Health — Key Signals"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(
        section_header("Credit Health Matrix — Utilization vs Overdue Risk"),
        unsafe_allow_html=True,
    )
    _render_health_matrix_section(df_filtered, df_avail_prep, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(
        section_header("Watchlist — Customers Needing Immediate Attention"),
        unsafe_allow_html=True,
    )
    _render_watchlist(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # ZONE 2 — PLANNING
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px;'>"
        "ZONE 2 — PLANNING</div>",
        unsafe_allow_html=True,
    )

    st.markdown(section_header("Collection Pipeline"), unsafe_allow_html=True)
    _render_collection_pipeline(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(section_header("Cash Inflow Planning"), unsafe_allow_html=True)
    _render_cash_inflow_forecast(df_filtered, view_type) 
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(section_header("Collection Planning"), unsafe_allow_html=True)
    _render_future_collection_forecast(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    st.markdown(section_header("Credit Planner — Action Board"), unsafe_allow_html=True)
    _render_credit_planner_board(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ==================================================================
    # ZONE 3 — HISTORICAL ANALYSIS
    # ==================================================================
    st.markdown(
        "<div style='font-size:0.72rem;font-weight:700;color:#8A9BB0;"
        "text-transform:uppercase;letter-spacing:0.08em;margin:8px 0 4px;'>"
        "ZONE 3 — HISTORICAL ANALYSIS</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        section_header("Credit Journey — Invoice Extension Sankey"),
        unsafe_allow_html=True,
    )
    _render_credit_journey_sankey(df_filtered, view_type)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)


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


def _dedup_avail_for_kpi(df_avail: pd.DataFrame) -> pd.DataFrame:
    """
    Mirror view_avail._dedup_for_kpi:
    Within each (AVAIL_YEAR, month) window, keep first per CUSTOMER_CODE.
    Prevents double-counting when 1 customer has multiple TYPE rows
    sharing the same CLEAN_CREDIT_MB.
    Returns deduped avail DataFrame.
    """
    if "CUSTOMER_CODE" not in df_avail.columns:
        return df_avail

    df = df_avail.copy()
    if "DATE" in df.columns:
        df["_MONTH_TMP"] = pd.to_datetime(df["DATE"], errors="coerce").dt.month
    else:
        df["_MONTH_TMP"] = None

    group_keys = [k for k in ("AVAIL_YEAR", "_MONTH_TMP") if k in df.columns]
    if not group_keys:
        return df.drop_duplicates(subset=["CUSTOMER_CODE"], keep="first").drop(columns=["_MONTH_TMP"], errors="ignore")

    parts = []
    for _, grp in df.groupby(group_keys, sort=False, dropna=False):
        parts.append(grp.drop_duplicates(subset=["CUSTOMER_CODE"], keep="first"))

    result = pd.concat(parts, ignore_index=True)
    return result.drop(columns=["_MONTH_TMP"], errors="ignore")


def _build_joined(df_avail: pd.DataFrame, df_overdue: pd.DataFrame) -> pd.DataFrame:
    if df_avail.empty or df_overdue.empty:
        return df_overdue.copy()

    # Dedup avail ก่อน join — กัน double-count shared credit limit
    avail_dedup = _dedup_avail_for_kpi(df_avail.copy())

    if "DATE" in avail_dedup.columns:
        snap = (
            avail_dedup.sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE"])
        )
    else:
        snap = avail_dedup.drop_duplicates(subset=["CUSTOMER_CODE"])

    avail_cols = [
        "CUSTOMER_CODE", "CUSTOMER_NAME", "TYPE",
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT",
        "AVAIL_YEAR",
    ]
    keep_cols = [c for c in avail_cols if c in snap.columns]
    snap = snap[keep_cols].copy().reset_index(drop=True)

    # เก็บ AVAIL name แยก — primary display name
    if "CUSTOMER_NAME" in snap.columns:
        snap = snap.rename(columns={"CUSTOMER_NAME": "AVAIL_CUSTOMER_NAME"})

    joined = df_overdue.merge(
        snap,
        left_on="Customer",
        right_on="CUSTOMER_CODE",
        how="left",
    ).reset_index(drop=True)

    # Display name: AVAIL_CUSTOMER_NAME ก่อน fallback CustomerName
    def _display_name(row):
        avail = str(row.get("AVAIL_CUSTOMER_NAME", "")).strip()
        over  = str(row.get("CustomerName", "")).strip()
        if avail and avail not in ("nan", "None", ""):
            return avail
        return over

    joined["DisplayName"] = joined.apply(_display_name, axis=1)

    if "CURRENT_DEBT_MILLION_THB_PERCENT" in joined.columns:
        joined["UtilizationPct"] = joined["CURRENT_DEBT_MILLION_THB_PERCENT"] * 100
    else:
        joined["UtilizationPct"] = np.nan

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
        return "Healthy"

    joined["RiskTier"] = joined.apply(_tier, axis=1)
    return joined


# =============================================================================
# Filters
# =============================================================================
def _render_filters(df_avail, df_overdue, df_joined):
    available_companies = (
        sorted(df_overdue["CompanyCode"].dropna().unique().tolist())
        if "CompanyCode" in df_overdue.columns else ["All"]
    )
    default_idx = available_companies.index("1190") if "1190" in available_companies else 0

    overdue_due_years = (
        sorted(df_overdue["DueYear"].dropna().astype(int).unique().tolist())
        if "DueYear" in df_overdue.columns else []
    )
    avail_years_available = (
        set(df_avail["AVAIL_YEAR"].dropna().astype(str).unique().tolist())
        if "AVAIL_YEAR" in df_avail.columns else set()
    )

    all_customer_names: list = []
    for col in ("DisplayName", "AVAIL_CUSTOMER_NAME", "CustomerName"):
        if col in df_joined.columns:
            names = (
                df_joined[col].dropna().astype(str).str.strip()
                .replace({"": None, "nan": None, "None": None}).dropna()
                .unique().tolist()
            )
            all_customer_names = sorted(names)
            break

    all_customer_codes = (
        sorted(df_joined["Customer"].dropna().astype(int).unique().tolist())
        if "Customer" in df_joined.columns else []
    )

    # =========================================================================
    # Single row layout:
    # View Type | Company Code | Due Year | Risk Tier | Customer Code | Customer Name
    # =========================================================================
    COLS = [0.85, 0.85, 0.9, 0.9, 1.3, 1.3]
    col_labels = [
        "View Type",
        "Company Code",
        "Overdue Due Year",
        "Risk Tier",
        f"Customer Code ({len(all_customer_codes)} total)",
        f"Customer Name ({len(all_customer_names)} total)",
    ]

    lc = st.columns(COLS, gap="small")
    for col, lbl in zip(lc, col_labels):
        with col:
            st.markdown(f'<span style="{LABEL_STYLE}">{lbl}</span>', unsafe_allow_html=True)

    wc = st.columns(COLS, gap="small")

    with wc[0]:
        view_type = st.selectbox(
            "View Type", ["Rounded Number", "Detail Number"],
            index=0, key="mon_view_type", label_visibility="collapsed",
        )
        vt_color = "#1A7A4A" if view_type == "Rounded Number" else "#1B4F8A"
        vt_short = "Rounded" if view_type == "Rounded Number" else "Detail"
        st.markdown(
            f'<span style="background:{vt_color};color:white;padding:1px 7px;'
            f'border-radius:8px;font-size:0.68rem;font-weight:600;'
            f'display:inline-block;margin-top:2px;">{vt_short}</span>',
            unsafe_allow_html=True,
        )

    with wc[1]:
        selected_company = st.selectbox(
            "Company Code", options=available_companies,
            index=default_idx, key="mon_company", label_visibility="collapsed",
        )

    with wc[2]:
        due_year_opts     = ["All"] + [str(y) for y in overdue_due_years]
        selected_due_year = st.selectbox(
            "Overdue Due Year", options=due_year_opts,
            index=0, key="mon_due_year", label_visibility="collapsed",
        )

    with wc[3]:
        tier_options  = ["All", "Critical", "High Risk", "Watch", "Healthy", "Unknown"]
        selected_tier = st.selectbox(
            "Risk Tier", options=tier_options,
            index=0, key="mon_tier", label_visibility="collapsed",
        )

    # Customer Code — selectbox only (ไม่มี text_input)
    with wc[4]:
        prev_code       = st.session_state.get("_mon_selected_code", "All codes")
        code_options    = ["All codes"] + [str(c) for c in all_customer_codes]
        default_code_ix = code_options.index(prev_code) if prev_code in code_options else 0
        selected_code_option = st.selectbox(
            "Customer Code", options=code_options,
            index=default_code_ix, key="mon_code_recommend",
            label_visibility="collapsed",
        )
        st.session_state["_mon_selected_code"] = selected_code_option

    # Customer Name — selectbox only (ไม่มี text_input)
    with wc[5]:
        prev_name       = st.session_state.get("_mon_selected_customer", "All customers")
        recommend_opts  = ["All customers"] + all_customer_names
        default_name_ix = recommend_opts.index(prev_name) if prev_name in recommend_opts else 0
        selected_name_option = st.selectbox(
            "Customer Name", options=recommend_opts,
            index=default_name_ix, key="mon_customer_recommend",
            label_visibility="collapsed",
        )
        st.session_state["_mon_selected_customer"] = selected_name_option

    # =========================================================================
    # Apply filters + debug logging
    # =========================================================================
    df = df_joined.copy()

    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    if selected_due_year != "All":
        try:
            due_year_int = int(selected_due_year)
        except (ValueError, TypeError):
            due_year_int = None

        if due_year_int and "DueYear" in df.columns:
            due_year_dist = df["DueYear"].value_counts().sort_index().to_dict()

            rows_before = len(df)
            df = df[df["DueYear"] == due_year_int]
            rows_after  = len(df)

            due_year_str   = str(due_year_int)
            avail_year_int = sorted([int(y) for y in avail_years_available if y.isdigit()])

            if due_year_str in avail_years_available:
                matched_avail_year = due_year_str
            elif avail_year_int:
                before = [y for y in avail_year_int if y <= due_year_int]
                after  = [y for y in avail_year_int if y > due_year_int]
                matched_avail_year = str(max(before)) if before else str(min(after))
            else:
                matched_avail_year = None
            if matched_avail_year and not df_avail.empty:
                avail_for_year = df_avail[
                    df_avail["AVAIL_YEAR"].astype(str) == matched_avail_year
                ].copy()

                if not avail_for_year.empty:
                    avail_for_year = _dedup_avail_for_kpi(avail_for_year)

                    if "DATE" in avail_for_year.columns:
                        snap = (
                            avail_for_year.sort_values("DATE", ascending=False)
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

                    drop_cols = [c for c in df.columns if c in {
                        "CUSTOMER_CODE", "AVAIL_CUSTOMER_NAME", "TYPE",
                        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
                        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT",
                        "AVAIL_YEAR", "UtilizationPct", "RiskTier", "DisplayName",
                    }]
                    rows_before_merge = len(df)
                    df = df.drop(columns=drop_cols, errors="ignore")
                    df = df.merge(snap, left_on="Customer", right_on="CUSTOMER_CODE", how="left")

                    join_null = int(df["CUSTOMER_CODE"].isna().sum()) if "CUSTOMER_CODE" in df.columns else -1
                    if "CLEAN_CREDIT_MB" in df.columns:
                        credit_null = int(df["CLEAN_CREDIT_MB"].isna().sum())

                    def _display_name(row):
                        avail = str(row.get("AVAIL_CUSTOMER_NAME", "")).strip()
                        over  = str(row.get("CustomerName", "")).strip()
                        return avail if avail not in ("nan", "None", "") else over

                    df["DisplayName"] = df.apply(_display_name, axis=1)

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
                        if pd.isna(util): return "Unknown"
                        if util >= 80 and dpd >= DPD_HIGH: return "Critical"
                        elif util >= 80 or dpd >= DPD_HIGH: return "High Risk"
                        elif util >= 50 or dpd >= DPD_MED: return "Watch"
                        return "Healthy"

                    df["RiskTier"] = df.apply(_tier, axis=1)
                    tier_dist = df["RiskTier"].value_counts().to_dict()

                if matched_avail_year == due_year_str:
                    st.info(
                        f"Overdue {due_year_int} — mapped with Availability {matched_avail_year} (exact match)",
                        icon="✅",
                    )
                else:
                    st.warning(
                        f"Overdue {due_year_int} — using nearest Availability year: {matched_avail_year}."
                    )
            else:
                st.warning(f"Overdue {due_year_int} — no Availability data to map.")

    if selected_tier != "All" and "RiskTier" in df.columns:
        df = df[df["RiskTier"] == selected_tier]

    if selected_code_option != "All codes":
        try:
            code_int = int(selected_code_option)
            if "Customer" in df.columns:
                df = df[df["Customer"] == code_int]
        except ValueError:
            pass

    if selected_name_option != "All customers":
        for col_search in ("DisplayName", "AVAIL_CUSTOMER_NAME", "CustomerName"):
            if col_search in df.columns:
                df = df[df[col_search].astype(str) == selected_name_option]
                break

    return df, selected_company, selected_due_year, view_type

# =============================================================================
# SECTION 1 — Monitoring KPI Row
# =============================================================================
def _build_customer_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build customer-level snapshot จาก df โดยไม่กรอง OverdueAmount
    ยึด CUSTOMER_CODE เป็น primary key
    ยึดชื่อจาก AVAIL_CUSTOMER_NAME ก่อน fallback CustomerName
    """
    if df.empty or "Customer" not in df.columns:
        return pd.DataFrame()

    name_col = "DisplayName" if "DisplayName" in df.columns else (
        "AVAIL_CUSTOMER_NAME" if "AVAIL_CUSTOMER_NAME" in df.columns else "CustomerName"
    )

    agg_dict = {}

    # name: prefer avail name
    if "AVAIL_CUSTOMER_NAME" in df.columns:
        agg_dict["AVAIL_NAME"] = ("AVAIL_CUSTOMER_NAME", "first")
    if "CustomerName" in df.columns:
        agg_dict["OVERDUE_NAME"] = ("CustomerName", "first")
    if name_col in df.columns and name_col not in ("AVAIL_CUSTOMER_NAME", "CustomerName"):
        agg_dict["DisplayName"] = (name_col, "first")

    # avail metrics
    for col in ("CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
                "CURRENT_DEBT_MILLION_THB_PERCENT", "TYPE", "AVAIL_YEAR"):
        if col in df.columns:
            agg_dict[col] = (col, "first")

    # utilization — prefer > 0 mean
    if "UtilizationPct" in df.columns:
        agg_dict["UtilizationPct"] = (
            "UtilizationPct",
            lambda x: x[x > 0].mean() if (x > 0).any() else x.mean()
        )

    # risk tier — mode
    if "RiskTier" in df.columns:
        agg_dict["RiskTier"] = (
            "RiskTier",
            lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"
        )

    # overdue metrics — only from debit notes (OverdueAmount > 0)
    debit_df = df[df["OverdueAmount"] > 0].copy() if "OverdueAmount" in df.columns else pd.DataFrame()

    snap = df.groupby("Customer").agg(**agg_dict).reset_index()

    # join overdue metrics
    if not debit_df.empty and "Customer" in debit_df.columns:
        ov_dict = {
            "GrossOverdue":     ("OverdueAmount",  "sum"),
            "OverdueInvoices":  ("OverdueAmount",  "count"),
        }
        if "OverdueAbs" in debit_df.columns:
            ov_dict["GrossOverdue"] = ("OverdueAbs", "sum")
        if "DPD" in debit_df.columns:
            ov_dict["MaxDPD"] = ("DPD", "max")
            ov_dict["AvgDPD"] = ("DPD", "mean")

        ov_agg = debit_df.groupby("Customer").agg(**ov_dict).reset_index()

        # credit note offset
        cn_df = df[df["OverdueAmount"] < 0] if "OverdueAmount" in df.columns else pd.DataFrame()
        if not cn_df.empty:
            cn_agg = (
                cn_df.groupby("Customer")["OverdueAmount"]
                .apply(lambda x: x.abs().sum())
                .reset_index()
                .rename(columns={"OverdueAmount": "CreditNoteOffset"})
            )
            ov_agg = ov_agg.merge(cn_agg, on="Customer", how="left")
            ov_agg["CreditNoteOffset"] = ov_agg["CreditNoteOffset"].fillna(0.0)
        else:
            ov_agg["CreditNoteOffset"] = 0.0

        ov_agg["NetOverdue"] = (ov_agg["GrossOverdue"] - ov_agg["CreditNoteOffset"]).clip(lower=0)

        snap = snap.merge(ov_agg, on="Customer", how="left")
    else:
        # ไม่มี debit note → fill 0
        for col in ("GrossOverdue", "NetOverdue", "CreditNoteOffset",
                    "OverdueInvoices", "MaxDPD", "AvgDPD"):
            snap[col] = 0.0

    # fill numeric nulls
    for col in ("GrossOverdue", "NetOverdue", "CreditNoteOffset",
                "OverdueInvoices", "MaxDPD", "AvgDPD",
                "UtilizationPct", "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB"):
        if col in snap.columns:
            snap[col] = pd.to_numeric(snap[col], errors="coerce").fillna(0.0)

    # primary display name
    if "AVAIL_NAME" in snap.columns:
        snap["PrimaryName"] = snap["AVAIL_NAME"].astype(str).str.strip()
        if "OVERDUE_NAME" in snap.columns:
            mask = snap["PrimaryName"].isin(["nan", "None", ""])
            snap.loc[mask, "PrimaryName"] = snap.loc[mask, "OVERDUE_NAME"].astype(str)
    elif "OVERDUE_NAME" in snap.columns:
        snap["PrimaryName"] = snap["OVERDUE_NAME"].astype(str)
    else:
        snap["PrimaryName"] = snap["Customer"].astype(str)

    return snap


def _render_kpi_row(df: pd.DataFrame, view_type: str):
    snap = _build_customer_snapshot(df)

    total_customers   = int(df["Customer"].nunique()) if "Customer" in df.columns else 0
    critical_count    = (
        int(df[df["RiskTier"] == "Critical"]["Customer"].nunique())
        if "RiskTier" in df.columns else 0
    )
    avg_util = (
        float(df["UtilizationPct"].dropna().mean())
        if "UtilizationPct" in df.columns else 0.0
    )

    net_overdue        = float(snap["NetOverdue"].sum())        if not snap.empty and "NetOverdue"        in snap.columns else 0.0
    gross_overdue      = float(snap["GrossOverdue"].sum())      if not snap.empty and "GrossOverdue"      in snap.columns else 0.0
    credit_note_offset = float(snap["CreditNoteOffset"].sum())  if not snap.empty and "CreditNoteOffset"  in snap.columns else 0.0
    overdue_customers  = int((snap["NetOverdue"] > 0).sum())    if not snap.empty and "NetOverdue"        in snap.columns else 0
    pct_overdue        = (overdue_customers / total_customers * 100) if total_customers > 0 else 0.0

    cards = [
        (
            "Portfolio Coverage",
            _fmt_count(total_customers, view_type),
            "Active customers monitored",
            "info",
        ),
        (
            "Critical Exposure",
            _fmt_count(critical_count, view_type),
            "High util & overdue risk",
            "danger" if critical_count > 0 else "safe",
        ),
        (
            "Net Overdue Exposure",
            _fmt_thb(net_overdue, view_type),
            f"Gross {_fmt_thb(gross_overdue, view_type)}",
            "danger" if net_overdue > 0 else "safe",
        ),
        (
            "Credit Utilization",
            _fmt_pct(avg_util, view_type),
            "Avg debt vs credit limit",
            "danger" if avg_util >= 80 else ("warning" if avg_util >= 50 else "info"),
        ),
        (
            "Overdue Rate",
            _fmt_pct(pct_overdue, view_type),
            f"{overdue_customers:,} of {total_customers:,} customers",
            "danger" if pct_overdue >= 30 else ("warning" if pct_overdue >= 10 else "safe"),
        ),
    ]

    cols = st.columns(5, gap="small")
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(_mon_kpi_card(label, value, sub, variant), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    _render_kpi_detail_tabs(df, snap, view_type)


def _render_kpi_detail_tabs(df: pd.DataFrame, snap: pd.DataFrame, view_type: str):
    """snap = output จาก _build_customer_snapshot() ไม่ใช่ _agg_customer_overdue()"""

    DATE_COLS = ["OriginalDueDate", "CollectionDate", "CustomerDueDate"]

    def _fmt_dates(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        for dc in DATE_COLS:
            if dc in frame.columns:
                if not pd.api.types.is_datetime64_any_dtype(frame[dc]):
                    frame[dc] = pd.to_datetime(frame[dc], errors="coerce")
                frame[dc] = frame[dc].dt.strftime("%Y-%m-%d")
        return frame

    with st.expander("Detail View — KPI Breakdown", expanded=False):
        tab_all, tab_crit, tab_net, tab_pct = st.tabs([
            "Monitored Customers",
            "Critical Risk",
            "Net Overdue Exposure",
            "% Customers Overdue",
        ])

        # ------------------------------------------------------------------
        # Tab 1 — Monitored Customers (ทุก customer แม้ overdue = 0)
        # ------------------------------------------------------------------
        with tab_all:
            st.caption(
                "All distinct customers in current filter — joined with credit availability. "
                "Customers with no overdue show 0 in overdue columns."
            )
            if snap.empty:
                st.info("No data.")
            else:
                display_cols = [c for c in [
                    "Customer", "PrimaryName", "AVAIL_NAME", "OVERDUE_NAME",
                    "RiskTier", "UtilizationPct",
                    "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
                    "GrossOverdue", "NetOverdue", "CreditNoteOffset",
                    "OverdueInvoices", "MaxDPD",
                ] if c in snap.columns]

                sort_col, _ = st.columns([2, 5])
                with sort_col:
                    sort_by = st.selectbox(
                        "Sort By",
                        ["Net Overdue (High to Low)", "Utilization % (High to Low)",
                         "Customer Name (A-Z)"],
                        index=0, key="kpi_tab_all_sort",
                    )
                sort_map = {
                    "Net Overdue (High to Low)":   ("NetOverdue", False),
                    "Utilization % (High to Low)": ("UtilizationPct", False),
                    "Customer Name (A-Z)":          ("PrimaryName", True),
                }
                sc, sa = sort_map.get(sort_by, ("NetOverdue", False))
                tbl = snap[display_cols].sort_values(sc, ascending=sa) if sc in snap.columns else snap[display_cols]
                tbl = tbl.reset_index(drop=True)

                st.dataframe(
                    tbl, use_container_width=True, hide_index=True, height=400,
                    column_config={
                        "Customer":                  st.column_config.NumberColumn("Cust. Code"),
                        "PrimaryName":               st.column_config.TextColumn("Customer Name", width="large"),
                        "AVAIL_NAME":                st.column_config.TextColumn("Name (Avail)", width="large"),
                        "OVERDUE_NAME":              st.column_config.TextColumn("Name (Overdue)", width="large"),
                        "RiskTier":                  st.column_config.TextColumn("Risk Tier"),
                        "UtilizationPct":            st.column_config.NumberColumn("Util %", format="%.1f%%"),
                        "CLEAN_CREDIT_MB":           st.column_config.NumberColumn("Credit Limit (MB)", format="%.2f"),
                        "CURRENT_DEBT_MILLION_THB":  st.column_config.NumberColumn("Current Debt (MB)", format="%.2f"),
                        "GrossOverdue":              st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f"),
                        "NetOverdue":                st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                        "CreditNoteOffset":          st.column_config.NumberColumn("Credit Note (THB)", format="%,.0f"),
                        "OverdueInvoices":           st.column_config.NumberColumn("Overdue Invoices", format="%d"),
                        "MaxDPD":                    st.column_config.NumberColumn("Max DPD (days)", format="%d"),
                    },
                )
                st.caption(f"{len(tbl):,} customer(s) | {len(tbl[tbl.get('NetOverdue', pd.Series(dtype=float)) > 0]):,} with net overdue > 0" if "NetOverdue" in tbl.columns else f"{len(tbl):,} customer(s)")

        # ------------------------------------------------------------------
        # Tab 2 — Critical Risk
        # ------------------------------------------------------------------
        with tab_crit:
            st.caption("Customers classified as Critical: Utilization >= 80% AND DPD >= 60 days.")
            if "RiskTier" not in df.columns:
                st.info("RiskTier column not available.")
            else:
                crit_codes = df[df["RiskTier"] == "Critical"]["Customer"].unique()
                crit_snap  = snap[snap["Customer"].isin(crit_codes)].copy() if not snap.empty else pd.DataFrame()

                if crit_snap.empty:
                    st.success("No Critical Risk customers in current filter.")
                else:
                    inv_cols = [c for c in [
                        "Customer", "PrimaryName", "AVAIL_NAME",
                        "OriginalDueDate", "CollectionDate", "CustomerDueDate",
                        "OverdueAmount", "InvoiceAmount", "DPD", "RiskTier",
                    ] if c in df.columns]
                    inv_df = df[df["Customer"].isin(crit_codes) & (df["OverdueAmount"] > 0)][inv_cols].copy()
                    inv_df = _fmt_dates(inv_df)
                    inv_df = inv_df.sort_values("OverdueAmount", ascending=False).reset_index(drop=True)

                    st.dataframe(
                        inv_df, use_container_width=True, hide_index=True, height=380,
                        column_config={
                            "Customer":      st.column_config.NumberColumn("Cust. Code"),
                            "PrimaryName":   st.column_config.TextColumn("Customer Name", width="large"),
                            "AVAIL_NAME":    st.column_config.TextColumn("Name (Avail)", width="large"),
                            "OverdueAmount": st.column_config.NumberColumn("Overdue (THB)", format="%,.2f"),
                            "InvoiceAmount": st.column_config.NumberColumn("Invoice Amt (THB)", format="%,.2f"),
                            "DPD":           st.column_config.NumberColumn("DPD (days)", format="%d"),
                            "RiskTier":      st.column_config.TextColumn("Risk Tier"),
                        },
                    )
                    st.caption(f"{len(crit_snap):,} critical customer(s) | {len(inv_df):,} overdue invoice(s)")

        # ------------------------------------------------------------------
        # Tab 3 — Net Overdue Exposure
        # ------------------------------------------------------------------
        with tab_net:
            st.caption("Net Overdue = Gross Overdue (Debit > 0) minus Credit Note, per customer.")
            if snap.empty or "NetOverdue" not in snap.columns:
                st.info("No data.")
            else:
                net_snap = snap[snap["NetOverdue"] > 0].copy()
                if net_snap.empty:
                    st.success("No net overdue exposure — all invoices settled.")
                else:
                    display_cols = [c for c in [
                        "Customer", "PrimaryName", "AVAIL_NAME",
                        "GrossOverdue", "CreditNoteOffset", "NetOverdue",
                        "OverdueInvoices", "MaxDPD", "UtilizationPct",
                    ] if c in net_snap.columns]
                    tbl_net = net_snap[display_cols].sort_values("NetOverdue", ascending=False).reset_index(drop=True)
                    st.dataframe(
                        tbl_net, use_container_width=True, hide_index=True, height=380,
                        column_config={
                            "Customer":         st.column_config.NumberColumn("Cust. Code"),
                            "PrimaryName":      st.column_config.TextColumn("Customer Name", width="large"),
                            "AVAIL_NAME":       st.column_config.TextColumn("Name (Avail)", width="large"),
                            "GrossOverdue":     st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f"),
                            "CreditNoteOffset": st.column_config.NumberColumn("Credit Note (THB)", format="%,.0f"),
                            "NetOverdue":       st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                            "OverdueInvoices":  st.column_config.NumberColumn("Debit Invoices", format="%d"),
                            "MaxDPD":           st.column_config.NumberColumn("Max DPD (days)", format="%d"),
                            "UtilizationPct":   st.column_config.NumberColumn("Util %", format="%.1f%%"),
                        },
                    )
                    total_net = float(tbl_net["NetOverdue"].sum())
                    st.caption(
                        f"{len(tbl_net):,} customer(s) with net overdue | "
                        f"Total: {_fmt_thb(total_net, view_type)}"
                    )

        # ------------------------------------------------------------------
        # Tab 4 — % Customers Overdue
        # ------------------------------------------------------------------
        with tab_pct:
            st.caption("Customers with at least 1 overdue invoice (OverdueAmount > 0) vs total monitored.")
            if snap.empty:
                st.info("No data.")
            else:
                total_n   = len(snap)
                overdue_n = int((snap["NetOverdue"] > 0).sum()) if "NetOverdue" in snap.columns else 0
                clean_n   = total_n - overdue_n

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Monitored", f"{total_n:,}")
                c2.metric("Overdue",  f"{overdue_n:,}",
                          delta=f"{overdue_n/total_n*100:.1f}%" if total_n else "0%",
                          delta_color="inverse")
                c3.metric("Clean (Settled)", f"{clean_n:,}")

                display_cols = [c for c in [
                    "Customer", "PrimaryName", "AVAIL_NAME",
                    "NetOverdue", "OverdueInvoices", "MaxDPD",
                    "RiskTier", "UtilizationPct",
                ] if c in snap.columns]
                tbl_pct = snap[display_cols].copy()
                tbl_pct["Status"] = tbl_pct["NetOverdue"].apply(
                    lambda v: "Overdue" if v > 0 else "Settled"
                ) if "NetOverdue" in tbl_pct.columns else "Unknown"
                tbl_pct = tbl_pct.sort_values(
                    ["Status", "NetOverdue"], ascending=[True, False]
                ).reset_index(drop=True)

                st.dataframe(
                    tbl_pct, use_container_width=True, hide_index=True, height=360,
                    column_config={
                        "Customer":       st.column_config.NumberColumn("Cust. Code"),
                        "PrimaryName":    st.column_config.TextColumn("Customer Name", width="large"),
                        "AVAIL_NAME":     st.column_config.TextColumn("Name (Avail)", width="large"),
                        "NetOverdue":     st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                        "OverdueInvoices":st.column_config.NumberColumn("Overdue Invoices", format="%d"),
                        "MaxDPD":         st.column_config.NumberColumn("Max DPD (days)", format="%d"),
                        "RiskTier":       st.column_config.TextColumn("Risk Tier"),
                        "UtilizationPct": st.column_config.NumberColumn("Util %", format="%.1f%%"),
                        "Status":         st.column_config.TextColumn("Status"),
                    },
                )


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


def _render_health_bubble(df: pd.DataFrame, view_type: str = "Detail Number"):
    """
    Scatter ใช้ข้อมูลจาก credit avail (UtilizationPct) เป็นหลัก
    ไม่ขึ้นกับ OverdueAmount > 0 — แสดงทุก customer ที่มี UtilizationPct
    Net Overdue = 0 ก็แสดง (ใช้ OverdueAbs แทน NetOverdue จาก _agg_customer_overdue)
    """
    if "Customer" not in df.columns or "UtilizationPct" not in df.columns:
        st.info("Insufficient columns for Health Matrix (need Customer, UtilizationPct).")
        return

    # --- aggregate ระดับ customer โดยไม่กรอง OverdueAmount ---
    # ใช้ทุก row รวมถึง row ที่ OverdueAmount = 0 (จ่ายแล้ว)
    agg_dict = {
        "OverdueAbs":      ("OverdueAbs",    "sum"),
        "UtilizationPct":  ("UtilizationPct", lambda x: x[x > 0].mean() if (x > 0).any() else x.mean()),
        "RiskTier":        ("RiskTier",       lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"),
    }
    if "CLEAN_CREDIT_MB" in df.columns:
        agg_dict["CLEAN_CREDIT_MB"] = ("CLEAN_CREDIT_MB", "mean")
    if "GrossOverdue" in df.columns:
        agg_dict["GrossOverdue"] = ("GrossOverdue", "sum")
    if "CreditNoteOffset" in df.columns:
        agg_dict["CreditNoteOffset"] = ("CreditNoteOffset", "sum")

    # หา name column
    name_col = "DisplayName" if "DisplayName" in df.columns else (
        "AVAIL_CUSTOMER_NAME" if "AVAIL_CUSTOMER_NAME" in df.columns else "CustomerName"
    )
    if name_col in df.columns:
        agg_dict["Label"] = (name_col, "first")

    agg = df.groupby("Customer").agg(**agg_dict).reset_index()

    if agg.empty:
        st.info("No customer data to display in Health Matrix.")
        return

    # --- ถ้าไม่มี RiskTier จาก avail ให้คำนวณใหม่จาก UtilizationPct ---
    if "RiskTier" not in agg.columns:
        def _tier_from_util(util):
            if pd.isna(util): return "Unknown"
            if util >= 80:    return "High Risk"
            if util >= 50:    return "Watch"
            return "Healthy"
        agg["RiskTier"] = agg["UtilizationPct"].apply(_tier_from_util)

    if "Label" not in agg.columns:
        agg["Label"] = agg["Customer"].astype(str)

    agg["UtilizationPct"] = agg["UtilizationPct"].fillna(0.0).astype(float)
    agg["OverdueAbs"]     = agg["OverdueAbs"].fillna(0.0).astype(float)

    # --- Bubble size จาก CLEAN_CREDIT_MB ---
    FALLBACK_SIZE = 18.0
    if "CLEAN_CREDIT_MB" in agg.columns:
        raw_credit   = agg["CLEAN_CREDIT_MB"].fillna(0.0)
        if raw_credit.sum() == 0:
            agg["BubbleSize"] = FALLBACK_SIZE
        else:
            credit_vals  = raw_credit.clip(lower=1.0)
            credit_range = max(float(credit_vals.max()) - float(credit_vals.min()), 1.0)
            agg["BubbleSize"] = 8.0 + ((credit_vals - float(credit_vals.min())) / credit_range) * 42.0
    else:
        agg["BubbleSize"] = FALLBACK_SIZE

    agg["BubbleSize"] = agg["BubbleSize"].fillna(FALLBACK_SIZE).clip(lower=6.0, upper=60.0)

    # --- Y axis scale ตาม view_type ---
    max_y_raw = float(agg["OverdueAbs"].max()) if not agg.empty else 1.0
    if view_type == "Rounded Number":
        if max_y_raw >= 1_000_000_000:
            y_div, y_suffix = 1_000_000_000, " B THB"
        elif max_y_raw >= 1_000_000:
            y_div, y_suffix = 1_000_000, " M THB"
        else:
            y_div, y_suffix = 1_000, " K THB"
        agg["Y_PLOT"] = agg["OverdueAbs"] / y_div
        y_axis_cfg = dict(
            title=f"Overdue Amount ({y_suffix.strip()})",
            ticksuffix=y_suffix, tickformat=".1f",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        )
    else:
        agg["Y_PLOT"] = agg["OverdueAbs"]
        y_axis_cfg = dict(
            title="Overdue Amount (THB)",
            tickformat=",.0f", ticksuffix=" THB",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        )

    median_y   = float(agg["Y_PLOT"].median())
    max_util   = float(agg["UtilizationPct"].max()) * 1.1 if not agg.empty else 120.0

    fig = go.Figure()
    for tier in TIER_ORDER:
        grp = agg[agg["RiskTier"] == tier].copy()
        if grp.empty:
            continue

        credit_vals_hover = grp["CLEAN_CREDIT_MB"].fillna(0.0).tolist() if "CLEAN_CREDIT_MB" in grp.columns else [0.0] * len(grp)

        custom = list(zip(
            grp["OverdueAbs"].tolist(),
            credit_vals_hover,
        ))

        fig.add_trace(go.Scatter(
            x    = grp["UtilizationPct"].tolist(),
            y    = grp["Y_PLOT"].tolist(),
            mode = "markers",
            name = tier,
            marker = dict(
                size     = grp["BubbleSize"].tolist(),
                color    = TIER_COLOR.get(tier, PALETTE["nodata"]),
                opacity  = 0.82,
                line     = dict(width=1, color="white"),
                sizemode = "diameter",
            ),
            text       = grp["Label"].astype(str).tolist(),
            customdata = custom,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Utilization  : %{x:.1f}%<br>"
                "Overdue Amt  : %{customdata[0]:,.0f} THB<br>"
                "Credit Limit : %{customdata[1]:,.1f} MB"
                "<extra></extra>"
            ),
        ))

    fig.add_vline(
        x=80, line_dash="dash", line_color=PALETTE["threshold"], line_width=1,
        annotation_text="80% Util",
        annotation_font=dict(size=8, color=PALETTE["threshold"]),
    )
    if median_y > 0:
        fig.add_hline(
            y=median_y, line_dash="dot", line_color="#aaaaaa", line_width=1,
            annotation_text="Median Overdue",
            annotation_font=dict(size=8, color="#777777"),
        )

    apply_base_layout(fig, {
        "height": 380,
        "margin": dict(l=0, r=20, t=30, b=10),
        "title": dict(
            text="Credit Health Matrix — Utilization % vs Overdue Amount",
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title="Credit Utilization %", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            range=[0, max(120.0, max_util)],
        ),
        "yaxis": y_axis_cfg,
        "legend": dict(
            orientation="v", yanchor="top", y=1, xanchor="left", x=1.01,
            font=dict(size=9), bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#d0dae6", borderwidth=1,
        ),
        "showlegend": True,
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=11, color="#1B2A3B"), align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_health_bubble")



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
        labels        = tier_counts["Tier"].tolist(),
        values        = tier_counts["Count"].tolist(),
        marker        = dict(
            colors=[TIER_COLOR.get(t, PALETTE["nodata"]) for t in tier_counts["Tier"]],
            line=dict(color="white", width=2),
        ),
        hole          = 0.48,
        textinfo      = "label+percent",
        textfont      = dict(size=10),
        hovertemplate = "%{label}<br>Customers: %{value}<br>Share: %{percent}<extra></extra>",
        showlegend    = False,
        sort          = False,
        direction     = "clockwise",
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
# SECTION 2B — Risk Tier Donut
# =============================================================================
def _render_health_matrix_section(df: pd.DataFrame, df_avail_full: pd.DataFrame, view_type: str):
    """Wrapper ที่มี month filter สำหรับ scatter + donut เท่านั้น"""

    # Month filter — อิงจาก DATE ใน df_avail (ไม่ re-parse ถ้าเป็น datetime แล้ว)
    avail_months: list = []
    if df_avail_full is not None and "DATE" in df_avail_full.columns:
        raw_date = df_avail_full["DATE"]
        if pd.api.types.is_datetime64_any_dtype(raw_date):
            dt_avail = raw_date
        else:
            dt_avail = pd.to_datetime(raw_date, errors="coerce")

        month_ints = sorted(dt_avail.dropna().dt.month.unique().astype(int).tolist())
        avail_months = [(m, MONTH_MAP.get(m, str(m))) for m in month_ints]

    month_col, _ = st.columns([2, 5])
    with month_col:
        st.markdown(f'<span style="{LABEL_STYLE}">Filter by Availability Month</span>', unsafe_allow_html=True)
        month_opts = ["All"] + [f"{m:02d} — {lbl}" for m, lbl in avail_months]
        month_to_int = {f"{m:02d} — {lbl}": m for m, lbl in avail_months}
        sel_month_lbl = st.selectbox(
            "Avail Month", month_opts, index=0,
            key="mon_health_month", label_visibility="collapsed",
        )
        sel_month = None if sel_month_lbl == "All" else month_to_int.get(sel_month_lbl)

    # Filter df โดยอิง AVAIL_YEAR + month จาก DATE ของ avail
    df_section = df.copy()
    if sel_month is not None and df_avail_full is not None and "DATE" in df_avail_full.columns:
        raw_date = df_avail_full["DATE"]
        if pd.api.types.is_datetime64_any_dtype(raw_date):
            dt_avail = raw_date
        else:
            dt_avail = pd.to_datetime(raw_date, errors="coerce")

        # หา CUSTOMER_CODE ที่มี snapshot ในเดือนนั้น
        avail_with_dt = df_avail_full.copy()
        avail_with_dt["_dt"] = dt_avail
        codes_in_month = (
            avail_with_dt[avail_with_dt["_dt"].dt.month == sel_month]["CUSTOMER_CODE"]
            .dropna().astype(int).unique().tolist()
        )
        if "Customer" in df_section.columns:
            df_section = df_section[df_section["Customer"].isin(codes_in_month)]

    col_bubble, col_tier = st.columns([3, 2], gap="medium")
    with col_bubble:
        _render_health_bubble(df_section)
    with col_tier:
        _render_risk_tier_donut(df_section)


def _render_health_bubble(df: pd.DataFrame, view_type: str = "Detail Number"):
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

    FALLBACK_SIZE = 18.0
    if "CLEAN_CREDIT_MB" in agg.columns:
        raw_credit   = agg["CLEAN_CREDIT_MB"].fillna(0.0)
        if raw_credit.sum() == 0:
            agg["BubbleSize"] = FALLBACK_SIZE
        else:
            credit_vals  = raw_credit.clip(lower=1.0)
            credit_range = max(float(credit_vals.max()) - float(credit_vals.min()), 1.0)
            agg["BubbleSize"] = 8.0 + ((credit_vals - float(credit_vals.min())) / credit_range) * 42.0
    else:
        agg["BubbleSize"] = FALLBACK_SIZE

    agg["BubbleSize"]     = agg["BubbleSize"].fillna(FALLBACK_SIZE).clip(lower=6.0, upper=60.0)
    agg["UtilizationPct"] = agg["UtilizationPct"].fillna(0.0)
    agg["TotalOverdue"]   = agg["TotalOverdue"].fillna(0.0)

    label_col = "CustomerName" if "CustomerName" in agg.columns else "Customer"

    fig = go.Figure()
    for tier in TIER_ORDER:
        grp = agg[agg["RiskTier"] == tier].copy()
        if grp.empty:
            continue

        gross_col  = "GrossOverdue"      if "GrossOverdue"      in grp.columns else "TotalOverdue"
        cn_col     = "CreditNoteOffset"  if "CreditNoteOffset"  in grp.columns else None
        credit_col = "CLEAN_CREDIT_MB"   if "CLEAN_CREDIT_MB"   in grp.columns else None

        custom = list(zip(
            grp["TotalOverdue"].tolist(),
            grp[gross_col].tolist(),
            grp[cn_col].tolist()             if cn_col     else [0.0] * len(grp),
            grp[credit_col].fillna(0.0).tolist() if credit_col else [0.0] * len(grp),
        ))

        fig.add_trace(go.Scatter(
            x=grp["UtilizationPct"].tolist(),
            y=grp["TotalOverdue"].tolist(),
            mode="markers",
            name=tier,
            marker=dict(
                size=grp["BubbleSize"].tolist(),
                color=TIER_COLOR.get(tier, PALETTE["nodata"]),
                opacity=0.80,
                line=dict(width=1, color="white"),
                sizemode="diameter",
            ),
            text=grp[label_col].astype(str).tolist(),
            customdata=custom,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Utilization  : %{x:.1f}%<br>"
                "Net Overdue  : %{customdata[0]:,.0f} THB<br>"
                "Gross Overdue: %{customdata[1]:,.0f} THB<br>"
                "Credit Note  : %{customdata[2]:,.0f} THB<br>"
                "Credit Limit : %{customdata[3]:,.1f} MB"
                "<extra></extra>"
            ),
        ))

    median_overdue = float(agg["TotalOverdue"].median()) if not agg.empty else 0.0
    max_util       = float(agg["UtilizationPct"].max()) * 1.1 if not agg.empty else 120.0

    # Y axis format ตาม view_type
    if view_type == "Rounded Number":
        max_y = float(agg["TotalOverdue"].max()) if not agg.empty else 1.0
        if max_y >= 1_000_000_000:
            y_div, y_suffix = 1_000_000_000, " B THB"
        elif max_y >= 1_000_000:
            y_div, y_suffix = 1_000_000, " M THB"
        else:
            y_div, y_suffix = 1_000, " K THB"
        for trace in fig.data:
            trace.y = [v / y_div for v in trace.y]
            trace.customdata = [
                (c[0] / y_div, c[1] / y_div, c[2] / y_div, c[3])
                for c in trace.customdata
            ]
        median_overdue /= y_div
        y_axis_cfg = dict(
            title=f"Net Overdue ({y_suffix.strip()})",
            ticksuffix=y_suffix, tickformat=".1f",
            showgrid=True, gridcolor=GRID_COLOR, color=FONT_COLOR, tickfont=dict(size=9),
        )
    else:
        y_axis_cfg = dict(
            title="Net Overdue (THB)",
            tickformat=",.0f", ticksuffix=" THB",
            showgrid=True, gridcolor=GRID_COLOR, color=FONT_COLOR, tickfont=dict(size=9),
        )

    fig.add_vline(x=80, line_dash="dash", line_color=PALETTE["threshold"], line_width=1,
                  annotation_text="80% Util", annotation_font=dict(size=8, color=PALETTE["threshold"]))
    fig.add_hline(y=median_overdue, line_dash="dot", line_color="#aaaaaa", line_width=1,
                  annotation_text="Median", annotation_font=dict(size=8, color="#777777"))

    apply_base_layout(fig, {
        "height": 380,
        "margin": dict(l=0, r=20, t=30, b=10),
        "title": dict(text="Credit Health Matrix — Utilization % vs Net Overdue",
                      font=dict(size=10, color=FONT_COLOR), x=0),
        "xaxis": dict(title="Credit Utilization %", ticksuffix="%",
                      showgrid=True, gridcolor=GRID_COLOR, color=FONT_COLOR,
                      tickfont=dict(size=9), range=[0, max(120.0, max_util)]),
        "yaxis": y_axis_cfg,
        "legend": dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01,
                       font=dict(size=9), bgcolor="rgba(255,255,255,0.9)",
                       bordercolor="#d0dae6", borderwidth=1),
        "showlegend": True,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_health_bubble")


# =============================================================================
# SECTION 3 — Watchlist Heatmap Table
# =============================================================================
def _render_watchlist(df: pd.DataFrame, view_type: str = "Detail Number", top_n: int = 20):
    need = {"Customer", "UtilizationPct", "OverdueAmount", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("Watchlist requires joined data.")
        return

    # ---- aggregate ระดับ customer ----
    cust_agg = _agg_customer_overdue(df)
    if cust_agg.empty:
        st.success("No overdue customers.")
        return

    watchlist = cust_agg[cust_agg["NetOverdue"] > 0].copy()
    if watchlist.empty:
        st.success("No customers with net overdue > 0 after Credit Note offset.")
        return

    tier_rank = {"Critical": 0, "High Risk": 1, "Watch": 2, "Healthy": 3, "Unknown": 4}
    watchlist["_rank"] = watchlist["RiskTier"].map(tier_rank).fillna(9)
    watchlist = (
        watchlist.sort_values(["_rank", "NetOverdue"], ascending=[True, False])
        .head(top_n).reset_index(drop=True)
    )

    # ---- Summary cards (ขึ้นก่อน) ----
    n_critical  = int((watchlist["RiskTier"] == "Critical").sum())
    n_highrisk  = int((watchlist["RiskTier"] == "High Risk").sum())
    n_watch     = int((watchlist["RiskTier"] == "Watch").sum())
    total_net   = float(watchlist["NetOverdue"].sum())
    total_cn    = float(watchlist["CreditNoteOffset"].sum()) if "CreditNoteOffset" in watchlist.columns else 0.0

    card_items = [
        ("Critical",             f"{n_critical:,}",                  PALETTE["crimson"],     "danger"),
        ("High Risk",            f"{n_highrisk:,}",                  PALETTE["amber"],       "warning"),
        ("Watch",                f"{n_watch:,}",                     PALETTE["amber_lt"],    "warning"),
        ("Net Exposure",         _fmt_thb(total_net, view_type),     PALETTE["jade"],        "danger" if total_net > 0 else "safe"),
        ("Credit Note Offset",   _fmt_thb(total_cn, view_type),      PALETTE["sapphire"],    "info"),
    ]

    cols = st.columns(5, gap="small")
    for col, (label, value, accent, variant) in zip(cols, card_items):
        with col:
            variant_styles = {
                "danger":  ("rgba(215,38,61,0.07)",  "#A01F2D"),
                "warning": ("rgba(181,98,10,0.07)",  "#B5620A"),
                "safe":    ("rgba(26,122,74,0.07)",  "#1A7A4A"),
                "info":    ("rgba(27,79,138,0.07)",  "#1B4F8A"),
            }
            bg, acc = variant_styles.get(variant, variant_styles["info"])
            vlen = len(str(value))
            v_font = "1.10rem" if vlen <= 12 else ("0.90rem" if vlen <= 20 else "0.75rem")
            st.markdown(
                f'<div style="background:{bg};border-left:3px solid {acc};'
                f'border-radius:8px;padding:12px 14px;'
                f'display:grid;grid-template-rows:auto 1fr;'
                f'height:90px;box-sizing:border-box;">'
                f'<div style="font-size:0.68rem;font-weight:700;color:{acc};'
                f'letter-spacing:0.06em;text-transform:uppercase;">{label}</div>'
                f'<div style="font-size:{v_font};font-weight:800;color:#1a2a3a;'
                f'line-height:1.15;align-self:center;">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    # ---- Toggle: Per Customer / Per Invoice ----
    toggle_col, _ = st.columns([2, 5])
    with toggle_col:
        view_mode = st.radio(
            "View Mode", ["Per Customer", "Per Invoice"],
            horizontal=True, index=0, key="watchlist_view_mode",
        )

    name_col = "DisplayName" if "DisplayName" in df.columns else (
        "AVAIL_CUSTOMER_NAME" if "AVAIL_CUSTOMER_NAME" in df.columns else "CustomerName"
    )

    if view_mode == "Per Customer":
        _render_watchlist_per_customer(df, watchlist, name_col, view_type)
    else:
        _render_watchlist_per_invoice(df, watchlist, name_col, view_type)


def _render_watchlist_per_customer(
    df: pd.DataFrame,
    watchlist: pd.DataFrame,
    name_col: str,
    view_type: str,
):
    rename_map = {
        "NetOverdue":              "Net Overdue (THB)",
        "GrossOverdue":            "Gross Overdue (THB)",
        "CreditNoteOffset":        "Credit Note (THB)",
        "OverdueInvoices":         "Invoices",
        "MaxDPD":                  "Max DPD",
        "UtilizationPct":          "Util %",
        "RiskTier":                "Risk Tier",
        "CustomerName":            "Customer Name (Overdue)",
        "CLEAN_CREDIT_MB":         "Credit Limit (MB)",
        "CURRENT_DEBT_MILLION_THB":"Current Debt (MB)",
        "TYPE":                    "Type",
    }
    display_order = [
        "Customer", name_col, "CustomerName", "TYPE",
        "UtilizationPct", "MaxDPD",
        "NetOverdue", "GrossOverdue", "CreditNoteOffset",
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "OverdueInvoices", "RiskTier",
    ]
    show_cols = [c for c in display_order if c in watchlist.columns]
    tbl = watchlist[show_cols].rename(columns=rename_map)

    for col in ("Net Overdue (THB)", "Gross Overdue (THB)", "Credit Note (THB)",
                "Util %", "Credit Limit (MB)", "Current Debt (MB)"):
        if col in tbl.columns:
            tbl[col] = pd.to_numeric(tbl[col], errors="coerce")

    st.dataframe(
        tbl, use_container_width=True, height=360, hide_index=True,
        column_config={
            "Customer":              st.column_config.NumberColumn("Cust. Code", width="small"),
            name_col:                st.column_config.TextColumn("Customer Name (Avail)", width="large"),
            "Customer Name (Overdue)": st.column_config.TextColumn("Customer Name (Overdue)", width="large"),
            "Type":                  st.column_config.TextColumn("Type", width="small"),
            "Util %":                st.column_config.NumberColumn("Util %", format="%.1f%%", width="small"),
            "Max DPD":               st.column_config.NumberColumn("Max DPD", format="%d days", width="small"),
            "Net Overdue (THB)":     st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f", width="medium"),
            "Gross Overdue (THB)":   st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f", width="medium"),
            "Credit Note (THB)":     st.column_config.NumberColumn("Credit Note (THB)", format="%,.0f", width="medium"),
            "Credit Limit (MB)":     st.column_config.NumberColumn("Credit Limit (MB)", format="%.1f", width="small"),
            "Current Debt (MB)":     st.column_config.NumberColumn("Current Debt (MB)", format="%.1f", width="small"),
            "Invoices":              st.column_config.NumberColumn("Invoices", width="small"),
            "Risk Tier":             st.column_config.TextColumn("Risk Tier", width="small"),
        },
    )


def _render_watchlist_per_invoice(
    df: pd.DataFrame,
    watchlist: pd.DataFrame,
    name_col: str,
    view_type: str,
):
    watchlist_codes = watchlist["Customer"].unique()
    inv_df = df[
        df["Customer"].isin(watchlist_codes) &
        (df["OverdueAmount"] > 0)
    ].copy()

    if inv_df.empty:
        st.info("No overdue invoices for watchlist customers.")
        return

    # Sum per invoice doc ก่อน แล้วค่อย map customer
    if "InvoiceDocument" in inv_df.columns:
        inv_grp = (
            inv_df.groupby(["Customer", "InvoiceDocument"])
            .agg(
                InvoiceOverdue  =("OverdueAmount",  "sum"),
                InvoiceAmount   =("InvoiceAmount",  "sum") if "InvoiceAmount" in inv_df.columns else ("OverdueAmount", "sum"),
                OriginalDueDate =("OriginalDueDate","first"),
                CollectionDate  =("CollectionDate", "first"),
                CustomerDueDate =("CustomerDueDate","first"),
                DPD             =("DPD",            "max"),
                RiskTier        =("RiskTier",       "first"),
            )
            .reset_index()
        )
    else:
        inv_grp = inv_df.copy()
        inv_grp["InvoiceDocument"] = "N/A"

    # map DisplayName จาก watchlist
    code_name_map = {}
    for col_n in (name_col, "CustomerName"):
        if col_n in watchlist.columns:
            code_name_map = watchlist.set_index("Customer")[col_n].to_dict()
            break

    inv_grp["CustomerDisplay"] = inv_grp["Customer"].map(code_name_map).fillna(inv_grp["Customer"].astype(str))

    for dc in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
        if dc in inv_grp.columns:
            if not pd.api.types.is_datetime64_any_dtype(inv_grp[dc]):
                inv_grp[dc] = pd.to_datetime(inv_grp[dc], errors="coerce")
            inv_grp[dc] = inv_grp[dc].dt.strftime("%Y-%m-%d")

    inv_grp = inv_grp.sort_values(["Customer", "InvoiceOverdue"], ascending=[True, False]).reset_index(drop=True)

    tab_inv, tab_cust_summary = st.tabs(["Per Invoice", "Customer Summary"])

    with tab_inv:
        st.caption("Each row = 1 invoice document. Summed per InvoiceDocument then mapped to customer.")
        col_cfg = {
            "Customer":        st.column_config.NumberColumn("Cust. Code", width="small"),
            "CustomerDisplay": st.column_config.TextColumn("Customer Name", width="large"),
            "InvoiceDocument": st.column_config.TextColumn("Invoice Doc.", width="medium"),
            "InvoiceOverdue":  st.column_config.NumberColumn("Overdue (THB)", format="%,.2f"),
            "InvoiceAmount":   st.column_config.NumberColumn("Invoice Amt (THB)", format="%,.2f"),
            "OriginalDueDate": st.column_config.TextColumn("Original Due", width="medium"),
            "CollectionDate":  st.column_config.TextColumn("Collection Date", width="medium"),
            "CustomerDueDate": st.column_config.TextColumn("Customer Due", width="medium"),
            "DPD":             st.column_config.NumberColumn("DPD (days)", format="%d"),
            "RiskTier":        st.column_config.TextColumn("Risk Tier"),
        }
        show = [c for c in ["Customer", "CustomerDisplay", "InvoiceDocument",
                             "InvoiceOverdue", "InvoiceAmount",
                             "OriginalDueDate", "CollectionDate", "CustomerDueDate",
                             "DPD", "RiskTier"] if c in inv_grp.columns]
        st.dataframe(inv_grp[show], use_container_width=True, hide_index=True, height=420, column_config=col_cfg)
        st.caption(f"{len(inv_grp):,} invoice record(s) for {len(watchlist_codes):,} watchlist customer(s)")

    with tab_cust_summary:
        st.caption("Aggregated from invoice level — sum per customer.")
        if "InvoiceDocument" in inv_grp.columns:
            summary = (
                inv_grp.groupby(["Customer", "CustomerDisplay"])
                .agg(
                    TotalOverdue    =("InvoiceOverdue", "sum"),
                    InvoiceCount    =("InvoiceDocument","count"),
                    MaxDPD          =("DPD",            "max"),
                )
                .reset_index()
                .sort_values("TotalOverdue", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(
                summary, use_container_width=True, hide_index=True, height=360,
                column_config={
                    "Customer":        st.column_config.NumberColumn("Cust. Code"),
                    "CustomerDisplay": st.column_config.TextColumn("Customer Name", width="large"),
                    "TotalOverdue":    st.column_config.NumberColumn("Total Overdue (THB)", format="%,.2f"),
                    "InvoiceCount":    st.column_config.NumberColumn("Invoices", format="%d"),
                    "MaxDPD":          st.column_config.NumberColumn("Max DPD (days)", format="%d"),
                },
            )
            total = float(summary["TotalOverdue"].sum())
            st.caption(f"Total Overdue: {_fmt_thb(total, view_type)}")


# =============================================================================
# SECTION 4 — Collection Efficiency Trend (On-time vs Late vs Not Collected)
# =============================================================================
def _render_collection_pipeline(df_filtered: pd.DataFrame, view_type: str = "Detail Number"):
    df = df_filtered.copy()

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
        ("Total Invoices",       _fmt_thb(amt_total,       view_type), f"{cnt_total:,} invoices",                    "info"),
        ("Paid",                 _fmt_thb(amt_paid,         view_type), f"{cnt_paid:,} invoices — OverdueAmount = 0", "safe"),
        ("Credit Note",          _fmt_thb(amt_credit_note,  view_type), f"{cnt_credit_note:,} invoices — Amt < 0",   "warning"),
        ("Net Overdue (Unpaid)", _fmt_thb(amt_overdue,      view_type), f"{cnt_overdue:,} invoices — Amt > 0",       "danger" if amt_overdue > 0 else "safe"),
    ]
    for col, (lbl, val, sub, variant) in zip(col_kpis, kpi_data):
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, variant), unsafe_allow_html=True)

    st.markdown(
        "<div style='font-size:0.72rem;color:#8A9BB0;margin-top:6px;margin-bottom:12px;'>"
        "Paid = OverdueAmount = 0 &nbsp;|&nbsp; "
        "Credit Note = OverdueAmount &lt; 0 &nbsp;|&nbsp; "
        "Net Overdue = OverdueAmount &gt; 0"
        "</div>",
        unsafe_allow_html=True,
    )

    floor_pct = 0.03
    floor_val = amt_total * floor_pct

    def _floored(val: float) -> float:
        return max(val, floor_val) if val > 0 else 0.0

    labels  = ["Invoice Total", "Paid", "Net Overdue", "Past Original Due", "Upcoming Due", "Credit Note"]
    parents = ["", "Invoice Total", "Invoice Total", "Net Overdue", "Net Overdue", "Invoice Total"]
    values  = [0, _floored(amt_paid), _floored(amt_overdue),
               _floored(amt_pastdue), _floored(amt_upcoming), _floored(amt_credit_note)]
    real_values = [
        amt_paid + amt_overdue + amt_credit_note,
        amt_paid, amt_overdue, amt_pastdue, amt_upcoming, amt_credit_note,
    ]
    counts = [
        cnt_paid + cnt_overdue + cnt_credit_note,
        cnt_paid, cnt_overdue, cnt_pastdue, cnt_upcoming, cnt_credit_note,
    ]
    pct_of_total = [
        100.0,
        (amt_paid        / amt_total   * 100) if amt_total   > 0 else 0.0,
        (amt_overdue     / amt_total   * 100) if amt_total   > 0 else 0.0,
        (amt_pastdue     / amt_overdue * 100) if amt_overdue > 0 else 0.0,
        (amt_upcoming    / amt_overdue * 100) if amt_overdue > 0 else 0.0,
        (amt_credit_note / amt_total   * 100) if amt_total   > 0 else 0.0,
    ]

    # treemap text ใช้ _fmt_thb แทน raw number
    fmt_labels = [_fmt_thb(v, view_type) for v in real_values]
    colors = [
        PALETTE["sapphire"], PALETTE["jade_lt"],   PALETTE["crimson_lt"],
        PALETTE["crimson"],  PALETTE["amber_lt"],  PALETTE["amber"],
    ]

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        customdata=list(zip(real_values, counts, pct_of_total, fmt_labels)),
        texttemplate=(
            "<b>%{label}</b><br>"
            "%{customdata[3]}<br>"       # fmt_labels — แสดง Rounded หรือ Detail ตาม mode
            "%{customdata[2]:.1f}%"
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Amount  : %{customdata[3]}<br>"
            "Invoices: %{customdata[1]:,}<br>"
            "Share   : %{customdata[2]:.1f}%"
            "<extra></extra>"
        ),
        marker=dict(colors=colors, line=dict(width=2, color="white")),
        textfont=dict(size=11, color="white", family="Inter, sans-serif"),
        tiling=dict(packing="squarify", pad=4),
    ))
    fig.update_layout(
        height=420, margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
        title=dict(text="Collection Pipeline — Invoice Status Treemap",
                   font=dict(size=10, color=FONT_COLOR), x=0),
    )

    col_chart, col_info = st.columns([7, 3], gap="medium")
    with col_chart:
        st.plotly_chart(fig, use_container_width=True, key="chart_collection_pipeline")
    with col_info:
        paid_pct     = (amt_paid        / amt_total   * 100) if amt_total   > 0 else 0.0
        cn_pct       = (amt_credit_note / amt_total   * 100) if amt_total   > 0 else 0.0
        ov_pct       = (amt_overdue     / amt_total   * 100) if amt_total   > 0 else 0.0
        past_pct     = (amt_pastdue     / amt_overdue * 100) if amt_overdue > 0 else 0.0
        upcoming_pct = (amt_upcoming    / amt_overdue * 100) if amt_overdue > 0 else 0.0

        st.markdown(
            "<div style='padding:12px 14px;background:#f7f9fc;"
            "border-radius:8px;border:1px solid #d0dae6;'>"
            "<div style='font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;'>"
            "Information Detail</div>"
            f"<div style='font-size:0.72rem;color:#1A7A4A;margin-bottom:6px;'>"
            f"<b>Paid</b><br>"
            f"{_fmt_thb(amt_paid, view_type)} ({paid_pct:.1f}%)<br>"
            f"{cnt_paid:,} invoices</div>"
            f"<div style='font-size:0.72rem;color:#B5620A;margin-bottom:6px;'>"
            f"<b>Credit Note</b><br>"
            f"{_fmt_thb(amt_credit_note, view_type)} ({cn_pct:.1f}%)<br>"
            f"{cnt_credit_note:,} invoices</div>"
            f"<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:2px;'>"
            f"<b>Net Overdue</b><br>"
            f"{_fmt_thb(amt_overdue, view_type)} ({ov_pct:.1f}%)<br>"
            f"{cnt_overdue:,} invoices</div>"
            f"<div style='font-size:0.72rem;color:#A01F2D;padding-left:10px;"
            f"margin-bottom:2px;border-left:2px solid #A01F2D;'>"
            f"Past Due<br>"
            f"{_fmt_thb(amt_pastdue, view_type)} ({past_pct:.1f}%) | {cnt_pastdue:,} inv</div>"
            f"<div style='font-size:0.72rem;color:#E8A838;padding-left:10px;"
            f"margin-bottom:10px;border-left:2px solid #E8A838;'>"
            f"Upcoming Due<br>"
            f"{_fmt_thb(amt_upcoming, view_type)} ({upcoming_pct:.1f}%) | {cnt_upcoming:,} inv</div>"
            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;'>"
            "Variables</div>"
            "<div style='font-size:0.72rem;color:#3D5166;line-height:1.6;'>"
            "OverdueAmount<br>OriginalDueDate<br>InvoiceAmount"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div style='font-size:0.72rem;color:#8A9BB0;margin-top:4px;'>"
        "Segment sizes scaled with 3% floor for visibility — hover for exact values."
        "</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# SECTION 6 — Raw Joined Table
# =============================================================================
def _render_cash_inflow_forecast(df_filtered: pd.DataFrame, view_type: str = "Detail Number"):
    df = df_filtered.copy()

    amount_col = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"
    today      = pd.Timestamp("today").normalize()

    c1, c2 = st.columns([1, 1])
    with c1:
        horizon = st.selectbox(
            "Forecast Horizon",
            options=["7 days", "14 days", "30 days", "60 days", "90 days", "120 days"],
            index=2, key="cif_horizon", label_visibility="visible",
        )
    with c2:
        date_col_options, date_col_labels = [], []
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
            index=0, key="cif_date_col", label_visibility="visible",
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
        .reset_index().sort_values("WeekNum")
    )

    if weekly.empty:
        st.info("No weekly data.")
        return

    total_forecast = float(weekly["Amount"].sum())
    peak_week      = weekly.loc[weekly["Amount"].idxmax(), "WeekLabel"]
    trough_week    = weekly.loc[weekly["Amount"].idxmin(), "WeekLabel"]

    # KPI cards — ใช้ view_type
    k1, k2, k3 = st.columns(3, gap="small")
    for col, lbl, val, sub, variant in [
        (k1, "Total Planned Inflow", _fmt_thb(total_forecast, view_type),
         f"Next {horizon_days} days — {amount_col}", "info"),
        (k2, "Peak Week",   peak_week,   "Highest planned inflow", "safe"),
        (k3, "Trough Week", trough_week, "Lowest planned inflow",  "warning"),
    ]:
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, variant), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

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
    avg_val         = float(weekly["Amount"].mean())

    # Y axis ตาม view_type — detect magnitude จริง
    max_raw = float(weekly["Amount"].max()) if not weekly.empty else 0.0
    if view_type == "Rounded Number":
        if max_raw >= 1_000_000_000:
            y_div, y_title = 1_000_000_000, "Planned Inflow (Billion Baht)"
        elif max_raw >= 1_000_000:
            y_div, y_title = 1_000_000, "Planned Inflow (Million Baht)"
        elif max_raw >= 1_000:
            y_div, y_title = 1_000, "Planned Inflow (Thousand Baht)"
        else:
            y_div, y_title = 1, "Planned Inflow (Baht)"

        weekly["Y_PLOT"]  = weekly["Amount"] / y_div
        avg_plot          = avg_val / y_div
        y_tickfmt         = ".1f"
        y_axis_cfg        = dict(
            title=y_title,
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            tickformat=y_tickfmt, rangemode="tozero",
        )
        hover_amt_fmt = lambda v: _fmt_thb(v, view_type)
        avg_annotation = _fmt_bar_mon(avg_val, view_type)
    else:
        weekly["Y_PLOT"] = weekly["Amount"]
        avg_plot         = avg_val
        y_axis_cfg       = dict(
            title=f"{amount_col} (Baht)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            tickformat=",.0f", rangemode="tozero",
        )
        hover_amt_fmt  = lambda v: f"{v:,.2f} Baht"
        avg_annotation = f"{avg_val:,.2f}"

    fig = go.Figure()

    for i, band in enumerate(month_bands):
        x0 = x_labels[band["start"]]
        x1 = x_labels[band["end"]]
        fig.add_vrect(x0=x0, x1=x1, fillcolor=band_colors_alt[i % 2], line_width=0, layer="below")
        mid_label = x_labels[(band["start"] + band["end"]) // 2]
        fig.add_annotation(
            x=mid_label, y=1.02, yref="paper",
            text=f"<b>{band['month']}</b>",
            showarrow=False, font=dict(size=8, color="#5a6a7a"),
            xanchor="center", yanchor="bottom",
        )

    fig.add_trace(go.Scatter(
        x=x_labels, y=weekly["Y_PLOT"].tolist(),
        mode="none", fill="tozeroy",
        fillcolor="rgba(58,123,213,0.07)",
        showlegend=False, hoverinfo="skip",
    ))

    point_colors = [
        PALETTE["jade_lt"] if v >= avg_plot else PALETTE["sapphire_lt"]
        for v in weekly["Y_PLOT"]
    ]

    # customdata เก็บ raw Amount เพื่อ hover แสดงตามโหมด
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=weekly["Y_PLOT"].tolist(),
        mode="lines+markers",
        name="Planned Cash Inflow",
        line=dict(color=PALETTE["sapphire_lt"], width=2.5, shape="spline", smoothing=0.7),
        marker=dict(size=8, color=point_colors, line=dict(color="white", width=2)),
        customdata=list(zip(
            weekly["Amount"].tolist(),          # [0] raw amount
            weekly["Invoices"].tolist(),        # [1]
            weekly["WeekStart"].dt.strftime("%d %b %Y").tolist(),  # [2]
            weekly["WeekEnd"].dt.strftime("%d %b %Y").tolist(),    # [3]
            weekly["MonthYear"].tolist(),       # [4]
        )),
        hovertemplate=(
            "<b>%{x}</b> — %{customdata[4]}<br>"
            "%{customdata[2]} to %{customdata[3]}<br>"
            "Planned Inflow : %{customdata[0]:,.2f} Baht<br>"
            "Invoices       : %{customdata[1]:,}"
            "<extra></extra>"
        ),
    ))

    fig.add_hline(
        y=avg_plot,
        line_dash="dot", line_color="#cccccc", line_width=1,
        annotation_text=f"Avg {avg_annotation}",
        annotation_font=dict(size=8, color="#999999"),
        annotation_position="bottom right",
    )

    apply_base_layout(fig, {
        "height": 400,
        "margin": dict(l=0, r=20, t=50, b=20),
        "title": dict(
            text=(
                f"Cash Inflow Planning — {amount_col} | "
                f"Next {horizon_days} days "
                f"({today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')})"
            ),
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            showgrid=False, color=FONT_COLOR,
            tickfont=dict(size=9), tickangle=-35, type="category",
        ),
        "yaxis": y_axis_cfg,
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_cash_inflow")

    st.markdown(
        f"<div style='font-size:0.75rem;color:#8A9BB0;margin-top:2px;'>"
        f"Based on {selected_date_col} | Amount = {amount_col} | "
        f"Horizon: {today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_future_collection_forecast(df_overdue: pd.DataFrame, view_type: str = "Detail Number"):
    df = df_overdue.copy()

    if "OverdueAmount" not in df.columns:
        st.info("OverdueAmount not found.")
        return

    today = pd.Timestamp("today").normalize()
    c1, c2 = st.columns([1, 1])
    with c1:
        horizon = st.selectbox(
            "Horizon (days)", options=["7", "14", "30", "60", "90", "120"],
            index=2, key="fcf_horizon", label_visibility="visible",
        )
    with c2:
        date_col_options, date_col_labels = [], []
        for dc, lbl in [
            ("CollectionDate",  "CollectionDate (planned extension)"),
            ("OriginalDueDate", "OriginalDueDate (original due)"),
            ("CustomerDueDate", "CustomerDueDate (customer confirm)"),
        ]:
            if dc in df.columns:
                date_col_options.append(dc)
                date_col_labels.append(lbl)
        selected_date_col = st.selectbox(
            "Based on", options=date_col_options,
            format_func=lambda x: dict(zip(date_col_options, date_col_labels)).get(x, x),
            index=0, key="fcf_date_col", label_visibility="visible",
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
            f"No unpaid invoices with {selected_date_col} "
            f"within next {horizon_days} days (up to {cutoff.strftime('%d %b %Y')})."
        )
        return

    daily = (
        df_plan.groupby(selected_date_col)
        .agg(Amount=("OverdueAmount", "sum"), Invoices=("OverdueAmount", "count"))
        .reset_index().sort_values(selected_date_col)
    )
    daily["Cumulative"] = daily["Amount"].cumsum()

    def _sum_horizon(d):
        return float(daily[daily[selected_date_col] <= today + pd.Timedelta(days=d)]["Amount"].sum())

    next7  = _sum_horizon(7)
    next14 = _sum_horizon(14)
    next30 = _sum_horizon(30)
    total  = float(daily["Amount"].sum())

    # KPI cards — ใช้ view_type
    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, lbl, val, sub in [
        (k1, "Next 7 Days",         _fmt_thb(next7,  view_type), "Overdue Amount"),
        (k2, "Next 14 Days",        _fmt_thb(next14, view_type), "Overdue Amount"),
        (k3, "Next 30 Days",        _fmt_thb(next30, view_type), "Overdue Amount"),
        (k4, f"Total ({horizon}d)", _fmt_thb(total,  view_type), "Overdue Amount"),
    ]:
        with col:
            st.markdown(_mon_kpi_card(lbl, val, sub, "info"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    # Y axis detect magnitude จาก raw
    max_raw = float(daily["Amount"].max()) if not daily.empty else 0.0
    max_cum = float(daily["Cumulative"].max()) if not daily.empty else 0.0

    if view_type == "Rounded Number":
        if max_raw >= 1_000_000_000:
            y_div = 1_000_000_000; y_title = "Overdue Amount (Billion Baht)"
            y2_div = 1_000_000_000; y2_title = "Cumulative (Billion Baht)"
        elif max_raw >= 1_000_000:
            y_div = 1_000_000; y_title = "Overdue Amount (Million Baht)"
            y2_div = 1_000_000 if max_cum < 1_000_000_000 else 1_000_000_000
            y2_title = f"Cumulative ({'Million' if y2_div == 1_000_000 else 'Billion'} Baht)"
        elif max_raw >= 1_000:
            y_div = 1_000; y_title = "Overdue Amount (Thousand Baht)"
            y2_div = 1_000; y2_title = "Cumulative (Thousand Baht)"
        else:
            y_div = 1; y_title = "Overdue Amount (Baht)"
            y2_div = 1; y2_title = "Cumulative (Baht)"

        daily["Y_BAR"]  = daily["Amount"]     / y_div
        daily["Y_LINE"] = daily["Cumulative"] / y2_div
        bar_tickfmt  = ".1f"
        line_tickfmt = ".1f"
        hover_bar  = "<b>%{x}</b><br>Planned Collect : %{customdata[0]}<extra></extra>"
        hover_line = "<b>%{x}</b><br>Cumulative : %{customdata[1]}<extra></extra>"
        daily["_bar_fmt"]  = daily["Amount"].apply(lambda v: _fmt_thb(v, view_type))
        daily["_line_fmt"] = daily["Cumulative"].apply(lambda v: _fmt_thb(v, view_type))
    else:
        y_div = 1; y_title = "Overdue Amount (Baht)"
        y2_div = 1; y2_title = "Cumulative (Baht)"
        daily["Y_BAR"]  = daily["Amount"]
        daily["Y_LINE"] = daily["Cumulative"]
        bar_tickfmt  = ",.0f"
        line_tickfmt = ",.0f"
        hover_bar  = "<b>%{x}</b><br>Planned Collect : %{customdata[0]}<extra></extra>"
        hover_line = "<b>%{x}</b><br>Cumulative : %{customdata[1]}<extra></extra>"
        daily["_bar_fmt"]  = daily["Amount"].apply(lambda v: f"{v:,.2f} Baht")
        daily["_line_fmt"] = daily["Cumulative"].apply(lambda v: f"{v:,.2f} Baht")

    x_labels = daily[selected_date_col].dt.strftime("%b %d").tolist()
    custom   = list(zip(daily["_bar_fmt"].tolist(), daily["_line_fmt"].tolist()))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x_labels, y=daily["Y_BAR"].tolist(),
        name="Daily Overdue Amount",
        marker_color=PALETTE["sapphire_lt"], opacity=0.6,
        customdata=custom,
        hovertemplate=hover_bar,
    ))
    fig.add_trace(go.Scatter(
        x=x_labels, y=daily["Y_LINE"].tolist(),
        name="Cumulative", mode="lines+markers", yaxis="y2",
        line=dict(color=PALETTE["jade_lt"], width=2),
        marker=dict(size=5, color=PALETTE["jade_lt"]),
        customdata=custom,
        hovertemplate=hover_line,
    ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=60, t=30, b=10),
        "barmode": "overlay",
        "title": dict(
            text=(
                f"Collection Planning — Overdue Amount | "
                f"Next {horizon_days} days "
                f"({today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')})"
            ),
            font=dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(showgrid=False, color=FONT_COLOR, tickangle=-35, tickfont=dict(size=8)),
        "yaxis": dict(
            title=y_title, showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9), tickformat=bar_tickfmt,
        ),
        "yaxis2": dict(
            title=y2_title, overlaying="y", side="right",
            showgrid=False, color=PALETTE["jade_lt"],
            tickfont=dict(size=9), tickformat=line_tickfmt,
        ),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02,
                       xanchor="right", x=1, font=dict(size=9)),
        "showlegend": True,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_future_forecast")
    st.markdown(
        f"<div style='font-size:0.75rem;color:#8A9BB0;margin-top:2px;'>"
        f"Based on {selected_date_col} | Only unpaid (OverdueAmount > 0) | "
        f"Horizon: {today.strftime('%d %b %Y')} → {cutoff.strftime('%d %b %Y')}"
        f"</div>",
        unsafe_allow_html=True,
    )



def _render_credit_planner_board(df: pd.DataFrame):
    if df.empty:
        st.info("No data for action board.")
        return

    today     = pd.Timestamp("today").normalize()
    due_min   = df["OriginalDueDate"].min() if "OriginalDueDate" in df.columns else pd.NaT
    due_max   = df["OriginalDueDate"].max() if "OriginalDueDate" in df.columns else pd.NaT
    due_range = ""
    if pd.notna(due_min) and pd.notna(due_max):
        due_range = f"{due_min.strftime('%d %b %Y')} — {due_max.strftime('%d %b %Y')}"

    st.markdown(
        f"<div style='display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap;'>"
        f"<div style='font-size:0.78rem;color:#3D5166;'>"
        f"<span style='font-weight:600;color:#1B4F8A;'>As of</span> {today.strftime('%d %b %Y')}</div>"
        f"<div style='font-size:0.78rem;color:#3D5166;'>"
        f"<span style='font-weight:600;color:#1B4F8A;'>Invoice Due Range</span> {due_range}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    cust_agg = _agg_customer_overdue(df)
    if cust_agg.empty:
        st.info("No overdue data for action board.")
        return

    label_col = "CustomerName" if "CustomerName" in cust_agg.columns else "Customer"

    has_customer_due = "CustomerDueDate" in df.columns
    has_original_due = "OriginalDueDate" in df.columns

    if has_customer_due and has_original_due:
        ext_df = df[df["OverdueAmount"] > 0].copy()
        ext_df["_ExtDays"] = (
            (ext_df["CustomerDueDate"] - ext_df["OriginalDueDate"])
            .dt.days.fillna(0).clip(lower=0)
        )
        ext_agg = ext_df.groupby("Customer")["_ExtDays"].max().reset_index()
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
        f"<div style='font-size:0.78rem;color:#3D5166;margin-bottom:12px;'>"
        f"Rules: Overdue &gt; {CALL_THRESHOLD/1e6:.0f}M THB = Review Customer &nbsp;|&nbsp; "
        f"Utilization &gt; {REVIEW_UTIL_THRESHOLD:.0f}% = Review Credit Limit &nbsp;|&nbsp; "
        f"Extension &gt; {ESCALATE_EXT_DAYS} days = Escalate"
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

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    action_tabs = st.tabs(["Review Customer", "Review Credit Limit", "Invoice Detail"])

    with action_tabs[0]:
        tbl_review = (
            cust_agg[cust_agg["Action_Review"]]
            [[c for c in ["Customer", label_col, "NetOverdue", "GrossOverdue",
                          "UtilizationPct", "MaxDPD", "MaxExtension"] if c in cust_agg.columns]]
            .sort_values("NetOverdue", ascending=False)
            .reset_index(drop=True)
        )
        if "InvoiceDocument" in df.columns:
            inv_breakdown = (
                df[df["OverdueAmount"] > 0]
                .groupby(["Customer", "InvoiceDocument"])["OverdueAmount"]
                .sum().reset_index()
                .rename(columns={"OverdueAmount": "InvAmount"})
            )
            inv_summary = (
                inv_breakdown.groupby("Customer")
                .apply(lambda x: ", ".join(
                    f"{int(row['InvoiceDocument'])}:{row['InvAmount']:,.0f}"
                    for _, row in x.sort_values("InvAmount", ascending=False).head(3).iterrows()
                ))
                .reset_index().rename(columns={0: "Top Invoices"})
            )
            tbl_review = tbl_review.merge(inv_summary, on="Customer", how="left")

        st.dataframe(
            tbl_review, use_container_width=True, height=320, hide_index=True,
            column_config={
                "Customer":       st.column_config.NumberColumn("Cust. Code", width="small"),
                label_col:        st.column_config.TextColumn("Customer Name", width="large"),
                "NetOverdue":     st.column_config.NumberColumn("Net Overdue (THB)", format="%,.0f"),
                "GrossOverdue":   st.column_config.NumberColumn("Gross Overdue (THB)", format="%,.0f"),
                "UtilizationPct": st.column_config.NumberColumn("Util %", format="%.1f%%"),
                "MaxDPD":         st.column_config.NumberColumn("Max DPD", format="%d days"),
                "MaxExtension":   st.column_config.NumberColumn("Max Extension (days)", format="%d days"),
                "Top Invoices":   st.column_config.TextColumn("Top 3 Invoices (Doc:THB)", width="large"),
            },
        )
        st.caption(f"{len(tbl_review):,} customer(s) with overdue > {CALL_THRESHOLD/1e6:.0f}M THB")

    with action_tabs[1]:
        tbl_creditrv = (
            cust_agg[cust_agg["Action_CreditRv"]]
            [[c for c in ["Customer", label_col, "UtilizationPct", "NetOverdue",
                          "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB", "MaxExtension"] if c in cust_agg.columns]]
            .sort_values("UtilizationPct", ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(
            tbl_creditrv, use_container_width=True, height=320, hide_index=True,
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
        st.caption(f"{len(tbl_creditrv):,} customer(s) with utilization > {REVIEW_UTIL_THRESHOLD:.0f}%")

    with action_tabs[2]:
        st.caption("Invoice-level breakdown for all action customers.")
        action_codes = set(
            cust_agg[cust_agg["Action_Review"] | cust_agg["Action_CreditRv"]]["Customer"].tolist()
        )
        inv_detail = df[
            df["Customer"].isin(action_codes) & (df["OverdueAmount"] > 0)
        ].copy()

        if inv_detail.empty:
            st.info("No overdue invoices for action customers.")
        else:
            inv_detail = inv_detail.loc[:, ~inv_detail.columns.duplicated()]

            name_cols_to_show = []
            if label_col in inv_detail.columns:
                name_cols_to_show.append(label_col)
            if "CustomerName" in inv_detail.columns and "CustomerName" != label_col:
                name_cols_to_show.append("CustomerName")

            display_inv_cols = list(dict.fromkeys([c for c in (
                ["Customer"]
                + name_cols_to_show
                + ["InvoiceDocument",
                   "OriginalDueDate", "CollectionDate", "CustomerDueDate",
                   "OverdueAmount", "InvoiceAmount", "DPD",
                   "HasExtension", "ExtensionDays", "RiskTier"]
            ) if c in inv_detail.columns]))

            for dc in ("OriginalDueDate", "CollectionDate", "CustomerDueDate"):
                if dc in inv_detail.columns:
                    if not pd.api.types.is_datetime64_any_dtype(inv_detail[dc]):
                        inv_detail[dc] = pd.to_datetime(inv_detail[dc], errors="coerce")
                    inv_detail[dc] = inv_detail[dc].dt.strftime("%Y-%m-%d")

            inv_detail = (
                inv_detail[display_inv_cols]
                .sort_values(["Customer", "OverdueAmount"], ascending=[True, False])
                .reset_index(drop=True)
            )

            col_cfg = {
                "Customer":        st.column_config.NumberColumn("Cust. Code"),
                label_col:         st.column_config.TextColumn("Customer Name (Avail)", width="large"),
                "CustomerName":    st.column_config.TextColumn("Customer Name (Overdue)", width="large"),
                "InvoiceDocument": st.column_config.TextColumn("Invoice Doc.", width="medium"),
                "OverdueAmount":   st.column_config.NumberColumn("Overdue (THB)", format="%,.2f"),
                "InvoiceAmount":   st.column_config.NumberColumn("Invoice Amt (THB)", format="%,.2f"),
                "DPD":             st.column_config.NumberColumn("DPD (days)", format="%d"),
                "HasExtension":    st.column_config.CheckboxColumn("Has Extension"),
                "ExtensionDays":   st.column_config.NumberColumn("Extension (days)", format="%d"),
                "RiskTier":        st.column_config.TextColumn("Risk Tier"),
            }

            st.dataframe(
                inv_detail, use_container_width=True, height=420,
                hide_index=True, column_config=col_cfg,
            )
            st.caption(f"{len(inv_detail):,} invoice(s) for {len(action_codes):,} action customer(s)")


def _render_credit_journey_sankey(df_filtered: pd.DataFrame, view_type: str = "Detail Number"):
    df = df_filtered[df_filtered["OverdueAmount"] >= 0].copy()

    if "OriginalDueDate" not in df.columns or df.empty:
        st.info("No invoice data available for Sankey.")
        return

    has_customer_due = "CustomerDueDate" in df.columns
    amount_col       = "InvoiceAmount" if "InvoiceAmount" in df.columns else "OverdueAmount"

    if has_customer_due:
        df["_ExtDays"] = (
            (df["CustomerDueDate"] - df["OriginalDueDate"])
            .dt.days.fillna(0).clip(lower=0)
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
                return "Paid On-Time" if row["CustomerDueDate"] <= row["OriginalDueDate"] else "Paid with Extension"
            return "Paid On-Time"
        return "Overdue (Large)" if row[amount_col] >= LARGE_OVERDUE_THB else "Overdue (Small)"

    df["_ExtBucket"] = df["_ExtDays"].apply(_ext_bucket)
    df["_Outcome"]   = df.apply(_outcome, axis=1)

    flow = (
        df.groupby(["_ExtBucket", "_Outcome"])[amount_col]
        .sum().reset_index()
        .rename(columns={amount_col: "Amount"})
    )
    flow = flow[flow["Amount"] > 0]

    if flow.empty:
        st.info("No flow data to display.")
        return

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

    # node hover ใช้ _fmt_thb
    node_totals = {}
    for s, t, v in zip(sources, targets, values):
        node_totals[s] = node_totals.get(s, 0) + v
        node_totals[t] = node_totals.get(t, 0) + v

    node_hover = [
        f"{all_nodes[i]}<br>Total: {_fmt_thb(node_totals.get(i, 0), view_type)}"
        for i in range(len(all_nodes))
    ]
    link_hover = [
        f"{all_nodes[s]} → {all_nodes[t]}<br>Amount: {_fmt_thb(v, view_type)}"
        for s, t, v in zip(sources, targets, values)
    ]

    col_chart, col_info = st.columns([7, 3], gap="medium")

    with col_chart:
        fig = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18, thickness=22,
                line=dict(color="#d0dae6", width=0.5),
                label=all_nodes,
                color=node_colors[:len(all_nodes)],
                hovertemplate="%{customdata}<extra></extra>",
                customdata=node_hover,
            ),
            link=dict(
                source=sources, target=targets, value=values, color=link_colors,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=link_hover,
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
        paid_pct     = (total_paid   / total_all * 100) if total_all > 0 else 0.0
        unpaid_pct   = (total_unpaid / total_all * 100) if total_all > 0 else 0.0
        n_ext        = int((df["_ExtDays"] > 0).sum())
        avg_ext      = float(df.loc[df["_ExtDays"] > 0, "_ExtDays"].mean()) if n_ext > 0 else 0.0
        max_ext      = float(df["_ExtDays"].max())

        paid_fmt   = _fmt_thb(total_paid,   view_type)
        unpaid_fmt = _fmt_thb(total_unpaid, view_type)

        st.markdown(
            "<div style='padding:12px 14px;background:#f7f9fc;"
            "border-radius:8px;border:1px solid #d0dae6;'>"
            "<div style='font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;'>"
            "Summary</div>"
            f"<div style='font-size:0.72rem;color:#1A7A4A;margin-bottom:3px;'>"
            f"Paid: {paid_fmt} ({paid_pct:.1f}%)</div>"
            f"<div style='font-size:0.72rem;color:#A01F2D;margin-bottom:3px;'>"
            f"Unpaid: {unpaid_fmt} ({unpaid_pct:.1f}%)</div>"
            f"<div style='font-size:0.72rem;color:#3D5166;margin-bottom:3px;'>"
            f"With Extension: {n_ext:,} invoices</div>"
            f"<div style='font-size:0.72rem;color:#3D5166;margin-bottom:10px;'>"
            f"Avg Ext: {avg_ext:.1f}d  |  Max: {max_ext:.0f}d</div>"
            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;'>"
            "Extension Buckets (Left)</div>"
            "<div style='font-size:0.72rem;color:#3D5166;line-height:1.7;'>"
            "Ext 0-7d  — Extension 0-7 days<br>"
            "Ext 8-30d — Extension 8-30 days<br>"
            "Ext 30+d  — Extension &gt; 30 days"
            "</div>"
            "<div style='border-top:1px solid #d0dae6;margin-top:8px;padding-top:8px;"
            "font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;'>"
            "ExtDays</div>"
            "<div style='font-size:0.72rem;color:#3D5166;margin-bottom:10px;'>"
            "CustomerDueDate &minus; OriginalDueDate</div>"
            "<div style='border-top:1px solid #d0dae6;padding-top:8px;"
            "font-size:0.72rem;font-weight:700;color:#1B4F8A;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;'>"
            "Variables</div>"
            "<div style='font-size:0.72rem;color:#3D5166;line-height:1.6;'>"
            "CustomerDueDate<br>OriginalDueDate<br>CollectionDate<br>OverdueAmount"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Flow Detail Table", expanded=False):
        tab_flow, tab_flow_detail = st.tabs(["Summary", "Invoice Detail"])

        with tab_flow:
            flow_disp = (
                flow.rename(columns={"_ExtBucket": "Extension Bucket", "_Outcome": "Outcome", "Amount": "Amount (THB)"})
                .sort_values("Amount (THB)", ascending=False)
                .reset_index(drop=True)
            )
            # เพิ่มคอลัมน์ formatted สำหรับ view_type
            flow_disp["Amount (Formatted)"] = flow_disp["Amount (THB)"].apply(
                lambda v: _fmt_thb(v, view_type)
            )
            flow_disp["Amount (THB)"] = flow_disp["Amount (THB)"].round(0)
            st.dataframe(
                flow_disp[["Extension Bucket", "Outcome", "Amount (THB)", "Amount (Formatted)"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "Extension Bucket":  st.column_config.TextColumn("Extension Bucket"),
                    "Outcome":           st.column_config.TextColumn("Outcome"),
                    "Amount (THB)":      st.column_config.NumberColumn("Amount (THB)", format="%,.0f"),
                    "Amount (Formatted)":st.column_config.TextColumn("Amount (Formatted)"),
                },
            )

        with tab_flow_detail:
            st.caption("Invoice-level detail per extension bucket and outcome.")
            detail_inv = df.copy()
            detail_inv = detail_inv.loc[:, ~detail_inv.columns.duplicated()]
            detail_inv = detail_inv.rename(columns={
                "_ExtBucket": "Ext Bucket", "_Outcome": "Outcome", "_ExtDays": "Ext Days",
            })
            detail_cols = list(dict.fromkeys([c for c in [
                "Customer", "CustomerName", "InvoiceDocument",
                "Ext Bucket", "Outcome", "Ext Days",
                "OverdueAmount", amount_col,
                "OriginalDueDate", "CustomerDueDate", "CollectionDate",
            ] if c in detail_inv.columns]))

            for dc in ("OriginalDueDate", "CustomerDueDate", "CollectionDate"):
                if dc in detail_inv.columns:
                    if not pd.api.types.is_datetime64_any_dtype(detail_inv[dc]):
                        detail_inv[dc] = pd.to_datetime(detail_inv[dc], errors="coerce")
                    detail_inv[dc] = detail_inv[dc].dt.strftime("%Y-%m-%d")

            detail_inv = (
                detail_inv[detail_cols]
                .sort_values(["Ext Bucket", "OverdueAmount"], ascending=[True, False])
                .reset_index(drop=True)
            )
            st.dataframe(
                detail_inv, use_container_width=True, hide_index=True, height=420,
                column_config={
                    "Customer":        st.column_config.NumberColumn("Cust. Code"),
                    "CustomerName":    st.column_config.TextColumn("Customer Name", width="large"),
                    "InvoiceDocument": st.column_config.TextColumn("Invoice Doc.", width="medium"),
                    "Ext Bucket":      st.column_config.TextColumn("Ext Bucket"),
                    "Outcome":         st.column_config.TextColumn("Outcome"),
                    "Ext Days":        st.column_config.NumberColumn("Ext Days", format="%d"),
                    "OverdueAmount":   st.column_config.NumberColumn("Overdue (THB)", format="%,.2f"),
                    amount_col:        st.column_config.NumberColumn("Invoice Amt (THB)", format="%,.2f"),
                },
            )
            st.caption(f"{len(detail_inv):,} invoice record(s)")

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
