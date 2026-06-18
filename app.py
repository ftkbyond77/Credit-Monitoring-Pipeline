import streamlit as st
import datetime
import config
from et_pipeline import get_sheet_names, analyze_excel_sheets, run_pipeline

st.set_page_config(page_title="Credit Automate Dashboard", layout="wide")

st.title("Credit Automate Dashboard")

if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False

def reset_state():
    st.session_state.data_processed = False

col1, col2 = st.columns(2)

with col1:
    st.info("ส่วนที่ 1: Credit Availability\n\nอัปโหลดไฟล์ข้อมูลตั้งต้น (Excel) ที่นี่")
    avail_file = st.file_uploader("Availability File", type=['xlsx', 'xls'], key="avail", on_change=reset_state)
    
    selected_sheets = []
    if avail_file:
        # ดึงฟังก์ชันวิเคราะห์ระบบจากหลังบ้านมาตรวจสอบล่วงหน้า
        valid_sheets, invalid_sheets = analyze_excel_sheets(avail_file)
        
        # แสดงผลลัพธ์การตรวจสอบเพื่อธรรมาภิบาลข้อมูล (Governance Notice)
        if invalid_sheets:
            st.error(f"ระบบตรวจพบ Sheet ที่โครงสร้างไม่ถูกต้อง (ไม่มีคอลัมน์ Customer Code): {', '.join(invalid_sheets)}")
        if valid_sheets:
            st.success(f"ระบบตรวจพบ Sheet ที่มีโครงสร้างสมบูรณ์: {', '.join(valid_sheets)}")
            
        # ใช้ Multiselect เพื่อให้สิทธิ์ผู้ใช้ในการเพิ่มหรือถอดออกด้วยตัวเอง
        # ตั้งค่าเริ่มต้น (default) ให้ดึงเฉพาะกลุ่ม valid_sheets เท่านั้นเพื่อความปลอดภัย
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

if avail_file and selected_sheets and overdue_files:
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("ประมวลผลข้อมูลตั้งต้น (Process Data)", type="primary", use_container_width=True):
            st.session_state.data_processed = True

if st.session_state.data_processed and avail_file and selected_sheets and overdue_files:
    with st.spinner("กำลังดำเนินการทำความสะอาดและจัดรูปแบบข้อมูล..."):
        try:
            # ส่งรายชื่อไฟล์และกล่องรายชื่อ Sheet ที่คัดกรองแล้วเข้าไปทำงาน
            df_avail, df_overdue, latest_overdue_name, debug_info_dict = run_pipeline(avail_file, selected_sheets, overdue_files)
            
            tab1, tab2 = st.tabs(["Credit Availability", "Credit Overdue Analysis"])
            
            # ==========================================
            # การแสดงผลข้อมูล Credit Availability
            # ==========================================
            with tab1:
                st.subheader("ภาพรวมข้อมูล Credit Availability")
                
                st.markdown("ส่วนควบคุมข้อมูลประจำรอบ (Snapshot Date)")
                if 'DATE' in df_avail.columns:
                    date_list = sorted(df_avail['DATE'].dropna().unique().tolist(), reverse=True)
                    if date_list:
                        selected_date = st.selectbox("เลือกวันที่ของข้อมูล:", date_list, index=0)
                        filtered_avail = df_avail[df_avail['DATE'] == selected_date]
                    else:
                        filtered_avail = df_avail
                else:
                    filtered_avail = df_avail
                
                st.divider()
                
                view_avail = st.radio("รูปแบบการแสดงตาราง:", ["Preview (30 แถว)", "แสดงทั้งหมด"], horizontal=True, key="view_avail")
                display_df_avail = filtered_avail.head(30) if "Preview" in view_avail else filtered_avail
                
                st.dataframe(
                    display_df_avail,
                    column_config={
                        "CURRENT_DEBT_MILLION_THB_PERCENT": st.column_config.NumberColumn("Debt Percent", format="%.2f"),
                        "DATE": st.column_config.DateColumn("Date", format="YYYY-MM-DD")
                    },
                    use_container_width=True,
                    height=450
                )
                
                # ==========================================
                # DEBUG & DATA GOVERNANCE SECTION (ปรับเป็น Dynamic)
                # ==========================================
                st.divider()
                with st.expander("ตรวจสอบความถูกต้องของข้อมูล (Data Governance & Debug Log)", expanded=False):
                    st.markdown("รายงานสรุปการทำความสะอาดข้อมูล (Data Cleansing Summary แยกตาม Sheet ที่เลือกใช้งาน)")
                    
                    # ตรวจสอบและแสดงผลเฉพาะกลุ่ม Sheet ที่ถูกเลือกเข้ามาประมวลผลจริงเท่านั้น
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
                
            # ==========================================
            # การแสดงผลข้อมูล Credit Overdue
            # ==========================================
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
                
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดระหว่างการทำงานของระบบ: {e}")
