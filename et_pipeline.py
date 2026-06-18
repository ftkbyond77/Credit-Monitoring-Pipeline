import pandas as pd
import numpy as np
import datetime

def get_sheet_names(file_buffer):
    xls = pd.ExcelFile(file_buffer)
    return xls.sheet_names

def analyze_excel_sheets(file_buffer):
    xls = pd.ExcelFile(file_buffer)
    valid_sheets = []
    invalid_sheets = []
    
    for sheet in xls.sheet_names:
        try:
            df_sample = pd.read_excel(xls, sheet_name=sheet, nrows=5)
            has_customer_code = any('customer code' in str(col).strip().lower() for col in df_sample.columns)
            
            if has_customer_code:
                valid_sheets.append(sheet)
            else:
                invalid_sheets.append(sheet)
        except Exception:
            invalid_sheets.append(sheet)
            
    return valid_sheets, invalid_sheets

def _transform_availability(df, sheet_name):
    raw_rows_count = len(df)
    
    # 1. จัดการเปลี่ยนชื่อคอลัมน์ให้เป็นมาตรฐานแบบระบบปิด (Robust Mapping)
    new_cols = []
    debt_count = 0
    prev_clean_col = ""
    
    for col in df.columns:
        c_clean = str(col).strip()
        c_upper = c_clean.upper()
        
        if 'CUSTOMER CODE' in c_upper:
            clean_name = 'CUSTOMER_CODE'
        elif 'CUSTOMER NAME' in c_upper:
            clean_name = 'CUSTOMER_NAME'
        elif c_upper == 'TYPE' or 'TYPECLEAN' in c_upper:
            clean_name = 'TYPE'
        elif 'CLEAN CREDIT' in c_upper:
            clean_name = 'CLEAN_CREDIT_MB'
        elif 'CURRENT DEBT' in c_upper and 'MILLION BAHT' in c_upper:
            if debt_count == 0:
                clean_name = 'CURRENT_DEBT_MILLION_THB'
                debt_count += 1
            else:
                clean_name = 'CURRENT_DEBT_MILLION_THB_PERCENT'
        elif 'EST' in c_upper and 'FURTHER' in c_upper:
            clean_name = 'EST_FURTHER_AMOUNT'
        elif 'EST' in c_upper and 'DEBT' in c_upper:
            clean_name = 'EST_DEBT'
        elif c_upper == 'DATE':
            clean_name = 'DATE'
        elif 'ESTIMATE' in c_upper and 'AMOUNT' in c_upper:
            clean_name = 'ESTIMATE_AMOUNT'
        elif c_upper == 'CCS':
            clean_name = 'CCS'
        elif c_upper == 'MMA':
            clean_name = 'MMA'
        elif 'NBMA' in c_upper:
            clean_name = 'NBMA'
        elif 'IBMA' in c_upper:
            clean_name = 'IBMA'
        elif c_upper == 'MAA':
            clean_name = 'MAA'
        elif 'HIGHER ESTER' in c_upper or 'HIGHER_ESTER' in c_upper:
            clean_name = 'HIGHER_ESTER'
        elif 'PRICE' in c_upper:
            prefix = prev_clean_col if prev_clean_col else 'UNKNOWN'
            clean_name = f"{prefix}_PRICE"
        else:
            clean_name = c_clean.replace(' ', '_').replace('.', '').upper()
            
        new_cols.append(clean_name)
        if 'PRICE' not in clean_name:
            prev_clean_col = clean_name
            
    df.columns = new_cols

    # 2. ขั้นตอนการกรองและเก็บ Log Data Governance
    drop_mask = pd.Series(False, index=df.index)

    if 'CUSTOMER_CODE' in df.columns:
        code_str = df['CUSTOMER_CODE'].astype(str).str.strip().str.lower()
        drop_mask |= code_str.str.contains('customer code', na=False)
        
    if 'CUSTOMER_NAME' in df.columns:
        name_str = df['CUSTOMER_NAME'].astype(str).str.strip().str.lower()
        drop_mask |= name_str.str.contains('customer name', na=False)
        
    if 'TYPE' in df.columns:
        type_str = df['TYPE'].astype(str).str.strip().str.lower()
        drop_mask |= (type_str == 'type') | type_str.str.contains('typeclean', na=False)

    df_dropped_headers = df[drop_mask].copy()
    df = df[~drop_mask]

    len_before_na = len(df)
    
    if 'CUSTOMER_CODE' in df.columns:
        code_series = df['CUSTOMER_CODE'].astype(str).str.strip().str.lower()
        df = df[~code_series.isin(['none', 'nan', '', ' '])]
        df = df.dropna(subset=['CUSTOMER_CODE'])
    
    na_rows_dropped_count = len_before_na - len(df)

    # 3. จัดการข้อมูลและแปลง Data Types
    float_cols = ['CLEAN_CREDIT_MB', 'CURRENT_DEBT_MILLION_THB', 
                  'CURRENT_DEBT_MILLION_THB_PERCENT', 'EST_FURTHER_AMOUNT', 
                  'EST_DEBT', 'ESTIMATE_AMOUNT']
    
    for c in float_cols:
        if c in df.columns:
            df[c] = df[c].replace(['-', '#DIV/0!', '#N/A', ' - ', 'None'], np.nan)
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    if 'CUSTOMER_CODE' in df.columns:
        df['CUSTOMER_CODE'] = pd.to_numeric(df['CUSTOMER_CODE'], errors='coerce').fillna(0).astype(int)
    if 'CUSTOMER_NAME' in df.columns:
        df['CUSTOMER_NAME'] = df['CUSTOMER_NAME'].astype(str).replace('nan', '')
    if 'TYPE' in df.columns:
        df['TYPE'] = df['TYPE'].astype(str).replace('nan', '')
        
    if 'DATE' in df.columns:
        df['DATE'] = df['DATE'].ffill()
        
        def parse_and_realign_date(val):
            if pd.isna(val) or str(val).strip().lower() in ['none', 'nan', '', 'nat']:
                return np.nan
            
            try:
                # แปลงข้อมูลอินพุตทุกรูปแบบ (ไม่ว่าจะเป็นวัตถุวันที่หรือตัวอักษร) ให้เป็นโครงสร้างมาตรฐานของ pandas
                ts = pd.to_datetime(val)
                year = ts.year
                month = ts.month
                day = ts.day
                
                # แยกตรรกะการประมวลผลเพื่อความแม่นยำในการรักษาโครงสร้างข้อมูล
                if str(sheet_name).strip() in ['2023', '2024']:
                    # กลุ่มข้อมูลปีเก่า ระบบสแกนและตีความค่าปี-เดือน-วัน ได้ถูกต้องตรงตัวอยู่แล้ว
                    return datetime.date(year, month, day)
                else:
                    # กลุ่มข้อมูลปีใหม่และอนาคต (2025, 2026+) ตรวจพบการสลับตำแหน่งระหว่าง วัน และ เดือน
                    # ทำการจัดเรียงโครงสร้างใหม่ให้ถูกต้อง (วันสลับเป็นเดือน / เดือนสลับเป็นวัน)
                    # พร้อมเพิ่มระบบความปลอดภัย (Guard) หากค่าของวันเกิน 12 จะไม่สลับตำแหน่งเพื่อป้องกันระบบพัง
                    if day <= 12:
                        return datetime.date(year, day, month)
                    else:
                        return datetime.date(year, month, day)
            except Exception:
                return np.nan

        df['DATE'] = df['DATE'].apply(parse_and_realign_date)

    debug_info = {
        'raw_rows': raw_rows_count,
        'header_dropped_df': df_dropped_headers,
        'na_dropped_count': na_rows_dropped_count,
        'final_rows': len(df)
    }

    return df, debug_info

def _clean_overdue(df):
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]
    if 'OverdueAmount' in df.columns:
        df['OverdueAmount'] = pd.to_numeric(df['OverdueAmount'], errors='coerce').fillna(0.0)
    if 'CollectionDate' in df.columns:
        df['CollectionDate'] = df['CollectionDate'].astype(str).replace('nan', '')
    return df

def run_pipeline(avail_file, sheets_to_process, overdue_files):
    xls = pd.ExcelFile(avail_file)
    all_avail_cleaned = []
    all_debug_info = {}
    
    for sheet in sheets_to_process:
        df_raw = pd.read_excel(xls, sheet_name=sheet)
        df_clean, debug = _transform_availability(df_raw, sheet_name=sheet)
        
        if not df_clean.empty:
            df_clean.insert(0, 'SOURCE_SHEET', sheet)
            all_avail_cleaned.append(df_clean)
            
        all_debug_info[sheet] = debug
        
    if all_avail_cleaned:
        df_avail_combined = pd.concat(all_avail_cleaned, ignore_index=True)
        
        # กำหนดลำดับคอลัมน์มาตรฐาน (Master Order Template) เพื่อบังคับโครงสร้างตารางหลังการยุบรวม
        MASTER_ORDER = [
            'SOURCE_SHEET', 'CUSTOMER_CODE', 'CUSTOMER_NAME', 'TYPE', 'CLEAN_CREDIT_MB',
            'CURRENT_DEBT_MILLION_THB', 'CURRENT_DEBT_MILLION_THB_PERCENT', 
            'EST_FURTHER_AMOUNT', 'EST_DEBT', 'DATE', 'ESTIMATE_AMOUNT',
            'CCS', 'CCS_PRICE', 'MMA', 'MMA_PRICE', 'NBMA', 'NBMA_PRICE',
            'IBMA', 'IBMA_PRICE', 'MAA', 'MAA_PRICE', 'HIGHER_ESTER', 'HIGHER_ESTER_PRICE'
        ]
        
        # ตรวจสอบและเลือกเฉพาะคอลัมน์ที่มีอยู่จริงในข้อมูลชุดนั้นๆ เพื่อไม่ให้เกิดการสร้างคอลัมน์ว่างเปล่า (Scalable Guard)
        existing_cols = [col for col in MASTER_ORDER if col in df_avail_combined.columns]
        
        # กรณีที่มีคอลัมน์อื่นหลุดมาเพิ่มเติมในอนาคต ให้ต่อท้ายหลังจากเรียงคอลัมน์หลักเสร็จสิ้น
        extra_cols = [col for col in df_avail_combined.columns if col not in existing_cols]
        
        df_avail_combined = df_avail_combined[existing_cols + extra_cols]
    else:
        df_avail_combined = pd.DataFrame()
    
    overdue_files.sort(key=lambda x: x.name, reverse=True)
    latest_overdue_file = overdue_files[0]
    df_overdue_raw = pd.read_excel(latest_overdue_file)
    df_overdue_clean = _clean_overdue(df_overdue_raw)

    return df_avail_combined, df_overdue_clean, latest_overdue_file.name, all_debug_info