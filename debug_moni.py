# debug_moni.py
# streamlit run debug_moni.py
# Independent file — ไม่พึ่ง app.py หรือ views ใดๆ
# อัปโหลด 2 ไฟล์: Availability Excel + Overdue Excel
# ตรวจสอบการ map OverDue Year กับ Avail Year ว่าถูกต้องหรือเปล่า

import streamlit as st
import pandas as pd
import numpy as np
import datetime

st.set_page_config(page_title="Debug — OverDue Year Mapping", layout="wide")
st.title("Debug: OverDue Year Mapping Verification")

MONTH_MAP = {
    1: "Jan", 2: "Feb",  3: "Mar",  4: "Apr",
    5: "May", 6: "Jun",  7: "Jul",  8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

DPD_HIGH = 60
DPD_MED  = 30


# =============================================================================
# ET Pipeline — inlined (ไม่ import จาก et_pipeline.py)
# =============================================================================
def _transform_availability(df: pd.DataFrame, sheet_name: str):
    new_cols = []
    debt_count = 0
    prev_clean_col = ""

    for col in df.columns:
        c_clean = str(col).strip()
        c_upper = c_clean.upper()

        if "CUSTOMER CODE" in c_upper:
            clean_name = "CUSTOMER_CODE"
        elif "CUSTOMER NAME" in c_upper:
            clean_name = "CUSTOMER_NAME"
        elif c_upper == "TYPE" or "TYPECLEAN" in c_upper:
            clean_name = "TYPE"
        elif "CLEAN CREDIT" in c_upper:
            clean_name = "CLEAN_CREDIT_MB"
        elif "CURRENT DEBT" in c_upper and "MILLION BAHT" in c_upper:
            if debt_count == 0:
                clean_name = "CURRENT_DEBT_MILLION_THB"
                debt_count += 1
            else:
                clean_name = "CURRENT_DEBT_MILLION_THB_PERCENT"
        elif "EST" in c_upper and "FURTHER" in c_upper:
            clean_name = "EST_FURTHER_AMOUNT"
        elif "EST" in c_upper and "DEBT" in c_upper:
            clean_name = "EST_DEBT"
        elif c_upper == "DATE":
            clean_name = "DATE"
        else:
            clean_name = c_clean.replace(" ", "_").replace(".", "").upper()

        new_cols.append(clean_name)
        if "PRICE" not in clean_name:
            prev_clean_col = clean_name

    df.columns = new_cols

    drop_mask = pd.Series(False, index=df.index)
    if "CUSTOMER_CODE" in df.columns:
        drop_mask |= df["CUSTOMER_CODE"].astype(str).str.strip().str.lower().str.contains(
            "customer code", na=False
        )
    if "CUSTOMER_NAME" in df.columns:
        drop_mask |= df["CUSTOMER_NAME"].astype(str).str.strip().str.lower().str.contains(
            "customer name", na=False
        )
    df = df[~drop_mask]

    if "CUSTOMER_CODE" in df.columns:
        code_series = df["CUSTOMER_CODE"].astype(str).str.strip().str.lower()
        df = df[~code_series.isin(["none", "nan", "", " "])]
        df = df.dropna(subset=["CUSTOMER_CODE"])

    float_cols = [
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_FURTHER_AMOUNT",
        "EST_DEBT", "ESTIMATE_AMOUNT",
    ]
    for c in float_cols:
        if c in df.columns:
            df[c] = df[c].replace(["-", "#DIV/0!", "#N/A", " - ", "None"], np.nan)
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "CUSTOMER_CODE" in df.columns:
        df["CUSTOMER_CODE"] = (
            pd.to_numeric(df["CUSTOMER_CODE"], errors="coerce").fillna(0).astype(int)
        )
    if "CUSTOMER_NAME" in df.columns:
        df["CUSTOMER_NAME"] = df["CUSTOMER_NAME"].astype(str).replace("nan", "")

    if "DATE" in df.columns:
        df["DATE"] = df["DATE"].ffill()

        def _parse_date(val):
            if pd.isna(val) or str(val).strip().lower() in ["none", "nan", "", "nat"]:
                return np.nan
            try:
                ts = pd.to_datetime(val)
                y, m, d = ts.year, ts.month, ts.day
                if str(sheet_name).strip() in ["2023", "2024"]:
                    return datetime.date(y, m, d)
                else:
                    if d <= 12:
                        return datetime.date(y, d, m)
                    else:
                        return datetime.date(y, m, d)
            except Exception:
                return np.nan

        df["DATE"] = df["DATE"].apply(_parse_date)

    has_pct = "CURRENT_DEBT_MILLION_THB_PERCENT" in df.columns
    needs_fallback = (
        not has_pct
        or df["CURRENT_DEBT_MILLION_THB_PERCENT"].fillna(0).eq(0).all()
    )
    if needs_fallback and "CURRENT_DEBT_MILLION_THB" in df.columns and "CLEAN_CREDIT_MB" in df.columns:
        df["CURRENT_DEBT_MILLION_THB_PERCENT"] = (
            df["CURRENT_DEBT_MILLION_THB"] / df["CLEAN_CREDIT_MB"].replace(0, np.nan)
        ).fillna(0.0).clip(upper=10.0)

    df.insert(0, "SOURCE_SHEET", sheet_name)
    return df


def _clean_overdue(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).replace("'", "").strip() for c in df.columns]

    for col in ("OriginalDueDate", "CollectionDate"):
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col].astype(str).str.strip().replace({"nan": None, "": None}),
                format="%Y%m%d",
                errors="coerce",
            )

    for col in ("OverdueAmount", "InvoiceAmount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "CompanyCode" in df.columns:
        df["CompanyCode"] = df["CompanyCode"].astype(str).str.strip()
    if "Customer" in df.columns:
        df["Customer"] = pd.to_numeric(df["Customer"], errors="coerce").fillna(0).astype(int)

    df["IsOverdue"]    = df["OverdueAmount"] > 0
    df["IsCreditNote"] = df["OverdueAmount"] < 0
    df["OverdueAbs"]   = df["OverdueAmount"].clip(lower=0)
    df["IsPaid"]       = df["CollectionDate"].notna() if "CollectionDate" in df.columns else False

    today = pd.Timestamp("today").normalize()
    if "OriginalDueDate" in df.columns:
        df["DPD"] = np.where(
            df["IsPaid"], 0,
            np.where(
                df["OriginalDueDate"].notna(),
                (today - df["OriginalDueDate"]).dt.days.clip(lower=0),
                np.nan,
            ),
        )
        df["DueYear"]       = df["OriginalDueDate"].dt.year.astype("Int64")
        df["DueMonth"]      = df["OriginalDueDate"].dt.month.astype("Int64")
        df["DueQuarter"]    = df["OriginalDueDate"].dt.quarter.astype("Int64")
        df["DueMonthLabel"] = df["DueMonth"].map(MONTH_MAP)

    if "CollectionDate" in df.columns and "OriginalDueDate" in df.columns:
        is_inv = df["OverdueAmount"] > 0
        df["PaidLate"]     = is_inv & df["CollectionDate"].notna() & (df["CollectionDate"] > df["OriginalDueDate"])
        df["PaidOnTime"]   = is_inv & df["CollectionDate"].notna() & ~df["PaidLate"]
        df["NotCollected"] = is_inv & df["CollectionDate"].isna()
    else:
        df["PaidLate"] = df["PaidOnTime"] = df["NotCollected"] = False

    return df


def _build_joined(df_avail: pd.DataFrame, df_overdue: pd.DataFrame) -> pd.DataFrame:
    if df_avail.empty or df_overdue.empty:
        return df_overdue.copy()

    if "DATE" in df_avail.columns:
        snap = df_avail.sort_values("DATE", ascending=False).drop_duplicates(subset=["CUSTOMER_CODE"])
    else:
        snap = df_avail.drop_duplicates(subset=["CUSTOMER_CODE"])

    avail_cols = [
        "CUSTOMER_CODE", "CUSTOMER_NAME", "TYPE",
        "CLEAN_CREDIT_MB", "CURRENT_DEBT_MILLION_THB",
        "CURRENT_DEBT_MILLION_THB_PERCENT", "EST_DEBT", "SOURCE_SHEET",
    ]
    keep = [c for c in avail_cols if c in snap.columns]
    snap = snap[keep].copy()
    snap = snap.rename(columns={
        "CUSTOMER_NAME":  "AVAIL_CUSTOMER_NAME",
        "SOURCE_SHEET":   "AVAIL_YEAR",
    })

    joined = df_overdue.merge(snap, left_on="Customer", right_on="CUSTOMER_CODE", how="left")

    if "CURRENT_DEBT_MILLION_THB_PERCENT" in joined.columns:
        joined["UtilizationPct"] = joined["CURRENT_DEBT_MILLION_THB_PERCENT"].fillna(0.0) * 100
    else:
        joined["UtilizationPct"] = np.nan

    def _tier(row):
        util = row.get("UtilizationPct", np.nan)
        dpd  = row.get("DPD", 0) or 0
        if pd.isna(util):
            return "Unknown"
        if util >= 80 and dpd >= DPD_HIGH:
            return "Critical"
        elif util >= 80 or dpd >= DPD_HIGH:
            return "High Risk"
        elif util >= 50 or dpd >= DPD_MED:
            return "Watch"
        return "Healthy"

    joined["RiskTier"] = joined.apply(_tier, axis=1)
    return joined


# =============================================================================
# UI
# =============================================================================
st.markdown("---")
st.subheader("Step 1 — Upload Files")

col_a, col_b = st.columns(2)
with col_a:
    avail_file = st.file_uploader("Availability Excel (.xlsx)", type=["xlsx"], key="dbg_avail")
with col_b:
    overdue_file = st.file_uploader("Overdue Excel (.xlsx)", type=["xlsx"], key="dbg_overdue")

if not avail_file or not overdue_file:
    st.info("Please upload both files to start debugging.")
    st.stop()

# --- Process Avail ---
xls = pd.ExcelFile(avail_file)
sheet_names = xls.sheet_names
st.markdown(f"**Avail sheets found:** `{sheet_names}`")

avail_frames = []
for sheet in sheet_names:
    try:
        df_raw = pd.read_excel(xls, sheet_name=sheet)
        df_clean = _transform_availability(df_raw.copy(), sheet_name=sheet)
        avail_frames.append(df_clean)
    except Exception as e:
        st.warning(f"Sheet `{sheet}` failed: {e}")

if not avail_frames:
    st.error("No valid Availability sheets processed.")
    st.stop()

df_avail = pd.concat(avail_frames, ignore_index=True)
df_avail["AVAIL_YEAR"] = df_avail["SOURCE_SHEET"].astype(str).str.strip()

# --- Process Overdue ---
df_overdue_raw = pd.read_excel(overdue_file)
df_overdue = _clean_overdue(df_overdue_raw.copy())

# --- Build Joined ---
df_joined = _build_joined(df_avail.copy(), df_overdue.copy())

st.markdown("---")
st.subheader("Step 2 — Raw Data Overview")

t1, t2, t3 = st.tabs(["df_avail", "df_overdue", "df_joined"])

with t1:
    st.markdown(f"Shape: `{df_avail.shape}` | Columns: `{list(df_avail.columns)}`")
    st.markdown(f"AVAIL_YEAR unique: `{sorted(df_avail['AVAIL_YEAR'].dropna().unique().tolist())}`")
    st.dataframe(df_avail.head(100), use_container_width=True, height=300)

with t2:
    st.markdown(f"Shape: `{df_overdue.shape}` | Columns: `{list(df_overdue.columns)}`")
    due_years = sorted(df_overdue["DueYear"].dropna().astype(int).unique().tolist()) if "DueYear" in df_overdue.columns else []
    st.markdown(f"DueYear unique (from OriginalDueDate): `{due_years}`")
    st.dataframe(df_overdue.head(100), use_container_width=True, height=300)

with t3:
    st.markdown(f"Shape: `{df_joined.shape}` | Columns: `{list(df_joined.columns)}`")
    st.dataframe(df_joined.head(100), use_container_width=True, height=300)

st.markdown("---")
st.subheader("Step 3 — OverDue Year Mapping Verification")

avail_years_available = set(df_avail["AVAIL_YEAR"].dropna().astype(str).unique().tolist())
overdue_due_years = (
    sorted(df_overdue["DueYear"].dropna().astype(int).unique().tolist())
    if "DueYear" in df_overdue.columns else []
)

st.markdown(f"**Avail Years available:** `{sorted(avail_years_available)}`")
st.markdown(f"**OverDue DueYears (OriginalDueDate):** `{overdue_due_years}`")

avail_year_int = sorted([int(y) for y in avail_years_available if str(y).isdigit()])
mapping_rows = []
for due_yr in overdue_due_years:
    due_yr_str = str(due_yr)
    if due_yr_str in avail_years_available:
        mapped = due_yr_str
        match_type = "Exact Match"
    elif avail_year_int:
        before = [y for y in avail_year_int if y <= due_yr]
        after  = [y for y in avail_year_int if y > due_yr]
        if before:
            mapped = str(max(before))
            match_type = "Nearest Before"
        else:
            mapped = str(min(after))
            match_type = "Nearest After (no prior year)"
    else:
        mapped = "N/A"
        match_type = "No Avail Data"

    n_overdue_rows = int((df_overdue["DueYear"] == due_yr).sum()) if "DueYear" in df_overdue.columns else 0
    mapping_rows.append({
        "OverDue Year": due_yr,
        "Mapped Avail Year": mapped,
        "Match Type": match_type,
        "Overdue Rows": n_overdue_rows,
    })

df_mapping = pd.DataFrame(mapping_rows)
st.dataframe(df_mapping, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("Step 4 — Per-Year Join Detail")

selected_due_year = st.selectbox(
    "Select OverDue Year to inspect",
    options=["All"] + [str(y) for y in overdue_due_years],
    index=0,
    key="dbg_year_sel",
)

if selected_due_year == "All":
    df_inspect = df_joined.copy()
else:
    try:
        yr_int = int(selected_due_year)
    except ValueError:
        yr_int = None

    df_inspect = df_joined.copy()
    if yr_int and "DueYear" in df_inspect.columns:
        df_inspect = df_inspect[df_inspect["DueYear"] == yr_int]

        due_yr_str = str(yr_int)
        if due_yr_str in avail_years_available:
            matched_avail = due_yr_str
        elif avail_year_int:
            before = [y for y in avail_year_int if y <= yr_int]
            after  = [y for y in avail_year_int if y > yr_int]
            matched_avail = str(max(before)) if before else str(min(after))
        else:
            matched_avail = None

        if matched_avail:
            avail_snap = df_avail[df_avail["AVAIL_YEAR"] == matched_avail].copy()
            if "DATE" in avail_snap.columns:
                avail_snap = avail_snap.sort_values("DATE", ascending=False).drop_duplicates(subset=["CUSTOMER_CODE"])
            else:
                avail_snap = avail_snap.drop_duplicates(subset=["CUSTOMER_CODE"])

            avail_keep = ["CUSTOMER_CODE", "CUSTOMER_NAME", "CLEAN_CREDIT_MB",
                          "CURRENT_DEBT_MILLION_THB", "CURRENT_DEBT_MILLION_THB_PERCENT",
                          "EST_DEBT", "AVAIL_YEAR"]
            avail_snap = avail_snap[[c for c in avail_keep if c in avail_snap.columns]].copy()
            avail_snap = avail_snap.rename(columns={
                "CUSTOMER_NAME": "AVAIL_CUSTOMER_NAME_REMAP",
                "AVAIL_YEAR":    "AVAIL_YEAR_REMAP",
            })

            drop_remap = [c for c in df_inspect.columns if c in {
                "CUSTOMER_CODE", "AVAIL_CUSTOMER_NAME", "CLEAN_CREDIT_MB",
                "CURRENT_DEBT_MILLION_THB", "CURRENT_DEBT_MILLION_THB_PERCENT",
                "EST_DEBT", "AVAIL_YEAR", "UtilizationPct", "RiskTier",
            }]
            df_inspect = df_inspect.drop(columns=drop_remap, errors="ignore")
            df_inspect = df_inspect.merge(avail_snap, left_on="Customer", right_on="CUSTOMER_CODE", how="left")

            if "CURRENT_DEBT_MILLION_THB_PERCENT" in df_inspect.columns:
                pct = df_inspect["CURRENT_DEBT_MILLION_THB_PERCENT"].fillna(0.0)
                df_inspect["UtilizationPct"] = pct * 100
            else:
                df_inspect["UtilizationPct"] = np.nan

            st.info(
                f"OverDue Year {yr_int} → Mapped Avail Year: **{matched_avail}** "
                f"({'Exact' if matched_avail == due_yr_str else 'Nearest'})"
            )

st.markdown(f"**Rows in view:** `{len(df_inspect)}`")

# Join quality check
if "CUSTOMER_CODE" in df_inspect.columns:
    total_rows      = len(df_inspect)
    joined_rows     = int(df_inspect["CUSTOMER_CODE"].notna().sum())
    unjoined_rows   = total_rows - joined_rows
    join_pct        = joined_rows / total_rows * 100 if total_rows > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Overdue Rows",  f"{total_rows:,}")
    m2.metric("Joined (Avail found)", f"{joined_rows:,}")
    m3.metric("Unjoined (no avail)", f"{unjoined_rows:,}")
    m4.metric("Join Rate",           f"{join_pct:.1f}%")

st.markdown("### Joined Detail Table")
show_cols = [
    "Customer", "AVAIL_CUSTOMER_NAME", "AVAIL_CUSTOMER_NAME_REMAP",
    "DueYear", "DueMonth", "DueMonthLabel",
    "OriginalDueDate", "CollectionDate",
    "OverdueAmount", "IsPaid", "PaidOnTime", "PaidLate", "NotCollected",
    "DPD", "AVAIL_YEAR", "AVAIL_YEAR_REMAP",
    "CUSTOMER_CODE", "CLEAN_CREDIT_MB",
    "CURRENT_DEBT_MILLION_THB", "CURRENT_DEBT_MILLION_THB_PERCENT",
    "UtilizationPct", "RiskTier",
]
show_cols = [c for c in show_cols if c in df_inspect.columns]
st.dataframe(df_inspect[show_cols].head(500), use_container_width=True, height=420)

st.markdown("### Customers NOT Joined (no Avail match)")
if "CUSTOMER_CODE" in df_inspect.columns:
    unjoined = df_inspect[df_inspect["CUSTOMER_CODE"].isna()].copy()
    if unjoined.empty:
        st.success("All overdue customers matched an Avail record.")
    else:
        unjoined_summary = (
            unjoined.groupby("Customer")
            .agg(Rows=("OverdueAmount", "count"),
                 TotalOverdue=("OverdueAmount", "sum"))
            .reset_index()
            .sort_values("TotalOverdue", ascending=False)
        )
        st.warning(f"{len(unjoined_summary)} customers have no Avail match.")
        st.dataframe(unjoined_summary, use_container_width=True, height=280)

st.markdown("---")
st.subheader("Step 5 — OriginalDueDate Parse Check")
if "OriginalDueDate" in df_overdue.columns:
    date_check = df_overdue[["Customer", "OriginalDueDate", "DueYear", "DueMonth", "DueQuarter"]].copy()
    date_check["ParseOK"] = df_overdue["OriginalDueDate"].notna()
    failed_parse = date_check[~date_check["ParseOK"]]
    st.markdown(f"Total rows: `{len(date_check)}` | Parse failed: `{len(failed_parse)}`")
    if not failed_parse.empty:
        st.warning("Rows where OriginalDueDate could NOT be parsed:")
        st.dataframe(failed_parse, use_container_width=True, height=200)
    else:
        st.success("All OriginalDueDate rows parsed successfully.")
    st.dataframe(date_check.head(200), use_container_width=True, height=300)


# =============================================================================
# STEP 6 — Session Log (copy และส่งให้ตรวจสอบได้)
# =============================================================================
st.markdown("---")
st.subheader("Step 6 — Session Log")

import io
import traceback

log_lines = []

def log(msg: str):
    log_lines.append(msg)

# --- Avail summary ---
log("=== AVAIL SUMMARY ===")
log(f"Sheets processed : {sheet_names}")
log(f"AVAIL_YEAR unique: {sorted(df_avail['AVAIL_YEAR'].dropna().unique().tolist())}")
log(f"Rows             : {len(df_avail)}")
log(f"Columns          : {list(df_avail.columns)}")
log("")

# --- Overdue summary ---
log("=== OVERDUE SUMMARY ===")
due_years_log = (
    sorted(df_overdue["DueYear"].dropna().astype(int).unique().tolist())
    if "DueYear" in df_overdue.columns else []
)
log(f"DueYear unique   : {due_years_log}")
log(f"Rows             : {len(df_overdue)}")
log(f"Columns          : {list(df_overdue.columns)}")
log(f"OriginalDueDate parse failed: {int(df_overdue['OriginalDueDate'].isna().sum()) if 'OriginalDueDate' in df_overdue.columns else 'N/A'}")
log(f"PaidOnTime total : {int(df_overdue['PaidOnTime'].sum()) if 'PaidOnTime' in df_overdue.columns else 'N/A'}")
log(f"PaidLate total   : {int(df_overdue['PaidLate'].sum()) if 'PaidLate' in df_overdue.columns else 'N/A'}")
log(f"NotCollected total: {int(df_overdue['NotCollected'].sum()) if 'NotCollected' in df_overdue.columns else 'N/A'}")
log("")

# --- Mapping summary ---
log("=== OVERDUE YEAR → AVAIL YEAR MAPPING ===")
for row in mapping_rows:
    log(
        f"  DueYear {row['OverDue Year']} → Avail {row['Mapped Avail Year']}"
        f" [{row['Match Type']}] ({row['Overdue Rows']} rows)"
    )
log("")

# --- Join summary ---
log("=== JOIN SUMMARY (df_joined) ===")
log(f"Total joined rows: {len(df_joined)}")
if "CUSTOMER_CODE" in df_joined.columns:
    joined_ok  = int(df_joined["CUSTOMER_CODE"].notna().sum())
    joined_no  = len(df_joined) - joined_ok
    join_rate  = joined_ok / len(df_joined) * 100 if len(df_joined) > 0 else 0.0
    log(f"Joined (avail found) : {joined_ok}")
    log(f"Unjoined (no avail)  : {joined_no}")
    log(f"Join rate            : {join_rate:.1f}%")

    unjoined_customers = (
        df_joined[df_joined["CUSTOMER_CODE"].isna()]["Customer"]
        .dropna().astype(int).unique().tolist()
    )
    if unjoined_customers:
        log(f"Unjoined Customer codes: {sorted(unjoined_customers)}")
    else:
        log("All customers matched Avail.")
log("")

# --- RiskTier distribution ---
if "RiskTier" in df_joined.columns:
    log("=== RISK TIER DISTRIBUTION (df_joined) ===")
    tier_dist = df_joined["RiskTier"].value_counts().to_dict()
    for tier, cnt in tier_dist.items():
        log(f"  {tier}: {cnt} rows")
    log("")

# --- UtilizationPct sanity check ---
if "UtilizationPct" in df_joined.columns:
    log("=== UTILIZATION PCT SANITY ===")
    util = df_joined["UtilizationPct"].dropna()
    log(f"  count : {len(util)}")
    log(f"  mean  : {util.mean():.2f}%")
    log(f"  min   : {util.min():.2f}%")
    log(f"  max   : {util.max():.2f}%")
    zero_util = int((util == 0).sum())
    log(f"  zero  : {zero_util} rows")
    log("")

# --- Per-year inspect summary (ถ้าเลือก year ใน Step 4) ---
if selected_due_year != "All" and "df_inspect" in dir():
    log(f"=== STEP 4 INSPECT — DueYear {selected_due_year} ===")
    log(f"Rows in inspect  : {len(df_inspect)}")
    if "CUSTOMER_CODE" in df_inspect.columns:
        ok  = int(df_inspect["CUSTOMER_CODE"].notna().sum())
        no  = len(df_inspect) - ok
        log(f"Joined           : {ok}")
        log(f"Unjoined         : {no}")
    if "UtilizationPct" in df_inspect.columns:
        u = df_inspect["UtilizationPct"].dropna()
        log(f"UtilizationPct mean: {u.mean():.2f}% | max: {u.max():.2f}%")
    log("")

log("=== END OF LOG ===")

# --- Render log box + download button ---
full_log = "\n".join(log_lines)

st.text_area(
    label="Log Output (copy ส่งให้ตรวจสอบได้เลย)",
    value=full_log,
    height=400,
    key="debug_log_area",
)

st.download_button(
    label="Download log (.txt)",
    data=full_log.encode("utf-8"),
    file_name="debug_moni.log",
    mime="text/plain",
)