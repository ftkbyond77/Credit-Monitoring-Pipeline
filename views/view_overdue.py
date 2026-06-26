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

    # Section 1 : KPI Row
    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # Section 2 : Priority Monitoring | Risk Matrix
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

    # Section 3 : Aging Distribution
    st.markdown(
        section_header("Aging Distribution — Current Debt by DPD Bucket"),
        unsafe_allow_html=True,
    )
    _render_exposure_utilization(df_filtered, df_avail_full)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # Section 4 : Invoice Date Segmentation
    st.markdown(
        section_header("Invoice Date Segmentation — Payment Status by Stage"),
        unsafe_allow_html=True,
    )
    _render_invoice_date_segmentation(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # Section 5 : Aging Analysis & Trend
    st.markdown(section_header("Aging Analysis & Trend"), unsafe_allow_html=True)

    with st.expander("Portfolio Classification — เกณฑ์การแบ่งกลุ่ม", expanded=False):
        guide_cls = [
            {
                "Classification":  "Escalating",
                "ความหมาย":        "หนี้มีแนวโน้มเพิ่มขึ้นต่อเนื่อง",
                "Slope":           "slope > 0",
                "Active Ratio":    ">= 50% ของ period ทั้งหมด",
                "ระดับความเสี่ยง": "สูง",
            },
            {
                "Classification":  "Improving",
                "ความหมาย":        "หนี้มีแนวโน้มลดลง",
                "Slope":           "slope < 0",
                "Active Ratio":    ">= 30% ของ period ทั้งหมด",
                "ระดับความเสี่ยง": "ปานกลาง — กำลังดีขึ้น",
            },
            {
                "Classification":  "Persistent",
                "ความหมาย":        "หนี้ค้างสม่ำเสมอ ไม่เพิ่มไม่ลด",
                "Slope":           "slope >= 0",
                "Active Ratio":    ">= 50% ของ period ทั้งหมด",
                "ระดับความเสี่ยง": "ปานกลาง — ค้างเรื้อรัง",
            },
            {
                "Classification":  "Intermittent",
                "ความหมาย":        "หนี้เกิดเป็นครั้งคราว ไม่สม่ำเสมอ",
                "Slope":           "ใดก็ได้",
                "Active Ratio":    "< 50% ของ period ทั้งหมด",
                "ระดับความเสี่ยง": "ต่ำ",
            },
        ]
        st.dataframe(
            pd.DataFrame(guide_cls),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Classification":  st.column_config.TextColumn("Classification", width="medium"),
                "ความหมาย":        st.column_config.TextColumn("ความหมาย",       width="large"),
                "Slope":           st.column_config.TextColumn("Slope",          width="small"),
                "Active Ratio":    st.column_config.TextColumn("Active Ratio",   width="medium"),
                "ระดับความเสี่ยง": st.column_config.TextColumn("ระดับความเสี่ยง",width="medium"),
            },
        )
        st.caption(
            "Slope = linear regression ของยอดหนี้ per-period (polyfit deg=1)  |  "
            "Active Ratio = periods ที่มีหนี้ > 0 / periods ทั้งหมดใน filter range"
        )

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

    # Section 6 : Portfolio Concentration
    st.markdown(section_header("Portfolio Concentration"), unsafe_allow_html=True)
    col_pareto, col_tree = st.columns(2, gap="medium")
    with col_pareto:
        _render_pareto(df_filtered)
    with col_tree:
        _render_treemap(df_filtered)
    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

    # Section 7 : Raw Records
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

# =============================================================================
# FILTER BAR
# แก้: Search Customer Name เปลี่ยนจาก text_input ธรรมดา
#       เป็น text_input + selectbox recommend (pattern เดียวกับ view_avail.py
#       _render_trend_analysis) — ผล filter ยังคงส่งผ่าน df_filtered เหมือนเดิม
# =============================================================================
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

    COLS = [1.2, 1, 1, 1, 1, 1.6]

    lc1, lc2, lc3, lc4, lc5, lc6 = st.columns(COLS, gap="small")
    with lc1:
        st.markdown("Company Code",         unsafe_allow_html=True)
    with lc2:
        st.markdown("OriginalDueDate From", unsafe_allow_html=True)
    with lc3:
        st.markdown("OriginalDueDate To",   unsafe_allow_html=True)
    with lc4:
        st.markdown("CollectionDate From",  unsafe_allow_html=True)
    with lc5:
        st.markdown("CollectionDate To",    unsafe_allow_html=True)
    with lc6:
        st.markdown("Search Customer Name", unsafe_allow_html=True)

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
            "Due From", value=None, key="od_due_start",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc3:
        due_end = st.date_input(
            "Due To", value=None, key="od_due_end",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc4:
        coll_start = st.date_input(
            "Coll From", value=None, key="od_coll_start",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )
    with wc5:
        coll_end = st.date_input(
            "Coll To", value=None, key="od_coll_end",
            label_visibility="collapsed", format="YYYY/MM/DD",
        )

    # ------------------------------------------------------------------
    # Search Customer Name — text_input + selectbox recommend (scroll)
    # ใช้ df_all scope ตาม CompanyCode ที่เลือกแล้ว
    # ------------------------------------------------------------------
    df_company_scope = df_all[df_all["CompanyCode"] == selected_company]
    all_customer_names: list = []
    if "CustomerName" in df_company_scope.columns:
        all_customer_names = sorted(
            df_company_scope["CustomerName"].dropna().unique().tolist(),
            key=lambda x: str(x).lower(),
        )

    with wc6:
        search_query = st.text_input(
            "Search Customer Name",
            placeholder="Type name to filter list...",
            key="od_customer_search",
            label_visibility="collapsed",
        ).strip()

    # กรอง recommend list ตาม query
    if search_query:
        q_lower = search_query.lower()
        recommend_list = [n for n in all_customer_names if q_lower in str(n).lower()]
    else:
        recommend_list = all_customer_names

    # selectbox recommend — ใต้ filter bar เต็มแถว (ไม่บีบ column)
    OPTION_ALL = "All customers"
    options_with_all = [OPTION_ALL] + recommend_list

    if recommend_list:
        # รักษา selection เดิมถ้า key ยังอยู่ใน list
        prev_sel = st.session_state.get("od_customer_select", OPTION_ALL)
        default_sel_ix = (
            options_with_all.index(prev_sel)
            if prev_sel in options_with_all
            else 0
        )
        selected_customer_name = st.selectbox(
            f"Select Customer ({len(recommend_list)} found)",
            options=options_with_all,
            index=default_sel_ix,
            key="od_customer_select",
            label_visibility="visible",
        )
    else:
        if search_query:
            st.caption(f"No customer matched '{search_query}'.")
        selected_customer_name = OPTION_ALL

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    df_company = df_company_scope.copy()
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

    # กรองตาม selectbox (ถ้าเลือก specific customer)
    if (
        selected_customer_name != OPTION_ALL
        and "CustomerName" in df_filtered.columns
    ):
        df_filtered = df_filtered[
            df_filtered["CustomerName"] == selected_customer_name
        ]

    parts = []
    if due_start or due_end:
        parts.append("Due: " + " -> ".join(filter(None, [
            str(due_start) if due_start else None,
            str(due_end)   if due_end   else None,
        ])))
    if coll_start or coll_end:
        parts.append("Collected: " + " -> ".join(filter(None, [
            str(coll_start) if coll_start else None,
            str(coll_end)   if coll_end   else None,
        ])))
    if selected_customer_name != OPTION_ALL:
        parts.append(f"Customer: {selected_customer_name}")

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
def _render_exposure_utilization(df_overdue_filtered: pd.DataFrame, df_avail: pd.DataFrame):
    if "DPD" not in df_overdue_filtered.columns:
        st.error("DPD column not found. Check _prepare_overdue().")
        return

    overdue_df = df_overdue_filtered[df_overdue_filtered["IsOverdue"]].copy()
    if overdue_df.empty:
        st.info("No overdue records (Debit Note) for aging distribution.")
        return

    # sanity check
    if (overdue_df["OverdueAbs"] < 0).any():
        overdue_df["OverdueAbs"] = overdue_df["OverdueAbs"].abs()

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

    # ------------------------------------------------------------------
    # Per-record DPD bucket — ถูกต้องกว่า AvgDPD per customer
    # เพราะ customer เดียวอาจมี invoice ต่าง bucket
    # ------------------------------------------------------------------
    def _bucket(dpd):
        if pd.isna(dpd) or dpd <= 0: return "Current"
        elif dpd <= 30:               return "1-30"
        elif dpd <= 60:               return "31-60"
        elif dpd <= 90:               return "61-90"
        elif dpd <= 180:              return "91-180"
        elif dpd <= 365:              return "181-365"
        else:                         return "365+"

    overdue_df["DPD_Bucket"] = overdue_df["DPD"].apply(_bucket)

    # Aggregate per bucket — ใช้ OverdueAbs โดยตรง (unit: THB)
    # แปลงเป็น MB เพื่อแสดงผล
    hist = (
        overdue_df.groupby("DPD_Bucket")
        .agg(
            SumOverdue=("OverdueAbs",    "sum"),
            RecordCount=("OverdueAbs",   "count"),
            CustomerCount=("CustomerName", "nunique") if "CustomerName" in overdue_df.columns
                          else ("Customer", "nunique"),
        )
        .reindex(DPD_BUCKETS, fill_value=0)
        .reset_index()
    )
    hist["SumOverdueMB"] = hist["SumOverdue"] / 1_000_000

    bar_colors = [
        BUCKET_COLORS[DPD_BUCKETS.index(b)]
        for b in hist["DPD_Bucket"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hist["DPD_Bucket"],
        y=hist["SumOverdueMB"],
        marker_color=bar_colors,
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=[
            f"{v:.2f}M" if v >= 0.01 else (f"{v*1000:.0f}K" if v >= 0.00001 else "")
            for v in hist["SumOverdueMB"]
        ],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=9, color=FONT_COLOR),
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

    y_max = float(hist["SumOverdueMB"].max()) * 1.25 if hist["SumOverdueMB"].max() > 0 else 1.0

    apply_base_layout(fig, {
        "height": 360,
        "margin": dict(l=0, r=20, t=20, b=4),
        "xaxis": dict(
            title="DPD Bucket (per invoice)",
            showgrid=False,
            color=FONT_COLOR,
            tickfont=dict(size=10),
            categoryorder="array",
            categoryarray=DPD_BUCKETS,
        ),
        "yaxis": dict(
            title="Overdue Amount — Million THB",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
            range=[0, y_max],
        ),
        "showlegend": False,
        "bargap": 0.28,
    })
    st.plotly_chart(fig, use_container_width=True, key="chart_aging_dist_bucket")

    # caption ยืนยัน filter
    total_rec = int(hist["RecordCount"].sum())
    total_cust = overdue_df["CustomerName"].nunique() if "CustomerName" in overdue_df.columns \
                 else overdue_df["Customer"].nunique()
    st.caption(
        f"Showing {total_rec:,} overdue invoice(s) from {total_cust:,} customer(s) "
        f"— filtered by main filter above. DPD computed per invoice."
    )


# =============================================================================
# Invoice Date Segmentation — Payment Status by Stage
# แทน Funnel ด้วย Multi-level Treemap (Root -> Stage -> Customer)
# เพิ่ม guideline expander ก่อน chart
# =============================================================================
# =============================================================================
# Invoice Date Segmentation — Payment Status by Stage
# =============================================================================
def _render_invoice_date_segmentation(df: pd.DataFrame):
    today = pd.Timestamp("today").normalize()

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

    work["Stage"] = work.apply(
        lambda r: _classify_invoice_stage(r, today), axis=1
    )

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

    # ------------------------------------------------------------------
    # Guideline expander — Action Item ออก
    # ------------------------------------------------------------------
    with st.expander("Stage Guideline — Credit Management Logic Matrix", expanded=False):
        guide_rows = [
            {
                "Stage":              "1. Normal (ปกติ)",
                "OriginalDueDate":     "ไม่เกิน",
                "CustomerDueDate":     "ไม่เกิน",
                "CollectionDate":   "ไม่เกิน",
                "ระดับความเสี่ยง":    "LOW",
            },
            {
                "Stage":              "2. Grace Period (ผ่อนผัน)",
                "OriginalDueDate":     "เกินแล้ว",
                "CustomerDueDate":     "ไม่เกิน",
                "CollectionDate":   "ไม่เกิน",
                "ระดับความเสี่ยง":    "MEDIUM",
            },
            {
                "Stage":              "3. Late Warning (เตือนเข้ม)",
                "OriginalDueDate":     "เกินแล้ว",
                "CustomerDueDate":     "เกินแล้ว",
                "CollectionDate":   "ไม่เกิน",
                "ระดับความเสี่ยง":    "HIGH",
            },
            {
                "Stage":              "4. Critical (วิกฤต)",
                "OriginalDueDate":     "เกินแล้ว",
                "CustomerDueDate":     "เกินแล้ว",
                "CollectionDate":   "เกินแล้ว",
                "ระดับความเสี่ยง":    "CRITICAL",
            },
        ]
        st.dataframe(
            pd.DataFrame(guide_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stage":              st.column_config.TextColumn("Stage",              width="medium"),
                "OriginalDueDate":     st.column_config.TextColumn("OriginalDueDate",    width="small"),
                "CustomerDueDate":     st.column_config.TextColumn("CustomerDueDate",    width="small"),
                "CollectionDate":   st.column_config.TextColumn("CollectionDate",  width="small"),
                "ระดับความเสี่ยง":    st.column_config.TextColumn("ระดับความเสี่ยง",   width="small"),
            },
        )

    # ------------------------------------------------------------------
    # Count mode selector
    # ------------------------------------------------------------------
    mode_col, _ = st.columns([2, 5])
    with mode_col:
        count_mode = st.radio(
            "Count mode",
            options=["Per Invoice", "Per Customer"],
            index=0,
            horizontal=True,
            key="seg_count_mode",
            help=(
                "Per Invoice: นับทุก invoice record  |  "
                "Per Customer: 1 ลูกค้า = 1 stage (worst stage)"
            ),
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
                Stage = ("Stage",     lambda x: max(x, key=lambda s: stage_rank[s])),
                _val  = ("OverdueAbs","sum"),
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

    # กรองเฉพาะ stage ที่มีข้อมูล
    stage_sum_active = stage_sum[stage_sum["Count"] > 0].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Layout: 35% Pie | 65% table
    # ------------------------------------------------------------------
    col_pie, col_table = st.columns([35, 65], gap="medium")

    with col_pie:
        if stage_sum_active.empty:
            st.info("No stage data to display.")
        else:
            pie_labels  = stage_sum_active["Stage"].tolist()
            pie_counts  = stage_sum_active["Count"].tolist()
            pie_totals  = stage_sum_active["TotalOverdue"].tolist()
            pie_pcts    = stage_sum_active["Pct"].tolist()
            pie_colors  = [STAGE_COLOR[s] for s in pie_labels]
            pie_risks   = [STAGE_RISK[s]  for s in pie_labels]

            hover_texts = [
                (
                    f"<b>{pie_labels[i]}</b><br>"
                    f"Risk     : {pie_risks[i]}<br>"
                    f"Count    : {pie_counts[i]:,} {funnel_label}<br>"
                    f"Share    : {pie_pcts[i]:.1f}%<br>"
                    f"Overdue  : {pie_totals[i]:,.0f} THB"
                )
                for i in range(len(pie_labels))
            ]

            fig_pie = go.Figure(go.Pie(
                labels        = pie_labels,
                values        = pie_counts,
                hole          = 0.40,
                marker        = dict(
                    colors = pie_colors,
                    line   = dict(color="white", width=2),
                ),
                text          = [f"{p:.1f}%" for p in pie_pcts],
                textinfo      = "text",
                textfont      = dict(size=11),
                hovertext     = hover_texts,
                hovertemplate = "%{hovertext}<extra></extra>",
                sort          = False,
                direction     = "clockwise",
            ))

            fig_pie.add_annotation(
                text      = f"{total_count:,}<br>{funnel_label}",
                x=0.5, y=0.5,
                font      = dict(size=12, color=FONT_COLOR),
                showarrow = False,
            )

            fig_pie.update_layout(
                height        = 340,
                margin        = dict(l=0, r=0, t=30, b=0),
                paper_bgcolor = "rgba(0,0,0,0)",
                plot_bgcolor  = "rgba(0,0,0,0)",
                font          = dict(color=FONT_COLOR, family="Inter, sans-serif", size=10),
                title         = dict(
                    text = f"Stage Distribution ({count_mode})",
                    font = dict(size=11, color=FONT_COLOR), x=0,
                ),
                legend = dict(
                    orientation = "h",
                    yanchor     = "top",
                    y           = -0.06,
                    xanchor     = "center",
                    x           = 0.5,
                    font        = dict(size=9),
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

            # summary strip ใต้ pie
            for _, sr in stage_sum_active.iterrows():
                stage = sr["Stage"]
                cnt   = int(sr["Count"])
                pct   = float(sr["Pct"])
                tot   = float(sr["TotalOverdue"])
                risk  = STAGE_RISK[stage]
                col   = STAGE_COLOR[stage]
                st.markdown(
                    f"<div style='border-left:3px solid {col};"
                    f"background:rgba(0,0,0,0.03);"
                    f"border-radius:0 6px 6px 0;"
                    f"padding:5px 10px;margin-bottom:5px;'>"
                    f"<div style='font-size:0.67rem;font-weight:700;color:{col};'>"
                    f"{stage} — {risk}</div>"
                    f"<div style='font-size:0.70rem;color:{FONT_COLOR};'>"
                    f"{cnt:,} {funnel_label} ({pct:.1f}%)</div>"
                    f"<div style='font-size:0.67rem;color:#6b7a8d;'>"
                    f"Overdue: {tot:,.0f} THB</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # --- Detailed Debtor Registry ---
    with col_table:
        st.markdown(
            f"<div style='font-size:0.75rem;font-weight:700;"
            f"color:{PALETTE['sapphire']};letter-spacing:0.05em;"
            f"text-transform:uppercase;margin-bottom:8px;'>"
            f"Detailed Debtor Registry</div>",
            unsafe_allow_html=True,
        )

        fc1, fc2 = st.columns([2, 2])
        with fc1:
            stage_filter = st.multiselect(
                "Filter by Stage",
                options=STAGE_ORDER,
                default=STAGE_ORDER,
                key="seg_stage_filter",
            )
        with fc2:
            sort_opt = st.selectbox(
                "Sort Overdue Amount",
                options=["High to Low", "Low to High"],
                index=0,
                key="seg_sort",
            )

        if count_mode == "Per Invoice":
            desired_cols = [
                cust_col, "Stage", "OverdueAbs",
                "OriginalDueDate", "CustomerDueDate", "CollectionDate", "DPD",
            ]
            avail_cols = [c for c in desired_cols if c in work.columns]
            table_df   = work[avail_cols].copy().rename(columns={
                cust_col:     "Customer Name",
                "OverdueAbs": "Overdue Amount",
                "Stage":      "Risk Stage",
            })
        else:
            table_df = (
                work.groupby(cust_col)
                .agg(
                    Stage        = ("Stage",      lambda x: max(x, key=lambda s: {s: i for i, s in enumerate(STAGE_ORDER)}[s])),
                    TotalOverdue = ("OverdueAbs", "sum"),
                    InvoiceCount = ("OverdueAbs", "count"),
                )
                .reset_index()
                .rename(columns={
                    cust_col:      "Customer Name",
                    "Stage":       "Risk Stage",
                    "TotalOverdue":"Overdue Amount",
                    "InvoiceCount":"Invoices",
                })
            )

        table_df.insert(
            table_df.columns.tolist().index("Risk Stage") + 1,
            "Risk Level",
            table_df["Risk Stage"].map(STAGE_RISK),
        )

        filtered_table = (
            table_df[table_df["Risk Stage"].isin(stage_filter)]
            .copy()
            .sort_values("Overdue Amount", ascending=(sort_opt == "Low to High"))
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
                "Overdue Amount": st.column_config.NumberColumn(
                    "Overdue Amount (THB)", format="%.2f"
                ),
                "Risk Stage":  st.column_config.TextColumn("Risk Stage"),
                "Risk Level":  st.column_config.TextColumn("Risk Level"),
                "DPD":         st.column_config.NumberColumn("DPD (days)", format="%d"),
            }
            if "Invoices" in filtered_table.columns:
                col_cfg["Invoices"] = st.column_config.NumberColumn("Invoices", format="%d")

            st.dataframe(
                filtered_table,
                use_container_width=True,
                hide_index=True,
                height=460,
                column_config=col_cfg,
            )

            total_shown  = len(filtered_table)
            total_amount = float(filtered_table["Overdue Amount"].sum())
            st.caption(
                f"{total_shown:,} record(s) shown — "
                f"Total Overdue: {total_amount:,.2f} THB"
            )

# =============================================================================
# Section 5 Left (60%) : Overdue Trend
# =============================================================================
def _render_overdue_trend(df: pd.DataFrame, granularity: str) -> dict:
    import plotly.express as px
    import numpy as _np

    if "OriginalDueDate" not in df.columns:
        st.info("OriginalDueDate column not found.")
        return {}

    overdue_df = df[
        df["IsOverdue"] &
        (df["OverdueAbs"] > 0)
    ].copy()

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
            "Mode",
            options=["Per-Period", "Cumulative"],
            index=0,
            key="od_trend_mode",
            label_visibility="collapsed",
        )

    if search_text.strip():
        terms = [t.strip().lower() for t in search_text.split(",") if t.strip()]
        recommend = [
            c for c in all_customer_names
            if any(t in c.lower() for t in terms)
        ]
    else:
        recommend = all_customer_names

    OPTION_ALL       = "__top_n__"
    LABEL_ALL        = f"Top {int(top_n)} by total overdue"
    options_display  = [LABEL_ALL] + recommend
    options_internal = [OPTION_ALL] + recommend

    prev_sel   = st.session_state.get("od_trend_customer_select", OPTION_ALL)
    default_ix = (
        options_internal.index(prev_sel)
        if prev_sel in options_internal else 0
    )

    if recommend:
        selected_display = st.selectbox(
            f"Select customer ({len(recommend)} found)",
            options=options_display,
            index=default_ix,
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

    if selected_internal == OPTION_ALL:
        sel_customers = all_customers[:int(top_n)]
    else:
        sel_customers = [selected_internal]

    if not sel_customers:
        st.info("No customers to display.")
        return {}

    grp_sel    = grp[grp["CustomerName"].isin(sel_customers)]
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

        color   = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        y_plot  = pivot_plot.loc[cust].tolist()
        y_raw   = pivot_raw.loc[cust].tolist()
        cls     = cust_meta.get(cust, {}).get("classification", "")

        # ------------------------------------------------------------------
        # customdata per point:
        #   [0] = previous period raw amount (period ก่อนหน้า)
        #   [1] = current period raw amount (หนี้ใหม่ period นี้)
        #   [2] = classification
        #   [3] = previous period label
        # ------------------------------------------------------------------
        n = len(y_raw)
        prev_amounts = [0.0] + y_raw[:-1]          # shift right by 1
        prev_labels  = ["—"] + all_periods[:-1]    # shift period label right by 1

        customdata = list(zip(
            prev_amounts,
            y_raw,
            [cls] * n,
            prev_labels,
        ))

        if trend_mode == "Per-Period":
            hover = (
                f"<b>{cust}</b><br>"
                "Period           : %{x}<br>"
                "Overdue          : <b>%{y:,.2f} THB</b><br>"
                "Prev Period Amt  : %{customdata[0]:,.2f} THB  (%{customdata[3]})<br>"
                "This Period Amt  : %{customdata[1]:,.2f} THB<br>"
                "Classification   : %{customdata[2]}<br>"
                "<extra></extra>"
            )
        else:
            # Cumulative: y_plot = cumsum, y_raw = new this period
            hover = (
                f"<b>{cust}</b><br>"
                "Period            : %{x}<br>"
                "Outstanding Total : <b>%{y:,.2f} THB</b><br>"
                "New This Period   : %{customdata[1]:,.2f} THB<br>"
                "Classification    : %{customdata[2]}<br>"
                "<extra></extra>"
            )

        fig.add_trace(go.Scatter(
            x          = all_periods,
            y          = y_plot,
            mode       = "lines+markers",
            name       = cust,
            line       = dict(width=2.5, color=color),
            marker     = dict(size=8, color=color, line=dict(width=1.5, color="white")),
            customdata = customdata,
            hovertemplate = hover,
        ))

    if len(sel_customers) > 1:
        avg_y = pivot_plot.mean(axis=0).tolist()
        fig.add_trace(go.Scatter(
            x    = all_periods,
            y    = avg_y,
            mode = "lines",
            name = "Portfolio Average",
            line = dict(width=2, dash="dot", color="rgba(0,0,0,0.45)"),
            hovertemplate=(
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