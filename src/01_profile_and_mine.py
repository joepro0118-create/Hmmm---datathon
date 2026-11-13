import os
import time
import duckdb
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 80)

# STRICT COMPLIANCE: Use ONLY the raw dataset provided by Swift.
# Zero external CSVs, GDP tables, timezone files, or external APIs.
CSV_PATH = r"C:\Users\Joe\Downloads\swift_umdac_datathon_2026_fictitious_payment_data\swift_umdac_datathon_2026_fictitious_payment_data.csv"
SAMPLE_PARQUET_PATH = r"c:\Users\Joe\OneDrive\Desktop\Hmmm-datathon\data\sample_200k.parquet"


def main():
    t0 = time.time()
    print("=" * 100)
    print("UMDAC DATATHON 2026 — SWIFT PAYMENTS 4GB DATASET PROFILER & ARCHETYPE MINER")
    print("COMPLIANCE MODE: 100% INTERNAL DATASET FEATURES ONLY (NO EXTERNAL TABLES/APIs)")
    print("=" * 100)

    con = duckdb.connect()
    con.execute("SET memory_limit = '4GB';")
    con.execute("SET preserve_insertion_order = false;")

    csv_sql_path = CSV_PATH.replace("\\", "/")
    sample_sql_path = SAMPLE_PARQUET_PATH.replace("\\", "/")

    # Create lazy view over the 4GB CSV
    con.execute(f"CREATE VIEW payments AS SELECT * FROM read_csv_auto('{csv_sql_path}', sample_size=100000);")

    # -------------------------------------------------------------------------
    # SECTION 1: SCHEMA, ROW COUNT, NULL RATES & SUMMARY STATS (ALL 20 COLUMNS)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("1. DATASET SCHEMA & SAMPLE ROWS")
    print("=" * 100)
    schema_df = con.execute("DESCRIBE payments;").df()
    print(schema_df.to_string(index=False))

    print("\n--- First 3 Rows (Transposed) ---")
    head_df = con.execute("SELECT * FROM payments LIMIT 3;").df()
    print(head_df.T)

    print("\n" + "=" * 100)
    print("1B. FULL-DATASET ROW COUNT, NULL RATES & SUMMARY STATS ACROSS ALL 20 COLUMNS")
    print("=" * 100)
    summary_query = """
    SELECT
        COUNT(*) AS total_rows,
        -- Null counts across all 20 columns (+ DISCLAIMER)
        COUNT(*) - COUNT(DISCLAIMER) AS null_DISCLAIMER,
        COUNT(*) - COUNT(EPOCH_SECONDS) AS null_EPOCH_SECONDS,
        COUNT(*) - COUNT(CURRENCY_CODE) AS null_CURRENCY_CODE,
        COUNT(*) - COUNT(USD_AMOUNT) AS null_USD_AMOUNT,
        COUNT(*) - COUNT(ORDERING_BIC8) AS null_ORDERING_BIC8,
        COUNT(*) - COUNT(BENEFICIARY_BIC8) AS null_BENEFICIARY_BIC8,
        COUNT(*) - COUNT(BIC8_PATH) AS null_BIC8_PATH,
        COUNT(*) - COUNT(TOTAL_DURATION) AS null_TOTAL_DURATION,
        COUNT(*) - COUNT(CONTINUITY_QFLAG) AS null_CONTINUITY_QFLAG,
        COUNT(*) - COUNT(CURRENCY_CONVERSION_COUNT) AS null_CURRENCY_CONVERSION_COUNT,
        COUNT(*) - COUNT(PARTICIPANT_COUNT) AS null_PARTICIPANT_COUNT,
        COUNT(*) - COUNT(TRANSACTION_TYPE_CODE) AS null_TRANSACTION_TYPE_CODE,
        COUNT(*) - COUNT(ORDERING_ACCOUNT) AS null_ORDERING_ACCOUNT,
        COUNT(*) - COUNT(BENEFICIARY_ACCOUNT) AS null_BENEFICIARY_ACCOUNT,
        COUNT(*) - COUNT(ORDERING_DETAILS) AS null_ORDERING_DETAILS,
        COUNT(*) - COUNT(ORDERING_TOKENS) AS null_ORDERING_TOKENS,
        COUNT(*) - COUNT(BENEFICIARY_DETAILS) AS null_BENEFICIARY_DETAILS,
        COUNT(*) - COUNT(BENEFICIARY_TOKENS) AS null_BENEFICIARY_TOKENS,
        COUNT(*) - COUNT(ORDERING_TYPE) AS null_ORDERING_TYPE,
        COUNT(*) - COUNT(BENEFICIARY_TYPE) AS null_BENEFICIARY_TYPE,
        COUNT(*) - COUNT(ANOMALY_TYPE) AS null_ANOMALY_TYPE,

        -- Numeric summary stats
        MIN(EPOCH_SECONDS) AS min_epoch,
        MAX(EPOCH_SECONDS) AS max_epoch,
        TO_TIMESTAMP(MIN(EPOCH_SECONDS)) AT TIME ZONE 'UTC' AS min_utc_time,
        TO_TIMESTAMP(MAX(EPOCH_SECONDS)) AT TIME ZONE 'UTC' AS max_utc_time,

        MIN(USD_AMOUNT) AS min_usd,
        QUANTILE_CONT(USD_AMOUNT, 0.25) AS p25_usd,
        MEDIAN(USD_AMOUNT) AS median_usd,
        QUANTILE_CONT(USD_AMOUNT, 0.75) AS p75_usd,
        QUANTILE_CONT(USD_AMOUNT, 0.99) AS p99_usd,
        MAX(USD_AMOUNT) AS max_usd,
        AVG(USD_AMOUNT) AS mean_usd,
        STDDEV(USD_AMOUNT) AS std_usd,

        MIN(TOTAL_DURATION) AS min_duration,
        MEDIAN(TOTAL_DURATION) AS median_duration,
        AVG(TOTAL_DURATION) AS mean_duration,
        MAX(TOTAL_DURATION) AS max_duration,

        MIN(CURRENCY_CONVERSION_COUNT) AS min_fx_cnt,
        AVG(CURRENCY_CONVERSION_COUNT) AS mean_fx_cnt,
        MAX(CURRENCY_CONVERSION_COUNT) AS max_fx_cnt,

        MIN(PARTICIPANT_COUNT) AS min_part_cnt,
        AVG(PARTICIPANT_COUNT) AS mean_part_cnt,
        MAX(PARTICIPANT_COUNT) AS max_part_cnt,

        -- Approximate distinct counts for categorical/string columns
        APPROX_COUNT_DISTINCT(CURRENCY_CODE) AS approx_dist_currency,
        APPROX_COUNT_DISTINCT(ORDERING_BIC8) AS approx_dist_ord_bic8,
        APPROX_COUNT_DISTINCT(BENEFICIARY_BIC8) AS approx_dist_ben_bic8,
        APPROX_COUNT_DISTINCT(BIC8_PATH) AS approx_dist_bic8_path,
        APPROX_COUNT_DISTINCT(CONTINUITY_QFLAG) AS approx_dist_qflag,
        APPROX_COUNT_DISTINCT(TRANSACTION_TYPE_CODE) AS approx_dist_tx_type,
        APPROX_COUNT_DISTINCT(ORDERING_ACCOUNT) AS approx_dist_ord_acct,
        APPROX_COUNT_DISTINCT(BENEFICIARY_ACCOUNT) AS approx_dist_ben_acct,
        APPROX_COUNT_DISTINCT(ORDERING_DETAILS) AS approx_dist_ord_details,
        APPROX_COUNT_DISTINCT(ORDERING_TOKENS) AS approx_dist_ord_tokens,
        APPROX_COUNT_DISTINCT(BENEFICIARY_DETAILS) AS approx_dist_ben_details,
        APPROX_COUNT_DISTINCT(BENEFICIARY_TOKENS) AS approx_dist_ben_tokens,
        APPROX_COUNT_DISTINCT(ORDERING_TYPE) AS approx_dist_ord_type,
        APPROX_COUNT_DISTINCT(BENEFICIARY_TYPE) AS approx_dist_ben_type,
        APPROX_COUNT_DISTINCT(ANOMALY_TYPE) AS approx_dist_anomaly_type
    FROM payments;
    """
    t_s1 = time.time()
    s1_df = con.execute(summary_query).df()
    total_rows = int(s1_df['total_rows'].iloc[0])
    print(f"Total Row Count: {total_rows:,} (computed in {time.time() - t_s1:.1f}s)\n")

    cols_20 = [
        "EPOCH_SECONDS", "CURRENCY_CODE", "USD_AMOUNT", "ORDERING_BIC8", "BENEFICIARY_BIC8",
        "BIC8_PATH", "TOTAL_DURATION", "CONTINUITY_QFLAG", "CURRENCY_CONVERSION_COUNT",
        "PARTICIPANT_COUNT", "TRANSACTION_TYPE_CODE", "ORDERING_ACCOUNT", "BENEFICIARY_ACCOUNT",
        "ORDERING_DETAILS", "ORDERING_TOKENS", "BENEFICIARY_DETAILS", "BENEFICIARY_TOKENS",
        "ORDERING_TYPE", "BENEFICIARY_TYPE", "ANOMALY_TYPE"
    ]
    print("--- Null Counts & Null Rates Across All 20 Appendix A.1 Columns ---")
    for c in cols_20:
        n_null = int(s1_df[f"null_{c}"].iloc[0])
        pct_null = 100.0 * n_null / total_rows
        print(f"  {c:<28} : {n_null:>12,} nulls ({pct_null:6.2f}%)")

    # -------------------------------------------------------------------------
    # SECTION 2: SENDER/RECEIVER ISO COUNTRIES & HANDOUT ARCHETYPE TESTS
    # (100% DERIVED FROM THE 20 COLUMNS INSIDE SWIFT'S DATASET)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("2A. ARCHETYPE TEST 1: CURRENCY CODE PATTERNS & FX CONVERSIONS VS. USD_AMOUNT")
    print("=" * 100)
    q_currency_pattern = """
    SELECT
        CASE WHEN SUBSTR(UPPER(CURRENCY_CODE), 1, 1) IN ('A', 'E', 'I', 'O', 'U')
             THEN 'Vowel (A,E,I,O,U)'
             ELSE 'Consonant'
        END AS first_letter_type,
        LENGTH(CURRENCY_CODE) AS curr_code_len,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_tx,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.25), 2) AS p25_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.75), 2) AS p75_usd,
        ROUND(STDDEV(USD_AMOUNT), 2) AS std_usd
    FROM payments
    WHERE CURRENCY_CODE IS NOT NULL
    GROUP BY 1, 2
    ORDER BY 1, 2;
    """
    print("--- First Letter (Consonant vs. Vowel) & Length of CURRENCY_CODE vs. USD_AMOUNT ---")
    print(con.execute(q_currency_pattern).df().to_string(index=False))

    q_top_currencies = """
    SELECT
        CURRENCY_CODE,
        CASE WHEN SUBSTR(UPPER(CURRENCY_CODE), 1, 1) IN ('A', 'E', 'I', 'O', 'U') THEN 'Vowel' ELSE 'Consonant' END AS first_char,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_tx,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.75), 2) AS p75_usd,
        ROUND(AVG(CURRENCY_CONVERSION_COUNT), 3) AS avg_fx_conversions
    FROM payments
    GROUP BY 1, 2
    ORDER BY n_tx DESC
    LIMIT 25;
    """
    print("\n--- Top 25 Currencies by Volume & USD_AMOUNT Stats ---")
    print(con.execute(q_top_currencies).df().to_string(index=False))

    q_fx_vs_usd = """
    SELECT
        CURRENCY_CONVERSION_COUNT,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_tx,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.25), 2) AS p25_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.75), 2) AS p75_usd,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_duration_sec,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS median_duration_sec,
        ROUND(AVG(PARTICIPANT_COUNT), 2) AS mean_participants
    FROM payments
    GROUP BY 1
    ORDER BY 1;
    """
    print("\n--- CURRENCY_CONVERSION_COUNT vs. USD_AMOUNT, TOTAL_DURATION & PARTICIPANT_COUNT ---")
    print(con.execute(q_fx_vs_usd).df().to_string(index=False))

    print("\n" + "=" * 100)
    print("2B. SENDER & RECEIVER BIC8 COUNTRIES (SUBSTR(BIC8, 5, 2)) & UTC HOUR DISTRIBUTIONS")
    print("    (Derived strictly from ORDERING_BIC8, BENEFICIARY_BIC8, EPOCH_SECONDS, ORDERING_TYPE, BENEFICIARY_TYPE)")
    print("=" * 100)
    q_countries = """
    WITH c_ext AS (
        SELECT
            SUBSTR(ORDERING_BIC8, 5, 2) AS ord_country,
            SUBSTR(BENEFICIARY_BIC8, 5, 2) AS ben_country,
            ORDERING_TYPE,
            BENEFICIARY_TYPE,
            USD_AMOUNT,
            EPOCH_SECONDS
        FROM payments
    )
    SELECT
        ben_country AS country_code,
        COUNT(*) AS ben_tx_count,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_total,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_B,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_B,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(SUM(USD_AMOUNT) / 1e9, 2) AS internal_total_usd_bn
    FROM c_ext
    GROUP BY 1
    ORDER BY ben_tx_count DESC
    LIMIT 25;
    """
    print("--- Top 25 Beneficiary Countries (Internal Dataset Volume, Entity Split & Total USD Value) ---")
    print(con.execute(q_countries).df().to_string(index=False))

    q_country_utc_peaks = """
    WITH c_time AS (
        SELECT
            SUBSTR(ORDERING_BIC8, 5, 2) AS ord_country,
            SUBSTR(BENEFICIARY_BIC8, 5, 2) AS ben_country,
            ORDERING_TYPE,
            BENEFICIARY_TYPE,
            USD_AMOUNT,
            EXTRACT('hour' FROM TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC') AS utc_hour
        FROM payments
    )
    SELECT
        ord_country,
        COUNT(*) AS total_sent,
        ROUND(SUM(USD_AMOUNT) / 1e9, 2) AS sent_usd_bn,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_B,
        MODE(CASE WHEN ORDERING_TYPE = 'B' THEN utc_hour END) AS peak_utc_hour_ord_B,
        MODE(CASE WHEN ORDERING_TYPE = 'C' THEN utc_hour END) AS peak_utc_hour_ord_C,
        ROUND(AVG(utc_hour), 2) AS mean_utc_hour
    FROM c_time
    GROUP BY 1
    ORDER BY total_sent DESC
    LIMIT 20;
    """
    print("\n--- Top 20 Ordering Countries: Internal Peak UTC Hours by ORDERING_TYPE (B vs C) ---")
    print(con.execute(q_country_utc_peaks).df().to_string(index=False))

    q_utc_dist = """
    SELECT
        EXTRACT('hour' FROM TO_TIMESTAMP(EPOCH_SECONDS) AT TIME ZONE 'UTC') AS utc_hour,
        COUNT(*) AS total_cnt,
        SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) AS B2B_cnt,
        SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) AS B2C_cnt,
        SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) AS C2B_cnt,
        SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) AS C2C_cnt,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS median_usd
    FROM payments
    GROUP BY 1
    ORDER BY 1;
    """
    print("\n--- Raw UTC Hour Distribution (0..23) across Party Pairs (B2B, B2C, C2B, C2C) ---")
    print(con.execute(q_utc_dist).df().to_string(index=False))

    # -------------------------------------------------------------------------
    # SECTION 3: ROUTING, CONTINUITY, PARTICIPANTS, DURATION & ANOMALY TYPES
    # -------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("3A. ROUTING BREAKDOWNS: TRANSACTION_TYPE_CODE, CONTINUITY_QFLAG, PARTICIPANT_COUNT, TOTAL_DURATION")
    print("=" * 100)
    q_tx_type_summary = """
    SELECT
        TRANSACTION_TYPE_CODE,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_total,
        ROUND(100.0 * SUM(CASE WHEN CONTINUITY_QFLAG = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_qflag_Y,
        ROUND(100.0 * SUM(CASE WHEN ORDERING_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ord_B,
        ROUND(100.0 * SUM(CASE WHEN BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ben_B,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS med_usd,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS med_dur_sec,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_dur_sec,
        ROUND(AVG(PARTICIPANT_COUNT), 2) AS mean_participants,
        ROUND(AVG(CURRENCY_CONVERSION_COUNT), 2) AS mean_fx
    FROM payments
    GROUP BY 1
    ORDER BY n_tx DESC;
    """
    print(con.execute(q_tx_type_summary).df().to_string(index=False))

    print("\n" + "=" * 100)
    print("3B. FULL-DATASET BREAKDOWN ACROSS ANOMALY_TYPE CATEGORIES & NORMAL TRAFFIC")
    print("=" * 100)
    q_anomaly = """
    SELECT
        COALESCE(ANOMALY_TYPE, 'NONE (Normal)') AS anomaly_category,
        COUNT(*) AS n_tx,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 4) AS pct_total,
        SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) AS B2B,
        SUM(CASE WHEN ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) AS B2C,
        SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'B' THEN 1 ELSE 0 END) AS C2B,
        SUM(CASE WHEN ORDERING_TYPE = 'C' AND BENEFICIARY_TYPE = 'C' THEN 1 ELSE 0 END) AS C2C,
        ROUND(MIN(USD_AMOUNT), 2) AS min_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.25), 2) AS p25_usd,
        ROUND(MEDIAN(USD_AMOUNT), 2) AS med_usd,
        ROUND(AVG(USD_AMOUNT), 2) AS mean_usd,
        ROUND(QUANTILE_CONT(USD_AMOUNT, 0.75), 2) AS p75_usd,
        ROUND(MAX(USD_AMOUNT), 2) AS max_usd,
        ROUND(MEDIAN(TOTAL_DURATION), 2) AS med_dur_sec,
        ROUND(AVG(TOTAL_DURATION), 2) AS mean_dur_sec,
        ROUND(AVG(PARTICIPANT_COUNT), 2) AS mean_part,
        ROUND(AVG(CURRENCY_CONVERSION_COUNT), 2) AS mean_fx,
        ROUND(100.0 * SUM(CASE WHEN CONTINUITY_QFLAG = 'Y' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_qflag_Y,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Direct' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Direct,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Indirect' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Indirect,
        ROUND(100.0 * SUM(CASE WHEN TRANSACTION_TYPE_CODE = 'Covered' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_Covered
    FROM payments
    GROUP BY 1
    ORDER BY n_tx DESC;
    """
    print(con.execute(q_anomaly).df().to_string(index=False))

    # -------------------------------------------------------------------------
    # SECTION 4: VERIFY EXISTING 200,000-ROW STRATIFIED SAMPLE
    # -------------------------------------------------------------------------
    if os.path.exists(SAMPLE_PARQUET_PATH):
        print("\n" + "=" * 100)
        print("4. VERIFIED 200,000-ROW STRATIFIED SAMPLE (data/sample_200k.parquet)")
        print("=" * 100)
        verify_sample = con.execute(f"""
            SELECT
                COALESCE(ANOMALY_TYPE, 'NONE (Normal)') AS anomaly_type,
                COUNT(*) AS sample_rows,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_sample
            FROM read_parquet('{sample_sql_path}')
            GROUP BY 1
            ORDER BY sample_rows DESC;
        """).df()
        print(verify_sample.to_string(index=False))

    print("\n" + "=" * 100)
    print(f"COMPLETED IN {time.time() - t0:.1f} SECONDS.")
    print("=" * 100)


if __name__ == "__main__":
    main()
