# eda.py
# วัตถุประสงค์ : สำรวจข้อมูลทั้งหมดผ่าน et_pipeline แล้ว log ลง EDA.log
# ไม่ depend on streamlit หรือ library ภายนอกใดๆ นอกจาก pandas + numpy
# วิธีใช้ : python eda.py
# =============================================================================

import os
import sys
import logging
import datetime
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------
LOG_PATH = "EDA.log"

logging.basicConfig(
    filename=LOG_PATH,
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)
log = logging.getLogger("eda")

# also print to console
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(console)


def sep(title: str = ""):
    line = "=" * 70
    log.info("")
    log.info(line)
    if title:
        log.info(f"  {title}")
        log.info(line)


def log_df_overview(name: str, df: pd.DataFrame):
    sep(f"OVERVIEW : {name}")
    log.info(f"Shape          : {df.shape}")
    log.info(f"Columns        : {list(df.columns)}")
    log.info(f"Memory (MB)    : {df.memory_usage(deep=True).sum() / 1e6:.2f}")
    log.info(f"Duplicated rows: {df.duplicated().sum()}")


def log_dtypes(df: pd.DataFrame):
    sep("DTYPES")
    for col, dtype in df.dtypes.items():
        null_n   = int(df[col].isna().sum())
        null_pct = null_n / max(len(df), 1) * 100
        uniq     = df[col].nunique()
        log.info(
            f"  {col:<45} dtype={str(dtype):<12} "
            f"nulls={null_n:>6} ({null_pct:>5.1f}%)  unique={uniq}"
        )


def log_numeric_stats(df: pd.DataFrame):
    sep("NUMERIC COLUMN STATISTICS")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        log.info("  (no numeric columns)")
        return
    for col in num_cols:
        s    = df[col].dropna()
        if len(s) == 0:
            log.info(f"  {col} : all null")
            continue
        q1   = float(s.quantile(0.25))
        q3   = float(s.quantile(0.75))
        iqr  = q3 - q1
        skew = float(s.skew())
        kurt = float(s.kurt())
        log.info(
            f"\n  --- {col} ---\n"
            f"    count   : {len(s)}\n"
            f"    min     : {s.min():.4f}\n"
            f"    max     : {s.max():.4f}\n"
            f"    mean    : {s.mean():.4f}\n"
            f"    median  : {s.median():.4f}\n"
            f"    std     : {s.std():.4f}\n"
            f"    Q1      : {q1:.4f}\n"
            f"    Q3      : {q3:.4f}\n"
            f"    IQR     : {iqr:.4f}\n"
            f"    skewness: {skew:.4f}  "
            f"{'(highly skewed)' if abs(skew) > 1 else '(moderate)' if abs(skew) > 0.5 else '(normal-ish)'}\n"
            f"    kurtosis: {kurt:.4f}\n"
            f"    zeros   : {(s == 0).sum()}\n"
            f"    negatives: {(s < 0).sum()}\n"
            f"    p1      : {s.quantile(0.01):.4f}\n"
            f"    p5      : {s.quantile(0.05):.4f}\n"
            f"    p25     : {q1:.4f}\n"
            f"    p50     : {s.quantile(0.50):.4f}\n"
            f"    p75     : {q3:.4f}\n"
            f"    p90     : {s.quantile(0.90):.4f}\n"
            f"    p95     : {s.quantile(0.95):.4f}\n"
            f"    p99     : {s.quantile(0.99):.4f}"
        )


def log_categorical_stats(df: pd.DataFrame, max_cats: int = 20):
    sep("CATEGORICAL / OBJECT COLUMN STATISTICS")
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if not cat_cols:
        log.info("  (no categorical columns)")
        return
    for col in cat_cols:
        vc   = df[col].value_counts(dropna=False)
        top  = vc.head(max_cats).to_dict()
        log.info(
            f"\n  --- {col} ---\n"
            f"    unique   : {df[col].nunique()}\n"
            f"    nulls    : {df[col].isna().sum()}\n"
            f"    top {max_cats}  : {top}"
        )


def log_date_stats(df: pd.DataFrame):
    sep("DATE COLUMN STATISTICS")
    date_cols = df.select_dtypes(include=["datetime64", "datetime64[ns]",
                                           "datetimetz"]).columns.tolist()
    # also check object columns that look like dates
    for col in df.select_dtypes(include=["object"]).columns:
        sample = df[col].dropna().head(5).tolist()
        try:
            parsed = pd.to_datetime(sample, errors="raise")
            date_cols.append(col)
        except Exception:
            pass

    if not date_cols:
        log.info("  (no date columns detected)")
        return

    for col in date_cols:
        try:
            s = pd.to_datetime(df[col], errors="coerce").dropna()
            log.info(
                f"\n  --- {col} ---\n"
                f"    count   : {len(s)}\n"
                f"    min     : {s.min()}\n"
                f"    max     : {s.max()}\n"
                f"    range   : {(s.max() - s.min()).days} days\n"
                f"    nulls   : {df[col].isna().sum()}"
            )
        except Exception as e:
            log.info(f"  {col} : error parsing — {e}")


def log_outlier_analysis(df: pd.DataFrame):
    sep("OUTLIER ANALYSIS (IQR method)")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in num_cols:
        s   = df[col].dropna()
        if len(s) < 4:
            continue
        q1  = s.quantile(0.25)
        q3  = s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo  = q1 - 1.5 * iqr
        hi  = q3 + 1.5 * iqr
        out = ((s < lo) | (s > hi)).sum()
        pct = out / len(s) * 100
        log.info(
            f"  {col:<45} outliers={out:>5} ({pct:>5.1f}%)  "
            f"fence=[{lo:.3f}, {hi:.3f}]"
        )


def log_distribution_shape(df: pd.DataFrame):
    sep("DISTRIBUTION SHAPE DIAGNOSIS")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in num_cols:
        s    = df[col].dropna()
        if len(s) < 4:
            continue
        skew = float(s.skew())
        zero_pct = (s == 0).sum() / len(s) * 100
        neg_pct  = (s < 0).sum()  / len(s) * 100
        max_val  = s.max()
        min_val  = s.min()
        median   = s.median()
        mean     = s.mean()
        cv       = s.std() / mean if mean != 0 else float("inf")

        issues = []
        if abs(skew) > 2:
            issues.append("HIGHLY_SKEWED")
        elif abs(skew) > 1:
            issues.append("SKEWED")
        if zero_pct > 50:
            issues.append("ZERO_HEAVY")
        if neg_pct > 0:
            issues.append("HAS_NEGATIVES")
        if cv > 2:
            issues.append("HIGH_VARIANCE")
        if max_val > 0 and (max_val / max(median, 0.0001)) > 100:
            issues.append("EXTREME_OUTLIER")

        log.info(
            f"  {col:<45} skew={skew:>7.2f}  cv={cv:>6.2f}  "
            f"zero%={zero_pct:>5.1f}  neg%={neg_pct:>5.1f}  "
            f"issues={issues if issues else ['OK']}"
        )


def log_correlation(df: pd.DataFrame):
    sep("CORRELATION MATRIX (numeric columns)")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) < 2:
        log.info("  (need at least 2 numeric columns)")
        return
    corr = df[num_cols].corr().round(3)
    log.info("\n" + corr.to_string())


def log_data_sample(name: str, df: pd.DataFrame, n: int = 10):
    sep(f"SAMPLE ({n} rows) : {name}")
    log.info("\n" + df.head(n).to_string())


def log_transformation_recommendations(df: pd.DataFrame):
    sep("DATA SCIENCE RECOMMENDATIONS")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    recs = []
    for col in num_cols:
        s    = df[col].dropna()
        if len(s) < 4:
            continue
        skew     = float(s.skew())
        zero_pct = (s == 0).sum() / len(s) * 100
        neg_pct  = (s < 0).sum()  / len(s) * 100
        max_val  = s.max()
        median   = s.median()

        rec = {"column": col, "actions": []}

        if neg_pct > 0:
            rec["actions"].append(
                "HAS_NEGATIVES: พิจารณา abs() หรือ separate negative/positive"
            )
        if zero_pct > 70:
            rec["actions"].append(
                "ZERO_HEAVY (>70%): พิจารณา binary flag + model โดยแยก zero vs non-zero"
            )
        if skew > 2 and zero_pct < 50 and neg_pct == 0:
            rec["actions"].append(
                "RIGHT_SKEW: แนะนำ log1p transform หรือ sqrt transform"
            )
        if skew < -2:
            rec["actions"].append(
                "LEFT_SKEW: แนะนำ reflect + log transform"
            )
        if max_val > 0 and (max_val / max(median, 0.0001)) > 100:
            rec["actions"].append(
                "EXTREME_OUTLIER: พิจารณา winsorize (clip) ที่ p95 หรือ p99"
            )
        if not rec["actions"]:
            rec["actions"].append("OK: ไม่จำเป็นต้อง transform")

        recs.append(rec)

    for r in recs:
        log.info(f"\n  {r['column']}:")
        for a in r["actions"]:
            log.info(f"    -> {a}")


# =============================================================================
# main
# =============================================================================
def main():
    sep("EDA SESSION START")
    log.info(f"Timestamp : {datetime.datetime.now()}")
    log.info(f"Python    : {sys.version}")
    log.info(f"Pandas    : {pd.__version__}")
    log.info(f"Numpy     : {np.__version__}")

    # ------------------------------------------------------------------
    # Locate files
    # ------------------------------------------------------------------
    sep("FILE DISCOVERY")

    # Credit Availability file
    avail_file = None
    for fname in os.listdir("."):
        if fname.lower().endswith(".xlsx") and "availability" in fname.lower():
            avail_file = fname
            break
    if avail_file is None:
        # fallback: first xlsx that is NOT overdue-looking
        for fname in os.listdir("."):
            if fname.lower().endswith(".xlsx") and "overdue" not in fname.lower():
                avail_file = fname
                break

    # Overdue file
    overdue_file = None
    for fname in sorted(os.listdir("."), reverse=True):
        if fname.lower().endswith(".xlsx") and fname != avail_file:
            overdue_file = fname
            break

    log.info(f"Availability file : {avail_file}")
    log.info(f"Overdue file      : {overdue_file}")

    if not avail_file or not overdue_file:
        log.error("ไม่พบไฟล์ที่จำเป็น — วาง Credit Availability.xlsx และ Overdue.xlsx ในโฟลเดอร์เดียวกัน")
        return

    # ------------------------------------------------------------------
    # Import et_pipeline (same directory)
    # ------------------------------------------------------------------
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import et_pipeline as etp
        log.info("et_pipeline imported successfully")
    except ImportError as e:
        log.error(f"ไม่สามารถ import et_pipeline ได้: {e}")
        return

    # ------------------------------------------------------------------
    # Load Availability via et_pipeline
    # ------------------------------------------------------------------
    sep("LOADING CREDIT AVAILABILITY via et_pipeline")
    try:
        xls     = pd.ExcelFile(avail_file)
        sheets  = xls.sheet_names
        log.info(f"Sheets found: {sheets}")

        valid_sheets, invalid_sheets = etp.analyze_excel_sheets(avail_file)
        log.info(f"Valid sheets   : {valid_sheets}")
        log.info(f"Invalid sheets : {invalid_sheets}")

        if not valid_sheets:
            log.warning("ไม่พบ valid sheet — ลอง load ทุก sheet แทน")
            valid_sheets = [s for s in sheets if s.lower() not in ["sheet2","sheet3"]]

        av_frames = []
        for sheet in valid_sheets:
            df_raw = pd.read_excel(xls, sheet_name=sheet)
            df_t, debug = etp._transform_availability(df_raw, sheet_name=sheet)
            df_t.insert(0, "SOURCE_SHEET", str(sheet))
            av_frames.append(df_t)
            log.info(
                f"  Sheet '{sheet}' : raw={debug['raw_rows']} "
                f"final={debug['final_rows']} "
                f"na_dropped={debug['na_dropped_count']}"
            )

        df_avail = pd.concat(av_frames, ignore_index=True) if av_frames else pd.DataFrame()
        log.info(f"df_avail combined shape: {df_avail.shape}")

    except Exception as e:
        log.error(f"Error loading avail: {e}")
        import traceback
        log.error(traceback.format_exc())
        df_avail = pd.DataFrame()

    # ------------------------------------------------------------------
    # Load Overdue via et_pipeline
    # ------------------------------------------------------------------
    sep("LOADING CREDIT OVERDUE via et_pipeline")
    try:
        df_ov_raw  = pd.read_excel(overdue_file)
        df_overdue = etp._clean_overdue(df_ov_raw.copy())
        log.info(f"df_overdue shape: {df_overdue.shape}")
    except Exception as e:
        log.error(f"Error loading overdue: {e}")
        import traceback
        log.error(traceback.format_exc())
        df_overdue = pd.DataFrame()

    # ------------------------------------------------------------------
    # EDA : Credit Availability
    # ------------------------------------------------------------------
    if not df_avail.empty:
        sep("=== EDA : CREDIT AVAILABILITY ===")
        log_df_overview("Credit Availability", df_avail)
        log_data_sample("Credit Availability", df_avail)
        log_dtypes(df_avail)
        log_numeric_stats(df_avail)
        log_categorical_stats(df_avail)
        log_date_stats(df_avail)
        log_outlier_analysis(df_avail)
        log_distribution_shape(df_avail)
        log_correlation(df_avail)
        log_transformation_recommendations(df_avail)

        # Per-sheet stats
        sep("PER-SHEET STATISTICS (Availability)")
        if "SOURCE_SHEET" in df_avail.columns:
            for sheet, grp in df_avail.groupby("SOURCE_SHEET"):
                log.info(
                    f"  Sheet '{sheet}' : rows={len(grp)}  "
                    f"unique_customers={grp['CUSTOMER_CODE'].nunique() if 'CUSTOMER_CODE' in grp.columns else 'N/A'}"
                )
                if "CURRENT_DEBT_MILLION_THB" in grp.columns:
                    s = grp["CURRENT_DEBT_MILLION_THB"].dropna()
                    log.info(
                        f"    CURRENT_DEBT: mean={s.mean():.2f}  "
                        f"median={s.median():.2f}  max={s.max():.2f}  "
                        f"skew={s.skew():.2f}"
                    )
                if "ESTIMATE_AMOUNT" in grp.columns:
                    s = grp["ESTIMATE_AMOUNT"].dropna()
                    log.info(
                        f"    ESTIMATE_AMOUNT: mean={s.mean():.2f}  "
                        f"median={s.median():.2f}  max={s.max():.2f}  "
                        f"skew={s.skew():.2f}"
                    )

    # ------------------------------------------------------------------
    # EDA : Credit Overdue
    # ------------------------------------------------------------------
    if not df_overdue.empty:
        sep("=== EDA : CREDIT OVERDUE ===")
        log_df_overview("Credit Overdue", df_overdue)
        log_data_sample("Credit Overdue", df_overdue)
        log_dtypes(df_overdue)
        log_numeric_stats(df_overdue)
        log_categorical_stats(df_overdue)
        log_date_stats(df_overdue)
        log_outlier_analysis(df_overdue)
        log_distribution_shape(df_overdue)
        log_correlation(df_overdue)
        log_transformation_recommendations(df_overdue)

        # Overdue-specific analysis
        sep("OVERDUE SPECIFIC ANALYSIS")

        # CompanyCode distribution
        if "CompanyCode" in df_overdue.columns:
            vc = df_overdue["CompanyCode"].value_counts()
            log.info(f"CompanyCode distribution:\n{vc.to_string()}")

        # OverdueAmount sign analysis
        if "OverdueAmount" in df_overdue.columns:
            s    = pd.to_numeric(df_overdue["OverdueAmount"], errors="coerce")
            neg  = (s < 0).sum()
            zero = (s == 0).sum()
            pos  = (s > 0).sum()
            log.info(
                f"\nOverdueAmount sign breakdown:\n"
                f"  negative (<0) = {neg}  ({neg/len(s)*100:.1f}%)\n"
                f"  zero (=0)     = {zero} ({zero/len(s)*100:.1f}%)\n"
                f"  positive (>0) = {pos}  ({pos/len(s)*100:.1f}%)\n"
                f"  SCG convention: overdue = OverdueAmount <= 0"
            )

        # DPD calculation
        if "OriginalDueDate" in df_overdue.columns:
            dates = pd.to_datetime(
                df_overdue["OriginalDueDate"].astype(str).str.strip(),
                format="%Y%m%d", errors="coerce"
            )
            today = pd.Timestamp("today").normalize()
            dpd   = (today - dates).dt.days.clip(lower=0)
            log.info(
                f"\nDPD (Days Past Due) from OriginalDueDate:\n"
                f"  count   : {dpd.notna().sum()}\n"
                f"  min     : {dpd.min():.0f}\n"
                f"  max     : {dpd.max():.0f}\n"
                f"  mean    : {dpd.mean():.1f}\n"
                f"  median  : {dpd.median():.1f}\n"
                f"  p75     : {dpd.quantile(0.75):.1f}\n"
                f"  p90     : {dpd.quantile(0.90):.1f}\n"
                f"  p99     : {dpd.quantile(0.99):.1f}\n"
                f"  skewness: {dpd.skew():.2f}\n"
                f"\nDPD bucket distribution:\n"
                f"  Current (0d)   : {(dpd == 0).sum()}\n"
                f"  1-30d          : {((dpd > 0)  & (dpd <= 30)).sum()}\n"
                f"  31-60d         : {((dpd > 30) & (dpd <= 60)).sum()}\n"
                f"  61-90d         : {((dpd > 60) & (dpd <= 90)).sum()}\n"
                f"  91-180d        : {((dpd > 90) & (dpd <= 180)).sum()}\n"
                f"  181-360d       : {((dpd > 180) & (dpd <= 360)).sum()}\n"
                f"  360+d          : {(dpd > 360).sum()}"
            )

        # Customer concentration
        if "Customer" in df_overdue.columns and "OverdueAmount" in df_overdue.columns:
            df_c = df_overdue.copy()
            df_c["OverdueAmount"] = pd.to_numeric(df_c["OverdueAmount"], errors="coerce")
            df_c["IsOverdue"]     = df_c["OverdueAmount"] <= 0
            df_c["OverdueAbs"]    = df_c["OverdueAmount"].abs()
            cust_agg = (
                df_c[df_c["IsOverdue"]]
                .groupby("Customer")["OverdueAbs"].sum()
                .sort_values(ascending=False)
            )
            total    = cust_agg.sum()
            top10    = cust_agg.head(10).sum() / max(total, 1) * 100
            top1     = cust_agg.head(1).sum()  / max(total, 1) * 100
            log.info(
                f"\nCustomer Overdue Concentration:\n"
                f"  total overdue customers : {len(cust_agg)}\n"
                f"  total overdue amount    : {total:,.2f} THB\n"
                f"  top 1 customer share    : {top1:.1f}%\n"
                f"  top 10 customer share   : {top10:.1f}%\n"
                f"\nTop 20 customers by overdue:\n"
                + cust_agg.head(20).to_string()
            )

    # ------------------------------------------------------------------
    # Join feasibility check
    # ------------------------------------------------------------------
    sep("JOIN FEASIBILITY CHECK")
    if not df_avail.empty and not df_overdue.empty:
        if "CUSTOMER_CODE" in df_avail.columns and "Customer" in df_overdue.columns:
            av_codes = set(
                pd.to_numeric(df_avail["CUSTOMER_CODE"], errors="coerce")
                .fillna(0).astype(int).unique()
            )
            ov_codes = set(
                pd.to_numeric(df_overdue["Customer"], errors="coerce")
                .fillna(0).astype(int).unique()
            )
            matched   = av_codes & ov_codes
            unmatched = ov_codes - av_codes
            log.info(
                f"  avail CUSTOMER_CODE unique : {len(av_codes)}\n"
                f"  overdue Customer unique    : {len(ov_codes)}\n"
                f"  MATCHED                    : {len(matched)} "
                f"({len(matched)/max(len(ov_codes),1)*100:.1f}%)\n"
                f"  NOT matched (overdue only) : {len(unmatched)}\n"
                f"  matched sample             : {sorted(matched)[:15]}\n"
                f"  unmatched sample           : {sorted(unmatched)[:15]}"
            )

    sep("EDA SESSION COMPLETE")
    log.info(f"Log saved to: {os.path.abspath(LOG_PATH)}")


if __name__ == "__main__":
    main()