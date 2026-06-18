import streamlit as st
import datetime
import config
from et_pipeline import get_sheet_names, analyze_excel_sheets, run_pipeline

st.set_page_config(page_title="Credit Automate Dashboard", layout="wide")

# ==========================================
# ระบบจัดการหน่วยความจำ (Session State Management)
# ==========================================
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'df_avail' not in st.session_state:
    st.session_state.df_avail = None
if 'df_overdue' not in st.session_state:
    st.session_state.df_overdue = None
if 'latest_overdue_name' not in st.session_state:
    st.session_state.latest_overdue_name = ""
if 'debug_info_dict' not in st.session_state:
    st.session_state.debug_info_dict = {}

def reset_state():
    """ล้างข้อมูลในหน่วยความจำเมื่อมีการเปลี่ยนไฟล์หรือตั้งค่าใหม่"""
    st.session_state.data_processed = False
    st.session_state.df_avail = None
    st.session_state.df_overdue = None
    st.session_state.latest_overdue_name = ""
    st.session_state.debug_info_dict = {}

# ==========================================
# แถบเมนูด้านข้าง (Sidebar Navigation)
# ==========================================
st.sidebar.title("Navigation Menu")
page = st.sidebar.radio(
    "เลือกหน้าต่างการทำงาน:",
    ["Data Preview and Processing", "Credit Availability Dashboard", "Credit Overdue Dashboard"]
)

# ==========================================
# หน้าที่ 1: Data Preview and Processing
# ==========================================
if page == "Data Preview and Processing":
    st.title("Data Preview and Processing")
    
    col1, col2 = st.columns(2)

    with col1:
        st.info("ส่วนที่ 1: Credit Availability\n\nอัปโหลดไฟล์ข้อมูลตั้งต้น (Excel) ที่นี่")
        avail_file = st.file_uploader("Availability File", type=['xlsx', 'xls'], key="avail", on_change=reset_state)
        
        selected_sheets = []
        if avail_file:
            valid_sheets, invalid_sheets = analyze_excel_sheets(avail_file)
            
            if invalid_sheets:
                st.error(f"ระบบตรวจพบ Sheet ที่โครงสร้างไม่ถูกต้อง (ไม่มีคอลัมน์ Customer Code): {', '.join(invalid_sheets)}")
            if valid_sheets:
                st.success(f"ระบบตรวจพบ Sheet ที่มีโครงสร้างสมบูรณ์: {', '.join(valid_sheets)}")
                
            selected_sheets = st.multiselect(
                "ระบุรายชื่อ Sheet ที่ต้องการนำไปประมวลผล:",
                options=valid_sheets + invalid_sheets,
                default=valid_sheets,
                on_change=reset_state
            )

    with col2:
        st.info("ส่วนที่ 2: Credit Overdue\n\nอัปโหลดไฟล์ที่ทำการ Export จากระบบ Fiori ที่นี่ (ระบบจะเลือกไฟล์ล่าสุดอัตโนมัติ)")
        overdue_files = st.file_uploader("Overdue Files", type=['xlsx', 'xls'], accept_multiple_files=True, key="overdue", on_change=reset_state)

    st.divider()

    # ปุ่มประมวลผลข้อมูล
    if avail_file and selected_sheets and overdue_files:
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("ประมวลผลข้อมูลตั้งต้น (Process Data)", type="primary", use_container_width=True):
                with st.spinner("กำลังดำเนินการทำความสะอาดและจัดรูปแบบข้อมูล..."):
                    try:
                        # ประมวลผลและเก็บข้อมูลลง Session State เพื่อนำไปใช้หน้าอื่น
                        df_a, df_o, latest_name, debug_info = run_pipeline(avail_file, selected_sheets, overdue_files)
                        st.session_state.df_avail = df_a
                        st.session_state.df_overdue = df_o
                        st.session_state.latest_overdue_name = latest_name
                        st.session_state.debug_info_dict = debug_info
                        st.session_state.data_processed = True
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดระหว่างการทำงานของระบบ: {e}")

    # แสดงผลตารางเมื่อข้อมูลถูกประมวลผลแล้ว
    if st.session_state.data_processed:
        df_avail = st.session_state.df_avail
        df_overdue = st.session_state.df_overdue
        latest_overdue_name = st.session_state.latest_overdue_name
        debug_info_dict = st.session_state.debug_info_dict
        
        tab1, tab2 = st.tabs(["Credit Availability", "Credit Overdue Analysis"])
        
        # --- ส่วนแสดงผล Credit Availability ---
        with tab1:
            st.subheader("ภาพรวมข้อมูล Credit Availability")
            
            filtered_avail = df_avail.copy()
            
            if 'SOURCE_SHEET' in filtered_avail.columns:
                available_sheets_in_data = filtered_avail['SOURCE_SHEET'].unique().tolist()
                
                if len(available_sheets_in_data) > 1:
                    selected_view_sheet = st.selectbox(
                        "เลือก Sheet ที่ต้องการเรียกดูข้อมูล:", 
                        available_sheets_in_data,
                        key="view_sheet_selector"
                    )
                    filtered_avail = filtered_avail[filtered_avail['SOURCE_SHEET'] == selected_view_sheet]
            
            st.markdown("ส่วนควบคุมข้อมูลประจำรอบ (Snapshot Date)")
            if 'DATE' in filtered_avail.columns:
                date_list = sorted(filtered_avail['DATE'].dropna().unique().tolist(), reverse=True)
                if date_list:
                    formatted_date_options = {d: d.strftime('%d/%m/%Y') for d in date_list}
                    
                    selected_date = st.selectbox(
                        "เลือกวันที่ของข้อมูล:", 
                        options=date_list, 
                        format_func=lambda x: formatted_date_options[x],
                        index=0
                    )
                    filtered_avail = filtered_avail[filtered_avail['DATE'] == selected_date]
            
            st.divider()
            
            view_avail = st.radio("รูปแบบการแสดงตาราง:", ["Preview (30 แถว)", "แสดงทั้งหมด"], horizontal=True, key="view_avail")
            display_df_avail = filtered_avail.head(30) if "Preview" in view_avail else filtered_avail
            
            st.dataframe(
                display_df_avail,
                column_config={
                    "CURRENT_DEBT_MILLION_THB_PERCENT": st.column_config.NumberColumn("Debt Percent", format="%.2f"),
                    "DATE": st.column_config.DateColumn("Date", format="DD/MM/YYYY")
                },
                use_container_width=True,
                height=450
            )
            
            st.divider()
            with st.expander("ตรวจสอบความถูกต้องของข้อมูล (Data Governance & Debug Log)", expanded=False):
                st.markdown("รายงานสรุปการทำความสะอาดข้อมูล (Data Cleansing Summary แยกตาม Sheet ที่เลือกใช้งาน)")
                
                active_debug_sheets = [s for s in selected_sheets if s in debug_info_dict]
                
                if active_debug_sheets:
                    debug_tabs = st.tabs(active_debug_sheets)
                    for idx, sheet in enumerate(active_debug_sheets):
                        with debug_tabs[idx]:
                            d_info = debug_info_dict[sheet]
                            
                            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                            m_col1.metric(label="ข้อมูลดิบตั้งต้น (แถว)", value=d_info['raw_rows'])
                            m_col2.metric(label="ลบแถวหัวข้อซ้ำซ้อน (แถว)", value=len(d_info['header_dropped_df']), delta="- ตัดออก", delta_color="inverse")
                            m_col3.metric(label="ลบแถวว่าง/ข้อมูลแหว่ง (แถว)", value=d_info['na_dropped_count'], delta="- ตัดออก", delta_color="inverse")
                            m_col4.metric(label="ข้อมูลพร้อมใช้งาน (แถว)", value=d_info['final_rows'], delta="สมบูรณ์", delta_color="normal")
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            
                            d_col1, d_col2 = st.columns(2)
                            with d_col1:
                                st.markdown("**รายการแถวหัวข้อซ้ำซ้อนที่ถูกตัดออก:**")
                                st.caption("ข้อมูลเหล่านี้ถูกตรวจสอบและตัดออกเพื่อไม่ให้กระทบกับการประมวลผลตัวเลข")
                                if not d_info['header_dropped_df'].empty:
                                    st.dataframe(d_info['header_dropped_df'], height=200, use_container_width=True)
                                else:
                                    st.info("ไม่พบแถวที่เป็นหัวข้อซ้ำซ้อนใน Sheet นี้")
                                    
                            with d_col2:
                                st.markdown("**การตรวจสอบชนิดข้อมูล (Data Types Schema):**")
                                st.caption("โครงสร้างประเภทข้อมูลที่ผ่านการแปลงรูปแล้ว")
                                dtype_df = df_avail.dtypes.astype(str).reset_index()
                                dtype_df.columns = ['ชื่อคอลัมน์ (Column)', 'ประเภทข้อมูล (Data Type)']
                                st.dataframe(dtype_df, height=200, use_container_width=True)
                else:
                    st.info("กรุณาเลือก Sheet ที่ต้องการตรวจสอบ")
            
        # --- ส่วนแสดงผล Credit Overdue ---
        with tab2:
            with st.expander("แสดงข้อมูล Overdue ทั้งหมด (Overview)", expanded=False):
                st.caption(f"อ้างอิงจากไฟล์: {latest_overdue_name}")
                st.dataframe(df_overdue.head(10), use_container_width=True)

            st.divider()
            
            st.subheader("ส่วนควบคุมการคัดกรองข้อมูล (Dynamic Filters)")
            
            with st.form("overdue_filter_form"):
                st.markdown("กรุณาเลือกเงื่อนไขที่ต้องการกรองข้อมูล (สามารถเลือกได้หลายคอลัมน์พร้อมกัน) และกดปุ่มมุมขวาล่างเพื่อประมวลผล")
                
                filter_columns = st.columns(4)
                user_filters = {}
                
                for idx, col_name in enumerate(df_overdue.columns):
                    with filter_columns[idx % 4]:
                        unique_vals = df_overdue[col_name].dropna().unique()
                        try:
                            unique_vals = sorted(unique_vals)
                        except TypeError:
                            unique_vals = sorted(unique_vals, key=str)
                        
                        selected_vals = st.multiselect(col_name, unique_vals, key=f"form_filter_{col_name}")
                        
                        if selected_vals:
                            user_filters[col_name] = selected_vals

                st.markdown("<br>", unsafe_allow_html=True)
                f_spacer, f_btn = st.columns([5, 1])
                with f_btn:
                    submit_filter = st.form_submit_button("ประมวลผลการกรอง", type="primary", use_container_width=True)

            filtered_overdue = df_overdue.copy()
            for filter_col, selected_values in user_filters.items():
                filtered_overdue = filtered_overdue[filtered_overdue[filter_col].isin(selected_values)]

            st.divider()

            st.subheader("ผลลัพธ์ข้อมูล Overdue")
            view_overdue = st.radio("รูปแบบการแสดงตาราง:", ["Preview (30 แถว)", "แสดงทั้งหมด"], horizontal=True, key="view_overdue")
            display_df_overdue = filtered_overdue.head(30) if "Preview" in view_overdue else filtered_overdue
            
            st.dataframe(display_df_overdue, use_container_width=True, height=500)
            st.caption(f"โครงสร้างข้อมูลที่ถูกคัดกรอง: {filtered_overdue.shape[1]} คอลัมน์ x {filtered_overdue.shape[0]} แถว (จากข้อมูลตั้งต้น {df_overdue.shape[0]} แถว)")

# ==========================================
# หน้าที่ 2: Credit Availability Dashboard
# ==========================================
elif page == "Credit Availability Dashboard":
    st.title("Credit Availability Dashboard")
    st.info("พื้นที่ว่างสำหรับสร้าง Dashboard อนาคต (Credit Availability)")
    
    if not st.session_state.data_processed:
        st.warning("กรุณากลับไปที่หน้า 'Data Preview and Processing' เพื่ออัปโหลดและประมวลผลข้อมูลก่อนเข้าใช้งานส่วนนี้")

# ==========================================
# หน้าที่ 3: Credit Overdue Dashboard
# ==========================================
elif page == "Credit Overdue Dashboard":
    st.title("Credit Overdue Dashboard")
    st.info("พื้นที่ว่างสำหรับสร้าง Dashboard อนาคต (Credit Overdue)")
    
    if not st.session_state.data_processed:
        st.warning("กรุณากลับไปที่หน้า 'Data Preview and Processing' เพื่ออัปโหลดและประมวลผลข้อมูลก่อนเข้าใช้งานส่วนนี้")