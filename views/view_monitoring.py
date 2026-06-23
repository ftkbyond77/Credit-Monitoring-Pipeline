# =============================================================================
# views/view_monitoring.py
# Dashboard : Credit Monitoring (Joined View — Availability × Overdue)
# Entry point : render()
#
# Layout:
#   ── SECTION 0 : Title bar + Filters
#   ── SECTION 1 : Monitoring KPI Row (5 cards) — joined health signal
#   ── SECTION 2 : Credit Health Matrix (Utilization vs Overdue Risk)
#                  [Bubble Scatter 60%] | [Risk Tier Donut 40%]
#   ── SECTION 3 : Watchlist — customers needing immediate attention
#                  [Heatmap table: Util% × DPD × Overdue Amount]
#   ── SECTION 4 : Collection Efficiency Trend (On-time vs Delayed)
#                  [Stacked Bar: on-time / late / overdue over time]
#   ── SECTION 5 : Overdue Breakdown Stats
#                  [Aging Bar] | [Top Overdue Customers Bar]
#   ── SECTION 6 : Raw Joined Table (expandable)
#
# Join key : df_overdue.Customer == df_avail.CUSTOMER_CODE
# =============================================================================

import streamlit as st
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

    # ------------------------------------------------------------------
    # Title bar
    # ------------------------------------------------------------------
    st.markdown(
        dash_title_bar(
            "Credit Monitoring Dashboard",
            "Analytics Dashboard — joined credit health signal (Availability × Overdue)",
        ),
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Prepare & join data
    # ------------------------------------------------------------------
    df_avail_prep   = _prepare_avail(df_avail.copy())
    df_overdue_prep = _prepare_overdue(df_overdue.copy())
    df_joined       = _build_joined(df_avail_prep, df_overdue_prep)

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
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
    st.markdown("<br>", unsafe_allow_html=True)

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
    st.markdown("<br>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 3 : Watchlist
    # ==================================================================
    st.markdown(section_header("Watchlist — Customers Needing Immediate Attention"), unsafe_allow_html=True)
    _render_watchlist(df_filtered)
    st.markdown("<br>", unsafe_allow_html=True)

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

    # 4A : Portfolio-level stacked bar
    _render_collection_trend(df_overdue_prep, selected_company, granularity)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4B : Per-customer drill-down
    st.markdown(
        "<p style='font-size:0.85rem;font-weight:700;color:#1B4F8A;"
        "margin:0 0 6px 0;letter-spacing:0.02em;'>"
        "On-Time vs Delay Trend Analysis — Per Customer</p>",
        unsafe_allow_html=True,
    )
    _render_ontime_delay_trend(
        df_overdue      = df_overdue_prep,
        selected_company= selected_company,
        granularity     = granularity,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 5 : Overdue Breakdown Stats
    # ==================================================================
    st.markdown(section_header("Overdue Breakdown Statistics"), unsafe_allow_html=True)
    col_aging, col_top = st.columns([1, 1], gap="medium")
    with col_aging:
        _render_aging_bar(df_filtered)
    with col_top:
        _render_top_overdue(df_filtered)
    st.markdown("<br>", unsafe_allow_html=True)

    # ==================================================================
    # SECTION 6 : Raw Joined Table
    # ==================================================================
    with st.expander("View Joined Records — Credit Availability × Overdue", expanded=False):
        _render_joined_table(df_filtered)


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
    """Clean & type-cast df_overdue — strip quote artifacts, parse dates."""
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

    # Standardise join key
    if "Customer" in df.columns:
        df["Customer"] = (
            pd.to_numeric(df["Customer"], errors="coerce").fillna(0).astype(int)
        )

    today = pd.Timestamp("today").normalize()
    df["IsOverdue"]  = df["OverdueAmount"] < 0  # negative = actual overdue
    df["OverdueAbs"] = df["OverdueAmount"].abs()

    if "OriginalDueDate" in df.columns:
        df["DPD"]          = (today - df["OriginalDueDate"]).dt.days.clip(lower=0)
        df["DueYear"]      = df["OriginalDueDate"].dt.year.astype("Int64")
        df["DueMonth"]     = df["OriginalDueDate"].dt.month.astype("Int64")
        df["DueQuarter"]   = df["OriginalDueDate"].dt.quarter.astype("Int64")
        df["DueMonthLabel"] = df["DueMonth"].map(MONTH_MAP)

        df["AgingBucket"] = pd.cut(
            df["DPD"],
            bins=[-1, 30, 60, 90, float("inf")],
            labels=["1-30", "31-60", "61-90", "90+"],
        )

    # Payment classification
    if "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
        df["PaidLate"] = (
            df["CollectionDate"] > df["OriginalDueDate"]
        )
        df["PaidOnTime"] = (
            df["CollectionDate"].notna()
            & ~df["PaidLate"]
        )
        df["NotCollected"] = df["CollectionDate"].isna()
    return df


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

    # Available companies from overdue
    available_companies = (
        sorted(df_overdue["CompanyCode"].dropna().unique().tolist())
        if "CompanyCode" in df_overdue.columns
        else ["All"]
    )
    default_idx = 0
    if "1190" in available_companies:
        default_idx = available_companies.index("1190")

    # Available years
    avail_years = (
        sorted(df_avail["AVAIL_YEAR"].dropna().unique().tolist())
        if "AVAIL_YEAR" in df_avail.columns
        else []
    )

    COLS = [1.0, 1.0, 1.0, 1.0, 1.8]
    lc1, lc2, lc3, lc4, lc5 = st.columns(COLS, gap="small")
    with lc1: st.markdown(f"<span style='{LABEL_STYLE}'>Company Code</span>", unsafe_allow_html=True)
    with lc2: st.markdown(f"<span style='{LABEL_STYLE}'>Availability Year</span>", unsafe_allow_html=True)
    with lc3: st.markdown(f"<span style='{LABEL_STYLE}'>Risk Tier</span>", unsafe_allow_html=True)
    with lc4: st.markdown(f"<span style='{LABEL_STYLE}'>DPD Bucket</span>", unsafe_allow_html=True)
    with lc5: st.markdown(f"<span style='{LABEL_STYLE}'>Search Customer Name</span>", unsafe_allow_html=True)

    wc1, wc2, wc3, wc4, wc5 = st.columns(COLS, gap="small")

    with wc1:
        selected_company = st.selectbox(
            "Company Code", options=available_companies,
            index=default_idx, key="mon_company",
            label_visibility="collapsed",
        )
    with wc2:
        year_options = ["All"] + avail_years
        selected_year = st.selectbox(
            "Year", options=year_options,
            index=0, key="mon_year",
            label_visibility="collapsed",
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
    # Apply filters on joined df
    # ------------------------------------------------------------------
    df = df_joined.copy()

    if "CompanyCode" in df.columns:
        df = df[df["CompanyCode"] == selected_company]

    if selected_year != "All" and "AVAIL_YEAR" in df.columns:
        df = df[df["AVAIL_YEAR"] == selected_year]

    if selected_tier != "All" and "RiskTier" in df.columns:
        df = df[df["RiskTier"] == selected_tier]

    if selected_bucket != "All" and "AgingBucket" in df.columns:
        df = df[df["AgingBucket"].astype(str) == selected_bucket]

    if customer_search:
        name_col = "CustomerName" if "CustomerName" in df.columns else None
        if name_col:
            df = df[df[name_col].str.contains(customer_search, case=False, na=False)]

    return df, selected_company, selected_year


# =============================================================================
# SECTION 1 — Monitoring KPI Row
# =============================================================================
def _render_kpi_row(df: pd.DataFrame):
    """
    5 Monitoring-focused KPIs (joined view):
    1. Total Monitored Customers
    2. Critical Risk Customers (Util >= 80% AND DPD >= 60)
    3. Total Overdue Exposure (THB)
    4. Avg Credit Utilization %
    5. % Customers Overdue
    """
    total_customers = (
        int(df["Customer"].nunique())
        if "Customer" in df.columns else 0
    )
    critical_count = (
        int(df[df["RiskTier"] == "Critical"]["Customer"].nunique())
        if "RiskTier" in df.columns and "Customer" in df.columns else 0
    )
    total_overdue_exposure = (
        float(df[df["IsOverdue"]]["OverdueAbs"].sum())
        if "IsOverdue" in df.columns and "OverdueAbs" in df.columns else 0.0
    )
    avg_util = (
        float(df["UtilizationPct"].dropna().mean())
        if "UtilizationPct" in df.columns else 0.0
    )

    overdue_customers = (
        int(df[df["IsOverdue"]]["Customer"].nunique())
        if "IsOverdue" in df.columns and "Customer" in df.columns else 0
    )
    pct_overdue = (
        (overdue_customers / total_customers * 100)
        if total_customers > 0 else 0.0
    )

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
            "Util ≥80% & DPD ≥60",
            "danger" if critical_count > 0 else "safe",
        ),
        (
            "Overdue Exposure",
            f"{total_overdue_exposure:,.0f}",
            "THB — selected filters",
            "danger" if total_overdue_exposure > 0 else "safe",
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
    Bubble Scatter: X = Utilization%, Y = Total Overdue (THB)
    Bubble size = Clean Credit MB  (fallback = fixed size 18 ถ้าไม่มีข้อมูล)
    Color = Risk Tier
    Each point = 1 unique customer (aggregated)
    """
    need = {"Customer", "UtilizationPct", "OverdueAbs", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("Insufficient columns for Health Matrix.")
        return

    name_col = "CustomerName" if "CustomerName" in df.columns else "Customer"

    # ------------------------------------------------------------------
    # Aggregate per customer
    # ------------------------------------------------------------------
    agg_dict = {
        "UtilizationPct": ("UtilizationPct", "mean"),
        "TotalOverdue":   ("OverdueAbs",      "sum"),
        "RiskTier":       (
            "RiskTier",
            lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"
        ),
    }
    if "CLEAN_CREDIT_MB" in df.columns:
        agg_dict["CLEAN_CREDIT_MB"] = ("CLEAN_CREDIT_MB", "mean")
    if name_col == "CustomerName":
        agg_dict["CustomerName"] = ("CustomerName", "first")

    agg = df.groupby("Customer").agg(**agg_dict).reset_index()

    # ------------------------------------------------------------------
    # BubbleSize — fillna ก่อนทุกขั้นตอน แล้ว cast เป็น float ล้วนๆ
    # ------------------------------------------------------------------
    FALLBACK_SIZE = 18.0

    if "CLEAN_CREDIT_MB" in agg.columns:
        # ① fillna ด้วย 0 ก่อน
        raw_credit = agg["CLEAN_CREDIT_MB"].fillna(0.0)

        # ② ถ้าทุก row เป็น 0 (join ไม่ match เลย) → ใช้ fallback ทั้งหมด
        if raw_credit.sum() == 0:
            agg["BubbleSize"] = FALLBACK_SIZE
        else:
            # ③ clip lower=1 เพื่อไม่ให้ size = 0
            credit_vals       = raw_credit.clip(lower=1.0)
            credit_min        = float(credit_vals.min())
            credit_max        = float(credit_vals.max())
            credit_range      = max(credit_max - credit_min, 1.0)
            agg["BubbleSize"] = 8.0 + ((credit_vals - credit_min) / credit_range) * 42.0
    else:
        agg["BubbleSize"] = FALLBACK_SIZE

    # ④ Safety net สุดท้าย — แทน NaN ที่อาจหลุดรอดมาด้วย fallback
    agg["BubbleSize"] = (
        agg["BubbleSize"]
        .fillna(FALLBACK_SIZE)
        .clip(lower=6.0, upper=60.0)
        .astype(float)
    )

    # ------------------------------------------------------------------
    # UtilizationPct / TotalOverdue — fillna ด้วย 0.0 ก่อนส่ง Plotly
    # ------------------------------------------------------------------
    agg["UtilizationPct"] = agg["UtilizationPct"].fillna(0.0).astype(float)
    agg["TotalOverdue"]   = agg["TotalOverdue"].fillna(0.0).astype(float)

    label_col = "CustomerName" if "CustomerName" in agg.columns else "Customer"

    # ------------------------------------------------------------------
    # Build figure
    # ------------------------------------------------------------------
    fig = go.Figure()

    for tier in TIER_ORDER:
        grp = agg[agg["RiskTier"] == tier].copy()
        if grp.empty:
            continue

        x_vals    = grp["UtilizationPct"].tolist()
        y_vals    = grp["TotalOverdue"].tolist()
        size_vals = grp["BubbleSize"].tolist()       
        text_vals = grp[label_col].astype(str).tolist()

        if "CLEAN_CREDIT_MB" in grp.columns:
            custom = list(zip(
                grp["CLEAN_CREDIT_MB"].fillna(0.0).tolist(),
                grp["TotalOverdue"].tolist(),
            ))
        else:
            custom = [(0.0, v) for v in y_vals]

        fig.add_trace(go.Scatter(
            x          = x_vals,
            y          = y_vals,
            mode       = "markers",
            name       = tier,
            marker     = dict(
                size     = size_vals,          
                color    = TIER_COLOR.get(tier, PALETTE["nodata"]),
                opacity  = 0.80,
                line     = dict(width=1, color="white"),
                sizemode = "diameter",
            ),
            text           = text_vals,
            customdata     = custom,
            hovertemplate  = (
                "<b>%{text}</b><br>"
                "────────────────────<br>"
                "Utilization  : %{x:.1f}%<br>"
                "Overdue      : %{y:,.0f} THB<br>"
                "Clean Credit : %{customdata[0]:,.1f} MB<br>"
                "<extra></extra>"
            ),
        ))

    # Quadrant reference lines
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
        "title":  dict(
            text = "Credit Health Matrix — Utilization % vs Overdue Amount",
            font = dict(size=10, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            title      = "Credit Utilization %",
            ticksuffix = "%",
            showgrid   = True, gridcolor=GRID_COLOR,
            color      = FONT_COLOR, tickfont=dict(size=9),
            range      = [0, max(120.0, max_util)],
        ),
        "yaxis": dict(
            title    = "Total Overdue (THB)",
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
    Styled watchlist table — customers with highest combined risk signal.
    Shows: Name, Util%, DPD (avg), Overdue Amount, Clean Credit, Tier, Alert
    """
    need = {"Customer", "UtilizationPct", "OverdueAbs", "RiskTier"}
    if not need.issubset(df.columns):
        st.info("Watchlist requires joined data.")
        return

    overdue_df = df[df["IsOverdue"]].copy() if "IsOverdue" in df.columns else df.copy()
    if overdue_df.empty:
        st.success("No overdue customers match the current filters.")
        return

    name_col = "CustomerName" if "CustomerName" in overdue_df.columns else "Customer"

    agg_dict = {
        "UtilizationPct": ("UtilizationPct", "mean"),
        "OverdueAbs":     ("OverdueAbs",      "sum"),
        "DPD":            ("DPD",             "max"),
        "RiskTier":       ("RiskTier",        lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"),
        "InvoiceCount":   ("OverdueAbs",      "count"),
    }
    if name_col == "CustomerName":
        agg_dict["CustomerName"] = ("CustomerName", "first")
    if "CLEAN_CREDIT_MB" in overdue_df.columns:
        agg_dict["CLEAN_CREDIT_MB"] = ("CLEAN_CREDIT_MB", "first")
    if "TYPE" in overdue_df.columns:
        agg_dict["TYPE"] = ("TYPE", "first")

    watchlist = overdue_df.groupby("Customer").agg(**agg_dict).reset_index()

    # Sort: Critical first, then by OverdueAbs desc
    tier_rank = {"Critical": 0, "High Risk": 1, "Watch": 2, "Healthy": 3, "Unknown": 4}
    watchlist["_rank"] = watchlist["RiskTier"].map(tier_rank).fillna(9)
    watchlist = (
        watchlist.sort_values(["_rank", "OverdueAbs"], ascending=[True, False])
        .head(top_n)
        .reset_index(drop=True)
    )

    # Alert signal badge
    def _alert(row):
        tier = row["RiskTier"]
        dpd  = row.get("DPD", 0)
        util = row.get("UtilizationPct", 0)
        if tier == "Critical":
            return "🔴 CRITICAL"
        elif tier == "High Risk" and dpd >= DPD_HIGH:
            return "🟠 HIGH DPD"
        elif tier == "High Risk" and util >= 80:
            return "🟠 HIGH UTIL"
        elif tier == "Watch":
            return "🟡 WATCH"
        else:
            return "🟢 MONITOR"

    watchlist["Alert"] = watchlist.apply(_alert, axis=1)
    watchlist["UtilizationPct"] = watchlist["UtilizationPct"].round(1)

    # Display columns
    display_cols = {
        "Customer":       "Cust. Code",
        "CustomerName":   "Customer Name",
        "TYPE":           "Type",
        "UtilizationPct": "Util %",
        "DPD":            "Max DPD",
        "OverdueAbs":     "Overdue (THB)",
        "CLEAN_CREDIT_MB":"Credit Limit (MB)",
        "InvoiceCount":   "Invoices",
        "RiskTier":       "Risk Tier",
        "Alert":          "Alert Signal",
    }
    show_cols = [c for c in display_cols.keys() if c in watchlist.columns]
    tbl = watchlist[show_cols].rename(columns=display_cols)

    col_config = {
        "Cust. Code":       st.column_config.NumberColumn("Cust. Code", width="small"),
        "Customer Name":    st.column_config.TextColumn("Customer Name", width="large"),
        "Type":             st.column_config.TextColumn("Type", width="small"),
        "Util %":           st.column_config.NumberColumn("Util %", format="%.1f%%", width="small"),
        "Max DPD":          st.column_config.NumberColumn("Max DPD", format="%d days", width="small"),
        "Overdue (THB)":    st.column_config.NumberColumn("Overdue (THB)", format="%,.0f", width="medium"),
        "Credit Limit (MB)":st.column_config.NumberColumn("Credit Limit (MB)", format="%.1f", width="medium"),
        "Invoices":         st.column_config.NumberColumn("Invoices", width="small"),
        "Risk Tier":        st.column_config.TextColumn("Risk Tier", width="small"),
        "Alert Signal":     st.column_config.TextColumn("Alert Signal", width="medium"),
    }

    st.dataframe(tbl, use_container_width=True, height=380,
                 hide_index=True, column_config=col_config)

    # Summary strip below table
    n_critical = int((watchlist["RiskTier"] == "Critical").sum())
    n_highrisk = int((watchlist["RiskTier"] == "High Risk").sum())
    n_watch    = int((watchlist["RiskTier"] == "Watch").sum())
    total_exp  = float(watchlist["OverdueAbs"].sum())

    summary_html = f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;">
        <div style="background:rgba(160,31,45,0.08);border-radius:6px;padding:6px 14px;font-size:0.78rem;">
            🔴 <b>Critical:</b> {n_critical}
        </div>
        <div style="background:rgba(181,98,10,0.08);border-radius:6px;padding:6px 14px;font-size:0.78rem;">
            🟠 <b>High Risk:</b> {n_highrisk}
        </div>
        <div style="background:rgba(232,168,56,0.08);border-radius:6px;padding:6px 14px;font-size:0.78rem;">
            🟡 <b>Watch:</b> {n_watch}
        </div>
        <div style="background:rgba(27,79,138,0.08);border-radius:6px;padding:6px 14px;font-size:0.78rem;">
            💰 <b>Total Exposure:</b> {total_exp:,.0f} THB
        </div>
    </div>
    """
    st.markdown(summary_html, unsafe_allow_html=True)


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

    required = {"CustomerName", "PaidOnTime", "PaidLate", "NotCollected", "OriginalDueDate"}
    if not required.issubset(df.columns):
        st.info("Required columns not found.")
        return
    if df.empty:
        st.info("No data for this company.")
        return

    all_customers = sorted(df["CustomerName"].dropna().unique().tolist())
    if not all_customers:
        st.info("No customers found.")
        return

    # ------------------------------------------------------------------
    # Filter Row
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
        st.markdown(f"<span style='{LABEL_STYLE}'>Sort By (Recommend Order)</span>",
                    unsafe_allow_html=True)
        sort_by = st.selectbox(
            "Sort By",
            options=["On-Time (Highest)", "Delay (Highest)", "Not Collected (Highest)"],
            index=0,
            key="otd_sort_by",
            label_visibility="collapsed",
            help=(
                "On-Time (Highest)       — recommend customers with best on-time rate first\n"
                "Delay (Highest)         — recommend customers with most delays first\n"
                "Not Collected (Highest) — recommend customers with most uncollected invoices first"
            ),
        )

    # ------------------------------------------------------------------
    # Apply date filter
    # ------------------------------------------------------------------
    df_dated = df.copy()
    if date_from and "OriginalDueDate" in df_dated.columns:
        df_dated = df_dated[df_dated["OriginalDueDate"] >= pd.Timestamp(date_from)]
    if date_to and "OriginalDueDate" in df_dated.columns:
        df_dated = df_dated[df_dated["OriginalDueDate"] <= pd.Timestamp(date_to)]

    if df_dated.empty:
        st.warning("No data in the selected date range.")
        return

    # ------------------------------------------------------------------
    # Customer summary
    # ------------------------------------------------------------------
    cust_summary = (
        df_dated.groupby("CustomerName")
        .agg(
            OnTimeCount  =("PaidOnTime",   "sum"),
            LateCount    =("PaidLate",     "sum"),
            NotCollCount =("NotCollected", "sum"),
            TotalInvoices=("PaidOnTime",   "count"),
        )
        .reset_index()
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
    sort_col, sort_asc = sort_col_map[sort_by]
    cust_summary = (
        cust_summary
        .sort_values(sort_col, ascending=sort_asc)
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # Search + Selectbox
    # ------------------------------------------------------------------
    lf1, lf2, _ = st.columns([2.5, 1.4, 2.1])

    with lf1:
        st.markdown(
            f"<span style='{LABEL_STYLE}'>Customer Search</span>",
            unsafe_allow_html=True,
        )
        search_query = st.text_input(
            "Customer Search",
            placeholder="Type name to search...",
            key="otd_search",
            label_visibility="collapsed",
        ).strip()

    with lf2:
        st.markdown(
            f"<span style='{LABEL_STYLE}'>Period (Trend)</span>",
            unsafe_allow_html=True,
        )
        gran_options  = ["Monthly", "Quarterly", "Yearly"]
        default_index = (
            gran_options.index(granularity)
            if granularity in gran_options else 0
        )
        local_gran = st.selectbox(
            "Period (Trend)", gran_options,
            index=default_index,
            key="otd_local_gran",
            label_visibility="collapsed",
        )

    if search_query:
        q = search_query.lower()
        filtered_names = [
            n for n in cust_summary["CustomerName"].tolist()
            if q in n.lower()
        ]
    else:
        filtered_names = cust_summary["CustomerName"].tolist()

    if not filtered_names:
        st.warning(f"No customer matched '{search_query}'.")
        return

    st.markdown(
        f"<span style='font-size:0.70rem;color:#8A9BB0;'>"
        f"{len(filtered_names)} result(s)"
        + (f" — search: {search_query}" if search_query else "")
        + "</span>",
        unsafe_allow_html=True,
    )

    prev_key   = st.session_state.get("otd_customer_select")
    default_ix = (
        filtered_names.index(prev_key)
        if prev_key and prev_key in filtered_names else 0
    )
    selected_customer = st.selectbox(
        "Select Customer",
        filtered_names,
        index=default_ix,
        key="otd_customer_select",
    )

    # ------------------------------------------------------------------
    # Filter for selected customer
    # ------------------------------------------------------------------
    df_cust = df_dated[df_dated["CustomerName"] == selected_customer].copy()
    if df_cust.empty:
        st.info(f"No data for {selected_customer} in the selected date range.")
        return

    # ------------------------------------------------------------------
    # Period label
    # ------------------------------------------------------------------
    if local_gran == "Yearly":
        df_cust["_Period"]  = df_cust["DueYear"].astype(str)
        period_sort_cols    = ["DueYear"]
    elif local_gran == "Quarterly":
        df_cust["_Period"]  = (
            df_cust["DueYear"].astype(str)
            + "-Q" + df_cust["DueQuarter"].astype(str)
        )
        period_sort_cols    = ["DueYear", "DueQuarter"]
    else:
        df_cust["_Period"]  = (
            df_cust["DueYear"].astype(str)
            + "-" + df_cust["DueMonthLabel"].fillna("")
        )
        period_sort_cols    = ["DueYear", "DueMonth"]

    grp = (
        df_cust.groupby("_Period")
        .agg(
            OnTime =("PaidOnTime",   "sum"),
            Late   =("PaidLate",     "sum"),
            NotColl=("NotCollected", "sum"),
            Total  =("PaidOnTime",   "count"),
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
    notcol_pct   = total_notcol / total_inv * 100         if total_inv else 0.0

    # ------------------------------------------------------------------
    # KPI strip — text + border only
    # ------------------------------------------------------------------
    kpi_html = f"""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 14px 0;">
        <div style="border:1px solid #d0dae6;border-radius:8px;padding:10px 18px;min-width:130px;">
            <p style="margin:0;font-size:0.68rem;color:#8A9BB0;font-weight:600;
                      text-transform:uppercase;letter-spacing:0.04em;">On-Time Rate</p>
            <p style="margin:4px 0 0;font-size:1.30rem;font-weight:700;color:#1B2A3B;">
                {ontime_pct:.1f}%</p>
            <p style="margin:2px 0 0;font-size:0.70rem;color:#5a6a7a;">
                {total_ontime:,} of {total_inv:,} invoices</p>
        </div>
        <div style="border:1px solid #d0dae6;border-radius:8px;padding:10px 18px;min-width:130px;">
            <p style="margin:0;font-size:0.68rem;color:#8A9BB0;font-weight:600;
                      text-transform:uppercase;letter-spacing:0.04em;">Late (Delay) Rate</p>
            <p style="margin:4px 0 0;font-size:1.30rem;font-weight:700;color:#1B2A3B;">
                {late_pct:.1f}%</p>
            <p style="margin:2px 0 0;font-size:0.70rem;color:#5a6a7a;">
                {total_late:,} invoices delayed</p>
        </div>
        <div style="border:1px solid #d0dae6;border-radius:8px;padding:10px 18px;min-width:130px;">
            <p style="margin:0;font-size:0.68rem;color:#8A9BB0;font-weight:600;
                      text-transform:uppercase;letter-spacing:0.04em;">Not Collected</p>
            <p style="margin:4px 0 0;font-size:1.30rem;font-weight:700;color:#1B2A3B;">
                {notcol_pct:.1f}%</p>
            <p style="margin:2px 0 0;font-size:0.70rem;color:#5a6a7a;">
                {total_notcol:,} invoices uncollected</p>
        </div>
    </div>
    """
    st.markdown(
        f"<p style='font-size:0.78rem;font-weight:700;color:#1B4F8A;"
        f"margin:0 0 2px 0;'>{selected_customer}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    col_line, col_pie = st.columns([3, 2], gap="medium")

    # ── LEFT : Line Trend ──────────────────────────────────────────────
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
                "On-Time : <b>%{customdata[0]:,}</b> invoices<br>"
                "Total   : %{customdata[1]:,} invoices<br>"
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
                "Late    : <b>%{customdata[0]:,}</b> invoices<br>"
                "Total   : %{customdata[1]:,} invoices<br>"
                "<extra></extra>"
            ),
        ))
        fig.add_hline(
            y=0, line_dash="dash", line_color="#cccccc", line_width=1,
            annotation_text="", annotation_font=dict(size=8, color="#aaaaaa"),
        )

        y_max = max(float(grp["OnTime"].max()), float(grp["Late"].max())) * 1.20

        apply_base_layout(fig, {
            "height": 320,
            "margin": dict(l=0, r=12, t=40, b=64),
            "title": dict(
                text=(
                    f"{selected_customer}"
                    f" — On-Time vs Delay Trend ({local_gran})"
                ),
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
                color=FONT_COLOR,
                range=[0, max(y_max, 1)],
                tickformat=",d",
            ),
            "legend": dict(
                orientation="h",
                xanchor="right", x=1.0,
                yanchor="top",   y=-0.22,
                font=dict(size=10),
                bgcolor="rgba(255,255,255,0.92)",
                bordercolor="#d0dae6", borderwidth=1,
            ),
            "showlegend": True,
            "hoverlabel": dict(
                bgcolor="white", bordercolor="#d0dae6",
                font=dict(size=11, color="#1B2A3B"), align="left",
            ),
        })
        st.plotly_chart(fig, use_container_width=True, key="chart_otd_line")

    # ── RIGHT : Pie + Summary strip ────────────────────────────────────
    with col_pie:
        pie_data_raw = [
            ("On-Time",       total_ontime, PALETTE["jade_lt"]),
            ("Late (Delay)",  total_late,   PALETTE["amber"]),
            ("Not Collected", total_notcol, PALETTE["crimson"]),
        ]
        pie_data = [(lbl, val, col) for lbl, val, col in pie_data_raw if val > 0]

        if not pie_data:
            st.info("No pie data available.")
        else:
            p_labels, p_values, p_colors = zip(*pie_data)

            # ── Pie figure ────────────────────────────────────────────
            fig_pie = go.Figure(go.Pie(
                labels    = list(p_labels),
                values    = list(p_values),
                marker    = dict(
                    colors = list(p_colors),
                    line   = dict(color="white", width=2),
                ),
                hole         = 0.44,
                textinfo     = "label+percent",
                textfont     = dict(size=11),
                hovertemplate= (
                    "<b>%{label}</b><br>"
                    "Invoices : %{value:,}<br>"
                    "Share    : %{percent}<br>"
                    "<extra></extra>"
                ),
                # ✅ ปิด legend ทั้ง trace-level และจะปิด layout-level ด้วย
                showlegend = False,
                pull       = [
                    0.06 if v == min(p_values) else 0.0
                    for v in p_values
                ],
                # ✅ domain เต็ม figure — ไม่ compress pie ลง
                domain     = dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            ))

            # Center annotation
            dominant     = p_labels[list(p_values).index(max(p_values))]
            dominant_pct = max(p_values) / sum(p_values) * 100
            center_color = (
                PALETTE["jade"]    if dominant == "On-Time"      else
                PALETTE["amber"]   if dominant == "Late (Delay)" else
                PALETTE["crimson"]
            )
            fig_pie.add_annotation(
                text      = f"{dominant_pct:.0f}%<br>{dominant}",
                x=0.5, y=0.5,
                font      = dict(size=13, color=center_color),
                showarrow = False,
            )

            fig_pie.update_layout(
                height        = 300,
                # ✅ margin รัดรูป — ให้ pie ขยายเต็ม
                margin        = dict(l=0, r=0, t=30, b=0),
                paper_bgcolor = "rgba(0,0,0,0)",
                plot_bgcolor  = "rgba(0,0,0,0)",
                font          = dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
                title         = dict(
                    text = "Payment Breakdown",
                    font = dict(size=10, color=FONT_COLOR),
                    x    = 0,
                    pad  = dict(t=0, b=0),
                ),
                # ✅ ปิด legend ระดับ layout — กัน Plotly บางเวอร์ชัน override
                showlegend    = False,
            )

            st.plotly_chart(fig_pie, use_container_width=True, key="chart_otd_pie")

            # ── Summary bar strip — st.markdown แยกต่างหาก ─────────
            # (ไม่ใช้ annotation ใน figure เพื่อหลีกเลี่ยง domain ซ้อน)
            summary_items = [
                ("On-Time",       total_ontime, ontime_pct,  PALETTE["jade_lt"]),
                ("Late (Delay)",  total_late,   late_pct,    PALETTE["amber"]),
                ("Not Collected", total_notcol, notcol_pct,  PALETTE["crimson"]),
            ]
            summary_html = (
                "<div style='display:flex;flex-direction:column;"
                "gap:6px;margin-top:0px;'>"           # margin-top=0 ชิด pie
            )
            for lbl, cnt, pct, col in summary_items:
                bar_w = max(float(pct), 2.0)
                summary_html += (
                    f"<div style='font-size:0.72rem;'>"
                    f"<div style='display:flex;justify-content:space-between;"
                    f"margin-bottom:3px;'>"
                    f"<span style='color:{col};font-weight:600;'>{lbl}</span>"
                    f"<span style='color:#5a6a7a;'>{cnt:,} ({pct:.1f}%)</span>"
                    f"</div>"
                    f"<div style='background:#f0f0f0;border-radius:4px;height:6px;'>"
                    f"<div style='background:{col};width:{bar_w:.1f}%;"
                    f"height:6px;border-radius:4px;'></div>"
                    f"</div></div>"
                )
            summary_html += "</div>"
            st.markdown(summary_html, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Ranking Table
    # ------------------------------------------------------------------
    with st.expander(f"Ranking — sorted by {sort_by}", expanded=False):
        rank_tbl = cust_summary.copy().reset_index(drop=True)
        rank_tbl.index = rank_tbl.index + 1
        rank_tbl = rank_tbl.rename(columns={
            "CustomerName":  "Customer",
            "TotalInvoices": "Total",
            "OnTimeCount":   "On-Time",
            "LateCount":     "Late",
            "NotCollCount":  "Not Collected",
            "OnTimePct":     "On-Time %",
            "LatePct":       "Late %",
        })
        st.dataframe(
            rank_tbl[[
                "Customer", "Total",
                "On-Time", "Late", "Not Collected",
                "On-Time %", "Late %",
            ]],
            use_container_width=True,
            height=300,
            column_config={
                "Customer":      st.column_config.TextColumn("Customer", width="large"),
                "Total":         st.column_config.NumberColumn("Total"),
                "On-Time":       st.column_config.NumberColumn("On-Time"),
                "Late":          st.column_config.NumberColumn("Late"),
                "Not Collected": st.column_config.NumberColumn("Not Collected"),
                "On-Time %":     st.column_config.NumberColumn("On-Time %",  format="%.1f%%"),
                "Late %":        st.column_config.NumberColumn("Late %",     format="%.1f%%"),
            },
            hide_index=False,
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