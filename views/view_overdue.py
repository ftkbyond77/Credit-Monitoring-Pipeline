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
from streamlit_echarts import st_echarts
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
    df_all        = _prepare_overdue(raw_overdue.copy())
    st.markdown(
        dash_title_bar(
            "Credit Overdue Dashboard",
            "Analytics Dashboard — overdue exposure monitoring by customer",
        ),
        unsafe_allow_html=True,
    )
    df_filtered, selected_company, period_label_str = _render_filters(df_all)
    if df_filtered is None or df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return
    df_company_all = df_all[df_all["CompanyCode"] == selected_company].copy()
    # ------------------------------------------------------------------
    # Section 1 : KPI Row
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
        _render_risk_matrix(df_filtered, df_avail_full)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    # ------------------------------------------------------------------
    # Section 3 : Aging Distribution
    # ------------------------------------------------------------------
    st.markdown(
        section_header("Aging Distribution — Current Debt by DPD Bucket"),
        unsafe_allow_html=True,
    )
    _render_exposure_utilization(df_filtered, df_avail_full)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    # ------------------------------------------------------------------
    # Section 4 : Overdue Velocity
    # ------------------------------------------------------------------
    st.markdown(
        section_header("Overdue Velocity — Who Is Getting Worse"),
        unsafe_allow_html=True,
    )
    _render_overdue_velocity(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    # ------------------------------------------------------------------
    # Section 5 : Aging Analysis & Trend
    # Period Granularity selector วางที่นี่ ใช้กับ Section 5 เป็นต้นไป
    # ------------------------------------------------------------------
    st.markdown(section_header("Aging Analysis & Trend"), unsafe_allow_html=True)
    gran_col, _ = st.columns([1, 4])
    with gran_col:
        granularity_vel = st.selectbox(
            "Period Granularity",
            options=["Monthly", "Weekly", "Daily", "Yearly"],
            index=0,
            key="od_gran_vel",
            help="Granularity for Aging Analysis and subsequent charts",
        )
    col_trend, col_panel = st.columns([3, 2], gap="medium")
    with col_trend:
        cust_meta = _render_overdue_trend(df_filtered, granularity_vel)
    with col_panel:
        _render_trend_summary_panel(cust_meta or {})
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    # ------------------------------------------------------------------
    # Section 6 : Portfolio Concentration — Pareto | Treemap
    # ------------------------------------------------------------------
    st.markdown(section_header("Portfolio Concentration"), unsafe_allow_html=True)
    col_pareto, col_tree = st.columns(2, gap="medium")
    with col_pareto:
        _render_pareto(df_filtered)
    with col_tree:
        _render_treemap(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    # ------------------------------------------------------------------
    # Section 7 : Raw Overdue Records (expandable)
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
# Row 1 Right (40%) : Risk Matrix Bubble — X=DPD, Y=OverdueAmount, 4 Quadrants
# =============================================================================
def _render_risk_matrix(df: pd.DataFrame, df_avail: pd.DataFrame = None):
    """
    Risk Matrix — ECharts Bubble
    X    = DPD
    Y    = ESTIMATE_AMOUNT (fallback: TotalOverdue/1e6 ถ้าไม่มี avail)
    Size = Current Debt    (fallback: TotalOverdue log-scaled)
    Color= Zone (Critical / Monitor / Watch / Low Risk)
    """
    import numpy as np

    if "Customer" not in df.columns:
        st.info("Join key 'Customer' not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records for risk matrix.")
        return

    agg = (
        overdue_df.groupby(["Customer", "CustomerName", "DueYear"])
        .agg(TotalOverdue=("OverdueAbs", "sum"), AvgDPD=("DPD", "mean"))
        .reset_index()
    )

    # Join avail
    agg = _join_avail(agg, df_avail, extra_cols=["ESTIMATE_AMOUNT"])

    # Fallback columns
    if "CURRENT_DEBT_MILLION_THB" not in agg.columns:
        agg["CURRENT_DEBT_MILLION_THB"] = float("nan")
    if "ESTIMATE_AMOUNT" not in agg.columns:
        agg["ESTIMATE_AMOUNT"] = float("nan")

    agg["CURRENT_DEBT_MILLION_THB"] = agg["CURRENT_DEBT_MILLION_THB"].fillna(0.0)
    agg["ESTIMATE_AMOUNT"]          = agg["ESTIMATE_AMOUNT"].fillna(0.0)

    # ถ้า ESTIMATE_AMOUNT เป็น 0 ทั้งหมด ใช้ TotalOverdue/1e6 แทน
    if agg["ESTIMATE_AMOUNT"].sum() == 0:
        agg["ESTIMATE_AMOUNT"] = agg["TotalOverdue"] / 1_000_000

    # ถ้า CURRENT_DEBT_MILLION_THB เป็น 0 ทั้งหมด ใช้ TotalOverdue log แทน
    if agg["CURRENT_DEBT_MILLION_THB"].sum() == 0:
        agg["CURRENT_DEBT_MILLION_THB"] = agg["TotalOverdue"] / 1_000_000

    # Quadrant
    median_dpd = float(agg["AvgDPD"].median())
    median_est = float(agg["ESTIMATE_AMOUNT"].median())

    ZONE_COLOR = {
        "Critical": "#A01F2D",
        "Monitor":  "#8E6DC0",
        "Watch":    "#E8A838",
        "Low Risk": "#3A7BD5",
    }

    def _zone(row):
        high_dpd = row["AvgDPD"]        >= median_dpd
        high_est = row["ESTIMATE_AMOUNT"] >= median_est
        if   high_dpd and high_est:      return "Critical"
        elif not high_dpd and high_est:  return "Monitor"
        elif high_dpd and not high_est:  return "Watch"
        else:                            return "Low Risk"

    agg["Zone"] = agg.apply(_zone, axis=1)

    # Bubble size — normalise 10-55
    d_vals         = agg["CURRENT_DEBT_MILLION_THB"].clip(lower=0)
    d_min, d_max   = d_vals.min(), d_vals.max()
    d_range        = max(d_max - d_min, 1)
    agg["BubbleSize"] = (10 + ((d_vals - d_min) / d_range) * 45).clip(upper=55)

    # Build series
    series = []
    for zone, color in ZONE_COLOR.items():
        grp = agg[agg["Zone"] == zone]
        if grp.empty:
            continue
        data = [
            {
                "name":  str(r["CustomerName"]),
                "value": [
                    round(float(r["AvgDPD"]), 1),
                    round(float(r["ESTIMATE_AMOUNT"]), 2),
                    round(float(r["BubbleSize"]), 1),
                ],
                "debt":    round(float(r["CURRENT_DEBT_MILLION_THB"]), 2),
                "overdue": round(float(r["TotalOverdue"]), 0),
            }
            for _, r in grp.iterrows()
        ]
        series.append({
            "name":       zone,
            "type":       "scatter",
            "data":       data,
            "symbolSize": "function(val){ return val[2]; }",
            "itemStyle":  {
                "color":       color,
                "opacity":     0.82,
                "borderColor": "#ffffff",
                "borderWidth": 1,
            },
            "emphasis": {
                "label": {
                    "show":      True,
                    "formatter": "function(p){ return p.data.name.substring(0,14); }",
                    "fontSize":  8,
                    "color":     "#2c3e50",
                },
            },
        })

    # Median dividers
    series.append({
        "name": "",
        "type": "scatter",
        "data": [],
        "markLine": {
            "silent":    True,
            "symbol":    ["none", "none"],
            "lineStyle": {"type": "dashed", "color": "#cccccc", "width": 1},
            "data":      [{"xAxis": median_dpd}, {"yAxis": median_est}],
            "label":     {"show": False},
        },
    })

    x_max = float(agg["AvgDPD"].max()) * 1.12
    y_max = float(agg["ESTIMATE_AMOUNT"].max()) * 1.15

    option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "item",
            "formatter": (
                "function(p){"
                "  if(!p.data || !p.data.value) return '';"
                "  return '<b>' + p.data.name + '</b><br/>'"
                "       + 'DPD: '          + p.data.value[0] + ' days<br/>'"
                "       + 'Est. Amount: '  + p.data.value[1].toLocaleString() + ' MB<br/>'"
                "       + 'Current Debt: ' + p.data.debt.toLocaleString()    + ' MB<br/>'"
                "       + 'Overdue: '      + p.data.overdue.toLocaleString() + ' THB';"
                "}"
            ),
        },
        "legend": {
            "data":      list(ZONE_COLOR.keys()),
            "bottom":    0,
            "itemWidth": 10, "itemHeight": 10,
            "textStyle": {"fontSize": 10},
        },
        "graphic": [
            {"type": "text", "style": {"text": "CRITICAL", "fill": "#A01F2D",
             "fontSize": 11, "fontWeight": "bold"}, "left": "78%", "top": "6%"},
            {"type": "text", "style": {"text": "MONITOR",  "fill": "#8E6DC0",
             "fontSize": 11, "fontWeight": "bold"}, "left": "4%",  "top": "6%"},
            {"type": "text", "style": {"text": "WATCH",    "fill": "#E8A838",
             "fontSize": 11, "fontWeight": "bold"}, "left": "78%", "top": "84%"},
            {"type": "text", "style": {"text": "LOW RISK", "fill": "#3A7BD5",
             "fontSize": 11, "fontWeight": "bold"}, "left": "4%",  "top": "84%"},
        ],
        "xAxis": {
            "name":         "DPD (Days Past Due)",
            "nameLocation": "middle",
            "nameGap":      30,
            "max":          x_max,
            "splitLine":    {"show": True, "lineStyle": {"type": "dashed", "color": "#eeeeee"}},
            "axisLabel":    {"fontSize": 9},
        },
        "yAxis": {
            "name":         "Estimate Amount (MB)",
            "nameLocation": "middle",
            "nameGap":      55,
            "max":          y_max,
            "splitLine":    {"show": True, "lineStyle": {"type": "dashed", "color": "#eeeeee"}},
            "axisLabel":    {"fontSize": 9},
        },
        "series": series,
    }

    st_echarts(option, height="400px", key="echart_risk_matrix")


# =============================================================================
# Row 2 : Linked Bubble
# =============================================================================
def _render_exposure_utilization(df_overdue_filtered: pd.DataFrame, df_avail: pd.DataFrame):
    """
    Aging Distribution — Plotly Bar (ไม่มีเส้นประ)
    X = DPD Bucket
    Y = SUM(Current Debt) MB
    """
    if "Customer" not in df_overdue_filtered.columns:
        st.error(f"Join key 'Customer' not found. Columns: {list(df_overdue_filtered.columns)}")
        return

    overdue_df = df_overdue_filtered[df_overdue_filtered["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records for aging distribution.")
        return

    agg = (
        overdue_df.groupby(["Customer", "CustomerName", "DueYear"])
        .agg(TotalOverdue=("OverdueAbs", "sum"), AvgDPD=("DPD", "mean"))
        .reset_index()
    )

    agg = _join_avail(agg, df_avail)

    if "CURRENT_DEBT_MILLION_THB" not in agg.columns:
        agg["CURRENT_DEBT_MILLION_THB"] = 0.0
    agg["CURRENT_DEBT_MILLION_THB"] = agg["CURRENT_DEBT_MILLION_THB"].fillna(0.0)

    # ถ้าไม่มี avail ใช้ TotalOverdue แทน
    if agg["CURRENT_DEBT_MILLION_THB"].sum() == 0:
        agg["CURRENT_DEBT_MILLION_THB"] = agg["TotalOverdue"] / 1_000_000

    DPD_BUCKETS = ["Current", "1-30", "31-60", "61-90", "91-180", "181-365", "365+"]
    BUCKET_COLORS = [
        PALETTE["jade_lt"],
        PALETTE["sapphire_lt"],
        PALETTE["sapphire"],
        PALETTE["amber_lt"],
        PALETTE["amber"],
        PALETTE["crimson"],
        "#6B0F1A",
    ]

    def _bucket(dpd):
        if pd.isna(dpd) or dpd <= 0: return "Current"
        elif dpd <= 30:   return "1-30"
        elif dpd <= 60:   return "31-60"
        elif dpd <= 90:   return "61-90"
        elif dpd <= 180:  return "91-180"
        elif dpd <= 365:  return "181-365"
        else:             return "365+"

    agg["DPD_Bucket"] = agg["AvgDPD"].apply(_bucket)

    hist = (
        agg.groupby("DPD_Bucket")
        .agg(
            SumDebt=("CURRENT_DEBT_MILLION_THB", "sum"),
            CustomerCount=("Customer",            "nunique"),
        )
        .reindex(DPD_BUCKETS, fill_value=0)
        .reset_index()
    )

    bar_colors = [
        BUCKET_COLORS[DPD_BUCKETS.index(b)]
        for b in hist["DPD_Bucket"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hist["DPD_Bucket"],
        y=hist["SumDebt"],
        marker_color=bar_colors,
        marker=dict(
            color=bar_colors,
            line=dict(width=0),         # ไม่มี border
        ),
        text=[
            f"{v:.1f}M" if v >= 1 else f"{v*1000:.0f}K"
            for v in hist["SumDebt"]
        ],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=9, color=FONT_COLOR),
        customdata=hist["CustomerCount"].values,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Current Debt  : %{y:.2f} MB<br>"
            "Customers     : %{customdata}<br>"
            "<extra></extra>"
        ),
        name="Current Debt (MB)",
    ))
    # ไม่มี secondary axis / เส้นประ

    y_max = float(hist["SumDebt"].max()) * 1.20

    apply_base_layout(fig, {
        "height": 360,
        "margin": dict(l=0, r=20, t=20, b=4),
        "xaxis": dict(
            title="DPD Bucket",
            showgrid=False,
            color=FONT_COLOR,
            tickfont=dict(size=10),
            categoryorder="array",
            categoryarray=DPD_BUCKETS,
        ),
        "yaxis": dict(
            title="SUM(Current Debt) — Million THB",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            range=[0, y_max],
        ),
        "showlegend": False,
        "bargap": 0.28,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_aging_dist_bucket")


# =============================================================================
# Section 3C : Overdue Velocity — Option 2
# =============================================================================
def _render_overdue_velocity(df: pd.DataFrame):
    """
    Overdue Velocity
    ใช้ df_filtered จาก main filter โดยตรง
    Auto-detect granularity จากช่วงข้อมูลที่มี :
      - span >= 365 days  → Yearly
      - span >= 60 days   → Monthly
      - span >= 14 days   → Weekly
      - otherwise         → Daily
    """
    if "OriginalDueDate" not in df.columns or "Customer" not in df.columns:
        st.info("Required columns (Customer, OriginalDueDate) not found.")
        return

    overdue_df = df[df["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records for Velocity analysis.")
        return

    # -- Auto-detect granularity from data span ------------------------------
    date_min = overdue_df["OriginalDueDate"].dropna().min()
    date_max = overdue_df["OriginalDueDate"].dropna().max()
    span_days = (date_max - date_min).days if pd.notna(date_min) and pd.notna(date_max) else 0

    if span_days >= 365:
        auto_gran = "Yearly"
    elif span_days >= 60:
        auto_gran = "Monthly"
    elif span_days >= 14:
        auto_gran = "Weekly"
    else:
        auto_gran = "Daily"

    st.caption(
        f"Date span in filtered data : {span_days} days  "
        f"— auto granularity : {auto_gran}"
    )

    # -- Period label (ใช้ helpers เดิม) -------------------------------------
    overdue_df["_PeriodLabel"] = _period_label_series(overdue_df, auto_gran)
    overdue_df["_SortKey"]     = _sort_key_series(overdue_df, auto_gran)

    all_periods = (
        overdue_df[["_PeriodLabel", "_SortKey"]]
        .drop_duplicates()
        .sort_values("_SortKey")["_PeriodLabel"]
        .tolist()
    )

    if len(all_periods) < 2:
        st.info(
            f"Only {len(all_periods)} period(s) found ({', '.join(all_periods)}). "
            f"At least 2 periods are required to compute Velocity. "
            f"Try expanding the date range in the main filter above."
        )
        return

    prev_period = all_periods[-2]
    curr_period = all_periods[-1]

    st.caption(
        f"Comparing  {prev_period}  (previous)  vs  {curr_period}  (current)"
    )

    # -- ส่วนที่เหลือเหมือนเดิมทุกอย่าง ------------------------------------
    def _agg_period(period_str: str) -> pd.DataFrame:
        sub = overdue_df[overdue_df["_PeriodLabel"] == period_str]
        return (
            sub.groupby(["Customer", "CustomerName"])
            .agg(
                OverdueAmt=("OverdueAbs", "sum"),
                Invoices  =("OverdueAbs", "count"),
            )
            .reset_index()
        )

    df_prev = _agg_period(prev_period).rename(columns={
        "OverdueAmt": "PrevOverdue",
        "Invoices":   "PrevInvoices",
    })
    df_curr = _agg_period(curr_period).rename(columns={
        "OverdueAmt": "CurrOverdue",
        "Invoices":   "CurrInvoices",
    })

    df_vel = df_curr.merge(df_prev, on=["Customer", "CustomerName"], how="outer")
    df_vel["CurrOverdue"]  = df_vel["CurrOverdue"].fillna(0.0)
    df_vel["PrevOverdue"]  = df_vel["PrevOverdue"].fillna(0.0)
    df_vel["CustomerName"] = df_vel["CustomerName"].fillna(
        df_vel["Customer"].astype(str)
    )

    df_vel["VelocityAmt"] = df_vel["CurrOverdue"] - df_vel["PrevOverdue"]
    df_vel["VelocityPct"] = (
        df_vel["VelocityAmt"]
        / df_vel["PrevOverdue"].replace(0.0, float("nan"))
        * 100
    )
    fill_vals = pd.Series(
        [100.0 if c > 0 else 0.0 for c in df_vel["CurrOverdue"]],
        index=df_vel.index,
    )
    df_vel["VelocityPct"] = df_vel["VelocityPct"].fillna(fill_vals)

    surge_thresh = (
        float(df_vel["VelocityAmt"].quantile(0.75))
        if len(df_vel) >= 4 else 0.0
    )

    def _tier_q(v: float) -> str:
        if v > surge_thresh and v > 0: return "Surging"
        elif v > 0:                    return "Rising"
        elif v == 0:                   return "Flat"
        else:                          return "Improving"

    df_vel["VelocityTier"] = df_vel["VelocityAmt"].apply(_tier_q)

    TIER_COLOR = {
        "Surging":   PALETTE["crimson"],
        "Rising":    PALETTE["amber"],
        "Flat":      PALETTE["nodata"],
        "Improving": PALETTE["jade_lt"],
    }
    TIER_ORDER = ["Surging", "Rising", "Flat", "Improving"]

    # -- KPI row --------------------------------------------------------------
    net_change = float(df_vel["VelocityAmt"].sum())
    surging    = df_vel[df_vel["VelocityTier"] == "Surging"]
    rising     = df_vel[df_vel["VelocityAmt"] > 0]
    improving  = df_vel[df_vel["VelocityAmt"] < 0]

    v_cols = st.columns(4, gap="small")
    kpi_vel = [
        (
            "Surging",
            f"{len(surging):,} customers",
            f"+{surging['VelocityAmt'].sum():,.0f} THB",
            "danger",
        ),
        (
            "Rising (All)",
            f"{len(rising):,} customers",
            f"+{rising['VelocityAmt'].sum():,.0f} THB",
            "warning",
        ),
        (
            "Improving",
            f"{len(improving):,} customers",
            f"{improving['VelocityAmt'].sum():,.0f} THB",
            "safe",
        ),
        (
            "Net Portfolio Change",
            f"{net_change:+,.0f} THB",
            f"{prev_period} to {curr_period}",
            "danger" if net_change > 0 else "safe",
        ),
    ]
    for col_ui, (label, value, sub, variant) in zip(v_cols, kpi_vel):
        col_ui.markdown(
            _overdue_kpi_card(label=label, value=value, sub=sub, variant=variant),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    col_bar, col_scatter = st.columns([1, 1], gap="medium")

    with col_bar:
        top_growth = (
            df_vel[df_vel["VelocityAmt"] > 0]
            .sort_values("VelocityAmt", ascending=False)
            .head(15)
            .copy()
        )

        if top_growth.empty:
            st.info("No customers with increasing overdue in this period.")
        else:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x           = [float(v) for v in top_growth["VelocityAmt"]],
                y           = [str(v)   for v in top_growth["CustomerName"]],
                orientation = "h",
                marker_color = [
                    TIER_COLOR.get(t, PALETTE["nodata"])
                    for t in top_growth["VelocityTier"]
                ],
                text = [
                    f"+{v:,.0f}  ({p:+.0f}%)"
                    for v, p in zip(
                        top_growth["VelocityAmt"],
                        top_growth["VelocityPct"],
                    )
                ],
                textposition = "outside",
                cliponaxis   = False,
                textfont     = dict(size=8, color=FONT_COLOR),
                customdata   = list(zip(
                    [float(v) for v in top_growth["CurrOverdue"]],
                    [float(v) for v in top_growth["PrevOverdue"]],
                )),
                hovertemplate = (
                    "<b>%{y}</b><br>"
                    "Delta Overdue         : %{x:+,.2f} THB<br>"
                    f"Previous ({prev_period}) : %{{customdata[1]:,.2f}} THB<br>"
                    f"Current  ({curr_period}) : %{{customdata[0]:,.2f}} THB<br>"
                    "<extra></extra>"
                ),
            ))
            apply_base_layout(fig_bar, {
                "height": 420,
                "margin": dict(l=0, r=90, t=20, b=4),
                "xaxis": dict(
                    title="Delta Overdue Amount (THB)",
                    showgrid=True, gridcolor=GRID_COLOR,
                    color=FONT_COLOR, tickfont=dict(size=8),
                    zeroline=False,
                ),
                "yaxis": dict(
                    autorange="reversed",
                    showgrid=False,
                    color=FONT_COLOR, tickfont=dict(size=8),
                ),
                "showlegend": False,
                "title": dict(
                    text=f"Top 15 Overdue Growth  ({prev_period} to {curr_period})",
                    font=dict(size=10, color=FONT_COLOR), x=0,
                ),
            })
            st.plotly_chart(fig_bar, use_container_width=True, key="chart_velocity_bar")

    with col_scatter:
        df_plot = df_vel[
            (df_vel["CurrOverdue"] > 0) | (df_vel["PrevOverdue"] > 0)
        ].copy()

        if df_plot.empty:
            st.info("No data for scatter plot.")
        else:
            s_vals  = df_plot["CurrOverdue"].clip(lower=1.0)
            s_min, s_max = float(s_vals.min()), float(s_vals.max())
            s_range = max(s_max - s_min, 1.0)
            df_plot["BubbleSize"] = (
                6 + ((s_vals - s_min) / s_range) * 44
            ).clip(upper=50)

            fig_sc = go.Figure()

            for tier in TIER_ORDER:
                grp = df_plot[df_plot["VelocityTier"] == tier]
                if grp.empty:
                    continue
                fig_sc.add_trace(go.Scatter(
                    x    = [float(v) for v in grp["PrevOverdue"]],
                    y    = [float(v) for v in grp["CurrOverdue"]],
                    mode = "markers",
                    name = tier,
                    marker = dict(
                        size     = [float(v) for v in grp["BubbleSize"]],
                        color    = TIER_COLOR.get(tier, PALETTE["nodata"]),
                        opacity  = 0.80,
                        line     = dict(width=1, color="white"),
                        sizemode = "diameter",
                    ),
                    text = [str(v) for v in grp["CustomerName"]],
                    customdata = list(zip(
                        [float(v) for v in grp["VelocityAmt"]],
                        [float(v) for v in grp["VelocityPct"]],
                    )),
                    hovertemplate = (
                        "<b>%{text}</b><br>"
                        f"Previous ({prev_period}) : %{{x:,.2f}} THB<br>"
                        f"Current  ({curr_period}) : %{{y:,.2f}} THB<br>"
                        "Delta        : %{customdata[0]:+,.2f} THB<br>"
                        "Delta %%     : %{customdata[1]:+.1f}%%<extra></extra>"
                    ),
                ))

            axis_max = float(max(
                df_plot["CurrOverdue"].max(),
                df_plot["PrevOverdue"].max(),
            )) * 1.08
            fig_sc.add_trace(go.Scatter(
                x=[0.0, axis_max], y=[0.0, axis_max],
                mode="lines",
                line=dict(dash="dot", color="#cccccc", width=1),
                showlegend=False,
                hoverinfo="skip",
            ))
            fig_sc.add_annotation(
                x=axis_max * 0.12, y=axis_max * 0.88,
                text="Deteriorating<br>(above line)",
                showarrow=False,
                font=dict(color=PALETTE["crimson"], size=9),
                bgcolor="rgba(255,255,255,0.75)",
            )
            fig_sc.add_annotation(
                x=axis_max * 0.75, y=axis_max * 0.10,
                text="Improving<br>(below line)",
                showarrow=False,
                font=dict(color=PALETTE["jade"], size=9),
                bgcolor="rgba(255,255,255,0.75)",
            )
            apply_base_layout(fig_sc, {
                "height": 420,
                "margin": dict(l=0, r=20, t=20, b=4),
                "xaxis": dict(
                    title=f"Previous Overdue — {prev_period} (THB)",
                    showgrid=True, gridcolor=GRID_COLOR,
                    color=FONT_COLOR, tickfont=dict(size=8),
                    range=[-axis_max * 0.02, axis_max],
                    zeroline=False,
                ),
                "yaxis": dict(
                    title=f"Current Overdue — {curr_period} (THB)",
                    showgrid=True, gridcolor=GRID_COLOR,
                    color=FONT_COLOR, tickfont=dict(size=8),
                    range=[-axis_max * 0.02, axis_max],
                    zeroline=False,
                ),
                "legend": dict(
                    font=dict(size=9),
                    orientation="h",
                    yanchor="bottom", y=1.01,
                    xanchor="right",  x=1,
                ),
                "title": dict(
                    text="Previous vs Current Period",
                    font=dict(size=10, color=FONT_COLOR), x=0,
                ),
            })
            st.plotly_chart(
                fig_sc, use_container_width=True, key="chart_velocity_scatter"
            )


# =============================================================================
# Section 5 Left (60%) : Overdue Trend
# =============================================================================
def _render_overdue_trend(df: pd.DataFrame, granularity: str):
    if "OriginalDueDate" not in df.columns:
        st.info("OriginalDueDate column not found.")
        return None

    overdue_df = df[
        df["IsOverdue"] &
        (df["OverdueAbs"] > 0)
    ].copy()

    if overdue_df.empty:
        st.info("No overdue records with amount > 0.")
        return None

    if "CustomerName" not in overdue_df.columns:
        st.info("CustomerName column not found.")
        return None

    overdue_df["_PeriodLabel"] = _period_label_series(overdue_df, granularity)
    overdue_df["_SortKey"]     = _sort_key_series(overdue_df, granularity)

    ctl1, ctl2, ctl3 = st.columns([2, 1, 1])
    with ctl1:
        search_text = st.text_input(
            "Search customer name",
            placeholder="Type company name (leave blank for Top N)",
            key="od_trend_search",
            label_visibility="collapsed",
        )
    with ctl2:
        top_n = st.number_input(
            "Top N", min_value=1, max_value=50, value=10, step=1,
            key="od_trend_topn",
            label_visibility="collapsed",
            help="Top N customers by total overdue",
        )
    with ctl3:
        trend_mode = st.selectbox(
            "Mode",
            options=["Per-Period", "Cumulative"],
            index=0,
            key="od_trend_mode",
            label_visibility="collapsed",
        )

    grp = (
        overdue_df
        .groupby(["CustomerName", "_PeriodLabel", "_SortKey"])
        .agg(OverdueAbs=("OverdueAbs", "sum"))
        .reset_index()
        .sort_values("_SortKey")
    )

    cust_totals   = (
        grp.groupby("CustomerName")["OverdueAbs"]
        .sum().sort_values(ascending=False)
    )
    all_customers = cust_totals.index.tolist()

    if search_text.strip():
        terms = [t.strip().lower() for t in search_text.split(",") if t.strip()]
        sel_customers = [c for c in all_customers
                         if any(t in c.lower() for t in terms)]
        if not sel_customers:
            st.warning(f"No customers match: {search_text}")
            sel_customers = all_customers[:int(top_n)]
    else:
        sel_customers = all_customers[:int(top_n)]

    if not sel_customers:
        st.info("No customers to display.")
        return None

    grp_sel = grp[grp["CustomerName"].isin(sel_customers)]

    all_periods = (
        grp_sel[["_PeriodLabel", "_SortKey"]]
        .drop_duplicates()
        .sort_values("_SortKey")["_PeriodLabel"]
        .tolist()
    )

    if not all_periods:
        st.info("No period data found.")
        return None

    pivot_raw = (
        grp_sel.pivot_table(
            index="CustomerName",
            columns="_PeriodLabel",
            values="OverdueAbs",
            aggfunc="sum",
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

    import plotly.express as px
    import numpy as _np

    COLOR_PALETTE = (
        px.colors.qualitative.Plotly
        + px.colors.qualitative.D3
        + px.colors.qualitative.Set1
    )

    cust_meta = {}
    for i, cust in enumerate(sel_customers):
        if cust not in pivot_raw.index:
            continue
        color  = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        y_raw  = pivot_raw.loc[cust].tolist()
        x_idx  = list(range(len(y_raw)))

        if len(y_raw) >= 2 and sum(y_raw) > 0:
            coeffs = _np.polyfit(x_idx, y_raw, 1)
            slope  = float(coeffs[0])
        else:
            slope = 0.0

        active_periods = int(sum(1 for v in y_raw if v > 0))
        total_periods  = len(y_raw)
        total_ov       = sum(y_raw)
        last_ov        = y_raw[-1]
        first_ov       = next((v for v in y_raw if v > 0), 0.0)
        delta_ov       = last_ov - first_ov
        max_ov         = max(y_raw) if y_raw else 0.0
        ratio          = active_periods / max(total_periods, 1)

        if slope > 0 and ratio >= 0.5:
            classification = "Escalating"
        elif slope < 0 and ratio >= 0.3:
            classification = "Improving"
        elif ratio >= 0.5:
            classification = "Persistent"
        else:
            classification = "Intermittent"

        cust_meta[cust] = {
            "color": color, "total_ov": total_ov, "last_ov": last_ov,
            "delta_ov": delta_ov, "max_ov": max_ov, "slope": slope,
            "active_periods": active_periods, "total_periods": total_periods,
            "classification": classification,
        }

    fig = go.Figure()

    for i, cust in enumerate(sel_customers):
        if cust not in pivot_plot.index:
            continue
        color  = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        y_plot = pivot_plot.loc[cust].tolist()
        y_raw  = pivot_raw.loc[cust].tolist()

        fig.add_trace(go.Scatter(
            x    = all_periods,
            y    = y_plot,
            mode = "lines+markers",
            name = cust,
            line   = dict(width=2.5, color=color),
            marker = dict(
                size=8, color=color,
                line=dict(width=1.5, color="white"),
            ),
            customdata = list(zip(
                y_raw,
                [cust_meta.get(cust, {}).get("classification", "")] * len(y_raw),
            )),
            hovertemplate = (
                f"<b>{cust}</b><br>"
                "Period         : %{x}<br>"
                "Overdue        : <b>%{y:,.2f} THB</b><br>"
                "Period Amount  : %{customdata[0]:,.2f} THB<br>"
                "Classification : %{customdata[1]}<br>"
                "<extra></extra>"
            ),
        ))

    if len(sel_customers) > 1:
        avg_y = pivot_plot.mean(axis=0).tolist()
        fig.add_trace(go.Scatter(
            x    = all_periods,
            y    = avg_y,
            mode = "lines",
            name = "Portfolio Average",
            line = dict(width=2, dash="dot", color="rgba(0,0,0,0.45)"),
            hovertemplate = (
                "Portfolio Average<br>"
                "Period : %{x}<br>"
                "Overdue : <b>%{y:,.2f} THB</b>"
                "<extra></extra>"
            ),
        ))

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
            title         = f"Period ({granularity})",
            tickangle     = -35,
            tickfont      = dict(size=8),
            showgrid      = True,
            gridcolor     = GRID_COLOR,
            color         = FONT_COLOR,
            type          = "category",
            categoryorder = "array",
            categoryarray = all_periods,
        ),
        "yaxis": dict(
            title     = y_title,
            showgrid  = True, gridcolor=GRID_COLOR,
            color     = FONT_COLOR, tickfont=dict(size=9),
            rangemode = "tozero",
        ),
        "legend": dict(
            orientation="v", x=1.01, y=1,
            font=dict(size=8),
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