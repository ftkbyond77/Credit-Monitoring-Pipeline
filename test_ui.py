# ============================================================
#  SUPER SONIX UI  ·  Streamlit 3D/4D Landing Page
# ============================================================

import streamlit as st
import time
import random

# ── Page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="SUPER SONIX UI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ╔══════════════════════════════════════════════════════════╗
# ║                   GLOBAL CSS / JS                        ║
# ╚══════════════════════════════════════════════════════════╝
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600&display=swap');

/* ── Reset ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stHeader"], [data-testid="stToolbar"] {
    background: #000 !important;
    color: #e0e0e0;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"] { background: #050510 !important; }
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0a1a; }
::-webkit-scrollbar-thumb { background: #00f0ff; border-radius: 3px; }

/* ─────────────────────────────────────────
   HERO SECTION
───────────────────────────────────────── */
.hero-wrapper {
    position: relative;
    width: 100%;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: radial-gradient(ellipse at 50% 40%, #050520 0%, #000005 70%);
}

/* Starfield canvas is injected by JS */
#starfield {
    position: absolute;
    inset: 0;
    z-index: 0;
}

/* 3-D grid floor */
.grid-floor {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 45%;
    background:
        linear-gradient(rgba(0,240,255,.12) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,240,255,.12) 1px, transparent 1px);
    background-size: 60px 60px;
    transform: perspective(600px) rotateX(60deg);
    transform-origin: bottom center;
    z-index: 1;
    mask-image: linear-gradient(to top, black 0%, transparent 90%);
}

/* Holographic orb */
.orb {
    position: absolute;
    top: 30%; left: 50%;
    transform: translate(-50%, -50%);
    width: 340px; height: 340px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%,
        rgba(0,240,255,.5) 0%,
        rgba(120,0,255,.3) 40%,
        rgba(0,0,10,.0) 70%);
    box-shadow:
        0 0 80px 30px rgba(0,240,255,.25),
        0 0 160px 60px rgba(120,0,255,.15),
        inset 0 0 60px rgba(0,240,255,.1);
    animation: orbPulse 4s ease-in-out infinite,
               orbRotate 12s linear infinite;
    z-index: 2;
}
@keyframes orbPulse {
    0%,100% { transform: translate(-50%,-50%) scale(1);   box-shadow: 0 0 80px 30px rgba(0,240,255,.25), 0 0 160px 60px rgba(120,0,255,.15); }
    50%      { transform: translate(-50%,-50%) scale(1.08); box-shadow: 0 0 120px 50px rgba(0,240,255,.4),  0 0 240px 80px rgba(120,0,255,.25); }
}
@keyframes orbRotate {
    from { filter: hue-rotate(0deg); }
    to   { filter: hue-rotate(360deg); }
}

/* 4-D rotating ring system */
.ring-system {
    position: absolute;
    top: 30%; left: 50%;
    transform: translate(-50%, -50%);
    width: 420px; height: 420px;
    z-index: 3;
}
.ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid transparent;
    animation: ringRotate var(--dur, 6s) linear infinite;
}
.ring:nth-child(1) {
    border-color: rgba(0,240,255,.6) transparent;
    --dur: 5s;
    box-shadow: 0 0 15px rgba(0,240,255,.5);
}
.ring:nth-child(2) {
    border-color: rgba(120,0,255,.6) transparent transparent;
    --dur: 7s;
    transform: rotateX(60deg);
    box-shadow: 0 0 15px rgba(120,0,255,.5);
    animation-direction: reverse;
}
.ring:nth-child(3) {
    border-color: rgba(255,0,180,.5) transparent transparent transparent;
    --dur: 9s;
    transform: rotateY(60deg);
    box-shadow: 0 0 15px rgba(255,0,180,.4);
}
.ring:nth-child(4) {
    width: 80%; height: 80%;
    top: 10%; left: 10%;
    border-color: rgba(0,255,120,.5) transparent;
    --dur: 11s;
    transform: rotateX(30deg) rotateY(45deg);
    box-shadow: 0 0 10px rgba(0,255,120,.4);
    animation-direction: reverse;
}
@keyframes ringRotate {
    from { transform: rotate(0deg)   rotateX(var(--rx,0)) rotateY(var(--ry,0)); }
    to   { transform: rotate(360deg) rotateX(var(--rx,0)) rotateY(var(--ry,0)); }
}

/* Hero text */
.hero-content {
    position: relative;
    z-index: 10;
    text-align: center;
    padding: 2rem;
}
.hero-eyebrow {
    font-family: 'Orbitron', monospace;
    font-size: .7rem;
    letter-spacing: .4em;
    color: #00f0ff;
    text-transform: uppercase;
    animation: fadeSlideDown .8s ease both;
}
.hero-title {
    font-family: 'Orbitron', monospace;
    font-size: clamp(2.8rem, 6vw, 6rem);
    font-weight: 900;
    line-height: 1;
    margin: .5rem 0 1.2rem;
    background: linear-gradient(135deg, #00f0ff 0%, #7800ff 50%, #ff00b4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: fadeSlideDown .9s .1s ease both;
    text-shadow: none;
    filter: drop-shadow(0 0 30px rgba(0,240,255,.4));
}
.hero-sub {
    font-size: 1.1rem;
    color: rgba(220,220,255,.7);
    max-width: 520px;
    margin: 0 auto 2.5rem;
    line-height: 1.6;
    animation: fadeSlideDown 1s .2s ease both;
}
.hero-btn {
    display: inline-block;
    padding: .9rem 2.5rem;
    font-family: 'Orbitron', monospace;
    font-size: .85rem;
    letter-spacing: .12em;
    color: #000;
    background: linear-gradient(90deg, #00f0ff, #7800ff);
    border-radius: 50px;
    text-decoration: none;
    cursor: pointer;
    border: none;
    box-shadow: 0 0 30px rgba(0,240,255,.5), 0 0 60px rgba(120,0,255,.3);
    animation: fadeSlideDown 1.1s .3s ease both, btnGlow 3s 1.5s ease-in-out infinite;
    transition: transform .2s, box-shadow .2s;
}
.hero-btn:hover {
    transform: scale(1.06);
    box-shadow: 0 0 50px rgba(0,240,255,.7), 0 0 100px rgba(120,0,255,.5);
}
@keyframes btnGlow {
    0%,100% { box-shadow: 0 0 30px rgba(0,240,255,.5), 0 0 60px rgba(120,0,255,.3); }
    50%      { box-shadow: 0 0 60px rgba(0,240,255,.8), 0 0 120px rgba(120,0,255,.6); }
}
@keyframes fadeSlideDown {
    from { opacity:0; transform: translateY(-30px); }
    to   { opacity:1; transform: translateY(0); }
}

/* Floating data particles */
.particle {
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    animation: floatParticle var(--pd,8s) var(--pd2,0s) ease-in-out infinite alternate;
    z-index: 4;
}
@keyframes floatParticle {
    from { transform: translate(0,0) scale(1); opacity: .6; }
    to   { transform: translate(var(--tx,20px), var(--ty,-40px)) scale(1.4); opacity: 1; }
}

/* ─────────────────────────────────────────
   UPLOAD / LOADING PAGE
───────────────────────────────────────── */
.upload-zone {
    border: 2px dashed rgba(0,240,255,.4);
    border-radius: 20px;
    padding: 3rem 2rem;
    text-align: center;
    background: rgba(0,10,30,.6);
    backdrop-filter: blur(10px);
    position: relative;
    overflow: hidden;
    transition: border-color .3s, box-shadow .3s;
}
.upload-zone::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(0,240,255,.04), rgba(120,0,255,.04));
    animation: scanLine 3s linear infinite;
}
@keyframes scanLine {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}
.upload-icon {
    font-size: 4rem;
    animation: iconFloat 3s ease-in-out infinite;
    filter: drop-shadow(0 0 20px #00f0ff);
}
@keyframes iconFloat {
    0%,100% { transform: translateY(0); }
    50%     { transform: translateY(-12px); }
}
.upload-title {
    font-family: 'Orbitron', monospace;
    font-size: 1.3rem;
    color: #00f0ff;
    margin: 1rem 0 .5rem;
    letter-spacing: .08em;
}
.upload-sub { color: rgba(200,200,255,.6); font-size: .9rem; }

/* ─────────────────────────────────────────
   PROGRESS BAR (animated)
───────────────────────────────────────── */
.progress-wrapper {
    background: rgba(0,10,30,.8);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    border: 1px solid rgba(0,240,255,.15);
    box-shadow: 0 0 40px rgba(0,240,255,.05);
    margin: 1rem 0;
}
.progress-label {
    font-family: 'Orbitron', monospace;
    font-size: .75rem;
    letter-spacing: .15em;
    color: #00f0ff;
    margin-bottom: .6rem;
    display: flex;
    justify-content: space-between;
}
.progress-track {
    width: 100%;
    height: 10px;
    background: rgba(0,240,255,.1);
    border-radius: 10px;
    overflow: hidden;
    position: relative;
}
.progress-fill {
    height: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg, #00f0ff, #7800ff, #ff00b4);
    background-size: 200% 100%;
    animation: progressShimmer 1.5s linear infinite;
    position: relative;
    transition: width .4s ease;
}
.progress-fill::after {
    content: '';
    position: absolute;
    right: 0; top: 50%;
    transform: translateY(-50%);
    width: 16px; height: 16px;
    background: #fff;
    border-radius: 50%;
    box-shadow: 0 0 15px #00f0ff, 0 0 30px #7800ff;
}
@keyframes progressShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Multi-track progress */
.track-row { margin: .8rem 0; }
.track-name { font-size: .78rem; color: rgba(200,200,255,.7); margin-bottom: .3rem; font-family: 'Orbitron', monospace; letter-spacing: .05em; }

/* ─────────────────────────────────────────
   WAITING ANIMATION
───────────────────────────────────────── */
.waiting-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    gap: 2rem;
}

/* DNA Helix spinner */
.dna-spinner {
    display: flex;
    gap: 6px;
    align-items: center;
}
.dna-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #00f0ff;
    animation: dnaBounce 1.2s ease-in-out infinite;
    box-shadow: 0 0 10px #00f0ff;
}
.dna-dot:nth-child(2)  { background: #7800ff; box-shadow: 0 0 10px #7800ff; animation-delay: .1s; }
.dna-dot:nth-child(3)  { background: #ff00b4; box-shadow: 0 0 10px #ff00b4; animation-delay: .2s; }
.dna-dot:nth-child(4)  { background: #00ff78; box-shadow: 0 0 10px #00ff78; animation-delay: .3s; }
.dna-dot:nth-child(5)  { background: #ff7800; box-shadow: 0 0 10px #ff7800; animation-delay: .4s; }
.dna-dot:nth-child(6)  { background: #00f0ff; box-shadow: 0 0 10px #00f0ff; animation-delay: .5s; }
.dna-dot:nth-child(7)  { background: #7800ff; box-shadow: 0 0 10px #7800ff; animation-delay: .6s; }
.dna-dot:nth-child(8)  { background: #ff00b4; box-shadow: 0 0 10px #ff00b4; animation-delay: .7s; }
@keyframes dnaBounce {
    0%,80%,100% { transform: scaleY(1); height: 10px; }
    40%          { transform: scaleY(2.5); height: 25px; }
}

/* Cube 3D spinner */
.cube-scene {
    width: 80px; height: 80px;
    perspective: 200px;
}
.cube {
    width: 100%; height: 100%;
    position: relative;
    transform-style: preserve-3d;
    animation: cubeRotate3D 4s linear infinite;
}
.cube-face {
    position: absolute;
    width: 80px; height: 80px;
    border: 2px solid rgba(0,240,255,.8);
    background: rgba(0,240,255,.05);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
}
.cube-face.front  { transform: rotateY(  0deg) translateZ(40px); border-color: rgba(0,240,255,.8); }
.cube-face.back   { transform: rotateY(180deg) translateZ(40px); border-color: rgba(120,0,255,.8); }
.cube-face.left   { transform: rotateY(-90deg) translateZ(40px); border-color: rgba(255,0,180,.8); }
.cube-face.right  { transform: rotateY( 90deg) translateZ(40px); border-color: rgba(0,255,120,.8); }
.cube-face.top    { transform: rotateX( 90deg) translateZ(40px); border-color: rgba(255,120,0,.8); }
.cube-face.bottom { transform: rotateX(-90deg) translateZ(40px); border-color: rgba(0,120,255,.8); }
@keyframes cubeRotate3D {
    0%   { transform: rotateX(0)    rotateY(0)    rotateZ(0); }
    33%  { transform: rotateX(120deg) rotateY(240deg) rotateZ(60deg); }
    66%  { transform: rotateX(240deg) rotateY(120deg) rotateZ(240deg); }
    100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(360deg); }
}

/* Ripple rings */
.ripple-container {
    position: relative;
    width: 100px; height: 100px;
    display: flex; align-items: center; justify-content: center;
}
.ripple-ring {
    position: absolute;
    border-radius: 50%;
    border: 2px solid #00f0ff;
    animation: rippleOut 2.4s ease-out infinite;
}
.ripple-ring:nth-child(1) { animation-delay: 0s; }
.ripple-ring:nth-child(2) { animation-delay: .8s; }
.ripple-ring:nth-child(3) { animation-delay: 1.6s; }
@keyframes rippleOut {
    0%   { width: 20px; height: 20px; opacity: 1; border-color: #00f0ff; }
    100% { width: 100px; height: 100px; opacity: 0; border-color: #7800ff; }
}
.ripple-core {
    width: 20px; height: 20px;
    background: #00f0ff;
    border-radius: 50%;
    box-shadow: 0 0 20px #00f0ff, 0 0 40px #7800ff;
    animation: corePulse 1.2s ease-in-out infinite;
    z-index: 1;
}
@keyframes corePulse {
    0%,100% { transform: scale(1); }
    50%     { transform: scale(1.4); }
}

/* Glitch text effect */
.glitch {
    font-family: 'Orbitron', monospace;
    font-size: 1rem;
    color: #00f0ff;
    letter-spacing: .2em;
    position: relative;
    animation: glitchBase 3s infinite;
}
.glitch::before, .glitch::after {
    content: attr(data-text);
    position: absolute; top: 0; left: 0;
    width: 100%;
}
.glitch::before {
    color: #ff00b4;
    animation: glitchTop 3s infinite;
    clip-path: polygon(0 0, 100% 0, 100% 33%, 0 33%);
}
.glitch::after {
    color: #00ff78;
    animation: glitchBot 3s infinite;
    clip-path: polygon(0 67%, 100% 67%, 100% 100%, 0 100%);
}
@keyframes glitchBase {
    0%,90%,100% { transform: none; }
    91% { transform: skewX(-3deg); }
    93% { transform: skewX(3deg); }
    95% { transform: skewX(-1deg); }
}
@keyframes glitchTop {
    0%,90%,100% { transform: none; }
    91% { transform: translate(-2px, -2px); }
    93% { transform: translate(2px,  2px); }
}
@keyframes glitchBot {
    0%,90%,100% { transform: none; }
    91% { transform: translate(2px, 2px); }
    93% { transform: translate(-2px, -2px); }
}

/* ─────────────────────────────────────────
   CARDS
───────────────────────────────────────── */
.card-3d {
    background: linear-gradient(135deg, rgba(0,20,50,.8), rgba(10,0,30,.8));
    border: 1px solid rgba(0,240,255,.2);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: transform .3s, box-shadow .3s;
    transform: perspective(600px) rotateX(0) rotateY(0);
}
.card-3d::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,240,255,.06), transparent 60%);
}
.card-3d:hover {
    transform: perspective(600px) rotateX(-4deg) rotateY(4deg) scale(1.03);
    box-shadow: -8px 8px 40px rgba(0,240,255,.2), 8px -8px 40px rgba(120,0,255,.2);
}
.card-icon { font-size: 2.5rem; margin-bottom: .8rem; filter: drop-shadow(0 0 12px #00f0ff); }
.card-title { font-family: 'Orbitron', monospace; font-size: .9rem; color: #00f0ff; letter-spacing: .08em; }
.card-desc  { font-size: .82rem; color: rgba(200,200,255,.6); margin-top: .4rem; line-height: 1.5; }

/* ── Section labels ── */
.section-badge {
    display: inline-block;
    font-family: 'Orbitron', monospace;
    font-size: .65rem;
    letter-spacing: .3em;
    padding: .3rem 1rem;
    border: 1px solid rgba(0,240,255,.4);
    border-radius: 50px;
    color: #00f0ff;
    background: rgba(0,240,255,.05);
    margin-bottom: 1rem;
}
.section-title {
    font-family: 'Orbitron', monospace;
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00f0ff, #7800ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.divider {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,240,255,.4), rgba(120,0,255,.4), transparent);
    margin: 2rem 0;
}

/* Stats */
.stat-val {
    font-family: 'Orbitron', monospace;
    font-size: 2.4rem;
    font-weight: 900;
    background: linear-gradient(90deg, #00f0ff, #7800ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.stat-label { color: rgba(200,200,255,.5); font-size: .8rem; letter-spacing: .1em; }

/* Notification toast */
.toast {
    background: rgba(0,10,30,.95);
    border: 1px solid rgba(0,240,255,.3);
    border-left: 4px solid #00f0ff;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    font-size: .85rem;
    color: rgba(220,220,255,.9);
    backdrop-filter: blur(10px);
    animation: toastIn .4s ease;
    box-shadow: 0 8px 30px rgba(0,240,255,.1);
}
@keyframes toastIn {
    from { opacity:0; transform: translateX(30px); }
    to   { opacity:1; transform: translateX(0); }
}

/* Streamlit overrides */
.stButton > button {
    background: linear-gradient(90deg, #00f0ff20, #7800ff20) !important;
    color: #00f0ff !important;
    border: 1px solid rgba(0,240,255,.4) !important;
    border-radius: 50px !important;
    font-family: 'Orbitron', monospace !important;
    letter-spacing: .08em !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: linear-gradient(90deg, #00f0ff40, #7800ff40) !important;
    box-shadow: 0 0 20px rgba(0,240,255,.3) !important;
    transform: translateY(-2px) !important;
}
.stSelectbox label, .stSlider label, .stFileUploader label {
    color: rgba(200,200,255,.8) !important;
    font-family: 'Orbitron', monospace !important;
    font-size: .78rem !important;
    letter-spacing: .05em !important;
}
[data-baseweb="select"] {
    background: rgba(0,10,30,.8) !important;
    border-color: rgba(0,240,255,.3) !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Orbitron', monospace !important;
    font-size: .72rem !important;
    letter-spacing: .08em !important;
    color: rgba(180,180,255,.7) !important;
}
.stTabs [aria-selected="true"] {
    color: #00f0ff !important;
    border-bottom: 2px solid #00f0ff !important;
}
</style>
"""

# ══════════════════════════════════════════════════════════════
#  HERO HTML (canvas starfield + orb + rings + particles + text)
# ══════════════════════════════════════════════════════════════
HERO_HTML = """
<div class="hero-wrapper" id="hero">
  <canvas id="starfield"></canvas>
  <div class="grid-floor"></div>
  <div class="orb"></div>
  <div class="ring-system">
    <div class="ring"></div>
    <div class="ring"></div>
    <div class="ring"></div>
    <div class="ring"></div>
  </div>

  <!-- floating particles -->
  <div class="particle" style="width:6px;height:6px;background:#00f0ff;top:20%;left:15%;--pd:7s;--pd2:0s;--tx:30px;--ty:-50px;box-shadow:0 0 10px #00f0ff;"></div>
  <div class="particle" style="width:4px;height:4px;background:#7800ff;top:60%;left:80%;--pd:9s;--pd2:.5s;--tx:-20px;--ty:-60px;box-shadow:0 0 8px #7800ff;"></div>
  <div class="particle" style="width:8px;height:8px;background:#ff00b4;top:75%;left:25%;--pd:6s;--pd2:1s;--tx:40px;--ty:-30px;box-shadow:0 0 12px #ff00b4;"></div>
  <div class="particle" style="width:5px;height:5px;background:#00ff78;top:35%;left:70%;--pd:8s;--pd2:2s;--tx:-35px;--ty:-45px;box-shadow:0 0 10px #00ff78;"></div>
  <div class="particle" style="width:3px;height:3px;background:#ff7800;top:50%;left:10%;--pd:10s;--pd2:.8s;--tx:50px;--ty:-20px;box-shadow:0 0 8px #ff7800;"></div>
  <div class="particle" style="width:7px;height:7px;background:#00f0ff;top:15%;left:85%;--pd:7.5s;--pd2:1.5s;--tx:-40px;--ty:30px;box-shadow:0 0 10px #00f0ff;opacity:.7;"></div>

  <div class="hero-content">
    <div class="hero-eyebrow">⚡ Next Generation Interface System</div>
    <h1 class="hero-title">SUPER<br>SONIX UI</h1>
    <p class="hero-sub">
      Ultra-dimensional interface powered by<br>
      <strong style="color:#00f0ff;">3D · 4D · Neural Particles · Quantum Animations</strong>
    </p>
    <a class="hero-btn" onclick="document.getElementById('main-content').scrollIntoView({behavior:'smooth'})">
      ⚡ LAUNCH INTERFACE
    </a>
  </div>
</div>

<script>
(function() {
  const canvas = document.getElementById('starfield');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, stars = [];

  function resize() {
    W = canvas.width  = canvas.offsetWidth  || window.innerWidth;
    H = canvas.height = canvas.offsetHeight || window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // init stars
  for (let i = 0; i < 280; i++) {
    stars.push({
      x: Math.random() * W,
      y: Math.random() * H,
      z: Math.random() * W,
      r: Math.random() * 1.5 + .3,
      color: ['#00f0ff','#7800ff','#ff00b4','#ffffff','#00ff78'][Math.floor(Math.random()*5)]
    });
  }

  let frame = 0;
  function draw() {
    ctx.clearRect(0, 0, W, H);
    frame++;
    stars.forEach(s => {
      // 4-D: slowly shift z for depth-pulse
      s.z -= .3 + Math.sin(frame * .002) * .2;
      if (s.z <= 0) { s.z = W; s.x = Math.random() * W; s.y = Math.random() * H; }
      const k  = 128 / s.z;
      const sx = (s.x - W/2) * k + W/2;
      const sy = (s.y - H/2) * k + H/2;
      const sr = Math.max(0, s.r * (1 - s.z/W) * 4);
      if (sx < 0 || sx > W || sy < 0 || sy > H) return;
      ctx.beginPath();
      ctx.arc(sx, sy, sr, 0, Math.PI * 2);
      ctx.fillStyle = s.color;
      ctx.shadowBlur = 6;
      ctx.shadowColor = s.color;
      ctx.globalAlpha = Math.min(1, (1 - s.z/W) * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }
  draw();
})();
</script>
"""

# ══════════════════════════════════════════════════════════════
#  UPLOAD / LOADING PAGE HTML
# ══════════════════════════════════════════════════════════════
def upload_zone_html(file_name="", status="idle"):
    if status == "idle":
        icon, title, sub = "📡", "DROP FILE INTO THE MATRIX", "Supports CSV · JSON · XLSX · PDF · Any format"
    elif status == "uploading":
        icon, title, sub = "⚡", "TRANSMITTING DATA...", "Quantum channel active — do not disconnect"
    else:
        icon, title, sub = "✅", "FILE LOADED SUCCESSFULLY", f"<span style='color:#00ff78'>{file_name}</span> · Ready for processing"
    return f"""
    <div class="upload-zone">
      <div class="upload-icon">{icon}</div>
      <div class="upload-title">{title}</div>
      <div class="upload-sub">{sub}</div>
    </div>"""

# ══════════════════════════════════════════════════════════════
#  ANIMATED PROGRESS BAR HTML
# ══════════════════════════════════════════════════════════════
def progress_bar_html(pct: int, label: str = "PROCESSING", color_start="#00f0ff", color_end="#7800ff"):
    return f"""
    <div class="progress-wrapper">
      <div class="progress-label">
        <span>{label}</span>
        <span style="color:#fff;font-size:.9rem;">{pct}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:{pct}%;background:linear-gradient(90deg,{color_start},{color_end});background-size:200% 100%;animation:progressShimmer 1.5s linear infinite;"></div>
      </div>
    </div>"""

def multi_progress_html(tracks):
    rows = ""
    colors = [("#00f0ff","#7800ff"),("#ff00b4","#ff7800"),("#00ff78","#00f0ff"),("#7800ff","#ff00b4")]
    for i, (name, pct) in enumerate(tracks):
        c1, c2 = colors[i % len(colors)]
        rows += f"""
        <div class="track-row">
          <div class="track-name">{name}</div>
          <div class="progress-track">
            <div class="progress-fill" style="width:{pct}%;background:linear-gradient(90deg,{c1},{c2});background-size:200% 100%;animation:progressShimmer 1.5s linear infinite;"></div>
          </div>
        </div>"""
    return f'<div class="progress-wrapper">{rows}</div>'

# ══════════════════════════════════════════════════════════════
#  WAITING ANIMATIONS HTML
# ══════════════════════════════════════════════════════════════
WAITING_DNA = """
<div class="waiting-wrapper">
  <div class="dna-spinner">
    <div class="dna-dot"></div><div class="dna-dot"></div>
    <div class="dna-dot"></div><div class="dna-dot"></div>
    <div class="dna-dot"></div><div class="dna-dot"></div>
    <div class="dna-dot"></div><div class="dna-dot"></div>
  </div>
  <div class="glitch" data-text="PROCESSING DATA STREAM">PROCESSING DATA STREAM</div>
</div>"""

WAITING_CUBE = """
<div class="waiting-wrapper">
  <div class="cube-scene">
    <div class="cube">
      <div class="cube-face front">⚡</div>
      <div class="cube-face back">🔮</div>
      <div class="cube-face left">💠</div>
      <div class="cube-face right">🌀</div>
      <div class="cube-face top">✦</div>
      <div class="cube-face bottom">◈</div>
    </div>
  </div>
  <div class="glitch" data-text="NEURAL CORE ACTIVE">NEURAL CORE ACTIVE</div>
</div>"""

WAITING_RIPPLE = """
<div class="waiting-wrapper">
  <div class="ripple-container">
    <div class="ripple-ring"></div>
    <div class="ripple-ring"></div>
    <div class="ripple-ring"></div>
    <div class="ripple-core"></div>
  </div>
  <div class="glitch" data-text="SCANNING QUANTUM FIELD">SCANNING QUANTUM FIELD</div>
</div>"""

# ══════════════════════════════════════════════════════════════
#  CARDS HTML
# ══════════════════════════════════════════════════════════════
FEATURE_CARDS = [
    ("🌀", "3D RENDER ENGINE",  "Real-time perspective transforms with hardware-accelerated CSS"),
    ("⚡", "4D TIME DIMENSION",  "Temporal animations that evolve across time axes — not just space"),
    ("💠", "QUANTUM PARTICLES", "Probabilistic particle fields with dynamic color state"),
    ("🔮", "NEURAL INTERFACE",  "Adaptive UI that learns from your interaction patterns"),
    ("🛸", "SPATIAL AUDIO",     "Immersive 3D positional sound synthesis for every action"),
    ("🌐", "HOLOGRAPHIC GRID",  "Infinite perspective-mapped grid floor with depth fog"),
]

def cards_html(cards):
    items = ""
    for icon, title, desc in cards:
        items += f"""
        <div style="padding:.5rem;">
          <div class="card-3d">
            <div class="card-icon">{icon}</div>
            <div class="card-title">{title}</div>
            <div class="card-desc">{desc}</div>
          </div>
        </div>"""
    return f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;">{items}</div>'

# ══════════════════════════════════════════════════════════════
#  STATS ROW
# ══════════════════════════════════════════════════════════════
STATS_HTML = """
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:1.5rem 0;">
  <div style="text-align:center;padding:1.5rem;background:rgba(0,10,30,.6);border:1px solid rgba(0,240,255,.15);border-radius:12px;">
    <div class="stat-val">99.9%</div><div class="stat-label">UPTIME SLA</div>
  </div>
  <div style="text-align:center;padding:1.5rem;background:rgba(0,10,30,.6);border:1px solid rgba(120,0,255,.15);border-radius:12px;">
    <div class="stat-val" style="background:linear-gradient(90deg,#7800ff,#ff00b4);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">4D</div>
    <div class="stat-label">DIMENSIONS</div>
  </div>
  <div style="text-align:center;padding:1.5rem;background:rgba(0,10,30,.6);border:1px solid rgba(255,0,180,.15);border-radius:12px;">
    <div class="stat-val" style="background:linear-gradient(90deg,#ff00b4,#ff7800);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">280</div>
    <div class="stat-label">STAR PARTICLES</div>
  </div>
  <div style="text-align:center;padding:1.5rem;background:rgba(0,10,30,.6);border:1px solid rgba(0,255,120,.15);border-radius:12px;">
    <div class="stat-val" style="background:linear-gradient(90deg,#00ff78,#00f0ff);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">60fps</div>
    <div class="stat-label">ANIMATION RATE</div>
  </div>
</div>"""

# ══════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── HERO ────────────────────────────────────────────────────
st.markdown(HERO_HTML, unsafe_allow_html=True)

# ── MAIN CONTENT ────────────────────────────────────────────
st.markdown('<div id="main-content"></div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "⚡  OVERVIEW",
    "📡  FILE UPLOAD",
    "📊  PROGRESS BARS",
    "🌀  WAIT ANIMATIONS",
])

# ────────────────────────────────────────────────────────────
with tab1:
    st.markdown(STATS_HTML, unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-badge">CORE MODULES</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">System Capabilities</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(cards_html(FEATURE_CARDS), unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⚡ INITIALISE", use_container_width=True):
            st.markdown('<div class="toast">⚡ System initialised — all cores online</div>', unsafe_allow_html=True)
    with col2:
        if st.button("🔮 SCAN MATRIX", use_container_width=True):
            st.markdown('<div class="toast">🔮 Matrix scan complete — no anomalies detected</div>', unsafe_allow_html=True)
    with col3:
        if st.button("🌀 CALIBRATE", use_container_width=True):
            st.markdown('<div class="toast">🌀 Holographic calibration successful</div>', unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-badge">DATA INGESTION MODULE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">File Upload Portal</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(upload_zone_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    uploaded = st.file_uploader("SELECT FILE", label_visibility="visible", type=None)
    if uploaded:
        st.markdown(upload_zone_html(uploaded.name, "uploading"), unsafe_allow_html=True)
        prog_ph = st.empty()
        for pct in range(0, 101, 4):
            prog_ph.markdown(
                progress_bar_html(pct, "UPLOADING TO QUANTUM CORE", "#00f0ff", "#7800ff"),
                unsafe_allow_html=True)
            time.sleep(0.04)
        st.markdown(upload_zone_html(uploaded.name, "done"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="toast">✅ <strong>{uploaded.name}</strong> · {uploaded.size:,} bytes · CHECKSUM VERIFIED</div>',
            unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-badge">ANALYTICS ENGINE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Progress Visualisation</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    speed = st.select_slider("SIMULATION SPEED", options=["SLOW", "NORMAL", "FAST", "LUDICROUS"], value="NORMAL")
    delay = {"SLOW": .07, "NORMAL": .04, "FAST": .018, "LUDICROUS": .005}[speed]
    if st.button("▶  RUN SIMULATION", use_container_width=True):
        placeholder = st.empty()
        tracks_data = [
            ("NEURAL NETWORK COMPILE", 0),
            ("QUANTUM DATA ENCODE",    0),
            ("HOLOGRAPHIC RENDER",     0),
            ("SPATIAL CALIBRATION",    0),
        ]
        for step in range(101):
            tracks_data = [
                (tracks_data[0][0], min(100, step + random.randint(0,3))),
                (tracks_data[1][0], min(100, step + random.randint(-2,2))),
                (tracks_data[2][0], min(100, max(0, step - 5 + random.randint(0,5)))),
                (tracks_data[3][0], min(100, step + random.randint(-1,4))),
            ]
            placeholder.markdown(multi_progress_html(tracks_data), unsafe_allow_html=True)
            time.sleep(delay)
        st.markdown('<div class="toast">✅ All processes completed — system nominal</div>', unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div style="margin-top:1rem">', unsafe_allow_html=True)
    manual_pct = st.slider("MANUAL OVERRIDE", 0, 100, 42)
    st.markdown(
        progress_bar_html(manual_pct, "MANUAL CONTROL", "#ff00b4", "#ff7800"),
        unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-badge">WAIT STATE MODULE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Waiting Animations</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    anim_type = st.selectbox(
        "SELECT ANIMATION TYPE",
        ["🧬 DNA Helix Bounce", "⬛ 3D Rotating Cube", "🌊 Quantum Ripple Rings"])
    anim_map = {
        "🧬 DNA Helix Bounce":    WAITING_DNA,
        "⬛ 3D Rotating Cube":    WAITING_CUBE,
        "🌊 Quantum Ripple Rings": WAITING_RIPPLE,
    }
    wait_secs = st.slider("SIMULATE WAIT (seconds)", 1, 10, 3)
    if st.button("🌀 TRIGGER WAIT STATE", use_container_width=True):
        ph = st.empty()
        ph.markdown(anim_map[anim_type], unsafe_allow_html=True)
        time.sleep(wait_secs)
        ph.markdown(
            '<div class="toast">⚡ Operation complete — returning to active state</div>',
            unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("**Preview all animations simultaneously:**", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(WAITING_DNA,    unsafe_allow_html=True)
    with c2:
        st.markdown(WAITING_CUBE,   unsafe_allow_html=True)
    with c3:
        st.markdown(WAITING_RIPPLE, unsafe_allow_html=True)