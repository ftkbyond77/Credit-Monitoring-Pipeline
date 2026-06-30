# views/view_loading.py
import io
import streamlit as st
import streamlit.components.v1 as components
from et_pipeline import analyze_excel_sheets, run_pipeline

_PIPELINE_KEYS = {
    "data_processed":      False,
    "df_avail":            None,
    "df_overdue":          None,
    "latest_overdue_name": "",
    "debug_info_dict":     {},
    "selected_sheets":     [],
}

def _reset_pipeline_state():
    for k, v in _PIPELINE_KEYS.items():
        st.session_state[k] = v

_THREE_JS = """
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background: transparent; overflow: hidden; }
  canvas { display: block; }
</style>
</head>
<body>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function(){
  const W = window.innerWidth, H = window.innerHeight;
  const scene    = new THREE.Scene();
  const camera   = new THREE.PerspectiveCamera(60, W/H, 0.1, 200);
  const renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(window.devicePixelRatio);
  document.body.appendChild(renderer.domElement);
  camera.position.set(0, 0, 22);
  const C_NODE_MAIN = 0x049a8a;
  const C_NODE_SUB  = 0x5bbfb5;
  const C_NODE_DIM  = 0xaacfcc;
  const C_EDGE      = 0x049a8a;
  const C_PULSE     = 0xffffff;
  const NODE_COUNT  = 22;
  const nodes = [];
  const R = 7;
  for(let i=0;i<NODE_COUNT;i++){
    const phi   = Math.acos(-1 + (2*i)/NODE_COUNT);
    const theta = Math.sqrt(NODE_COUNT * Math.PI) * phi;
    nodes.push(new THREE.Vector3(
      R * Math.sin(phi) * Math.cos(theta),
      R * Math.sin(phi) * Math.sin(theta),
      R * Math.cos(phi)
    ));
  }
  const edges = [];
  const edgeMat = new THREE.LineBasicMaterial({ color:C_EDGE, transparent:true, opacity:0.25 });
  for(let i=0;i<NODE_COUNT;i++){
    for(let j=i+1;j<NODE_COUNT;j++){
      if(nodes[i].distanceTo(nodes[j]) < 6.5){
        const geo  = new THREE.BufferGeometry().setFromPoints([nodes[i], nodes[j]]);
        const line = new THREE.Line(geo, edgeMat.clone());
        scene.add(line);
        edges.push({ line, i, j, t:Math.random() });
      }
    }
  }
  const nodeMeshes = nodes.map((pos, idx) => {
    const size = idx < 3 ? 0.38 : idx < 8 ? 0.26 : 0.18;
    const col  = idx < 3 ? C_NODE_MAIN : idx < 8 ? C_NODE_SUB : C_NODE_DIM;
    const geo  = new THREE.SphereGeometry(size, 20, 20);
    const mat  = new THREE.MeshBasicMaterial({ color:col });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(pos);
    scene.add(mesh);
    return mesh;
  });
  const pulses = edges.slice(0, 12).map(e => {
    const geo  = new THREE.SphereGeometry(0.10, 10, 10);
    const mat  = new THREE.MeshBasicMaterial({ color:C_PULSE, transparent:true, opacity:0.9 });
    const mesh = new THREE.Mesh(geo, mat);
    scene.add(mesh);
    return { mesh, edge:e, t: Math.random() };
  });
  const group = new THREE.Group();
  nodeMeshes.forEach(m => group.add(m));
  edges.forEach(e => group.add(e.line));
  pulses.forEach(p => group.add(p.mesh));
  scene.add(group);
  const ringGeo = new THREE.TorusGeometry(7.8, 0.04, 8, 80);
  const ringMat = new THREE.MeshBasicMaterial({ color:C_EDGE, transparent:true, opacity:0.18 });
  const ring    = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2.2;
  group.add(ring);
  const clock = new THREE.Clock();
  function animate(){
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();
    group.rotation.y = t * 0.12;
    group.rotation.x = Math.sin(t * 0.07) * 0.18;
    pulses.forEach(p => {
      p.t = (p.t + 0.004) % 1;
      const a = nodes[p.edge.i], b = nodes[p.edge.j];
      p.mesh.position.lerpVectors(a, b, p.t);
      p.mesh.material.opacity = Math.sin(p.t * Math.PI) * 0.9;
    });
    edges.forEach((e, i) => {
      e.line.material.opacity = 0.12 + 0.14 * Math.sin(t * 0.6 + i * 0.4);
    });
    renderer.render(scene, camera);
  }
  window.addEventListener('resize', () => {
    const w = window.innerWidth, h = window.innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
  animate();
})();
</script>
</body>
</html>
"""

_UPLOAD_CSS = """
<style>
.lp-hero {
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    padding: 0 8px;
}
.lp-eyebrow {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #049a8a;
    margin-bottom: 10px;
}
.lp-title {
    font-size: 2.1rem;
    font-weight: 800;
    color: #1a2540;
    line-height: 1.15;
    margin-bottom: 14px;
}
.lp-title span { color: #049a8a; }
.lp-desc {
    font-size: 13px;
    color: #6b7a90;
    line-height: 1.65;
    max-width: 340px;
    margin-bottom: 24px;
}
.lp-steps { display: flex; flex-direction: column; gap: 8px; }
.lp-step  { display: flex; align-items: center; gap: 10px; font-size: 12px; color: #4a5568; }
.lp-step-num {
    width: 22px; height: 22px;
    border-radius: 50%;
    background: #049a8a;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.up-section-tag {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: #1a2540;
    margin-bottom: 8px;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-left: 3.5px solid #049a8a;
    padding-left: 10px;
    line-height: 1.3;
}
.up-section-tag::after { content: ""; flex: 1; height: 1px; background: #dde5ef; }
.up-card {
    background: #ffffff;
    border: 1.5px dashed #c8d4e0;
    border-radius: 10px;
    padding: 14px 16px 8px 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.up-card:hover { border-color: #049a8a; }
.up-card-desc  { font-size: 11px; color: #8a9ab0; margin-bottom: 6px; line-height: 1.5; }
.badge-ok      { display:inline-block; background:#e6f9f0; color:#1a7a4a; font-size:10px; font-weight:600; padding:2px 8px; border-radius:20px; }
.badge-warn    { display:inline-block; background:#fff4e0; color:#b06000; font-size:10px; font-weight:600; padding:2px 8px; border-radius:20px; }
.badge-info    { display:inline-block; background:#e8f4fd; color:#1a5a8a; font-size:10px; font-weight:600; padding:2px 8px; border-radius:20px; }
.badge-cached  { display:inline-block; background:#f0eeff; color:#4a35a0; font-size:10px; font-weight:600; padding:2px 8px; border-radius:20px; }
.lp-divider { border:none; border-top:1.5px solid #e8edf3; margin: 16px 0; }
</style>
"""

_PIPELINE_STEPS = [
    "Reading Availability workbook",
    "Validating and cleaning sheets",
    "Parsing Overdue Fiori export",
    "Applying transformation rules",
    "Finalising output dataframes",
]


def _render_overlay(slot, step_index: int):
    total = len(_PIPELINE_STEPS)
    pct   = int((step_index / total) * 100)

    rows_html = ""
    for i, label in enumerate(_PIPELINE_STEPS):
        if i < step_index:
            dot_bg     = "#049a8a"
            dot_border = "#049a8a"
            row_color  = "#049a8a"
            row_weight = "600"
            icon       = "&#10003;"
        elif i == step_index:
            dot_bg     = "#ffffff"
            dot_border = "#049a8a"
            row_color  = "#1a2540"
            row_weight = "700"
            icon       = ""
        else:
            dot_bg     = "#e8edf3"
            dot_border = "#dde5ef"
            row_color  = "#b0bac8"
            row_weight = "400"
            icon       = ""

        rows_html += (
            f'<div style="display:flex;align-items:center;gap:12px;padding:5px 0;'
            f'color:{row_color};font-weight:{row_weight};">'
            f'<div style="width:18px;height:18px;border-radius:50%;flex-shrink:0;'
            f'background:{dot_bg};border:2px solid {dot_border};'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:10px;color:#fff;">{icon}</div>'
            f'{label}'
            f'</div>'
        )

    slot.markdown(
        f'<div style="position:fixed;inset:0;background:rgba(15,23,40,0.62);'
        f'backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);'
        f'display:flex;align-items:center;justify-content:center;z-index:99999;">'
        f'<div style="background:#ffffff;border-radius:18px;padding:38px 44px 34px 44px;'
        f'width:440px;box-shadow:0 28px 72px rgba(4,154,138,0.20),0 4px 20px rgba(0,0,0,0.14);">'
        f'<div style="font-size:10px;font-weight:700;letter-spacing:2.5px;'
        f'text-transform:uppercase;color:#049a8a;margin-bottom:6px;">'
        f'Credit Automate · ETL Pipeline</div>'
        f'<div style="font-size:1.25rem;font-weight:800;color:#1a2540;'
        f'margin-bottom:22px;line-height:1.2;">Processing your data...</div>'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:center;margin-bottom:6px;">'
        f'<div style="font-size:11px;color:#8a9ab0;">Progress</div>'
        f'<div style="font-size:12px;font-weight:700;color:#049a8a;">{pct}%</div>'
        f'</div>'
        f'<div style="width:100%;height:7px;background:#e8edf3;'
        f'border-radius:99px;overflow:hidden;margin-bottom:22px;">'
        f'<div style="height:100%;width:{pct}%;'
        f'background:linear-gradient(90deg,#049a8a,#5bbfb5);border-radius:99px;"></div>'
        f'</div>'
        f'{rows_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def render():
    st.markdown(_UPLOAD_CSS, unsafe_allow_html=True)
    hero_col, upload_col = st.columns([1.1, 1], gap="large")

    with hero_col:
        components.html(_THREE_JS, height=340, scrolling=False)
        st.markdown("""
        <div class="lp-hero">
            <div class="lp-eyebrow">Credit Automate · ETL Pipeline</div>
            <div class="lp-title">Transform Raw Data<br>into <span>Credit Insight</span></div>
            <div class="lp-desc">
                Upload your source files below and the pipeline will validate,
                transform, and prepare all credit availability and overdue
                data ready for dashboard analysis.
            </div>
            <div class="lp-steps">
                <div class="lp-step"><div class="lp-step-num">1</div>Upload Credit Availability Excel file</div>
                <div class="lp-step"><div class="lp-step-num">2</div>Upload Overdue Fiori export files</div>
                <div class="lp-step"><div class="lp-step-num">3</div>Run Pipeline and explore dashboards</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with upload_col:
        st.markdown('<div class="up-section-tag">Step 1 · Availability Source</div>', unsafe_allow_html=True)
        st.markdown('<div class="up-card"><div class="up-card-desc">Credit Availability master file — one workbook with customer sheets</div>', unsafe_allow_html=True)
        avail_file = st.file_uploader(
            "Drag & drop or browse",
            type=["xlsx", "xls"],
            key="avail_file",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if avail_file is not None:
            new_name  = avail_file.name
            new_bytes = avail_file.read()
            avail_file.seek(0)
            if st.session_state.get("_cached_avail_name") != new_name:
                st.session_state["_cached_avail_name"]  = new_name
                st.session_state["_cached_avail_bytes"] = new_bytes
                _reset_pipeline_state()
            avail_src      = io.BytesIO(st.session_state["_cached_avail_bytes"])
            avail_src.name = st.session_state["_cached_avail_name"]
        elif st.session_state.get("_cached_avail_bytes"):
            avail_src      = io.BytesIO(st.session_state["_cached_avail_bytes"])
            avail_src.name = st.session_state["_cached_avail_name"]
            st.markdown(
                f'<span class="badge-cached">Cached: {st.session_state["_cached_avail_name"]}</span>',
                unsafe_allow_html=True,
            )
        else:
            avail_src = None

        selected_sheets = []
        if avail_src is not None:
            avail_src.seek(0)
            valid_sheets, invalid_sheets = analyze_excel_sheets(avail_src)
            if invalid_sheets:
                st.markdown(
                    f'<span class="badge-warn">Missing Customer Code: {", ".join(invalid_sheets)}</span>',
                    unsafe_allow_html=True,
                )
            if valid_sheets:
                st.markdown(
                    f'<span class="badge-ok">{len(valid_sheets)} valid sheet(s) found</span>',
                    unsafe_allow_html=True,
                )
                selected_sheets = st.multiselect(
                    "Sheets to process",
                    options=valid_sheets + invalid_sheets,
                    default=valid_sheets,
                    key="selected_sheets_widget",
                )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        st.markdown('<div class="up-section-tag">Step 2 · Overdue Source (Fiori)</div>', unsafe_allow_html=True)
        st.markdown('<div class="up-card"><div class="up-card-desc">One or more Fiori export files — latest file date used automatically</div>', unsafe_allow_html=True)
        overdue_files = st.file_uploader(
            "Drag & drop or browse",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="overdue_files",
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if overdue_files:
            curr_names = tuple(sorted(f.name for f in overdue_files))
            if st.session_state.get("_cached_overdue_names") != curr_names:
                st.session_state["_cached_overdue_names"] = curr_names
                st.session_state["_cached_overdue_data"]  = [
                    (f.name, f.read()) for f in overdue_files
                ]
                _reset_pipeline_state()
            overdue_src = [
                _make_bytesio(name, data)
                for name, data in st.session_state["_cached_overdue_data"]
            ]
        elif st.session_state.get("_cached_overdue_data"):
            overdue_src  = [
                _make_bytesio(name, data)
                for name, data in st.session_state["_cached_overdue_data"]
            ]
            cached_names = ", ".join(
                n for n, _ in st.session_state["_cached_overdue_data"]
            )
            st.markdown(
                f'<span class="badge-cached">Cached: {cached_names}</span>',
                unsafe_allow_html=True,
            )
        else:
            overdue_src = []

        if overdue_src:
            st.markdown(
                f'<span class="badge-info">{len(overdue_src)} file(s) ready — latest used automatically</span>',
                unsafe_allow_html=True,
            )

        st.markdown("<hr class='lp-divider'>", unsafe_allow_html=True)

        if st.session_state.get("data_processed"):
            st.markdown(
                "<div style='background:#e6f9f0;border:1.5px solid #a3d9b8;border-radius:8px;"
                "padding:10px 16px;font-size:12px;color:#1a7a4a;text-align:center;font-weight:600;'>"
                "Pipeline completed — navigate to dashboards from the sidebar."
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Re-run Pipeline", use_container_width=True):
                _reset_pipeline_state()
                st.rerun()
            return

        ready = bool(avail_src and selected_sheets and overdue_src)
        if ready:
            if st.button("Run Pipeline", type="primary", use_container_width=True):
                overlay = st.empty()
                total   = len(_PIPELINE_STEPS)
                try:
                    for step in range(total):
                        _render_overlay(overlay, step)
                        if step == total - 1:
                            avail_src.seek(0)
                            for f in overdue_src:
                                f.seek(0)
                            df_a, df_o, latest_name, debug_info = run_pipeline(
                                avail_src, selected_sheets, overdue_src
                            )
                    overlay.empty()
                    st.session_state.df_avail            = df_a
                    st.session_state.df_overdue          = df_o
                    st.session_state.latest_overdue_name = latest_name
                    st.session_state.debug_info_dict     = debug_info
                    st.session_state.selected_sheets     = selected_sheets
                    st.session_state.data_processed      = True
                    st.rerun()
                except Exception as e:
                    overlay.empty()
                    st.error(f"Pipeline error: {e}")
        else:
            missing = []
            if not avail_src:
                missing.append("Availability file")
            elif not selected_sheets:
                missing.append("sheet selection")
            if not overdue_src:
                missing.append("Overdue file(s)")
            st.markdown(
                f"<div style='background:#f4f6fa;border:1.5px solid #dde5ef;border-radius:8px;"
                f"padding:10px 16px;font-size:12px;color:#8a9ab0;text-align:center;'>"
                f"Waiting for: {' · '.join(missing)}</div>",
                unsafe_allow_html=True,
            )


def _make_bytesio(name: str, data: bytes) -> io.BytesIO:
    buf      = io.BytesIO(data)
    buf.name = name
    return buf