import os
import re
import sys
import time
from collections import Counter
import duckdb
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 150)
pd.set_option('display.width', 1200)
pd.set_option('display.max_colwidth', 100)

# STRICT COMPLIANCE: Use ONLY the dataset provided by Swift.
# Zero external CSVs, GDP tables, timezone files, or external APIs.
DEFAULT_CSV_PATH = r"C:\Users\Joe\Downloads\swift_umdac_datathon_2026_fictitious_payment_data\swift_umdac_datathon_2026_fictitious_payment_data.csv"
CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_PATH
SAMPLE_PARQUET_PATH = os.path.join("data", "sample_200k.parquet")


def run_sample_decision_trees_and_token_discovery():
    print("\n" + "=" * 110)
    print("PHASE A: FAST CAUSAL RULE DISCOVERY ON data/sample_200k.parquet (SHALLOW DECISION TREES & TOKEN MINING)")
    print("=" * 110)

    df = pd.read_parquet(SAMPLE_PARQUET_PATH)
    print(f"[INFO] Loaded stratified sample: {len(df):,} rows, {df.shape[1]} columns")

    # 1. Discover all exact token tags in ORDERING_TOKENS and BENEFICIARY_TOKENS
    ord_counter = Counter()
    ben_counter = Counter()
    tag_pattern = re.compile(r"<([a-zA-Z0-9_]+)(?::[^>]+)?>")

    for txt in df["ORDERING_TOKENS"].dropna():
        ord_counter.update(set(tag_pattern.findall(txt)))
    for txt in df["BENEFICIARY_TOKENS"].dropna():
        ben_counter.update(set(tag_pattern.findall(txt)))

    print("\n--- Discovered Token Tags in ORDERING_TOKENS (Doc Frequency in 200k Sample) ---")
    for tag, cnt in ord_counter.most_common():
        print(f"  <{tag}:...> : {cnt:>8,} rows ({100.0 * cnt / len(df):6.2f}%)")

    print("\n--- Discovered Token Tags in BENEFICIARY_TOKENS (Doc Frequency in 200k Sample) ---")
    for tag, cnt in ben_counter.most_common():
        print(f"  <{tag}:...> : {cnt:>8,} rows ({100.0 * cnt / len(df):6.2f}%)")

    # Check sample rows of DISCLAIMER and each ANOMALY_TYPE
    print("\n--- Sample Non-Null DISCLAIMER Rows in 200k Sample ---")
    disc_rows = df[df["DISCLAIMER"].notna()]
    print(f"Non-null DISCLAIMER count in 200k sample: {len(disc_rows)}")
    if len(disc_rows) > 0:
        print(disc_rows[["DISCLAIMER", "ANOMALY_TYPE", "ORDERING_TYPE", "BENEFICIARY_TYPE", "USD_AMOUNT"]].head(10))

    # Engineer internal features on the 200k sample for Decision Tree rule discovery
    df["ord_country"] = df["ORDERING_BIC8"].str.slice(4, 6)
    df["ben_country"] = df["BENEFICIARY_BIC8"].str.slice(4, 6)
    df["is_domestic"] = (df["ord_country"] == df["ben_country"]).astype(int)

    # Derive internal modal currency per country strictly from normal sample rows
    normal_mask = df["ANOMALY_TYPE"].isna()
    country_modal_curr = (
        df[normal_mask]
        .groupby("ord_country")["CURRENCY_CODE"]
        .agg(lambda s: s.value_counts().index[0] if len(s) > 0 else "")
        .to_dict()
    )
    df["ord_modal_curr"] = df["ord_country"].map(country_modal_curr)
    df["ben_modal_curr"] = df["ben_country"].map(country_modal_curr)
    df["is_ord_home_curr"] = (df["CURRENCY_CODE"] == df["ord_modal_curr"]).astype(int)
    df["is_ben_home_curr"] = (df["CURRENCY_CODE"] == df["ben_modal_curr"]).astype(int)
    df["is_third_curr"] = ((df["is_ord_home_curr"] == 0) & (df["is_ben_home_curr"] == 0)).astype(int)
    df["is_usd_or_eur"] = df["CURRENCY_CODE"].isin(["USD", "EUR"]).astype(int)
    df["curr_starts_vowel"] = df["CURRENCY_CODE"].str.slice(0, 1).isin(["A", "E", "I", "O", "U"]).astype(int)

    # Temporal features from EPOCH_SECONDS
    dt_utc = pd.to_datetime(df["EPOCH_SECONDS"], unit="s", utc=True)
    df["utc_hour"] = dt_utc.dt.hour
    df["day_of_week"] = dt_utc.dt.dayofweek  # 0=Mon .. 6=Sun
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Party type flags
    df["ord_is_B"] = (df["ORDERING_TYPE"] == "B").astype(int)
    df["ben_is_B"] = (df["BENEFICIARY_TYPE"] == "B").astype(int)
    df["is_B2B"] = ((df["ord_is_B"] == 1) & (df["ben_is_B"] == 1)).astype(int)
    df["is_B2C"] = ((df["ord_is_B"] == 1) & (df["ben_is_B"] == 0)).astype(int)
    df["is_C2B"] = ((df["ord_is_B"] == 0) & (df["ben_is_B"] == 1)).astype(int)
    df["is_C2C"] = ((df["ord_is_B"] == 0) & (df["ben_is_B"] == 0)).astype(int)

    # Routing & Path flags
    df["qflag_Y"] = (df["CONTINUITY_QFLAG"] == "Y").astype(int)
    df["path_hop_cnt"] = df["BIC8_PATH"].str.count(";") + 1
    df["path_has_dots"] = df["BIC8_PATH"].str.contains(r"\.\.\.", regex=True).astype(int)
    df["tx_Direct"] = (df["TRANSACTION_TYPE_CODE"] == "Direct").astype(int)
    df["tx_Indirect"] = (df["TRANSACTION_TYPE_CODE"] == "Indirect").astype(int)
    df["tx_Covered"] = (df["TRANSACTION_TYPE_CODE"] == "Covered").astype(int)

    # Token features
    for side, col in [("ord", "ORDERING_TOKENS"), ("ben", "BENEFICIARY_TOKENS")]:
        s = df[col].fillna("")
        df[f"{side}_tok_len"] = s.str.len()
        df[f"{side}_has_iban"] = s.str.contains("<iban:", regex=False).astype(int)
        df[f"{side}_has_business"] = s.str.contains("<business:", regex=False).astype(int)
        df[f"{side}_has_comp_kw"] = s.str.contains("<company_keyword:", regex=False).astype(int)
        df[f"{side}_has_first_name"] = s.str.contains("<first_name:", regex=False).astype(int)
        df[f"{side}_has_last_name"] = s.str.contains("<last_name:", regex=False).astype(int)
        df[f"{side}_has_street"] = s.str.contains("<street:", regex=False).astype(int)
        df[f"{side}_has_city"] = s.str.contains("<city:", regex=False).astype(int)
        df[f"{side}_has_country_code"] = s.str.contains("<country_code:", regex=False).astype(int)
        df[f"{side}_has_country_name"] = s.str.contains("<country_name:", regex=False).astype(int)
        df[f"{side}_has_finance_word"] = s.str.contains("<finance_word:", regex=False).astype(int)
        df[f"{side}_has_line_break"] = s.str.contains("<line_break:", regex=False).astype(int)

    df["ord_acct_has_iban_fmt"] = df["ORDERING_ACCOUNT"].str.match(r"^_FAKE_[A-Z]{2}\d{2}").astype(int)
    df["ben_acct_has_iban_fmt"] = df["BENEFICIARY_ACCOUNT"].str.match(r"^_FAKE_[A-Z]{2}\d{2}").astype(int)
    df["log10_usd"] = np.log10(df["USD_AMOUNT"].clip(lower=0.01))
    df["log10_dur"] = np.log10(df["TOTAL_DURATION"].clip(lower=1))

    # -------------------------------------------------------------------------
    # TREE 1: Predict LOG10(USD_AMOUNT) on Normal Traffic (max_depth=3)
    # -------------------------------------------------------------------------
    amt_features = [
        "ord_is_B", "ben_is_B", "is_B2B", "is_C2C", "is_domestic",
        "CURRENCY_CONVERSION_COUNT", "PARTICIPANT_COUNT",
        "is_ord_home_curr", "is_ben_home_curr", "is_third_curr", "is_usd_or_eur", "curr_starts_vowel",
        "tx_Direct", "tx_Covered", "is_weekend", "utc_hour",
        "ord_has_iban", "ben_has_iban", "ord_has_finance_word", "ben_has_finance_word",
        "ord_tok_len", "ben_tok_len"
    ]
    df_norm = df[normal_mask].copy()
    dt_amt = DecisionTreeRegressor(max_depth=3, min_samples_leaf=500, random_state=42)
    dt_amt.fit(df_norm[amt_features], df_norm["log10_usd"])
    print("\n--- DECISION TREE 1: Predicting LOG10(USD_AMOUNT) on Normal Traffic (max_depth=3) ---")
    print(f"R^2 on 200k Normal Sample: {dt_amt.score(df_norm[amt_features], df_norm['log10_usd']):.4f}")
    print(export_text(dt_amt, feature_names=amt_features, decimals=3))

    # -------------------------------------------------------------------------
    # TREE 2: Predict TRANSACTION_TYPE_CODE (Direct vs Indirect vs Covered)
    # and specifically Covered vs Indirect when PARTICIPANT_COUNT >= 3
    # -------------------------------------------------------------------------
    routing_features = [
        "PARTICIPANT_COUNT", "CURRENCY_CONVERSION_COUNT", "is_domestic",
        "is_ord_home_curr", "is_ben_home_curr", "is_third_curr", "is_usd_or_eur",
        "ord_is_B", "ben_is_B", "log10_usd", "qflag_Y",
        "ord_has_iban", "ben_has_iban", "ord_tok_len", "ben_tok_len"
    ]
    dt_route = DecisionTreeClassifier(max_depth=3, min_samples_leaf=500, random_state=42)
    dt_route.fit(df_norm[routing_features], df_norm["TRANSACTION_TYPE_CODE"])
    print("\n--- DECISION TREE 2A: Predicting TRANSACTION_TYPE_CODE (All Normal Rows, max_depth=3) ---")
    print(export_text(dt_route, feature_names=routing_features, class_names=list(dt_route.classes_)))

    df_multihop = df_norm[df_norm["PARTICIPANT_COUNT"] >= 3].copy()
    routing_features_no_part = [f for f in routing_features if f != "PARTICIPANT_COUNT"]
    dt_cover = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, class_weight="balanced", random_state=42)
    dt_cover.fit(df_multihop[routing_features_no_part], df_multihop["TRANSACTION_TYPE_CODE"])
    print("\n--- DECISION TREE 2B: Separating Covered vs Indirect (PARTICIPANT_COUNT >= 3, balanced, max_depth=3) ---")
    print(export_text(dt_cover, feature_names=routing_features_no_part, class_names=list(dt_cover.classes_)))

    # -------------------------------------------------------------------------
    # TREE 3: Predict LOG10(TOTAL_DURATION) on All Rows (max_depth=3)
    # -------------------------------------------------------------------------
    dur_features = [
        "PARTICIPANT_COUNT", "CURRENCY_CONVERSION_COUNT", "tx_Direct", "tx_Indirect", "tx_Covered",
        "qflag_Y", "is_domestic", "ord_is_B", "ben_is_B", "log10_usd", "is_weekend", "utc_hour",
        "ord_has_iban", "ben_has_iban", "ord_tok_len", "ben_tok_len",
        "ord_acct_has_iban_fmt", "ben_acct_has_iban_fmt"
    ]
    dt_dur = DecisionTreeRegressor(max_depth=3, min_samples_leaf=500, random_state=42)
    dt_dur.fit(df_norm[dur_features], df_norm["log10_dur"])
    print("\n--- DECISION TREE 3: Predicting LOG10(TOTAL_DURATION) on Normal Traffic (max_depth=3) ---")
    print(f"R^2 on 200k Normal Sample: {dt_dur.score(df_norm[dur_features], df_norm['log10_dur']):.4f}")
    print(export_text(dt_dur, feature_names=dur_features, decimals=3))

    # -------------------------------------------------------------------------
    # TREE 4: Predict CONTINUITY_QFLAG (Y vs N) without path_has_dots
    # -------------------------------------------------------------------------
    qflag_features = [
        "PARTICIPANT_COUNT", "CURRENCY_CONVERSION_COUNT", "tx_Direct", "tx_Indirect", "tx_Covered",
        "is_domestic", "is_ord_home_curr", "is_ben_home_curr", "is_third_curr",
        "ord_is_B", "ben_is_B", "log10_usd", "log10_dur",
        "ord_has_iban", "ben_has_iban", "ord_tok_len", "ben_tok_len"
    ]
    dt_qf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=500, class_weight="balanced", random_state=42)
    dt_qf.fit(df_norm[qflag_features], df_norm["CONTINUITY_QFLAG"])
    print("\n--- DECISION TREE 4: Predicting CONTINUITY_QFLAG (Y vs N, balanced, max_depth=3) ---")
    print(export_text(dt_qf, feature_names=qflag_features, class_names=list(dt_qf.classes_)))

    # -------------------------------------------------------------------------
    # TREE 5: One-vs-Rest Decision Trees (max_depth=3) for All 6 ANOMALY_TYPEs
    # -------------------------------------------------------------------------
    anom_features = [
        "ord_is_B", "ben_is_B", "is_B2B", "is_B2C", "is_C2B", "is_C2C",
        "log10_usd", "USD_AMOUNT", "log10_dur", "TOTAL_DURATION",
        "PARTICIPANT_COUNT", "CURRENCY_CONVERSION_COUNT",
        "tx_Direct", "tx_Indirect", "tx_Covered", "qflag_Y", "is_domestic",
        "is_ord_home_curr", "is_ben_home_curr", "is_third_curr", "is_weekend", "utc_hour",
        "ord_has_iban", "ben_has_iban", "ord_has_business", "ben_has_business",
        "ord_has_first_name", "ben_has_first_name", "ord_has_last_name", "ben_has_last_name",
        "ord_has_street", "ben_has_street", "ord_has_city", "ben_has_city",
        "ord_has_country_code", "ben_has_country_code", "ord_has_country_name", "ben_has_country_name",
        "ord_has_finance_word", "ben_has_finance_word", "ord_has_line_break", "ben_has_line_break",
        "ord_tok_len", "ben_tok_len", "ord_acct_has_iban_fmt", "ben_acct_has_iban_fmt"
    ]
    anomaly_classes = [
        "ROMANCE_SCAM", "FAT_FINGER_MISTAKE", "CEO_SCAM",
        "DUPLICATE_PAYMENT", "ACCOUNT_REPLACEMENT_SCAM", "CUSTOMER_RECALL"
    ]
    for anom in anomaly_classes:
        y_bin = (df["ANOMALY_TYPE"] == anom).astype(int)
        clf = DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, class_weight="balanced", random_state=42)
        clf.fit(df[anom_features], y_bin)
        print(f"\n--- DECISION TREE 5 ({anom} vs Rest, max_depth=3) ---")
        print(export_text(clf, feature_names=anom_features, class_names=["Normal/Other", anom], decimals=2))


def run_full_10m_duckdb_verification():
    print("\n" + "=" * 110)
    print("PHASE B: FULL 10,000,000-ROW DUCKDB VERIFICATION ACROSS ALL 7 FEATURE GROUPS")
    print("=" * 110)

    con = duckdb.connect()
    con.execute("SET memory_limit = '4GB';")
    con.execute("SET preserve_insertion_order = false;")

    csv_sql_path = CSV_PATH.replace("\\", "/")
    con.execute(f"CREATE VIEW payments AS SELECT * FROM read_csv_auto('{csv_sql_path}', sample_size=100000);")

    # =========================================================================
    # GROUP 0: DATA CLEANING & INTEGRITY AUDIT (RUBRIC 3.1)
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 0: DATA CLEANING & STRUCTURAL INTEGRITY AUDIT (10,000,000 ROWS)")
    print("=" * 110)

    q_group0 = """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISCLAIMER) AS non_null_disclaimer_cnt,
        SUM(CASE WHEN USD_AMOUNT <= 0 OR USD_AMOUNT IS NULL OR ISNAN(USD_AMOUNT) THEN 1 ELSE 0 END) AS invalid_usd_cnt,
        SUM(CASE WHEN TOTAL_DURATION <= 0 OR TOTAL_DURATION IS NULL THEN 1 ELSE 0 END) AS invalid_duration_cnt,
        SUM(CASE WHEN LENGTH(ORDERING_BIC8) != 8 THEN 1 ELSE 0 END) AS invalid_ord_bic8_len,
        SUM(CASE WHEN LENGTH(BENEFICIARY_BIC8) != 8 THEN 1 ELSE 0 END) AS invalid_ben_bic8_len,
        SUM(CASE WHEN SPLIT_PART(BIC8_PATH, ';', 1) != ORDERING_BIC8 THEN 1 ELSE 0 END) AS path_start_mismatch,
        SUM(CASE WHEN SPLIT_PART(BIC8_PATH, ';', 1) = '...' THEN 1 ELSE 0 END) AS path_starts_with_dots,
        SUM(CASE WHEN RIGHT(BIC8_PATH, 8) != BENEFICIARY_BIC8 THEN 1 ELSE 0 END) AS path_end_mismatch,
        SUM(CASE WHEN RIGHT(BIC8_PATH, 3) = '...' THEN 1 ELSE 0 END) AS path_ends_with_dots,
        SUM(CASE WHEN (CONTINUITY_QFLAG = 'N') != (BIC8_PATH LIKE '%...%') THEN 1 ELSE 0 END) AS qflag_dots_mismatch,
        SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Direct' AND PARTICIPANT_COUNT != 2 THEN 1 ELSE 0 END) AS direct_not_2_part,
        SUM(CASE WHEN TRANSACTION_TYPE_CODE IN ('Indirect', 'Covered') AND PARTICIPANT_COUNT < 3 THEN 1 ELSE 0 END) AS ind_cov_lt_3_part,
        SUM(CASE WHEN CONTINUITY_QFLAG = 'Y' AND (LENGTH(BIC8_PATH) - LENGTH(REPLACE(BIC8_PATH, ';', '')) + 1) != PARTICIPANT_COUNT THEN 1 ELSE 0 END) AS qflag_Y_hop_mismatch,
        SUM(CASE WHEN (LENGTH(BIC8_PATH) - LENGTH(REPLACE(BIC8_PATH, ';', '')) + 1) - ((LENGTH(BIC8_PATH) - LENGTH(REPLACE(BIC8_PATH, '...', ''))) / 3) != PARTICIPANT_COUNT THEN 1 ELSE 0 END) AS observable_bic_cnt_mismatch
    FROM payments;
    """
    print("--- Full 10M Integrity & Boundary Audit ---")
    print(con.execute(q_group0).df().T)

    print("\n--- Non-Null DISCLAIMER Values (Full 10M Rows) ---")
    q_disc = """
    SELECT DISCLAIMER, ANOMALY_TYPE, COUNT(*) AS n_rows
    FROM payments
    WHERE DISCLAIMER IS NOT NULL
    GROUP BY 1, 2
    ORDER BY n_rows DESC
    LIMIT 20;
    """
    print(con.execute(q_disc).df().to_string(index=False))

    print("\n--- BIC8_PATH Token Count vs PARTICIPANT_COUNT by CONTINUITY_QFLAG (Full 10M Rows) ---")
    q_path_hops = """
    SELECT
        CONTINUITY_QFLAG,
        BIC8_PATH LIKE '%...%' AS has_ellipsis,
        PARTICIPANT_COUNT,
        (LENGTH(BIC8_PATH) - LENGTH(REPLACE(BIC8_PATH, ';', '')) + 1) AS path_semicolon_elements,
        PARTICIPANT_COUNT - (LENGTH(BIC8_PATH) - LENGTH(REPLACE(BIC8_PATH, ';', ''))) AS hidden_institutions_in_ellipsis,
        COUNT(*) AS n_tx,
        ANY_VALUE(BIC8_PATH) AS example_bic8_path
    FROM payments
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY n_tx DESC
    LIMIT 20;
    """
    print(con.execute(q_path_hops).df().to_string(index=False))

    # =========================================================================
    # GROUP 1: TEMPORAL & CORRIDOR CLOCKS (WEEKDAY VS WEEKEND & B VS C PEAKS)
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 1: TEMPORAL & CORRIDOR CLOCKS (WEEKDAY VS WEEKEND & INTERNAL LOCAL CLOCKS)")
    print("=" * 110)

    q_dow = """
    WITH t AS (
        SELECT
            EXTRACT('isodow' FROM TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC') AS isodow,
            CAST(TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC' AS DATE) AS utc_date,
            ORDERING_TYPE,
            BENEFICIARY_TYPE,
            USD_AMOUNT,
            TOTAL_DURATION,
            ANOMALY_TYPE
        FROM payments
    )
    SELECT
        isodow,
        CASE isodow
            WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed'
            WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' WHEN 7 THEN 'Sun'
        END AS day_name,
        CASE WHEN isodow <= 5 THEN 'Weekday (Mon-Fri)' ELSE 'Weekend (Sat-Sun)' END AS day_type,
        COUNT(DISTINCT utc_date) AS n_calendar_days,
        COUNT(*) AS total_tx,
        ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT utc_date), 1) AS avg_tx_per_day,
        ROUND(SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) * 1.0 / COUNT(DISTINCT utc_date), 1) AS B2B_per_day,
        ROUND(SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) * 1.0 / COUNT(DISTINCT utc_date), 1) AS B2C_per_day,
        ROUND(SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) * 1.0 / COUNT(DISTINCT utc_date), 1) AS C2B_per_day,
        ROUND(SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) * 1.0 / COUNT(DISTINCT utc_date), 1) AS C2C_per_day,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_B,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_B,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS median_dur_sec
    FROM t
    GROUP BY 1, 2, 3
    ORDER BY 1;
    """
    print("--- Day-of-Week (UTC ISODOW 1=Mon..7=Sun) Daily Volume & Party Mix (Full 10M Rows) ---")
    print(con.execute(q_dow).df().to_string(index=False))

    # Internal Country Timezone Calibration & Local Hour Alignment
    q_internal_clock = """
    WITH country_peaks AS (
        SELECT
            SUBSTR(ORDERING_BIC8, 5, 2) AS country,
            COUNT(*) AS country_ord_tx,
            MODE(CASE WHEN ORDERING_TYPE = 'B' THEN EXTRACT('hour' FROM TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC') END) AS modal_utc_hr_B,
            MODE(CASE WHEN ORDERING_TYPE = 'C' THEN EXTRACT('hour' FROM TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC') END) AS modal_utc_hr_C
        FROM payments
        GROUP BY 1
    ),
    aligned AS (
        SELECT
            p.ORDERING_TYPE,
            p.BENEFICIARY_TYPE,
            p.USD_AMOUNT,
            p.TOTAL_DURATION,
            cp.country_ord_tx,
            -- Align each country's clock so that its Business (B) peak UTC hour maps to 16:00 internal local time
            MOD(CAST(EXTRACT('hour' FROM TO_TIMESTAMP(p.EPOCH_SECONDS) AT TIME ZONE 'UTC') - cp.modal_utc_hr_B + 16 + 24 AS INTEGER), 24) AS internal_local_hour
        FROM payments p
        JOIN country_peaks cp ON SUBSTR(p.ORDERING_BIC8, 5, 2) = cp.country
    )
    SELECT
        internal_local_hour,
        COUNT(*) AS total_tx,
        SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) AS ord_B_tx,
        SUM(CASE WHEN ORDERING_TYPE = 'C' THEN 1 ELSE 0 END) AS ord_C_tx,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) / SUM(SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END)) OVER (), 2) AS pct_of_all_B_day,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'C' THEN 1 ELSE 0 END) / SUM(SUM(CASE WHEN ORDERING_TYPE = 'C' THEN 1 ELSE 0 END)) OVER (), 2) AS pct_of_all_C_day,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'C' THEN 1 ELSE 0 END) / COUNT(*), 2) AS share_C_within_hour,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd
    FROM aligned
    GROUP BY 1
    ORDER BY 1;
    """
    print("\n--- Internally Calibrated Local Clock (0..23, anchored on Country Modal B Peak = 16:00) Across All 10M Rows ---")
    print(con.execute(q_internal_clock).df().to_string(index=False))

    # =========================================================================
    # GROUP 2 & 3: AMOUNT, CURRENCY & PARTY TYPE RULES (FULL 10M ROWS)
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 2 & 3: USD_AMOUNT, CURRENCY REGIMES & PARTY TYPE FLOWS (FULL 10M ROWS)")
    print("=" * 110)

    q_amt_corridor_curr = """
    WITH modal_curr AS (
        SELECT
            SUBSTR(ORDERING_BIC8, 5, 2) AS country,
            MODE(CURRENCY_CODE) AS home_curr
        FROM payments
        GROUP BY 1
    ),
    enriched AS (
        SELECT
            p.ORDERING_TYPE || '2' || p.BENEFICIARY_TYPE AS party_flow,
            SUBSTR(p.ORDERING_BIC8, 5, 2) AS ord_country,
            SUBSTR(p.BENEFICIARY_BIC8, 5, 2) AS ben_country,
            CASE WHEN SUBSTR(p.ORDERING_BIC8, 5, 2) = SUBSTR(p.BENEFICIARY_BIC8, 5, 2)
                 THEN 'Domestic (Same Country)'
                 ELSE 'Cross-Border'
            END AS corridor_scope,
            CASE
                WHEN p.CURRENCY_CODE = mo.home_curr AND p.CURRENCY_CODE = mb.home_curr THEN '1_Both_Home_Curr'
                WHEN p.CURRENCY_CODE = mo.home_curr THEN '2_Sender_Home_Curr'
                WHEN p.CURRENCY_CODE = mb.home_curr THEN '3_Receiver_Home_Curr'
                ELSE '4_Third_Vehicle_Curr'
            END AS currency_regime,
            p.CURRENCY_CONVERSION_COUNT,
            p.TRANSACTION_TYPE_CODE,
            p.PARTICIPANT_COUNT,
            p.USD_AMOUNT,
            p.TOTAL_DURATION
        FROM payments p
        LEFT JOIN modal_curr mo ON SUBSTR(p.ORDERING_BIC8, 5, 2) = mo.country
        LEFT JOIN modal_curr mb ON SUBSTR(p.BENEFICIARY_BIC8, 5, 2) = mb.country
        WHERE p.ANOMALY_TYPE IS NULL
    )
    SELECT
        party_flow,
        corridor_scope,
        currency_regime,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_normal,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(AVG(CURRENCY_CONVERSION_COUNT), 2) AS mean_fx_cnt,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Direct' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Direct,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Indirect' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Indirect,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Covered' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Covered
    FROM enriched
    GROUP BY 1, 2, 3
    ORDER BY 1, 2, 3;
    """
    print("--- Party Flow x Domestic/Cross-Border x Internal Currency Regime (Normal Traffic, Full 10M Rows) ---")
    print(con.execute(q_amt_corridor_curr).df().to_string(index=False))

    # Check exact relationship between Currency Regime and CURRENCY_CONVERSION_COUNT!
    q_curr_regime_fx = """
    WITH modal_curr AS (
        SELECT SUBSTR(ORDERING_BIC8, 5, 2) AS country, MODE(CURRENCY_CODE) AS home_curr
        FROM payments GROUP BY 1
    ),
    enriched AS (
        SELECT
            CASE WHEN SUBSTR(p.ORDERING_BIC8, 5, 2) = SUBSTR(p.BENEFICIARY_BIC8, 5, 2)
                 THEN 'Domestic' ELSE 'Cross-Border' END AS scope,
            CASE
                WHEN p.CURRENCY_CODE = mo.home_curr AND p.CURRENCY_CODE = mb.home_curr THEN '1_Both_Home_Curr'
                WHEN p.CURRENCY_CODE = mo.home_curr THEN '2_Sender_Home_Curr'
                WHEN p.CURRENCY_CODE = mb.home_curr THEN '3_Receiver_Home_Curr'
                ELSE '4_Third_Vehicle_Curr'
            END AS currency_regime,
            p.TRANSACTION_TYPE_CODE,
            p.PARTICIPANT_COUNT,
            p.CURRENCY_CONVERSION_COUNT,
            p.USD_AMOUNT,
            p.TOTAL_DURATION
        FROM payments p
        LEFT JOIN modal_curr mo ON SUBSTR(p.ORDERING_BIC8, 5, 2) = mo.country
        LEFT JOIN modal_curr mb ON SUBSTR(p.BENEFICIARY_BIC8, 5, 2) = mb.country
    )
    SELECT
        scope,
        currency_regime,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_all,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS med_usd,
        ROUND(AVG(CURRENCY_CONVERSION_COUNT), 3) AS avg_fx_cnt,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_0,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_1,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_2plus,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Direct' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Direct,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Indirect' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Indirect,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Covered' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Covered
    FROM enriched
    GROUP BY 1, 2
    ORDER BY 1, 2;
    """
    print("\n--- Currency Regime vs FX Conversion Count & Routing Category (Full 10M Rows) ---")
    print(con.execute(q_curr_regime_fx).df().to_string(index=False))

    # =========================================================================
    # GROUP 4: ROUTING, COVER PAYMENTS & TOTAL_DURATION MECHANICS
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 4: ROUTING TRIGGERS (DIRECT VS INDIRECT VS COVERED) & TOTAL_DURATION MODEL")
    print("=" * 110)

    # Check what intermediary countries appear in BIC8_PATH for Covered vs Indirect!
    q_cover_vs_indirect = """
    WITH modal_curr AS (
        SELECT SUBSTR(ORDERING_BIC8, 5, 2) AS country, MODE(CURRENCY_CODE) AS home_curr
        FROM payments GROUP BY 1
    ),
    mhop AS (
        SELECT
            p.TRANSACTION_TYPE_CODE,
            p.CONTINUITY_QFLAG,
            p.PARTICIPANT_COUNT,
            p.CURRENCY_CONVERSION_COUNT,
            p.CURRENCY_CODE,
            SUBSTR(p.ORDERING_BIC8, 5, 2) AS ord_c,
            SUBSTR(p.BENEFICIARY_BIC8, 5, 2) AS ben_c,
            SUBSTR(SPLIT_PART(p.BIC8_PATH, ';', 2), 5, 2) AS hop2_c,
            mo.home_curr AS ord_curr,
            mb.home_curr AS ben_curr,
            p.USD_AMOUNT,
            p.TOTAL_DURATION
        FROM payments p
        LEFT JOIN modal_curr mo ON SUBSTR(p.ORDERING_BIC8, 5, 2) = mo.country
        LEFT JOIN modal_curr mb ON SUBSTR(p.BENEFICIARY_BIC8, 5, 2) = mb.country
        WHERE p.PARTICIPANT_COUNT >= 3
    )
    SELECT
        TRANSACTION_TYPE_CODE,
        COUNT(*) AS n_tx,
        ROUND(100.0 * SUM(CASE WHEN ord_c = ben_c THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_domestic,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CODE = ord_curr AND CURRENCY_CODE = ben_curr THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_both_home_curr,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CODE = ord_curr AND CURRENCY_CODE != ben_curr THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_home_only,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CODE != ord_curr AND CURRENCY_CODE = ben_curr THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_home_only,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CODE != ord_curr AND CURRENCY_CODE != ben_curr THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_third_curr,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_0,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_1,
        ROUND(100.0 * SUM(CASE WHEN CURRENCY_CONVERSION_COUNT >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fx_2plus,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS med_usd,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS med_dur_sec,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_dur_sec
    FROM mhop
    GROUP BY 1;
    """
    print("--- Multi-Hop (PARTICIPANT_COUNT >= 3): Covered vs Indirect Breakdown (Full 10M Rows) ---")
    print(con.execute(q_cover_vs_indirect).df().to_string(index=False))

    # Check if Covered rate scales with USD_AMOUNT brackets or specific currencies!
    q_cover_by_amount = """
    SELECT
        CASE
            WHEN USD_AMOUNT < 100 THEN '1_<100'
            WHEN USD_AMOUNT < 1000 THEN '2_100-1k'
            WHEN USD_AMOUNT < 10000 THEN '3_1k-10k'
            WHEN USD_AMOUNT < 100000 THEN '4_10k-100k'
            WHEN USD_AMOUNT < 1000000 THEN '5_100k-1M'
            ELSE '6_>=1M'
        END AS usd_bracket,
        COUNT(*) AS total_tx,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Direct' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Direct,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Indirect' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Indirect,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Covered' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Covered,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Covered' THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN TRANSACTION_TYPE_CODE IN ('Indirect', 'Covered') THEN 1 ELSE 0 END), 0), 2) AS share_Covered_of_multihop,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS med_dur_sec,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_dur_sec
    FROM payments
    GROUP BY 1
    ORDER BY 1;
    """
    print("\n--- Routing & Duration across USD_AMOUNT Brackets (Full 10M Rows) ---")
    print(con.execute(q_cover_by_amount).df().to_string(index=False))

    # =========================================================================
    # GROUP 5: TOKEN & TEXT STRUCTURE RULES (FULL 10M ROWS)
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 5: PARTY DETAILS & TOKEN STRUCTURE RULES (FULL 10M ROWS)")
    print("=" * 110)

    q_tokens_party = """
    SELECT
        ORDERING_TYPE,
        BENEFICIARY_TYPE,
        COUNT(*) AS n_tx,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<iban:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_iban,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<iban:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_iban,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<business:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_business,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<business:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_business,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<company_keyword:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_comp_kw,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<company_keyword:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_comp_kw,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<first_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_fname,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<first_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_fname,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<last_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_lname,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<last_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_lname,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<finance_word:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_fin_word,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<finance_word:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_fin_word
    FROM payments
    GROUP BY 1, 2
    ORDER BY 1, 2;
    """
    print("--- Token Tag Prevalence by ORDERING_TYPE x BENEFICIARY_TYPE (Full 10M Rows) ---")
    print(con.execute(q_tokens_party).df().to_string(index=False))

    # Check how <iban:>, <street:>, <city:>, <country_code:>, <finance_word:> affect TOTAL_DURATION!
    q_tokens_duration = """
    SELECT
        ORDERING_TOKENS LIKE '%<iban:%' AS ord_has_iban,
        BENEFICIARY_TOKENS LIKE '%<iban:%' AS ben_has_iban,
        BENEFICIARY_TOKENS LIKE '%<street:%' AS ben_has_street,
        BENEFICIARY_TOKENS LIKE '%<country_code:%' OR BENEFICIARY_TOKENS LIKE '%<country_name:%' AS ben_has_country,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_total,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS med_dur_sec,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_dur_sec,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS med_usd,
        ROUND(100.0 * SUM(CASE WHEN CONTINUITY_QFLAG = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_qflag_Y
    FROM payments
    WHERE ANOMALY_TYPE IS NULL
    GROUP BY 1, 2, 3, 4
    ORDER BY n_tx DESC;
    """
    print("\n--- Impact of IBAN, Street & Country Tokens on TOTAL_DURATION & CONTINUITY_QFLAG (Full 10M Normal Rows) ---")
    print(con.execute(q_tokens_duration).df().to_string(index=False))

    # Check Token Tag Prevalence across all 6 ANOMALY_TYPEs!
    q_tokens_anomaly = """
    SELECT
        COALESCE(ANOMALY_TYPE, 'NONE (Normal)') AS anomaly_type,
        COUNT(*) AS n_tx,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<iban:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ord_iban,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<iban:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ben_iban,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<business:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ord_bus,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<business:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ben_bus,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<first_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ord_fname,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<first_name:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ben_fname,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<street:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ord_street,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<street:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ben_street,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TOKENS LIKE '%<finance_word:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ord_fin_w,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TOKENS LIKE '%<finance_word:%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS ben_fin_w,
        ROUND(AVG(LENGTH(ORDERING_TOKENS)), 1) AS avg_ord_tok_len,
        ROUND(AVG(LENGTH(BENEFICIARY_TOKENS)), 1) AS avg_ben_tok_len
    FROM payments
    GROUP BY 1
    ORDER BY n_tx DESC;
    """
    print("\n--- Token Tag Prevalence Across All 6 ANOMALY_TYPEs (Full 10M Rows) ---")
    print(con.execute(q_tokens_anomaly).df().to_string(index=False))

    # =========================================================================
    # GROUP 6 & 7: ACCOUNT GRAPH, INTER-TX DELTAS & ALL 6 ANOMALIES (FULL 10M ROWS)
    # =========================================================================
    print("\n" + "=" * 110)
    print("GROUP 6 & 7: ACCOUNT VELOCITY, FAN-OUT, INTER-TX DELTAS & ANOMALY SIGNATURES (FULL 10M ROWS)")
    print("=" * 110)

    # Step 1: Build compact per-sender summary table across all 10,000,000 rows (~400k unique accounts, fits in ~20MB RAM)
    con.execute("""
    CREATE TEMP TABLE sender_stats AS
    SELECT
        ORDERING_ACCOUNT,
        ANY_VALUE(ORDERING_TYPE) AS ORDERING_TYPE,
        COUNT(*) AS sender_total_tx,
        COUNT(DISTINCT BENEFICIARY_ACCOUNT) AS sender_ben_fanout,
        MEDIAN(USD_AMOUNT) AS sender_median_usd,
        AVG(USD_AMOUNT) AS sender_mean_usd,
        SUM(CASE WHEN ANOMALY_TYPE IS NOT NULL THEN 1 ELSE 0 END) AS sender_anom_cnt
    FROM payments
    GROUP BY ORDERING_ACCOUNT;
    """)

    q_fanout = """
    SELECT
        ORDERING_TYPE,
        sender_anom_cnt > 0 AS has_any_anomaly,
        COUNT(*) AS n_unique_senders,
        ROUND(AVG(sender_total_tx), 2) AS mean_tx_per_sender,
        ROUND(MEDIAN(sender_total_tx), 1) AS med_tx_per_sender,
        ROUND(MAX(sender_total_tx), 0) AS max_tx_per_sender,
        ROUND(AVG(sender_ben_fanout), 2) AS mean_ben_fanout,
        ROUND(MEDIAN(sender_ben_fanout), 1) AS med_ben_fanout,
        ROUND(MAX(sender_ben_fanout), 0) AS max_ben_fanout
    FROM sender_stats
    GROUP BY 1, 2
    ORDER BY 1, 2;
    """
    print("--- Per-Sender Account Volume & Beneficiary Fan-Out by ORDERING_TYPE & Anomaly Involvement (Full 10M Rows) ---")
    print(con.execute(q_fanout).df().to_string(index=False))

    # Step 2: Extract 100% of all transactions from every sender account that ever had an anomaly,
    # plus a 5% hash sample of normal sender accounts, into an in-memory temp table (~550k rows, <60MB RAM, zero disk spill)
    con.execute("""
    CREATE TEMP TABLE tracked_tx AS
    SELECT
        p.EPOCH_SECONDS,
        p.CURRENCY_CODE,
        p.USD_AMOUNT,
        p.ORDERING_BIC8,
        p.BENEFICIARY_BIC8,
        p.TOTAL_DURATION,
        p.CONTINUITY_QFLAG,
        p.CURRENCY_CONVERSION_COUNT,
        p.PARTICIPANT_COUNT,
        p.TRANSACTION_TYPE_CODE,
        p.ORDERING_ACCOUNT,
        p.BENEFICIARY_ACCOUNT,
        p.ORDERING_DETAILS,
        p.BENEFICIARY_DETAILS,
        p.ORDERING_TOKENS,
        p.BENEFICIARY_TOKENS,
        p.ORDERING_TYPE,
        p.BENEFICIARY_TYPE,
        p.ANOMALY_TYPE,
        sb.sender_total_tx,
        sb.sender_ben_fanout,
        sb.sender_median_usd,
        sb.sender_anom_cnt
    FROM payments p
    JOIN sender_stats sb ON p.ORDERING_ACCOUNT = sb.ORDERING_ACCOUNT
    WHERE sb.sender_anom_cnt > 0 OR (HASH(p.ORDERING_ACCOUNT) % 20 = 0);
    """)

    q_acct_anomalies = """
    WITH acct_window AS (
        SELECT
            *,
            COUNT(*) OVER (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT) AS pair_total_tx,
            -- Inter-transaction time deltas for same sender
            EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_tx_gap_sec_sender,
            LEAD(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) - EPOCH_SECONDS AS next_tx_gap_sec_sender,
            -- Inter-transaction time deltas for same (sender, beneficiary) pair
            EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_tx_gap_sec_pair,
            -- Previous / next amount for same sender
            LAG(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_usd_sender,
            LEAD(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_usd_sender,
            -- Previous / next amount for same pair
            LAG(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_usd_pair,
            -- Previous / next beneficiary account & details for same sender
            LAG(BENEFICIARY_ACCOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_ben_acct_sender,
            LEAD(BENEFICIARY_ACCOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_ben_acct_sender,
            LAG(BENEFICIARY_DETAILS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_ben_details_sender,
            -- Previous / next anomaly type for same sender
            LAG(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_anom_sender,
            LEAD(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_anom_sender
        FROM tracked_tx
    )
    SELECT
        COALESCE(ANOMALY_TYPE, 'NONE (Normal)') AS anomaly_category,
        COUNT(*) AS n_tx,
        ROUND(MEDIAN(sender_total_tx), 1) AS med_sender_tx_cnt,
        ROUND(MEDIAN(sender_ben_fanout), 1) AS med_sender_fanout,
        ROUND(MEDIAN(pair_total_tx), 1) AS med_pair_tx_cnt,
        ROUND(MEDIAN(USD_AMOUNT / NULLIF(sender_median_usd, 0)), 2) AS med_ratio_to_sender_med_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT / NULLIF(sender_median_usd, 0), 0.25), 2) AS p25_ratio_sender_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT / NULLIF(sender_median_usd, 0), 0.75), 2) AS p75_ratio_sender_usd,
        ROUND(MEDIAN(prev_tx_gap_sec_sender), 1) AS med_prev_gap_sender_sec,
        ROUND(MEDIAN(prev_tx_gap_sec_pair), 1) AS med_prev_gap_pair_sec,
        ROUND(100.0 * SUM(CASE WHEN ABS(USD_AMOUNT - prev_usd_sender) < 0.01 OR ABS(USD_AMOUNT - next_usd_sender) < 0.01 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_exact_same_usd_adj_tx,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_ACCOUNT = prev_ben_acct_sender THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_same_ben_as_prev_tx,
        ROUND(100.0 * SUM(CASE WHEN prev_anom_sender IS NOT NULL OR next_anom_sender IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_adj_tx_also_anomaly
    FROM acct_window
    GROUP BY 1
    ORDER BY n_tx DESC;
    """
    print("\n--- Account Graph, Velocity, Amount Multiplier & Sequence Signatures Across All 6 Anomalies (Full 10M History) ---")
    print(con.execute(q_acct_anomalies).df().to_string(index=False))

    q_anom_pairs = """
    WITH acct_seq AS (
        SELECT
            ORDERING_ACCOUNT,
            BENEFICIARY_ACCOUNT,
            EPOCH_SECONDS,
            USD_AMOUNT,
            CURRENCY_CODE,
            TOTAL_DURATION,
            ORDERING_TYPE,
            BENEFICIARY_TYPE,
            ANOMALY_TYPE,
            BENEFICIARY_DETAILS,
            LAG(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_anom,
            LEAD(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_anom,
            EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS gap_from_prev_sec,
            LEAD(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) - EPOCH_SECONDS AS gap_to_next_sec,
            LAG(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_usd,
            LEAD(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_usd,
            LAG(BENEFICIARY_ACCOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_ben_acct,
            LEAD(BENEFICIARY_ACCOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_ben_acct
        FROM tracked_tx
    )
    SELECT
        ANOMALY_TYPE,
        COALESCE(prev_anom, 'NONE') AS prev_tx_anomaly,
        COALESCE(next_anom, 'NONE') AS next_tx_anomaly,
        COUNT(*) AS n_cases,
        ROUND(MEDIAN(gap_from_prev_sec), 1) AS med_gap_prev_sec,
        ROUND(MEDIAN(gap_to_next_sec), 1) AS med_gap_next_sec,
        ROUND(100.0 * SUM(CASE WHEN ABS(USD_AMOUNT - prev_usd) < 0.01 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_eq_prev_usd,
        ROUND(100.0 * SUM(CASE WHEN ABS(USD_AMOUNT - next_usd) < 0.01 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_eq_next_usd,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_ACCOUNT = prev_ben_acct THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_eq_prev_ben,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_ACCOUNT = next_ben_acct THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_eq_next_ben
    FROM acct_seq
    WHERE ANOMALY_TYPE IS NOT NULL
    GROUP BY 1, 2, 3
    HAVING COUNT(*) >= 5
    ORDER BY 1, n_cases DESC;
    """
    print("\n--- Anomaly Sequential Transition Matrix (Same ORDERING_ACCOUNT Preceding/Succeeding Anomaly & Amount Match) ---")
    print(con.execute(q_anom_pairs).df().to_string(index=False))

    # Check Beneficiary-side (Receiver) Fan-In & Sequence for DUPLICATE_PAYMENT, ACCOUNT_REPLACEMENT_SCAM, ROMANCE_SCAM, CEO_SCAM, CUSTOMER_RECALL
    q_ben_side = """
    WITH ben_seq AS (
        SELECT
            ANOMALY_TYPE,
            ORDERING_ACCOUNT,
            BENEFICIARY_ACCOUNT,
            EPOCH_SECONDS,
            USD_AMOUNT,
            ORDERING_DETAILS,
            BENEFICIARY_DETAILS,
            COUNT(*) OVER (PARTITION BY BENEFICIARY_ACCOUNT) AS ben_rx_cnt,
            COUNT(DISTINCT ORDERING_ACCOUNT) OVER (PARTITION BY BENEFICIARY_ACCOUNT) AS ben_distinct_senders,
            EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER (PARTITION BY BENEFICIARY_ACCOUNT ORDER BY EPOCH_SECONDS) AS ben_prev_gap_sec,
            LAG(USD_AMOUNT) OVER (PARTITION BY BENEFICIARY_ACCOUNT ORDER BY EPOCH_SECONDS) AS ben_prev_usd,
            LAG(ORDERING_ACCOUNT) OVER (PARTITION BY BENEFICIARY_ACCOUNT ORDER BY EPOCH_SECONDS) AS ben_prev_ord_acct
        FROM tracked_tx
    )
    SELECT
        COALESCE(ANOMALY_TYPE, 'NONE (Normal)') AS anomaly_type,
        COUNT(*) AS n_tx,
        ROUND(MEDIAN(ben_rx_cnt), 1) AS med_ben_rx_cnt,
        ROUND(MEDIAN(ben_distinct_senders), 1) AS med_ben_distinct_senders,
        ROUND(MEDIAN(ben_prev_gap_sec), 1) AS med_ben_prev_gap_sec,
        ROUND(100.0 * SUM(CASE WHEN ABS(USD_AMOUNT - ben_prev_usd) < 0.01 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_eq_prev_usd,
        ROUND(100.0 * SUM(CASE WHEN ABS(USD_AMOUNT - ben_prev_usd) < 0.01 AND ORDERING_ACCOUNT != ben_prev_ord_acct THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_same_usd_diff_sender
    FROM ben_seq
    GROUP BY 1
    ORDER BY n_tx DESC;
    """
    print("\n--- Beneficiary-Side (Receiver) Fan-In & Same-Amount Repeat Signatures ---")
    print(con.execute(q_ben_side).df().to_string(index=False))

    # Print concrete example pairs for DUPLICATE_PAYMENT, ACCOUNT_REPLACEMENT_SCAM, FAT_FINGER_MISTAKE, CUSTOMER_RECALL
    q_examples = """
    WITH seq AS (
        SELECT
            EPOCH_SECONDS,
            ANOMALY_TYPE,
            ORDERING_TYPE || '2' || BENEFICIARY_TYPE AS flow,
            ORDERING_ACCOUNT,
            LAG(BENEFICIARY_ACCOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_ben_acct,
            BENEFICIARY_ACCOUNT,
            EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS gap_sec,
            LAG(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_usd,
            USD_AMOUNT,
            ROUND(USD_AMOUNT / NULLIF(LAG(USD_AMOUNT) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS), 0), 2) AS ratio_to_prev_usd,
            ROUND(USD_AMOUNT / NULLIF(sender_median_usd, 0), 2) AS ratio_to_med_usd,
            LAG(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS prev_anom,
            LEAD(ANOMALY_TYPE) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS) AS next_anom,
            REPLACE(SUBSTR(BENEFICIARY_DETAILS, 1, 60), CHR(10), ' | ') AS ben_details_snip,
            REPLACE(SUBSTR(LAG(BENEFICIARY_DETAILS) OVER (PARTITION BY ORDERING_ACCOUNT ORDER BY EPOCH_SECONDS), 1, 60), CHR(10), ' | ') AS prev_ben_details_snip
        FROM tracked_tx
    )
    SELECT *
    FROM seq
    WHERE ANOMALY_TYPE IN ('DUPLICATE_PAYMENT', 'ACCOUNT_REPLACEMENT_SCAM', 'FAT_FINGER_MISTAKE', 'CUSTOMER_RECALL', 'ROMANCE_SCAM', 'CEO_SCAM')
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ANOMALY_TYPE ORDER BY EPOCH_SECONDS) <= 4
    ORDER BY ANOMALY_TYPE, gap_sec;
    """
    print("\n--- Concrete Sequential Examples for All 6 Anomaly Categories ---")
    print(con.execute(q_examples).df().to_string(index=False))

    # Check Cross-Scam Shared Money Mule Network across ROMANCE_SCAM, CEO_SCAM, ACCOUNT_REPLACEMENT_SCAM
    q_mule_network = """
    WITH mule_accts AS (
        SELECT
            BENEFICIARY_ACCOUNT,
            SUM(CASE WHEN ANOMALY_TYPE = 'ROMANCE_SCAM' THEN 1 ELSE 0 END) AS r_cnt,
            SUM(CASE WHEN ANOMALY_TYPE = 'CEO_SCAM' THEN 1 ELSE 0 END) AS c_cnt,
            SUM(CASE WHEN ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM' THEN 1 ELSE 0 END) AS a_cnt
        FROM payments
        WHERE ANOMALY_TYPE IN ('ROMANCE_SCAM', 'CEO_SCAM', 'ACCOUNT_REPLACEMENT_SCAM')
        GROUP BY 1
    )
    SELECT
        r_cnt > 0 AS in_romance_scam,
        c_cnt > 0 AS in_ceo_scam,
        a_cnt > 0 AS in_acct_replacement_scam,
        COUNT(*) AS n_unique_mule_accounts,
        SUM(r_cnt) AS romance_tx,
        SUM(c_cnt) AS ceo_tx,
        SUM(a_cnt) AS acct_rep_tx,
        SUM(r_cnt + c_cnt + a_cnt) AS total_fraud_tx
    FROM mule_accts
    GROUP BY 1, 2, 3
    ORDER BY n_unique_mule_accounts DESC;
    """
    print("\n--- Shared Cross-Scam Money Mule Network (ROMANCE_SCAM, CEO_SCAM, ACCOUNT_REPLACEMENT_SCAM) across Full 10M Rows ---")
    print(con.execute(q_mule_network).df().to_string(index=False))

    # Check Exact Duplicate Payment Cluster Invariants across Full 10M Rows
    q_dup_clusters = """
    WITH dup_clusters AS (
        SELECT
            ORDERING_ACCOUNT,
            BENEFICIARY_ACCOUNT,
            ROUND(USD_AMOUNT, 2) AS usd_amt,
            CURRENCY_CODE,
            COUNT(*) AS cluster_size,
            COUNT(DISTINCT TOTAL_DURATION) AS dist_durations,
            COUNT(DISTINCT BIC8_PATH) AS dist_paths,
            MIN(EPOCH_SECONDS) AS first_epoch,
            MAX(EPOCH_SECONDS) AS last_epoch,
            MAX(EPOCH_SECONDS) - MIN(EPOCH_SECONDS) AS total_span_sec
        FROM payments
        WHERE ANOMALY_TYPE = 'DUPLICATE_PAYMENT'
        GROUP BY 1, 2, 3, 4
    )
    SELECT
        cluster_size,
        COUNT(*) AS n_clusters,
        SUM(cluster_size) AS total_dup_rows,
        SUM(CASE WHEN dist_durations = 1 AND dist_paths = 1 THEN 1 ELSE 0 END) AS clusters_with_identical_dur_and_path,
        ROUND(MEDIAN(total_span_sec), 1) AS med_cluster_span_sec,
        ROUND(AVG(total_span_sec), 1) AS mean_cluster_span_sec
    FROM dup_clusters
    GROUP BY 1
    ORDER BY 1;
    """
    print("\n--- DUPLICATE_PAYMENT Exact Cluster Structure (Identical Sender, Receiver, Amount, Duration & Path) ---")
    print(con.execute(q_dup_clusters).df().to_string(index=False))


def main():
    t0 = time.time()
    print("=" * 110)
    print("UMDAC DATATHON 2026 — DEEP CAUSAL RULE MINING & 10M-ROW SQL VERIFICATION")
    print("COMPLIANCE MODE: 100% INTERNAL DATASET FEATURES ONLY (NO EXTERNAL TABLES/APIs)")
    print("=" * 110)

    run_sample_decision_trees_and_token_discovery()
    run_full_10m_duckdb_verification()

    print("\n" + "=" * 110)
    print(f"ALL DEEP RULE MINING & 10M VERIFICATION QUERIES COMPLETED IN {time.time() - t0:.1f} SECONDS.")
    print("=" * 110)


if __name__ == "__main__":
    main()
