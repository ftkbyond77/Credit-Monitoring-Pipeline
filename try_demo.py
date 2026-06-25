import streamlit as st
import streamlit.components.v1 as components

# --- 1. ตั้งค่าหน้าเว็บ ---
st.set_page_config(page_title="3D Model Preparation", layout="wide", initial_sidebar_state="collapsed")

# --- 2. ใส่ Custom CSS เพื่อปรับแต่ง UI ให้เหมือน Landing Page ---
st.markdown("""
    <style>
    /* ซ่อน UI เดิมของ Streamlit */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* ปรับสีพื้นหลังและฟอนต์ */
    .stApp {
        background-color: #f4f6fc;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* ส่วนของ Header/Navbar */
    .nav-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 0px 50px 0px;
    }
    .logo {
        font-size: 24px;
        font-weight: 900;
        font-style: italic;
        color: #2d3436;
    }
    .logo span {
        color: #6c5ce7;
    }
    .nav-links {
        display: flex;
        gap: 30px;
        color: #a4b0be;
        font-weight: 600;
        align-items: center;
    }
    .btn-get-started {
        background-color: #a29bfe;
        color: white;
        padding: 8px 20px;
        border-radius: 20px;
        text-decoration: none;
        font-weight: bold;
    }
    
    /* ส่วนของ Typography Hero Section */
    .hero-title {
        font-size: 4.5rem;
        font-weight: 800;
        color: #2f3542;
        line-height: 1.1;
        margin-bottom: 20px;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #747d8c;
        margin-bottom: 40px;
        line-height: 1.6;
        max-width: 80%;
    }
    
    /* ปรับแต่งปุ่มของ Streamlit */
    div[data-testid="stButton"] button {
        background-color: #a29bfe;
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 25px;
        font-size: 1.2rem;
        font-weight: bold;
        transition: 0.3s;
    }
    div[data-testid="stButton"] button:hover {
        background-color: #6c5ce7;
        box-shadow: 0px 4px 15px rgba(108, 92, 231, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. สร้าง Navigation Bar จำลอง ---
st.markdown("""
    <div class="nav-container">
        <div class="logo">YOUR <span>WEBSITE</span></div>
        <div class="nav-links">
            <span>Home</span>
            <span>About us</span>
            <span>Work</span>
            <span>Info</span>
            <a href="#" class="btn-get-started">Get Started</a>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- 4. สร้าง Hero Section (แบ่ง 2 คอลัมน์) ---
col1, col2 = st.columns([1, 1.2])

with col1:
    # เพิ่มพื้นที่ว่างด้านบนให้ข้อความดูอยู่ตรงกลาง
    st.write("<br><br>", unsafe_allow_html=True)
    
    # ข้อความอิงตามภาพ
    st.markdown('<div class="hero-title">3D Model<br>Preparation</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="hero-subtitle">
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
            Sed eget libero feugiat, faucibus libero id, scelerisque quam.
        </div>
    """, unsafe_allow_html=True)
    
    # ปุ่ม Learn More
    st.button("Learn More")

with col2:
    # --- 5. ฝังโมเดล 3D ที่ขยับได้ด้วย Three.js ---
    # โค้ด HTML/JS นี้จะสร้างโมเดลโครงข่าย (Node-Link) แบบในหน้าจอแล็ปท็อป และทำให้มันหมุนตลอดเวลา
    three_js_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <style>
            body { margin: 0; overflow: hidden; background-color: transparent; }
            #canvas-container { width: 100%; height: 100vh; display: flex; justify-content: center; align-items: center; }
        </style>
    </head>
    <body>
        <div id="canvas-container"></div>
        <script>
            // 1. ตั้งค่า Scene, Camera, Renderer
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true }); // alpha: true ทำให้พื้นหลังโปร่งใส
            
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.getElementById('canvas-container').appendChild(renderer.domElement);

            // 2. สร้างรูปทรง (เลียนแบบ 3D Shape ในหน้าจอจากรูปภาพ)
            // ใช้ Tetrahedron (ทรงสี่หน้า) เพื่อให้ได้โครงสร้างแบบ Node-Link
            const geometry = new THREE.TetrahedronGeometry(2.5, 0);
            
            // สร้างเส้นขอบ (Wireframe) สีม่วงเข้ม
            const edges = new THREE.EdgesGeometry(geometry);
            const lineMaterial = new THREE.LineBasicMaterial({ color: 0x2d3436, linewidth: 3 });
            const wireframe = new THREE.LineSegments(edges, lineMaterial);
            
            // สร้างจุด (Nodes) ที่มุม
            const positionAttribute = geometry.attributes.position;
            const nodeGeometry = new THREE.SphereGeometry(0.2, 16, 16);
            const nodeMaterial = new THREE.MeshBasicMaterial({ color: 0x6c5ce7 }); // สีม่วง
            
            const group = new THREE.Group();
            group.add(wireframe);

            for (let i = 0; i < positionAttribute.count; i++) {
                const sphere = new THREE.Mesh(nodeGeometry, nodeMaterial);
                sphere.position.fromBufferAttribute(positionAttribute, i);
                group.add(sphere);
            }

            scene.add(group);

            // ถอยกล้องออกมา
            camera.position.z = 6;

            // 3. ฟังก์ชัน Animation (ทำให้ขยับได้ 3D Format)
            function animate() {
                requestAnimationFrame(animate);
                
                // หมุนแกน X และ Y ช้าๆ
                group.rotation.x += 0.005;
                group.rotation.y += 0.01;
                
                // ขยับลอยขึ้นลงเล็กน้อย (Floating effect)
                group.position.y = Math.sin(Date.now() * 0.001) * 0.3;

                renderer.render(scene, camera);
            }

            // จัดการเมื่อย่อขยายหน้าจอ
            window.addEventListener('resize', () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            });

            animate();
        </script>
    </body>
    </html>
    """
    
    # แสดงผล HTML ลงใน Streamlit Col2
    components.html(three_js_code, height=550)