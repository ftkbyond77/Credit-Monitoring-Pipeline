# views/view_avail.py
#
# Layout:
#   Main Filter bar
#   Row 1 — KPI cards (5 full width)
#   Row 2 — [Current Debt % bar — wide] | [Credit Risk Distribution PIE]
#   Row 3 — [Debt by Product Type] | [Avg Debt % Trend]
#   Row 4 — Customer Credit Risk Preview  (full width table)
#   Row 5 — Customer Trend Analysis       (full width, independent customer filter)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components import (
    apply_base_layout, kpi_card, section_header,
    dash_title_bar, FONT_COLOR, GRID_COLOR,
)
DEBT_THRESHOLD = 0.8
MONTH_MAP = {
    1: 'Jan', 2: 'Feb',  3: 'Mar',  4: 'Apr',
    5: 'May', 6: 'Jun',  7: 'Jul',  8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
}
PALETTE = {
    'sapphire':    '#1B4F8A',
    'sapphire_lt': '#3A7BD5',
    'violet':      '#5C3D8F',
    'violet_lt':   '#8E6DC0',
    'opal':        '#1A7A74',
    'opal_lt':     '#34B8B0',
    'amber':       '#B5620A',
    'amber_lt':    '#E8A838',
    'indigo':      '#2E3A87',
    'jade':        '#1A6B45',
    'crimson':     '#A01F2D',
    'steel':       '#3D5166',
    'safe':        '#1A7A4A',
    'danger':      '#A01F2D',
    'nodata':      '#8A9BB0',
    'threshold':   '#C0392B',
}
TYPE_COLORS = [
    PALETTE['sapphire'], PALETTE['violet'], PALETTE['opal'],
    PALETTE['amber'],    PALETTE['indigo'], PALETTE['jade'],
    PALETTE['crimson'],  PALETTE['steel'],
]
TREND_SAFE   = PALETTE['sapphire_lt']
TREND_DANGER = PALETTE['crimson']
BAR_BASE     = PALETTE['sapphire']
BAR_EST      = PALETTE['amber_lt']
BAR_EST_OVER = PALETTE['crimson']

# =============================================================================
# Public entry point
# =============================================================================
def render():
    if not st.session_state.get('data_processed', False):
        _no_data_banner()
        return
    df_raw = _prepare(st.session_state.df_avail.copy())
    st.markdown(
        dash_title_bar(
            "Credit Availability Dashboard",
            "Analytics Dashboard — real-time credit exposure monitoring"
        ),
        unsafe_allow_html=True,
    )
    df, granularity, selected_years = _render_filters(df_raw)
    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df)
    st.markdown("", unsafe_allow_html=True)
    st.markdown(section_header("Credit Exposure Analysis"), unsafe_allow_html=True)
    r2_left, r2_right = st.columns([2.8, 1.2], gap="medium")
    with r2_left:
        _render_debt_pct_bar(df)
    with r2_right:
        _render_risk_pie(df)
    st.markdown("", unsafe_allow_html=True)
    st.markdown(section_header("Distribution and Trend"), unsafe_allow_html=True)
    r3_left, r3_right = st.columns([1, 1.6], gap="medium")
    with r3_left:
        _render_debt_by_type(df)
    with r3_right:
        _render_trend(df, granularity)
    st.markdown("", unsafe_allow_html=True)
    st.markdown(section_header("Customer Credit Risk Preview"), unsafe_allow_html=True)
    _render_customer_table(df)
    st.markdown("", unsafe_allow_html=True)
    st.markdown(section_header("Customer Trend Analysis"), unsafe_allow_html=True)
    _render_trend_analysis(df_raw, granularity, selected_years)

# =============================================================================
# Data preparation — UNCHANGED
# =============================================================================
def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df['YEAR'] = (
        df['SOURCE_SHEET'].astype(str).str.strip()
        if 'SOURCE_SHEET' in df.columns
        else df['DATE'].apply(lambda d: str(d.year) if pd.notna(d) else 'Unknown')
    )
    df['MONTH']       = df['DATE'].apply(lambda d: d.month if pd.notna(d) else None)
    df['WEEK']        = df['DATE'].apply(
        lambda d: d.isocalendar()[1] if pd.notna(d) else None
    )
    df['MONTH_LABEL'] = df['MONTH'].map(MONTH_MAP)
    return df

# =============================================================================
# Main Filter bar
# CHANGED: Year → st.pills (multi-select chips) — scale-friendly, UX-first
#   - ทุกปีแสดงเป็น pill กดได้, wrap อัตโนมัติเมื่อมีหลายปี
#   - "All" pill อยู่ซ้ายสุด: กด All → เลือกทุกปี, ยกเลิก All → เหลือที่เลือก
#   - fallback เป็น st.multiselect สำหรับ Streamlit < 1.42
# Returns (df_filtered, granularity, selected_years_list)
# =============================================================================
def _render_filters(df_raw: pd.DataFrame):
    all_years = sorted(df_raw['YEAR'].dropna().unique().tolist())
    all_types = (
        sorted(df_raw['TYPE'].dropna().unique().tolist())
        if 'TYPE' in df_raw.columns else []
    )

    # ── Year pill / chip selector ──────────────────────────────────────────
    st.markdown(
        '<p style="font-size:11px;font-weight:600;color:#1B4F8A;'
        'text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px;">'
        'Year (Sheet)</p>',
        unsafe_allow_html=True,
    )

    pill_options = ["All"] + all_years  # "All" เป็น option แรกเสมอ

    # ── ลอง st.pills ก่อน (Streamlit ≥ 1.42) ─────────────────────────────
    _use_pills = hasattr(st, "pills")

    if _use_pills:
        # st.pills คืน list ของที่เลือก (selection_mode="multi")
        # default = ["All"] → แสดงทุกปี
        prev_pill = st.session_state.get("_f_year_pills_prev", ["All"])

        selected_pills = st.pills(
            label="Year (Sheet)",
            options=pill_options,
            selection_mode="multi",
            default=prev_pill,
            key="f_year_pills",
            label_visibility="collapsed",
        )

        # ── Logic: All overrides / All auto-deselects ───────────────────
        if not selected_pills:
            # ไม่มีอะไรเลือก → fallback All
            selected_pills = ["All"]

        # ตรวจ: user เพิ่ง toggle "All" เข้ามาใหม่ → ล้างปีอื่นออก
        prev_had_all = "All" in prev_pill
        curr_has_all = "All" in selected_pills
        if curr_has_all and not prev_had_all:
            # All ถูก activate ใหม่
            selected_pills = ["All"]
        elif curr_has_all and prev_had_all and len(selected_pills) > 1:
            # มี All อยู่แล้ว แต่ user กดปีเพิ่ม → deselect All อัตโนมัติ
            selected_pills = [p for p in selected_pills if p != "All"]

        st.session_state["_f_year_pills_prev"] = selected_pills

        if "All" in selected_pills:
            selected_years = list(all_years)
        else:
            selected_years = [p for p in selected_pills if p in all_years]

    else:
        # ── Fallback: st.multiselect (Streamlit < 1.42) ────────────────
        st.caption("💡 Tip: อัปเกรด Streamlit ≥ 1.42 เพื่อใช้ pill selector")
        raw_sel = st.multiselect(
            "Year (Sheet)",
            options=all_years,
            default=all_years,          # default = ทั้งหมด
            placeholder="เลือกปี (ว่าง = ทุกปี)",
            key="f_year_multi",
            label_visibility="collapsed",
        )
        selected_years = list(all_years) if not raw_sel else raw_sel

    # ── แสดง summary badge ─────────────────────────────────────────────────
    if selected_years == list(all_years):
        badge = f"All {len(all_years)} year(s)"
        badge_color = "#1A7A4A"
    else:
        badge = ", ".join(str(y) for y in selected_years)
        badge_color = "#1B4F8A"

    st.markdown(
        f'<span style="font-size:10px;font-weight:600;color:{badge_color};">'
        f'● {badge}</span>',
        unsafe_allow_html=True,
    )

    # ── Filter controls row (granularity, month, type, debt, est) ─────────
    fc2, fc3, fc4, fc5, fc6 = st.columns([1.1, 1.3, 1.3, 1.1, 1.1])

    with fc2:
        granularity = st.selectbox(
            "Period",
            ["Monthly", "Weekly", "Daily", "Yearly"],
            key="f_gran",
        )

    # Month options scoped to selected years
    df_scope     = df_raw[df_raw['YEAR'].isin(selected_years)]
    avail_months = sorted(df_scope['MONTH'].dropna().unique().tolist())
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
        est_filter = st.selectbox("Est. Debt", ["All", ">= 80%", "< 80%"], key="f_est")

    # ── Apply filters ───────────────────────────────────────────────────────
    df = df_raw[df_raw['YEAR'].isin(selected_years)].copy()

    if sel_month:
        df = df[df['MONTH'] == sel_month]
    if sel_type != "All" and 'TYPE' in df.columns:
        df = df[df['TYPE'] == sel_type]
    if 'CURRENT_DEBT_MILLION_THB_PERCENT' in df.columns:
        if debt_filter == ">= 80%":
            df = df[df['CURRENT_DEBT_MILLION_THB_PERCENT'] >= DEBT_THRESHOLD]
        elif debt_filter == "< 80%":
            df = df[df['CURRENT_DEBT_MILLION_THB_PERCENT'] < DEBT_THRESHOLD]
    if 'EST_DEBT' in df.columns:
        if est_filter == ">= 80%":
            df = df[df['EST_DEBT'] >= DEBT_THRESHOLD]
        elif est_filter == "< 80%":
            df = df[df['EST_DEBT'] < DEBT_THRESHOLD]

    return df, granularity, selected_years

# =============================================================================
# Row 1 — KPI cards — UNCHANGED
# =============================================================================
def _render_kpi_row(df: pd.DataFrame):
    total_customers  = int(df['CUSTOMER_CODE'].nunique()) if 'CUSTOMER_CODE' in df.columns else 0
    total_credit     = df['CLEAN_CREDIT_MB'].sum()           if 'CLEAN_CREDIT_MB' in df.columns else 0.0
    total_debt       = df['CURRENT_DEBT_MILLION_THB'].sum()   if 'CURRENT_DEBT_MILLION_THB' in df.columns else 0.0
    avg_debt_pct     = (
        df['CURRENT_DEBT_MILLION_THB_PERCENT'].mean() * 100
        if 'CURRENT_DEBT_MILLION_THB_PERCENT' in df.columns else 0.0
    )
    high_risk_count  = 0
    est_exceed_count = 0
    if 'CURRENT_DEBT_MILLION_THB_PERCENT' in df.columns and 'CUSTOMER_CODE' in df.columns:
        high_risk_count = int(
            df[df['CURRENT_DEBT_MILLION_THB_PERCENT'] >= DEBT_THRESHOLD]['CUSTOMER_CODE'].nunique()
        )
    if 'EST_DEBT' in df.columns and 'CUSTOMER_CODE' in df.columns:
        est_exceed_count = int(
            df[df['EST_DEBT'] >= DEBT_THRESHOLD]['CUSTOMER_CODE'].nunique()
        )
    cols  = st.columns(5, gap="small")
    cards = [
        ("Total Customers",    f"{total_customers:,}",   "Distinct codes",                  "info"),
        ("Total Clean Credit", f"{total_credit:,.1f}M",  "THB credit limit",                "info"),
        ("Total Current Debt", f"{total_debt:,.1f}M",    f"Avg ratio: {avg_debt_pct:.2f}%", "info"),
        ("High Risk",          f"{high_risk_count:,}",   "Current Debt >= 80%",
         "danger" if high_risk_count > 0 else "safe"),
        ("Est. Will Exceed",   f"{est_exceed_count:,}",  "Forecast risk count",
         "warning" if est_exceed_count > 0 else "safe"),
    ]
    for col, (label, value, sub, variant) in zip(cols, cards):
        with col:
            st.markdown(kpi_card(label, value, sub, variant), unsafe_allow_html=True)

# =============================================================================
# Row 2 left — Current Debt % horizontal stack bar
# CHANGED: replaces _render_avg_debt_bar
#   - X axis = Current Debt % (0–100%+)
#   - Base bar  = Current Debt %  (blue, per customer latest snapshot)
#   - Stack bar = Est. Future Diff % = (EST_DEBT% − CURRENT_DEBT%) clipped ≥ 0
#                 colour: amber if (current + diff) < 80%, crimson if >= 80%
#   - Show Est. Future Diff controlled by toggle
#   - Top N slider still present
#   - 80% danger vline
# =============================================================================
def _render_debt_pct_bar(df: pd.DataFrame):
    # Controls row
    ctrl1, ctrl2, _ = st.columns([1.4, 1.6, 3])
    with ctrl1:
        show_est = st.toggle("Show Est. Future Diff", value=False, key="show_est")
    with ctrl2:
        top_n = st.select_slider("Top N", options=[5, 10, 15, 20], value=10, key="top_n")
    needed = {'CUSTOMER_NAME', 'CURRENT_DEBT_MILLION_THB_PERCENT'}
    if not needed.issubset(df.columns):
        st.info("Insufficient data.")
        return
    # Latest snapshot per customer
    snap = (
        df.sort_values('DATE', ascending=False).drop_duplicates(subset=['CUSTOMER_NAME'])
        if 'DATE' in df.columns
        else df.drop_duplicates(subset=['CUSTOMER_NAME'])
    ).copy()
    snap['DEBT_PCT_DISP'] = snap['CURRENT_DEBT_MILLION_THB_PERCENT'] * 100
    # Sort by current debt % desc, take top N, then reverse for horizontal bar
    snap = (
        snap.sort_values('DEBT_PCT_DISP', ascending=False)
        .head(top_n)
        .sort_values('DEBT_PCT_DISP', ascending=True)
        .reset_index(drop=True)
    )
    # Bar colour: danger if >= 80%, else sapphire
    base_colors = [
        PALETTE['danger'] if v >= 80 else BAR_BASE
        for v in snap['DEBT_PCT_DISP']
    ]
    fig = go.Figure()
    # Base: Current Debt %
    fig.add_trace(go.Bar(
        y=snap['CUSTOMER_NAME'],
        x=snap['DEBT_PCT_DISP'],
        orientation='h',
        name='Current Debt %',
        marker_color=base_colors,
        text=[f"{v:.1f}%" for v in snap['DEBT_PCT_DISP']],
        textposition='inside',
        insidetextanchor='end',
        textfont=dict(size=8, color='white'),
        hovertemplate='%{y}<br>Current Debt: %{x:.1f}%<extra></extra>',
    ))
    # Stack: Est. Future Diff (toggle)
    if show_est and 'EST_DEBT' in snap.columns:
        snap['EST_PCT_DISP'] = snap['EST_DEBT'] * 100
        snap['DIFF'] = (snap['EST_PCT_DISP'] - snap['DEBT_PCT_DISP']).clip(lower=0)
        # colour per bar: if (current + diff) >= 80 → crimson, else amber
        diff_colors = [
            BAR_EST_OVER if (row['DEBT_PCT_DISP'] + row['DIFF']) >= 80 else BAR_EST
            for _, row in snap.iterrows()
        ]
        fig.add_trace(go.Bar(
            y=snap['CUSTOMER_NAME'],
            x=snap['DIFF'],
            orientation='h',
            name='Est. Future Diff',
            marker_color=diff_colors,
            text=[f"+{v:.1f}%" if v > 0 else "" for v in snap['DIFF']],
            textposition='inside',
            insidetextanchor='start',
            textfont=dict(size=8, color='white'),
            hovertemplate='%{y}<br>Est. Future Diff: +%{x:.1f}%<extra></extra>',
        ))
        fig.update_layout(barmode='stack')
    else:
        fig.update_layout(barmode='stack')
    # 80% danger vline
    fig.add_vline(
        x=80,
        line_dash='dash',
        line_color=PALETTE['threshold'],
        line_width=1.2,
        annotation_text="80%",
        annotation_font=dict(size=8, color=PALETTE['threshold']),
        annotation_position="top",
    )
    bar_height = max(220, top_n * 28)
    apply_base_layout(fig, {
        'height': bar_height,
        'margin': dict(l=0, r=40, t=10, b=4),
        'xaxis': dict(
            title="Current Debt %",
            ticksuffix="%",
            showgrid=True,
            gridcolor=GRID_COLOR,
            zeroline=False,
            color=FONT_COLOR,
            tickfont=dict(size=9),
            range=[0, max(120, float(snap['DEBT_PCT_DISP'].max()) * 1.2)],
        ),
        'yaxis': dict(
            showgrid=False,
            color=FONT_COLOR,
            tickfont=dict(size=9),
        ),
        'showlegend': show_est,
        'legend': dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=9),
        ),
    })
    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# Row 2 right — Credit Risk Distribution PIE — UNCHANGED
# =============================================================================
def _render_risk_pie(df: pd.DataFrame):
    st.markdown(
        '<p class="section-sub">Credit Risk Distribution</p>',
        unsafe_allow_html=True,
    )
    if 'CURRENT_DEBT_MILLION_THB_PERCENT' not in df.columns or 'CUSTOMER_CODE' not in df.columns:
        st.info("No data.")
        return
    snap = (
        df.sort_values('DATE', ascending=False).drop_duplicates(subset=['CUSTOMER_CODE'])
        if 'DATE' in df.columns
        else df.drop_duplicates(subset=['CUSTOMER_CODE'])
    )
    safe_n   = int((snap['CURRENT_DEBT_MILLION_THB_PERCENT'] < DEBT_THRESHOLD).sum())
    danger_n = int((snap['CURRENT_DEBT_MILLION_THB_PERCENT'] >= DEBT_THRESHOLD).sum())
    nodata_n = int(snap['CURRENT_DEBT_MILLION_THB_PERCENT'].isna().sum())
    labels, values, colors = [], [], []
    for lbl, val, color in [
        ('Safe < 80%',       safe_n,   PALETTE['safe']),
        ('High Risk >= 80%', danger_n, PALETTE['danger']),
        ('No Data',          nodata_n, PALETTE['nodata']),
    ]:
        if val > 0:
            labels.append(lbl)
            values.append(val)
            colors.append(color)
    if not labels:
        st.info("No data.")
        return
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color='white', width=2)),
        textinfo='label+percent',
        textfont=dict(size=10),
        hovertemplate='%{label}: %{value} customers (%{percent})<extra></extra>',
        showlegend=False,
    ))
    apply_base_layout(fig, {
        'height': 260,
        'margin': dict(l=8, r=8, t=8, b=8),
        'showlegend': False,
    })
    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# Row 3 left — Debt by Product Type — UNCHANGED
# =============================================================================
def _render_debt_by_type(df: pd.DataFrame):
    st.markdown('<p class="section-sub">Debt by Product Type</p>', unsafe_allow_html=True)
    if 'TYPE' not in df.columns or 'CURRENT_DEBT_MILLION_THB' not in df.columns:
        st.info("No TYPE data.")
        return

    has_cust = 'CUSTOMER_CODE' in df.columns

    # ── Aggregate ──────────────────────────────────────────────────────────
    agg_dict = {'CURRENT_DEBT_MILLION_THB': ('CURRENT_DEBT_MILLION_THB', 'sum')}
    if has_cust:
        agg_dict['CUSTOMER_COUNT'] = ('CUSTOMER_CODE', 'nunique')

    by_type = (
        df.groupby('TYPE', as_index=False)
        .agg(**agg_dict)
        .rename(columns={'CURRENT_DEBT_MILLION_THB': 'TOTAL'})
        .sort_values('TOTAL', ascending=False)
        .reset_index(drop=True)
    )

    total_all      = by_type['TOTAL'].sum()
    by_type['PCT'] = (
        (by_type['TOTAL'] / total_all * 100).round(1) if total_all > 0 else 0.0
    )

    # ── Chart ─────────────────────────────────────────────────────────────
    fig = go.Figure()

    for i, row in by_type.iterrows():
        color      = TYPE_COLORS[i % len(TYPE_COLORS)]
        cust_count = int(row['CUSTOMER_COUNT']) if has_cust else None

        # Bar label: debt value บรรทัดแรก, customer count บรรทัดสอง
        if has_cust:
            bar_label = f"{row['TOTAL']:,.1f}<br><span style='font-size:8px'>({cust_count} co.)</span>"
        else:
            bar_label = f"{row['TOTAL']:,.1f}"

        # Hover tooltip
        hover_lines = [
            f"<b>{row['TYPE']}</b>",
            "──────────────────",
            f"💰 Total Debt  : <b>{row['TOTAL']:,.1f} MB</b>",
            f"📊 Share       : <b>{row['PCT']}%</b>",
        ]
        if has_cust:
            hover_lines.append(f"🏢 Customers   : <b>{cust_count:,} companies</b>")
        hover_str = "<br>".join(hover_lines) + "<extra></extra>"

        fig.add_trace(go.Bar(
            x=[row['TYPE']],
            y=[row['TOTAL']],
            name=f"{row['TYPE']} ({row['PCT']}%)",
            marker_color=color,
            text=[bar_label],
            textposition='outside',
            cliponaxis=False,
            textfont=dict(size=9, color=FONT_COLOR),
            hovertemplate=hover_str,
        ))

    apply_base_layout(fig, {
        'height': 250,
        'margin': dict(l=0, r=8, t=4, b=4),
        'barmode': 'group',
        'xaxis': dict(showgrid=False, color=FONT_COLOR, tickfont=dict(size=9)),
        'yaxis': dict(
            title="Total Debt (MB)", showgrid=True,
            gridcolor=GRID_COLOR, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        'showlegend': True,
        'legend': dict(
            orientation='v', yanchor='top', y=1.0, xanchor='left', x=1.02,
            font=dict(size=8), bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#d0dae6', borderwidth=1,
        ),
        'hoverlabel': dict(
            bgcolor='white',
            bordercolor='#d0dae6',
            font=dict(size=11, color='#1B2A3B'),
            align='left',
        ),
    })
    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# Row 3 right — Avg Debt % Trend — UNCHANGED
# =============================================================================
def _render_trend(df: pd.DataFrame, granularity: str):
    st.markdown(
        f'<p class="section-sub">Avg Debt % — {granularity} View</p>',
        unsafe_allow_html=True,
    )
    if 'CURRENT_DEBT_MILLION_THB_PERCENT' not in df.columns:
        st.info("No debt percent data.")
        return
    if granularity == "Yearly":
        group_cols = ['YEAR']
        label_fn   = lambda r: str(r['YEAR'])
        sort_cols  = ['YEAR']
    elif granularity == "Monthly":
        group_cols = ['YEAR', 'MONTH', 'MONTH_LABEL']
        label_fn   = lambda r: f"{r['YEAR']}-{r['MONTH_LABEL']}"
        sort_cols  = ['YEAR', 'MONTH']
    elif granularity == "Weekly":
        group_cols = ['YEAR', 'WEEK']
        label_fn   = lambda r: f"{r['YEAR']}-W{int(r.get('WEEK', 0)):02d}"
        sort_cols  = ['YEAR', 'WEEK']
    else:
        group_cols = ['DATE']
        label_fn   = lambda r: str(r['DATE'])
        sort_cols  = ['DATE']
    trend = (
        df.groupby(group_cols, as_index=False)['CURRENT_DEBT_MILLION_THB_PERCENT']
        .mean()
        .rename(columns={'CURRENT_DEBT_MILLION_THB_PERCENT': 'AVG_PCT'})
        .sort_values(sort_cols)
    )
    if 'MONTH_LABEL' not in trend.columns and 'MONTH' in trend.columns:
        trend['MONTH_LABEL'] = trend['MONTH'].map(MONTH_MAP)
    trend['X']            = trend.apply(label_fn, axis=1)
    trend['AVG_PCT_DISP'] = trend['AVG_PCT'] * 100
    bar_colors = [TREND_DANGER if v >= 80 else TREND_SAFE for v in trend['AVG_PCT_DISP']]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=trend['X'], y=trend['AVG_PCT_DISP'],
        marker_color=bar_colors,
        text=[f"{v:.1f}%" for v in trend['AVG_PCT_DISP']],
        textposition='outside', cliponaxis=False,
        textfont=dict(size=8, color=FONT_COLOR),
        hovertemplate='%{x}<br>Avg Debt: %{y:.2f}%',
    ))
    fig.add_hline(
        y=80, line_dash='dash',
        line_color=PALETTE['threshold'], line_width=1.2,
        annotation_text="80%",
        annotation_font=dict(size=8, color=PALETTE['threshold']),
        annotation_position="top left",
    )
    max_y = max(trend['AVG_PCT_DISP'].max() * 1.15, 90) if not trend.empty else 100
    apply_base_layout(fig, {
        'height': 250,
        'margin': dict(l=0, r=8, t=4, b=4),
        'xaxis': dict(
            showgrid=False, color=FONT_COLOR,
            tickangle=-35, tickfont=dict(size=8),
        ),
        'yaxis': dict(
            title="Avg Debt %", ticksuffix="%", showgrid=True,
            gridcolor=GRID_COLOR, color=FONT_COLOR,
            range=[0, max_y], tickformat='.2f',
        ),
        'showlegend': False,
    })
    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# Row 4 — Customer Credit Risk Preview (full width) — UNCHANGED
# =============================================================================
def _render_customer_table(df: pd.DataFrame):
    c_mode, _ = st.columns([2, 6])
    with c_mode:
        mode = st.radio(
            "View",
            ["Top Clean Credit", "Top Risk Customers"],
            horizontal=True,
            key="table_mode",
        )
    desired_cols = [
        'CUSTOMER_NAME', 'TYPE',
        'CLEAN_CREDIT_MB', 'CURRENT_DEBT_MILLION_THB',
        'CURRENT_DEBT_MILLION_THB_PERCENT',
    ]
    avail_cols = [c for c in desired_cols if c in df.columns]
    dedup_key  = ['CUSTOMER_NAME'] if 'CUSTOMER_NAME' in avail_cols else None
    if mode == "Top Clean Credit" and 'CLEAN_CREDIT_MB' in df.columns:
        tbl = (
            df[avail_cols].drop_duplicates(subset=dedup_key)
            .sort_values('CLEAN_CREDIT_MB', ascending=False)
            .head(10).reset_index(drop=True)
        )
    elif mode == "Top Risk Customers" and 'CURRENT_DEBT_MILLION_THB_PERCENT' in df.columns:
        tbl = (
            df[avail_cols].drop_duplicates(subset=dedup_key)
            .sort_values('CURRENT_DEBT_MILLION_THB_PERCENT', ascending=False)
            .head(10).reset_index(drop=True)
        )
    else:
        st.info("No data.")
        return
    st.dataframe(
        tbl,
        column_config={
            "CUSTOMER_NAME": st.column_config.TextColumn("Customer", width="large"),
            "TYPE":          st.column_config.TextColumn("Type", width="small"),
            "CLEAN_CREDIT_MB": st.column_config.NumberColumn(
                "Clean Credit (MB)", format="%.2f", width="medium"),
            "CURRENT_DEBT_MILLION_THB": st.column_config.NumberColumn(
                "Debt (MB)", format="%.2f", width="medium"),
            "CURRENT_DEBT_MILLION_THB_PERCENT": st.column_config.NumberColumn(
                "Debt %", format="%.2f", width="small"),
        },
        use_container_width=True, height=320, hide_index=True,
    )

# =============================================================================
# Row 5 — Customer Trend Analysis — UNCHANGED except emoji removed
# =============================================================================
# =============================================================================
# Row 5 — Customer Trend Analysis
# CHANGED:
#   - Est. Debt % → แสดงเป็นเส้นสีเหลือง (dash dot) แทนจุด
#   - Hover tooltip → เพิ่ม Clean Credit / Current Debt / Utilization %
# =============================================================================
def _render_trend_analysis(df_raw: pd.DataFrame, main_granularity: str, selected_years: list):
    required = {'CUSTOMER_NAME', 'CURRENT_DEBT_MILLION_THB_PERCENT', 'DATE'}
    if not required.issubset(df_raw.columns):
        st.info("Required columns: CUSTOMER_NAME, CURRENT_DEBT_MILLION_THB_PERCENT, DATE")
        return
    df_scoped = df_raw[df_raw['YEAR'].isin(selected_years)].copy()
    all_names = sorted(df_scoped['CUSTOMER_NAME'].dropna().unique().tolist())
    if not all_names:
        st.info("No customer data for the selected year(s).")
        return

    # ── Local filter row ───────────────────────────────────────────────────
    lf1, lf2, lf_space, lf3 = st.columns([2.5, 1.4, 1.6, 1.5])
    with lf1:
        st.markdown(
            '<p style="font-size:11px;font-weight:600;color:#1B4F8A;'
            'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">'
            'Customer Search</p>',
            unsafe_allow_html=True,
        )
        search_query = st.text_input(
            "Customer Search",
            placeholder="Type name or Customer Code…",
            key="trend_search",
            label_visibility="collapsed",
        ).strip()
    with lf2:
        st.markdown(
            '<p style="font-size:11px;font-weight:600;color:#1B4F8A;'
            'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">'
            'Period (Trend)</p>',
            unsafe_allow_html=True,
        )
        gran_options  = ["Monthly", "Weekly", "Daily", "Yearly"]
        default_index = gran_options.index(main_granularity) if main_granularity in gran_options else 0
        local_gran = st.selectbox(
            "Period (Trend)", gran_options,
            index=default_index, key="trend_local_gran",
            label_visibility="collapsed",
        )
    with lf3:
        st.markdown(
            '<p style="font-size:11px;font-weight:600;color:#1B4F8A;'
            'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">'
            'Est. Debt %</p>',
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
            f'<span style="font-size:10px;color:{badge_color};font-weight:600;">'
            f'● {badge_text}</span>',
            unsafe_allow_html=True,
        )

    # ── Customer search / filter ───────────────────────────────────────────
    if search_query:
        q = search_query.lower()
        filtered_names = [n for n in all_names if q in n.lower()]
        if 'CUSTOMER_CODE' in df_scoped.columns:
            code_hits = (
                df_scoped[
                    df_scoped['CUSTOMER_CODE'].astype(str).str.lower().str.contains(q, na=False)
                ]['CUSTOMER_NAME'].dropna().unique().tolist()
            )
            filtered_names = list(dict.fromkeys(filtered_names + code_hits))
    else:
        filtered_names = all_names
    if not filtered_names:
        st.warning(f"No customer matched '{search_query}'.")
        return
    st.markdown(
        f'<p style="font-size:11px;color:#5a6a80;margin:6px 0 4px 0;">'
        f'<b>{len(filtered_names)}</b> result(s)'
        + (f' — search: <i>{search_query}</i>' if search_query else '')
        + '</p>',
        unsafe_allow_html=True,
    )
    prev_key   = st.session_state.get("trend_customer_select")
    default_ix = (
        filtered_names.index(prev_key)
        if prev_key and prev_key in filtered_names else 0
    )
    selected_customer = st.selectbox(
        "Select Customer",
        filtered_names,
        index=default_ix,
        key="trend_customer_select",
    )

    # ── Build time-series for selected customer ────────────────────────────
    cdf = (
        df_scoped[df_scoped['CUSTOMER_NAME'] == selected_customer]
        .dropna(subset=['DATE', 'CURRENT_DEBT_MILLION_THB_PERCENT'])
        .sort_values('DATE').copy()
    )
    if cdf.empty:
        st.info("No trend data for this customer in the selected year(s).")
        return

    cdf['UTIL_PCT']    = cdf['CURRENT_DEBT_MILLION_THB_PERCENT'] * 100
    cdf['YEAR_COL']    = cdf['DATE'].apply(lambda d: str(d.year) if pd.notna(d) else 'Unknown')
    cdf['MONTH_NUM']   = cdf['DATE'].apply(lambda d: d.month if pd.notna(d) else None)
    cdf['WEEK_NUM']    = cdf['DATE'].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
    cdf['MONTH_LABEL'] = cdf['MONTH_NUM'].map(MONTH_MAP)

    # ── Granularity grouping — รวม CURRENT_DEBT + CLEAN_CREDIT เข้า grp ──
    #    ใช้ mean() สำหรับตัวเงิน (กรณี daily อาจมีหลายแถวต่อวัน)
    debt_col   = 'CURRENT_DEBT_MILLION_THB'
    credit_col = 'CLEAN_CREDIT_MB'
    extra_agg  = {
        col: (col, 'mean')
        for col in [debt_col, credit_col]
        if col in cdf.columns
    }

    def _group(frame, keys, sort_keys, label_fn):
        agg_dict = {'UTIL_PCT': ('UTIL_PCT', 'mean'), **extra_agg}
        g = frame.groupby(keys, as_index=False).agg(**agg_dict)
        g = g.sort_values(sort_keys).reset_index(drop=True)
        g['X'] = g.apply(label_fn, axis=1)
        return g

    if local_gran == "Yearly":
        grp = _group(cdf, ['YEAR_COL'], ['YEAR_COL'],
                     lambda r: str(r['YEAR_COL']))
    elif local_gran == "Monthly":
        grp = _group(cdf, ['YEAR_COL', 'MONTH_NUM', 'MONTH_LABEL'],
                     ['YEAR_COL', 'MONTH_NUM'],
                     lambda r: f"{r['YEAR_COL']}-{r['MONTH_LABEL']}")
    elif local_gran == "Weekly":
        grp = _group(cdf, ['YEAR_COL', 'WEEK_NUM'],
                     ['YEAR_COL', 'WEEK_NUM'],
                     lambda r: f"{r['YEAR_COL']}-W{int(r['WEEK_NUM']):02d}")
    else:  # Daily
        grp = _group(cdf, ['DATE'], ['DATE'],
                     lambda r: str(r['DATE']))

    if grp.empty:
        st.info("No data for this granularity.")
        return

    # ── KPI strip ─────────────────────────────────────────────────────────
    latest_util   = float(grp['UTIL_PCT'].iloc[-1])
    avg_util      = float(grp['UTIL_PCT'].mean())
    period_change = (
        float(grp['UTIL_PCT'].iloc[-1] - grp['UTIL_PCT'].iloc[-2])
        if len(grp) >= 2 else 0.0
    )
    risk_color = "#A01F2D" if latest_util >= 80 else ("#B5620A" if latest_util >= 50 else "#1A7A4A")
    chg_color  = "#A01F2D" if period_change > 0 else "#1A7A4A"
    chg_arrow  = "▲" if period_change > 0 else "▼"
    kpi_blocks = [
        ("Utilization (Latest)",    f"{latest_util:.1f}%",                    risk_color),
        (f"Change ({local_gran})",  f"{chg_arrow} {abs(period_change):.1f}%", chg_color),
        ("Avg Utilization",         f"{avg_util:.1f}%",                       FONT_COLOR),
    ]
    raw_cust = (
        df_scoped[df_scoped['CUSTOMER_NAME'] == selected_customer]
        .dropna(subset=['DATE']).sort_values('DATE')
    )
    if not raw_cust.empty:
        lr = raw_cust.iloc[-1]
        if debt_col in df_scoped.columns:
            v = lr.get(debt_col)
            if pd.notna(v):
                kpi_blocks.append(("Current Debt",  f"฿{float(v):,.1f}M", FONT_COLOR))
        if credit_col in df_scoped.columns:
            v = lr.get(credit_col)
            if pd.notna(v):
                kpi_blocks.append(("Credit Limit",  f"฿{float(v):,.0f}M", FONT_COLOR))
    card_style = (
        "background:#f0f4fa;border-radius:8px;padding:8px 16px;"
        "min-width:100px;flex:1 1 auto;"
    )
    kpi_html = "".join(
        f'<div style="{card_style}">'
        f'<div style="font-size:10px;color:#5a6a80;">{lbl}</div>'
        f'<div style="font-size:1.15rem;font-weight:700;color:{col};">{val}</div>'
        f'</div>'
        for lbl, val, col in kpi_blocks
    )
    st.markdown(
        f'<div style="display:flex;gap:8px;margin:10px 0 14px 0;flex-wrap:wrap;">{kpi_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Build customdata array for rich hover ─────────────────────────────
    #    columns: [0] debt_mb, [1] credit_mb
    #    ถ้าคอลัมน์ไม่มีในข้อมูล → fill None
    has_debt   = debt_col   in grp.columns
    has_credit = credit_col in grp.columns

    def _fmt_mb(series_or_none, row_idx):
        """คืน string สำหรับ customdata — 'N/A' ถ้าไม่มีข้อมูล"""
        if series_or_none is None:
            return "N/A"
        v = series_or_none.iloc[row_idx]
        return f"฿{v:,.1f} M" if pd.notna(v) else "N/A"

    customdata = [
        [
            grp[debt_col].iloc[i]   if has_debt   else None,
            grp[credit_col].iloc[i] if has_credit else None,
        ]
        for i in range(len(grp))
    ]

    # hovertemplate — จัด 3 บรรทัดสะอาด
    hover_util = (
        "<b>%{x}</b><br>"
        "──────────────────<br>"
        "📊 Utilization : <b>%{y:.1f}%</b><br>"
        "💳 Clean Credit : <b>%{customdata[1]:,.1f} M฿</b><br>"
        "📉 Current Debt : <b>%{customdata[0]:,.1f} M฿</b>"
        "<extra></extra>"
    )
    # กรณีไม่มีข้อมูลตัวเงิน → hovertemplate แบบเรียบ
    if not has_debt and not has_credit:
        hover_util = (
            "<b>%{x}</b><br>"
            "Utilization : <b>%{y:.1f}%</b>"
            "<extra></extra>"
        )

    # ── Chart ─────────────────────────────────────────────────────────────
    point_colors = [
        PALETTE['danger'] if v >= 80
        else (PALETTE['amber'] if v >= 50 else PALETTE['sapphire_lt'])
        for v in grp['UTIL_PCT']
    ]
    fig = go.Figure()

    # Area fill (decorative)
    fig.add_trace(go.Scatter(
        x=grp['X'], y=grp['UTIL_PCT'],
        mode='none', fill='tozeroy',
        fillcolor='rgba(58,123,213,0.08)',
        showlegend=False, hoverinfo='skip',
    ))

    # Utilization line — with rich hover
    fig.add_trace(go.Scatter(
        x=grp['X'],
        y=grp['UTIL_PCT'],
        mode='lines+markers',
        name='Utilization %',
        line=dict(color=PALETTE['sapphire_lt'], width=2),
        marker=dict(color=point_colors, size=7, line=dict(color='white', width=1.5)),
        customdata=customdata,
        hovertemplate=hover_util,
    ))

    # ── Est. Debt % line (toggle) — เส้นสีเหลือง dash-dot ────────────────
    if show_est_line and 'EST_DEBT' in df_scoped.columns:
        est_df = (
            df_scoped[df_scoped['CUSTOMER_NAME'] == selected_customer]
            .dropna(subset=['DATE', 'EST_DEBT']).copy()
        )
        if not est_df.empty:
            est_df['EST_PCT']     = est_df['EST_DEBT'] * 100
            est_df['YEAR_COL']    = est_df['DATE'].apply(lambda d: str(d.year))
            est_df['MONTH_NUM']   = est_df['DATE'].apply(lambda d: d.month)
            est_df['MONTH_LABEL'] = est_df['MONTH_NUM'].map(MONTH_MAP)
            est_df['WEEK_NUM']    = est_df['DATE'].apply(lambda d: d.isocalendar()[1])

            if local_gran == "Yearly":
                egrp = est_df.groupby(['YEAR_COL'], as_index=False)['EST_PCT'].mean()
                egrp['X'] = egrp['YEAR_COL'].astype(str)
                esort = ['YEAR_COL']
            elif local_gran == "Monthly":
                egrp = est_df.groupby(
                    ['YEAR_COL', 'MONTH_NUM', 'MONTH_LABEL'], as_index=False
                )['EST_PCT'].mean()
                egrp['X'] = egrp.apply(
                    lambda r: f"{r['YEAR_COL']}-{r['MONTH_LABEL']}", axis=1
                )
                esort = ['YEAR_COL', 'MONTH_NUM']
            elif local_gran == "Weekly":
                egrp = est_df.groupby(
                    ['YEAR_COL', 'WEEK_NUM'], as_index=False
                )['EST_PCT'].mean()
                egrp['X'] = egrp.apply(
                    lambda r: f"{r['YEAR_COL']}-W{int(r['WEEK_NUM']):02d}", axis=1
                )
                esort = ['YEAR_COL', 'WEEK_NUM']
            else:
                egrp = est_df.groupby(['DATE'], as_index=False)['EST_PCT'].mean()
                egrp['X'] = egrp['DATE'].astype(str)
                esort = ['DATE']

            egrp = egrp.sort_values(esort).reset_index(drop=True)

            fig.add_trace(go.Scatter(
                x=egrp['X'],
                y=egrp['EST_PCT'],
                # CHANGED: mode='lines' — เส้นต่อเนื่อง ไม่ใช่จุด
                mode='lines+markers',
                name='Est. Debt %',
                line=dict(
                    color=PALETTE['amber_lt'],   # สีเหลือง
                    width=2,
                    dash='dot',                  # เส้นประ เพื่อแยกจาก Utilization
                ),
                marker=dict(
                    symbol='diamond',
                    size=6,
                    color=PALETTE['amber_lt'],
                    line=dict(color='white', width=1),
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "──────────────────<br>"
                    "🔮 Est. Debt : <b>%{y:.1f}%</b>"
                    "<extra></extra>"
                ),
            ))

    # 80% danger line
    fig.add_hline(
        y=80, line_dash='dash',
        line_color=PALETTE['threshold'], line_width=1.2,
        annotation_text="80% Danger",
        annotation_font=dict(size=8, color=PALETTE['threshold']),
        annotation_position="top left",
    )

    max_y = max(float(grp['UTIL_PCT'].max()) * 1.15, 90)
    apply_base_layout(fig, {
        'height': 340,
        'margin': dict(l=0, r=12, t=40, b=64),
        'xaxis': dict(
            showgrid=False, color=FONT_COLOR,
            tickangle=-35, tickfont=dict(size=8),
        ),
        'yaxis': dict(
            title="Utilization %", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, range=[0, max_y], tickformat='.1f',
        ),
        'showlegend': True,
        'legend': dict(
            orientation='h',
            xanchor='right', x=1.0,
            yanchor='top',   y=-0.22,
            font=dict(size=10),
            bgcolor='rgba(255,255,255,0.92)',
            bordercolor='#d0dae6', borderwidth=1,
            itemwidth=50,
        ),
        'title': dict(
            text=(
                f"<b>{selected_customer}</b>"
                f" — Credit Utilization Trend ({local_gran})"
                f" · {', '.join(str(y) for y in sorted(selected_years))}"
            ),
            font=dict(size=11, color=FONT_COLOR),
            x=0, xanchor='left',
        ),
        # CHANGED: hoverlabel styling — ให้ tooltip ดูสะอาด
        'hoverlabel': dict(
            bgcolor='white',
            bordercolor='#d0dae6',
            font=dict(size=11, color='#1B2A3B'),
            align='left',
        ),
    })
    st.plotly_chart(fig, use_container_width=True, key="trend_analysis_chart")

# =============================================================================
# Utility — UNCHANGED
# =============================================================================
def _no_data_banner():
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <h3 style="color:#1B4F8A;">No Data Available</h3>
        <p style="color:#5a6a80;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
        </p>
    </div>
    """, unsafe_allow_html=True)