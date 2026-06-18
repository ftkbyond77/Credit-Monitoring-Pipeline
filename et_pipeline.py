import pandas as pd
import numpy as np


def get_sheet_names(file_buffer):
    xls = pd.ExcelFile(file_buffer)
    return xls.sheet_names

def analyze_excel_sheets(file_buffer):
    """วิเคราะห์โครงสร้างของแต่ละ Sheet เพื่อตรวจสอบความพร้อมของคอลัมน์ก่อนการประมวลผล"""
    xls = pd.ExcelFile(file_buffer)
    valid_sheets = []
    invalid_sheets = []
    
    for sheet in xls.sheet_names:
        try:
            # อ่านข้อมูลเพียง 5 แถวแรกเพื่อความรวดเร็วในการตรวจสอบโครงสร้าง
            df_sample = pd.read_excel(xls, sheet_name=sheet, nrows=5)
            
            # ตรวจสอบว่ามีคอลัมน์ใดที่มีคำว่า 'customer code' หรือไม่
            has_customer_code = any('customer code' in str(col).strip().lower() for col in df_sample.columns)
            
            if has_customer_code:
                valid_sheets.append(sheet)
            else:
                invalid_sheets.append(sheet)
        except Exception:
            invalid_sheets.append(sheet)
            
    return valid_sheets, invalid_sheets

def _transform_availability(df):
    raw_rows_count = len(df)
    
    # 1. จัดการเปลี่ยนชื่อคอลัมน์ให้เป็นมาตรฐาน
    new_cols = []
    debt_count = 0
    prev_raw_col = ""
    
    for col in df.columns:
        c_clean = str(col).strip()
        c_upper = c_clean.upper()
        
        if c_upper == 'CUSTOMER CODE': new_cols.append('CUSTOMER_CODE')
        elif c_upper == 'CUSTOMER NAME': new_cols.append('CUSTOMER_NAME')
        elif 'TYPECLEAN' in c_upper: new_cols.append('TYPE')
        elif 'CLEAN CREDIT' in c_upper: new_cols.append('CLEAN_CREDIT_MB')
        elif 'CURRENT DEBT' in c_upper and 'MILLION BAHT' in c_upper:
            if debt_count == 0:
                new_cols.append('CURRENT_DEBT_MILLION_THB')
                debt_count += 1
            else:
                new_cols.append('CURRENT_DEBT_MILLION_THB_PERCENT')
        elif c_upper == 'DATE': 
            new_cols.append('DATE')
        elif 'EST' in c_upper:
            new_cols.append(c_clean.replace('.', '').replace(' ', '_').upper())
        elif c_upper.startswith('PRICE'):
            prefix = new_cols[-1] if new_cols else 'UNKNOWN'
            new_cols.append(f"{prefix}_PRICE")
        else:
            formatted = c_clean.replace(' ', '_')
            if formatted not in ['nBMA', 'iBMA']: formatted = formatted.upper()
            new_cols.append(formatted)
            
        prev_raw_col = c_clean
        
    df.columns = new_cols

    # ==========================================
    # 2. ขั้นตอนการกรองและเก็บ Log Data Governance
    # ==========================================
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

    # ==========================================
    # 3. จัดการข้อมูลและแปลง Data Types
    # ==========================================
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
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce', dayfirst=True).dt.date

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
    
    # วนลูปประมวลผลเฉพาะรายชื่อ Sheet ที่ส่งมาจากหน้าจอ
    for sheet in sheets_to_process:
        df_raw = pd.read_excel(xls, sheet_name=sheet)
        df_clean, debug = _transform_availability(df_raw)
        
        if not df_clean.empty:
            df_clean.insert(0, 'SOURCE_SHEET', sheet)
            all_avail_cleaned.append(df_clean)
            
        all_debug_info[sheet] = debug
        
    if all_avail_cleaned:
        df_avail_combined = pd.concat(all_avail_cleaned, ignore_index=True)
    else:
        df_avail_combined = pd.DataFrame()
    
    overdue_files.sort(key=lambda x: x.name, reverse=True)
    latest_overdue_file = overdue_files[0]
    df_overdue_raw = pd.read_excel(latest_overdue_file)
    df_overdue_clean = _clean_overdue(df_overdue_raw)

    return df_avail_combined, df_overdue_clean, latest_overdue_file.name, all_debug_info