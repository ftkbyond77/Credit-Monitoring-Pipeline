import streamlit as st
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import time

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Nuclear & Quantum Physics Explorer",
    page_icon="⚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL CSS  (white, professional, no emoji)
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Root & body ── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    background-color: #ffffff;
    color: #1a1a2e;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b2a 0%, #1b2838 100%);
}
[data-testid="stSidebar"] * { color: #e0e6f0 !important; }
[data-testid="stSidebar"] .stRadio label { font-weight: 600; }

/* ── Hero banner ── */
.hero-banner {
    background: linear-gradient(135deg, #0d1b2a 0%, #1a3a5c 50%, #0d2137 100%);
    padding: 64px 48px;
    border-radius: 16px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
}
.hero-banner h1 {
    color: #ffffff;
    font-size: 2.8rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0 0 12px 0;
    line-height: 1.15;
}
.hero-banner p {
    color: #a8c7e8;
    font-size: 1.1rem;
    margin: 0;
    max-width: 640px;
    line-height: 1.7;
}
.hero-badge {
    display: inline-block;
    background: rgba(64,180,255,0.15);
    border: 1px solid rgba(64,180,255,0.4);
    color: #40b4ff;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 100px;
    margin-bottom: 20px;
}

/* ── Section heading ── */
.section-title {
    font-size: 1.65rem;
    font-weight: 700;
    color: #0d1b2a;
    border-left: 4px solid #0077b6;
    padding-left: 14px;
    margin: 36px 0 20px 0;
}
.section-sub {
    color: #555e70;
    font-size: 0.97rem;
    margin-bottom: 24px;
    line-height: 1.6;
}

/* ── Metric cards ── */
.metric-grid { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }
.metric-card {
    flex: 1; min-width: 180px;
    background: #f4f8fc;
    border: 1px solid #d0e4f4;
    border-radius: 12px;
    padding: 22px 20px;
}
.metric-card .label {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #4a6fa5;
    margin-bottom: 6px;
}
.metric-card .value {
    font-size: 1.65rem;
    font-weight: 800;
    color: #0d1b2a;
}
.metric-card .desc {
    font-size: 0.8rem;
    color: #778899;
    margin-top: 4px;
}

/* ── Info box ── */
.info-box {
    background: #f0f7ff;
    border-left: 4px solid #0077b6;
    border-radius: 0 10px 10px 0;
    padding: 18px 22px;
    margin: 18px 0;
    font-size: 0.94rem;
    color: #1a3a5c;
    line-height: 1.65;
}

/* ── Formula box ── */
.formula-box {
    background: #0d1b2a;
    color: #40b4ff;
    font-family: 'Courier New', monospace;
    font-size: 1.1rem;
    border-radius: 10px;
    padding: 18px 24px;
    text-align: center;
    margin: 16px 0;
    letter-spacing: 0.5px;
}

/* ── Dimension badge ── */
.dim-badge {
    background: linear-gradient(135deg, #023e8a, #0077b6);
    color: white;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 3px 12px;
    border-radius: 100px;
    display: inline-block;
    margin-bottom: 10px;
}

/* ── Tab strip ── */
div[data-baseweb="tab-list"] {
    background: #f0f4f8;
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
}
div[data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    font-weight: 600;
    color: #4a6fa5;
}
div[aria-selected="true"][data-baseweb="tab"] {
    background: #ffffff;
    color: #0077b6;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12);
}

/* ── Plotly container ── */
.stPlotlyChart { border-radius: 12px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Nuclear & Quantum Physics")
    st.markdown("---")
    section = st.radio(
        "Navigate",
        [
            "Overview",
            "Nuclear Reactions",
            "Quantum Wave Functions",
            "3D Atomic Orbitals",
            "4D Tesseract",
            "Particle Collider",
            "Quantum Entanglement",
            "Nuclear Reactor Sim",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#7090b0;'>Data is illustrative and uses real physical constants.</small>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# HERO BANNER  (shown on Overview)
# ─────────────────────────────────────────────
if section == "Overview":
    st.markdown("""
    <div class="hero-banner">
      <div class="hero-badge">Interactive Science Platform</div>
      <h1>Nuclear Power &amp;<br>Quantum Physics</h1>
      <p>
        Explore the fundamental forces of nature — from the nucleus of a uranium atom
        to the probabilistic fabric of quantum reality. Interactive 3D and 4D
        visualisations, real physical constants, and live simulations.
      </p>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  1. OVERVIEW
# ══════════════════════════════════════════════
if section == "Overview":
    st.markdown('<div class="section-title">Physical Constants</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="metric-grid">
        <div class="metric-card"><div class="label">Speed of Light</div>
            <div class="value">299,792,458</div><div class="desc">m/s &mdash; c</div></div>
        <div class="metric-card"><div class="label">Planck Constant</div>
            <div class="value">6.626 &times; 10<sup>-34</sup></div><div class="desc">J&middot;s &mdash; h</div></div>
        <div class="metric-card"><div class="label">Fine Structure</div>
            <div class="value">1 / 137.036</div><div class="desc">&alpha; &mdash; electromagnetic coupling</div></div>
        <div class="metric-card"><div class="label">Proton Mass</div>
            <div class="value">938.3 MeV/c&sup2;</div><div class="desc">Rest mass</div></div>
        <div class="metric-card"><div class="label">Electron Mass</div>
            <div class="value">0.511 MeV/c&sup2;</div><div class="desc">Rest mass</div></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown('<div class="section-title">Binding Energy per Nucleon</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">The curve that explains why fission liberates energy from heavy nuclei and fusion releases energy from light ones.</div>', unsafe_allow_html=True)

        # Bethe-Weizsacker binding energy approximation
        elements = {
            'H-2':2,'He-4':4,'Li-6':6,'C-12':12,'O-16':16,'Fe-56':56,
            'Ni-62':62,'Mo-96':96,'Sn-120':120,'Pb-208':208,'U-235':235,'U-238':238
        }
        Z_vals = {'H-2':1,'He-4':2,'Li-6':3,'C-12':6,'O-16':8,'Fe-56':26,
                  'Ni-62':28,'Mo-96':42,'Sn-120':50,'Pb-208':82,'U-235':92,'U-238':92}
        be_data = []
        for name, A in elements.items():
            Z = Z_vals[name]
            N = A - Z
            if A < 2: continue
            # Bethe-Weizsacker semi-empirical
            aV, aS, aC, aA, aP = 15.85, 18.34, 0.711, 23.21, 12.0
            delta = aP / (A**0.5) if (Z % 2 == 0 and N % 2 == 0) else (
                    -aP / (A**0.5) if (Z % 2 == 1 and N % 2 == 1) else 0)
            BE = (aV*A - aS*(A**(2/3)) - aC*Z*(Z-1)/(A**(1/3))
                  - aA*((N-Z)**2)/A + delta)
            be_data.append({'Nucleus': name, 'A': A, 'BE_per_A': BE/A})
        df_be = pd.DataFrame(be_data)

        A_cont = np.linspace(2, 240, 300)
        be_cont = []
        for A in A_cont:
            Z = A / 2.3
            N = A - Z
            aV,aS,aC,aA = 15.85,18.34,0.711,23.21
            be = (aV*A - aS*(A**(2/3)) - aC*Z*(Z-1)/(A**(1/3)) - aA*((N-Z)**2)/A) / A
            be_cont.append(be)

        fig_be = go.Figure()
        fig_be.add_trace(go.Scatter(
            x=A_cont, y=be_cont, mode='lines',
            line=dict(color='#0077b6', width=2.5), name='Semi-empirical curve', showlegend=True))
        fig_be.add_trace(go.Scatter(
            x=df_be['A'], y=df_be['BE_per_A'], mode='markers+text',
            marker=dict(size=11, color='#e63946', symbol='circle', line=dict(width=1.5, color='white')),
            text=df_be['Nucleus'], textposition='top center',
            textfont=dict(size=9, color='#333'), name='Known nuclei'))
        fig_be.add_vline(x=56, line_dash='dash', line_color='#f4a261',
                         annotation_text='Fe-56 (peak)', annotation_position='top right',
                         annotation_font_size=10)
        fig_be.update_layout(
            height=360, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            xaxis=dict(title='Mass Number (A)', gridcolor='#e8eef4', zeroline=False),
            yaxis=dict(title='Binding Energy / Nucleon (MeV)', gridcolor='#e8eef4', zeroline=False),
            legend=dict(x=0.65, y=0.08, bgcolor='rgba(255,255,255,0.85)',
                        bordercolor='#d0d8e4', borderwidth=1),
            margin=dict(l=10, r=10, t=10, b=10), font=dict(family='Inter,Segoe UI,sans-serif'))
        st.plotly_chart(fig_be, use_container_width=True)

    with col2:
        st.markdown('<div class="section-title">Nuclear Forces</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        <b>Strong Nuclear Force</b> — binds protons and neutrons inside the nucleus with a range
        of ~1 fm (10<sup>-15</sup> m). It is ~100x stronger than the electromagnetic force at
        that scale but drops to zero beyond ~2-3 fm.<br><br>
        <b>Weak Nuclear Force</b> — responsible for beta decay, converting neutrons to protons
        (or vice versa). Mediated by W and Z bosons discovered at CERN in 1983.<br><br>
        <b>Key insight:</b> The binding energy curve means that <em>splitting heavy nuclei</em>
        (fission) and <em>joining light nuclei</em> (fusion) both release net energy — both
        move nuclei toward the Fe-56 peak.
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="formula-box">E = mc&sup2; &nbsp;&nbsp;|&nbsp;&nbsp; &Delta;E = &Delta;m &times; c&sup2;</div>', unsafe_allow_html=True)

        # Fundamental forces spider
        categories = ['Relative Strength','Range','Mediator Mass','Discovery Year (scaled)','Coupling']
        forces_data = {
            'Strong':     [100, 85, 60, 70, 90],
            'Electromagnetic': [72, 100, 0, 90, 72],
            'Weak':       [40, 10, 100, 88, 38],
            'Gravity':    [2, 100, 0, 95, 1],
        }
        colors = ['#0077b6','#f4a261','#e63946','#6a994e']
        fig_sp = go.Figure()
        for (fname, vals), col in zip(forces_data.items(), colors):
            fig_sp.add_trace(go.Scatterpolar(
                r=vals + [vals[0]], theta=categories + [categories[0]],
                fill='toself', name=fname,
                line=dict(color=col, width=2),
                fillcolor=col.replace('#','rgba(').replace(')', ',0.08)') if '#' in col else col,
                opacity=0.85))
        fig_sp.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0,110], gridcolor='#e0e8f0',
                                tickfont=dict(size=8), showticklabels=False),
                angularaxis=dict(gridcolor='#e0e8f0', tickfont=dict(size=10, color='#333'))),
            showlegend=True, height=310,
            paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
            legend=dict(x=0.75, y=1.0, bgcolor='rgba(255,255,255,0.9)', borderwidth=1, bordercolor='#ccc'),
            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_sp, use_container_width=True)


# ══════════════════════════════════════════════
#  2. NUCLEAR REACTIONS
# ══════════════════════════════════════════════
elif section == "Nuclear Reactions":
    st.markdown('<div class="section-title">Nuclear Reactions — Fission vs Fusion</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Compare the energy released per reaction and the conditions required for each process.</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Fission (U-235)", "Fusion (D-T)"])

    with tab1:
        col_a, col_b = st.columns([1.3, 1])
        with col_a:
            st.markdown("""
            <div class="formula-box">
            <sup>235</sup>U + n &rarr; <sup>141</sup>Ba + <sup>92</sup>Kr + 3n + 200 MeV
            </div>
            """, unsafe_allow_html=True)

            # Fission fragment kinetic energy distribution (Gaussian approximation)
            mass_numbers = np.arange(70, 165)
            light_peak = np.exp(-((mass_numbers - 95)**2) / (2*12**2))
            heavy_peak = np.exp(-((mass_numbers - 140)**2) / (2*10**2))
            yield_dist = (light_peak + heavy_peak) * 6.5  # % fission yield

            fig_fiss = go.Figure()
            fig_fiss.add_trace(go.Scatter(
                x=mass_numbers, y=yield_dist, mode='lines',
                fill='tozeroy', line=dict(color='#0077b6', width=2.5),
                fillcolor='rgba(0,119,182,0.12)', name='Fission Yield'))
            fig_fiss.add_annotation(x=95, y=7.1, text="Light fragments<br>A ~ 90–100",
                                    showarrow=True, arrowhead=2, ax=40, ay=-30,
                                    font=dict(size=10, color='#0077b6'))
            fig_fiss.add_annotation(x=140, y=7.1, text="Heavy fragments<br>A ~ 135–145",
                                    showarrow=True, arrowhead=2, ax=-40, ay=-30,
                                    font=dict(size=10, color='#e63946'))
            fig_fiss.update_layout(
                title=dict(text='U-235 Fission Fragment Mass Distribution', font=dict(size=13), x=0),
                height=320, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
                xaxis=dict(title='Fragment Mass Number (A)', gridcolor='#e8eef4'),
                yaxis=dict(title='Relative Fission Yield (%)', gridcolor='#e8eef4'),
                margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_fiss, use_container_width=True)

        with col_b:
            st.markdown("""
            <div class="info-box">
            <b>U-235 Fission facts:</b><br>
            - Energy per fission: <b>~200 MeV</b><br>
            - 1 kg U-235 = energy equivalent of ~20,000 tonnes of TNT<br>
            - Critical mass (bare sphere): ~52 kg<br>
            - Chain reaction: each fission releases ~2.4 neutrons on average<br>
            - Fuel enrichment: natural U has 0.72% U-235; reactors use 3–5%
            </div>
            """, unsafe_allow_html=True)

            # Chain reaction neutron multiplier
            k_vals = np.linspace(0.7, 1.3, 200)
            n_gens = 20
            n_final = k_vals ** n_gens
            n_final = np.clip(n_final, 0, 50)

            fig_k = go.Figure()
            fig_k.add_trace(go.Scatter(
                x=k_vals, y=n_final, mode='lines',
                line=dict(color='#e63946', width=2.5), name='Neutron pop. after 20 gen.'))
            fig_k.add_vline(x=1.0, line_dash='dash', line_color='#f4a261',
                            annotation_text='k=1 (critical)', annotation_position='top left',
                            annotation_font_size=10)
            fig_k.update_layout(
                title=dict(text='Neutron Population vs. Multiplication Factor k', font=dict(size=11), x=0),
                height=220, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
                xaxis=dict(title='k (effective multiplication factor)', gridcolor='#e8eef4'),
                yaxis=dict(title='Relative neutron count', gridcolor='#e8eef4'),
                margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig_k, use_container_width=True)

    with tab2:
        col_a, col_b = st.columns([1.3, 1])
        with col_a:
            st.markdown("""
            <div class="formula-box">
            D + T &rarr; <sup>4</sup>He (3.5 MeV) + n (14.1 MeV)
            </div>
            """, unsafe_allow_html=True)

            # Fusion cross-section vs energy (Lawson criterion region)
            energy_keV = np.linspace(1, 200, 400)
            # Approximate D-T cross-section (parametric, barn)
            sigma_DT = 5.5 * np.exp(-((energy_keV - 64) ** 2) / (2 * 28**2))

            fig_fus = go.Figure()
            fig_fus.add_trace(go.Scatter(
                x=energy_keV, y=sigma_DT, mode='lines',
                fill='tozeroy', line=dict(color='#e63946', width=2.5),
                fillcolor='rgba(230,57,70,0.1)', name='D-T cross-section'))
            fig_fus.add_vline(x=64, line_dash='dash', line_color='#f4a261',
                              annotation_text='Peak ~64 keV', annotation_position='top right',
                              annotation_font_size=10)
            fig_fus.update_layout(
                title=dict(text='D-T Fusion Cross-Section vs. Ion Energy', font=dict(size=13), x=0),
                height=320, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
                xaxis=dict(title='Center-of-mass Energy (keV)', gridcolor='#e8eef4'),
                yaxis=dict(title='Cross-section (barn, relative)', gridcolor='#e8eef4'),
                margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig_fus, use_container_width=True)

        with col_b:
            st.markdown("""
            <div class="info-box">
            <b>D-T Fusion facts:</b><br>
            - Energy per reaction: <b>17.6 MeV</b><br>
            - Required temperature: <b>~150 million K</b><br>
            - Lawson criterion: n &times; &tau; &ge; 10<sup>20</sup> m<sup>-3</sup>s<br>
            - ITER (France): first plasma 2025, Q>10 target<br>
            - 1 kg D-T fuel = energy of ~85 million litres of oil<br>
            - Deuterium source: seawater (virtually limitless)
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            <div class="metric-grid">
                <div class="metric-card"><div class="label">Fusion gain Q</div>
                    <div class="value">Q &gt; 10</div><div class="desc">ITER target</div></div>
                <div class="metric-card"><div class="label">Plasma temp.</div>
                    <div class="value">150M K</div><div class="desc">10x hotter than the Sun's core</div></div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  3. QUANTUM WAVE FUNCTIONS
# ══════════════════════════════════════════════
elif section == "Quantum Wave Functions":
    st.markdown('<div class="section-title">Quantum Wave Functions</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">The Schrodinger equation governs how quantum probability amplitudes evolve. Explore hydrogen energy levels and wave packet dynamics.</div>', unsafe_allow_html=True)
    st.markdown('<div class="formula-box">i&hbar; &part;&Psi;/&part;t = [- &hbar;&sup2;/2m &nabla;&sup2; + V(r)] &Psi;</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Hydrogen Energy Levels — Bohr Model**")
        n_levels = 8
        En = -13.6 / np.arange(1, n_levels+1)**2  # eV
        fig_levels = go.Figure()
        for n, e in enumerate(En, 1):
            fig_levels.add_shape(type='line', x0=0.2, x1=0.8, y0=e, y1=e,
                                 line=dict(color='#0077b6', width=2))
            label = f"n={n} ({e:.2f} eV)"
            if n <= 5:
                fig_levels.add_annotation(x=0.85, y=e, text=label, showarrow=False,
                                          font=dict(size=9.5, color='#333'), xanchor='left')
        # Transitions (Lyman, Balmer)
        lyman_color, balmer_color = '#e63946', '#f4a261'
        for n_upper in range(2, 5):
            fig_levels.add_annotation(
                x=0.35, y=(En[0]+En[n_upper-1])/2,
                text=f"Lyman {n_upper}->1",
                showarrow=True,
                ax=0, ay=0,
                axref='pixel', ayref='pixel',
                arrowhead=2, arrowcolor=lyman_color,
                font=dict(size=8, color=lyman_color),
                xanchor='right')
        fig_levels.update_layout(
            height=380, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            xaxis=dict(visible=False, range=[0,1.3]),
            yaxis=dict(title='Energy (eV)', gridcolor='#e8eef4', zeroline=True,
                       zerolinecolor='#ccc'),
            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_levels, use_container_width=True)

    with col2:
        st.markdown("**Gaussian Wave Packet Evolution (1D, free particle)**")
        x = np.linspace(-10, 10, 600)
        t_steps = st.slider("Time step t (units of hbar/eV)", 0.0, 5.0, 0.0, 0.1, key='wvt')
        k0, sigma0 = 2.0, 1.0
        hbar, m = 1.0, 1.0
        vg = hbar * k0 / m
        x0 = -5 + vg * t_steps
        sigma_t = sigma0 * np.sqrt(1 + (hbar * t_steps / (m * sigma0**2))**2)
        psi_real = (np.exp(-(x - x0)**2 / (2*sigma_t**2)) /
                    (sigma_t * np.sqrt(2*np.pi))**0.5 *
                    np.cos(k0*(x - x0) - hbar*k0**2/(2*m)*t_steps))
        psi_imag = (np.exp(-(x - x0)**2 / (2*sigma_t**2)) /
                    (sigma_t * np.sqrt(2*np.pi))**0.5 *
                    np.sin(k0*(x - x0) - hbar*k0**2/(2*m)*t_steps))
        prob_density = psi_real**2 + psi_imag**2

        fig_wv = go.Figure()
        fig_wv.add_trace(go.Scatter(x=x, y=psi_real, mode='lines',
                                    line=dict(color='#0077b6', width=2), name='Re(psi)'))
        fig_wv.add_trace(go.Scatter(x=x, y=psi_imag, mode='lines',
                                    line=dict(color='#e63946', width=1.5, dash='dot'), name='Im(psi)'))
        fig_wv.add_trace(go.Scatter(x=x, y=prob_density, mode='lines',
                                    fill='tozeroy',
                                    line=dict(color='#2a9d8f', width=2),
                                    fillcolor='rgba(42,157,143,0.1)', name='|psi|^2'))
        fig_wv.update_layout(
            height=380, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            xaxis=dict(title='x (a.u.)', gridcolor='#e8eef4'),
            yaxis=dict(title='Amplitude', gridcolor='#e8eef4'),
            legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.85)', borderwidth=1,
                        bordercolor='#ccc'),
            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_wv, use_container_width=True)
        st.markdown("""
        <div class="info-box">
        The wave packet spreads over time — a consequence of the <b>uncertainty principle</b>:
        &Delta;x &middot; &Delta;p &ge; &hbar;/2. A narrower initial packet has broader momentum
        distribution, causing faster spreading.
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  4. 3D ATOMIC ORBITALS
# ══════════════════════════════════════════════
elif section == "3D Atomic Orbitals":
    st.markdown('<div class="section-title">3D Hydrogen Atomic Orbitals</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Volumetric probability density |psi(r,theta,phi)|^2 for hydrogen-like wave functions. Use the controls to explore different quantum states.</div>', unsafe_allow_html=True)
    st.markdown('<div class="dim-badge">3D Visualisation</div>', unsafe_allow_html=True)

    from scipy.special import sph_harm, genlaguerre, factorial
    import scipy.special as sp

    col_ctrl, col_vis = st.columns([1, 2.5])
    with col_ctrl:
        n_qn = st.selectbox("Principal n", [1,2,3,4], index=2)
        l_options = list(range(0, n_qn))
        l_qn = st.selectbox("Angular l", l_options, index=min(1, len(l_options)-1))
        m_options = list(range(-l_qn, l_qn+1))
        m_qn = st.selectbox("Magnetic m", m_options, index=l_qn)
        n_pts = st.slider("Resolution", 30, 60, 40, 5)
        iso_frac = st.slider("Isosurface threshold (%)", 5, 30, 10, 1)

        orbital_names = {(1,0):'1s',(2,0):'2s',(2,1):'2p',(3,0):'3s',(3,1):'3p',(3,2):'3d',(4,0):'4s',(4,1):'4p',(4,2):'4d',(4,3):'4f'}
        name = orbital_names.get((n_qn, l_qn), f'{n_qn}{chr(ord("s")+l_qn)}')
        st.markdown(f"**Orbital: {name}, m={m_qn}**")

    with col_vis:
        # Compute psi^2 on a 3D grid
        a0 = 1.0  # Bohr radius units
        r_max = 4 * n_qn * (n_qn + 1) * a0
        coords = np.linspace(-r_max, r_max, n_pts)
        X, Y, Z = np.meshgrid(coords, coords, coords, indexing='ij')
        R = np.sqrt(X**2 + Y**2 + Z**2) + 1e-12
        Theta = np.arccos(np.clip(Z/R, -1, 1))
        Phi = np.arctan2(Y, X)

        # Radial part
        rho = 2 * R / (n_qn * a0)
        norm_radial = np.sqrt(
            (2/(n_qn*a0))**3 *
            factorial(n_qn - l_qn - 1) / (2*n_qn*factorial(n_qn + l_qn)**3)
        )
        L = genlaguerre(n_qn - l_qn - 1, 2*l_qn + 1)(rho)
        radial = norm_radial * np.exp(-rho/2) * rho**l_qn * L

        # Angular part
        Ylm = sph_harm(abs(m_qn), l_qn, Phi, Theta)
        if m_qn > 0:
            angular = (Ylm + np.conj(Ylm)) / np.sqrt(2)
        elif m_qn < 0:
            angular = (Ylm - np.conj(Ylm)) / (1j*np.sqrt(2))
        else:
            angular = Ylm
        angular = np.real(angular)

        psi2 = (radial * angular)**2
        psi2_norm = psi2 / np.max(psi2)

        iso_val = iso_frac / 100.0
        fig_orb = go.Figure(data=go.Isosurface(
            x=X.flatten(), y=Y.flatten(), z=Z.flatten(),
            value=psi2_norm.flatten(),
            isomin=iso_val * 0.5,
            isomax=iso_val * 1.5,
            surface_count=3,
            colorscale=[
                [0.0, 'rgba(0,100,180,0.05)'],
                [0.3, 'rgba(0,150,220,0.3)'],
                [0.7, 'rgba(100,200,255,0.7)'],
                [1.0, 'rgba(255,255,255,1.0)'],
            ],
            caps=dict(x_show=False, y_show=False, z_show=False),
            lighting=dict(ambient=0.7, diffuse=0.8, roughness=0.5, specular=1.0, fresnel=0.5),
            lightposition=dict(x=100, y=200, z=300),
            showscale=False,
        ))
        axis_range = [-r_max*0.7, r_max*0.7]
        fig_orb.update_layout(
            scene=dict(
                xaxis=dict(title='x (a0)', range=axis_range, backgroundcolor='#f4f8fc',
                           gridcolor='#d0dce8', showbackground=True),
                yaxis=dict(title='y (a0)', range=axis_range, backgroundcolor='#f4f8fc',
                           gridcolor='#d0dce8', showbackground=True),
                zaxis=dict(title='z (a0)', range=axis_range, backgroundcolor='#f4f8fc',
                           gridcolor='#d0dce8', showbackground=True),
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
                bgcolor='#f8fbff',
            ),
            height=500,
            paper_bgcolor='#ffffff',
            margin=dict(l=0, r=0, t=0, b=0),
            title=dict(text=f'Hydrogen {name} orbital (n={n_qn}, l={l_qn}, m={m_qn}) — probability density',
                       font=dict(size=13, color='#1a1a2e'), x=0.01, y=0.98),
        )
        st.plotly_chart(fig_orb, use_container_width=True)


# ══════════════════════════════════════════════
#  5. 4D TESSERACT
# ══════════════════════════════════════════════
elif section == "4D Tesseract":
    st.markdown('<div class="section-title">4D Hypercube — Tesseract</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">A tesseract is to a cube as a cube is to a square. We project the 4D object into 3D space, then display the 3D projection. Rotate the w-axis to see the 4D structure unfold.</div>', unsafe_allow_html=True)
    st.markdown('<div class="dim-badge">4D Projection Visualisation</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    In 4D space, a tesseract has <b>16 vertices</b>, <b>32 edges</b>, <b>24 square faces</b>, and <b>8 cubic cells</b>.
    Each vertex is at (+-1, +-1, +-1, +-1). We rotate in the XW or YW plane and project orthographically
    onto 3D, then display the 3D projection interactively.
    </div>
    """, unsafe_allow_html=True)

    col_ctrl2, col_tess = st.columns([1, 2.8])
    with col_ctrl2:
        angle_xw = st.slider("Rotate XW plane (deg)", 0, 360, 30, 3)
        angle_yw = st.slider("Rotate YW plane (deg)", 0, 360, 0, 3)
        angle_zw = st.slider("Rotate ZW plane (deg)", 0, 360, 0, 3)
        perspective = st.checkbox("Perspective projection", value=True)
        d_persp = st.slider("Perspective distance", 1.5, 5.0, 2.5, 0.1,
                             disabled=not perspective)

    with col_tess:
        # 16 vertices of the tesseract
        verts_4d = np.array([[x, y, z, w]
                             for x in [-1,1] for y in [-1,1]
                             for z in [-1,1] for w in [-1,1]], dtype=float)

        # Build edges: two vertices connected if they differ in exactly one coordinate
        edges = []
        for i in range(16):
            for j in range(i+1, 16):
                diff = np.sum(np.abs(verts_4d[i] - verts_4d[j]))
                if abs(diff - 2.0) < 1e-6:
                    edges.append((i, j))

        # Rotation matrices in 4D
        def rot4d(angle_deg, plane='xw'):
            a = np.radians(angle_deg)
            R = np.eye(4)
            idx = {'xw':(0,3),'yw':(1,3),'zw':(2,3),'xy':(0,1),'xz':(0,2),'yz':(1,2)}[plane]
            i, j = idx
            R[i,i] = np.cos(a);  R[i,j] = -np.sin(a)
            R[j,i] = np.sin(a);  R[j,j] =  np.cos(a)
            return R

        Rxw = rot4d(angle_xw, 'xw')
        Ryw = rot4d(angle_yw, 'yw')
        Rzw = rot4d(angle_zw, 'zw')
        R_total = Rzw @ Ryw @ Rxw
        verts_rot = (R_total @ verts_4d.T).T

        # Project 4D -> 3D
        if perspective:
            w = verts_rot[:, 3]
            factor = d_persp / (d_persp - w)
            verts_3d = verts_rot[:, :3] * factor[:, np.newaxis]
        else:
            verts_3d = verts_rot[:, :3]

        # Build Plotly figure
        edge_x, edge_y, edge_z = [], [], []
        for i, j in edges:
            edge_x += [verts_3d[i,0], verts_3d[j,0], None]
            edge_y += [verts_3d[i,1], verts_3d[j,1], None]
            edge_z += [verts_3d[i,2], verts_3d[j,2], None]

        # Color edges by the w-coordinate of the midpoint
        w_mid = np.array([(verts_rot[i,3] + verts_rot[j,3])/2 for i,j in edges])
        w_norm = (w_mid - w_mid.min()) / (w_mid.ptp() + 1e-9)

        fig_tess = go.Figure()
        # Draw each edge with color
        cmap = px.colors.sequential.Blues
        for idx_e, (i, j) in enumerate(edges):
            c_idx = int(w_norm[idx_e] * (len(cmap)-1))
            fig_tess.add_trace(go.Scatter3d(
                x=[verts_3d[i,0], verts_3d[j,0]],
                y=[verts_3d[i,1], verts_3d[j,1]],
                z=[verts_3d[i,2], verts_3d[j,2]],
                mode='lines',
                line=dict(color=cmap[c_idx], width=4),
                showlegend=False, hoverinfo='skip'))

        # Vertices
        w_v = verts_rot[:, 3]
        w_v_norm = (w_v - w_v.min()) / (w_v.ptp() + 1e-9)
        fig_tess.add_trace(go.Scatter3d(
            x=verts_3d[:,0], y=verts_3d[:,1], z=verts_3d[:,2],
            mode='markers',
            marker=dict(
                size=7,
                color=w_v_norm,
                colorscale='Blues',
                cmin=0, cmax=1,
                showscale=True,
                colorbar=dict(title='w-coord', thickness=12, len=0.6,
                              tickfont=dict(size=9)),
                line=dict(width=1, color='white'),
            ),
            text=[f'v{k} w={verts_rot[k,3]:.2f}' for k in range(16)],
            hoverinfo='text', showlegend=False))

        fig_tess.update_layout(
            scene=dict(
                xaxis=dict(title='X', backgroundcolor='#f2f6fc', gridcolor='#d8e4f0', showbackground=True),
                yaxis=dict(title='Y', backgroundcolor='#f2f6fc', gridcolor='#d8e4f0', showbackground=True),
                zaxis=dict(title='Z', backgroundcolor='#f2f6fc', gridcolor='#d8e4f0', showbackground=True),
                camera=dict(eye=dict(x=1.6, y=1.4, z=1.0)),
                bgcolor='#f8fbff',
            ),
            height=560,
            paper_bgcolor='#ffffff',
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig_tess, use_container_width=True)

    st.markdown("""
    <div class="info-box">
    <b>Why does this relate to physics?</b><br>
    Spacetime in special relativity is a 4-dimensional Minkowski space (3 spatial + 1 time dimension).
    The tesseract illustrates how a 4th dimension can be projected and visualised. In quantum field theory,
    path integrals sum over trajectories through all four dimensions simultaneously.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  6. PARTICLE COLLIDER
# ══════════════════════════════════════════════
elif section == "Particle Collider":
    st.markdown('<div class="section-title">Particle Collision Simulation</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Simulating a proton-proton collision shower at LHC energies (13.6 TeV). Each track represents a secondary particle emerging from the interaction vertex.</div>', unsafe_allow_html=True)

    col_p1, col_p2 = st.columns([1, 2.5])
    with col_p1:
        n_tracks = st.slider("Number of secondary tracks", 20, 200, 80, 10)
        beam_energy = st.slider("Beam energy per proton (TeV)", 1.0, 7.0, 6.8, 0.1)
        seed = st.number_input("Random seed", value=42, min_value=0, max_value=9999)
        show_jets = st.checkbox("Highlight jet clusters", value=True)
        np.random.seed(int(seed))

    with col_p2:
        # Generate tracks from a central vertex
        phi = np.random.uniform(0, 2*np.pi, n_tracks)
        theta = np.random.choice(
            [np.random.normal(np.pi/2, 0.4, 1)[0], np.random.uniform(0.1, np.pi-0.1, 1)[0]],
            size=n_tracks)
        theta = np.clip(theta, 0.05, np.pi-0.05)
        momentum = np.random.exponential(2*beam_energy*0.05, n_tracks)
        track_len = np.log1p(momentum) * 3.5

        # 3D track endpoints
        x_end = track_len * np.sin(theta) * np.cos(phi)
        y_end = track_len * np.sin(theta) * np.sin(phi)
        z_end = track_len * np.cos(theta)

        # Jet clustering (2 hard jets back-to-back)
        jet1_phi = np.random.uniform(0, 2*np.pi)
        jet2_phi = jet1_phi + np.pi
        is_jet = np.abs(np.mod(phi - jet1_phi, 2*np.pi) - np.pi) > (np.pi - 0.7)

        fig_coll = go.Figure()
        # Detector cylinder
        t_cyl = np.linspace(0, 2*np.pi, 80)
        z_cyl = np.linspace(-12, 12, 30)
        T_cyl, Z_cyl = np.meshgrid(t_cyl, z_cyl)
        X_cyl = 8 * np.cos(T_cyl)
        Y_cyl = 8 * np.sin(T_cyl)
        fig_coll.add_trace(go.Surface(
            x=X_cyl, y=Y_cyl, z=Z_cyl,
            colorscale=[[0,'rgba(100,160,220,0.04)'],[1,'rgba(100,160,220,0.04)']],
            showscale=False, hoverinfo='skip',
            lighting=dict(ambient=0.8), name='Detector'))

        # Tracks
        for k in range(n_tracks):
            col_t = '#e63946' if (show_jets and is_jet[k]) else '#0077b6'
            alpha = 0.9 if (show_jets and is_jet[k]) else 0.45
            w = 2.5 if (show_jets and is_jet[k]) else 1.2
            fig_coll.add_trace(go.Scatter3d(
                x=[0, x_end[k]], y=[0, y_end[k]], z=[0, z_end[k]],
                mode='lines',
                line=dict(color=col_t, width=w),
                opacity=alpha, hoverinfo='skip', showlegend=False))

        # Vertex
        fig_coll.add_trace(go.Scatter3d(
            x=[0], y=[0], z=[0], mode='markers',
            marker=dict(size=6, color='#f4a261', symbol='diamond'),
            name='Primary vertex', showlegend=True))

        fig_coll.update_layout(
            scene=dict(
                xaxis=dict(title='x (m)', range=[-13,13], backgroundcolor='#0d1b2a',
                           gridcolor='#1a3a5c', showbackground=True,
                           tickfont=dict(color='#aaccee')),
                yaxis=dict(title='y (m)', range=[-13,13], backgroundcolor='#0d1b2a',
                           gridcolor='#1a3a5c', showbackground=True,
                           tickfont=dict(color='#aaccee')),
                zaxis=dict(title='z (m)', range=[-13,13], backgroundcolor='#0d1b2a',
                           gridcolor='#1a3a5c', showbackground=True,
                           tickfont=dict(color='#aaccee')),
                camera=dict(eye=dict(x=1.3, y=1.3, z=0.7)),
                bgcolor='#0d1b2a',
            ),
            height=540,
            paper_bgcolor='#ffffff',
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(x=0.01, y=0.99, font=dict(color='#333'), bgcolor='rgba(255,255,255,0.85)'),
        )
        st.plotly_chart(fig_coll, use_container_width=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""<div class="metric-card"><div class="label">Center-of-mass energy</div>
        <div class="value">{2*beam_energy:.1f} TeV</div>
        <div class="desc">Proton-proton collision</div></div>""", unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""<div class="metric-card"><div class="label">Secondary particles</div>
        <div class="value">{n_tracks}</div>
        <div class="desc">Simulated tracks</div></div>""", unsafe_allow_html=True)
    with col_m3:
        n_jets = int(np.sum(is_jet))
        st.markdown(f"""<div class="metric-card"><div class="label">Jet tracks (red)</div>
        <div class="value">{n_jets}</div>
        <div class="desc">Hard scattering products</div></div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  7. QUANTUM ENTANGLEMENT
# ══════════════════════════════════════════════
elif section == "Quantum Entanglement":
    st.markdown('<div class="section-title">Quantum Entanglement & Bell Inequality</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Two entangled particles measured at arbitrary angles. The quantum correlation violates the classical Bell inequality — confirming non-local correlations.</div>', unsafe_allow_html=True)
    st.markdown('<div class="formula-box">|&Phi;&sup+;&rang; = (1/&radic;2)(|00&rang; + |11&rang;) &nbsp;&nbsp;|&nbsp;&nbsp; C(&theta;) = -cos(&theta;)</div>', unsafe_allow_html=True)

    col_e1, col_e2 = st.columns(2)

    with col_e1:
        st.markdown("**Quantum vs Classical Correlation**")
        theta = np.linspace(0, 2*np.pi, 360)
        corr_quantum = -np.cos(theta)
        corr_classical = np.clip(-2*np.abs(theta/np.pi - np.round(theta/np.pi)), -1, 1)

        fig_bell = go.Figure()
        fig_bell.add_trace(go.Scatter(
            x=np.degrees(theta), y=corr_quantum, mode='lines',
            line=dict(color='#0077b6', width=2.5), name='Quantum (entangled)'))
        fig_bell.add_trace(go.Scatter(
            x=np.degrees(theta), y=corr_classical, mode='lines',
            line=dict(color='#e63946', width=2, dash='dash'), name='Classical (local hidden var.)'))
        fig_bell.add_hrect(y0=-1, y1=-0.7, fillcolor='rgba(230,57,70,0.06)',
                           line_width=0, annotation_text='Bell violation region',
                           annotation_position='bottom right',
                           annotation_font_size=9)
        fig_bell.update_layout(
            height=340, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            xaxis=dict(title='Measurement angle difference (degrees)', gridcolor='#e8eef4'),
            yaxis=dict(title='Correlation coefficient E', gridcolor='#e8eef4', range=[-1.1,1.1]),
            legend=dict(x=0.02, y=0.15, bgcolor='rgba(255,255,255,0.9)', borderwidth=1,
                        bordercolor='#ccc'),
            margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_bell, use_container_width=True)

    with col_e2:
        st.markdown("**Bell State Bloch Sphere (qubit A)**")
        # Single qubit state on Bloch sphere
        phi_angle = st.slider("Phi (azimuthal angle, deg)", 0, 360, 45, 3, key='bloch_phi')
        theta_angle = st.slider("Theta (polar angle, deg)", 0, 180, 60, 3, key='bloch_theta')

        phi_r = np.radians(phi_angle)
        theta_r = np.radians(theta_angle)

        # Bloch sphere wireframe
        u = np.linspace(0, 2*np.pi, 40)
        v = np.linspace(0, np.pi, 30)
        xs = np.outer(np.cos(u), np.sin(v))
        ys = np.outer(np.sin(u), np.sin(v))
        zs = np.outer(np.ones(40), np.cos(v))

        fig_bloch = go.Figure()
        fig_bloch.add_trace(go.Surface(
            x=xs, y=ys, z=zs,
            colorscale=[[0,'rgba(200,220,240,0.25)'],[1,'rgba(200,220,240,0.25)']],
            showscale=False, hoverinfo='skip', opacity=0.5))

        # Axes
        for ax_name, xv, yv, zv, col in [('|0>', 0,0,1,'#e63946'), ('|1>', 0,0,-1,'#0077b6'),
                                           ('+x',1,0,0,'#888'), ('-x',-1,0,0,'#888'),
                                           ('+y',0,1,0,'#888'), ('-y',0,-1,0,'#888')]:
            fig_bloch.add_trace(go.Scatter3d(
                x=[0,xv*1.2], y=[0,yv*1.2], z=[0,zv*1.2], mode='lines+text',
                line=dict(color=col, width=2, dash='dash'),
                text=['',ax_name], textfont=dict(size=10, color=col),
                showlegend=False, hoverinfo='skip'))

        # State vector
        sx = np.sin(theta_r) * np.cos(phi_r)
        sy = np.sin(theta_r) * np.sin(phi_r)
        sz = np.cos(theta_r)
        fig_bloch.add_trace(go.Scatter3d(
            x=[0, sx], y=[0, sy], z=[0, sz], mode='lines+markers',
            line=dict(color='#f4a261', width=6),
            marker=dict(size=[3,10], color=['#f4a261','#f4a261'], symbol=['circle','diamond']),
            name='State vector', showlegend=True))
        fig_bloch.add_trace(go.Scatter3d(
            x=[sx], y=[sy], z=[sz], mode='text',
            text=['|psi>'], textfont=dict(size=12, color='#0d1b2a'),
            showlegend=False, hoverinfo='skip'))

        fig_bloch.update_layout(
            scene=dict(
                xaxis=dict(visible=True, range=[-1.3,1.3], showgrid=True, gridcolor='#d8e8f4',
                           backgroundcolor='#f4f8fc', showbackground=True),
                yaxis=dict(visible=True, range=[-1.3,1.3], showgrid=True, gridcolor='#d8e8f4',
                           backgroundcolor='#f4f8fc', showbackground=True),
                zaxis=dict(visible=True, range=[-1.3,1.3], showgrid=True, gridcolor='#d8e8f4',
                           backgroundcolor='#f4f8fc', showbackground=True, title='Z (|0>/|1>)'),
                camera=dict(eye=dict(x=1.4, y=1.2, z=0.8)),
                bgcolor='#f8fbff',
                aspectmode='cube',
            ),
            height=380,
            paper_bgcolor='#ffffff',
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(x=0.01, y=0.99))
        st.plotly_chart(fig_bloch, use_container_width=True)

    st.markdown("""
    <div class="info-box">
    <b>Bell's Theorem (1964)</b> — No physical theory of local hidden variables can reproduce all
    the predictions of quantum mechanics. The Aspect experiments (1982, Nobel 2022) confirmed that
    quantum correlations violate Bell inequalities, ruling out local realism.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  8. NUCLEAR REACTOR SIM
# ══════════════════════════════════════════════
elif section == "Nuclear Reactor Sim":
    st.markdown('<div class="section-title">Nuclear Reactor — Point Kinetics Simulation</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Simulate reactor power transients using the delayed neutron point kinetics equations. Adjust reactivity insertion and observe the dynamic response.</div>', unsafe_allow_html=True)
    st.markdown('<div class="formula-box">dP/dt = [(rho - beta) / Lambda] P + sum_i(lambda_i C_i) + S</div>', unsafe_allow_html=True)

    col_r1, col_r2 = st.columns([1, 2.5])
    with col_r1:
        rho_insertion = st.slider("Reactivity insertion (pcm)", -300, 300, 50, 10,
                                  help="1 pcm = 10^-5 delta-k/k")
        t_insert = st.slider("Insertion time (s)", 0, 50, 5, 1)
        t_end = st.slider("Simulation duration (s)", 20, 200, 100, 5)
        fuel_type = st.selectbox("Fuel type", ["U-235 (thermal)", "U-233 (thermal)", "Pu-239 (fast)"])
        show_precursors = st.checkbox("Show delayed precursor groups", value=False)

    with col_r2:
        # 6-group delayed neutron data (U-235 thermal)
        beta_i = np.array([0.000215, 0.001424, 0.001274, 0.002568, 0.000748, 0.000273])
        lambda_i = np.array([0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01])  # 1/s
        beta_total = np.sum(beta_i)
        Lambda = 5e-5  # prompt neutron lifetime (s)

        if fuel_type == "U-233 (thermal)":
            beta_i *= 0.6; beta_total = np.sum(beta_i); Lambda = 3e-5
        elif fuel_type == "Pu-239 (fast)":
            beta_i *= 0.75; beta_total = np.sum(beta_i); Lambda = 1e-7

        dt = 0.05
        t_arr = np.arange(0, t_end + dt, dt)
        P = np.zeros(len(t_arr))
        C = np.zeros((len(t_arr), 6))
        P[0] = 1.0
        C[0, :] = beta_i / (lambda_i * Lambda)

        rho_vals = np.zeros(len(t_arr))
        rho_pcm = rho_insertion * 1e-5
        rho_vals[int(t_insert/dt):] = rho_pcm

        # Euler integration (fast enough for demo)
        for k in range(len(t_arr)-1):
            rho_k = rho_vals[k]
            dP = ((rho_k - beta_total) / Lambda) * P[k] + np.sum(lambda_i * C[k, :])
            dC = beta_i / Lambda * P[k] - lambda_i * C[k, :]
            P[k+1] = P[k] + dt * dP
            C[k+1, :] = C[k, :] + dt * dC
            P[k+1] = max(P[k+1], 0)

        fig_rx = make_subplots(rows=2, cols=1,
                               shared_xaxes=True,
                               row_heights=[0.65, 0.35],
                               vertical_spacing=0.04)
        fig_rx.add_trace(go.Scatter(
            x=t_arr, y=P, mode='lines',
            line=dict(color='#0077b6', width=2.5), name='Reactor Power P(t)'),
            row=1, col=1)
        fig_rx.add_shape(type='line', x0=t_insert, x1=t_insert, y0=0, y1=max(P)*1.05,
                         line=dict(color='#e63946', dash='dash', width=1.5), row=1, col=1)
        fig_rx.add_annotation(x=t_insert, y=max(P)*0.95, text='Reactivity inserted',
                               showarrow=True, arrowhead=2, ax=50, ay=0,
                               font=dict(size=9, color='#e63946'), row=1, col=1)
        fig_rx.add_trace(go.Scatter(
            x=t_arr, y=rho_vals * 1e5, mode='lines',
            line=dict(color='#e63946', width=1.5), name='Reactivity rho (pcm)'),
            row=2, col=1)

        if show_precursors:
            colors_prec = ['#f4a261','#2a9d8f','#a8dadc','#e9c46a','#264653','#6a994e']
            for gi in range(6):
                fig_rx.add_trace(go.Scatter(
                    x=t_arr, y=C[:,gi]/C[0,gi], mode='lines',
                    line=dict(color=colors_prec[gi], width=1.2, dash='dot'),
                    name=f'Group {gi+1}', opacity=0.7), row=1, col=1)

        fig_rx.update_layout(
            height=460, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            legend=dict(x=0.75, y=0.98, bgcolor='rgba(255,255,255,0.9)', borderwidth=1, bordercolor='#ccc'),
            margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family='Inter,Segoe UI,sans-serif'))
        fig_rx.update_yaxes(title_text='Power (normalized)', gridcolor='#e8eef4', row=1, col=1)
        fig_rx.update_yaxes(title_text='Reactivity (pcm)', gridcolor='#e8eef4', row=2, col=1)
        fig_rx.update_xaxes(title_text='Time (s)', gridcolor='#e8eef4', row=2, col=1)
        st.plotly_chart(fig_rx, use_container_width=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""<div class="metric-card"><div class="label">Peak Power</div>
        <div class="value">{max(P):.2f}x</div><div class="desc">Relative to initial</div></div>""",
        unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""<div class="metric-card"><div class="label">Beta total</div>
        <div class="value">{beta_total*1e5:.0f} pcm</div><div class="desc">Delayed fraction</div></div>""",
        unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""<div class="metric-card"><div class="label">Prompt lifetime</div>
        <div class="value">{Lambda*1e6:.0f} us</div><div class="desc">Lambda</div></div>""",
        unsafe_allow_html=True)
    with col_m4:
        status = "SUBCRITICAL" if rho_insertion < 0 else ("PROMPT-CRITICAL" if rho_insertion*1e-5 > beta_total else "DELAYED-CRITICAL")
        st.markdown(f"""<div class="metric-card"><div class="label">Reactor State</div>
        <div class="value" style="font-size:1.1rem;">{status}</div>
        <div class="desc">rho = {rho_insertion} pcm</div></div>""",
        unsafe_allow_html=True)

    st.markdown("""
    <div class="info-box">
    <b>Delayed neutrons</b> (0.65% of all neutrons in U-235 fission) are emitted by fission
    product decay on timescales of 0.5–80 seconds. Without them, reactors would be
    uncontrollable — the effective neutron lifetime with delayed neutrons is ~0.1s instead
    of 5 microseconds for prompt neutrons alone. This is the physical basis of all
    power reactor control systems.
    </div>
    """, unsafe_allow_html=True)