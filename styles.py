# styles.py

DASHBOARD_CSS = """
<style>
/* ============================================================
   Hide Streamlit auto-generated page navigation
   ============================================================ */
[data-testid="stSidebarNav"] { display: none !important; }

/* ============================================================
   KPI Card
   ============================================================ */
.kpi-card {
    background: #ffffff;
    border: 1.5px solid #c8d4e0;
    border-radius: 10px;
    padding: 10px 13px;
    text-align: left;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 2px;
}
.kpi-card.danger  { border-left: 4px solid #e74c3c; background: #fff8f8; border-color: #f0c0bc; }
.kpi-card.warning { border-left: 4px solid #e67e22; background: #fffbf0; border-color: #f0dba0; }
.kpi-card.safe    { border-left: 4px solid #27ae60; background: #f5fff8; border-color: #a0d8b4; }
.kpi-card.info    { border-left: 4px solid #2980b9; border-color: #a0c4e0; }

.kpi-label {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #7a90a8;
    margin-bottom: 3px;
}
.kpi-value          { font-size: 19px; font-weight: 700; color: #1a2540; line-height: 1.1; }
.kpi-value.danger   { color: #e74c3c; }
.kpi-value.warning  { color: #e67e22; }
.kpi-value.safe     { color: #27ae60; }
.kpi-sub            { font-size: 9px; color: #9aabbf; margin-top: 2px; }

/* ============================================================
   Section header
   ============================================================ */
.section-header {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #4a6fa5;
    margin: 0 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1.5px solid #d0dae6;
}

/* ============================================================
   Filter bar
   ============================================================ */
.filter-bar {
    background: #f4f6fa;
    border: 1.5px solid #d0dae6;
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 10px;
}

/* ============================================================
   Dashboard title bar
   ============================================================ */
.dash-title-bar {
    background: #ffffff;
    border: 1.5px solid #c8d4e0;
    border-radius: 10px;
    padding: 8px 14px;
    margin-bottom: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.dash-title    { font-size: 14px; font-weight: 700; color: #1a2540; margin: 0; }
.dash-subtitle { font-size: 9px; color: #8a9ab0; margin-top: 1px; }

/* ============================================================
   Sidebar nav labels
   ============================================================ */
.nav-section-label {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #4a6fa5;
    padding: 12px 0 4px 0;
    display: block;
}
.nav-divider {
    border: none;
    border-top: 1.5px solid #d0dae6;
    margin: 6px 0;
}

/* ============================================================
   Selectbox / Multiselect label
   ============================================================ */
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label {
    font-size: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.8px !important;
    text-transform: uppercase !important;
    color: #4a6fa5 !important;
}

/* ============================================================
   Table compact
   ============================================================ */
.stDataFrame { border-radius: 8px; overflow: hidden; }

/* ============================================================
   Global spacing
   ============================================================ */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 0.5rem !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }
</style>
"""


# Injected via st.components.v1.html() in app.py
# This runs inside an iframe that can access window.parent.document
# to reach the actual Streamlit sidebar DOM element.
SIDEBAR_TOGGLE_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  #toggle-btn {
    position: fixed;
    top: 14px;
    left: 14px;
    width: 36px;
    height: 36px;
    background: #ffffff;
    border: 1.5px solid #c8d4e0;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 99999;
    transition: background 0.15s, box-shadow 0.15s;
  }
  #toggle-btn:hover {
    background: #f0f4fa;
    box-shadow: 0 3px 12px rgba(0,0,0,0.16);
  }
  #toggle-btn svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: #4a6fa5;
    stroke-width: 2;
    stroke-linecap: round;
  }
</style>
</head>
<body>

<div id="toggle-btn" title="Toggle sidebar" onclick="handleToggle()">
  <svg id="icon-menu" viewBox="0 0 24 24">
    <line x1="3" y1="6"  x2="21" y2="6"/>
    <line x1="3" y1="12" x2="21" y2="12"/>
    <line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
  <svg id="icon-close" viewBox="0 0 24 24" style="display:none">
    <line x1="4" y1="4" x2="20" y2="20"/>
    <line x1="20" y1="4" x2="4"  y2="20"/>
  </svg>
</div>

<script>
(function () {
  var doc = window.parent.document;

  // -------------------------------------------------------------------
  // Locate sidebar and its native Streamlit collapse button
  // Streamlit renders a <button data-testid="collapsedControl"> that
  // programmatically fires the open/close — we click it so Streamlit's
  // own state machine stays in sync (no CSS hack needed).
  // -------------------------------------------------------------------
  function getSidebar() {
    return doc.querySelector('[data-testid="stSidebar"]');
  }

  function getNativeBtn() {
    // The native collapse button lives OUTSIDE the sidebar in newer Streamlit
    return doc.querySelector('[data-testid="collapsedControl"]');
  }

  function isOpen() {
    var sb = getSidebar();
    if (!sb) return false;
    // Streamlit sets aria-expanded="true/false" on the sidebar element
    return sb.getAttribute('aria-expanded') !== 'false';
  }

  function syncIcons(open) {
    var menu  = document.getElementById('icon-menu');
    var close = document.getElementById('icon-close');
    if (!menu || !close) return;
    if (open) {
      menu.style.display  = 'none';
      close.style.display = 'block';
    } else {
      menu.style.display  = 'block';
      close.style.display = 'none';
    }
  }

  window.handleToggle = function () {
    var btn = getNativeBtn();
    if (btn) {
      btn.click();           // delegate to Streamlit native toggle
    } else {
      // Fallback: manipulate aria-expanded directly if native btn not found
      var sb = getSidebar();
      if (!sb) return;
      var currently = isOpen();
      sb.setAttribute('aria-expanded', currently ? 'false' : 'true');
    }
    // Sync icon after a short delay to let Streamlit update the DOM
    setTimeout(function () { syncIcons(isOpen()); }, 80);
  };

  // -----------------------------------------------------------------------
  // Style the native collapse button to be invisible but still functional
  // (our custom button calls .click() on it)
  // -----------------------------------------------------------------------
  function hideNativeBtn() {
    var btn = getNativeBtn();
    if (btn) {
      btn.style.opacity  = '0';
      btn.style.pointerEvents = 'none';
      btn.style.position = 'fixed';
      btn.style.top      = '-999px';
    }
  }

  // -----------------------------------------------------------------------
  // Init — wait for Streamlit to finish painting
  // -----------------------------------------------------------------------
  function init() {
    var sb = getSidebar();
    if (!sb) {
      setTimeout(init, 150);
      return;
    }
    hideNativeBtn();
    syncIcons(isOpen());

    // Keep icon in sync if Streamlit changes sidebar state externally
    var observer = new MutationObserver(function () {
      syncIcons(isOpen());
    });
    observer.observe(sb, { attributes: true, attributeFilter: ['aria-expanded'] });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
</body>
</html>
"""