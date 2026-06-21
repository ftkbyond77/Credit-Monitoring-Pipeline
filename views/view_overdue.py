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

# ---------------------------------------------------------------------------
# Design tokens — consistent with existing PALETTE in view_avail.py
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
}

AGING_COLORS = {
    "1-30":  PALETTE["sapphire_lt"],
    "31-60": PALETTE["amber_lt"],
    "61-90": PALETTE["amber"],
    "90+":   PALETTE["crimson"],
}

DEFAULT_COMPANY = "1190"

MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


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
    df_all = _prepare_overdue(raw_overdue.copy())

    # Title
    st.markdown(
        dash_title_bar(
            "Credit Overdue Dashboard",
            "Analytics Dashboard — overdue exposure monitoring by customer",
        ),
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Main Filter bar  (granularity ไม่อยู่ที่นี่แล้ว)
    # ------------------------------------------------------------------
    df_filtered, selected_company, period_label_str = _render_filters(df_all)

    if df_filtered is None or df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    df_company_all = df_all[df_all["CompanyCode"] == selected_company].copy()

    # ------------------------------------------------------------------
    # Section 1 : KPI
    # ------------------------------------------------------------------
    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Section 2 : Priority Monitoring (60%) | Risk Matrix (40%)
    # ------------------------------------------------------------------
    st.markdown(
        section_header(f"Priority Monitoring & Risk Matrix — {period_label_str}"),
        unsafe_allow_html=True,
    )
    col_priority, col_risk = st.columns([3, 2], gap="medium")
    with col_priority:
        _render_top_overdue_bar(df_filtered)
    with col_risk:
        _render_risk_matrix(df_filtered)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Section 2b : Linked Bubble
    # ------------------------------------------------------------------
    st.markdown(
        section_header("Customer Debt vs Overdue Exposure (Linked with Credit Availability)"),
        unsafe_allow_html=True,
    )
    _render_linked_bubble(df_filtered, df_avail_full)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Section 3 : Aging Analysis
    # Granularity selector อยู่ที่นี่ — ใกล้ chart ที่ใช้มัน
    # ------------------------------------------------------------------
    st.markdown(section_header("Aging Analysis & Trend"), unsafe_allow_html=True)

    # --- Granularity selector ตรงนี้ ชิดซ้าย ไม่เต็ม row ---
    gran_col, gran_space = st.columns([1, 4])
    with gran_col:
        granularity = st.selectbox(
            "Period Granularity",
            options=["Monthly", "Weekly", "Daily", "Yearly"],
            index=0,
            key="od_gran",
            help="ใช้สำหรับ grouping แกน X ของ Aging และ Trend charts ด้านล่างนี้",
        )

    col_aging_dist, col_aging_trend = st.columns(2, gap="medium")
    with col_aging_dist:
        _render_aging_bucket(df_company_all, granularity)
    with col_aging_trend:
        _render_aging_trend(df_company_all, granularity)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Section 4 : Portfolio Concentration
    # ------------------------------------------------------------------
    st.markdown(section_header("Portfolio Concentration"), unsafe_allow_html=True)
    col_pareto, col_tree = st.columns(2, gap="medium")
    with col_pareto:
        _render_pareto(df_filtered)
    with col_tree:
        _render_treemap(df_filtered)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Raw table
    # ------------------------------------------------------------------
    with st.expander("View All Overdue Records — Selected Period", expanded=False):
        _render_priority_table(df_filtered)


# =============================================================================
# Data preparation
# =============================================================================
def _prepare_overdue(df: pd.DataFrame) -> pd.DataFrame:
    # Strip quote artifacts from column names
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]

    # --- Date parsing : YYYYMMDD -> datetime ---
    for col in ("OriginalDueDate", "CollectionDate"):
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col].astype(str).str.strip().replace({"nan": None, "": None}),
                format="%Y%m%d",
                errors="coerce",
            )

    # --- Numeric ---
    for col in ("OverdueAmount", "InvoiceAmount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # --- CompanyCode as string ---
    if "CompanyCode" in df.columns:
        df["CompanyCode"] = df["CompanyCode"].astype(str).str.strip()

    # ---------------------------------------------------------------
    # Join key : overdue "Customer" column  <->  avail "CUSTOMER_CODE"
    # _clean_overdue() strips leading ' so raw "'Customer" -> "Customer"
    # Standardise to int for reliable merge
    # ---------------------------------------------------------------
    if "Customer" in df.columns:
        df["Customer"] = (
            pd.to_numeric(df["Customer"], errors="coerce").fillna(0).astype(int)
        )
    # Defensive alias — ถ้าไฟล์บางเวอร์ชันใช้ชื่ออื่น ให้ตรวจแล้ว map มาเป็น Customer
    else:
        # ค้นหา column ที่น่าจะเป็น customer code จาก heuristic
        candidate_cols = [
            c for c in df.columns
            if "customer" in c.lower() and "name" not in c.lower()
        ]
        if candidate_cols:
            src_col = candidate_cols[0]
            df["Customer"] = (
                pd.to_numeric(df[src_col], errors="coerce").fillna(0).astype(int)
            )

    # --- Derived columns ---
    today = pd.Timestamp("today").normalize()

    df["IsOverdue"]  = df["OverdueAmount"] <= 0
    df["OverdueAbs"] = df["OverdueAmount"].abs()

    if "OriginalDueDate" in df.columns:
        df["DPD"] = (today - df["OriginalDueDate"]).dt.days.clip(lower=0)

        df["DueYear"]       = df["OriginalDueDate"].dt.year.astype("Int64")
        df["DueMonth"]      = df["OriginalDueDate"].dt.month.astype("Int64")
        df["DueWeek"]       = df["OriginalDueDate"].dt.isocalendar().week.astype("Int64")
        df["DueMonthLabel"] = df["DueMonth"].map(MONTH_MAP)

        df["AgingBucket"] = pd.cut(
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

def _render_filters(df_all: pd.DataFrame):
    available_companies = (
        sorted(df_all["CompanyCode"].dropna().unique().tolist())
        if "CompanyCode" in df_all.columns
        else [DEFAULT_COMPANY]
    )
    default_idx = (
        available_companies.index(DEFAULT_COMPANY)
        if DEFAULT_COMPANY in available_companies
        else 0
    )

    # ------------------------------------------------------------------
    # Label style — navy, font เดียวกันทุกตัว, ไม่มี text-transform
    # ------------------------------------------------------------------
    LABEL_STYLE = (
        "font-size:0.75rem;"
        "font-weight:600;"
        "color:#1B4F8A;"          # navy — แก้จาก #31333F
        "letter-spacing:0.01em;"
        "margin-bottom:2px;"
        "display:block;"
        "line-height:1.4;"
    )

    # ------------------------------------------------------------------
    # Column ratio : ตัด spacer column (w6) ออก → เหลือ 6 columns
    # สัดส่วน [1.2, 1, 1, 1, 1, 1.6]
    # Company Code แคบลง (1.2) ให้ใกล้เคียง date_input
    # Search ยาวขึ้น (1.6) ชดเชย space ที่ตัดออก
    # ------------------------------------------------------------------
    COLS = [1.2, 1, 1, 1, 1, 1.6]

    lc1, lc2, lc3, lc4, lc5, lc6 = st.columns(COLS, gap="small")

    # Label row
    with lc1:
        st.markdown(f"<span style='{LABEL_STYLE}'>Company Code</span>",        unsafe_allow_html=True)
    with lc2:
        st.markdown(f"<span style='{LABEL_STYLE}'>OriginalDueDate From</span>", unsafe_allow_html=True)
    with lc3:
        st.markdown(f"<span style='{LABEL_STYLE}'>OriginalDueDate To</span>",   unsafe_allow_html=True)
    with lc4:
        st.markdown(f"<span style='{LABEL_STYLE}'>CollectionDate From</span>",  unsafe_allow_html=True)
    with lc5:
        st.markdown(f"<span style='{LABEL_STYLE}'>CollectionDate To</span>",    unsafe_allow_html=True)
    with lc6:
        st.markdown(f"<span style='{LABEL_STYLE}'>Search Customer Name</span>", unsafe_allow_html=True)

    # Input row — สัดส่วนเดียวกัน, label ซ่อนทั้งหมด
    wc1, wc2, wc3, wc4, wc5, wc6 = st.columns(COLS, gap="small")

    with wc1:
        selected_company = st.selectbox(
            "Company Code",
            options=available_companies,
            index=default_idx,
            key="od_company",
            label_visibility="collapsed",
        )
    with wc2:
        due_start = st.date_input(
            "Due From",
            value=None,
            key="od_due_start",
            label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with wc3:
        due_end = st.date_input(
            "Due To",
            value=None,
            key="od_due_end",
            label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with wc4:
        coll_start = st.date_input(
            "Coll From",
            value=None,
            key="od_coll_start",
            label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with wc5:
        coll_end = st.date_input(
            "Coll To",
            value=None,
            key="od_coll_end",
            label_visibility="collapsed",
            format="YYYY/MM/DD",
        )
    with wc6:
        customer_search = st.text_input(
            "Search Customer Name",
            placeholder="Type to filter...",
            key="od_customer_search",
            label_visibility="collapsed",
        )

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    df_company = df_all[df_all["CompanyCode"] == selected_company].copy()
    if df_company.empty:
        st.warning("No data for selected company.")
        return None, selected_company, ""

    df_filtered = df_company.copy()

    if due_start and "OriginalDueDate" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["OriginalDueDate"] >= pd.Timestamp(due_start)
        ]
    if due_end and "OriginalDueDate" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["OriginalDueDate"] <= pd.Timestamp(due_end)
        ]
    if coll_start and "CollectionDate" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["CollectionDate"] >= pd.Timestamp(coll_start)
        ]
    if coll_end and "CollectionDate" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["CollectionDate"] <= pd.Timestamp(coll_end)
        ]
    if customer_search and "CustomerName" in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered["CustomerName"].str.contains(
                customer_search, case=False, na=False
            )
        ]

    # Period label string for section headers
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

    period_label_str = "  |  ".join(parts) if parts else "All Dates"
    return df_filtered, selected_company, period_label_str

# ---------------------------------------------------------------------------
# KPI card HTML builder สำหรับ overdue dashboard
# ต่างจาก kpi_card() ใน components.py ตรงที่:
#   - value font ลดลงอัตโนมัติเมื่อข้อความยาว (font-size clamp)
#   - height คงที่ 110px ทุก card
#   - sub line แสดงเต็ม ไม่ตัด
# ---------------------------------------------------------------------------
def _overdue_kpi_card(label: str, value: str, sub: str, variant: str) -> str:
    variant_styles = {
        "danger":  ("rgba(215,38,61,0.07)",  "#A01F2D"),
        "warning": ("rgba(181,98,10,0.07)",  "#B5620A"),
        "safe":    ("rgba(26,122,74,0.07)",  "#1A7A4A"),
        "info":    ("rgba(27,79,138,0.07)",  "#1B4F8A"),
    }
    bg, accent = variant_styles.get(variant, variant_styles["info"])

    # คำนวณ font size ตามความยาว value — ยิ่งยาวยิ่งเล็ก
    vlen = len(str(value))
    if vlen <= 8:
        v_font = "1.45rem"
    elif vlen <= 14:
        v_font = "1.15rem"
    elif vlen <= 22:
        v_font = "0.95rem"
    else:
        v_font = "0.80rem"

    sub_html = (
        f"<div style='"
        f"font-size:0.68rem;color:#6b7a8d;"
        f"margin-top:4px;line-height:1.3;"
        f"word-break:break-word;"
        f"'>{sub}</div>"
        if sub else ""
    )

    return (
        f"<div style='"
        f"background:{bg};"
        f"border:1px solid {accent}33;"
        f"border-radius:10px;"
        f"padding:14px 16px 12px 16px;"
        f"height:110px;"               # สูงเท่ากันทุก card
        f"box-sizing:border-box;"
        f"display:flex;"
        f"flex-direction:column;"
        f"justify-content:space-between;"
        f"overflow:hidden;"
        f"'>"
        f"<div style='"
        f"font-size:0.68rem;"
        f"font-weight:700;"
        f"color:{accent};"
        f"letter-spacing:0.06em;"
        f"text-transform:uppercase;"
        f"line-height:1.2;"
        f"'>{label}</div>"
        f"<div style='"
        f"font-size:{v_font};"
        f"font-weight:700;"
        f"color:{accent};"
        f"line-height:1.15;"
        f"word-break:break-word;"
        f"'>{value}</div>"
        f"{sub_html}"
        f"</div>"
    )


def _render_kpi_row(df: pd.DataFrame):
    overdue_df = df[df["IsOverdue"]]

    total_customers = (
        int(overdue_df["CustomerName"].nunique())
        if "CustomerName" in overdue_df.columns else 0
    )
    total_amount = (
        float(overdue_df["OverdueAbs"].sum())
        if "OverdueAbs" in overdue_df.columns else 0.0
    )
    total_invoices = int(len(overdue_df))
    avg_dpd = (
        float(overdue_df["DPD"].mean())
        if "DPD" in overdue_df.columns and not overdue_df.empty else 0.0
    )

    # Largest customer — แสดงชื่อเต็ม ไม่ตัด ให้ font scaling จัดการ
    largest_customer = "N/A"
    if "CustomerName" in overdue_df.columns and not overdue_df.empty:
        agg = overdue_df.groupby("CustomerName")["OverdueAbs"].sum()
        if not agg.empty:
            largest_customer = str(agg.idxmax())

    cards = [
        (
            "Overdue Customers",
            f"{total_customers:,}",
            "Unique customers with overdue",
            "danger" if total_customers > 0 else "safe",
        ),
        (
            "Total Overdue Amount",
            f"{total_amount:,.2f}",
            "THB — selected period",
            "danger" if total_amount > 0 else "safe",
        ),
        (
            "Overdue Invoices",
            f"{total_invoices:,}",
            "Records in selected period",
            "warning" if total_invoices > 0 else "safe",
        ),
        (
            "Avg DPD",
            f"{avg_dpd:.1f} days",
            "Avg Days Past Due",
            "warning" if avg_dpd > 30 else "info",
        ),
        (
            "Largest Overdue Customer",
            largest_customer,           # ชื่อเต็ม — font จะหด
            "By total overdue amount",
            "danger" if largest_customer != "N/A" else "info",
        ),
    ]

    cols = st.columns(5, gap="small")
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(
                _overdue_kpi_card(label, value, sub, variant),
                unsafe_allow_html=True,
            )

# =============================================================================
# KPI Row — 5 cards
# =============================================================================
def _render_kpi_row(df: pd.DataFrame):
    overdue_df = df[df["IsOverdue"]]

    total_customers = (
        int(overdue_df["CustomerName"].nunique())
        if "CustomerName" in overdue_df.columns else 0
    )
    total_amount = (
        float(overdue_df["OverdueAbs"].sum())
        if "OverdueAbs" in overdue_df.columns else 0.0
    )
    total_invoices = int(len(overdue_df))
    avg_dpd = (
        float(overdue_df["DPD"].mean())
        if "DPD" in overdue_df.columns and not overdue_df.empty else 0.0
    )

    # Largest overdue customer — truncate ถ้ายาวเกิน
    largest_customer     = "N/A"
    largest_customer_full = "N/A"
    if "CustomerName" in overdue_df.columns and not overdue_df.empty:
        agg = overdue_df.groupby("CustomerName")["OverdueAbs"].sum()
        if not agg.empty:
            largest_customer_full = str(agg.idxmax())
            # ตัดให้สั้น — card จะได้สูงเท่ากัน
            largest_customer = (
                largest_customer_full[:22] + "…"
                if len(largest_customer_full) > 22
                else largest_customer_full
            )

    cols = st.columns(5, gap="small")
    cards = [
        (
            "Overdue Customers",
            f"{total_customers:,}",
            "Unique customers with overdue",
            "danger" if total_customers > 0 else "safe",
        ),
        (
            "Total Overdue Amount",
            f"{total_amount:,.2f}",
            "THB — selected period",
            "danger" if total_amount > 0 else "safe",
        ),
        (
            "Overdue Invoices",
            f"{total_invoices:,}",
            "Records in selected period",
            "warning" if total_invoices > 0 else "safe",
        ),
        (
            "Avg DPD",
            f"{avg_dpd:.1f} days",
            "Avg Days Past Due",
            "warning" if avg_dpd > 30 else "info",
        ),
        (
            "Largest Overdue Customer",
            largest_customer,
            largest_customer_full,   
            "danger" if largest_customer_full != "N/A" else "info",
        ),
    ]

    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(
                _overdue_kpi_card(label, value, sub, variant),
                unsafe_allow_html=True,
            )


# =============================================================================
# Row 1 Left (60%) : Top Overdue Customers — Horizontal Bar
# =============================================================================
def _render_top_overdue_bar(df: pd.DataFrame, top_n: int = 12):
    if "CustomerName" not in df.columns:
        st.info("CustomerName column not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records in the selected period.")
        return

    grouped = (
        overdue_df.groupby("CustomerName")
        .agg(
            TotalOverdue=("OverdueAbs", "sum"),
            InvoiceCount=("OverdueAbs", "count"),
            AvgDPD=("DPD", "mean"),
        )
        .reset_index()
        .sort_values("TotalOverdue", ascending=False)
        .head(top_n)
        .sort_values("TotalOverdue", ascending=True)   # ascending for horizontal bar readability
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

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=grouped["CustomerName"],
        x=grouped["TotalOverdue"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:,.0f}" for v in grouped["TotalOverdue"]],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Overdue Amount : %{x:,.2f} THB<br>"
            "<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": max(360, top_n * 30),
        "margin": dict(l=0, r=80, t=10, b=4),
        "xaxis": dict(
            title="Overdue Amount (THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "yaxis": dict(
            showgrid=False, color=FONT_COLOR,
            tickfont=dict(size=9),
        ),
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_priority_bar")


# =============================================================================
# Row 1 Right (40%) : Risk Matrix Bubble — X=DPD, Y=OverdueAmount, 4 Quadrants
# =============================================================================
# =============================================================================
# Row 1 Right : Risk Matrix
# แก้ : ใช้ log Y-axis เพื่อให้เห็น matrix จริง ไม่ถูก outlier ดึง
# =============================================================================
def _render_risk_matrix(df: pd.DataFrame):
    if "DPD" not in df.columns or "CustomerName" not in df.columns:
        st.info("Insufficient columns for risk matrix.")
        return

    import numpy as np

    scatter_df = (
        df[df["IsOverdue"]]
        .groupby("CustomerName")
        .agg(
            AvgDPD=("DPD", "mean"),
            TotalOverdue=("OverdueAbs", "sum"),
            InvoiceCount=("OverdueAbs", "count"),
        )
        .reset_index()
    )
    if scatter_df.empty:
        st.info("No overdue data for risk matrix.")
        return

    # ------------------------------------------------------------------
    # Quadrant : ใช้ median จาก log-transformed values
    # เพื่อให้ median line อยู่กลาง chart จริงๆ บน log scale
    # ------------------------------------------------------------------
    scatter_df["LogOverdue"] = np.log1p(scatter_df["TotalOverdue"])
    median_dpd        = float(scatter_df["AvgDPD"].median())
    median_log_overdue = float(scatter_df["LogOverdue"].median())
    median_overdue_val = float(np.expm1(median_log_overdue))  # แปลงกลับสำหรับ hline

    def _quadrant(row):
        high_dpd    = row["AvgDPD"]    >= median_dpd
        high_amount = row["LogOverdue"] >= median_log_overdue
        if high_dpd and high_amount:
            return "Critical", PALETTE["crimson"]
        elif not high_dpd and high_amount:
            return "Monitor",  PALETTE["violet_lt"]
        elif high_dpd and not high_amount:
            return "Watch",    PALETTE["amber"]
        else:
            return "Low Risk", PALETTE["sapphire_lt"]

    scatter_df[["Quadrant", "Color"]] = scatter_df.apply(
        lambda r: pd.Series(_quadrant(r)), axis=1
    )

    # ------------------------------------------------------------------
    # Bubble size : log scale, cap ที่ 32px
    # ------------------------------------------------------------------
    log_vals         = scatter_df["LogOverdue"]
    log_min, log_max = log_vals.min(), log_vals.max()
    log_range        = max(log_max - log_min, 1)
    scatter_df["BubbleSize"] = (
        8 + ((log_vals - log_min) / log_range) * 24
    ).clip(upper=32)

    # ------------------------------------------------------------------
    # Label : top 3 ต่อ quadrant เท่านั้น
    # ------------------------------------------------------------------
    top_idx = (
        scatter_df
        .sort_values("TotalOverdue", ascending=False)
        .groupby("Quadrant")
        .head(3)
        .index
    )
    scatter_df["Label"] = scatter_df.apply(
        lambda r: (
            str(r["CustomerName"])[:13] + "…"
            if len(str(r["CustomerName"])) > 13
            else str(r["CustomerName"])
        ) if r.name in top_idx else "",
        axis=1,
    )

    # ------------------------------------------------------------------
    # Plot — แต่ละ quadrant เป็น trace แยก (legend)
    # Y-axis type = "log" — นี่คือ key fix
    # ------------------------------------------------------------------
    fig = go.Figure()

    quad_order = ["Critical", "Monitor", "Watch", "Low Risk"]
    quad_color_map = {
        "Critical": PALETTE["crimson"],
        "Monitor":  PALETTE["violet_lt"],
        "Watch":    PALETTE["amber"],
        "Low Risk": PALETTE["sapphire_lt"],
    }

    for quad in quad_order:
        grp = scatter_df[scatter_df["Quadrant"] == quad]
        if grp.empty:
            continue
        fig.add_trace(go.Scatter(
            x=grp["AvgDPD"],
            y=grp["TotalOverdue"],          # ค่าจริง — log แสดงโดย axis type
            mode="markers+text",
            name=quad,
            text=grp["Label"],
            textposition="top center",
            textfont=dict(size=8, color="#3a4a60"),
            marker=dict(
                size=grp["BubbleSize"],
                color=quad_color_map[quad],
                opacity=0.78,
                line=dict(color="white", width=0.8),
            ),
            customdata=grp[["CustomerName", "InvoiceCount", "TotalOverdue", "AvgDPD"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "DPD            : %{customdata[3]:.0f} days<br>"
                "Overdue Amount : %{customdata[2]:,.0f} THB<br>"
                "Invoice Count  : %{customdata[1]}<br>"
                "<extra></extra>"
            ),
        ))

    # ------------------------------------------------------------------
    # Quadrant dividers
    # vline = median DPD (linear axis ปกติ)
    # hline = median overdue ค่าจริง (บน log axis)
    # ------------------------------------------------------------------
    fig.add_vline(
        x=median_dpd,
        line_dash="dot", line_color="#bbbbbb", line_width=1,
    )
    fig.add_hline(
        y=median_overdue_val,
        line_dash="dot", line_color="#bbbbbb", line_width=1,
    )

    # Quadrant corner labels
    x_max = float(scatter_df["AvgDPD"].max())
    y_min_log = float(scatter_df["TotalOverdue"].min())
    y_max_log = float(scatter_df["TotalOverdue"].max())

    # ตำแหน่ง annotation บน log scale — ใช้ค่าจริงแต่เลือก position ที่ชัด
    for ax, ay, label, color in [
        (x_max * 0.92, y_max_log * 0.85,  "CRITICAL",  PALETTE["crimson"]),
        (median_dpd * 0.08, y_max_log * 0.85,  "MONITOR",   PALETTE["violet_lt"]),
        (x_max * 0.92, y_min_log * 1.5,   "WATCH",     PALETTE["amber"]),
        (median_dpd * 0.08, y_min_log * 1.5,   "LOW RISK",  PALETTE["sapphire_lt"]),
    ]:
        fig.add_annotation(
            x=ax, y=ay,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(size=9, color=color),
            opacity=0.45,
        )

    apply_base_layout(fig, {
        "height": 380,
        "margin": dict(l=0, r=10, t=10, b=4),
        "xaxis": dict(
            title="DPD (Days Past Due)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "yaxis": dict(
            title="Overdue Amount (THB)",
            type="log",                     # KEY FIX — log scale ทำให้เห็น matrix
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="right",  x=1,
            font=dict(size=9),
        ),
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=10, color="#1B2A3B"), align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_risk_matrix")


# =============================================================================
# Row 2 : Linked Bubble
# แก้ : X = OverdueAmount (แทน DPD), สีเข้มขึ้น
# =============================================================================
def _render_linked_bubble(df_overdue_filtered: pd.DataFrame, df_avail: pd.DataFrame):
    if df_avail is None or df_avail.empty:
        st.info("Credit Availability data not loaded.")
        return

    required_avail = {"CUSTOMER_CODE", "CURRENT_DEBT_MILLION_THB", "SOURCE_SHEET"}
    if not required_avail.issubset(df_avail.columns):
        st.info(f"Credit Availability missing columns: {required_avail - set(df_avail.columns)}")
        return

    if "Customer" not in df_overdue_filtered.columns:
        st.error(
            f"Join key 'Customer' not found. "
            f"Available columns: {list(df_overdue_filtered.columns)}"
        )
        return

    import numpy as np

    overdue_df = df_overdue_filtered[df_overdue_filtered["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records to plot.")
        return

    # Aggregate
    overdue_agg = (
        overdue_df.groupby(["Customer", "CustomerName", "DueYear"])
        .agg(TotalOverdue=("OverdueAbs", "sum"), AvgDPD=("DPD", "mean"))
        .reset_index()
    )

    # Prepare avail
    avail_prep = df_avail.copy()
    avail_prep["SOURCE_SHEET"]  = avail_prep["SOURCE_SHEET"].astype(str).str.strip()
    avail_prep["CUSTOMER_CODE"] = (
        pd.to_numeric(avail_prep["CUSTOMER_CODE"], errors="coerce").fillna(0).astype(int)
    )
    if "DATE" in avail_prep.columns:
        avail_prep = (
            avail_prep.sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE", "SOURCE_SHEET"])
        )
    else:
        avail_prep = avail_prep.drop_duplicates(subset=["CUSTOMER_CODE", "SOURCE_SHEET"])

    avail_cols = ["CUSTOMER_CODE", "SOURCE_SHEET", "CURRENT_DEBT_MILLION_THB"]
    if "CLEAN_CREDIT_MB" in avail_prep.columns:
        avail_cols.append("CLEAN_CREDIT_MB")
    avail_prep = avail_prep[avail_cols].copy()

    # Join year-matched
    overdue_agg["_avail_year"] = overdue_agg["DueYear"].astype(str)
    merged = overdue_agg.merge(
        avail_prep,
        left_on=["Customer", "_avail_year"],
        right_on=["CUSTOMER_CODE", "SOURCE_SHEET"],
        how="left",
    )

    # Fallback
    if merged["CURRENT_DEBT_MILLION_THB"].isna().all():
        avail_fallback = (
            avail_prep.sort_values("SOURCE_SHEET", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE"])
        )
        merged = overdue_agg.merge(
            avail_fallback, left_on="Customer", right_on="CUSTOMER_CODE", how="left",
        )
        st.caption("Note: No exact year match — using latest available snapshot per customer.")

    merged = merged.dropna(subset=["CURRENT_DEBT_MILLION_THB"])
    if merged.empty:
        st.info("No matching records after join.")
        return

    # ------------------------------------------------------------------
    # Bubble size : log scale, cap 38px
    # ------------------------------------------------------------------
    log_vals         = np.log1p(merged["AvgDPD"])
    log_min, log_max = log_vals.min(), log_vals.max()
    log_range        = max(log_max - log_min, 1)
    merged["BubbleSize"] = (
        7 + ((log_vals - log_min) / log_range) * 31
    ).clip(upper=38)

    # ------------------------------------------------------------------
    # Label : top 8 by score
    # ------------------------------------------------------------------
    merged["_Score"] = (
        merged["TotalOverdue"] / merged["TotalOverdue"].max()
        + merged["CURRENT_DEBT_MILLION_THB"] / merged["CURRENT_DEBT_MILLION_THB"].max()
    )
    top_idx = merged.nlargest(8, "_Score").index
    merged["Label"] = merged.apply(
        lambda r: (
            str(r["CustomerName"])[:13] + "…"
            if len(str(r["CustomerName"])) > 13
            else str(r["CustomerName"])
        ) if r.name in top_idx else "",
        axis=1,
    )

    # ------------------------------------------------------------------
    # Color scale เข้มขึ้น — เริ่มจาก mid-tone ไม่ใช่ขาว
    # ------------------------------------------------------------------
    has_credit  = "CLEAN_CREDIT_MB" in merged.columns
    extra_hover = "Clean Credit   : %{customdata[3]:,.1f} MB<br>" if has_credit else ""
    custom_cols = (
        ["CustomerName", "TotalOverdue", "AvgDPD", "CLEAN_CREDIT_MB"]
        if has_credit else ["CustomerName", "TotalOverdue", "AvgDPD"]
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        # KEY FIX : X = OverdueAmount แทน DPD
        x=merged["TotalOverdue"],
        y=merged["CURRENT_DEBT_MILLION_THB"],
        mode="markers+text",
        text=merged["Label"],
        textposition="top center",
        textfont=dict(size=8, color="#2c3e50"),
        marker=dict(
            size=merged["BubbleSize"],
            color=merged["TotalOverdue"],
            colorscale=[
                [0.0,  "#F4A261"],      # เริ่ม mid-orange — ไม่ใช่ขาว/ชมพูอ่อน
                [0.4,  "#E76F51"],
                [0.7,  PALETTE["crimson"]],
                [1.0,  "#6B0F1A"],      # เข้มมากสำหรับ outlier
            ],
            cmin=merged["TotalOverdue"].quantile(0.10),   # ตัด bottom 10% ออก
            cmax=merged["TotalOverdue"].quantile(0.95),   # cap top 5% ไม่ให้ดึง scale
            showscale=True,
            colorbar=dict(
                title=dict(text="Overdue (THB)", font=dict(size=9)),
                thickness=12,
                len=0.55,
                tickfont=dict(size=8),
            ),
            opacity=0.85,
            line=dict(color="white", width=0.8),
        ),
        customdata=merged[custom_cols].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Overdue Amount : %{x:,.0f} THB<br>"      # อัปเดต label ให้ตรงแกน
            "Current Debt   : %{y:,.1f} MB<br>"
            "Avg DPD        : %{customdata[2]:.0f} days<br>"
            + extra_hover +
            "<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": 420,
        "margin": dict(l=0, r=70, t=10, b=4),
        "xaxis": dict(
            title="Overdue Amount (THB)",       # เปลี่ยน label แกน X
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "yaxis": dict(
            title="Current Debt (Million THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "showlegend": False,
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=10, color="#1B2A3B"), align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_linked_bubble")

# =============================================================================
# Row 3 Left : Aging Bucket Distribution — Stacked Bar
# =============================================================================
def _render_aging_bucket(df: pd.DataFrame, granularity: str):
    if "AgingBucket" not in df.columns:
        st.info("AgingBucket column not available.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue data for aging analysis.")
        return

    overdue_df["_PeriodLabel"] = _period_label_series(overdue_df, granularity)
    overdue_df["_SortKey"]     = _sort_key_series(overdue_df, granularity)

    bucket_trend = (
        overdue_df.groupby(["_PeriodLabel", "_SortKey", "AgingBucket"])["OverdueAbs"]
        .sum()
        .reset_index()
        .sort_values("_SortKey")
    )

    periods = bucket_trend["_PeriodLabel"].unique()
    fig = go.Figure()

    for bucket, color in AGING_COLORS.items():
        bucket_data = bucket_trend[bucket_trend["AgingBucket"] == bucket]
        bucket_map  = bucket_data.set_index("_PeriodLabel")["OverdueAbs"].to_dict()
        fig.add_trace(go.Bar(
            x=periods,
            y=[bucket_map.get(p, 0) for p in periods],
            name=f"{bucket} DPD",
            marker_color=color,
            hovertemplate=f"<b>{bucket} DPD</b><br>%{{x}}<br>Amount : %{{y:,.2f}} THB<extra></extra>",
        ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=20, t=30, b=40),
        "barmode": "stack",
        "title": dict(
            text="Aging Bucket Distribution",
            font=dict(size=11, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            tickangle=-35, tickfont=dict(size=8),
            showgrid=False, color=FONT_COLOR,
        ),
        "yaxis": dict(
            title="Overdue Amount (THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            font=dict(size=9),
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_aging_bucket")


# =============================================================================
# Row 3 Right : Aging Trend — Multi-line chart
# =============================================================================
def _render_aging_trend(df: pd.DataFrame, granularity: str):
    if "AgingBucket" not in df.columns:
        st.info("AgingBucket column not available.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue data for aging trend.")
        return

    overdue_df["_PeriodLabel"] = _period_label_series(overdue_df, granularity)
    overdue_df["_SortKey"]     = _sort_key_series(overdue_df, granularity)

    trend = (
        overdue_df.groupby(["_PeriodLabel", "_SortKey", "AgingBucket"])["OverdueAbs"]
        .sum()
        .reset_index()
        .sort_values("_SortKey")
    )

    fig = go.Figure()

    for bucket, color in AGING_COLORS.items():
        bucket_data = trend[trend["AgingBucket"] == bucket].sort_values("_SortKey")
        if bucket_data.empty:
            continue
        fig.add_trace(go.Scatter(
            x=bucket_data["_PeriodLabel"],
            y=bucket_data["OverdueAbs"],
            mode="lines+markers",
            name=f"{bucket} DPD",
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            hovertemplate=(
                f"<b>{bucket} DPD</b><br>"
                "%{x}<br>"
                "Amount : %{y:,.2f} THB<br>"
                "<extra></extra>"
            ),
        ))

    apply_base_layout(fig, {
        "height": 320,
        "margin": dict(l=0, r=20, t=30, b=40),
        "title": dict(
            text="Aging Trend — Is Debt Quality Improving?",
            font=dict(size=11, color=FONT_COLOR), x=0,
        ),
        "xaxis": dict(
            tickangle=-35, tickfont=dict(size=8),
            showgrid=False, color=FONT_COLOR,
        ),
        "yaxis": dict(
            title="Overdue Amount (THB)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "legend": dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            font=dict(size=9),
        ),
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=10, color="#1B2A3B"), align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_aging_trend")


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
def _render_treemap(df: pd.DataFrame):
    if "CustomerName" not in df.columns:
        st.info("CustomerName column not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue data for treemap.")
        return

    grouped = (
        overdue_df.groupby("CustomerName")["OverdueAbs"]
        .sum()
        .reset_index()
        .sort_values("OverdueAbs", ascending=False)
        .head(25)
        .reset_index(drop=True)
    )

    total = grouped["OverdueAbs"].sum()
    grouped["Pct"] = (grouped["OverdueAbs"] / total * 100).round(2)
    grouped["Label"] = grouped.apply(
        lambda r: f"{r['CustomerName']}<br>{r['Pct']:.1f}%", axis=1
    )

    fig = go.Figure(go.Treemap(
        labels=grouped["Label"],
        parents=[""] * len(grouped),
        values=grouped["OverdueAbs"],
        textinfo="label",
        textfont=dict(size=10),
        marker=dict(
            colors=grouped["OverdueAbs"],
            colorscale=[
                [0.0,  "#FFDDD2"],
                [0.4,  PALETTE["amber_lt"]],
                [0.75, PALETTE["amber"]],
                [1.0,  PALETTE["crimson"]],
            ],
            showscale=False,
            line=dict(width=1.5, color="white"),
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Overdue Amount : %{value:,.2f} THB<br>"
            "<extra></extra>"
        ),
    ))

    apply_base_layout(fig, {
        "height": 340,
        "margin": dict(l=0, r=0, t=30, b=4),
        "title": dict(
            text="Concentration Treemap — Size = Overdue Amount",
            font=dict(size=11, color=FONT_COLOR), x=0,
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