# views/view_avail.py
#
# Layout:
#   Filter bar
#   Row 1 — KPI cards (5 full width)
#   Row 2 — [Avg Current Debt bar — wide] | [Credit Risk Distribution donut + interactive table]
#   Row 3 — [Debt by Product Type vertical] | [Avg Debt % Trend]
#   Row 4 — Customer table (toggle Top Credit / Top Risk)

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

# =============================================================================
# Color palette — formal but distinctive
# Sapphire, Violet, Opal-teal, Amber-gold, Slate-indigo, Jade, Crimson, Steel
# =============================================================================
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
    'safe':        '#1A7A4A',   # donut safe segment
    'danger':      '#A01F2D',   # donut danger segment
    'nodata':      '#8A9BB0',   # donut no-data segment
    'threshold':   '#C0392B',   # hline
}

# Chart-specific color sequences (ordered for multi-series)
TYPE_COLORS  = [
    PALETTE['sapphire'], PALETTE['violet'], PALETTE['opal'],
    PALETTE['amber'],    PALETTE['indigo'], PALETTE['jade'],
    PALETTE['crimson'],  PALETTE['steel'],
]
TREND_SAFE   = PALETTE['sapphire_lt']
TREND_DANGER = PALETTE['crimson']
BAR_BASE     = PALETTE['sapphire']
BAR_EST      = PALETTE['amber']
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

    df, granularity = _render_filters(df_raw)

    st.markdown(section_header("Key Metrics"), unsafe_allow_html=True)
    _render_kpi_row(df)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    st.markdown(section_header("Credit Exposure Analysis"), unsafe_allow_html=True)
    r2_left, r2_right = st.columns([2.8, 1.2], gap="medium")
    with r2_left:
        _render_avg_debt_bar(df)
    with r2_right:
        _render_risk_donut(df)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    st.markdown(section_header("Distribution and Trend"), unsafe_allow_html=True)
    r3_left, r3_right = st.columns([1, 1.6], gap="medium")
    with r3_left:
        _render_debt_by_type(df)
    with r3_right:
        _render_trend(df, granularity)

    st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
    st.markdown(section_header("Customer Detail"), unsafe_allow_html=True)
    _render_customer_table(df)


# =============================================================================
# Data preparation
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
# Filter bar
# =============================================================================
def _render_filters(df_raw: pd.DataFrame):
    all_years = sorted(df_raw['YEAR'].dropna().unique().tolist())
    all_types = (
        sorted(df_raw['TYPE'].dropna().unique().tolist())
        if 'TYPE' in df_raw.columns else []
    )

    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.3, 1.1, 1.3, 1.3, 1.1, 1.1])

    with fc1:
        sel_year = st.selectbox("Year (Sheet)", ["All"] + all_years, key="f_year")
    with fc2:
        granularity = st.selectbox(
            "Period", ["Monthly", "Weekly", "Daily", "Yearly"], key="f_gran"
        )

    df_scope     = df_raw if sel_year == "All" else df_raw[df_raw['YEAR'] == sel_year]
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

    st.markdown('</div>', unsafe_allow_html=True)

    df = df_raw.copy()
    if sel_year != "All":
        df = df[df['YEAR'] == sel_year]
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

    return df, granularity


# =============================================================================
# Row 1 — KPI cards
# =============================================================================
def _render_kpi_row(df: pd.DataFrame):
    total_customers  = int(df['CUSTOMER_CODE'].nunique()) if 'CUSTOMER_CODE' in df.columns else 0
    total_credit     = df['CLEAN_CREDIT_MB'].sum()          if 'CLEAN_CREDIT_MB' in df.columns else 0.0
    total_debt       = df['CURRENT_DEBT_MILLION_THB'].sum()  if 'CURRENT_DEBT_MILLION_THB' in df.columns else 0.0
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
# Row 2 left — Average Current Debt horizontal bar
# =============================================================================
def _render_avg_debt_bar(df: pd.DataFrame):
    ctrl1, ctrl2, _ = st.columns([1.2, 1.6, 3])
    with ctrl1:
        show_est = st.toggle("Show Est. Future Diff", value=False, key="show_est")
    with ctrl2:
        top_n = st.select_slider("Top N", options=[5, 10, 15, 20], value=10, key="top_n")

    if 'CUSTOMER_NAME' not in df.columns or 'CURRENT_DEBT_MILLION_THB' not in df.columns:
        st.info("Insufficient data.")
        return

    agg = (
        df.groupby('CUSTOMER_NAME', as_index=False)['CURRENT_DEBT_MILLION_THB']
        .mean()
        .rename(columns={'CURRENT_DEBT_MILLION_THB': 'AVG_DEBT'})
        .sort_values('AVG_DEBT', ascending=False)
        .head(top_n)
        .sort_values('AVG_DEBT', ascending=True)
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=agg['CUSTOMER_NAME'],
        x=agg['AVG_DEBT'],
        orientation='h',
        name='Avg Debt (MB)',
        marker_color=BAR_BASE,
        text=[f"{v:.1f}" for v in agg['AVG_DEBT']],
        textposition='outside',
        cliponaxis=False,
        textfont=dict(size=9, color=FONT_COLOR),
    ))

    if show_est and 'EST_DEBT' in df.columns:
        agg_est = (
            df.groupby('CUSTOMER_NAME', as_index=False)['EST_DEBT']
            .mean().rename(columns={'EST_DEBT': 'AVG_EST'})
        )
        agg = agg.merge(agg_est, on='CUSTOMER_NAME', how='left')
        agg['DIFF'] = (agg['AVG_EST'] - agg['AVG_DEBT']).clip(lower=0)
        diff_colors = [
            BAR_EST_OVER if (row.get('AVG_EST', 0) or 0) >= DEBT_THRESHOLD else BAR_EST
            for _, row in agg.iterrows()
        ]
        fig.add_trace(go.Bar(
            y=agg['CUSTOMER_NAME'],
            x=agg['DIFF'],
            orientation='h',
            name='Est. Future Diff',
            marker_color=diff_colors,
            text=[f"+{v:.1f}" if v > 0 else "" for v in agg['DIFF']],
            textposition='outside',
            cliponaxis=False,
            textfont=dict(size=9, color=BAR_EST_OVER),
        ))
        fig.update_layout(barmode='stack')

    bar_height = max(220, top_n * 26)
    apply_base_layout(fig, {
        'height': bar_height,
        'margin': dict(l=0, r=70, t=10, b=4),
        'xaxis': dict(
            title="Million THB", showgrid=True, gridcolor=GRID_COLOR,
            zeroline=False, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        'yaxis': dict(showgrid=False, color=FONT_COLOR, tickfont=dict(size=9)),
        'showlegend': show_est,
        'legend': dict(
            orientation='h', yanchor='bottom', y=1.02,
            xanchor='right', x=1, font=dict(size=9),
        ),
    })
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 2 right — Credit Risk Distribution donut + interactive detail table
# =============================================================================
def _render_risk_donut(df: pd.DataFrame):
    st.markdown(
        '<div style="font-size:9px;font-weight:700;letter-spacing:0.8px;'
        'text-transform:uppercase;color:#4a6fa5;margin-bottom:4px;">'
        'Credit Risk Distribution</div>',
        unsafe_allow_html=True,
    )

    if 'CURRENT_DEBT_MILLION_THB_PERCENT' not in df.columns or 'CUSTOMER_CODE' not in df.columns:
        st.info("No data.")
        return

    # Deduplicate to one row per customer (latest snapshot)
    snap = (
        df.sort_values('DATE', ascending=False).drop_duplicates(subset=['CUSTOMER_CODE'])
        if 'DATE' in df.columns
        else df.drop_duplicates(subset=['CUSTOMER_CODE'])
    )

    safe_mask   = snap['CURRENT_DEBT_MILLION_THB_PERCENT'] < DEBT_THRESHOLD
    danger_mask = snap['CURRENT_DEBT_MILLION_THB_PERCENT'] >= DEBT_THRESHOLD
    nodata_mask = snap['CURRENT_DEBT_MILLION_THB_PERCENT'].isna()

    safe_n   = int(safe_mask.sum())
    danger_n = int(danger_mask.sum())
    nodata_n = int(nodata_mask.sum())

    raw = [
        ('Safe < 80%',       safe_n,   PALETTE['safe'],   'safe'),
        ('High Risk >= 80%', danger_n, PALETTE['danger'], 'danger'),
        ('No Data',          nodata_n, PALETTE['nodata'], 'nodata'),
    ]
    segments = [(l, v, c, k) for l, v, c, k in raw if v > 0]
    if not segments:
        st.info("No data.")
        return

    fl, fv, fc, fk = zip(*segments)

    fig = go.Figure(go.Pie(
        labels=list(fl),
        values=list(fv),
        hole=0.60,
        marker=dict(colors=list(fc), line=dict(color='white', width=2)),
        textinfo='percent',
        textfont=dict(size=10, color='white'),
        hovertemplate='%{label}: %{value} customers (%{percent})<extra></extra>',
        # Store segment key in customdata for click identification
        customdata=list(fk),
    ))
    fig.add_annotation(
        text=f"<b>{safe_n + danger_n}</b>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=15, color='#1a2540'),
    )
    apply_base_layout(fig, {
        'height': 240,
        'margin': dict(l=0, r=0, t=4, b=0),
        'showlegend': True,
        'legend': dict(
            orientation='h', yanchor='bottom', y=-0.30,
            xanchor='center', x=0.5,
            font=dict(size=9), bgcolor='rgba(0,0,0,0)',
        ),
    })

    # Render the donut and capture click events via plotly_events
    # We use a session_state key to remember which segment is selected
    selected_key = st.session_state.get('donut_selected', None)

    # Render chart — use_container_width fits the column
    clicked = st.plotly_chart(
        fig,
        use_container_width=True,
        key="donut_chart",
        on_select="rerun",       # Streamlit >= 1.33: re-run on click
        selection_mode="points",
    )

    # Parse click: Streamlit returns selection info via the return value
    if clicked and hasattr(clicked, 'selection') and clicked.selection:
        pts = clicked.selection.get('points', [])
        if pts:
            label_clicked = pts[0].get('label', '')
            if 'Safe' in label_clicked:
                st.session_state['donut_selected'] = 'safe'
            elif 'High Risk' in label_clicked:
                st.session_state['donut_selected'] = 'danger'
            elif 'No Data' in label_clicked:
                st.session_state['donut_selected'] = 'nodata'
            else:
                st.session_state['donut_selected'] = None

    selected_key = st.session_state.get('donut_selected', None)

    # ----------------------------------------------------------------
    # Interactive detail table under the donut
    # ----------------------------------------------------------------
    if selected_key is not None:
        _render_donut_detail(snap, selected_key)


def _render_donut_detail(snap: pd.DataFrame, segment_key: str):
    """Render a compact detail table for the clicked donut segment."""

    # Filter rows for the selected segment
    if segment_key == 'safe':
        subset = snap[snap['CURRENT_DEBT_MILLION_THB_PERCENT'] < DEBT_THRESHOLD].copy()
        label  = "Safe Customers (Debt < 80%)"
        color  = PALETTE['safe']
    elif segment_key == 'danger':
        subset = snap[snap['CURRENT_DEBT_MILLION_THB_PERCENT'] >= DEBT_THRESHOLD].copy()
        label  = "High Risk Customers (Debt >= 80%)"
        color  = PALETTE['danger']
    else:
        subset = snap[snap['CURRENT_DEBT_MILLION_THB_PERCENT'].isna()].copy()
        label  = "No Data Customers"
        color  = PALETTE['nodata']

    # Desired columns — show only those that exist
    col_map = {
        'CUSTOMER_NAME':                   'Customer Name',
        'CLEAN_CREDIT_MB':                 'Clean Credit (MB)',
        'CURRENT_DEBT_MILLION_THB':        'Current Debt (MB)',
        'CURRENT_DEBT_MILLION_THB_PERCENT':'Debt %',
        'EST_FURTHER_AMOUNT':              'Est. Further Diff',
    }
    avail = {k: v for k, v in col_map.items() if k in subset.columns}

    if subset.empty or not avail:
        st.info("No records in this segment.")
        return

    subset = (
        subset[list(avail.keys())]
        .sort_values(
            'CURRENT_DEBT_MILLION_THB_PERCENT',
            ascending=(segment_key == 'safe'),
        )
        .reset_index(drop=True)
    )
    subset.rename(columns=avail, inplace=True)

    # Toggle between Top 5 and All
    show_all = st.toggle(
        f"Show all ({len(subset)})",
        value=False,
        key=f"donut_showall_{segment_key}",
    )
    display_df = subset if show_all else subset.head(5)

    # Section label with colored bar
    st.markdown(
        f'<div style="font-size:9px;font-weight:700;color:{color};'
        f'border-left:3px solid {color};padding-left:6px;margin-bottom:4px;">'
        f'{label}</div>',
        unsafe_allow_html=True,
    )

    # Build column_config dynamically
    col_cfg = {}
    if 'Clean Credit (MB)' in display_df.columns:
        col_cfg['Clean Credit (MB)'] = st.column_config.NumberColumn(
            'Clean Credit (MB)', format="%.2f"
        )
    if 'Current Debt (MB)' in display_df.columns:
        col_cfg['Current Debt (MB)'] = st.column_config.NumberColumn(
            'Current Debt (MB)', format="%.2f"
        )
    if 'Debt %' in display_df.columns:
        col_cfg['Debt %'] = st.column_config.NumberColumn(
            'Debt %', format="%.2f"
        )
    if 'Est. Further Diff' in display_df.columns:
        col_cfg['Est. Further Diff'] = st.column_config.NumberColumn(
            'Est. Further Diff', format="%.2f"
        )

    st.dataframe(
        display_df,
        column_config=col_cfg,
        use_container_width=True,
        height=min(180, 36 + len(display_df) * 35),
        hide_index=True,
    )


# =============================================================================
# Row 3 left — Debt by Product Type (vertical bar + % in legend)
# =============================================================================
def _render_debt_by_type(df: pd.DataFrame):
    st.markdown(
        '<div style="font-size:9px;font-weight:700;letter-spacing:0.8px;'
        'text-transform:uppercase;color:#4a6fa5;margin-bottom:4px;">'
        'Debt by Product Type</div>',
        unsafe_allow_html=True,
    )
    if 'TYPE' not in df.columns or 'CURRENT_DEBT_MILLION_THB' not in df.columns:
        st.info("No TYPE data.")
        return

    by_type = (
        df.groupby('TYPE', as_index=False)['CURRENT_DEBT_MILLION_THB']
        .sum()
        .rename(columns={'CURRENT_DEBT_MILLION_THB': 'TOTAL'})
        .sort_values('TOTAL', ascending=False)
        .reset_index(drop=True)
    )
    total_all   = by_type['TOTAL'].sum()
    by_type['PCT'] = (
        (by_type['TOTAL'] / total_all * 100).round(1)
        if total_all > 0 else 0.0
    )

    fig = go.Figure()
    for i, row in by_type.iterrows():
        color = TYPE_COLORS[i % len(TYPE_COLORS)]
        fig.add_trace(go.Bar(
            x=[row['TYPE']],
            y=[row['TOTAL']],
            name=f"{row['TYPE']} ({row['PCT']}%)",
            marker_color=color,
            text=[f"{row['TOTAL']:,.1f}"],
            textposition='outside',
            cliponaxis=False,
            textfont=dict(size=9, color=FONT_COLOR),
            hovertemplate=(
                f"<b>{row['TYPE']}</b><br>"
                f"Total Debt: {row['TOTAL']:,.1f} MB<br>"
                f"Share: {row['PCT']}%<extra></extra>"
            ),
        ))

    apply_base_layout(fig, {
        'height': 250,
        'margin': dict(l=0, r=8, t=4, b=4),
        'barmode': 'group',
        'xaxis': dict(
            showgrid=False, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        'yaxis': dict(
            title="Total Debt (MB)", showgrid=True,
            gridcolor=GRID_COLOR, color=FONT_COLOR, tickfont=dict(size=9),
        ),
        'showlegend': True,
        'legend': dict(
            orientation='v',
            yanchor='top', y=1.0,
            xanchor='left', x=1.02,
            font=dict(size=8),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#d0dae6',
            borderwidth=1,
        ),
    })
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 3 right — Avg Debt % Trend
# =============================================================================
def _render_trend(df: pd.DataFrame, granularity: str):
    st.markdown(
        '<div style="font-size:9px;font-weight:700;letter-spacing:0.8px;'
        'text-transform:uppercase;color:#4a6fa5;margin-bottom:4px;">'
        f'Avg Debt % — {granularity} View</div>',
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

    bar_colors = [
        TREND_DANGER if v >= 80 else TREND_SAFE
        for v in trend['AVG_PCT_DISP']
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=trend['X'],
        y=trend['AVG_PCT_DISP'],
        marker_color=bar_colors,
        text=[f"{v:.1f}%" for v in trend['AVG_PCT_DISP']],
        textposition='outside',
        cliponaxis=False,
        textfont=dict(size=8, color=FONT_COLOR),
        hovertemplate='%{x}<br>Avg Debt: %{y:.2f}%<extra></extra>',
    ))
    fig.add_hline(
        y=80, line_dash='dash',
        line_color=PALETTE['threshold'],
        line_width=1.2,
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
            title="Avg Debt %", ticksuffix="%",
            showgrid=True, gridcolor=GRID_COLOR,
            color=FONT_COLOR, range=[0, max_y],
            tickformat='.2f',
        ),
        'showlegend': False,
    })
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Row 4 — Customer table
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
            df[avail_cols]
            .drop_duplicates(subset=dedup_key)
            .sort_values('CLEAN_CREDIT_MB', ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
    elif mode == "Top Risk Customers" and 'CURRENT_DEBT_MILLION_THB_PERCENT' in df.columns:
        tbl = (
            df[avail_cols]
            .drop_duplicates(subset=dedup_key)
            .sort_values('CURRENT_DEBT_MILLION_THB_PERCENT', ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
    else:
        st.info("No data.")
        return

    st.dataframe(
        tbl,
        column_config={
            "CUSTOMER_NAME": st.column_config.TextColumn(
                "Customer", width="large"
            ),
            "TYPE": st.column_config.TextColumn(
                "Type", width="small"
            ),
            "CLEAN_CREDIT_MB": st.column_config.NumberColumn(
                "Clean Credit (MB)", format="%.2f", width="medium"
            ),
            "CURRENT_DEBT_MILLION_THB": st.column_config.NumberColumn(
                "Debt (MB)", format="%.2f", width="medium"
            ),
            "CURRENT_DEBT_MILLION_THB_PERCENT": st.column_config.NumberColumn(
                "Debt %", format="%.2f", width="small"
            ),
        },
        use_container_width=True,
        height=320,
        hide_index=True,
    )


# =============================================================================
# Utility
# =============================================================================
def _no_data_banner():
    st.markdown("""
    <div style="background:#f8f9fc;border:1.5px solid #d0dae6;border-radius:10px;
    padding:28px;text-align:center;margin-top:32px;">
        <div style="font-size:13px;font-weight:600;color:#1a2540;margin-bottom:6px;">
            No Data Available
        </div>
        <div style="font-size:11px;color:#7a90a8;">
            Go to <b>Loading and Processing Data</b> to upload and process files first.
        </div>
    </div>
    """, unsafe_allow_html=True)