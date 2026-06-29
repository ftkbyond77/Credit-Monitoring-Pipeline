import streamlit as st
import time
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ----------------------------------------
# การตั้งค่าหน้าเว็บ
# ----------------------------------------
st.set_page_config(page_title="3D Elephant Geometric", layout="wide")

if 'page' not in st.session_state:
    st.session_state.page = 'home'

# ----------------------------------------
# ฟังก์ชันสร้างพิกัด "ช้าง" สไตล์ Geometric (Nodes & Lines)
# ----------------------------------------
def create_elephant_wireframe():
    # กำหนดพิกัดจุดหลักๆ ของช้าง (x, y, z)
    nodes = {
        # Body
        'back_left': [-1, -1, 1], 'back_right': [1, -1, 1],
        'front_left': [-1, 1, 1], 'front_right': [1, 1, 1],
        'belly_bl': [-0.8, -0.8, 0], 'belly_br': [0.8, -0.8, 0],
        'belly_fl': [-0.8, 0.8, 0], 'belly_fr': [0.8, 0.8, 0],
        # Head
        'neck_l': [-0.5, 1.2, 1.2], 'neck_r': [0.5, 1.2, 1.2],
        'forehead': [0, 1.8, 1.5],
        # Ears (ใหญ่ๆ ตามสไตล์ช้าง)
        'ear_l_top': [-1.5, 1.3, 1.8], 'ear_l_bot': [-1.3, 1.0, 0.5],
        'ear_r_top': [1.5, 1.3, 1.8], 'ear_r_bot': [1.3, 1.0, 0.5],
        # Trunk (งวง)
        'trunk_1': [0, 2.0, 1.2], 'trunk_2': [0, 2.2, 0.6], 'trunk_3': [0.2, 2.3, 0.2],
        # Legs
        'leg_bl': [-0.8, -0.8, -1], 'leg_br': [0.8, -0.8, -1],
        'leg_fl': [-0.8, 0.8, -1], 'leg_fr': [0.8, 0.8, -1],
    }
    
    # เส้นเชื่อมโยง (Edges)
    edges = [
        ('back_left', 'back_right'), ('back_right', 'front_right'), ('front_right', 'front_left'), ('front_left', 'back_left'),
        ('back_left', 'belly_bl'), ('back_right', 'belly_br'), ('front_left', 'belly_fl'), ('front_right', 'belly_fr'),
        ('front_left', 'neck_l'), ('front_right', 'neck_r'), ('neck_l', 'neck_r'), ('neck_l', 'forehead'), ('neck_r', 'forehead'),
        ('neck_l', 'ear_l_top'), ('ear_l_top', 'ear_l_bot'), ('ear_l_bot', 'belly_fl'),
        ('neck_r', 'ear_r_top'), ('ear_r_top', 'ear_r_bot'), ('ear_r_bot', 'belly_fr'),
        ('forehead', 'trunk_1'), ('trunk_1', 'trunk_2'), ('trunk_2', 'trunk_3'),
        ('belly_bl', 'leg_bl'), ('belly_br', 'leg_br'), ('belly_fl', 'leg_fl'), ('belly_fr', 'leg_fr')
    ]

    return nodes, edges

def draw_3d_elephant():
    nodes, edges = create_elephant_wireframe()
    
    # ดึงค่าพิกัดออกมา
    node_names = list(nodes.keys())
    x_nodes = [nodes[n][0] for n in node_names]
    y_nodes = [nodes[n][1] for n in node_names]
    z_nodes = [nodes[n][2] for n in node_names]

    # สร้างเส้นเชื่อม
    edge_x, edge_y, edge_z = [], [], []
    for edge in edges:
        p1, p2 = nodes[edge[0]], nodes[edge[1]]
        edge_x.extend([p1[0], p2[0], None])
        edge_y.extend([p1[1], p2[1], None])
        edge_z.extend([p1[2], p2[2], None])

    # สีเขียวเทอควอยซ์ตามรูป
    theme_color = "#40E0D0" 

    # สร้างกราฟ Plotly
    fig = go.Figure()

    # เพิ่มเส้น (Links)
    fig.add_trace(go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode='lines',
        line=dict(color=theme_color, width=3),
        hoverinfo='none'
    ))

    # เพิ่มจุด (Nodes)
    fig.add_trace(go.Scatter3d(
        x=x_nodes, y=y_nodes, z=z_nodes,
        mode='markers',
        marker=dict(symbol='circle', size=8, color=theme_color, opacity=0.8),
        text=node_names,
        hoverinfo='text'
    ))

    # ตั้งค่า Layout และใส่ Animation การหมุน
    fig.update_layout(
        title="Geometric Elephant 3D Wireframe",
        template="plotly_dark",
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode='data',
            # สร้างการหมุนมุมกล้องอัตโนมัติ
            camera=dict(
                eye=dict(x=2, y=2, z=1)
            )
        ),
        margin=dict(l=0, r=0, b=0, t=50),
        showlegend=False,
        updatemenus=[dict(
            type="buttons",
            showactive=False,
            buttons=[dict(label="Play Animation",
                          method="animate",
                          args=[None, {"frame": {"duration": 50, "redraw": True}, "fromcurrent": True}])])]
    )

    # สร้าง Frames สำหรับการหมุน 360 องศา
    frames = []
    for t in np.arange(0, 6.28, 0.1):
        frames.append(go.Frame(layout=dict(scene_camera=dict(eye=dict(x=2*np.cos(t), y=2*np.sin(t), z=1)))))
    fig.frames = frames

    return fig

# ----------------------------------------
# Popup Dialog (Progress Bar)
# ----------------------------------------
@st.dialog("🐘 Preparing Elephant Data", width="large")
def transform_data_modal():
    st.write("ระบบกำลังเชื่อมต่อจุดพิกัดแบบ Geometric...")
    my_bar = st.progress(0)
    
    for p in range(100):
        time.sleep(0.02)
        my_bar.progress(p + 1)
    
    st.session_state.page = 'result'
    st.rerun()

# ----------------------------------------
# UI Routing
# ----------------------------------------
if st.session_state.page == 'home':
    st.title("🐘 3D Geometric Elephant App")
    st.write("แอปแสดงรูปทรงช้างแบบเส้นโครงร่าง (Wireframe) ตามสไตล์ภาพตัวอย่าง")
    
    if st.button("🌟 สร้างช้าง 3 มิติ (Popup Progress)", type="primary"):
        transform_data_modal()

elif st.session_state.page == 'result':
    st.title("✨ Elephant Wireframe Result")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fig = draw_3d_elephant()
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.info("**สไตล์ Geometric:**")
        st.write("- สีเทอควอยซ์สว่าง (#40E0D0)")
        st.write("- โครงสร้างจุดและเส้น (Nodes & Links)")
        st.write("- หมุนดูได้รอบทิศทาง")
        st.write("💡 กดปุ่ม **Play Animation** ในกราฟเพื่อให้ช้างหมุนอัตโนมัติ")
        
        if st.button("⬅️ กลับไปหน้าแรก"):
            st.session_state.page = 'home'
            st.rerun()