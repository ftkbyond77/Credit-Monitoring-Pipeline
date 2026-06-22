# debug.py — Full Version (Step 1-7A)
# streamlit run debug.py

import streamlit as st
import pandas as pd
import numpy as np
import io
import logging
import datetime
import traceback
import json
import sys
import os

st.set_page_config(page_title="Debug — Credit Risk", layout="wide")
st.title("Credit Risk Debug & Visualization")

# =============================================================================
# Logger
# =============================================================================
LOG_PATH = "debug_join.log"
logging.basicConfig(
    filename=LOG_PATH, filemode="w", level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("debug")

def lsec(t):
    log.info("\n" + "="*70 + f"\n{t}\n" + "="*70)

def ldf(label, df, n=5):
    log.info(f"{label} shape: {df.shape}")
    log.info(f"{label} columns: {list(df.columns)}")
    log.info(f"{label} sample:\n{df.head(n).to_string()}")

def ld(label, d):
    log.info(f"{label}:")
    for k, v in d.items():
        log.info(f"  {k}: {v}")

# =============================================================================
# et_pipeline embedded
# =============================================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import et_pipeline as etp
    ET_OK = True
except ImportError:
    ET_OK = False

def _transform_availability(df, sheet_name):
    if ET_OK:
        return etp._transform_availability(df, sheet_name)
    # fallback minimal
    df.columns = [str(c).strip() for c in df.columns]
    df.insert(0, "SOURCE_SHEET", str(sheet_name))
    return df, {}

def _clean_overdue(df):
    if ET_OK:
        return etp._clean_overdue(df)
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]
    return df

# =============================================================================
# Upload
# =============================================================================
lsec("STEP 1 — Upload Files")
st.header("1. Upload Files")
st.info("Availability = Credit Availability.xlsx | Overdue = ไฟล์ที่มี XTab DS_1")

c1, c2 = st.columns(2)
with c1:
    avail_file  = st.file_uploader("Availability File (sheets by year)", type=["xlsx"], key="av")
with c2:
    overdue_file = st.file_uploader("Overdue File (XTab DS_1)", type=["xlsx"], key="ov")

if not avail_file or not overdue_file:
    st.info("Upload ทั้ง 2 ไฟล์เพื่อเริ่ม")
    st.stop()

avail_bytes   = avail_file.read()
overdue_bytes = overdue_file.read()
log.info(f"avail: {avail_file.name} ({len(avail_bytes):,} bytes)")
log.info(f"overdue: {overdue_file.name} ({len(overdue_bytes):,} bytes)")

# =============================================================================
# Step 2 : Load Availability — แก้ให้ insert SOURCE_SHEET เอง
# =============================================================================
lsec("STEP 2 — Load Availability")
st.header("2. Load Availability")

av_xls    = pd.ExcelFile(io.BytesIO(avail_bytes), engine="openpyxl")
av_sheets = av_xls.sheet_names
log.info(f"avail sheets: {av_sheets}")
st.write(f"Sheets: {av_sheets}")

sel_av = st.multiselect(
    "เลือก sheets", av_sheets,
    default=[s for s in av_sheets if s not in ["Sheet2","Sheet1","Sheet3"]],
)
if not sel_av:
    st.stop()

av_frames = []
for sheet in sel_av:
    try:
        raw      = pd.read_excel(av_xls, sheet_name=sheet)
        df_t, _  = _transform_availability(raw, sheet)

        # ------------------------------------------------------------------
        # Insert SOURCE_SHEET ถ้ายังไม่มี
        # (et_pipeline._transform_availability ไม่ insert เอง
        #  มันทำใน run_pipeline() ข้างนอก)
        # ------------------------------------------------------------------
        if "SOURCE_SHEET" not in df_t.columns:
            df_t.insert(0, "SOURCE_SHEET", str(sheet))

        av_frames.append(df_t)
        log.info(f"avail sheet '{sheet}': {len(df_t)} rows")
    except Exception as e:
        log.error(f"sheet '{sheet}' error: {e}")
        st.warning(f"sheet '{sheet}' error: {e}")

df_avail = pd.concat(av_frames, ignore_index=True) if av_frames else pd.DataFrame()
ldf("df_avail", df_avail)

st.write({
    "shape":        df_avail.shape,
    "SOURCE_SHEET": sorted(df_avail["SOURCE_SHEET"].unique().tolist())
                    if "SOURCE_SHEET" in df_avail.columns else "MISSING",
    "columns":      list(df_avail.columns),
})

show_av = [c for c in ["SOURCE_SHEET","CUSTOMER_CODE","CUSTOMER_NAME",
                        "CURRENT_DEBT_MILLION_THB","ESTIMATE_AMOUNT","CLEAN_CREDIT_MB"]
           if c in df_avail.columns]
st.dataframe(df_avail[show_av].head(5))

# =============================================================================
# Step 3 : Load Overdue
# =============================================================================
lsec("STEP 3 — Load Overdue")
st.header("3. Load Overdue")

ov_xls    = pd.ExcelFile(io.BytesIO(overdue_bytes), engine="openpyxl")
ov_sheets = ov_xls.sheet_names
log.info(f"overdue sheets: {ov_sheets}")
st.write(f"Sheets: {ov_sheets}")

sel_ov = st.selectbox(
    "เลือก sheet ของ overdue",
    [s for s in ov_sheets if "xtab" in s.lower() or "filter" in s.lower()] or ov_sheets,
)
df_ov_raw = pd.read_excel(ov_xls, sheet_name=sel_ov)
df_ov     = _clean_overdue(df_ov_raw.copy())
ldf("df_overdue", df_ov)

st.write(f"df_overdue shape: {df_ov.shape} | columns: {list(df_ov.columns)}")
st.dataframe(df_ov.head(5))

# Join key
join_key = "Customer" if "Customer" in df_ov.columns else df_ov.columns[1]
st.write(f"Join key: **{join_key}**")

# =============================================================================
# Step 4 : Match Analysis
# =============================================================================
lsec("STEP 4 — Match Analysis")
st.header("4. Match Analysis")

df_ov[join_key] = pd.to_numeric(df_ov[join_key], errors="coerce").fillna(0).astype(int)
if "CUSTOMER_CODE" in df_avail.columns:
    df_avail["CUSTOMER_CODE"] = pd.to_numeric(df_avail["CUSTOMER_CODE"], errors="coerce").fillna(0).astype(int)

ov_codes   = set(df_ov[join_key].unique())
av_codes   = set(df_avail["CUSTOMER_CODE"].unique()) if "CUSTOMER_CODE" in df_avail.columns else set()
matched    = ov_codes & av_codes
unmatched  = ov_codes - av_codes

ld("match_analysis", {
    "overdue unique codes":  len(ov_codes),
    "avail unique codes":    len(av_codes),
    "MATCHED":               len(matched),
    "NOT matched":           len(unmatched),
})
st.write({"overdue": len(ov_codes), "avail": len(av_codes),
          "MATCHED": len(matched),  "NOT matched": len(unmatched)})
st.success(f"Matched: {sorted(matched)[:15]}")
st.warning(f"NOT matched: {sorted(unmatched)[:15]}")

# =============================================================================
# Step 5 : Company Code Filter
# =============================================================================
lsec("STEP 5 — Company Code Filter")
st.header("5. Company Code Filter")

comp_col = next((c for c in df_ov.columns if "companycode" in c.lower().replace(" ","")), None)
log.info(f"CompanyCode column: {comp_col}")
if comp_col:
    log.info(f"values: {df_ov[comp_col].unique().tolist()[:10]}")
    st.write(f"CompanyCode column: `{comp_col}` | values: {df_ov[comp_col].unique().tolist()}")

# =============================================================================
# Step 6 : Transform Pipeline
# =============================================================================
lsec("STEP 6 — Transform Pipeline")
st.header("6. Transform Pipeline")

# ------------------------------------------------------------------
# 6A : OverdueAmount convention
# จาก EDA: OverdueAmount > 0 = ค้างจริง
# ------------------------------------------------------------------
st.markdown("#### 6A — OverdueAmount Convention")
ov = df_ov.copy()
ov["OverdueAmount_num"] = pd.to_numeric(
    ov.get("OverdueAmount", 0), errors="coerce"
).fillna(0)
ov["InvoiceAmount_num"] = pd.to_numeric(
    ov.get("InvoiceAmount", 0), errors="coerce"
).fillna(0)

st.write({
    "OverdueAmt > 0":  int((ov["OverdueAmount_num"] > 0).sum()),
    "OverdueAmt = 0":  int((ov["OverdueAmount_num"] == 0).sum()),
    "OverdueAmt < 0":  int((ov["OverdueAmount_num"] < 0).sum()),
})

# ------------------------------------------------------------------
# 6B : Parse dates + DPD fix
# ------------------------------------------------------------------
st.markdown("#### 6B — Parse Dates + DPD (Fixed)")
today = pd.Timestamp("today").normalize()

ov["OriginalDueDate_parsed"] = pd.to_datetime(
    ov["OriginalDueDate"].astype(str).str.strip()
      .replace({"#": None, "nan": None, "": None}),
    format="%Y%m%d", errors="coerce",
)
ov["CollectionDate_parsed"] = pd.to_datetime(
    ov["CollectionDate"].astype(str).str.strip()
      .replace({"#": None, "nan": None, "": None}),
    format="%Y%m%d", errors="coerce",
)

ov["IsPaid"]  = ov["CollectionDate_parsed"].notna()
ov["DPD"]     = np.where(
    ov["IsPaid"], 0,
    np.where(
        ov["OriginalDueDate_parsed"].notna(),
        (today - ov["OriginalDueDate_parsed"]).dt.days.clip(lower=0),
        np.nan,
    ),
)
ov["DueYear"] = ov["OriginalDueDate_parsed"].dt.year.astype("Int64")

# Days Since Last Payment (สำหรับ Approach 6)
ov["DaysSincePayment"] = np.where(
    ov["CollectionDate_parsed"].notna(),
    (today - ov["CollectionDate_parsed"]).dt.days.clip(lower=0),
    np.nan,
)

# DPD Bucket (สำหรับ Approach 4)
DPD_BINS   = [-1,   0,   30,   60,   90,  float("inf")]
DPD_LABELS = ["Current", "1-30d", "31-60d", "61-90d", "90+d"]
ov["DPD_Bucket"] = pd.cut(
    ov["DPD"].fillna(0).clip(lower=0),
    bins=DPD_BINS, labels=DPD_LABELS,
).astype(str)

st.write({
    "IsPaid":          int(ov["IsPaid"].sum()),
    "Unpaid":          int((~ov["IsPaid"]).sum()),
    "OrigDate parsed": int(ov["OriginalDueDate_parsed"].notna().sum()),
    "DPD > 0":         int((ov["DPD"].fillna(0) > 0).sum()),
})

# ------------------------------------------------------------------
# 6C : Aggregate customer level
# ใช้ ALL rows (ไม่กรอง OverdueAmount > 0)
# เพราะ Current Debt จาก avail ไม่ขึ้นกับ OverdueAmount
# ------------------------------------------------------------------
st.markdown("#### 6C — Aggregate to Customer Level")

name_col = next(
    (c for c in ov.columns if "customername" in c.lower().replace(" ", "")),
    join_key,
)

# Invoice ที่ค้างจริง (OverdueAmount > 0)
overdue_only = ov[ov["OverdueAmount_num"] > 0].copy()
overdue_only["OverdueMB"] = overdue_only["OverdueAmount_num"] / 1_000_000

# Aggregate overdue per customer
cust_overdue = (
    overdue_only.groupby([join_key, name_col])
    .agg(
        TotalOverdueMB   = ("OverdueMB",          "sum"),
        OverdueInvoices  = ("OverdueMB",          "count"),
        AvgDPD           = ("DPD",                "mean"),
        MaxDPD           = ("DPD",                "max"),
        DaysSincePayment = ("DaysSincePayment",   "min"),  # วันล่าสุดที่จ่าย
    )
    .reset_index()
    .rename(columns={join_key: "Customer", name_col: "CustomerName"})
)

# All invoices per customer (สำหรับ InvoiceCount รวม)
cust_all_inv = (
    ov.groupby([join_key])
    .agg(TotalInvoices = (join_key, "count"))
    .reset_index()
    .rename(columns={join_key: "Customer"})
)

cust_risk = cust_overdue.merge(cust_all_inv, on="Customer", how="left")
cust_risk["DaysSincePayment"] = cust_risk["DaysSincePayment"].fillna(9999)

st.write(f"Customers with overdue > 0: {len(cust_risk)}")
st.dataframe(cust_risk.sort_values("TotalOverdueMB", ascending=False).head(10))

# ------------------------------------------------------------------
# 6D : Join Availability
# ดึง CurrentDebt, CleanCredit, EstAmount, TYPE
# ------------------------------------------------------------------
st.markdown("#### 6D — Join Availability")

cust_risk["CurrentDebtMB"]  = np.nan
cust_risk["CleanCreditMB"]  = np.nan
cust_risk["EstAmountMB"]    = np.nan
cust_risk["TYPE"]           = "Unknown"
cust_risk["UtilizationPct"] = np.nan

avail_prep   = pd.DataFrame()
avail_latest = pd.DataFrame()

if not df_avail.empty and "CUSTOMER_CODE" in df_avail.columns:
    avail_prep = df_avail.copy()

    if "SOURCE_SHEET" not in avail_prep.columns:
        avail_prep["SOURCE_SHEET"] = "unknown"

    avail_prep["SOURCE_SHEET"]  = avail_prep["SOURCE_SHEET"].astype(str).str.strip()
    avail_prep["CUSTOMER_CODE"] = (
        pd.to_numeric(avail_prep["CUSTOMER_CODE"], errors="coerce")
        .fillna(0).astype(int)
    )

    if "DATE" in avail_prep.columns:
        avail_prep = (
            avail_prep.sort_values("DATE", ascending=False)
            .drop_duplicates(subset=["CUSTOMER_CODE", "SOURCE_SHEET"])
        )
    else:
        avail_prep = avail_prep.drop_duplicates(
            subset=["CUSTOMER_CODE", "SOURCE_SHEET"]
        )

    keep_cols = ["CUSTOMER_CODE"]
    for c in ["CURRENT_DEBT_MILLION_THB","CLEAN_CREDIT_MB","ESTIMATE_AMOUNT","TYPE"]:
        if c in avail_prep.columns:
            keep_cols.append(c)

    avail_latest = (
        avail_prep.sort_values("SOURCE_SHEET", ascending=False)
        .drop_duplicates(subset=["CUSTOMER_CODE"])[keep_cols]
        .copy()
    )

    merged = cust_risk.merge(
        avail_latest,
        left_on="Customer", right_on="CUSTOMER_CODE", how="left",
    )

    for target, source in [
        ("CurrentDebtMB", "CURRENT_DEBT_MILLION_THB"),
        ("CleanCreditMB", "CLEAN_CREDIT_MB"),
        ("EstAmountMB",   "ESTIMATE_AMOUNT"),
    ]:
        if source in merged.columns:
            cust_risk[target] = merged[source].values

    if "TYPE" in merged.columns:
        cust_risk["TYPE"] = merged["TYPE"].fillna("Unknown").values

    cust_risk["UtilizationPct"] = (
        cust_risk["CurrentDebtMB"] /
        cust_risk["CleanCreditMB"].replace(0, np.nan) * 100
    ).clip(0, 200)

    # Overdue Ratio = OverdueMB / CurrentDebtMB
    cust_risk["OverdueRatio"] = (
        cust_risk["TotalOverdueMB"] /
        cust_risk["CurrentDebtMB"].replace(0, np.nan) * 100
    ).clip(0, 200).fillna(0)

    st.write({
        "joined":   int(cust_risk["CurrentDebtMB"].notna().sum()),
        "unjoined": int(cust_risk["CurrentDebtMB"].isna().sum()),
    })
else:
    cust_risk["OverdueRatio"] = 0.0
    st.warning("df_avail ว่าง — ข้าม join")

# ------------------------------------------------------------------
# 6E : Final transform + fillna สำหรับ visualization
# ------------------------------------------------------------------
st.markdown("#### 6E — Final Transform")

for col in ["CurrentDebtMB","CleanCreditMB","EstAmountMB","UtilizationPct","OverdueRatio"]:
    cust_risk[col] = cust_risk[col].fillna(0)

total_overdue          = cust_risk["TotalOverdueMB"].sum()
cust_risk["PctPortfolio"] = (
    cust_risk["TotalOverdueMB"] / max(total_overdue, 0.001) * 100
).round(2)

st.write({
    "customers":        len(cust_risk),
    "total OverdueMB":  round(float(total_overdue), 4),
    "has CurrentDebt":  int((cust_risk["CurrentDebtMB"] > 0).sum()),
    "has OverdueRatio": int((cust_risk["OverdueRatio"] > 0).sum()),
})
st.dataframe(
    cust_risk[[
        "CustomerName","TotalOverdueMB","CurrentDebtMB","CleanCreditMB",
        "OverdueRatio","AvgDPD","DaysSincePayment","OverdueInvoices","TYPE",
    ]].sort_values("TotalOverdueMB", ascending=False).head(15)
)


# =============================================================================
# Step 7: New Overdue Intelligence — Options 1, 2, 3
# =============================================================================
lsec("STEP 7 — New Overdue Intelligence")
st.header("7. New Overdue Intelligence")

import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

if cust_risk.empty:
    st.warning("ไม่มีข้อมูลใน cust_risk — ข้าม Step 7")
else:
    # ==========================================================================
    # ── HELPERS
    # ==========================================================================
    def to_native(series):
        out = []
        for v in series:
            if isinstance(v, float) and np.isnan(v):
                out.append(None)
            elif isinstance(v, np.integer):
                out.append(int(v))
            elif isinstance(v, np.floating):
                out.append(float(v))
            elif isinstance(v, np.str_):
                out.append(str(v))
            else:
                out.append(v)
        return out

    def bubble_norm(series, lo=6, hi=60):
        s = series.clip(lower=0.01)
        mx = float(s.max()) or 1.0
        return (s / mx * (hi - lo) + lo).tolist()

    TYPE_COLORS = px.colors.qualitative.Set2

    # ==========================================================================
    # ── GLOBAL FILTER BAR
    # ==========================================================================
    st.markdown("---")
    st.subheader("🔧 Global Filters")

    with st.container():
        fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 1.5, 1.5])

        min_date_raw = ov["OriginalDueDate_parsed"].dropna().min()
        max_date_raw = ov["OriginalDueDate_parsed"].dropna().max()
        min_date = min_date_raw.date() if not pd.isna(min_date_raw) else date(2020, 1, 1)
        max_date = max_date_raw.date() if not pd.isna(max_date_raw) else date.today()

        with fcol1:
            filter_start = st.date_input(
                "📅 Due Date — Start",
                value=min_date, min_value=min_date, max_value=max_date,
                key="f_start",
            )
        with fcol2:
            filter_end = st.date_input(
                "📅 Due Date — End",
                value=max_date, min_value=min_date, max_value=max_date,
                key="f_end",
            )
        with fcol3:
            granularity = st.selectbox(
                "📊 Group By (Opt 2 & 3)",
                options=["Yearly", "Monthly", "Weekly", "Daily"],
                index=1,
                key="f_gran",
            )
        with fcol4:
            all_types = sorted(cust_risk["TYPE"].dropna().unique().tolist())
            sel_types = st.multiselect(
                "🏷️ Product Type",
                options=all_types, default=all_types,
                key="f_type",
            )

    if filter_start > filter_end:
        st.error("Start date ต้องไม่เกิน End date")
        st.stop()

    # ── Map granularity → pandas Period alias ─────────────────────────────────
    GRAN_PERIOD = {"Yearly": "Y", "Monthly": "M", "Weekly": "W", "Daily": "D"}
    gran_p = GRAN_PERIOD[granularity]

    # ── Invoice-level filtered ─────────────────────────────────────────────────
    ov_f = ov[
        ov["OriginalDueDate_parsed"].notna() &
        (ov["OriginalDueDate_parsed"].dt.date >= filter_start) &
        (ov["OriginalDueDate_parsed"].dt.date <= filter_end)
    ].copy()

    ov_f["Period"] = ov_f["OriginalDueDate_parsed"].dt.to_period(gran_p).astype(str)

    # ── Customer-level filtered ───────────────────────────────────────────────
    valid_custs_f = set(
        ov_f[ov_f["OverdueAmount_num"] > 0][join_key].unique().tolist()
    )
    cr_f = cust_risk[cust_risk["Customer"].isin(valid_custs_f)].copy()
    if sel_types:
        cr_f = cr_f[cr_f["TYPE"].isin(sel_types)].copy()

    # ── Summary banner ─────────────────────────────────────────────────────────
    st.markdown(
        f"> **Date range:** {filter_start} → {filter_end} &nbsp;|&nbsp; "
        f"**Group:** {granularity} &nbsp;|&nbsp; "
        f"**Types:** {', '.join(sel_types) if sel_types else '—'} &nbsp;|&nbsp; "
        f"**Invoices:** {len(ov_f):,} &nbsp;|&nbsp; "
        f"**Customers:** {len(cr_f):,}"
    )

    if cr_f.empty:
        st.warning("ไม่มีข้อมูลหลังกรอง — ลองขยาย Date Range หรือเลือก Type เพิ่ม")
        st.stop()

    today_ts = pd.Timestamp("today").normalize()

    # ==========================================================================
    # Option 1 : New Overdue Monitoring
    # ==========================================================================
    st.markdown("---")
    st.subheader("Option 1 — New Overdue Monitoring")
    st.caption("Business Q: ลูกค้าคนไหนเพิ่งกลายเป็น Overdue?")

    # ── คำนวณ First Overdue Date ต่อ Customer จาก invoice ที่ filtered ─────────
    paid_rate = float(ov_f["IsPaid"].mean()) if "IsPaid" in ov_f.columns else 0.0

    if paid_rate >= 0.99:
        # CollectionDate ไม่น่าเชื่อถือ — ข้าม IsPaid filter
        ov_active = ov_f[ov_f["OverdueAmount_num"] > 0].copy()
        st.caption(
            f"⚠️ CollectionDate parse rate ต่ำ ({paid_rate:.0%} rows มี IsPaid=True) "
            f"— ใช้ OverdueAmount > 0 แทน"
        )
    else:
        ov_active = ov_f[
            (ov_f["OverdueAmount_num"] > 0) &
            (~ov_f["IsPaid"])
        ].copy()

    if ov_active.empty:
        st.info("ไม่มี active overdue invoice ในช่วงที่เลือก")
    else:
        first_overdue = (
            ov_active.groupby(join_key)["OriginalDueDate_parsed"]
            .min()
            .reset_index()
            .rename(columns={join_key: "Customer",
                             "OriginalDueDate_parsed": "FirstOverdueDate"})
        )

        df_opt1 = cr_f[cr_f["TotalOverdueMB"] > 0].copy()
        df_opt1 = df_opt1.merge(first_overdue, on="Customer", how="left")

        # Days Since First Overdue
        df_opt1["DaysSinceFirstOverdue"] = (
            today_ts - df_opt1["FirstOverdueDate"]
        ).dt.days.clip(lower=0)

        # Status buckets
        def overdue_status(d):
            if pd.isna(d):      return "Unknown"
            d = int(d)
            if d <= 7:          return "🆕 New (≤7d)"
            elif d <= 30:       return "🟡 Recent (8-30d)"
            elif d <= 90:       return "🟠 Aging (31-90d)"
            else:               return "🔴 Chronic (>90d)"

        df_opt1["OverdueStatus"] = df_opt1["DaysSinceFirstOverdue"].apply(overdue_status)

        STATUS_ORDER = [
            "🆕 New (≤7d)",
            "🟡 Recent (8-30d)",
            "🟠 Aging (31-90d)",
            "🔴 Chronic (>90d)",
            "Unknown",
        ]
        STATUS_COLOR = {
            "🆕 New (≤7d)":      "#1abc9c",
            "🟡 Recent (8-30d)": "#f1c40f",
            "🟠 Aging (31-90d)": "#e67e22",
            "🔴 Chronic (>90d)": "#e74c3c",
            "Unknown":           "#95a5a6",
        }

        # ── KPI row ──────────────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        for col_ui, status, col_ref in [
            (k1, "🆕 New (≤7d)",      k1),
            (k2, "🟡 Recent (8-30d)", k2),
            (k3, "🟠 Aging (31-90d)", k3),
            (k4, "🔴 Chronic (>90d)", k4),
        ]:
            sub = df_opt1[df_opt1["OverdueStatus"] == status]
            col_ui.metric(
                label=status,
                value=f"{len(sub)} customers",
                delta=f"{sub['TotalOverdueMB'].sum():.2f} MB overdue",
                delta_color="inverse",
            )

        # ── Scatter Plot ──────────────────────────────────────────────────────
        bs1 = bubble_norm(df_opt1["CurrentDebtMB"].fillna(0.01))
        all_i1 = df_opt1.index.tolist()

        fig1 = go.Figure()
        for status in STATUS_ORDER:
            grp = df_opt1[df_opt1["OverdueStatus"] == status]
            if grp.empty:
                continue
            idx = grp.index.tolist()
            fig1.add_trace(go.Scatter(
                x    = to_native(grp["DaysSinceFirstOverdue"]),
                y    = to_native(grp["TotalOverdueMB"]),
                mode = "markers",
                name = status,
                marker = dict(
                    size     = [bs1[all_i1.index(i)] for i in idx],
                    color    = STATUS_COLOR.get(status, "#95a5a6"),
                    opacity  = 0.80,
                    line     = dict(width=1, color="white"),
                    sizemode = "diameter",
                ),
                text = to_native(grp["CustomerName"]),
                customdata = list(zip(
                    to_native(grp["CurrentDebtMB"]),
                    to_native(grp["OverdueInvoices"]),
                    to_native(grp["AvgDPD"]),
                    [str(d.date()) if pd.notna(d) else "N/A"
                     for d in grp["FirstOverdueDate"]],
                )),
                hovertemplate = (
                    "<b>%{text}</b><br>"
                    "Days Since First Overdue: <b>%{x}</b> days<br>"
                    "Total Overdue: <b>%{y:.2f} MB</b><br>"
                    "Current Debt: %{customdata[0]:.2f} MB<br>"
                    "Overdue Invoices: %{customdata[1]}<br>"
                    "Avg DPD: %{customdata[2]:.0f} days<br>"
                    "First Overdue Date: %{customdata[3]}<extra></extra>"
                ),
            ))

        # Reference lines
        for d_ref, lbl, clr in [
            (7,  "New →",    "#1abc9c"),
            (30, "Recent →", "#f1c40f"),
            (90, "Aging →",  "#e67e22"),
        ]:
            fig1.add_vline(
                x=float(d_ref), line_dash="dash",
                line_color=clr, opacity=0.5,
                annotation_text=lbl,
                annotation_position="top right",
            )

        # Highlight zone: รีบโทร (x <= 30, y = top half)
        med_ov1 = float(df_opt1["TotalOverdueMB"].median())
        fig1.add_hrect(
            y0=med_ov1,
            y1=float(df_opt1["TotalOverdueMB"].max()) * 1.05,
            x0=0, x1=30,
            fillcolor="#1abc9c", opacity=0.06,
            line_width=0,
            annotation_text="🚨 รีบโทรหาด่วน",
            annotation_position="top left",
            annotation_font=dict(color="#1abc9c", size=12),
        )

        fig1.update_layout(
            title        = "New Overdue Monitoring — Days Since First Overdue vs Overdue Amount",
            xaxis        = dict(title="Days Since First Overdue (days)", zeroline=False),
            yaxis        = dict(title="Total Overdue Amount (MB)", zeroline=False),
            height       = 560,
            legend       = dict(title="Status"),
            plot_bgcolor = "#f9f9f9",
        )
        st.plotly_chart(fig1, use_container_width=True)

        # ── Detail table: New + Recent เรียง Overdue DESC ─────────────────────
        urgent = df_opt1[
            df_opt1["OverdueStatus"].isin(["🆕 New (≤7d)", "🟡 Recent (8-30d)"])
        ].sort_values("TotalOverdueMB", ascending=False).copy()

        if not urgent.empty:
            st.markdown("**🚨 Urgent List — New & Recent Overdue**")
            show_cols = [c for c in [
                "CustomerName", "OverdueStatus", "DaysSinceFirstOverdue",
                "TotalOverdueMB", "CurrentDebtMB", "OverdueInvoices",
                "AvgDPD", "TYPE",
            ] if c in urgent.columns]
            tbl1 = urgent[show_cols].copy()
            for c in ["TotalOverdueMB", "CurrentDebtMB", "AvgDPD"]:
                if c in tbl1.columns:
                    tbl1[c] = tbl1[c].round(2)
            st.dataframe(tbl1, hide_index=True)

    # ==========================================================================
    # Option 2 : Overdue Velocity
    # ==========================================================================
    st.markdown("---")
    st.subheader("Option 2 — Overdue Velocity")
    st.caption("Business Q: Overdue กำลังโตเร็วแค่ไหน? ใครกำลังแย่ลง (ไม่ใช่แค่ใครแย่แล้ว)")

    ov_ov = ov_f[ov_f["OverdueAmount_num"] > 0].copy()
    ov_ov["OverdueMB"] = ov_ov["OverdueAmount_num"] / 1_000_000

    # ── หา 2 periods ล่าสุดใน range ──────────────────────────────────────────
    all_periods = sorted(ov_ov["Period"].dropna().unique().tolist())

    if len(all_periods) < 2:
        st.info(
            f"มีเพียง {len(all_periods)} period ในช่วงที่เลือก "
            f"({', '.join(all_periods)}) — ต้องการอย่างน้อย 2 periods เพื่อคำนวณ Velocity\n\n"
            f"💡 ลองขยาย Date Range หรือเปลี่ยน Group By เป็น Monthly/Weekly"
        )
    else:
        prev_period = all_periods[-2]
        curr_period = all_periods[-1]

        st.caption(
            f"เปรียบเทียบ **{prev_period}** (previous) → **{curr_period}** (current)"
        )

        def agg_period(period_str):
            sub = ov_ov[ov_ov["Period"] == period_str]
            return (
                sub.groupby(join_key)
                .agg(OverdueMB=(  "OverdueMB", "sum"),
                     Invoices  =(join_key,     "count"))
                .reset_index()
                .rename(columns={join_key: "Customer"})
            )

        df_prev = agg_period(prev_period).rename(
            columns={"OverdueMB": "PrevOverdueMB", "Invoices": "PrevInvoices"}
        )
        df_curr = agg_period(curr_period).rename(
            columns={"OverdueMB": "CurrOverdueMB", "Invoices": "CurrInvoices"}
        )

        # Outer join: ลูกค้าที่อยู่ใน period ใด period หนึ่ง
        df_vel = df_curr.merge(df_prev, on="Customer", how="outer")
        df_vel["CurrOverdueMB"] = df_vel["CurrOverdueMB"].fillna(0)
        df_vel["PrevOverdueMB"] = df_vel["PrevOverdueMB"].fillna(0)

        df_vel["VelocityMB"]  = df_vel["CurrOverdueMB"] - df_vel["PrevOverdueMB"]
        df_vel["VelocityPct"] = (
            df_vel["VelocityMB"] /
            df_vel["PrevOverdueMB"].replace(0, np.nan) * 100
        ).fillna(                                          # ← ต้องเป็น Series ไม่ใช่ ndarray
            pd.Series(
                np.where(df_vel["CurrOverdueMB"] > 0, 100.0, 0.0),
                index=df_vel.index,
            )
        )

        # Join CustomerName + CurrentDebtMB
        name_debt = cr_f[["Customer","CustomerName","CurrentDebtMB","TYPE"]].drop_duplicates("Customer")
        df_vel = df_vel.merge(name_debt, on="Customer", how="left")
        df_vel["CustomerName"] = df_vel["CustomerName"].fillna(df_vel["Customer"].astype(str))

        # Velocity tier
        def vel_tier(v):
            if v > 10:   return "📈 Surging >10MB"
            elif v > 3:  return "⬆️ Growing 3-10MB"
            elif v > 0:  return "↗️ Rising 0-3MB"
            elif v == 0: return "➡️ Flat"
            else:        return "📉 Improving"

        df_vel["VelocityTier"] = df_vel["VelocityMB"].apply(vel_tier)

        VEL_COLOR = {
            "📈 Surging >10MB":  "#c0392b",
            "⬆️ Growing 3-10MB": "#e67e22",
            "↗️ Rising 0-3MB":   "#f1c40f",
            "➡️ Flat":           "#95a5a6",
            "📉 Improving":      "#27ae60",
        }
        VEL_ORDER = [
            "📈 Surging >10MB", "⬆️ Growing 3-10MB",
            "↗️ Rising 0-3MB",  "➡️ Flat", "📉 Improving",
        ]

        # ── KPI ───────────────────────────────────────────────────────────────
        v1, v2, v3, v4 = st.columns(4)
        surging = df_vel[df_vel["VelocityMB"] > 10]
        improving = df_vel[df_vel["VelocityMB"] < 0]
        net_change = float(df_vel["VelocityMB"].sum())
        v1.metric("📈 Surging (>10MB)",
                  f"{len(surging)} customers",
                  f"+{surging['VelocityMB'].sum():.2f} MB",
                  delta_color="inverse")
        v2.metric("⬆️ Growing / Rising",
                  f"{int((df_vel['VelocityMB'] > 0).sum())} customers",
                  f"+{df_vel[df_vel['VelocityMB']>0]['VelocityMB'].sum():.2f} MB",
                  delta_color="inverse")
        v3.metric("📉 Improving",
                  f"{len(improving)} customers",
                  f"{improving['VelocityMB'].sum():.2f} MB",
                  delta_color="normal")
        v4.metric("Net Portfolio Δ",
                  f"{net_change:+.2f} MB",
                  f"{prev_period} → {curr_period}",
                  delta_color="inverse" if net_change > 0 else "normal")

        # ── Top Growth Bar Chart ───────────────────────────────────────────────
        top_growth = (
            df_vel[df_vel["VelocityMB"] > 0]
            .sort_values("VelocityMB", ascending=False)
            .head(20)
            .copy()
        )
        top_improve = (
            df_vel[df_vel["VelocityMB"] < 0]
            .sort_values("VelocityMB", ascending=True)
            .head(10)
            .copy()
        )

        if not top_growth.empty:
            fig2a = go.Figure()
            fig2a.add_trace(go.Bar(
                x            = to_native(top_growth["VelocityMB"].round(3)),
                y            = top_growth["CustomerName"].tolist(),
                orientation  = "h",
                marker_color = [
                    VEL_COLOR.get(t, "#95a5a6")
                    for t in top_growth["VelocityTier"].tolist()
                ],
                text = [
                    f"+{v:.2f} MB ({p:+.0f}%)"
                    for v, p in zip(top_growth["VelocityMB"], top_growth["VelocityPct"])
                ],
                textposition = "outside",
                customdata   = list(zip(
                    to_native(top_growth["CurrOverdueMB"].round(2)),
                    to_native(top_growth["PrevOverdueMB"].round(2)),
                    to_native(top_growth["CurrentDebtMB"].fillna(0).round(2)),
                    top_growth["VelocityTier"].tolist(),
                )),
                hovertemplate = (
                    "<b>%{y}</b><br>"
                    "Δ Overdue: <b>%{x:+.2f} MB</b><br>"
                    f"Prev ({prev_period}): %{{customdata[1]:.2f}} MB<br>"
                    f"Curr ({curr_period}): %{{customdata[0]:.2f}} MB<br>"
                    "Current Debt: %{customdata[2]:.2f} MB<br>"
                    "Tier: %{customdata[3]}<extra></extra>"
                ),
            ))
            fig2a.update_layout(
                title        = f"Top 20 Overdue Growth — {prev_period} → {curr_period}",
                xaxis        = dict(title="Δ Overdue Amount (MB)"),
                yaxis        = dict(autorange="reversed"),
                height       = max(350, len(top_growth) * 36 + 80),
                plot_bgcolor = "#f9f9f9",
            )
            st.plotly_chart(fig2a, use_container_width=True)

        # ── Scatter: Current vs Previous ──────────────────────────────────────
        df_vel_plot = df_vel[
            (df_vel["CurrOverdueMB"] > 0) | (df_vel["PrevOverdueMB"] > 0)
        ].copy()

        if not df_vel_plot.empty:
            bs2 = bubble_norm(df_vel_plot["CurrentDebtMB"].fillna(0.01))
            all_i2 = df_vel_plot.index.tolist()

            fig2b = go.Figure()
            for tier in VEL_ORDER:
                grp = df_vel_plot[df_vel_plot["VelocityTier"] == tier]
                if grp.empty:
                    continue
                idx = grp.index.tolist()
                fig2b.add_trace(go.Scatter(
                    x    = to_native(grp["PrevOverdueMB"]),
                    y    = to_native(grp["CurrOverdueMB"]),
                    mode = "markers",
                    name = tier,
                    marker = dict(
                        size     = [bs2[all_i2.index(i)] for i in idx],
                        color    = VEL_COLOR.get(tier, "#95a5a6"),
                        opacity  = 0.78,
                        line     = dict(width=1, color="white"),
                        sizemode = "diameter",
                    ),
                    text = to_native(grp["CustomerName"]),
                    customdata = list(zip(
                        to_native(grp["VelocityMB"].round(3)),
                        to_native(grp["VelocityPct"].round(1)),
                        to_native(grp["CurrentDebtMB"].fillna(0).round(2)),
                    )),
                    hovertemplate = (
                        "<b>%{text}</b><br>"
                        f"Prev ({prev_period}): %{{x:.2f}} MB<br>"
                        f"Curr ({curr_period}): %{{y:.2f}} MB<br>"
                        "Δ: <b>%{customdata[0]:+.2f} MB</b> "
                        "(%{customdata[1]:+.0f}%)<br>"
                        "Current Debt: %{customdata[2]:.2f} MB<extra></extra>"
                    ),
                ))

            # Diagonal = no change line
            max_axis = float(max(
                df_vel_plot["CurrOverdueMB"].max(),
                df_vel_plot["PrevOverdueMB"].max()
            )) * 1.05
            fig2b.add_trace(go.Scatter(
                x=[0, max_axis], y=[0, max_axis],
                mode="lines",
                line=dict(dash="dot", color="gray", width=1),
                showlegend=False,
                hoverinfo="skip",
            ))
            # Zone annotations
            fig2b.add_annotation(
                x=max_axis*0.15, y=max_axis*0.85,
                text="▲ แย่ลง<br>(above line)",
                showarrow=False,
                font=dict(color="#e74c3c", size=11),
                bgcolor="rgba(255,255,255,0.7)",
            )
            fig2b.add_annotation(
                x=max_axis*0.75, y=max_axis*0.12,
                text="▼ ดีขึ้น<br>(below line)",
                showarrow=False,
                font=dict(color="#27ae60", size=11),
                bgcolor="rgba(255,255,255,0.7)",
            )

            fig2b.update_layout(
                title        = f"Overdue: Previous vs Current Period (Bubble = Debt)",
                xaxis        = dict(title=f"Prev Overdue — {prev_period} (MB)",
                                    range=[-0.5, max_axis], zeroline=False),
                yaxis        = dict(title=f"Curr Overdue — {curr_period} (MB)",
                                    range=[-0.5, max_axis], zeroline=False),
                height       = 520,
                legend       = dict(title="Velocity"),
                plot_bgcolor = "#f9f9f9",
            )
            st.plotly_chart(fig2b, use_container_width=True)

        # ── Improving list ─────────────────────────────────────────────────────
        if not top_improve.empty:
            with st.expander("📉 Top Improving Customers"):
                tbl_imp = top_improve[[
                    "CustomerName","PrevOverdueMB","CurrOverdueMB","VelocityMB","VelocityPct"
                ]].copy()
                for c in ["PrevOverdueMB","CurrOverdueMB","VelocityMB","VelocityPct"]:
                    tbl_imp[c] = tbl_imp[c].round(2)
                st.dataframe(tbl_imp, hide_index=True)

    # ==========================================================================
    # Option 3 : Recently Deteriorated Customers
    # ==========================================================================
    st.markdown("---")
    st.subheader("Option 3 — Recently Deteriorated Customers")
    st.caption("Business Q: ใครกำลังไหลไปสู่ Default? (DPD Change สูงสุด)")

    # ── คำนวณ DPD per invoice per period ─────────────────────────────────────
    ov_dpd = ov_f[ov_f["OverdueAmount_num"] > 0].copy()
    ov_dpd["OverdueMB"] = ov_dpd["OverdueAmount_num"] / 1_000_000

    all_periods_3 = sorted(ov_dpd["Period"].dropna().unique().tolist())

    if len(all_periods_3) < 2:
        st.info(
            f"มีเพียง {len(all_periods_3)} period — ต้องการอย่างน้อย 2 periods\n\n"
            f"💡 ลองขยาย Date Range หรือเปลี่ยน Group By"
        )
    else:
        prev_p3 = all_periods_3[-2]
        curr_p3 = all_periods_3[-1]

        st.caption(
            f"เปรียบเทียบ **{prev_p3}** (previous) → **{curr_p3}** (current)"
        )

        def max_dpd_per_period(period_str):
            sub = ov_dpd[ov_dpd["Period"] == period_str]
            return (
                sub.groupby(join_key)
                .agg(
                    MaxDPD     = ("DPD",      "max"),
                    AvgDPD     = ("DPD",      "mean"),
                    OverdueMB  = ("OverdueMB","sum"),
                    Invoices   = (join_key,   "count"),
                )
                .reset_index()
                .rename(columns={join_key: "Customer"})
            )

        dpd_prev = max_dpd_per_period(prev_p3).rename(columns={
            "MaxDPD":    "PrevMaxDPD",
            "AvgDPD":    "PrevAvgDPD",
            "OverdueMB": "PrevOverdueMB",
            "Invoices":  "PrevInvoices",
        })
        dpd_curr = max_dpd_per_period(curr_p3).rename(columns={
            "MaxDPD":    "CurrMaxDPD",
            "AvgDPD":    "CurrAvgDPD",
            "OverdueMB": "CurrOverdueMB",
            "Invoices":  "CurrInvoices",
        })

        df_det = dpd_curr.merge(dpd_prev, on="Customer", how="outer")
        df_det["CurrMaxDPD"]    = df_det["CurrMaxDPD"].fillna(0)
        df_det["PrevMaxDPD"]    = df_det["PrevMaxDPD"].fillna(0)
        df_det["CurrOverdueMB"] = df_det["CurrOverdueMB"].fillna(0)
        df_det["PrevOverdueMB"] = df_det["PrevOverdueMB"].fillna(0)
        df_det["DPD_Change"]    = df_det["CurrMaxDPD"] - df_det["PrevMaxDPD"]

        # Join name + debt
        name_debt3 = cr_f[["Customer","CustomerName","CurrentDebtMB",
                            "TYPE","OverdueRatio"]].drop_duplicates("Customer")
        df_det = df_det.merge(name_debt3, on="Customer", how="left")
        df_det["CustomerName"] = df_det["CustomerName"].fillna(df_det["Customer"].astype(str))

        # Deterioration tier
        def deter_tier(chg):
            if chg >= 60:   return "🔴 Critical Δ ≥60d"
            elif chg >= 30: return "🟠 Severe Δ 30-59d"
            elif chg >= 10: return "🟡 Moderate Δ 10-29d"
            elif chg >  0:  return "🟢 Mild Δ 1-9d"
            elif chg == 0:  return "⬜ No Change"
            else:           return "✅ Improved"

        df_det["DeterTier"] = df_det["DPD_Change"].apply(deter_tier)
        DETER_COLOR = {
            "🔴 Critical Δ ≥60d":  "#c0392b",
            "🟠 Severe Δ 30-59d":  "#e67e22",
            "🟡 Moderate Δ 10-29d":"#f1c40f",
            "🟢 Mild Δ 1-9d":      "#2ecc71",
            "⬜ No Change":         "#bdc3c7",
            "✅ Improved":          "#27ae60",
        }
        DETER_ORDER = [
            "🔴 Critical Δ ≥60d", "🟠 Severe Δ 30-59d",
            "🟡 Moderate Δ 10-29d", "🟢 Mild Δ 1-9d",
            "⬜ No Change", "✅ Improved",
        ]

        # ── KPI ───────────────────────────────────────────────────────────────
        d1, d2, d3, d4 = st.columns(4)
        crit  = df_det[df_det["DPD_Change"] >= 60]
        sev   = df_det[df_det["DPD_Change"].between(30, 59)]
        mod   = df_det[df_det["DPD_Change"].between(10, 29)]
        imp   = df_det[df_det["DPD_Change"] < 0]
        d1.metric("🔴 Critical (Δ≥60d)",   f"{len(crit)} customers",
                  f"{crit['CurrOverdueMB'].sum():.2f} MB", delta_color="inverse")
        d2.metric("🟠 Severe (Δ30-59d)",   f"{len(sev)} customers",
                  f"{sev['CurrOverdueMB'].sum():.2f} MB",  delta_color="inverse")
        d3.metric("🟡 Moderate (Δ10-29d)", f"{len(mod)} customers",
                  f"{mod['CurrOverdueMB'].sum():.2f} MB",  delta_color="inverse")
        d4.metric("✅ Improved",            f"{len(imp)} customers",
                  f"{imp['CurrOverdueMB'].sum():.2f} MB",  delta_color="normal")

        # ── Ranked Horizontal Bar (DPD Change DESC) ───────────────────────────
        df_det_plot = (
            df_det[df_det["DPD_Change"] > 0]
            .sort_values("DPD_Change", ascending=False)
            .head(25)
            .copy()
        )

        if df_det_plot.empty:
            st.info("ไม่มีลูกค้าที่ DPD แย่ลงในช่วงที่เลือก")
        else:
            fig3a = go.Figure()
            fig3a.add_trace(go.Bar(
                x           = to_native(df_det_plot["DPD_Change"].round(1)),
                y           = df_det_plot["CustomerName"].tolist(),
                orientation = "h",
                marker_color = [
                    DETER_COLOR.get(t, "#95a5a6")
                    for t in df_det_plot["DeterTier"].tolist()
                ],
                text = [
                    f"Δ+{int(v)}d  ({int(p)}→{int(c)} days)"
                    for v, p, c in zip(
                        df_det_plot["DPD_Change"],
                        df_det_plot["PrevMaxDPD"],
                        df_det_plot["CurrMaxDPD"],
                    )
                ],
                textposition = "outside",
                customdata   = list(zip(
                    to_native(df_det_plot["PrevMaxDPD"].round(0)),
                    to_native(df_det_plot["CurrMaxDPD"].round(0)),
                    to_native(df_det_plot["CurrOverdueMB"].round(2)),
                    to_native(df_det_plot["CurrentDebtMB"].fillna(0).round(2)),
                    df_det_plot["DeterTier"].tolist(),
                )),
                hovertemplate = (
                    "<b>%{y}</b><br>"
                    "DPD Change: <b>Δ+%{x:.0f} days</b><br>"
                    f"Prev Max DPD ({prev_p3}): %{{customdata[0]:.0f}} days<br>"
                    f"Curr Max DPD ({curr_p3}): %{{customdata[1]:.0f}} days<br>"
                    "Curr Overdue: %{customdata[2]:.2f} MB<br>"
                    "Current Debt: %{customdata[3]:.2f} MB<br>"
                    "Tier: %{customdata[4]}<extra></extra>"
                ),
            ))
            fig3a.update_layout(
                title        = f"Top 25 Deteriorated Customers — {prev_p3} → {curr_p3}",
                xaxis        = dict(title="DPD Change (days)", zeroline=False),
                yaxis        = dict(autorange="reversed"),
                height       = max(380, len(df_det_plot) * 36 + 80),
                plot_bgcolor = "#f9f9f9",
            )
            st.plotly_chart(fig3a, use_container_width=True)

        # ── Scatter: DPD Change vs Overdue Amount ─────────────────────────────
        df_det_sc = df_det[
            (df_det["DPD_Change"] != 0) | (df_det["CurrOverdueMB"] > 0)
        ].copy()

        if not df_det_sc.empty:
            bs3 = bubble_norm(df_det_sc["CurrentDebtMB"].fillna(0.01))
            all_i3 = df_det_sc.index.tolist()

            fig3b = go.Figure()
            for tier in DETER_ORDER:
                grp = df_det_sc[df_det_sc["DeterTier"] == tier]
                if grp.empty:
                    continue
                idx = grp.index.tolist()
                fig3b.add_trace(go.Scatter(
                    x    = to_native(grp["DPD_Change"]),
                    y    = to_native(grp["CurrOverdueMB"]),
                    mode = "markers",
                    name = tier,
                    marker = dict(
                        size     = [bs3[all_i3.index(i)] for i in idx],
                        color    = DETER_COLOR.get(tier, "#95a5a6"),
                        opacity  = 0.80,
                        line     = dict(width=1, color="white"),
                        sizemode = "diameter",
                    ),
                    text = to_native(grp["CustomerName"]),
                    customdata = list(zip(
                        to_native(grp["PrevMaxDPD"].round(0)),
                        to_native(grp["CurrMaxDPD"].round(0)),
                        to_native(grp["CurrentDebtMB"].fillna(0).round(2)),
                        grp["DeterTier"].tolist(),
                    )),
                    hovertemplate = (
                        "<b>%{text}</b><br>"
                        "DPD Change: <b>Δ%{x:+.0f} days</b><br>"
                        "Curr Overdue: <b>%{y:.2f} MB</b><br>"
                        f"Prev Max DPD: %{{customdata[0]:.0f}}d → "
                        f"Curr: %{{customdata[1]:.0f}}d<br>"
                        "Current Debt: %{customdata[2]:.2f} MB<br>"
                        "Tier: %{customdata[3]}<extra></extra>"
                    ),
                ))

            # Highlight zone: มุมขวาบน = DPD โตมาก + Overdue เยอะ
            dpd_chg_med = float(df_det_sc[df_det_sc["DPD_Change"] > 0]["DPD_Change"].median()) if (df_det_sc["DPD_Change"] > 0).any() else 30.0
            ov_med3     = float(df_det_sc["CurrOverdueMB"].median())
            x_max3      = float(df_det_sc["DPD_Change"].max()) * 1.05
            y_max3      = float(df_det_sc["CurrOverdueMB"].max()) * 1.05

            fig3b.add_vrect(
                x0=dpd_chg_med, x1=x_max3,
                fillcolor="#e74c3c", opacity=0.05, line_width=0,
            )
            fig3b.add_hrect(
                y0=ov_med3, y1=y_max3,
                fillcolor="#e74c3c", opacity=0.05, line_width=0,
            )
            fig3b.add_annotation(
                x=x_max3*0.80, y=y_max3*0.90,
                text="🚨 Default Risk Zone<br>(DPD โต + Overdue เยอะ)",
                showarrow=False,
                font=dict(color="#c0392b", size=11),
                bgcolor="rgba(255,255,255,0.75)",
            )
            fig3b.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.4)

            fig3b.update_layout(
                title        = "DPD Change vs Current Overdue (Bubble = Current Debt)",
                xaxis        = dict(title="DPD Change (days)", zeroline=False),
                yaxis        = dict(title="Current Overdue Amount (MB)", zeroline=False),
                height       = 560,
                legend       = dict(title="Deterioration"),
                plot_bgcolor = "#f9f9f9",
            )
            st.plotly_chart(fig3b, use_container_width=True)

        # ── Full Ranked Table ─────────────────────────────────────────────────
        st.markdown("**📋 Full Deterioration Ranking**")
        tbl3 = (
            df_det[df_det["DPD_Change"] > 0]
            .sort_values("DPD_Change", ascending=False)
            [[
                "CustomerName","DeterTier","DPD_Change",
                "PrevMaxDPD","CurrMaxDPD",
                "PrevOverdueMB","CurrOverdueMB","CurrentDebtMB","TYPE",
            ]]
            .copy()
        )
        for c in ["DPD_Change","PrevMaxDPD","CurrMaxDPD",
                  "PrevOverdueMB","CurrOverdueMB","CurrentDebtMB"]:
            if c in tbl3.columns:
                tbl3[c] = tbl3[c].round(2)
        st.dataframe(tbl3, hide_index=True)


# =============================================================================
# Step 8 : EDA Trend Analysis — Overdue per Customer over Time
# =============================================================================
lsec("STEP 8 — EDA Trend Analysis")
st.header("8. EDA Trend Analysis — Overdue Trend per Customer")
st.caption(
    "Business Q: บริษัทไหนมี Overdue เพิ่มขึ้นต่อเนื่อง? "
    "เช่น Jan 100M → Feb 200M → Mar 300M (Trend ชัดเจน)"
)

if cust_risk.empty or ov.empty:
    st.warning("ไม่มีข้อมูล cust_risk หรือ ov — ข้าม Step 8")
else:
    # ── 8-0 : Controls ────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔧 Trend Analysis Controls")

    t_col1, t_col2, t_col3, t_col4, t_col5 = st.columns([2, 2, 1.5, 1.5, 1.5])

    # Date range (independent จาก Global Filter ด้านบน)
    min_t = ov["OriginalDueDate_parsed"].dropna().min()
    max_t = ov["OriginalDueDate_parsed"].dropna().max()
    min_t_date = min_t.date() if not pd.isna(min_t) else date(2020, 1, 1)
    max_t_date = max_t.date() if not pd.isna(max_t) else date.today()

    with t_col1:
        trend_start = st.date_input(
            "📅 Trend Start",
            value=min_t_date,
            min_value=min_t_date,
            max_value=max_t_date,
            key="t_start",
        )
    with t_col2:
        trend_end = st.date_input(
            "📅 Trend End",
            value=max_t_date,
            min_value=min_t_date,
            max_value=max_t_date,
            key="t_end",
        )
    with t_col3:
        trend_gran = st.selectbox(
            "📊 Granularity",
            options=["Monthly", "Quarterly", "Weekly", "Yearly"],
            index=0,
            key="t_gran",
        )
    with t_col4:
        top_n = st.number_input(
            "🏆 Top N Customers",
            min_value=1, max_value=50, value=10, step=1,
            key="t_topn",
        )
    with t_col5:
        trend_mode = st.selectbox(
            "📈 Chart Mode",
            options=["Cumulative", "Per-Period"],
            index=0,
            key="t_mode",
            help=(
                "Cumulative = ยอด Overdue สะสมต่อ Period\n"
                "Per-Period = ยอด Overdue เฉพาะ Period นั้น"
            ),
        )

    # Customer search / filter
    st.markdown("##### 🔍 Customer Filter (optional)")
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        cust_search = st.text_input(
            "ค้นหาชื่อบริษัท (ใส่หลายชื่อคั่นด้วย ,)",
            placeholder="เช่น COMPANY A, COMPANY B",
            key="t_search",
        )
    with search_col2:
        show_avg_line = st.checkbox("แสดง Portfolio Average", value=True, key="t_avg")

    if trend_start > trend_end:
        st.error("Trend Start ต้องไม่เกิน Trend End")
        st.stop()

    GRAN_MAP = {
        "Monthly":   "M",
        "Quarterly": "Q",
        "Weekly":    "W",
        "Yearly":    "Y",
    }
    trend_period_alias = GRAN_MAP[trend_gran]

    # ── 8-1 : Build invoice-level dataset ────────────────────────────────────
    lsec("STEP 8-1 — Build Trend Dataset")

    ov_trend = ov[
        ov["OriginalDueDate_parsed"].notna() &
        (ov["OriginalDueDate_parsed"].dt.date >= trend_start) &
        (ov["OriginalDueDate_parsed"].dt.date <= trend_end) &
        (ov["OverdueAmount_num"] > 0)
    ].copy()

    if ov_trend.empty:
        st.warning("ไม่มี overdue invoice ในช่วงที่เลือก")
        st.stop()

    # Period label (string, sortable)
    ov_trend["TrendPeriod"] = (
        ov_trend["OriginalDueDate_parsed"]
        .dt.to_period(trend_period_alias)
        .astype(str)
    )
    ov_trend["OverdueMB"] = ov_trend["OverdueAmount_num"] / 1_000_000

    # Customer name lookup
    name_map = (
        ov_trend.groupby(join_key)
        .apply(lambda g: g[name_col].mode().iloc[0] if name_col in g.columns and not g[name_col].mode().empty else str(g[join_key].iloc[0]))
        .to_dict()
    )

    # ── 8-2 : Aggregate per (Customer, TrendPeriod) ───────────────────────────
    grp_trend = (
        ov_trend.groupby([join_key, "TrendPeriod"])
        .agg(
            OverdueMB    = ("OverdueMB",          "sum"),
            InvoiceCount = ("OverdueMB",          "count"),
            AvgDPD       = ("DPD",                "mean"),
        )
        .reset_index()
        .rename(columns={join_key: "Customer"})
    )
    grp_trend["CustomerName"] = grp_trend["Customer"].map(name_map).fillna(
        grp_trend["Customer"].astype(str)
    )

    # ── 8-3 : Select Top-N customers (by total overdue in range) ─────────────
    cust_totals = (
        grp_trend.groupby("Customer")["OverdueMB"].sum()
        .sort_values(ascending=False)
    )

    # Manual search overrides Top-N
    if cust_search.strip():
        search_terms = [s.strip().lower() for s in cust_search.split(",") if s.strip()]
        all_names_df = grp_trend[["Customer","CustomerName"]].drop_duplicates()
        matched_custs = all_names_df[
            all_names_df["CustomerName"].str.lower().apply(
                lambda n: any(t in n for t in search_terms)
            )
        ]["Customer"].tolist()
        if not matched_custs:
            st.warning(f"ไม่พบชื่อที่ค้นหา: {cust_search}")
            sel_custs = cust_totals.head(int(top_n)).index.tolist()
        else:
            sel_custs = matched_custs
            st.success(
                f"พบ {len(sel_custs)} บริษัทที่ตรงกับ: {cust_search}"
            )
    else:
        sel_custs = cust_totals.head(int(top_n)).index.tolist()

    df_sel = grp_trend[grp_trend["Customer"].isin(sel_custs)].copy()

    if df_sel.empty:
        st.warning("ไม่มีข้อมูลสำหรับ customer ที่เลือก")
        st.stop()

    # ── 8-4 : Pivot → full period grid (fill missing → 0) ───────────────────
    all_periods_trend = sorted(grp_trend["TrendPeriod"].unique().tolist())
    pivot = (
        df_sel.pivot_table(
            index="Customer",
            columns="TrendPeriod",
            values="OverdueMB",
            aggfunc="sum",
        )
        .reindex(columns=all_periods_trend, fill_value=0)
        .fillna(0)
    )

    # Cumulative mode
    if trend_mode == "Cumulative":
        pivot_plot = pivot.cumsum(axis=1)
        y_label = "Cumulative Overdue (MB)"
    else:
        pivot_plot = pivot.copy()
        y_label = "Overdue Amount (MB)"

    log.info(f"Trend pivot shape: {pivot_plot.shape}")
    log.info(f"Periods: {all_periods_trend}")
    log.info(f"Selected customers: {sel_custs}")

    # ── 8-5 : Line Chart (plotly) ────────────────────────────────────────────
    st.markdown("---")
    st.subheader(f"📈 Overdue Trend — {trend_mode} ({trend_gran})")
    st.caption(
        f"Top {len(sel_custs)} customers | "
        f"{trend_start} → {trend_end} | "
        f"Mode: {trend_mode}"
    )

    COLOR_PALETTE = (
        px.colors.qualitative.Plotly
        + px.colors.qualitative.D3
        + px.colors.qualitative.Set1
    )

    fig8 = go.Figure()

    for i, cust_id in enumerate(sel_custs):
        if cust_id not in pivot_plot.index:
            continue
        y_vals = pivot_plot.loc[cust_id].tolist()
        cust_name = name_map.get(cust_id, str(cust_id))
        color = COLOR_PALETTE[i % len(COLOR_PALETTE)]

        # Hover: raw OverdueMB per period (ไม่ว่าจะ Cumulative หรือ Per-Period)
        raw_y = pivot.loc[cust_id].tolist() if cust_id in pivot.index else y_vals

        fig8.add_trace(go.Scatter(
            x          = all_periods_trend,
            y          = y_vals,
            mode       = "lines+markers",
            name       = cust_name,
            line       = dict(width=2.5, color=color),
            marker     = dict(size=8, color=color,
                              line=dict(width=1.5, color="white")),
            customdata = list(zip(
                raw_y,
                [cust_name] * len(y_vals),
            )),
            hovertemplate = (
                f"<b>{cust_name}</b><br>"
                "Period: <b>%{x}</b><br>"
                + (f"Cumulative Overdue: <b>%{{y:.3f}} MB</b><br>"
                   f"Period Overdue: %{{customdata[0]:.3f}} MB"
                   if trend_mode == "Cumulative"
                   else "Overdue: <b>%{y:.3f} MB</b>")
                + "<extra></extra>"
            ),
        ))

    # Portfolio Average Line
    if show_avg_line and len(sel_custs) > 1:
        port_avg = pivot_plot.mean(axis=0).tolist()
        fig8.add_trace(go.Scatter(
            x          = all_periods_trend,
            y          = port_avg,
            mode       = "lines",
            name       = "── Portfolio Avg",
            line       = dict(width=2, dash="dot", color="rgba(0,0,0,0.45)"),
            marker     = dict(size=0),
            hovertemplate = (
                "Portfolio Avg<br>"
                "Period: <b>%{x}</b><br>"
                f"{y_label}: <b>%{{y:.3f}} MB</b>"
                "<extra></extra>"
            ),
        ))

    fig8.update_layout(
        title        = f"Overdue {trend_mode} Trend by Customer ({trend_gran})",
        xaxis        = dict(
            title       = f"Period ({trend_gran})",
            tickangle   = -35,
            showgrid    = True,
            gridcolor   = "#eeeeee",
            zeroline    = False,
        ),
        yaxis        = dict(
            title     = y_label,
            showgrid  = True,
            gridcolor = "#eeeeee",
            zeroline  = False,
        ),
        height       = 580,
        legend       = dict(
            title        = "Customer",
            orientation  = "v",
            x            = 1.01,
            y            = 1,
            bgcolor      = "rgba(255,255,255,0.85)",
            bordercolor  = "#cccccc",
            borderwidth  = 1,
        ),
        hovermode    = "x unified",
        plot_bgcolor = "#f9f9f9",
        paper_bgcolor= "white",
    )
    st.plotly_chart(fig8, use_container_width=True)

    # ── 8-6 : Trend Classification ───────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Trend Classification per Customer")
    st.caption(
        "คำนวณจาก Linear Regression slope ของ Per-Period Overdue MB "
        "→ จำแนกเป็น Escalating / Stable / Improving"
    )

    from numpy.polynomial import polynomial as P

    trend_rows = []
    for cust_id in sel_custs:
        if cust_id not in pivot.index:
            continue
        y_raw  = np.array(pivot.loc[cust_id].tolist(), dtype=float)
        x_idx  = np.arange(len(y_raw), dtype=float)
        cname  = name_map.get(cust_id, str(cust_id))

        # slope via polyfit degree-1
        if len(y_raw) >= 2 and y_raw.sum() > 0:
            coeffs = np.polyfit(x_idx, y_raw, 1)
            slope  = float(coeffs[0])          # MB per period
        else:
            slope = 0.0

        total_ov   = float(y_raw.sum())
        max_ov     = float(y_raw.max())
        min_ov     = float(y_raw.min())
        last_ov    = float(y_raw[-1])
        first_ov   = float(y_raw[0])
        delta_ov   = last_ov - first_ov        # last - first

        # Periods non-zero
        active_periods = int((y_raw > 0).sum())
        total_periods  = len(y_raw)

        # Classification
        if slope > 1.0:
            classification = "📈 Escalating"
        elif slope < -1.0:
            classification = "📉 Improving"
        elif abs(slope) <= 1.0 and active_periods / max(total_periods, 1) >= 0.5:
            classification = "➡️ Persistent"
        else:
            classification = "⬜ Intermittent"

        trend_rows.append({
            "Customer":       cust_id,
            "CustomerName":   cname,
            "Classification": classification,
            "Slope (MB/pd)":  round(slope, 3),
            "Total Overdue":  round(total_ov, 3),
            "First Period":   round(first_ov, 3),
            "Last Period":    round(last_ov, 3),
            "Δ (Last-First)": round(delta_ov, 3),
            "Max Single Pd":  round(max_ov, 3),
            "Active Periods": active_periods,
            "Total Periods":  total_periods,
        })

    df_trend_class = pd.DataFrame(trend_rows).sort_values(
        ["Classification", "Total Overdue"], ascending=[True, False]
    )

    # KPI summary
    tc1, tc2, tc3, tc4 = st.columns(4)
    esc = df_trend_class[df_trend_class["Classification"] == "📈 Escalating"]
    imp = df_trend_class[df_trend_class["Classification"] == "📉 Improving"]
    per = df_trend_class[df_trend_class["Classification"] == "➡️ Persistent"]
    imt = df_trend_class[df_trend_class["Classification"] == "⬜ Intermittent"]

    tc1.metric("📈 Escalating",   f"{len(esc)} companies",
               f"{esc['Total Overdue'].sum():.2f} MB", delta_color="inverse")
    tc2.metric("➡️ Persistent",   f"{len(per)} companies",
               f"{per['Total Overdue'].sum():.2f} MB", delta_color="inverse")
    tc3.metric("📉 Improving",    f"{len(imp)} companies",
               f"{imp['Total Overdue'].sum():.2f} MB", delta_color="normal")
    tc4.metric("⬜ Intermittent", f"{len(imt)} companies",
               f"{imt['Total Overdue'].sum():.2f} MB", delta_color="off")

    # Color rows
    CLASS_COLOR_MAP = {
        "📈 Escalating":   "#fde8e8",
        "➡️ Persistent":   "#fef3cd",
        "📉 Improving":    "#d4edda",
        "⬜ Intermittent": "#f0f0f0",
    }

    def style_class_row(row):
        color = CLASS_COLOR_MAP.get(row["Classification"], "#ffffff")
        return [f"background-color: {color}"] * len(row)

    styled_tbl = df_trend_class.style.apply(style_class_row, axis=1)
    st.dataframe(styled_tbl, hide_index=True, use_container_width=True)

    # ── 8-7 : Stacked Area Chart (Portfolio View) ────────────────────────────
    st.markdown("---")
    st.subheader("📉 Portfolio Stacked Area — Overdue over Time")
    st.caption("มองภาพรวม Portfolio ว่า Overdue กระจุกตัวอยู่ที่ Period ไหน")

    fig8_area = go.Figure()
    for i, cust_id in enumerate(sel_custs):
        if cust_id not in pivot.index:
            continue
        y_area  = pivot.loc[cust_id].tolist()    # Always Per-Period for stacked area
        cname   = name_map.get(cust_id, str(cust_id))
        color   = COLOR_PALETTE[i % len(COLOR_PALETTE)]

        fig8_area.add_trace(go.Scatter(
            x          = all_periods_trend,
            y          = y_area,
            mode       = "lines",
            name       = cname,
            stackgroup = "one",
            line       = dict(width=0.8, color=color),
            fillcolor  = color,
            opacity    = 0.75,
            hovertemplate = (
                f"<b>{cname}</b><br>"
                "Period: <b>%{x}</b><br>"
                "Overdue: <b>%{y:.3f} MB</b>"
                "<extra></extra>"
            ),
        ))

    fig8_area.update_layout(
        title        = "Stacked Area — Portfolio Overdue Trend (Per-Period)",
        xaxis        = dict(
            title     = f"Period ({trend_gran})",
            tickangle = -35,
            showgrid  = True,
            gridcolor = "#eeeeee",
        ),
        yaxis        = dict(
            title     = "Overdue Amount (MB)",
            showgrid  = True,
            gridcolor = "#eeeeee",
        ),
        height       = 480,
        legend       = dict(
            title       = "Customer",
            orientation = "v",
            x           = 1.01,
            bgcolor     = "rgba(255,255,255,0.85)",
        ),
        hovermode    = "x unified",
        plot_bgcolor = "#f9f9f9",
        paper_bgcolor= "white",
    )
    st.plotly_chart(fig8_area, use_container_width=True)

    # ── 8-8 : Pivot Table (Raw Data Preview) ─────────────────────────────────
    with st.expander("📋 Raw Trend Pivot Table (Per-Period Overdue MB)"):
        pivot_display = pivot.copy()
        pivot_display.index = pivot_display.index.map(
            lambda c: name_map.get(c, str(c))
        )
        pivot_display.index.name = "CustomerName"
        pivot_display = pivot_display.round(3)
        st.dataframe(pivot_display, use_container_width=True)

    log.info(f"Step 8 complete — {len(sel_custs)} customers, "
             f"{len(all_periods_trend)} periods")


# =============================================================================
# Step 9 : Overdue Amount vs Current Debt — Utilization Risk
# 9.1 Apache ECharts  (via streamlit-echarts)
# 9.2 Plotly          (native)
# =============================================================================
lsec("STEP 9 — Utilization Risk: Overdue vs Current Debt")
st.header("9. Utilization Risk — Overdue Amount vs Current Debt")
st.caption(
    "Business Q: Overdue เท่ากัน ≠ Risk เท่ากัน "
    "| ลูกค้าที่ Overdue/Debt สูง = อันตรายกว่ามาก แม้ยอดจะน้อยกว่าในเชิงตัวเลข"
)

# ── Guard ──────────────────────────────────────────────────────────────────
if cust_risk.empty:
    st.warning("ไม่มีข้อมูล cust_risk — ข้าม Step 9")
else:
    # ── 9-0 : Prepare dataset ─────────────────────────────────────────────
    df9 = cust_risk[
        (cust_risk["TotalOverdueMB"] > 0) &
        (cust_risk["CurrentDebtMB"]  > 0)
    ].copy()

    # Utilization = Overdue / CurrentDebt * 100
    df9["UtilizationRisk"] = (
        df9["TotalOverdueMB"] / df9["CurrentDebtMB"] * 100
    ).clip(0, 300).round(2)

    # Risk quadrant classification (2×2)
    med_debt  = float(df9["CurrentDebtMB"].median())
    med_util  = float(df9["UtilizationRisk"].median())

    def risk_quadrant(row):
        high_debt = row["CurrentDebtMB"]  >= med_debt
        high_util = row["UtilizationRisk"] >= med_util
        if high_debt and high_util:     return "🔴 High Debt · High Risk"
        elif high_debt and not high_util: return "🟡 High Debt · Low Risk"
        elif not high_debt and high_util: return "🟠 Low Debt · High Risk"
        else:                             return "🟢 Low Debt · Low Risk"

    df9["RiskQuadrant"] = df9.apply(risk_quadrant, axis=1)

    QUAD_COLOR = {
        "🔴 High Debt · High Risk":  "#e74c3c",
        "🟡 High Debt · Low Risk":   "#f1c40f",
        "🟠 Low Debt · High Risk":   "#e67e22",
        "🟢 Low Debt · Low Risk":    "#2ecc71",
    }
    QUAD_ORDER = [
        "🔴 High Debt · High Risk",
        "🟠 Low Debt · High Risk",
        "🟡 High Debt · Low Risk",
        "🟢 Low Debt · Low Risk",
    ]

    if df9.empty:
        st.warning("ไม่มีลูกค้าที่มีทั้ง TotalOverdueMB > 0 และ CurrentDebtMB > 0")
    else:
        # ── Controls ──────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🔧 Step 9 Controls")
        s9c1, s9c2, s9c3 = st.columns([2, 2, 2])
        with s9c1:
            util_threshold = st.slider(
                "⚠️ Utilization Risk Threshold (%)",
                min_value=10, max_value=200, value=50, step=5,
                key="s9_util",
                help="เส้นแบ่ง High/Low UtilizationRisk — ค่า default 50%",
            )
        with s9c2:
            top_n9 = st.number_input(
                "🏆 แสดง Top N (by UtilizationRisk)",
                min_value=5, max_value=min(100, len(df9)),
                value=min(30, len(df9)), step=5,
                key="s9_topn",
            )
        with s9c3:
            sel_types9 = st.multiselect(
                "🏷️ Filter Product Type",
                options=sorted(df9["TYPE"].dropna().unique().tolist()),
                default=sorted(df9["TYPE"].dropna().unique().tolist()),
                key="s9_type",
            )

        # Apply filters
        df9_f = df9.copy()
        if sel_types9:
            df9_f = df9_f[df9_f["TYPE"].isin(sel_types9)]

        # Recompute quadrant with user threshold
        def risk_quadrant_custom(row):
            high_debt = row["CurrentDebtMB"]  >= med_debt
            high_util = row["UtilizationRisk"] >= util_threshold
            if high_debt and high_util:       return "🔴 High Debt · High Risk"
            elif high_debt and not high_util: return "🟡 High Debt · Low Risk"
            elif not high_debt and high_util: return "🟠 Low Debt · High Risk"
            else:                             return "🟢 Low Debt · Low Risk"

        df9_f["RiskQuadrant"] = df9_f.apply(risk_quadrant_custom, axis=1)
        df9_top = df9_f.sort_values("UtilizationRisk", ascending=False).head(int(top_n9)).copy()

        # ── KPI Banner ────────────────────────────────────────────────────
        kp1, kp2, kp3, kp4 = st.columns(4)
        hi_risk = df9_f[df9_f["UtilizationRisk"] >= util_threshold]
        lo_risk = df9_f[df9_f["UtilizationRisk"] <  util_threshold]
        kp1.metric(
            f"⚠️ Util ≥ {util_threshold}%",
            f"{len(hi_risk)} customers",
            f"{hi_risk['TotalOverdueMB'].sum():.2f} MB overdue",
            delta_color="inverse",
        )
        kp2.metric(
            f"✅ Util < {util_threshold}%",
            f"{len(lo_risk)} customers",
            f"{lo_risk['TotalOverdueMB'].sum():.2f} MB overdue",
            delta_color="normal",
        )
        kp3.metric(
            "📊 Avg Utilization Risk",
            f"{df9_f['UtilizationRisk'].mean():.1f}%",
            f"Median {df9_f['UtilizationRisk'].median():.1f}%",
        )
        kp4.metric(
            "💀 Max Utilization Risk",
            f"{df9_f['UtilizationRisk'].max():.1f}%",
            df9_f.loc[df9_f['UtilizationRisk'].idxmax(), 'CustomerName'],
            delta_color="inverse",
        )

        # ══════════════════════════════════════════════════════════════════
        # 9.1 — Apache ECharts
        # ══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("9.1 — Apache ECharts")
        st.caption(
            "ECharts Scatter — bubble size = TotalOverdueMB | "
            "x = CurrentDebtMB | y = UtilizationRisk% | สี = RiskQuadrant"
        )

        try:
            from streamlit_echarts import st_echarts
            ECHARTS_OK = True
        except ImportError:
            ECHARTS_OK = False
            st.warning(
                "ยังไม่ได้ติดตั้ง `streamlit-echarts` — "
                "รัน `pip install streamlit-echarts` แล้วรีสตาร์ท\n\n"
                "ข้ามไปดู 9.2 Plotly ด้านล่างได้เลย"
            )

        if ECHARTS_OK:
            # ── Build series per quadrant ──────────────────────────────
            ECHARTS_COLOR_MAP = {
                "🔴 High Debt · High Risk":  "#e74c3c",
                "🟡 High Debt · Low Risk":   "#f1c40f",
                "🟠 Low Debt · High Risk":   "#e67e22",
                "🟢 Low Debt · Low Risk":    "#2ecc71",
            }

            # Bubble size: normalise TotalOverdueMB → [8, 60]
            max_ov9 = float(df9_top["TotalOverdueMB"].max()) or 1.0
            def bubble9(v):
                return round(max(8.0, (v / max_ov9) * 60.0), 1)

            series_list = []
            for quad in QUAD_ORDER:
                grp = df9_top[df9_top["RiskQuadrant"] == quad]
                if grp.empty:
                    continue
                data_pts = []
                for _, row in grp.iterrows():
                    data_pts.append({
                        "value": [
                            round(float(row["CurrentDebtMB"]),   3),
                            round(float(row["UtilizationRisk"]), 2),
                            round(float(row["TotalOverdueMB"]),  3),
                        ],
                        "name":        str(row["CustomerName"]),
                        "symbolSize":  bubble9(float(row["TotalOverdueMB"])),
                        "itemStyle":   {"color": ECHARTS_COLOR_MAP.get(quad, "#95a5a6")},
                        "label": {
                            "show":     True,
                            "formatter": str(row["CustomerName"]),
                            "fontSize":  9,
                            "color":    "#333",
                            "position": "top",
                        },
                    })
                series_list.append({
                    "name":            quad,
                    "type":            "scatter",
                    "data":            data_pts,
                    "emphasis": {
                        "focus": "series",
                        "label": {"show": True, "fontSize": 11, "fontWeight": "bold"},
                    },
                })

            # ── Marklines for quadrant dividers ──────────────────────
            # Add to first series
            if series_list:
                series_list[0]["markLine"] = {
                    "silent":    True,
                    "lineStyle": {"type": "dashed", "color": "#aaaaaa", "width": 1.5},
                    "data": [
                        {"xAxis": round(med_debt,  2), "name": f"Debt Median {med_debt:.1f}MB"},
                        {"yAxis": float(util_threshold),  "name": f"Risk Threshold {util_threshold}%"},
                    ],
                    "label": {"show": True, "fontSize": 10, "color": "#888"},
                }

            echarts_option = {
                "backgroundColor": "#fafafa",
                "title": {
                    "text":     "Utilization Risk Map",
                    "subtext":  f"Bubble = Overdue Amount | Threshold = {util_threshold}%",
                    "left":     "center",
                    "textStyle": {"fontSize": 16, "fontWeight": "bold"},
                    "subtextStyle": {"fontSize": 11, "color": "#666"},
                },
                "tooltip": {
                    "trigger":   "item",
                    "formatter": """function(p) {
                        var d = p.data;
                        return '<b>' + d.name + '</b><br/>'
                            + 'Current Debt: <b>' + d.value[0].toFixed(2) + ' MB</b><br/>'
                            + 'Utilization Risk: <b>' + d.value[1].toFixed(1) + '%</b><br/>'
                            + 'Total Overdue: <b>' + d.value[2].toFixed(2) + ' MB</b>';
                    }""",
                },
                "legend": {
                    "data":        QUAD_ORDER,
                    "bottom":      0,
                    "orient":      "horizontal",
                    "textStyle":   {"fontSize": 11},
                },
                "grid": {"left": "8%", "right": "5%", "top": "15%", "bottom": "12%"},
                "xAxis": {
                    "name":          "Current Debt (MB)",
                    "nameLocation":  "middle",
                    "nameGap":       30,
                    "nameTextStyle": {"fontSize": 12},
                    "splitLine":     {"lineStyle": {"type": "dashed", "color": "#e0e0e0"}},
                },
                "yAxis": {
                    "name":          "Utilization Risk (%)",
                    "nameLocation":  "middle",
                    "nameGap":       45,
                    "nameTextStyle": {"fontSize": 12},
                    "splitLine":     {"lineStyle": {"type": "dashed", "color": "#e0e0e0"}},
                },
                "series": series_list,
            }

            st_echarts(
                options=echarts_option,
                height="550px",
                key="echarts_util_risk",
            )

            # ── ECharts Bar: Top N by UtilizationRisk ─────────────────
            st.caption("📊 ECharts Bar — Top N by Utilization Risk%")
            bar_df = df9_top.sort_values("UtilizationRisk", ascending=False).head(20)
            bar_colors = [
                ECHARTS_COLOR_MAP.get(q, "#95a5a6")
                for q in bar_df["RiskQuadrant"].tolist()
            ]
            echarts_bar = {
                "backgroundColor": "#fafafa",
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                    "formatter": """function(p) {
                        var item = p[0];
                        return '<b>' + item.name + '</b><br/>'
                            + 'Utilization Risk: <b>' + item.value.toFixed(1) + '%</b>';
                    }""",
                },
                "grid": {"left": "3%", "right": "12%", "containLabel": True},
                "xAxis": {
                    "type": "value",
                    "name": "Utilization Risk (%)",
                    "nameLocation": "middle",
                    "nameGap": 28,
                    "splitLine": {"lineStyle": {"type": "dashed", "color": "#e0e0e0"}},
                },
                "yAxis": {
                    "type":        "category",
                    "data":        bar_df["CustomerName"].tolist(),
                    "inverse":     True,
                    "axisLabel":   {"fontSize": 11},
                },
                "series": [{
                    "type":  "bar",
                    "data":  [
                        {
                            "value":     round(float(v), 2),
                            "itemStyle": {"color": c},
                            "label": {
                                "show":      True,
                                "position":  "right",
                                "formatter": f"{{c}}%",
                                "fontSize":  10,
                            },
                        }
                        for v, c in zip(bar_df["UtilizationRisk"].tolist(), bar_colors)
                    ],
                    "barMaxWidth": 32,
                }],
            }
            st_echarts(
                options=echarts_bar,
                height=f"{max(300, len(bar_df) * 32 + 80)}px",
                key="echarts_util_bar",
            )

        # ══════════════════════════════════════════════════════════════════
        # 9.2 — Plotly
        # ══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("9.2 — Plotly")
        st.caption(
            "Plotly Scatter — bubble size = TotalOverdueMB | "
            "x = CurrentDebtMB | y = UtilizationRisk% | สี = RiskQuadrant"
        )

        # ── Scatter Bubble ────────────────────────────────────────────────
        bs9 = bubble_norm(df9_top["TotalOverdueMB"].clip(lower=0.01), lo=8, hi=55)
        all_i9 = df9_top.index.tolist()

        fig9a = go.Figure()
        for quad in QUAD_ORDER:
            grp = df9_top[df9_top["RiskQuadrant"] == quad]
            if grp.empty:
                continue
            idx = grp.index.tolist()
            fig9a.add_trace(go.Scatter(
                x    = to_native(grp["CurrentDebtMB"]),
                y    = to_native(grp["UtilizationRisk"]),
                mode = "markers+text",
                name = quad,
                text = grp["CustomerName"].tolist(),
                textposition = "top center",
                textfont     = dict(size=8, color="#333"),
                marker = dict(
                    size     = [bs9[all_i9.index(i)] for i in idx],
                    color    = QUAD_COLOR.get(quad, "#95a5a6"),
                    opacity  = 0.82,
                    line     = dict(width=1.2, color="white"),
                    sizemode = "diameter",
                ),
                customdata = list(zip(
                    to_native(grp["TotalOverdueMB"].round(3)),
                    to_native(grp["AvgDPD"].fillna(0).round(1)),
                    to_native(grp["MaxDPD"].fillna(0).round(0)),
                    grp["TYPE"].tolist(),
                    grp["RiskQuadrant"].tolist(),
                )),
                hovertemplate = (
                    "<b>%{text}</b><br>"
                    "Current Debt:      <b>%{x:.2f} MB</b><br>"
                    "Utilization Risk:  <b>%{y:.1f}%</b><br>"
                    "Total Overdue:     %{customdata[0]:.3f} MB<br>"
                    "Avg DPD:           %{customdata[1]:.0f} days<br>"
                    "Max DPD:           %{customdata[2]:.0f} days<br>"
                    "Type:              %{customdata[3]}<br>"
                    "Quadrant:          %{customdata[4]}"
                    "<extra></extra>"
                ),
            ))

        # Quadrant divider lines
        x_max9 = float(df9_top["CurrentDebtMB"].max()) * 1.1
        y_max9 = min(float(df9_top["UtilizationRisk"].max()) * 1.1, 310.0)

        fig9a.add_vline(
            x=med_debt, line_dash="dash", line_color="#aaaaaa", opacity=0.7,
            annotation_text=f"Debt Median<br>{med_debt:.1f} MB",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#777"),
        )
        fig9a.add_hline(
            y=util_threshold, line_dash="dash", line_color="#e74c3c", opacity=0.6,
            annotation_text=f"Risk Threshold {util_threshold}%",
            annotation_position="right",
            annotation_font=dict(size=10, color="#e74c3c"),
        )

        # Quadrant annotation labels
        for ann_txt, ax, ay, fc in [
            ("🔴 High Debt\nHigh Risk",   x_max9*0.78, y_max9*0.88, "#fde8e8"),
            ("🟡 High Debt\nLow Risk",    x_max9*0.78, y_max9*0.10, "#fef9e7"),
            ("🟠 Low Debt\nHigh Risk",    x_max9*0.05, y_max9*0.88, "#fef3e2"),
            ("🟢 Low Debt\nLow Risk",     x_max9*0.05, y_max9*0.10, "#e8f8f0"),
        ]:
            fig9a.add_annotation(
                x=ax, y=ay, text=ann_txt,
                showarrow=False,
                font=dict(size=10, color="#555"),
                bgcolor=fc,
                bordercolor="#ccc",
                borderwidth=1,
                borderpad=4,
                opacity=0.85,
            )

        fig9a.update_layout(
            title=dict(
                text=(
                    "Utilization Risk Map — Overdue vs Current Debt<br>"
                    f"<sup>Bubble size = Overdue Amount | "
                    f"Threshold = {util_threshold}% | "
                    f"Debt Median = {med_debt:.1f} MB</sup>"
                ),
                x=0.5,
            ),
            xaxis=dict(
                title="Current Debt (MB)",
                zeroline=False,
                range=[-0.5, x_max9],
                showgrid=True, gridcolor="#eeeeee",
            ),
            yaxis=dict(
                title="Utilization Risk — Overdue / Current Debt (%)",
                zeroline=False,
                range=[-5, y_max9],
                showgrid=True, gridcolor="#eeeeee",
            ),
            height=580,
            legend=dict(title="Risk Quadrant", orientation="v", x=1.01, y=1),
            plot_bgcolor="#f9f9f9",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig9a, use_container_width=True)

        # ── Plotly Horizontal Bar — Top N by UtilizationRisk ─────────────
        st.caption("📊 Plotly Bar — Top N by Utilization Risk%")
        bar9 = df9_top.sort_values("UtilizationRisk", ascending=False).head(20).copy()
        fig9b = go.Figure()
        fig9b.add_trace(go.Bar(
            x           = to_native(bar9["UtilizationRisk"].round(2)),
            y           = bar9["CustomerName"].tolist(),
            orientation = "h",
            marker_color = [
                QUAD_COLOR.get(q, "#95a5a6")
                for q in bar9["RiskQuadrant"].tolist()
            ],
            text = [
                f"{v:.1f}%  ({ov:.2f}MB / {db:.2f}MB)"
                for v, ov, db in zip(
                    bar9["UtilizationRisk"],
                    bar9["TotalOverdueMB"],
                    bar9["CurrentDebtMB"],
                )
            ],
            textposition = "outside",
            customdata   = list(zip(
                to_native(bar9["TotalOverdueMB"].round(3)),
                to_native(bar9["CurrentDebtMB"].round(2)),
                to_native(bar9["AvgDPD"].fillna(0).round(1)),
                bar9["RiskQuadrant"].tolist(),
                bar9["TYPE"].tolist(),
            )),
            hovertemplate = (
                "<b>%{y}</b><br>"
                "Utilization Risk: <b>%{x:.1f}%</b><br>"
                "Total Overdue:    %{customdata[0]:.3f} MB<br>"
                "Current Debt:     %{customdata[1]:.2f} MB<br>"
                "Avg DPD:          %{customdata[2]:.0f} days<br>"
                "Quadrant:         %{customdata[3]}<br>"
                "Type:             %{customdata[4]}"
                "<extra></extra>"
            ),
        ))
        # Threshold reference line
        fig9b.add_vline(
            x=float(util_threshold),
            line_dash="dash", line_color="#e74c3c", opacity=0.6,
            annotation_text=f"Threshold {util_threshold}%",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#e74c3c"),
        )
        fig9b.update_layout(
            title=f"Top {len(bar9)} Customers — Utilization Risk Ranking",
            xaxis=dict(
                title="Utilization Risk (%)",
                zeroline=False,
                showgrid=True, gridcolor="#eeeeee",
            ),
            yaxis=dict(autorange="reversed"),
            height=max(350, len(bar9) * 34 + 90),
            plot_bgcolor="#f9f9f9",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig9b, use_container_width=True)

        # ── 9.3 Comparison Note ───────────────────────────────────────────
        st.markdown("---")
        st.subheader("📝 ECharts vs Plotly — ข้อสังเกต")
        st.markdown("""
| Feature | Apache ECharts (9.1) | Plotly (9.2) |
|---|---|---|
| **Label บน Bubble** | ✅ built-in `label` per point | ⚠️ ต้องใช้ `mode="markers+text"` อาจทับกัน |
| **Tooltip** | ✅ Custom formatter (JS string) | ✅ `hovertemplate` (Pythonic) |
| **Quadrant Divider** | ✅ `markLine` inline ใน series | ✅ `add_vline` / `add_hline` แยกต่างหาก |
| **Bubble Size** | ✅ `symbolSize` per point | ✅ `marker.size` list |
| **Interactivity** | ✅ Legend toggle, zoom, brush | ✅ Legend toggle, zoom, hover |
| **Annotation Box** | ❌ ต้องใช้ `markArea` หรือ graphic | ✅ `add_annotation` ง่ายกว่า |
| **Integration** | ⚠️ ต้องติดตั้ง `streamlit-echarts` | ✅ built-in ใน Streamlit |
| **Code Style** | JSON/dict (option object) | Python OOP (go.Figure) |
| **Performance** | ✅ เร็วกว่าบน dataset ใหญ่ | ✅ เพียงพอสำหรับ <5,000 pts |
        """)

        # ── Full Table ────────────────────────────────────────────────────
        with st.expander("📋 Full Utilization Risk Table"):
            tbl9 = (
                df9_f
                .sort_values("UtilizationRisk", ascending=False)
                [[
                    "CustomerName", "RiskQuadrant", "UtilizationRisk",
                    "TotalOverdueMB", "CurrentDebtMB", "CleanCreditMB",
                    "AvgDPD", "MaxDPD", "OverdueInvoices", "TYPE",
                ]]
                .copy()
            )
            for c in ["UtilizationRisk","TotalOverdueMB","CurrentDebtMB",
                      "CleanCreditMB","AvgDPD","MaxDPD"]:
                if c in tbl9.columns:
                    tbl9[c] = tbl9[c].round(2)
            st.dataframe(tbl9, hide_index=True, use_container_width=True)

        log.info(
            f"Step 9 complete — {len(df9_f)} customers, "
            f"hi-risk {len(hi_risk)}, lo-risk {len(lo_risk)}"
        )
                # ══════════════════════════════════════════════════════════════════
        # 9.4 — Apache ECharts : Hexbin / Density Scatter
        # Concept เดิม: x = CurrentDebtMB, y = UtilizationRisk%
        # แต่เปลี่ยนจาก bubble → hex density grid
        # ══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.subheader("9.4 — ECharts Hexbin / Density Scatter")
        st.caption(
            "มองภาพ Density ของลูกค้า — ช่อง Hex ไหนมีลูกค้ากระจุกตัวมาก = "
            "สีเข้ม | x = Current Debt | y = Utilization Risk%"
        )

        if ECHARTS_OK:
            import math

            # ── 9.4-0 : Hexbin computation (pure Python) ─────────────────
            # Algorithm:
            #   1. Normalise x, y → grid space
            #   2. Assign each point to nearest hex centre
            #   3. Count points per hex → density
            #   4. Encode hex centre back to data space

            HEX_COLS = 18          # number of hex columns across x-axis
            ASPECT   = 0.55        # y-stretch so hexes look regular on chart

            x_vals = df9_f["CurrentDebtMB"].values.astype(float)
            y_vals_raw = df9_f["UtilizationRisk"].values.astype(float)

            x_min, x_max_h = float(x_vals.min()), float(x_vals.max())
            y_min, y_max_h = float(y_vals_raw.min()), float(y_vals_raw.max())

            # Guard: avoid division by zero when all values identical
            x_range = (x_max_h - x_min) or 1.0
            y_range = (y_max_h - y_min) or 1.0

            # Hex grid geometry
            hex_w = x_range / HEX_COLS          # hex width in data units
            hex_h = hex_w * ASPECT * (y_range / x_range) * HEX_COLS
            # Make hex_h sensible when aspect ratio is extreme
            HEX_ROWS = max(6, int(y_range / hex_h)) if hex_h > 0 else 10
            hex_h    = y_range / HEX_ROWS

            def hex_center(px, py):
                """Return (cx, cy) of the nearest hex centre for point (px, py)."""
                # Offset-coordinate hex grid (flat-top)
                col_f  = (px - x_min) / hex_w
                col_i  = int(round(col_f))
                offset = 0.5 if col_i % 2 == 1 else 0.0
                row_f  = (py - y_min) / hex_h - offset
                row_i  = int(round(row_f))
                cx = x_min + col_i * hex_w
                cy = y_min + (row_i + offset) * hex_h
                return (round(cx, 4), round(cy, 4))

            # Accumulate
            from collections import defaultdict
            hex_count   = defaultdict(int)
            hex_overdue = defaultdict(float)    # sum of TotalOverdueMB per hex
            hex_names   = defaultdict(list)     # customer names per hex

            for _, row in df9_f.iterrows():
                hc = hex_center(float(row["CurrentDebtMB"]),
                                float(row["UtilizationRisk"]))
                hex_count[hc]   += 1
                hex_overdue[hc] += float(row["TotalOverdueMB"])
                hex_names[hc].append(str(row["CustomerName"]))

            max_count  = max(hex_count.values()) if hex_count else 1
            max_overdue_hex = max(hex_overdue.values()) if hex_overdue else 1.0

            # ── 9.4-1 : ECharts option ───────────────────────────────────
            # Two series:
            #   Series 0 — "hex density"  : scatter with large symbolSize,
            #              symbol = 'circle' tiled as hex proxy,
            #              color mapped to count
            #   Series 1 — "raw scatter"  : small dots, colored by quadrant
            #              shown on top for reference

            # Hex series data  [cx, cy, count, sumOverdueMB, names_str]
            hex_data = []
            for (cx, cy), cnt in hex_count.items():
                hex_data.append([
                    cx, cy, cnt,
                    round(hex_overdue[(cx, cy)], 3),
                    ", ".join(hex_names[(cx, cy)][:5])
                    + ("…" if len(hex_names[(cx, cy)]) > 5 else ""),
                ])

            # Symbol size for hex tiles: fixed grid size (data-unit → pixel approx)
            # ECharts will scale by symbolSize; we use a constant large enough to tile
            HEX_SYMBOL_SIZE = max(18, int(900 / HEX_COLS))

            # Raw scatter data  [x, y, name, quadrant]
            raw_scatter_data = []
            for _, row in df9_f.iterrows():
                raw_scatter_data.append({
                    "value": [
                        round(float(row["CurrentDebtMB"]),    3),
                        round(float(row["UtilizationRisk"]),  2),
                    ],
                    "name":      str(row["CustomerName"]),
                    "quadrant":  str(row["RiskQuadrant"]),
                    "itemStyle": {
                        "color": ECHARTS_COLOR_MAP.get(
                            str(row["RiskQuadrant"]), "#95a5a6"
                        ),
                        "borderColor": "white",
                        "borderWidth": 1,
                    },
                })

            # Visual map: count → colour gradient (low=cool, high=hot)
            DENSITY_COLORS = [
                "#eaf4fb",   # 0  — nearly empty
                "#aed6f1",   # 1
                "#5dade2",   # 2
                "#1a5276",   # 3
                "#f9e79f",   # 4
                "#f39c12",   # 5
                "#e74c3c",   # 6  — very dense
                "#7b241c",   # 7  — max density
            ]

            echarts_hex_option = {
                "backgroundColor": "#fafafa",
                "title": {
                    "text":     "Hexbin Density — Utilization Risk Map",
                    "subtext":  (
                        f"Hex colour = customer density | "
                        f"Dots = individual customers | "
                        f"Threshold = {util_threshold}%"
                    ),
                    "left":    "center",
                    "textStyle":    {"fontSize": 15, "fontWeight": "bold"},
                    "subtextStyle": {"fontSize": 10, "color": "#666"},
                },
                "tooltip": {
                    "trigger": "item",
                    "formatter": """function(p) {
                        if (p.seriesIndex === 0) {
                            // Hex tile
                            return '<b>Hex Cell</b><br/>'
                                + 'Center Debt: <b>'  + p.data[0].toFixed(2) + ' MB</b><br/>'
                                + 'Center Util: <b>'  + p.data[1].toFixed(1) + '%</b><br/>'
                                + 'Customers: <b>'    + p.data[2] + '</b><br/>'
                                + 'Sum Overdue: <b>'  + p.data[3].toFixed(2) + ' MB</b><br/>'
                                + 'Names: '           + p.data[4];
                        } else {
                            // Raw dot
                            return '<b>' + p.data.name + '</b><br/>'
                                + 'Current Debt: <b>'     + p.data.value[0].toFixed(2) + ' MB</b><br/>'
                                + 'Utilization Risk: <b>' + p.data.value[1].toFixed(1) + '%</b><br/>'
                                + 'Quadrant: '            + p.data.quadrant;
                        }
                    }""",
                },
                "visualMap": {
                    "show":        True,
                    "type":        "continuous",
                    "seriesIndex": 0,           # only map hex series
                    "min":         1,
                    "max":         max_count,
                    "left":        "right",
                    "top":         "middle",
                    "orient":      "vertical",
                    "text":        ["Dense", "Sparse"],
                    "textStyle":   {"fontSize": 10},
                    "inRange": {
                        "color": DENSITY_COLORS,
                    },
                    "calculable": True,
                },
                "grid": {
                    "left":         "8%",
                    "right":        "12%",
                    "top":          "16%",
                    "bottom":       "10%",
                    "containLabel": True,
                },
                "xAxis": {
                    "type":          "value",
                    "name":          "Current Debt (MB)",
                    "nameLocation":  "middle",
                    "nameGap":       30,
                    "nameTextStyle": {"fontSize": 11},
                    "splitLine":     {"show": True,
                                     "lineStyle": {"type": "dashed",
                                                   "color": "#e0e0e0"}},
                    "axisLabel":     {"fontSize": 10},
                },
                "yAxis": {
                    "type":          "value",
                    "name":          "Utilization Risk (%)",
                    "nameLocation":  "middle",
                    "nameGap":       48,
                    "nameTextStyle": {"fontSize": 11},
                    "splitLine":     {"show": True,
                                     "lineStyle": {"type": "dashed",
                                                   "color": "#e0e0e0"}},
                    "axisLabel":     {"fontSize": 10},
                },
                "series": [
                    # ── Series 0 : Hex density tiles ─────────────────────
                    {
                        "name":        "Hex Density",
                        "type":        "scatter",
                        "data":        hex_data,
                        "symbolSize":  HEX_SYMBOL_SIZE,
                        "symbol":      "roundRect",   # nearest ECharts proxy for hex
                        "itemStyle":   {
                            "opacity":     0.72,
                            "borderColor": "white",
                            "borderWidth": 1.5,
                        },
                        "emphasis": {
                            "itemStyle": {
                                "opacity":     1.0,
                                "borderWidth": 2,
                            },
                        },
                        "encode": {
                            "x":       0,
                            "y":       1,
                            "value":   2,       # drives visualMap
                        },
                        "zlevel": 0,
                        "z":      2,
                    },
                    # ── Series 1 : Raw customer dots ─────────────────────
                    {
                        "name":       "Customers",
                        "type":       "scatter",
                        "data":       raw_scatter_data,
                        "symbolSize": 6,
                        "symbol":     "circle",
                        "itemStyle":  {
                            "opacity":     0.95,
                            "borderColor": "white",
                            "borderWidth": 1,
                        },
                        "emphasis": {
                            "label": {
                                "show":       True,
                                "formatter":  "{b}",
                                "fontSize":   10,
                                "fontWeight": "bold",
                                "color":      "#222",
                            },
                            "itemStyle": {"opacity": 1.0, "symbolSize": 12},
                        },
                        "zlevel": 1,
                        "z":      4,
                    },
                ],
                # Quadrant divider lines via markLine on a dummy series
                # → inject into Series 1 directly
            }

            # Inject markLine into Series 1 (raw dots) for quadrant dividers
            echarts_hex_option["series"][1]["markLine"] = {
                "silent":    False,
                "animation": False,
                "lineStyle": {"type": "dashed", "width": 1.5, "opacity": 0.6},
                "label":     {"show": True, "fontSize": 9, "color": "#888"},
                "data": [
                    {
                        "xAxis": round(med_debt, 2),
                        "name":  f"Debt Median {med_debt:.1f}MB",
                        "lineStyle": {"color": "#5d6d7e"},
                    },
                    {
                        "yAxis": float(util_threshold),
                        "name":  f"Risk {util_threshold}%",
                        "lineStyle": {"color": "#e74c3c"},
                    },
                ],
            }

            st_echarts(
                options=echarts_hex_option,
                height="580px",
                key="echarts_hexbin",
            )

            # ── 9.4-2 : Density summary table ────────────────────────────
            st.caption("📋 Hex Cell Summary — Top 10 Most Dense Cells")
            hex_summary_rows = []
            for (cx, cy), cnt in sorted(
                hex_count.items(), key=lambda kv: -kv[1]
            )[:10]:
                # Which quadrant does this hex center fall in?
                h_quad = "🔴 High Debt · High Risk"
                if cx < med_debt and cy >= util_threshold:
                    h_quad = "🟠 Low Debt · High Risk"
                elif cx >= med_debt and cy < util_threshold:
                    h_quad = "🟡 High Debt · Low Risk"
                elif cx < med_debt and cy < util_threshold:
                    h_quad = "🟢 Low Debt · Low Risk"
                hex_summary_rows.append({
                    "Hex Center Debt (MB)":  round(cx, 2),
                    "Hex Center Util (%)":   round(cy, 2),
                    "# Customers":           cnt,
                    "Sum Overdue (MB)":      round(hex_overdue[(cx, cy)], 3),
                    "Avg Overdue (MB)":      round(hex_overdue[(cx, cy)] / cnt, 3),
                    "Quadrant":              h_quad,
                    "Customers":             ", ".join(hex_names[(cx, cy)][:4])
                                             + ("…" if cnt > 4 else ""),
                })
            if hex_summary_rows:
                st.dataframe(
                    pd.DataFrame(hex_summary_rows),
                    hide_index=True,
                    use_container_width=True,
                )

            log.info(
                f"Step 9.4 Hexbin — {len(hex_data)} hex cells, "
                f"max density {max_count}, customers {len(df9_f)}"
            )
        else:
            st.info("ติดตั้ง `streamlit-echarts` เพื่อดู Hexbin chart")


# =============================================================================
# Download Log
# =============================================================================
log.info("SESSION COMPLETE")
st.header("Download Log")
with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
    log_content = f.read()
st.download_button(
    "Download debug_join.log",
    data=log_content,
    file_name="debug_join.log",
    mime="text/plain",
)
st.code(log_content[-3000:], language="text")