# views/view_avail.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from components import (
    apply_base_layout, kpi_card, section_header,
    dash_title_bar, FONT_COLOR, GRID_COLOR,
)

DEBT_THRESHOLD = 0.8
MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
QUARTER_MAP = {
    1: 1, 2: 1, 3: 1,
    4: 2, 5: 2, 6: 2,
    7: 3, 8: 3, 9: 3,
    10: 4, 11: 4, 12: 4,
}

PALETTE = {
    "sapphire":    "#1B4F8A", "sapphire_lt": "#3A7BD5",
    "violet":      "#5C3D8F", "violet_lt":   "#8E6DC0",
    "opal":        "#1A7A74", "opal_lt":     "#34B8B0",
    "amber":       "#B5620A", "amber_lt":    "#E8A838",
    "indigo":      "#2E3A87", "jade":        "#1A6B45",
    "crimson":     "#A01F2D", "steel":       "#3D5166",
    "safe":        "#1A7A4A", "danger":      "#A01F2D",
    "nodata":      "#8A9BB0", "threshold":   "#C0392B",
}
TYPE_COLORS = [
    PALETTE["sapphire"], PALETTE["violet"], PALETTE["opal"],
    PALETTE["amber"],    PALETTE["indigo"], PALETTE["jade"],
    PALETTE["crimson"],  PALETTE["steel"],
]
TREND_SAFE   = PALETTE["sapphire_lt"]
TREND_DANGER = PALETTE["crimson"]
BAR_BASE     = PALETTE["sapphire"]
BAR_EST      = PALETTE["amber_lt"]
BAR_EST_OVER = PALETTE["crimson"]

TYPE_LABEL_MAP = {
    "co.":   "Company",
    "CO.":   "Company",
    "ind.":  "Individual",
    "IND.":  "Individual",
    "corp.": "Corporate",
    "CORP.": "Corporate",
    "gov.":  "Government",
    "GOV.":  "Government",
    "sme":   "SME",
    "SME":   "SME",
}


# =============================================================================
# Helpers — number formatting
# =============================================================================
def _fmt(value: float, view_type: str) -> str:
    """
    input unit = Million Baht (MB)
    ออกแบบให้ scale ได้ทุก magnitude:
      Rounded : detect → floor 1 decimal → หน่วยเต็ม
      Detail  : เลขดิบ .2f → detect → หน่วยเต็ม (ไม่ scale เพราะ input = MB)
    """
    import math
    abs_val = abs(value)

    if view_type == "Rounded Number":
        if abs_val >= 1_000_000:          # >= 1 Trillion MB (ไม่น่าเกิด แต่ future-proof)
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:,.1f} Quadrillion Baht"
        if abs_val >= 1_000:              # >= 1,000 MB = 1 Billion Baht
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:,.1f} Billion Baht"
        if abs_val >= 1:                  # >= 1 MB = 1 Million Baht
            floored = math.floor(value * 10) / 10
            return f"{floored:,.1f} Million Baht"
        if abs_val >= 0.001:              # >= 0.001 MB = 1,000 Baht
            floored = math.floor(value * 1_000 * 10) / 10
            return f"{floored:,.1f} Thousand Baht"
        return f"{math.floor(value * 1_000_000 * 10) / 10:,.1f} Baht"
    else:
        # Detail: input = MB → แสดงเลขดิบ + บอกหน่วยตาม magnitude
        if abs_val >= 1_000:
            return f"{value:,.2f} Million Baht"   # ยังเป็น MB ไม่ scale
        if abs_val >= 1:
            return f"{value:,.2f} Million Baht"
        if abs_val >= 0.001:
            return f"{value * 1_000:,.2f} Thousand Baht"
        return f"{value * 1_000_000:,.2f} Baht"


def _fmt_plain(value: float, view_type: str) -> str:
    """
    Bar label สั้น — input unit = Million Baht
    Scale ได้ทุก magnitude
    """
    import math
    abs_val = abs(value)

    if view_type == "Rounded Number":
        if abs_val >= 1_000_000:
            floored = math.floor(value / 1_000_000 * 10) / 10
            return f"{floored:,.1f}Q"
        if abs_val >= 1_000:
            floored = math.floor(value / 1_000 * 10) / 10
            return f"{floored:,.1f}B"
        if abs_val >= 1:
            floored = math.floor(value * 10) / 10
            return f"{floored:,.1f}M"
        if abs_val >= 0.001:
            floored = math.floor(value * 1_000 * 10) / 10
            return f"{floored:,.1f}K"
        return f"{math.floor(value * 1_000_000 * 10) / 10:,.1f}"
    else:
        if abs_val >= 1_000:
            return f"{value:,.2f} MB"
        if abs_val >= 1:
            return f"{value:,.2f} MB"
        if abs_val >= 0.001:
            return f"{value * 1_000:,.2f} KB"
        return f"{value * 1_000_000:,.2f}"

def _fmt_pct(value: float, view_type: str) -> str:
    """Format percentage — Round: floor to int (no rounding), Detail: 2dp."""
    if view_type == "Rounded Number":
        return f"{int(value)}%"
    return f"{value:.2f}%"


def _normalize_type_label(t: str) -> str:
    return TYPE_LABEL_MAP.get(t.strip(), t.strip()) if isinstance(t, str) else t


# =============================================================================
# Public entry point
# =============================================================================
def render():
    if not st.session_state.get("data_processed", False):
        _no_data_banner()
        return

    df_raw = _prepare(st.session_state.df_avail.copy())
    st.markdown(
        dash_title_bar(
            "Credit Availability Dashboard",
            "Abalytics Dashboard - Credit Availability Exposure Monitoring",
        ),
        unsafe_allow_html=True,
    )

    df, granularity, selected_years, view_type = _render_filters(df_raw)

    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df, view_type)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Customer Credit Utilization"), unsafe_allow_html=True)
    _render_utilization_search(df)

    r2_left, r2_right = st.columns([3.2, 1.1], gap="medium")
    with r2_left:
        top_n = _render_debt_pct_bar(df, view_type)
    with r2_right:
        _render_risk_pie(df)

    st.markdown("", unsafe_allow_html=True)
    st.markdown(section_header("Debt Concentration & Average Monthly Utilization"), unsafe_allow_html=True)
    r3_left, r3_right = st.columns([1, 1.6], gap="medium")
    with r3_left:
        _render_debt_by_type(df, view_type)
    with r3_right:
        _render_trend(df, granularity, view_type)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Customer Credit Risk Preview"), unsafe_allow_html=True)
    _render_customer_table(df, top_n)
    st.markdown("", unsafe_allow_html=True)

    st.markdown(section_header("Customer Credit Utilization Trend Analysis"), unsafe_allow_html=True)
    _render_trend_analysis(df_raw, granularity, selected_years, view_type) 

# =============================================================================
# Data preparation
# =============================================================================
def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df["YEAR"] = (
        df["SOURCE_SHEET"].astype(str).str.strip()
        if "SOURCE_SHEET" in df.columns
        else df["DATE"].apply(lambda d: str(d.year) if pd.notna(d) else "Unknown")
    )
    df["MONTH"]       = df["DATE"].apply(lambda d: d.month if pd.notna(d) else None)
    df["WEEK"]        = df["DATE"].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
    df["MONTH_LABEL"] = df["MONTH"].map(MONTH_MAP)
    # QUARTER_NUM เป็น int 1-4 เสมอ (ไม่ใช่ string "Q1")
    df["QUARTER_NUM"] = df["MONTH"].map(QUARTER_MAP)
    if "TYPE" in df.columns:
        df["TYPE"] = df["TYPE"].apply(_normalize_type_label)
    return df


# =============================================================================
# Deduplication — distinct per (YEAR, MONTH, CUSTOMER_CODE), keep first
# Preserves raw df for type-level aggregation; returns deduped view for KPIs
# =============================================================================
def _dedup_for_kpi(df: pd.DataFrame) -> pd.DataFrame:
    """
    group ตาม (YEAR, MONTH) → dedup CUSTOMER_NAME keep first ทีละเดือน
    → concat กลับ (ยังมีหลายเดือน/หลาย sheet)
    → ใช้ sum ได้เลย = credit รวมทุกเดือนทุก sheet ที่ filter มา
    """
    if "CUSTOMER_NAME" in df.columns:
        dedup_col = "CUSTOMER_NAME"
    elif "CUSTOMER_CODE" in df.columns:
        dedup_col = "CUSTOMER_CODE"
    else:
        return df

    df = df.copy()
    df["_DEDUP_KEY"] = df[dedup_col].astype(str).str.strip().str.upper()

    group_keys = [k for k in ("YEAR", "MONTH") if k in df.columns]

    if not group_keys:
        result = df.drop_duplicates(subset=["_DEDUP_KEY"], keep="first")
        return result.drop(columns=["_DEDUP_KEY"])

    parts = []
    for _, grp in df.groupby(group_keys, sort=False):
        parts.append(grp.drop_duplicates(subset=["_DEDUP_KEY"], keep="first"))

    return pd.concat(parts, ignore_index=True).drop(columns=["_DEDUP_KEY"])

# =============================================================================
# Main Filter bar
# =============================================================================
def _render_filters(df_raw: pd.DataFrame):
    all_years = sorted(df_raw["YEAR"].dropna().unique().tolist())
    all_types = (
        sorted(df_raw["TYPE"].dropna().unique().tolist())
        if "TYPE" in df_raw.columns else []
    )

    st.markdown('<span style="font-size:0.75rem;font-weight:600;color:#1B4F8A;">Year (Sheet)</span>', unsafe_allow_html=True)

    pill_options = ["All"] + all_years
    _use_pills   = hasattr(st, "pills")

    if _use_pills:
        st.session_state.setdefault("_f_year_controlled", ["All"])
        current_state = st.session_state["_f_year_controlled"]
        if "f_year_pills" not in st.session_state:
            st.session_state["f_year_pills"] = current_state

        selected_pills = st.pills(
            label="Year (Sheet)", options=pill_options,
            selection_mode="multi", key="f_year_pills",
            label_visibility="collapsed",
        )
        if not selected_pills:
            selected_pills = list(current_state)

        prev, curr_years = list(current_state), [p for p in selected_pills if p != "All"]
        prev_had_all, curr_has_all = "All" in prev, "All" in selected_pills

        if curr_has_all and not prev_had_all:
            new_state = ["All"]
        elif curr_has_all and prev_had_all and curr_years:
            new_state = curr_years
        elif not curr_has_all and not curr_years:
            new_state = ["All"]
        else:
            new_state = list(selected_pills)

        if new_state != prev:
            st.session_state["_f_year_controlled"] = new_state
            st.session_state.pop("f_year_pills", None)
            st.rerun()

        selected_years = list(all_years) if "All" in new_state else [p for p in new_state if p in all_years]
    else:
        raw_sel = st.multiselect(
            "Year (Sheet)", options=all_years, default=all_years,
            key="f_year_multi", label_visibility="collapsed",
        )
        selected_years = list(all_years) if not raw_sel else raw_sel

    badge_color = "#1A7A4A" if selected_years == list(all_years) else "#1B4F8A"
    badge_years = "All" if selected_years == list(all_years) else ", ".join(str(y) for y in selected_years)
    st.markdown(
        f'<span style="background:{badge_color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.72rem;font-weight:600;">'
        f'SELECTED YEAR : {badge_years}</span>',
        unsafe_allow_html=True,
    )

    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.3, 1.1, 1.3, 1.3, 1.1, 1.1])

    with fc1:
        view_type = st.selectbox(
            "View Type",
            ["Rounded Number", "Detail Number"],
            index=0,
            key="f_view_type",
            help="Rounded Number: auto-scale (Billion / Million, no decimals)  |  Detail Number: 2 decimal places",
        )
        vt_color = "#1A7A4A" if view_type == "Rounded Number" else "#1B4F8A"
        st.markdown(
            f'<span style="background:{vt_color};color:white;padding:2px 8px;'
            f'border-radius:10px;font-size:0.70rem;font-weight:600;">'
            f'{view_type}</span>',
            unsafe_allow_html=True,
        )

    with fc2:
        granularity = st.selectbox(
            "Period", ["Monthly", "Weekly", "Daily", "Yearly"], key="f_gran",
        )

    df_scope     = df_raw[df_raw["YEAR"].isin(selected_years)]
    avail_months = sorted(df_scope["MONTH"].dropna().unique().tolist())
    month_opts   = ["All"] + [f"{m:02d} — {MONTH_MAP.get(m, '')}" for m in avail_months]
    month_to_int = {f"{m:02d} — {MONTH_MAP.get(m, '')}": m for m in avail_months}

    with fc3:
        sel_month_lbl = st.selectbox(
            "Month", month_opts, key="f_month",
            disabled=(granularity == "Yearly"),
        )
        sel_month = None if sel_month_lbl == "All" else month_to_int.get(sel_month_lbl)

    with fc4:
        sel_type = st.selectbox("Product Type", ["All"] + all_types, key="f_type")
    with fc5:
        debt_filter = st.selectbox("Debt Risk", ["All", ">= 80%", "< 80%"], key="f_debt")
    with fc6:
        est_filter  = st.selectbox("Est. Debt",  ["All", ">= 80%", "< 80%"], key="f_est")

    df = df_raw[df_raw["YEAR"].isin(selected_years)].copy()
    if sel_month:
        df = df[df["MONTH"] == sel_month]
    if sel_type != "All" and "TYPE" in df.columns:
        df = df[df["TYPE"] == sel_type]
    if "CURRENT_DEBT_MILLION_THB_PERCENT" in df.columns:
        if debt_filter == ">= 80%":
            df = df[df["CURRENT_DEBT_MILLION_THB_PERCENT"] >= DEBT_THRESHOLD]
        elif debt_filter == "< 80%":
            df = df[df["CURRENT_DEBT_MILLION_THB_PERCENT"] < DEBT_THRESHOLD]
    if "EST_DEBT" in df.columns:
        if est_filter == ">= 80%":
            df = df[df["EST_DEBT"] >= DEBT_THRESHOLD]
        elif est_filter == "< 80%":
            df = df[df["EST_DEBT"] < DEBT_THRESHOLD]

    return df, granularity, selected_years, view_type


# =============================================================================
# Row 1 — KPI cards
# Uses _dedup_for_kpi() to prevent double-counting from multi-TYPE rows
# =============================================================================
def _render_kpi_row(df: pd.DataFrame, view_type: str):
    df_kpi = _dedup_for_kpi(df)

    total_customers = (
        int(df_kpi["CUSTOMER_NAME"].nunique())
        if "CUSTOMER_NAME" in df_kpi.columns else 0
    )
    total_credit = df_kpi["CLEAN_CREDIT_MB"].sum()          if "CLEAN_CREDIT_MB" in df_kpi.columns else 0.0
    total_debt   = df_kpi["CURRENT_DEBT_MILLION_THB"].sum() if "CURRENT_DEBT_MILLION_THB" in df_kpi.columns else 0.0
    avg_debt_pct = (
        df_kpi["CURRENT_DEBT_MILLION_THB_PERCENT"].mean() * 100
        if "CURRENT_DEBT_MILLION_THB_PERCENT" in df_kpi.columns else 0.0
    )

    dedup_col = "CUSTOMER_NAME" if "CUSTOMER_NAME" in df_kpi.columns else "CUSTOMER_CODE"
    # snap_kpi  = (
    #     df_kpi.sort_values("DATE", ascending=False).drop_duplicates(subset=[dedup_col])
    #     if "DATE" in df_kpi.columns
    #     else df_kpi.drop_duplicates(subset=[dedup_col])
    # )
    snap_kpi = (
    df_kpi.sort_values("DATE", ascending=False)
    .drop_duplicates(subset=[dedup_col])  # ← dedup_col อาจเป็น CUSTOMER_NAME อยู่แล้ว
    )
    high_risk_count = int(
        (snap_kpi["CURRENT_DEBT_MILLION_THB_PERCENT"] >= DEBT_THRESHOLD).sum()
    ) if "CURRENT_DEBT_MILLION_THB_PERCENT" in snap_kpi.columns else 0
    est_exceed_count = int(
        (snap_kpi["EST_DEBT"] >= DEBT_THRESHOLD).sum()
    ) if "EST_DEBT" in snap_kpi.columns else 0

    avg_pct_str = _fmt_pct(avg_debt_pct, view_type)

    cards = [
        ("Total Customers",    f"{total_customers:,}",          "Unique customers",              "info"),
        ("Total Clean Credit", _fmt(total_credit, view_type),   "Net credit limit",              "info"),
        ("Total Current Debt", _fmt(total_debt, view_type),     f"Avg utilization: {avg_pct_str}", "info"),
        ("High Risk",          f"{high_risk_count:,}",          "Debt >= 80% of limit",
         "danger" if high_risk_count > 0 else "safe"),
        ("Est. Will Exceed",   f"{est_exceed_count:,}",         "Forecast risk count",
         "warning" if est_exceed_count > 0 else "safe"),
    ]

    # outer div บังคับให้ทุก column ใน row นี้มี height เท่ากันผ่าน align-items:stretch
    cols = st.columns(5, gap="small")
    st.markdown(
        '<style>'
        '[data-testid="stHorizontalBlock"]:has(.kpi-row-anchor){'
        'align-items:stretch;}'
        '</style>'
        '<span class="kpi-row-anchor" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(kpi_card(label, value, sub, variant), unsafe_allow_html=True)


# =============================================================================
# Utilization search — shared state for bar + pie
# =============================================================================
def _render_utilization_search(df: pd.DataFrame):
    if "CUSTOMER_NAME" not in df.columns:
        st.session_state["_util_filtered_names"]    = []
        st.session_state["_util_selected_customer"] = None
        return

    snap = (
        df.sort_values("DATE", ascending=False).drop_duplicates(subset=["CUSTOMER_NAME"])
        if "DATE" in df.columns
        else df.drop_duplicates(subset=["CUSTOMER_NAME"])
    )
    all_names = sorted(snap["CUSTOMER_NAME"].dropna().unique().tolist())

    search_col, _ = st.columns([2.5, 4])
    with search_col:
        st.markdown('<span style="font-size:0.75rem;font-weight:600;color:#1B4F8A;">Customer Search</span>', unsafe_allow_html=True)
        options  = ["All customers"] + all_names
        prev_sel = st.session_state.get("_util_selected_customer", "All customers")
        default_ix = options.index(prev_sel) if prev_sel in options else 0
        selected = st.selectbox(
            "Customer Search (Utilization)", options=options,
            index=default_ix, key="utilization_search",
            label_visibility="collapsed",
        )

    st.session_state["_util_selected_customer"] = selected
    st.session_state["_util_filtered_names"] = (
        all_names if selected == "All customers" else [selected]
    )


# =============================================================================
# Row 2 left — Current Debt % horizontal stacked bar
# =============================================================================
def _render_debt_pct_bar(df: pd.DataFrame, view_type: str) -> int:
    needed = {"CUSTOMER_NAME", "CURRENT_DEBT_MILLION_THB_PERCENT"}
    if not needed.issubset(df.columns):
        st.info("Insufficient data.")
        return 10

    distinct_n = df["CUSTOMER_CODE"].nunique() if "CUSTOMER_CODE" in df.columns else df["CUSTOMER_NAME"].nunique()
    max_n = max(distinct_n, 5)

    ctrl1, ctrl2, ctrl3, _ = st.columns([1.4, 2.2, 1.6, 1.2])
    with ctrl1:
        show_est = st.toggle("Show Est. Future Diff", value=False, key="show_est")
    with ctrl2:
        top_n_options = sorted(set(list(range(5, max_n + 1)) + [10]))
        default_top_n = 10 if 10 in top_n_options else top_n_options[0]
        top_n = st.select_slider("Top N", options=top_n_options, value=default_top_n, key="top_n")
    with ctrl3:
        sort_dir = st.selectbox("Sort", ["High to Low", "Low to High"], index=0, key="avail_sort_dir")

    snap_full = (
        df.sort_values("DATE", ascending=False).drop_duplicates(subset=["CUSTOMER_NAME"])
        if "DATE" in df.columns
        else df.drop_duplicates(subset=["CUSTOMER_NAME"])
    ).copy()
    snap_full["DEBT_PCT_DISP"] = snap_full["CURRENT_DEBT_MILLION_THB_PERCENT"] * 100

    filtered_names = st.session_state.get("_util_filtered_names")
    if filtered_names is not None:
        snap_full = snap_full[snap_full["CUSTOMER_NAME"].isin(filtered_names)]
    if snap_full.empty:
        st.info("No customer matched the search.")
        return top_n

    pool = snap_full[snap_full["DEBT_PCT_DISP"] > 0].copy()
    if pool.empty:
        pool = snap_full.copy()

    snap = (
        pool.sort_values("DEBT_PCT_DISP", ascending=(sort_dir == "Low to High"))
        .head(min(top_n, len(pool)))
        .reset_index(drop=True)
    )

    # text font size — slightly larger for readability
    bar_text_size = 10

    base_colors = [PALETTE["danger"] if v >= 80 else BAR_BASE for v in snap["DEBT_PCT_DISP"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=snap["CUSTOMER_NAME"],
        x=snap["DEBT_PCT_DISP"],
        orientation="h",
        name="Current Debt %",
        marker_color=base_colors,
        text=[_fmt_pct(v, view_type) for v in snap["DEBT_PCT_DISP"]],
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(size=bar_text_size, color="white"),
        hovertemplate="%{y}<br>Current Debt: %{x:.2f}%<extra></extra>",
    ))

    if show_est and "EST_DEBT" in snap.columns:
        snap = snap.copy()
        snap["EST_PCT_DISP"] = snap["EST_DEBT"] * 100
        snap["DIFF"] = (snap["EST_PCT_DISP"] - snap["DEBT_PCT_DISP"]).clip(lower=0)
        diff_colors = [
            BAR_EST_OVER if (r["DEBT_PCT_DISP"] + r["DIFF"]) >= 80 else BAR_EST
            for _, r in snap.iterrows()
        ]
        diff_labels = [
            (f"+{int(v)}%" if view_type == "Rounded Number" else f"+{v:.2f}%") if v > 0 else ""
            for v in snap["DIFF"]
        ]
        fig.add_trace(go.Bar(
            y=snap["CUSTOMER_NAME"],
            x=snap["DIFF"],
            orientation="h",
            name="Est. Future Diff",
            marker_color=diff_colors,
            text=diff_labels,
            textposition="inside",
            insidetextanchor="start",
            textfont=dict(size=bar_text_size, color="white"),
            hovertemplate="%{y}<br>Est. Future Diff: +%{x:.2f}%<extra></extra>",
            showlegend=False,
        ))
        fig.add_trace(go.Bar(
            y=[None], x=[None], orientation="h",
            name="Est. Future Diff", marker_color=BAR_EST, showlegend=True,
        ))

    fig.update_layout(barmode="stack")
    fig.add_vline(
        x=80, line_dash="dash", line_color=PALETTE["threshold"], line_width=1.2,
        annotation_text="80% Threshold",
        annotation_font=dict(size=8, color=PALETTE["threshold"]),
        annotation_position="top",
    )
    apply_base_layout(fig, {
        "height": max(220, len(snap) * 28),
        "margin": dict(l=0, r=40, t=10, b=4),
        "xaxis": dict(
            title="Current Debt Utilization (%)", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR, zeroline=False,
            color=FONT_COLOR, tickfont=dict(size=9),
            range=[0, max(120, float(snap["DEBT_PCT_DISP"].max()) * 1.2)],
        ),
        "yaxis": dict(
            title="Customer",
            showgrid=False, color=FONT_COLOR, tickfont=dict(size=9),
            categoryorder="total ascending",
        ),
        "showlegend": show_est,
        "legend": dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=9),
        ),
    })
    st.plotly_chart(fig, use_container_width=True)
    return top_n


# =============================================================================
# Row 2 right — Credit Risk Distribution Pie
# =============================================================================
def _render_risk_pie(df: pd.DataFrame):
    st.markdown('<span style="font-size:0.80rem;font-weight:600;color:#3a4a60;">Credit Risk Distribution</span>', unsafe_allow_html=True)
    if "CURRENT_DEBT_MILLION_THB_PERCENT" not in df.columns or "CUSTOMER_CODE" not in df.columns:
        st.info("No data.")
        return

    snap = (
        df.sort_values("DATE", ascending=False).drop_duplicates(subset=["CUSTOMER_NAME"])
        if "DATE" in df.columns
        else df.drop_duplicates(subset=["CUSTOMER_NAME"])
    ).copy()

    filtered_names = st.session_state.get("_util_filtered_names")
    if filtered_names is not None and "CUSTOMER_NAME" in snap.columns:
        snap = snap[snap["CUSTOMER_NAME"].isin(filtered_names)]
    if snap.empty:
        st.info("No customer matched the search.")
        return

    safe_n   = int(((snap["CURRENT_DEBT_MILLION_THB_PERCENT"] > 0) & (snap["CURRENT_DEBT_MILLION_THB_PERCENT"] < DEBT_THRESHOLD)).sum())
    danger_n = int((snap["CURRENT_DEBT_MILLION_THB_PERCENT"] >= DEBT_THRESHOLD).sum())
    nodata_n = int(snap["CURRENT_DEBT_MILLION_THB_PERCENT"].isna().sum())

    labels, values, colors = [], [], []
    for lbl, val, color in [
        ("Safe (< 80%)",       safe_n,   PALETTE["safe"]),
        ("High Risk (>= 80%)", danger_n, PALETTE["danger"]),
        ("No Data",            nodata_n, PALETTE["nodata"]),
    ]:
        if val > 0:
            labels.append(lbl); values.append(val); colors.append(color)

    if not labels:
        st.info("No data.")
        return

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent", textfont=dict(size=10),
        hovertemplate="%{label}: %{value} customers (%{percent})<extra></extra>",
        showlegend=False,
    ))
    apply_base_layout(fig, {"height": 200, "margin": dict(l=8, r=8, t=8, b=8), "showlegend": False})
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 3 left — Debt by Product Type
# view_type controls number format on bar labels
# =============================================================================
def _render_debt_by_type(df: pd.DataFrame, view_type: str):
    st.markdown(
        '<span style="font-size:0.80rem;font-weight:600;color:#3a4a60;">Debt by Product Type</span>',
        unsafe_allow_html=True,
    )
    if "TYPE" not in df.columns or "CURRENT_DEBT_MILLION_THB" not in df.columns:
        st.info("No product type data available.")
        return

    has_cust = "CUSTOMER_CODE" in df.columns
    agg_dict = {"CURRENT_DEBT_MILLION_THB": ("CURRENT_DEBT_MILLION_THB", "sum")}
    if has_cust:
        agg_dict["CUSTOMER_COUNT"] = ("CUSTOMER_CODE", "nunique")

    by_type = (
        df.groupby("TYPE", as_index=False)
        .agg(**agg_dict)
        .rename(columns={"CURRENT_DEBT_MILLION_THB": "TOTAL"})
        .sort_values("TOTAL", ascending=False)
        .reset_index(drop=True)
    )
    total_all      = by_type["TOTAL"].sum()
    by_type["PCT"] = (by_type["TOTAL"] / total_all * 100) if total_all > 0 else 0.0

    fig = go.Figure()
    for i, row in by_type.iterrows():
        color       = TYPE_COLORS[i % len(TYPE_COLORS)]
        cust_count  = int(row["CUSTOMER_COUNT"]) if has_cust else None
        pct_str     = _fmt_pct(float(row["PCT"]), view_type)
        bar_label   = (
            f"{_fmt_plain(row['TOTAL'], view_type)} ({cust_count} companies)"
            if has_cust
            else _fmt_plain(row["TOTAL"], view_type)
        )
        hover_lines = [
            f"<b>{row['TYPE']}</b>",
            "──────────────────",
            f"Total Debt  : {_fmt(row['TOTAL'], view_type)}",
            f"Share       : {pct_str}",
        ]
        if has_cust:
            hover_lines.append(f"Customers   : {cust_count:,} companies")

        fig.add_trace(go.Bar(
            x=[row["TYPE"]], y=[row["TOTAL"]],
            name=f"{row['TYPE']} ({pct_str})",
            marker_color=color,
            text=[bar_label],
            textposition="outside", cliponaxis=False,
            textfont=dict(size=15, color=FONT_COLOR, family="Inter, sans-serif"),
            hovertemplate="<br>".join(hover_lines) + "<extra></extra>",
        ))

    apply_base_layout(fig, {
        "height": 300,         
        "margin": dict(l=0, r=8, t=24, b=4),  
        "barmode": "group",
        "xaxis": dict(
            title="Product Type",
            showgrid=False, color=FONT_COLOR,
            tickfont=dict(size=9, family="Inter, sans-serif"),
        ),
        "yaxis": dict(
            title="Total Current Debt (Million Baht)",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, tickfont=dict(size=9),
        ),
        "showlegend": True,
        "legend": dict(
            orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02,
            font=dict(size=8), bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#d0dae6", borderwidth=1,
        ),
        "hoverlabel": dict(
            bgcolor="white", bordercolor="#d0dae6",
            font=dict(size=11, color="#1B2A3B"), align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 3 right — Avg Debt % Trend
# =============================================================================
def _render_trend(df: pd.DataFrame, granularity: str, view_type: str):
    st.markdown(
        f'<span style="font-size:0.80rem;font-weight:600;color:#3a4a60;">'
        f'Avg Debt % — {granularity} View</span>',
        unsafe_allow_html=True,
    )
    if "CURRENT_DEBT_MILLION_THB_PERCENT" not in df.columns:
        st.info("No debt percent data.")
        return

    if granularity == "Yearly":
        group_cols, sort_cols = ["YEAR"], ["YEAR"]
        label_fn = lambda r: str(r["YEAR"])
    elif granularity == "Monthly":
        group_cols, sort_cols = ["YEAR", "MONTH", "MONTH_LABEL"], ["YEAR", "MONTH"]
        label_fn = lambda r: f"{r['YEAR']}-{r['MONTH_LABEL']}"
    elif granularity == "Weekly":
        group_cols, sort_cols = ["YEAR", "WEEK"], ["YEAR", "WEEK"]
        label_fn = lambda r: f"{r['YEAR']}-W{int(r.get('WEEK', 0)):02d}"
    else:
        group_cols, sort_cols = ["DATE"], ["DATE"]
        label_fn = lambda r: str(r["DATE"])

    trend = (
        df.groupby(group_cols, as_index=False)["CURRENT_DEBT_MILLION_THB_PERCENT"]
        .mean()
        .rename(columns={"CURRENT_DEBT_MILLION_THB_PERCENT": "AVG_PCT"})
        .sort_values(sort_cols)
    )
    if "MONTH_LABEL" not in trend.columns and "MONTH" in trend.columns:
        trend["MONTH_LABEL"] = trend["MONTH"].map(MONTH_MAP)
    trend["X"]            = trend.apply(label_fn, axis=1)
    trend["AVG_PCT_DISP"] = trend["AVG_PCT"] * 100

    bar_colors = [TREND_DANGER if v >= 80 else TREND_SAFE for v in trend["AVG_PCT_DISP"]]
    tick_fmt   = ".0f" if view_type == "Rounded Number" else ".2f"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=trend["X"], y=trend["AVG_PCT_DISP"],
        marker_color=bar_colors,
        text=[_fmt_pct(v, view_type) for v in trend["AVG_PCT_DISP"]],
        textposition="outside", cliponaxis=False,
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate="%{x}<br>Avg Debt Utilization: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(
        y=80, line_dash="dash", line_color=PALETTE["threshold"], line_width=1.2,
        annotation_text="80% Threshold",
        annotation_font=dict(size=8, color=PALETTE["threshold"]),
        annotation_position="top left",
    )
    max_y = max(trend["AVG_PCT_DISP"].max() * 1.15, 90) if not trend.empty else 100
    apply_base_layout(fig, {
        "height": 280,
        "margin": dict(l=0, r=8, t=4, b=4),
        "xaxis": dict(
            title=f"Period ({granularity})",
            showgrid=False, color=FONT_COLOR, tickangle=-35, tickfont=dict(size=8),
        ),
        "yaxis": dict(
            title="Average Debt Utilization (%)", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, range=[0, max_y], tickformat=tick_fmt,
        ),
        "showlegend": False,
    })
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 4 — Customer Credit Risk Preview table
# =============================================================================
def _render_customer_table(df: pd.DataFrame, top_n: int = 10):
    c_mode, _ = st.columns([2, 6])
    with c_mode:
        mode = st.radio(
            "View", ["Top Clean Credit", "Top Risk Customers"],
            horizontal=True, key="table_mode",
        )
    desired_cols = [
        "CUSTOMER_NAME", "TYPE", "CLEAN_CREDIT_MB",
        "CURRENT_DEBT_MILLION_THB", "CURRENT_DEBT_MILLION_THB_PERCENT",
    ]
    avail_cols = [c for c in desired_cols if c in df.columns]
    dedup_key  = ["CUSTOMER_NAME"] if "CUSTOMER_NAME" in avail_cols else None

    if mode == "Top Clean Credit" and "CLEAN_CREDIT_MB" in df.columns:
        tbl = (
            df[avail_cols].drop_duplicates(subset=dedup_key)
            .sort_values("CLEAN_CREDIT_MB", ascending=False)
            .head(top_n).reset_index(drop=True)
        )
    elif mode == "Top Risk Customers" and "CURRENT_DEBT_MILLION_THB_PERCENT" in df.columns:
        tbl = (
            df[avail_cols].drop_duplicates(subset=dedup_key)
            .sort_values("CURRENT_DEBT_MILLION_THB_PERCENT", ascending=False)
            .head(top_n).reset_index(drop=True)
        )
    else:
        st.info("No data.")
        return

    st.dataframe(
        tbl,
        column_config={
            "CUSTOMER_NAME":                     st.column_config.TextColumn("Customer Name", width="large"),
            "TYPE":                              st.column_config.TextColumn("Product Type", width="small"),
            "CLEAN_CREDIT_MB":                   st.column_config.NumberColumn("Clean Credit (MB)", format="%.2f", width="medium"),
            "CURRENT_DEBT_MILLION_THB":          st.column_config.NumberColumn("Current Debt (MB)", format="%.2f", width="medium"),
            "CURRENT_DEBT_MILLION_THB_PERCENT":  st.column_config.NumberColumn("Debt Utilization %", format="%.2f", width="small"),
        },
        use_container_width=True, height=320, hide_index=True,
    )


# =============================================================================
# Row 5 — Customer Trend Analysis
# Added: Quarter granularity
# =============================================================================
def _render_trend_analysis(df_raw: pd.DataFrame, main_granularity: str,
                           selected_years: list, view_type: str):
    required = {"CUSTOMER_NAME", "CURRENT_DEBT_MILLION_THB_PERCENT", "DATE"}
    if not required.issubset(df_raw.columns):
        st.info("Required columns: CUSTOMER_NAME, CURRENT_DEBT_MILLION_THB_PERCENT, DATE")
        return

    df_scoped = df_raw[df_raw["YEAR"].isin(selected_years)].copy()

    if "CUSTOMER_CODE" in df_scoped.columns:
        name_map = (
            df_scoped.dropna(subset=["CUSTOMER_CODE", "CUSTOMER_NAME"])
            .sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE"])[["CUSTOMER_CODE", "CUSTOMER_NAME"]]
            .set_index("CUSTOMER_CODE")["CUSTOMER_NAME"]
            .to_dict()
        )
        valid_codes = (
            df_scoped
            .dropna(subset=["DATE", "CURRENT_DEBT_MILLION_THB_PERCENT", "CUSTOMER_CODE"])
            ["CUSTOMER_CODE"].unique().tolist()
        )
        all_names = sorted(
            set(name_map[c] for c in valid_codes if c in name_map),
            key=lambda x: x.lower(),
        )
    else:
        all_names = sorted(
            df_scoped
            .dropna(subset=["DATE", "CURRENT_DEBT_MILLION_THB_PERCENT", "CUSTOMER_NAME"])
            ["CUSTOMER_NAME"].unique().tolist(),
            key=lambda x: x.lower(),
        )

    if not all_names:
        st.info("No customer data for the selected year(s).")
        return

    # --- Filter controls ---
    lf1, lf2, lf_space, lf3 = st.columns([2.5, 1.4, 1.6, 1.5])

    with lf1:
        st.markdown(
            '<span style="font-size:0.75rem;font-weight:600;color:#1B4F8A;">Customer Search</span>',
            unsafe_allow_html=True,
        )
        search_query = st.text_input(
            "Customer Search",
            placeholder="Type name or Customer Code...",
            key="trend_search",
            label_visibility="collapsed",
        ).strip()

    with lf2:
        st.markdown(
            '<span style="font-size:0.75rem;font-weight:600;color:#1B4F8A;">Period (Trend)</span>',
            unsafe_allow_html=True,
        )
        gran_options  = ["Monthly", "Quarterly", "Weekly", "Daily", "Yearly"]
        default_index = gran_options.index(main_granularity) if main_granularity in gran_options else 0
        local_gran = st.selectbox(
            "Period (Trend)", gran_options,
            index=default_index, key="trend_local_gran",
            label_visibility="collapsed",
        )

    with lf3:
        st.markdown(
            '<span style="font-size:0.75rem;font-weight:600;color:#1B4F8A;">Est. Debt %</span>',
            unsafe_allow_html=True,
        )
        show_est_line = st.toggle(
            "Show Est. Debt %",
            value=False,
            key="trend_show_est",
            label_visibility="collapsed",
            help="Enable to overlay Estimated Debt % line on the chart.",
        )
        badge_color = "#1A7A4A" if show_est_line else "#8A9BB0"
        badge_text  = "ON — visible on chart" if show_est_line else "OFF — hidden"
        st.markdown(
            f'<span style="background:{badge_color};color:white;padding:2px 8px;'
            f'border-radius:10px;font-size:0.70rem;font-weight:600;">{badge_text}</span>',
            unsafe_allow_html=True,
        )

    # --- Search filter ---
    if search_query:
        q = search_query.lower()
        filtered_names = [n for n in all_names if q in n.lower()]
        if "CUSTOMER_CODE" in df_scoped.columns:
            code_hits = (
                df_scoped[
                    df_scoped["CUSTOMER_CODE"].astype(str).str.lower().str.contains(q, na=False)
                ]["CUSTOMER_NAME"].dropna().unique().tolist()
            )
            filtered_names = list(dict.fromkeys(filtered_names + code_hits))
    else:
        filtered_names = all_names

    if not filtered_names:
        st.warning(f"No customer matched '{search_query}'.")
        return

    st.markdown(
        f'<span style="font-size:0.72rem;color:#555;">'
        f'{len(filtered_names)} result(s)'
        + (f" — search: {search_query}" if search_query else "")
        + "</span>",
        unsafe_allow_html=True,
    )

    prev_key      = st.session_state.get("trend_customer_select")
    default_ix    = filtered_names.index(prev_key) if prev_key and prev_key in filtered_names else 0
    selected_customer = st.selectbox(
        "Select Customer", filtered_names, index=default_ix, key="trend_customer_select",
    )

    # --- Prepare customer data ---
    cdf = (
        df_scoped[df_scoped["CUSTOMER_NAME"] == selected_customer]
        .dropna(subset=["DATE", "CURRENT_DEBT_MILLION_THB_PERCENT"])
        .sort_values("DATE").copy()
    )
    if cdf.empty:
        st.info("No trend data for this customer in the selected year(s).")
        return

    cdf["UTIL_PCT"]    = cdf["CURRENT_DEBT_MILLION_THB_PERCENT"] * 100
    cdf["YEAR_COL"]    = cdf["DATE"].apply(lambda d: str(d.year) if pd.notna(d) else "Unknown")
    cdf["MONTH_NUM"]   = cdf["DATE"].apply(lambda d: d.month if pd.notna(d) else None)
    cdf["WEEK_NUM"]    = cdf["DATE"].apply(
        lambda d: int(d.isocalendar()[1]) if pd.notna(d) else None
    )
    cdf["MONTH_LABEL"] = cdf["MONTH_NUM"].map(MONTH_MAP)
    # QUARTER_NUM: int 1-4 derived from month, coerced defensively
    cdf["QUARTER_NUM"] = (
        pd.to_numeric(cdf["MONTH_NUM"].map(QUARTER_MAP), errors="coerce")
        .fillna(0).astype(int)
    )

    debt_col   = "CURRENT_DEBT_MILLION_THB"
    credit_col = "CLEAN_CREDIT_MB"
    extra_agg  = {
        col: (col, "mean")
        for col in [debt_col, credit_col]
        if col in cdf.columns
    }

    def _group(frame, keys, sort_keys, label_fn):
        agg_dict = {"UTIL_PCT": ("UTIL_PCT", "mean"), **extra_agg}
        g = frame.groupby(keys, as_index=False).agg(**agg_dict)
        g = g.sort_values(sort_keys).reset_index(drop=True)
        g["X"] = g.apply(label_fn, axis=1)
        return g

    # --- Grouping by granularity ---
    if local_gran == "Yearly":
        grp = _group(
            cdf, ["YEAR_COL"], ["YEAR_COL"],
            lambda r: str(r["YEAR_COL"]),
        )
    elif local_gran == "Quarterly":
        cdf["QUARTER_NUM"] = (
            pd.to_numeric(cdf["QUARTER_NUM"], errors="coerce").fillna(0).astype(int)
        )
        grp = _group(
            cdf, ["YEAR_COL", "QUARTER_NUM"], ["YEAR_COL", "QUARTER_NUM"],
            lambda r: f"{r['YEAR_COL']}-Q{int(r['QUARTER_NUM'])}",
        )
    elif local_gran == "Monthly":
        grp = _group(
            cdf, ["YEAR_COL", "MONTH_NUM", "MONTH_LABEL"], ["YEAR_COL", "MONTH_NUM"],
            lambda r: f"{r['YEAR_COL']}-{r['MONTH_LABEL']}",
        )
    elif local_gran == "Weekly":
        cdf["WEEK_NUM"] = (
            pd.to_numeric(cdf["WEEK_NUM"], errors="coerce").fillna(0).astype(int)
        )
        grp = _group(
            cdf, ["YEAR_COL", "WEEK_NUM"], ["YEAR_COL", "WEEK_NUM"],
            lambda r: f"{r['YEAR_COL']}-W{int(r['WEEK_NUM']):02d}",
        )
    else:  # Daily
        grp = _group(
            cdf, ["DATE"], ["DATE"],
            lambda r: str(r["DATE"]),
        )

    if grp.empty:
        st.info("No data for this granularity.")
        return

    # --- Mini KPI blocks ---
    latest_util   = float(grp["UTIL_PCT"].iloc[-1])
    avg_util      = float(grp["UTIL_PCT"].mean())
    period_change = (
        float(grp["UTIL_PCT"].iloc[-1] - grp["UTIL_PCT"].iloc[-2])
        if len(grp) >= 2 else 0.0
    )
    risk_color = "#A01F2D" if latest_util >= 80 else ("#B5620A" if latest_util >= 50 else "#1A7A4A")
    chg_color  = "#A01F2D" if period_change > 0 else "#1A7A4A"
    chg_arrow  = "▲" if period_change > 0 else "▼"

    kpi_blocks = [
        ("Utilization (Latest)",   _fmt_pct(latest_util, view_type),                          risk_color),
        (f"Change ({local_gran})", f"{chg_arrow} {_fmt_pct(abs(period_change), view_type)}",  chg_color),
        ("Avg Utilization",        _fmt_pct(avg_util, view_type),                             FONT_COLOR),
    ]

    raw_cust = (
        df_scoped[df_scoped["CUSTOMER_NAME"] == selected_customer]
        .dropna(subset=["DATE"]).sort_values("DATE")
    )
    if not raw_cust.empty:
        lr = raw_cust.iloc[-1]
        for col_name, label in [(debt_col, "Current Debt"), (credit_col, "Credit Limit")]:
            if col_name in df_scoped.columns:
                v = lr.get(col_name)
                if pd.notna(v):
                    kpi_blocks.append((label, _fmt(float(v), view_type), FONT_COLOR))

    card_style = (
        "background:#f0f4fa;border-radius:8px;padding:8px 16px;"
        "min-width:100px;flex:1 1 auto;"
    )
    kpi_html = "".join(
        f'<div style="{card_style}">'
        f'<div style="font-size:0.68rem;color:#666;font-weight:600;">{lbl}</div>'
        f'<div style="font-size:1.1rem;font-weight:700;color:{col};">{val}</div>'
        f'</div>'
        for lbl, val, col in kpi_blocks
    )
    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">{kpi_html}</div>',
        unsafe_allow_html=True,
    )

    # --- Chart traces ---
    has_debt   = debt_col   in grp.columns
    has_credit = credit_col in grp.columns

    customdata = [
        [
            grp[debt_col].iloc[i]   if has_debt   else None,
            grp[credit_col].iloc[i] if has_credit else None,
        ]
        for i in range(len(grp))
    ]

    hover_util = (
        "%{x}<br>──────────────────<br>"
        "Utilization : %{y:.1f}%<br>"
        "Clean Credit : %{customdata[1]:,.1f} MB<br>"
        "Current Debt : %{customdata[0]:,.1f} MB"
        "<extra></extra>"
        if has_debt and has_credit else
        "%{x}<br>Utilization : %{y:.1f}%<extra></extra>"
    )

    point_colors = [
        PALETTE["danger"]       if v >= 80
        else (PALETTE["amber"]  if v >= 50 else PALETTE["sapphire_lt"])
        for v in grp["UTIL_PCT"]
    ]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=grp["X"], y=grp["UTIL_PCT"],
        mode="none", fill="tozeroy",
        fillcolor="rgba(58,123,213,0.08)",
        showlegend=False, hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=grp["X"], y=grp["UTIL_PCT"],
        mode="lines+markers",
        name="Utilization %",
        line=dict(color=PALETTE["sapphire_lt"], width=2),
        marker=dict(color=point_colors, size=7, line=dict(color="white", width=1.5)),
        customdata=customdata,
        hovertemplate=hover_util,
    ))

    # --- Est. Debt overlay ---
    if show_est_line and "EST_DEBT" in df_scoped.columns:
        est_df = (
            df_scoped[df_scoped["CUSTOMER_NAME"] == selected_customer]
            .dropna(subset=["DATE", "EST_DEBT"]).copy()
        )
        if not est_df.empty:
            est_df["EST_PCT"]     = est_df["EST_DEBT"] * 100
            est_df["YEAR_COL"]    = est_df["DATE"].apply(lambda d: str(d.year))
            est_df["MONTH_NUM"]   = est_df["DATE"].apply(lambda d: d.month)
            est_df["MONTH_LABEL"] = est_df["MONTH_NUM"].map(MONTH_MAP)
            est_df["WEEK_NUM"]    = est_df["DATE"].apply(
                lambda d: int(d.isocalendar()[1])
            )
            est_df["QUARTER_NUM"] = (
                pd.to_numeric(est_df["MONTH_NUM"].map(QUARTER_MAP), errors="coerce")
                .fillna(0).astype(int)
            )

            if local_gran == "Yearly":
                egrp = est_df.groupby(["YEAR_COL"], as_index=False)["EST_PCT"].mean()
                egrp["X"] = egrp["YEAR_COL"].astype(str)
                esort = ["YEAR_COL"]
            elif local_gran == "Quarterly":
                egrp = est_df.groupby(
                    ["YEAR_COL", "QUARTER_NUM"], as_index=False
                )["EST_PCT"].mean()
                egrp["X"] = egrp.apply(
                    lambda r: f"{r['YEAR_COL']}-Q{int(r['QUARTER_NUM'])}", axis=1
                )
                esort = ["YEAR_COL", "QUARTER_NUM"]
            elif local_gran == "Monthly":
                egrp = est_df.groupby(
                    ["YEAR_COL", "MONTH_NUM", "MONTH_LABEL"], as_index=False
                )["EST_PCT"].mean()
                egrp["X"] = egrp.apply(
                    lambda r: f"{r['YEAR_COL']}-{r['MONTH_LABEL']}", axis=1
                )
                esort = ["YEAR_COL", "MONTH_NUM"]
            elif local_gran == "Weekly":
                egrp = est_df.groupby(
                    ["YEAR_COL", "WEEK_NUM"], as_index=False
                )["EST_PCT"].mean()
                egrp["X"] = egrp.apply(
                    lambda r: f"{r['YEAR_COL']}-W{int(r['WEEK_NUM']):02d}", axis=1
                )
                esort = ["YEAR_COL", "WEEK_NUM"]
            else:  # Daily
                egrp = est_df.groupby(["DATE"], as_index=False)["EST_PCT"].mean()
                egrp["X"] = egrp["DATE"].astype(str)
                esort = ["DATE"]

            egrp = egrp.sort_values(esort).reset_index(drop=True)

            fig.add_trace(go.Scatter(
                x=egrp["X"], y=egrp["EST_PCT"],
                mode="lines+markers",
                name="Est. Debt %",
                line=dict(color=PALETTE["amber_lt"], width=2, dash="dot"),
                marker=dict(
                    symbol="diamond", size=6,
                    color=PALETTE["amber_lt"],
                    line=dict(color="white", width=1),
                ),
                hovertemplate=(
                    "%{x}<br>──────────────────<br>"
                    "Est. Debt : %{y:.1f}%<extra></extra>"
                ),
            ))

    # --- Reference line ---
    fig.add_hline(
        y=80, line_dash="dash",
        line_color=PALETTE["threshold"], line_width=1.2,
        annotation_text="80% Danger Zone",
        annotation_font=dict(size=8, color=PALETTE["threshold"]),
        annotation_position="top left",
    )

    # --- Layout ---
    max_y    = max(float(grp["UTIL_PCT"].max()) * 1.15, 90)
    tick_fmt = ".0f" if view_type == "Rounded Number" else ".1f"

    apply_base_layout(fig, {
        "height": 340,
        "margin": dict(l=0, r=12, t=40, b=64),
        "xaxis": dict(
            title=f"Period ({local_gran})",
            showgrid=False, color=FONT_COLOR,
            tickangle=-35, tickfont=dict(size=8),
        ),
        "yaxis": dict(
            title="Credit Utilization (%)", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, range=[0, max_y], tickformat=tick_fmt,
        ),
        "showlegend": True,
        "legend": dict(
            orientation="h",
            xanchor="right", x=1.0,
            yanchor="top",   y=-0.22,
            font=dict(size=10),
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#d0dae6", borderwidth=1,
            itemwidth=50,
        ),
        "title": dict(
            text=(
                f"<b>{selected_customer}</b>"
                f" — Credit Utilization Trend ({local_gran})"
                f" · {', '.join(str(y) for y in sorted(selected_years))}"
            ),
            font=dict(size=11, color=FONT_COLOR),
            x=0, xanchor="left",
        ),
        "hoverlabel": dict(
            bgcolor="white",
            bordercolor="#d0dae6",
            font=dict(size=11, color="#1B2A3B"),
            align="left",
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="trend_analysis_chart")


# =============================================================================
# No data banner
# =============================================================================
def _no_data_banner():
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
        <div style="font-size:1.2rem;font-weight:700;color:#3a4a60;">No Data Available</div>
        <div style="font-size:0.9rem;color:#666;margin-top:8px;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
        </div>
    </div>
    """, unsafe_allow_html=True)