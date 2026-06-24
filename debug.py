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


# =============================================================================
# Step 10 : Advanced Portfolio Analytics — 3 Approaches Preview
# (Prototype ก่อน migrate เข้า view_monitoring.py)
#
# Approach A : Customer Payment DNA     (Scatter — Behavioral Map)
# Approach B : Cash Flow Leakage        (Dual Cumulative Line)
# Approach C : Concentration Risk       (Sunburst)
#
# Data used:
#   ov        — invoice-level (from Step 6B)
#   cust_risk — customer-level aggregated (from Step 6E)
#   ov_f      — invoice filtered by date range (from Step 7 global filter)
# =============================================================================

lsec("STEP 10 — Advanced Portfolio Analytics Preview")
st.markdown("---")
st.header("10. Advanced Portfolio Analytics — 3 Approaches Preview")
st.caption(
    "Prototype visualization ก่อนนำเข้า view_monitoring.py — "
    "ใช้ข้อมูลจาก Step 6 (cust_risk) และ Step 7 (ov_f)"
)

if cust_risk.empty:
    st.warning("cust_risk ว่าง — รัน Step 6 ก่อน")
    st.stop()

tab_a, tab_b, tab_c = st.tabs([
    "A : Customer Payment DNA",
    "B : Cash Flow Leakage",
    "C : Concentration Risk",
])

# ===========================================================================
# APPROACH A — Customer Payment DNA
# X = Avg Delay (AvgDPD), Y = Delay Volatility (StdDPD)
# Size = TotalInvoices, Color = Quadrant
# ===========================================================================
with tab_a:
    st.subheader("A — Customer Payment DNA")
    st.caption(
        "แต่ละจุด = 1 customer | "
        "X = Avg DPD | Y = Std DPD (Volatility) | "
        "Size = Total Invoices | Color = Behavioral Quadrant"
    )

    # ------------------------------------------------------------------
    # Build per-customer DNA stats จาก ov (invoice-level)
    # ------------------------------------------------------------------
    # ใช้ทุก invoice ใน date range (ov_f) ไม่กรองแค่ overdue
    # เพื่อให้ Collection Rate สะท้อนภาพรวม
    # ------------------------------------------------------------------
    ov_dna = ov_f.copy()
    ov_dna["DPD_filled"] = ov_dna["DPD"].fillna(0).clip(lower=0)

    dna_agg = (
        ov_dna.groupby(join_key)
        .agg(
            AvgDelay      = ("DPD_filled", "mean"),
            StdDelay      = ("DPD_filled", "std"),
            MaxDelay      = ("DPD_filled", "max"),
            TotalInvoices = (join_key,     "count"),
            OverdueCount  = ("OverdueAmount_num", lambda x: (x > 0).sum()),
        )
        .reset_index()
        .rename(columns={join_key: "Customer"})
    )

    # Join CustomerName + Type
    name_map = cust_risk[["Customer", "CustomerName", "TYPE"]].drop_duplicates("Customer")
    dna_agg  = dna_agg.merge(name_map, on="Customer", how="left")
    dna_agg["CustomerName"] = dna_agg["CustomerName"].fillna(dna_agg["Customer"].astype(str))
    dna_agg["TYPE"]         = dna_agg["TYPE"].fillna("Unknown")

    dna_agg["StdDelay"]  = dna_agg["StdDelay"].fillna(0.0)
    dna_agg["AvgDelay"]  = dna_agg["AvgDelay"].fillna(0.0)
    dna_agg["MaxDelay"]  = dna_agg["MaxDelay"].fillna(0.0)

    # Collection Rate
    dna_agg["CollectionRate"] = (
        (dna_agg["TotalInvoices"] - dna_agg["OverdueCount"])
        / dna_agg["TotalInvoices"].replace(0, np.nan) * 100
    ).fillna(0.0).clip(0, 100)

    dna_agg = dna_agg[dna_agg["TotalInvoices"] > 0].reset_index(drop=True)

    if dna_agg.empty:
        st.info("ไม่มีข้อมูลสำหรับ Payment DNA ในช่วงที่เลือก")
    else:
        # Quadrant (median split)
        med_avg = float(dna_agg["AvgDelay"].median())
        med_std = float(dna_agg["StdDelay"].median())

        def _dna_quad(avg, std):
            hi_avg = avg >= med_avg
            hi_std = std >= med_std
            if not hi_avg and not hi_std:
                return "Predictable"
            elif hi_avg and hi_std:
                return "Nightmare"
            elif hi_avg and not hi_std:
                return "Consistently Late"
            else:
                return "Erratic"

        dna_agg["Quadrant"] = dna_agg.apply(
            lambda r: _dna_quad(r["AvgDelay"], r["StdDelay"]), axis=1
        )

        QUAD_COLOR = {
            "Predictable":       "#2A9D8F",
            "Nightmare":         "#A01F2D",
            "Consistently Late": "#B5620A",
            "Erratic":           "#8E6DC0",
        }
        QUAD_ORDER = ["Predictable", "Consistently Late", "Erratic", "Nightmare"]

        # Bubble size — TotalInvoices
        inv_s    = dna_agg["TotalInvoices"].clip(lower=1).astype(float)
        inv_min  = float(inv_s.min())
        inv_max  = float(inv_s.max())
        inv_rng  = max(inv_max - inv_min, 1.0)
        dna_agg["BubbleSize"] = (
            8.0 + ((inv_s - inv_min) / inv_rng) * 42.0
        ).clip(6.0, 50.0)

        # KPI summary
        qa_col, qb_col, qc_col, qd_col = st.columns(4)
        for col_ui, quad in zip(
            [qa_col, qb_col, qc_col, qd_col], QUAD_ORDER
        ):
            cnt = int((dna_agg["Quadrant"] == quad).sum())
            col_ui.metric(quad, f"{cnt} customers")

        # Figure
        fig_dna = go.Figure()
        for quad in QUAD_ORDER:
            grp = dna_agg[dna_agg["Quadrant"] == quad].copy()
            if grp.empty:
                continue
            fig_dna.add_trace(go.Scatter(
                x    = grp["AvgDelay"].tolist(),
                y    = grp["StdDelay"].tolist(),
                mode = "markers",
                name = quad,
                marker = dict(
                    size     = grp["BubbleSize"].tolist(),
                    color    = QUAD_COLOR.get(quad, "#8A9BB0"),
                    opacity  = 0.82,
                    line     = dict(width=1, color="white"),
                    sizemode = "diameter",
                ),
                text       = grp["CustomerName"].astype(str).tolist(),
                customdata = list(zip(
                    grp["AvgDelay"].round(1).tolist(),
                    grp["StdDelay"].round(1).tolist(),
                    grp["MaxDelay"].tolist(),
                    grp["TotalInvoices"].tolist(),
                    grp["CollectionRate"].round(1).tolist(),
                )),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "────────────────────<br>"
                    "Avg Delay        : %{customdata[0]:.1f} days<br>"
                    "Delay Volatility : %{customdata[1]:.1f} days (std)<br>"
                    "Max Delay        : %{customdata[2]:,} days<br>"
                    "Total Invoices   : %{customdata[3]:,}<br>"
                    "Collection Rate  : %{customdata[4]:.1f}%<br>"
                    "<extra></extra>"
                ),
            ))

        # Quadrant reference lines
        fig_dna.add_vline(
            x=med_avg, line_dash="dot", line_color="#cccccc", line_width=1.2,
            annotation_text=f"Median Avg ({med_avg:.0f}d)",
            annotation_font=dict(size=8, color="#999999"),
        )
        fig_dna.add_hline(
            y=med_std, line_dash="dot", line_color="#cccccc", line_width=1.2,
            annotation_text=f"Median Std ({med_std:.0f}d)",
            annotation_font=dict(size=8, color="#999999"),
            annotation_position="right",
        )

        # Quadrant background labels
        x_max_dna = float(dna_agg["AvgDelay"].max()) * 1.1
        y_max_dna = float(dna_agg["StdDelay"].max()) * 1.1
        quad_annotations = [
            (med_avg * 0.25, med_std * 1.65, "Erratic",           QUAD_COLOR["Erratic"]),
            (med_avg * 1.75, med_std * 1.65, "Nightmare",         QUAD_COLOR["Nightmare"]),
            (med_avg * 0.25, med_std * 0.30, "Predictable",       QUAD_COLOR["Predictable"]),
            (med_avg * 1.75, med_std * 0.30, "Consistently Late", QUAD_COLOR["Consistently Late"]),
        ]
        for qx, qy, qlabel, qcol in quad_annotations:
            fig_dna.add_annotation(
                x=qx, y=qy, text=f"<i>{qlabel}</i>",
                showarrow=False,
                font=dict(size=9, color=qcol), opacity=0.50,
            )

        fig_dna.update_layout(
            title        = "Customer Payment DNA — Avg Delay vs Delay Volatility",
            xaxis        = dict(title="Average Delay (days)", zeroline=False,
                                range=[0, max(x_max_dna, 1)]),
            yaxis        = dict(title="Delay Volatility — Std Dev (days)", zeroline=False,
                                range=[0, max(y_max_dna, 1)]),
            height       = 520,
            legend       = dict(title="Quadrant"),
            plot_bgcolor = "#f9f9f9",
        )
        st.plotly_chart(fig_dna, use_container_width=True, key="step10_dna")

        # Quadrant breakdown table
        with st.expander("Quadrant Detail Table", expanded=False):
            show_dna = dna_agg[[
                "CustomerName", "Quadrant", "AvgDelay", "StdDelay",
                "MaxDelay", "TotalInvoices", "OverdueCount", "CollectionRate", "TYPE",
            ]].sort_values(["Quadrant", "AvgDelay"], ascending=[True, False]).copy()
            for c in ["AvgDelay", "StdDelay", "MaxDelay", "CollectionRate"]:
                show_dna[c] = show_dna[c].round(1)
            st.dataframe(show_dna, hide_index=True, use_container_width=True)


# ===========================================================================
# APPROACH B — Expected vs Actual Collection Curve (Cash Flow Leakage)
# X = Period, Y = Cumulative Cash (InvoiceAmount)
# Expected = grouped by OriginalDueDate
# Actual   = grouped by CollectionDate (collected only)
# ===========================================================================
with tab_b:
    st.subheader("B — Expected vs Actual Collection Curve")
    st.caption(
        "Expected = ถ้าทุกคนจ่ายตรงตาม OriginalDueDate | "
        "Actual = จ่ายจริงตาม CollectionDate | "
        "Gap = Cash Flow Leakage"
    )

    # Granularity selector (local — ไม่ขึ้นกับ global filter)
    cf_gran_b = st.selectbox(
        "Period Granularity",
        options=["Monthly", "Quarterly", "Yearly"],
        index=0,
        key="step10_cf_gran",
    )
    GRAN_MAP_B = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}
    gran_pb = GRAN_MAP_B[cf_gran_b]

    # ------------------------------------------------------------------
    # Expected — group InvoiceAmount by OriginalDueDate
    # ------------------------------------------------------------------
    ov_cf = ov_f.copy()
    ov_cf["InvoiceAmount_num"] = pd.to_numeric(
        ov_cf.get("InvoiceAmount_num", ov_cf.get("InvoiceAmount", 0)),
        errors="coerce",
    ).fillna(0.0).abs()

    exp_df = ov_cf.dropna(subset=["OriginalDueDate_parsed"]).copy()
    exp_df["Period_exp"] = (
        exp_df["OriginalDueDate_parsed"].dt.to_period(gran_pb).astype(str)
    )
    exp_grp = (
        exp_df.groupby("Period_exp")
        .agg(Expected=("InvoiceAmount_num", "sum"))
        .reset_index()
        .sort_values("Period_exp")
        .reset_index(drop=True)
    )
    exp_grp["CumExpected"] = exp_grp["Expected"].cumsum()

    # ------------------------------------------------------------------
    # Actual — group InvoiceAmount by CollectionDate (collected only)
    # ------------------------------------------------------------------
    act_df = ov_cf.dropna(subset=["CollectionDate_parsed"]).copy()
    act_df = act_df[act_df["CollectionDate_parsed"].notna()]
    act_df["Period_act"] = (
        act_df["CollectionDate_parsed"].dt.to_period(gran_pb).astype(str)
    )
    act_grp = (
        act_df.groupby("Period_act")
        .agg(Actual=("InvoiceAmount_num", "sum"))
        .reset_index()
        .rename(columns={"Period_act": "Period_exp"})
        .sort_values("Period_exp")
        .reset_index(drop=True)
    )
    act_grp["CumActual"] = act_grp["Actual"].cumsum()

    # Merge
    cf_merged = exp_grp[["Period_exp", "CumExpected"]].merge(
        act_grp[["Period_exp", "CumActual"]],
        on="Period_exp", how="left",
    )
    cf_merged["CumActual"] = (
        cf_merged["CumActual"]
        .ffill()                  
        .fillna(0.0)              
    )
    cf_merged = cf_merged.sort_values("Period_exp").reset_index(drop=True)

    if cf_merged.empty or cf_merged["CumExpected"].sum() == 0:
        st.info("ไม่มีข้อมูล InvoiceAmount ในช่วงที่เลือก")
    else:
        total_exp_b = float(cf_merged["CumExpected"].iloc[-1])
        total_act_b = float(cf_merged["CumActual"].iloc[-1])
        leakage_b   = total_exp_b - total_act_b
        leakage_pct_b = leakage_b / total_exp_b * 100 if total_exp_b > 0 else 0.0

        # KPI
        kb1, kb2, kb3 = st.columns(3)
        kb1.metric("Expected Collection", f"{total_exp_b:,.0f} THB")
        kb2.metric("Actual Collection",   f"{total_act_b:,.0f} THB")
        kb3.metric(
            "Cash Flow Leakage",
            f"{leakage_b:,.0f} THB",
            delta=f"{leakage_pct_b:.1f}% of expected",
            delta_color="inverse",
        )

        # Figure
        fig_cf = go.Figure()

        # Leakage fill zone
        if total_act_b > 0:
            fig_cf.add_trace(go.Scatter(
                x          = cf_merged["Period_exp"].tolist(),
                y          = cf_merged["CumExpected"].tolist(),
                mode       = "none",
                fill       = "tonexty",
                fillcolor  = "rgba(160,31,45,0.07)",
                showlegend = False,
                hoverinfo  = "skip",
            ))

        # Actual line
        if total_act_b > 0:
            fig_cf.add_trace(go.Scatter(
                x    = cf_merged["Period_exp"].tolist(),
                y    = cf_merged["CumActual"].tolist(),
                mode = "lines+markers",
                name = "Actual Collection",
                line = dict(color="#3A7BD5", width=2.5),
                marker = dict(size=6, color="#3A7BD5",
                              line=dict(color="white", width=1.5)),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Actual Cumulative : %{y:,.0f} THB<br>"
                    "<extra></extra>"
                ),
            ))

        # Expected line
        fig_cf.add_trace(go.Scatter(
            x    = cf_merged["Period_exp"].tolist(),
            y    = cf_merged["CumExpected"].tolist(),
            mode = "lines+markers",
            name = "Expected Collection",
            line = dict(color="#2A9D8F", width=2.5, dash="dot"),
            marker = dict(symbol="diamond", size=6, color="#2A9D8F",
                          line=dict(color="white", width=1.5)),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Expected Cumulative : %{y:,.0f} THB<br>"
                "<extra></extra>"
            ),
        ))

        y_max_cf = float(cf_merged["CumExpected"].max()) * 1.15
        fig_cf.update_layout(
            title        = "Expected vs Actual Collection Curve — Cash Flow Leakage",
            xaxis        = dict(title="Period", showgrid=False, tickangle=-35),
            yaxis        = dict(title="Cumulative Cash (THB)", range=[0, y_max_cf],
                                tickformat=",.0f"),
            height       = 480,
            legend       = dict(orientation="h", y=-0.2),
            plot_bgcolor = "#f9f9f9",
        )
        st.plotly_chart(fig_cf, use_container_width=True, key="step10_cashflow")

        # Gap table
        with st.expander("Period Gap Detail", expanded=False):
            cf_detail = cf_merged.copy()
            cf_detail["Gap"] = cf_detail["CumExpected"] - cf_detail["CumActual"]
            cf_detail["Gap %"] = (
                cf_detail["Gap"] / cf_detail["CumExpected"].replace(0, np.nan) * 100
            ).fillna(0.0).round(1)
            for c in ["CumExpected", "CumActual", "Gap"]:
                cf_detail[c] = cf_detail[c].round(0).astype(int)
            st.dataframe(
                cf_detail.rename(columns={
                    "Period_exp":   "Period",
                    "CumExpected":  "Cum Expected (THB)",
                    "CumActual":    "Cum Actual (THB)",
                    "Gap":          "Gap (THB)",
                    "Gap %":        "Gap %",
                }),
                hide_index=True,
                use_container_width=True,
            )


# ===========================================================================
# APPROACH C — Customer Concentration Risk (Sunburst)
# DebtShare = CustomerDebt / PortfolioDebt
# Tier: Critical >= 20%, Major >= 5%, Minor < 5%
# ===========================================================================
with tab_c:
    st.subheader("C — Customer Concentration Risk")
    st.caption(
        "Sunburst: Level 1 = Tier (Critical/Major/Minor) | "
        "Level 2 = Customer | "
        "Size = TotalOverdueMB"
    )

    conc_df = cust_risk[cust_risk["TotalOverdueMB"] > 0].copy()

    # ใช้ CurrentDebtMB ถ้ามี, fallback TotalOverdueMB
    if (conc_df["CurrentDebtMB"] > 0).any():
        debt_col_c  = "CurrentDebtMB"
        debt_label  = "Current Debt (MB)"
    else:
        debt_col_c  = "TotalOverdueMB"
        debt_label  = "Total Overdue (MB)"

    if sel_types:
        conc_df = conc_df[conc_df["TYPE"].isin(sel_types)].copy()

    if conc_df.empty:
        st.info("ไม่มีข้อมูลสำหรับ Concentration Risk")
    else:
        portfolio_total_c = float(conc_df[debt_col_c].sum())
        if portfolio_total_c == 0:
            st.info("Portfolio total = 0")
        else:
            conc_df["DebtShare"] = (
                conc_df[debt_col_c] / portfolio_total_c * 100
            ).round(2)

            def _conc_tier(share):
                if share >= 20: return "Critical"
                elif share >= 5:  return "Major"
                else:             return "Minor"

            conc_df["Tier"] = conc_df["DebtShare"].apply(_conc_tier)

            TIER_COLOR_C = {
                "Critical": "#A01F2D",
                "Major":    "#B5620A",
                "Minor":    "#3A7BD5",
            }

            # KPI
            top3_c = conc_df.sort_values("DebtShare", ascending=False).head(3)
            kc1, kc2, kc3 = st.columns(3)
            kc1.metric("Portfolio Total", f"{portfolio_total_c:,.1f} MB",
                       f"{int(len(conc_df))} customers")
            kc2.metric("Critical (≥20%)",
                       f"{int((conc_df['Tier']=='Critical').sum())} customers",
                       delta="Highest concentration risk", delta_color="inverse")
            kc3.metric("Top 3 Share",
                       f"{float(top3_c['DebtShare'].sum()):.1f}%",
                       "of total portfolio")

            # Sunburst data
            sb_ids, sb_labels, sb_parents, sb_values, sb_colors, sb_text = (
                [], [], [], [], [], []
            )

            # Root
            sb_ids.append("Portfolio")
            sb_labels.append("Portfolio")
            sb_parents.append("")
            sb_values.append(float(portfolio_total_c))
            sb_colors.append("#3D5166")
            sb_text.append(f"Total: {portfolio_total_c:,.1f} MB")

            for tier in ["Critical", "Major", "Minor"]:
                tier_df    = conc_df[conc_df["Tier"] == tier]
                tier_total = float(tier_df[debt_col_c].sum())
                tier_share = tier_total / portfolio_total_c * 100

                sb_ids.append(tier)
                sb_labels.append(f"{tier} ({tier_share:.1f}%)")
                sb_parents.append("Portfolio")
                sb_values.append(tier_total)
                sb_colors.append(TIER_COLOR_C[tier])
                sb_text.append(
                    f"{tier}: {tier_total:,.1f} MB ({tier_share:.1f}%)"
                )

                # Top 10 customers per tier
                tier_sorted = tier_df.sort_values(debt_col_c, ascending=False)
                top_c       = tier_sorted.head(10)
                rest_c      = tier_sorted.iloc[10:]

                for _, row in top_c.iterrows():
                    cname  = str(row["CustomerName"])
                    cdebt  = float(row[debt_col_c])
                    cshare = float(row["DebtShare"])
                    label_short = cname[:22] + "…" if len(cname) > 22 else cname

                    sb_ids.append(f"{tier}__{cname}")
                    sb_labels.append(label_short)
                    sb_parents.append(tier)
                    sb_values.append(cdebt)
                    sb_colors.append(TIER_COLOR_C[tier])
                    sb_text.append(f"{cname}<br>{cdebt:,.1f} MB ({cshare:.1f}%)")

                if not rest_c.empty:
                    rest_d = float(rest_c[debt_col_c].sum())
                    rest_s = rest_d / portfolio_total_c * 100
                    sb_ids.append(f"{tier}__Others")
                    sb_labels.append(f"Others ({len(rest_c)})")
                    sb_parents.append(tier)
                    sb_values.append(rest_d)
                    sb_colors.append(TIER_COLOR_C[tier])
                    sb_text.append(
                        f"Others ({len(rest_c)} customers)<br>"
                        f"{rest_d:,.1f} MB ({rest_s:.1f}%)"
                    )

            fig_sun = go.Figure(go.Sunburst(
                ids           = sb_ids,
                labels        = sb_labels,
                parents       = sb_parents,
                values        = sb_values,
                marker        = dict(
                    colors = sb_colors,
                    line   = dict(color="white", width=1.5),
                ),
                text          = sb_text,
                hovertemplate = "<b>%{label}</b><br>%{text}<extra></extra>",
                textfont      = dict(size=10),
                insidetextorientation = "radial",
                branchvalues  = "total",
                maxdepth      = 2,
            ))
            fig_sun.update_layout(
                title        = f"Customer Concentration Risk — {debt_label}",
                height       = 520,
                margin       = dict(l=0, r=0, t=40, b=0),
                paper_bgcolor= "rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_sun, use_container_width=True, key="step10_sunburst")

            # Top 15 table
            with st.expander("Top 15 Customers by Debt Share", expanded=False):
                top15_c = (
                    conc_df[["CustomerName", "TYPE", debt_col_c, "DebtShare", "Tier"]]
                    .sort_values("DebtShare", ascending=False)
                    .head(15)
                    .copy()
                    .reset_index(drop=True)
                )
                top15_c.index = top15_c.index + 1
                top15_c[debt_col_c]   = top15_c[debt_col_c].round(2)
                top15_c["DebtShare"]  = top15_c["DebtShare"].round(2)
                st.dataframe(
                    top15_c.rename(columns={
                        "CustomerName": "Customer",
                        "TYPE":         "Type",
                        debt_col_c:     debt_label,
                        "DebtShare":    "Share %",
                    }),
                    hide_index=False,
                    use_container_width=True,
                )


# =============================================================================
# Step 11 : Credit Risk Network Graph — 5 Approaches
# ใช้ตัวแปรจาก Step 6E (cust_risk) และ Step 7 (cr_f, ov_f)
#
# 11.A : Customer Similarity Network  (Cosine / Euclidean)
# 11.B : Customer → Risk Bucket Network
# 11.C : Exposure Concentration Network
# 11.D : Credit Risk Propagation + Community Detection (Louvain / Leiden)
# 11.E : Bipartite Network — ECharts Graph Series  ← Impact สูงสุด
# =============================================================================

lsec("STEP 11 — Credit Risk Network Graph")
st.markdown("---")
st.header("11. Credit Risk Network Graph")

if cust_risk.empty:
    st.warning("cust_risk ว่าง — รัน Step 6 ก่อน")
    st.stop()

# ใช้ cr_f ถ้ามี ไม่งั้น fallback cust_risk
graph_base = cr_f.copy() if (not cr_f.empty) else cust_risk.copy()
graph_base = graph_base.reset_index(drop=True)

# Guard — fillna ทุก numeric column ที่จะใช้
for _c in ["UtilizationPct", "CurrentDebtMB", "TotalOverdueMB",
           "AvgDPD", "OverdueRatio", "CleanCreditMB"]:
    if _c in graph_base.columns:
        graph_base[_c] = graph_base[_c].fillna(0.0)

try:
    from streamlit_echarts import st_echarts
    ECHARTS_OK = True
except ImportError:
    ECHARTS_OK = False
    st.warning("streamlit-echarts ไม่ได้ติดตั้ง — Step 11.E จะข้ามไป")

import math
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
import plotly.graph_objects as go

# =============================================================================
# Helper — short name (ตัดชื่อยาว)
# =============================================================================
def _short(name: str, n: int = 20) -> str:
    s = str(name)
    return s[:n] + "…" if len(s) > n else s

# =============================================================================
# Helper — Risk Tier (ใช้ร่วมกันทุก sub-step)
# =============================================================================
def _tier(util, dpd):
    u = float(util) if not pd.isna(util) else 0.0
    d = float(dpd)  if not pd.isna(dpd)  else 0.0
    if u >= 80 and d >= 60: return "Critical"
    elif u >= 80 or d >= 60: return "High Risk"
    elif u >= 50 or d >= 30: return "Watch"
    else:                    return "Healthy"

TIER_HEX = {
    "Critical":  "#A01F2D",
    "High Risk": "#B5620A",
    "Watch":     "#E8A838",
    "Healthy":   "#2A9D8F",
    "Unknown":   "#8A9BB0",
}

graph_base["RiskTier"] = graph_base.apply(
    lambda r: _tier(r["UtilizationPct"], r["AvgDPD"]), axis=1
)

# =============================================================================
# Tab layout
# =============================================================================
tab11a, tab11b, tab11c, tab11d, tab11e = st.tabs([
    "11.A  Similarity Network",
    "11.B  Risk Bucket Network",
    "11.C  Exposure Concentration",
    "11.D  Risk Propagation + Community",
    "11.E  Bipartite (ECharts)",
])


# ─────────────────────────────────────────────────────────────────────────────
# 11.A : Customer Similarity Network
# Feature vector : [Utilization, CurrentDebt, TotalOverdue, AvgDPD]
# Metric         : Cosine Similarity  OR  Euclidean Distance
# Edge           : เชื่อมเมื่อ similarity เกิน threshold
# ─────────────────────────────────────────────────────────────────────────────
with tab11a:
    st.subheader("11.A — Customer Similarity Network")
    st.caption(
        "ลูกค้าที่มีพฤติกรรมเครดิตคล้ายกันจะเชื่อมกัน | "
        "Feature Vector: [Utilization%, CurrentDebt, TotalOverdue, AvgDPD]"
    )

    # Controls
    ca1, ca2, ca3, ca4 = st.columns([1.5, 1.5, 1.5, 1.5])
    with ca1:
        sim_metric = st.selectbox(
            "Similarity Metric",
            ["Cosine Similarity", "Euclidean Distance"],
            key="sim_metric",
        )
    with ca2:
        sim_threshold = st.slider(
            "Edge Threshold (similarity)",
            min_value=0.50, max_value=0.99, value=0.85, step=0.01,
            key="sim_thresh",
            help="Cosine: เชื่อมถ้า similarity >= threshold\n"
                 "Euclidean: เชื่อมถ้า distance <= (1-threshold)*max_dist",
        )
    with ca3:
        sim_top_n = st.slider(
            "Top N Customers",
            min_value=5, max_value=min(50, len(graph_base)),
            value=min(20, len(graph_base)), step=5,
            key="sim_top_n",
        )
    with ca4:
        sim_show_isolated = st.checkbox(
            "Show isolated nodes", value=True, key="sim_isolated"
        )

    df_sim = (
        graph_base
        .sort_values("TotalOverdueMB", ascending=False)
        .head(sim_top_n)
        .reset_index(drop=True)
        .copy()
    )

    # Feature matrix
    feat_cols = ["UtilizationPct", "CurrentDebtMB", "TotalOverdueMB", "AvgDPD"]
    feat_cols = [c for c in feat_cols if c in df_sim.columns]
    X_raw = df_sim[feat_cols].fillna(0).values.astype(float)

    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # Similarity / Distance matrix
    if sim_metric == "Cosine Similarity":
        # Add epsilon เพื่อกัน zero-vector
        X_eps    = X_scaled + 1e-9
        sim_mat  = cosine_similarity(X_eps)
        # เชื่อมถ้า similarity >= threshold (และไม่ใช่ตัวเอง)
        def _connected(i, j):
            return i != j and sim_mat[i, j] >= sim_threshold
        def _edge_weight(i, j):
            return float(sim_mat[i, j])
    else:
        dist_mat = euclidean_distances(X_scaled)
        max_dist = float(dist_mat.max()) or 1.0
        dist_thresh = (1.0 - sim_threshold) * max_dist
        def _connected(i, j):
            return i != j and dist_mat[i, j] <= dist_thresh
        def _edge_weight(i, j):
            # แปลง distance → similarity-like score
            return float(1.0 - dist_mat[i, j] / max_dist)

    # Build edges
    edges_sim = []
    for i in range(len(df_sim)):
        for j in range(i + 1, len(df_sim)):
            if _connected(i, j):
                edges_sim.append((i, j, _edge_weight(i, j)))

    # Connected node set
    connected_nodes = set()
    for e in edges_sim:
        connected_nodes.add(e[0])
        connected_nodes.add(e[1])

    # Layout — force-directed approximation (spring layout manual)
    n = len(df_sim)
    angles = [2 * math.pi * i / n for i in range(n)]
    # Base radius — connected nodes inner, isolated outer
    pos_x = [math.cos(a) * (1.8 if i in connected_nodes else 3.2)
              for i, a in enumerate(angles)]
    pos_y = [math.sin(a) * (1.8 if i in connected_nodes else 3.2)
              for i, a in enumerate(angles)]

    # Figure
    fig_sim = go.Figure()

    # Edges
    for (i, j, w) in edges_sim:
        alpha = max(0.15, min(float(w), 0.85))
        fig_sim.add_trace(go.Scatter(
            x=[pos_x[i], pos_x[j], None],
            y=[pos_y[i], pos_y[j], None],
            mode="lines",
            line=dict(
                color=f"rgba(100,150,200,{alpha:.2f})",
                width=max(0.5, w * 3),
            ),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Nodes — grouped by RiskTier
    for tier in ["Critical", "High Risk", "Watch", "Healthy", "Unknown"]:
        idxs = [i for i in range(n)
                if df_sim.iloc[i]["RiskTier"] == tier
                and (sim_show_isolated or i in connected_nodes)]
        if not idxs:
            continue

        fig_sim.add_trace(go.Scatter(
            x=[pos_x[i] for i in idxs],
            y=[pos_y[i] for i in idxs],
            mode="markers+text",
            name=tier,
            marker=dict(
                size=[
                    10 + float(df_sim.iloc[i]["TotalOverdueMB"])
                    / max(float(graph_base["TotalOverdueMB"].max()), 0.001) * 28
                    for i in idxs
                ],
                color=TIER_HEX.get(tier, "#8A9BB0"),
                opacity=0.85,
                line=dict(color="white", width=1.5),
            ),
            text=[_short(df_sim.iloc[i]["CustomerName"]) for i in idxs],
            textposition="top center",
            textfont=dict(size=8, color="#2d3748"),
            hovertext=[
                f"<b>{df_sim.iloc[i]['CustomerName']}</b><br>"
                f"Tier         : {df_sim.iloc[i]['RiskTier']}<br>"
                f"Utilization  : {df_sim.iloc[i]['UtilizationPct']:.1f}%<br>"
                f"CurrentDebt  : {df_sim.iloc[i]['CurrentDebtMB']:.2f} MB<br>"
                f"TotalOverdue : {df_sim.iloc[i]['TotalOverdueMB']:.2f} MB<br>"
                f"Avg DPD      : {df_sim.iloc[i]['AvgDPD']:.0f} days<br>"
                f"Connections  : {sum(1 for e in edges_sim if i in (e[0],e[1]))}"
                for i in idxs
            ],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    fig_sim.update_layout(
        title=dict(
            text=(
                f"Customer Similarity Network — {sim_metric} "
                f"(threshold={sim_threshold:.2f}) | "
                f"Edges: {len(edges_sim)}"
            ),
            font=dict(size=12), x=0,
        ),
        height=580,
        plot_bgcolor="#f8fafc",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        legend=dict(orientation="h", y=1.05, x=0,
                    bgcolor="rgba(255,255,255,0.85)", bordercolor="#d0dae6", borderwidth=1),
        hoverlabel=dict(bgcolor="white", bordercolor="#d0dae6",
                        font=dict(size=11, color="#1B2A3B")),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(fig_sim, use_container_width=True, key="net11a")

    # Similarity matrix heatmap
    with st.expander("Similarity Matrix Heatmap", expanded=False):
        names_sim = [_short(r["CustomerName"], 16) for _, r in df_sim.iterrows()]
        if sim_metric == "Cosine Similarity":
            mat_display = sim_mat
            colorscale  = "Blues"
            ztitle      = "Cosine Similarity"
        else:
            mat_display = 1.0 - dist_mat / max(float(dist_mat.max()), 1e-9)
            colorscale  = "RdYlGn"
            ztitle      = "Similarity (1 - norm dist)"

        fig_heat = go.Figure(go.Heatmap(
            z=mat_display.tolist(),
            x=names_sim, y=names_sim,
            colorscale=colorscale,
            zmin=0, zmax=1,
            hovertemplate="X: %{x}<br>Y: %{y}<br>Score: %{z:.3f}<extra></extra>",
        ))
        fig_heat.update_layout(
            title=f"{ztitle} Matrix",
            height=480,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_heat, use_container_width=True, key="net11a_heat")


# ─────────────────────────────────────────────────────────────────────────────
# 11.B : Customer → Risk Bucket Network (Bipartite Plotly)
# Left  = Customer nodes
# Right = DPD Bucket nodes
# Edge  = Customer อยู่ใน bucket นั้น, weight = OverdueMB
# ─────────────────────────────────────────────────────────────────────────────
with tab11b:
    st.subheader("11.B — Customer → Risk Bucket Network")
    st.caption(
        "Bipartite: Customer (ซ้าย) → DPD Bucket (ขวา) | "
        "Edge weight = TotalOverdueMB | "
        "Node size = OverdueMB (Customer) / Total exposure (Bucket)"
    )

    cb1, cb2 = st.columns([2, 2])
    with cb1:
        bucket_top_n = st.slider(
            "Top N Customers (by TotalOverdueMB)",
            min_value=5, max_value=min(40, len(graph_base)),
            value=min(15, len(graph_base)), step=5,
            key="bucket_top_n",
        )
    with cb2:
        bucket_edge_col = st.selectbox(
            "Edge Weight Column",
            ["TotalOverdueMB", "CurrentDebtMB", "OverdueRatio"],
            key="bucket_edge_col",
        )

    df_bkt = (
        graph_base
        .sort_values("TotalOverdueMB", ascending=False)
        .head(bucket_top_n)
        .reset_index(drop=True)
        .copy()
    )

    # DPD Bucket assignment
    BUCKETS = ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
    BKT_COLOR = {
        "Current":    "#2A9D8F",
        "1-30 DPD":  "#3A7BD5",
        "31-60 DPD": "#E8A838",
        "61-90 DPD": "#B5620A",
        "90+ DPD":   "#A01F2D",
    }

    def _dpd_bucket(dpd):
        d = float(dpd) if not pd.isna(dpd) else 0.0
        if d <= 0:   return "Current"
        elif d <= 30: return "1-30 DPD"
        elif d <= 60: return "31-60 DPD"
        elif d <= 90: return "61-90 DPD"
        else:         return "90+ DPD"

    df_bkt["DPDBucket"] = df_bkt["AvgDPD"].apply(_dpd_bucket)

    # Layout — customers on left (x=0), buckets on right (x=1)
    n_custs   = len(df_bkt)
    n_buckets = len(BUCKETS)

    # Customer y-positions — evenly spaced
    cust_y = {
        i: 1.0 - i / max(n_custs - 1, 1)
        for i in range(n_custs)
    }
    # Bucket y-positions — evenly spaced
    bkt_y = {
        b: 1.0 - j / max(n_buckets - 1, 1)
        for j, b in enumerate(BUCKETS)
    }

    fig_bkt = go.Figure()

    # Edges
    edge_bx, edge_by = [], []
    edge_w_list = []
    for i, row in df_bkt.iterrows():
        bkt   = row["DPDBucket"]
        ew    = float(row.get(bucket_edge_col, 0))
        cy    = cust_y[i]
        by    = bkt_y[bkt]
        alpha = max(0.15, min(ew / max(float(df_bkt[bucket_edge_col].max()), 0.001), 0.90))
        col   = BKT_COLOR.get(bkt, "#aaaaaa")

        fig_bkt.add_trace(go.Scatter(
            x=[0.15, 0.85, None],
            y=[cy, by, None],
            mode="lines",
            line=dict(
                color=col,
                width=max(0.8, ew / max(float(df_bkt[bucket_edge_col].max()), 0.001) * 5),
            ),
            opacity=float(alpha),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Customer nodes (left)
    max_ov_b = float(df_bkt["TotalOverdueMB"].max()) or 1.0
    fig_bkt.add_trace(go.Scatter(
        x=[0.15] * n_custs,
        y=[cust_y[i] for i in range(n_custs)],
        mode="markers+text",
        name="Customer",
        marker=dict(
            size=[
                10 + float(df_bkt.iloc[i]["TotalOverdueMB"]) / max_ov_b * 28
                for i in range(n_custs)
            ],
            color=[TIER_HEX.get(df_bkt.iloc[i]["RiskTier"], "#8A9BB0")
                   for i in range(n_custs)],
            opacity=0.88,
            line=dict(color="white", width=1.5),
        ),
        text=[_short(df_bkt.iloc[i]["CustomerName"], 18) for i in range(n_custs)],
        textposition="middle left",
        textfont=dict(size=8, color="#2d3748"),
        hovertext=[
            f"<b>{df_bkt.iloc[i]['CustomerName']}</b><br>"
            f"DPD Bucket    : {df_bkt.iloc[i]['DPDBucket']}<br>"
            f"Risk Tier     : {df_bkt.iloc[i]['RiskTier']}<br>"
            f"TotalOverdue  : {df_bkt.iloc[i]['TotalOverdueMB']:.2f} MB<br>"
            f"CurrentDebt   : {df_bkt.iloc[i]['CurrentDebtMB']:.2f} MB<br>"
            f"Avg DPD       : {df_bkt.iloc[i]['AvgDPD']:.0f} days"
            for i in range(n_custs)
        ],
        hovertemplate="%{hovertext}<extra></extra>",
    ))

    # Bucket nodes (right)
    bkt_exposure = df_bkt.groupby("DPDBucket")["TotalOverdueMB"].sum()
    bkt_count    = df_bkt.groupby("DPDBucket")["Customer"].count()
    max_bkt_exp  = float(bkt_exposure.max()) if not bkt_exposure.empty else 1.0

    fig_bkt.add_trace(go.Scatter(
        x=[0.85] * n_buckets,
        y=[bkt_y[b] for b in BUCKETS],
        mode="markers+text",
        name="DPD Bucket",
        marker=dict(
            size=[
                14 + float(bkt_exposure.get(b, 0)) / max(max_bkt_exp, 0.001) * 34
                for b in BUCKETS
            ],
            color=[BKT_COLOR[b] for b in BUCKETS],
            symbol="diamond",
            opacity=0.90,
            line=dict(color="white", width=2),
        ),
        text=BUCKETS,
        textposition="middle right",
        textfont=dict(size=10, color="#2d3748", family="Inter, sans-serif"),
        hovertext=[
            f"<b>{b}</b><br>"
            f"Customers     : {int(bkt_count.get(b, 0))}<br>"
            f"Total Exposure: {float(bkt_exposure.get(b, 0)):.2f} MB"
            for b in BUCKETS
        ],
        hovertemplate="%{hovertext}<extra></extra>",
    ))

    fig_bkt.update_layout(
        title=dict(
            text=f"Customer → DPD Bucket Network | Weight: {bucket_edge_col}",
            font=dict(size=12), x=0,
        ),
        height=max(520, n_custs * 30 + 100),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   visible=False, range=[-0.2, 1.2]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        legend=dict(orientation="h", y=1.05, x=0,
                    bgcolor="rgba(255,255,255,0.85)", bordercolor="#d0dae6", borderwidth=1),
        hoverlabel=dict(bgcolor="white", bordercolor="#d0dae6",
                        font=dict(size=11, color="#1B2A3B")),
        margin=dict(l=120, r=120, t=60, b=20),
    )
    st.plotly_chart(fig_bkt, use_container_width=True, key="net11b")

    # Bucket Summary
    st.markdown("**Bucket Exposure Summary**")
    bkt_summary = (
        df_bkt.groupby("DPDBucket")
        .agg(
            Customers    = ("Customer",       "count"),
            TotalOverdue = ("TotalOverdueMB", "sum"),
            TotalDebt    = ("CurrentDebtMB",  "sum"),
            AvgDPD       = ("AvgDPD",         "mean"),
        )
        .reindex(BUCKETS, fill_value=0)
        .reset_index()
    )
    portfolio_total_b = float(bkt_summary["TotalOverdue"].sum())
    bkt_summary["Share %"] = (
        bkt_summary["TotalOverdue"]
        / max(portfolio_total_b, 0.001) * 100
    ).round(1)
    for _c in ["TotalOverdue", "TotalDebt", "AvgDPD"]:
        bkt_summary[_c] = bkt_summary[_c].round(2)
    st.dataframe(
        bkt_summary.rename(columns={
            "DPDBucket":   "Bucket",
            "Customers":   "# Customers",
            "TotalOverdue":"Overdue (MB)",
            "TotalDebt":   "Debt (MB)",
            "AvgDPD":      "Avg DPD",
            "Share %":     "Portfolio Share %",
        }),
        hide_index=True, use_container_width=True, height=220,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 11.C : Exposure Concentration Network
# Node size  = CurrentDebtMB
# Edge       = เชื่อมลูกค้าที่มี Debt / Overdue ใกล้กัน
# Cluster    = Large / Medium / Small Exposure
# ─────────────────────────────────────────────────────────────────────────────
with tab11c:
    st.subheader("11.C — Exposure Concentration Network")
    st.caption(
        "เชื่อมลูกค้าที่มี Debt หรือ Overdue ใกล้กัน → เห็น Concentration Cluster | "
        "Node size = CurrentDebtMB | Color = Exposure Tier"
    )

    cc1, cc2, cc3 = st.columns([1.5, 1.5, 1.5])
    with cc1:
        conc_edge_basis = st.selectbox(
            "Edge Connection Basis",
            ["CurrentDebtMB", "TotalOverdueMB"],
            key="conc_basis",
            help="เชื่อมลูกค้าที่มีค่านี้ใกล้กัน",
        )
    with cc2:
        conc_pct_thresh = st.slider(
            "Proximity Threshold (%)",
            min_value=5, max_value=50, value=25, step=5,
            key="conc_pct_thresh",
            help="เชื่อมถ้า |A - B| / max <= threshold%",
        )
    with cc3:
        conc_top_n = st.slider(
            "Top N Customers",
            min_value=5, max_value=min(40, len(graph_base)),
            value=min(20, len(graph_base)), step=5,
            key="conc_top_n",
        )

    df_conc = (
        graph_base
        .sort_values("CurrentDebtMB", ascending=False)
        .head(conc_top_n)
        .reset_index(drop=True)
        .copy()
    )

    # Exposure tier
    vals_c   = df_conc[conc_edge_basis].values
    p67, p33 = float(np.percentile(vals_c, 67)), float(np.percentile(vals_c, 33))
    def _exp_tier(v):
        if v >= p67:   return "Large"
        elif v >= p33: return "Medium"
        else:          return "Small"

    df_conc["ExposureTier"] = df_conc[conc_edge_basis].apply(_exp_tier)
    EXP_COLOR = {"Large": "#A01F2D", "Medium": "#B5620A", "Small": "#3A7BD5"}

    # Build edges — proximity
    max_val_c = float(df_conc[conc_edge_basis].max()) or 1.0
    thresh_c  = conc_pct_thresh / 100.0

    edges_conc = []
    for i in range(len(df_conc)):
        for j in range(i + 1, len(df_conc)):
            vi = float(df_conc.iloc[i][conc_edge_basis])
            vj = float(df_conc.iloc[j][conc_edge_basis])
            proximity = 1.0 - abs(vi - vj) / max_val_c
            if proximity >= (1.0 - thresh_c):
                edges_conc.append((i, j, proximity))

    # Layout — group by ExposureTier in circular clusters
    tier_groups = {"Large": [], "Medium": [], "Small": []}
    for i, row in df_conc.iterrows():
        tier_groups[row["ExposureTier"]].append(i)

    tier_centers = {
        "Large":  (-2.0, 0.5),
        "Medium": (0.0, -1.5),
        "Small":  (2.0,  0.5),
    }
    conc_pos_x, conc_pos_y = {}, {}
    for tier_c, idxs_c in tier_groups.items():
        cx_c, cy_c = tier_centers[tier_c]
        for k, idx in enumerate(idxs_c):
            angle = 2 * math.pi * k / max(len(idxs_c), 1)
            r_c   = 0.6 + (k % 3) * 0.3
            conc_pos_x[idx] = cx_c + r_c * math.cos(angle)
            conc_pos_y[idx] = cy_c + r_c * math.sin(angle)

    fig_conc = go.Figure()

    # Edges
    for (i, j, prox) in edges_conc:
        fig_conc.add_trace(go.Scatter(
            x=[conc_pos_x[i], conc_pos_x[j], None],
            y=[conc_pos_y[i], conc_pos_y[j], None],
            mode="lines",
            line=dict(color=f"rgba(150,150,150,{prox*0.5:.2f})", width=prox * 2.5),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Cluster label annotations
    for tier_c, (cx_c, cy_c) in tier_centers.items():
        n_in_tier = len(tier_groups[tier_c])
        exp_total = float(
            df_conc[df_conc["ExposureTier"] == tier_c][conc_edge_basis].sum()
        )
        fig_conc.add_annotation(
            x=cx_c, y=cy_c + 1.2,
            text=f"<b>{tier_c} Exposure</b><br>{n_in_tier} customers<br>{exp_total:.1f} MB",
            showarrow=False,
            font=dict(size=10, color=EXP_COLOR.get(tier_c, "#555")),
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor=EXP_COLOR.get(tier_c, "#aaa"),
            borderwidth=1,
            borderpad=4,
        )

    # Nodes
    max_debt_c = float(df_conc["CurrentDebtMB"].max()) or 1.0
    for tier_c in ["Large", "Medium", "Small"]:
        idxs_t = [i for i in range(len(df_conc))
                  if df_conc.iloc[i]["ExposureTier"] == tier_c]
        if not idxs_t:
            continue
        fig_conc.add_trace(go.Scatter(
            x=[conc_pos_x[i] for i in idxs_t],
            y=[conc_pos_y[i] for i in idxs_t],
            mode="markers+text",
            name=f"{tier_c} Exposure",
            marker=dict(
                size=[
                    12 + float(df_conc.iloc[i]["CurrentDebtMB"])
                    / max_debt_c * 32
                    for i in idxs_t
                ],
                color=EXP_COLOR[tier_c],
                opacity=0.85,
                line=dict(color="white", width=1.5),
            ),
            text=[_short(df_conc.iloc[i]["CustomerName"]) for i in idxs_t],
            textposition="top center",
            textfont=dict(size=8, color="#2d3748"),
            hovertext=[
                f"<b>{df_conc.iloc[i]['CustomerName']}</b><br>"
                f"Exposure Tier : {df_conc.iloc[i]['ExposureTier']}<br>"
                f"CurrentDebt   : {df_conc.iloc[i]['CurrentDebtMB']:.2f} MB<br>"
                f"TotalOverdue  : {df_conc.iloc[i]['TotalOverdueMB']:.2f} MB<br>"
                f"Utilization   : {df_conc.iloc[i]['UtilizationPct']:.1f}%<br>"
                f"Connections   : {sum(1 for e in edges_conc if i in (e[0],e[1]))}"
                for i in idxs_t
            ],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    portfolio_conc_c = float(df_conc[conc_edge_basis].sum())
    large_share = float(
        df_conc[df_conc["ExposureTier"] == "Large"][conc_edge_basis].sum()
    ) / max(portfolio_conc_c, 0.001) * 100

    fig_conc.update_layout(
        title=dict(
            text=(
                f"Exposure Concentration Network | Basis: {conc_edge_basis} | "
                f"Proximity: {conc_pct_thresh}% | Edges: {len(edges_conc)} | "
                f"Large cluster = {large_share:.1f}% of portfolio"
            ),
            font=dict(size=11), x=0,
        ),
        height=580,
        plot_bgcolor="#f8fafc",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        legend=dict(orientation="h", y=1.05, x=0,
                    bgcolor="rgba(255,255,255,0.85)", bordercolor="#d0dae6", borderwidth=1),
        hoverlabel=dict(bgcolor="white", bordercolor="#d0dae6",
                        font=dict(size=11, color="#1B2A3B")),
        margin=dict(l=20, r=20, t=70, b=20),
    )
    st.plotly_chart(fig_conc, use_container_width=True, key="net11c")


# ─────────────────────────────────────────────────────────────────────────────
# 11.D : Credit Risk Propagation + Community Detection
# RiskScore = 0.4*Util + 0.3*DPD_norm + 0.3*OverdueRatio_norm
# Edge      = |RiskScore_i - RiskScore_j| <= threshold
# Community = Louvain vs Leiden (เปรียบเทียบ)
# ─────────────────────────────────────────────────────────────────────────────
with tab11d:
    st.subheader("11.D — Credit Risk Propagation + Community Detection")
    st.caption(
        "RiskScore = 0.4×Util + 0.3×DPD_norm + 0.3×OverdueRatio_norm | "
        "Edge = |RiskScore_i − RiskScore_j| ≤ threshold | "
        "Community = Louvain vs Leiden"
    )

    cd1, cd2, cd3 = st.columns([1.5, 1.5, 1.5])
    with cd1:
        prop_top_n = st.slider(
            "Top N Customers",
            min_value=5, max_value=min(40, len(graph_base)),
            value=min(20, len(graph_base)), step=5,
            key="prop_top_n",
        )
    with cd2:
        prop_thresh = st.slider(
            "Edge Threshold (RiskScore diff)",
            min_value=0.05, max_value=0.50, value=0.20, step=0.05,
            key="prop_thresh",
            help="เชื่อมถ้า |score_i - score_j| <= threshold",
        )
    with cd3:
        prop_algo = st.selectbox(
            "Community Algorithm",
            ["Louvain", "Leiden", "Both (Compare)"],
            key="prop_algo",
        )

    df_prop = (
        graph_base
        .sort_values("TotalOverdueMB", ascending=False)
        .head(prop_top_n)
        .reset_index(drop=True)
        .copy()
    )

    # Normalize features → [0,1]
    def _norm_series(s):
        mn, mx = float(s.min()), float(s.max())
        return (s - mn) / max(mx - mn, 1e-9)

    df_prop["_util_n"] = _norm_series(df_prop["UtilizationPct"])
    df_prop["_dpd_n"]  = _norm_series(df_prop["AvgDPD"])
    df_prop["_ovr_n"]  = _norm_series(df_prop["OverdueRatio"])

    df_prop["RiskScore"] = (
        0.4 * df_prop["_util_n"]
        + 0.3 * df_prop["_dpd_n"]
        + 0.3 * df_prop["_ovr_n"]
    ).clip(0.0, 1.0)

    def _risk_level(score):
        if score >= 0.70:   return "High Risk"
        elif score >= 0.40: return "Medium Risk"
        else:               return "Low Risk"

    df_prop["RiskLevel"] = df_prop["RiskScore"].apply(_risk_level)
    RISK_LEVEL_COLOR = {
        "High Risk":   "#A01F2D",
        "Medium Risk": "#B5620A",
        "Low Risk":    "#2A9D8F",
    }

    # Build adjacency for community detection
    n_prop = len(df_prop)
    scores = df_prop["RiskScore"].values

    edges_prop = []
    adj = {i: [] for i in range(n_prop)}
    for i in range(n_prop):
        for j in range(i + 1, n_prop):
            diff = abs(scores[i] - scores[j])
            if diff <= prop_thresh:
                w = float(1.0 - diff / prop_thresh)
                edges_prop.append((i, j, w))
                adj[i].append(j)
                adj[j].append(i)

    # ------------------------------------------------------------------
    # Community Detection — Louvain (manual greedy implementation)
    # ใช้ networkx ถ้ามี, fallback greedy partition
    # ------------------------------------------------------------------
    def _louvain_community(adj_dict, n):
        """Greedy modularity-based community — lightweight version"""
        try:
            import networkx as nx
            import community as community_louvain
            G = nx.Graph()
            G.add_nodes_from(range(n))
            for i in range(n):
                for j in adj_dict[i]:
                    if i < j:
                        G.add_edge(i, j)
            partition = community_louvain.best_partition(G)
            return [partition.get(i, 0) for i in range(n)]
        except ImportError:
            pass
        try:
            import networkx as nx
            from networkx.algorithms.community import greedy_modularity_communities
            G = nx.Graph()
            G.add_nodes_from(range(n))
            for i in range(n):
                for j in adj_dict[i]:
                    if i < j:
                        G.add_edge(i, j)
            comms = list(greedy_modularity_communities(G))
            labels = [0] * n
            for cid, comm in enumerate(comms):
                for node in comm:
                    labels[node] = cid
            return labels
        except Exception:
            pass
        # Final fallback — RiskScore quantile
        q33 = float(np.percentile(scores, 33))
        q67 = float(np.percentile(scores, 67))
        return [
            0 if scores[i] < q33 else (1 if scores[i] < q67 else 2)
            for i in range(n)
        ]

    def _leiden_community(adj_dict, n):
        """Leiden community — ใช้ leidenalg ถ้ามี, fallback bisection"""
        try:
            import igraph as ig
            import leidenalg
            G = ig.Graph(n=n)
            edge_list = [
                (i, j)
                for i in range(n)
                for j in adj_dict[i]
                if i < j
            ]
            G.add_edges(edge_list)
            part = leidenalg.find_partition(G, leidenalg.ModularityVertexPartition)
            labels = [0] * n
            for cid, comm in enumerate(part):
                for node in comm:
                    labels[node] = cid
            return labels
        except ImportError:
            pass
        # Fallback — RiskScore split (slightly different from Louvain fallback)
        med = float(np.median(scores))
        return [
            0 if scores[i] < med * 0.7
            else (1 if scores[i] < med * 1.3 else 2)
            for i in range(n)
        ]

    louvain_labels = _louvain_community(adj, n_prop)
    leiden_labels  = _leiden_community(adj, n_prop)

    df_prop["Community_Louvain"] = louvain_labels
    df_prop["Community_Leiden"]  = leiden_labels

    # Choose which label to display
    display_algo = prop_algo if prop_algo != "Both (Compare)" else "Louvain"
    comm_col     = f"Community_{display_algo}"

    # Color palette for communities
    COMM_COLORS = [
        "#1B4F8A","#A01F2D","#2A9D8F","#B5620A",
        "#5C3D8F","#1A7A4A","#3D5166","#8A9BB0",
    ]

    def _comm_color(cid):
        return COMM_COLORS[int(cid) % len(COMM_COLORS)]

    # Layout — RiskScore on X axis, spread Y
    prop_pos_x = scores.tolist()
    rng = {}
    for i in range(n_prop):
        c = louvain_labels[i]
        rng.setdefault(c, [])
        rng[c].append(i)
    prop_pos_y = [0.0] * n_prop
    for c, idxs_c in rng.items():
        for k, idx in enumerate(idxs_c):
            prop_pos_y[idx] = (k - len(idxs_c) / 2) * 0.25

    # Figure
    def _draw_prop_network(comm_labels, title_suffix, key_suffix):
        fig_p = go.Figure()

        # Edges
        for (i, j, w) in edges_prop:
            fig_p.add_trace(go.Scatter(
                x=[prop_pos_x[i], prop_pos_x[j], None],
                y=[prop_pos_y[i], prop_pos_y[j], None],
                mode="lines",
                line=dict(color=f"rgba(150,150,150,{w*0.4:.2f})", width=w * 2),
                hoverinfo="skip",
                showlegend=False,
            ))

        # Nodes — colored by community
        unique_comms = sorted(set(comm_labels))
        for cid in unique_comms:
            idxs_c = [i for i in range(n_prop) if comm_labels[i] == cid]
            col    = _comm_color(cid)
            fig_p.add_trace(go.Scatter(
                x=[prop_pos_x[i] for i in idxs_c],
                y=[prop_pos_y[i] for i in idxs_c],
                mode="markers+text",
                name=f"Community {cid}",
                marker=dict(
                    size=[
                        10 + float(df_prop.iloc[i]["CurrentDebtMB"])
                        / max(float(df_prop["CurrentDebtMB"].max()), 0.001) * 28
                        for i in idxs_c
                    ],
                    color=col,
                    opacity=0.88,
                    line=dict(color="white", width=1.5),
                    # Border thickness = RiskScore
                    # (visualize risk intensity)
                ),
                text=[_short(df_prop.iloc[i]["CustomerName"]) for i in idxs_c],
                textposition="top center",
                textfont=dict(size=8, color="#2d3748"),
                hovertext=[
                    f"<b>{df_prop.iloc[i]['CustomerName']}</b><br>"
                    f"RiskScore    : {df_prop.iloc[i]['RiskScore']:.3f}<br>"
                    f"RiskLevel    : {df_prop.iloc[i]['RiskLevel']}<br>"
                    f"Community    : {comm_labels[i]}<br>"
                    f"Utilization  : {df_prop.iloc[i]['UtilizationPct']:.1f}%<br>"
                    f"Avg DPD      : {df_prop.iloc[i]['AvgDPD']:.0f} days<br>"
                    f"OverdueRatio : {df_prop.iloc[i]['OverdueRatio']:.1f}%<br>"
                    f"CurrentDebt  : {df_prop.iloc[i]['CurrentDebtMB']:.2f} MB"
                    for i in idxs_c
                ],
                hovertemplate="%{hovertext}<extra></extra>",
            ))

        # RiskScore zones
        fig_p.add_vrect(x0=0.0, x1=0.40, fillcolor="#2A9D8F",
                        opacity=0.04, line_width=0)
        fig_p.add_vrect(x0=0.40, x1=0.70, fillcolor="#E8A838",
                        opacity=0.04, line_width=0)
        fig_p.add_vrect(x0=0.70, x1=1.00, fillcolor="#A01F2D",
                        opacity=0.04, line_width=0)
        for x_ref, lbl, clr in [
            (0.20, "Low Risk",    "#2A9D8F"),
            (0.55, "Medium Risk", "#B5620A"),
            (0.85, "High Risk",   "#A01F2D"),
        ]:
            fig_p.add_annotation(
                x=x_ref, y=float(max(prop_pos_y)) + 0.35,
                text=f"<b>{lbl}</b>",
                showarrow=False,
                font=dict(size=10, color=clr),
                bgcolor="rgba(255,255,255,0.7)",
            )

        fig_p.update_layout(
            title=dict(
                text=(
                    f"Credit Risk Propagation — {title_suffix} | "
                    f"Edges: {len(edges_prop)} | "
                    f"Communities: {len(unique_comms)}"
                ),
                font=dict(size=11), x=0,
            ),
            height=520,
            plot_bgcolor="#f8fafc",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                title="Risk Score (0=Low, 1=High)",
                showgrid=True, gridcolor="rgba(200,210,220,0.4)",
                zeroline=False, range=[-0.05, 1.05],
                tickformat=".2f",
            ),
            yaxis=dict(showgrid=False, zeroline=False,
                       showticklabels=False, visible=False),
            legend=dict(orientation="h", y=1.05, x=0,
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="#d0dae6", borderwidth=1,
                        font=dict(size=9)),
            hoverlabel=dict(bgcolor="white", bordercolor="#d0dae6",
                            font=dict(size=11, color="#1B2A3B")),
            margin=dict(l=20, r=20, t=70, b=40),
        )
        return fig_p

    if prop_algo == "Both (Compare)":
        col_lo, col_le = st.columns(2, gap="medium")
        with col_lo:
            st.markdown("**Louvain Community**")
            st.plotly_chart(
                _draw_prop_network(louvain_labels, "Louvain", "lo"),
                use_container_width=True, key="net11d_louvain",
            )
        with col_le:
            st.markdown("**Leiden Community**")
            st.plotly_chart(
                _draw_prop_network(leiden_labels, "Leiden", "le"),
                use_container_width=True, key="net11d_leiden",
            )
        # Agreement rate
        agree = sum(
            1 for i in range(n_prop)
            if louvain_labels[i] == leiden_labels[i]
        )
        st.info(
            f"Community Agreement: {agree}/{n_prop} nodes "
            f"({agree/max(n_prop,1)*100:.1f}%) assigned to same community ID "
            f"by both algorithms"
        )
    else:
        st.plotly_chart(
            _draw_prop_network(
                louvain_labels if prop_algo == "Louvain" else leiden_labels,
                prop_algo, prop_algo.lower()
            ),
            use_container_width=True, key="net11d_single",
        )

    # RiskScore distribution table
    with st.expander("RiskScore Detail Table", expanded=False):
        tbl_prop = df_prop[[
            "CustomerName", "RiskScore", "RiskLevel",
            "Community_Louvain", "Community_Leiden",
            "UtilizationPct", "AvgDPD", "OverdueRatio", "CurrentDebtMB",
        ]].sort_values("RiskScore", ascending=False).copy()
        for _c in ["RiskScore", "UtilizationPct", "AvgDPD", "OverdueRatio", "CurrentDebtMB"]:
            tbl_prop[_c] = tbl_prop[_c].round(3)
        st.dataframe(tbl_prop, hide_index=True, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 11.E : Bipartite Network — ECharts Graph Series
# Node type 1 : Customer  (circle)
# Node type 2 : Risk Level (Low / Medium / High / Critical)
# Edge weight : CurrentDebtMB หรือ TotalOverdueMB
# Layout      : Force-directed (ECharts built-in)
# ─────────────────────────────────────────────────────────────────────────────
with tab11e:
    st.subheader("11.E — Bipartite Network (ECharts) — Executive View")
    st.caption(
        "Node สองประเภท: Customer (circle) และ Risk Level (diamond) | "
        "Edge weight = CurrentDebtMB หรือ TotalOverdueMB | "
        "ผู้บริหารมองแว๊บเดียวรู้ว่ากลุ่ม Critical มีใครบ้าง และมูลหนี้รวมเท่าไร"
    )

    if not ECHARTS_OK:
        st.error(
            "ต้องติดตั้ง streamlit-echarts ก่อน:\n\n"
            "```\npip install streamlit-echarts\n```"
        )
        st.stop()

    ce1, ce2, ce3 = st.columns([1.5, 1.5, 1.5])
    with ce1:
        bip_top_n = st.slider(
            "Top N Customers",
            min_value=5, max_value=min(50, len(graph_base)),
            value=min(25, len(graph_base)), step=5,
            key="bip_top_n",
        )
    with ce2:
        bip_edge_col = st.selectbox(
            "Edge Weight",
            ["CurrentDebtMB", "TotalOverdueMB"],
            key="bip_edge_col",
        )
    with ce3:
        bip_layout = st.selectbox(
            "Graph Layout",
            ["force", "circular"],
            key="bip_layout",
            help="force = force-directed (แนะนำ) | circular = วงกลม",
        )

    df_bip = (
        graph_base
        .sort_values("TotalOverdueMB", ascending=False)
        .head(bip_top_n)
        .reset_index(drop=True)
        .copy()
    )

    # Risk Level assignment (4 levels)
    def _risk_level_4(util, dpd, overdue_ratio):
        u = float(util)
        d = float(dpd)
        o = float(overdue_ratio)
        score = 0.4 * min(u / 100, 1.0) + 0.3 * min(d / 180, 1.0) + 0.3 * min(o / 100, 1.0)
        if score >= 0.70:   return "Critical"
        elif score >= 0.45: return "High"
        elif score >= 0.20: return "Medium"
        else:               return "Low"

    df_bip["RiskLevel4"] = df_bip.apply(
        lambda r: _risk_level_4(
            r["UtilizationPct"], r["AvgDPD"], r["OverdueRatio"]
        ), axis=1
    )

    RISK4_COLOR = {
        "Critical": "#A01F2D",
        "High":     "#B5620A",
        "Medium":   "#E8A838",
        "Low":      "#2A9D8F",
    }
    RISK4_ORDER = ["Critical", "High", "Medium", "Low"]

    # ------------------------------------------------------------------
    # Build ECharts nodes & edges
    # ------------------------------------------------------------------
    ec_nodes = []
    ec_edges = []

    max_edge_val = float(df_bip[bip_edge_col].max()) or 1.0

    # Risk Level hub nodes
    for lvl in RISK4_ORDER:
        lvl_df    = df_bip[df_bip["RiskLevel4"] == lvl]
        lvl_total = float(lvl_df[bip_edge_col].sum())
        lvl_count = int(len(lvl_df))
        if lvl_count == 0:
            continue

        ec_nodes.append({
            "id":         f"risk_{lvl}",
            "name":       lvl,
            "symbolSize": 48 + lvl_count * 4,
            "symbol":     "diamond",
            "itemStyle":  {"color": RISK4_COLOR[lvl], "borderColor": "#fff", "borderWidth": 3},
            "label": {
                "show":       True,
                "fontSize":   13,
                "fontWeight": "bold",
                "color":      "#ffffff",
                "formatter":  (
                    f"{lvl}\n"
                    f"{lvl_count} customers\n"
                    f"{lvl_total:.1f} MB"
                ),
            },
            "tooltip": {
                "formatter": (
                    f"<b>Risk Level: {lvl}</b><br>"
                    f"Customers: {lvl_count}<br>"
                    f"Total {bip_edge_col}: {lvl_total:.2f} MB"
                )
            },
            "_type":      "hub",
            "_level":     lvl,
        })

    # Customer nodes
    for _, row in df_bip.iterrows():
        cid       = int(row["Customer"])
        cname     = str(row["CustomerName"])
        lvl       = row["RiskLevel4"]
        edge_val  = float(row.get(bip_edge_col, 0))
        node_size = 12 + edge_val / max_edge_val * 32

        ec_nodes.append({
            "id":         f"cust_{cid}",
            "name":       _short(cname, 18),
            "symbolSize": float(node_size),
            "symbol":     "circle",
            "itemStyle":  {
                "color":       RISK4_COLOR.get(lvl, "#8A9BB0"),
                "opacity":     0.88,
                "borderColor": "#ffffff",
                "borderWidth": 1.5,
            },
            "label": {
                "show":     True,
                "fontSize": 9,
                "color":    "#2d3748",
            },
            "tooltip": {
                "formatter": (
                    f"<b>{cname}</b><br>"
                    f"Risk Level    : {lvl}<br>"
                    f"Utilization   : {row['UtilizationPct']:.1f}%<br>"
                    f"CurrentDebt   : {row['CurrentDebtMB']:.2f} MB<br>"
                    f"TotalOverdue  : {row['TotalOverdueMB']:.2f} MB<br>"
                    f"Avg DPD       : {row['AvgDPD']:.0f} days<br>"
                    f"OverdueRatio  : {row['OverdueRatio']:.1f}%"
                )
            },
            "_type":  "customer",
            "_level": lvl,
        })

        # Edge: Customer → Risk Level hub
        ec_edges.append({
            "source":    f"cust_{cid}",
            "target":    f"risk_{lvl}",
            "value":     float(edge_val),
            "lineStyle": {
                "width":   max(0.5, edge_val / max_edge_val * 5),
                "color":   RISK4_COLOR.get(lvl, "#aaaaaa"),
                "opacity": max(0.15, min(edge_val / max_edge_val * 0.80, 0.75)),
                "curveness": 0.2,
            },
            "tooltip": {
                "formatter": (
                    f"<b>{_short(cname)}</b> → <b>{lvl}</b><br>"
                    f"{bip_edge_col}: {edge_val:.2f} MB"
                )
            },
        })

    # ------------------------------------------------------------------
    # ECharts option
    # ------------------------------------------------------------------
    force_opt = {
        "repulsion":     [800, 1200],
        "gravity":       0.08,
        "edgeLength":    [80, 200],
        "friction":      0.6,
        "layoutAnimation": True,
    } if bip_layout == "force" else {}

    ec_option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "show":      True,
            "trigger":   "item",
            "formatter": "{b}",
        },
        "legend": [{
            "data": [
                {"name": lvl, "itemStyle": {"color": RISK4_COLOR[lvl]}}
                for lvl in RISK4_ORDER
                if any(n["_level"] == lvl for n in ec_nodes if n["_type"] == "hub")
            ],
            "top":        "bottom",
            "orient":     "horizontal",
            "textStyle":  {"fontSize": 11, "color": "#1B2A3B"},
            "itemWidth":  18,
            "itemHeight": 12,
        }],
        "animationDuration":    1200,
        "animationEasingUpdate":"quinticInOut",
        "series": [{
            "type":              "graph",
            "layout":            bip_layout,
            "force":             force_opt,
            "data":              ec_nodes,
            "edges":             ec_edges,
            "roam":              True,
            "draggable":         True,
            "focusNodeAdjacency":True,
            "symbolSize":        20,
            "label": {
                "show":     True,
                "position": "right",
                "fontSize": 9,
                "color":    "#2d3748",
            },
            "edgeSymbol":      ["none", "arrow"],
            "edgeSymbolSize":  [0, 8],
            "lineStyle": {
                "opacity": 0.5,
                "width":   1.5,
                "curveness": 0.2,
            },
            "emphasis": {
                "focus":    "adjacency",
                "label":    {"fontSize": 11, "fontWeight": "bold"},
                "lineStyle":{"width": 4},
            },
            "categories": [
                {"name": lvl, "itemStyle": {"color": RISK4_COLOR[lvl]}}
                for lvl in RISK4_ORDER
            ],
        }],
    }

    st_echarts(options=ec_option, height="620px", key="net11e_echarts")

    # ------------------------------------------------------------------
    # KPI Summary strip
    # ------------------------------------------------------------------
    st.markdown("**Risk Level Summary**")
    kpi_cols = st.columns(4)
    for col_ui, lvl in zip(kpi_cols, RISK4_ORDER):
        lvl_df    = df_bip[df_bip["RiskLevel4"] == lvl]
        lvl_count = int(len(lvl_df))
        lvl_total = float(lvl_df[bip_edge_col].sum())
        lvl_share = lvl_total / max(float(df_bip[bip_edge_col].sum()), 0.001) * 100
        col_ui.metric(
            label=f"{lvl} Risk",
            value=f"{lvl_count} customers",
            delta=f"{lvl_total:.1f} MB ({lvl_share:.1f}%)",
            delta_color="inverse" if lvl in ["Critical", "High"] else "off",
        )

    # ------------------------------------------------------------------
    # Customer detail table per Risk Level
    # ------------------------------------------------------------------
    with st.expander("Customer Detail by Risk Level", expanded=False):
        for lvl in RISK4_ORDER:
            lvl_df = df_bip[df_bip["RiskLevel4"] == lvl].copy()
            if lvl_df.empty:
                continue
            st.markdown(
                f"<span style='color:{RISK4_COLOR[lvl]};font-weight:700;'>"
                f"{lvl} — {len(lvl_df)} customers</span>",
                unsafe_allow_html=True,
            )
            show_cols = [c for c in [
                "CustomerName", "UtilizationPct", "CurrentDebtMB",
                "TotalOverdueMB", "AvgDPD", "OverdueRatio", "TYPE",
            ] if c in lvl_df.columns]
            tbl_lvl = lvl_df[show_cols].sort_values(
                bip_edge_col if bip_edge_col in show_cols else show_cols[0],
                ascending=False,
            ).copy()
            for _c in ["UtilizationPct", "CurrentDebtMB", "TotalOverdueMB",
                       "AvgDPD", "OverdueRatio"]:
                if _c in tbl_lvl.columns:
                    tbl_lvl[_c] = tbl_lvl[_c].round(2)
            st.dataframe(tbl_lvl, hide_index=True, use_container_width=True, height=180)




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