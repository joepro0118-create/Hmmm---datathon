"""Verify the Datathon rules on the supplied CSV and export aggregate evidence."""

import argparse
from collections import defaultdict
from itertools import product
import json
from math import comb
from pathlib import Path
from random import Random

import duckdb


QUERIES = {
    "audit": """
        SELECT count(*) AS n, count(label) AS labeled, min(day) AS first_day,
               max(day) AS last_day, count_if(amount <= 0 OR NOT isfinite(amount)
               OR amount IS NULL) AS bad_amount, count_if(gap) AS gaps,
               count_if(gap IS DISTINCT FROM has_ellipsis) AS gap_mismatch,
               count_if(participants IS DISTINCT FROM visible_bics) AS count_mismatch,
               count_if(route NOT IN ('Direct','Indirect','Covered') OR route IS NULL
                         OR (route = 'Direct') IS DISTINCT FROM (participants = 2)
                         OR participants IS NULL OR participants < 2) AS route_mismatch,
               count_if(has_disclaimer) AS disclaimers
        FROM payments
    """,
    "daily": """
        SELECT day, isodow(day) AS dow, count(*) AS n,
               count(*) FILTER (WHERE label IS NULL) AS unlabeled_n
        FROM payments GROUP BY ALL ORDER BY day
    """,
    "timing_by_flow": """
        SELECT flow, count(*) FILTER (WHERE isodow(day) <= 5) AS weekday_n,
               count(*) FILTER (WHERE isodow(day) > 5) AS weekend_n
        FROM payments
        WHERE day > (SELECT min(day) FROM payments) AND day < (SELECT max(day) FROM payments)
        GROUP BY flow ORDER BY flow
    """,
    "timing_by_corridor": """
        WITH interior AS (
            SELECT * FROM payments
            WHERE day > (SELECT min(day) FROM payments) AND day < (SELECT max(day) FROM payments)
        ), days AS (
            SELECT count(DISTINCT day) FILTER (WHERE isodow(day) <= 5) AS weekdays,
                   count(DISTINCT day) FILTER (WHERE isodow(day) > 5) AS weekends
            FROM interior
        ), strata AS (
            SELECT flow, sender_country, receiver_country,
                   count(*) FILTER (WHERE isodow(day) <= 5) AS weekday_n,
                   count(*) FILTER (WHERE isodow(day) > 5) AS weekend_n
            FROM interior GROUP BY ALL
            HAVING weekday_n >= 100 AND weekend_n >= 100
        )
        SELECT flow, count(*) AS strata, sum(weekday_n + weekend_n) AS n,
               count_if(weekend_n * weekdays < weekday_n * weekends) AS lower_weekend,
               median(weekend_n * weekdays / (weekday_n * weekends)) AS median_rate_ratio
        FROM strata CROSS JOIN days GROUP BY flow ORDER BY flow
    """,
    "timing_peaks_holdout": """
        WITH hours AS (
            SELECT sender_country, left(flow, 1) AS entity,
                   day < (SELECT min(day) + 46 FROM payments) AS calibration,
                   hour(to_timestamp(epoch)) AS utc_hour, count(*) AS n
            FROM payments WHERE label IS NULL
              AND day > (SELECT min(day) FROM payments) AND day < (SELECT max(day) FROM payments)
            GROUP BY ALL
        ), peaks AS (
            SELECT sender_country, entity, calibration, sum(n) AS n,
                   first(utc_hour ORDER BY n DESC, utc_hour) AS peak
            FROM hours GROUP BY ALL HAVING sum(n) >= 1000
        ), matched AS (
            SELECT sender_country, sum(n) FILTER (WHERE NOT calibration) AS holdout_n,
                   max(peak) FILTER (WHERE calibration AND entity = 'B') AS earlier_business,
                   max(peak) FILTER (WHERE NOT calibration AND entity = 'B') AS later_business,
                   max(peak) FILTER (WHERE NOT calibration AND entity = 'C') AS later_consumer
            FROM peaks GROUP BY sender_country
            HAVING earlier_business IS NOT NULL AND later_business IS NOT NULL AND later_consumer IS NOT NULL
        )
        SELECT count(*) AS countries, sum(holdout_n) AS holdout_n,
               count_if(later_business = earlier_business) AS business_peak_repeated,
               median((later_consumer - later_business + 36) % 24 - 12) AS median_consumer_lag_hours,
               count_if((later_consumer - later_business + 36) % 24 - 12 > 0) AS consumer_peak_later,
               count_if((later_consumer - later_business + 36) % 24 - 12 = 2) AS consumer_peak_two_hours_later
        FROM matched
    """,
    "amount_by_flow": """
        SELECT flow, label IS NULL AS unlabeled, count(*) AS n, median(amount) AS median_usd,
               quantile_cont(amount, 0.25) AS p25_usd, quantile_cont(amount, 0.75) AS p75_usd
        FROM payments WHERE amount > 0 AND isfinite(amount) GROUP BY ALL ORDER BY ALL
    """,
    "amount_matched": """
        WITH medians AS (
            SELECT flow, sender_country, receiver_country, currency,
                   count(*) AS n, median(amount) AS med
            FROM payments
            WHERE label IS NULL AND isfinite(amount) AND amount > 0
            GROUP BY ALL HAVING n >= 100
        ), compared AS (
            SELECT sender_country, receiver_country, currency,
                   max(n) FILTER (WHERE flow = 'B2B') AS b2b_n,
                   max(n) FILTER (WHERE flow = 'C2C') AS c2c_n,
                   max(med) FILTER (WHERE flow = 'B2B') AS b2b,
                   max(med) FILTER (WHERE flow = 'C2C') AS c2c,
                   max(med) FILTER (WHERE flow = 'B2C') AS b2c,
                   max(med) FILTER (WHERE flow = 'C2B') AS c2b
            FROM medians GROUP BY ALL HAVING b2b_n IS NOT NULL AND c2c_n IS NOT NULL
        )
        SELECT count(*) AS strata, sum(b2b_n) AS b2b_n, sum(c2c_n) AS c2c_n,
               count_if(b2b > c2c) AS positive_strata, median(b2b / c2c) AS median_ratio,
               min(b2b / c2c) AS min_ratio, max(b2b / c2c) AS max_ratio,
               count_if(b2c IS NOT NULL AND c2b IS NOT NULL) AS all_four_strata,
               count_if(c2c < least(b2c,c2b) AND greatest(b2c,c2b) < b2b
                        AND b2c IS NOT NULL AND c2b IS NOT NULL) AS four_ordered
        FROM compared
    """,
    "amount_by_week": """
        SELECT date_trunc('week', day) AS week, flow, count(DISTINCT day) AS days,
               count(*) AS n, median(amount) AS median_usd
        FROM payments WHERE label IS NULL AND flow IN ('B2B','C2C')
        GROUP BY ALL ORDER BY ALL
    """,
    "currency_initial": """
        SELECT subset, starts_vowel, count(*) AS n, median(amount) AS median_usd
        FROM (
            SELECT 'All currencies' AS subset, starts_vowel, amount FROM payments
            UNION ALL
            SELECT 'Without EUR and USD', starts_vowel, amount FROM payments
            WHERE currency NOT IN ('EUR','USD')
        ) GROUP BY ALL ORDER BY ALL
    """,
    "currency_fx": """
        SELECT domestic, regime, coalesce(flow, 'All') AS flow, week, count(*) AS n,
               count_if(fx = 0) AS zero_fx, count_if(fx >= 2) AS multiple_fx,
               count_if(route = 'Direct') AS direct_n
        FROM currency_regimes GROUP BY GROUPING SETS ((domestic, regime), (domestic, regime, flow),
                                                     (domestic, regime,week))
        ORDER BY ALL
    """,
    "routing": """
        SELECT participants, route, gap, count(*) AS n, median(duration) AS median_sec,
               avg(duration) AS mean_sec, quantile_cont(duration, 0.75) AS p75_sec
        FROM payments WHERE participants <= 6 GROUP BY ALL ORDER BY ALL
    """,
    "routing_by_week": """
        SELECT date_trunc('week', day) AS week, route, gap, count(*) AS n, median(duration) AS median_sec
        FROM payments WHERE participants = 3 AND route IN ('Covered','Indirect')
        GROUP BY ALL ORDER BY ALL
    """,
    "covered_matched": """
        WITH cells AS (
            SELECT sender_country = receiver_country AS domestic, gap, flow,
                   floor(log10(amount)) AS usd_decade, route,
                   count(*) AS n, median(duration) AS median_sec
            FROM payments
            WHERE label IS NULL AND participants = 3 AND route IN ('Covered', 'Indirect')
            GROUP BY ALL HAVING n >= 100
        ), compared AS (
            SELECT domestic, gap, flow, usd_decade,
                   max(median_sec) FILTER (WHERE route = 'Covered') AS covered,
                   max(median_sec) FILTER (WHERE route = 'Indirect') AS indirect,
                   sum(n) AS n
            FROM cells GROUP BY ALL HAVING covered IS NOT NULL AND indirect IS NOT NULL
        )
        SELECT count(*) AS strata, sum(n) AS n, count_if(covered > indirect) AS covered_slower,
               median(covered - indirect) AS median_difference_sec,
               min(covered - indirect) AS min_difference_sec,
               max(covered - indirect) AS max_difference_sec
        FROM compared
    """,
    "token_audit": """
        WITH parties AS (
            SELECT 'Ordering' AS side, left(flow,1) AS entity, label,
                   ord_business AS business, ord_personal AS personal,
                   ord_country_tag AS tag, sender_country AS country,
                   ord_iban_eligible AS iban_eligible, ord_iban_match AS iban_match
            FROM payments
            UNION ALL
            SELECT 'Beneficiary', right(flow,1), label, ben_business, ben_personal,
                   ben_country_tag, receiver_country, ben_iban_eligible, ben_iban_match
            FROM payments
        )
        SELECT side, entity, label IS NULL AS unlabeled, count(*) AS n,
               count_if(business) AS business_n, count_if(personal) AS personal_n,
               count(tag) AS tagged_n, count_if(tag = country) AS tag_matches,
               count_if(iban_eligible) AS iban_n, count_if(iban_match) AS iban_matches
        FROM parties GROUP BY ALL ORDER BY ALL
    """,
    "anomaly_profile": """
        SELECT label, coalesce(flow, 'All') AS flow, count(*) AS n, count_if(flow = 'C2C') AS c2c_n,
               count_if(left(flow,1) = 'B') AS business_sender_n,
               count_if(gap) AS gap_n, median(amount) AS median_usd,
               median(duration) AS median_sec, count_if(route = 'Covered') AS covered_n
        FROM payments GROUP BY GROUPING SETS ((label), (label,flow)) ORDER BY label, flow
    """,
    "recall_matched": """
        SELECT route, participants, count(*) FILTER (WHERE label IS NULL) AS baseline_n,
               count(*) FILTER (WHERE label IS NULL AND gap) AS baseline_gap_n,
               count(*) FILTER (WHERE label = 'CUSTOMER_RECALL') AS recall_n,
               count(*) FILTER (WHERE label = 'CUSTOMER_RECALL' AND gap) AS recall_gap_n
        FROM payments WHERE label IS NULL OR label = 'CUSTOMER_RECALL'
        GROUP BY ALL HAVING recall_n > 0 ORDER BY route, participants
    """,
    "ram_and_versions": """
        SELECT version() AS duckdb_version, current_setting('memory_limit') AS memory_limit,
               current_setting('threads') AS threads,
               (SELECT sum(memory_usage_bytes) FROM duckdb_memory()) AS final_tracked_bytes
    """,
    "duplicate": """
        WITH windows AS (
            SELECT label, flow, day, epoch,
                   epoch - lag(epoch) OVER signature AS prev_gap,
                   lead(epoch) OVER signature - epoch AS next_gap
            FROM payments
            WINDOW signature AS (PARTITION BY sender, receiver, currency, amount ORDER BY epoch)
        )
        SELECT label, coalesce(flow, 'All') AS flow, date_trunc('week', day) AS week, count(*) AS n,
               count_if(least(prev_gap, next_gap) <= 60) AS repeat_60s,
               count_if(least(prev_gap, next_gap) <= 3600) AS repeat_1h,
               count_if(least(prev_gap, next_gap) <= 86400) AS repeat_24h
        FROM windows
        WHERE label IS NULL OR label = 'DUPLICATE_PAYMENT'
        GROUP BY GROUPING SETS ((label), (label,flow), (label, week)) ORDER BY ALL
    """,
    "fat_finger": """
        WITH fingerprints AS (
            SELECT p.label, p.flow, date_trunc('week', p.day) AS week, p.amount / m.baseline AS ratio
            FROM payments p JOIN fat_finger_baselines m USING (sender)
            WHERE p.label IS NULL OR p.label = 'FAT_FINGER_MISTAKE'
        )
        SELECT label, coalesce(flow, 'All') AS flow, week, count(*) AS n, median(ratio) AS median_ratio,
               count_if(ratio >= 10) AS at_least_10x, count_if(ratio >= 100) AS at_least_100x
        FROM fingerprints GROUP BY GROUPING SETS ((label),(label, flow),(label,week)) ORDER BY ALL
    """,
    "romance_pairs": """
        WITH pairs AS (
            SELECT sender, receiver, flow,
                   count_if(label = 'ROMANCE_SCAM') AS romance_n,
                   count(*) FILTER (WHERE label IS NULL) AS unlabeled_n
            FROM payments WHERE left(flow,1) = 'C' GROUP BY ALL
        )
        SELECT flow, sum(romance_n) AS romance_n, sum(unlabeled_n) AS unlabeled_n,
               sum(romance_n) FILTER (WHERE romance_n >= 2) AS label_repeat_n,
               sum(romance_n) FILTER (WHERE romance_n + unlabeled_n >= 2) AS romance_repeat_n,
               sum(unlabeled_n) FILTER (WHERE romance_n + unlabeled_n >= 2) AS unlabeled_repeat_n
        FROM pairs GROUP BY flow ORDER BY flow
    """,
    "replacement": """
        WITH matches AS (
            SELECT label, flow,
                   min(receiver) OVER day_window <> max(receiver) OVER day_window AS switch_24h,
                   min(receiver) OVER week_window <> max(receiver) OVER week_window AS switch_7d
            FROM payments
            WINDOW day_window AS (PARTITION BY sender, currency, amount ORDER BY epoch
                       RANGE BETWEEN 86400 PRECEDING AND 86400 FOLLOWING),
                   week_window AS (PARTITION BY sender, currency, amount ORDER BY epoch
                       RANGE BETWEEN 604800 PRECEDING AND 604800 FOLLOWING)
        )
        SELECT label, coalesce(flow, 'All') AS flow, count(*) AS n,
               count_if(switch_24h) AS switch_24h, count_if(switch_7d) AS switch_7d
        FROM matches WHERE label IS NULL OR label = 'ACCOUNT_REPLACEMENT_SCAM'
        GROUP BY GROUPING SETS ((label), (label,flow)) ORDER BY ALL
    """,
}


def rows(connection, sql):
    result = connection.execute(sql)
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def prepare_payments(connection, csv_path):
    connection.read_csv(csv_path, header=True, sample_size=100000,
                        dtype={"ANOMALY_TYPE": "VARCHAR"}).create_view("swift_csv")
    # Retain only the fields needed for comparisons. Large raw text stays in the CSV.
    connection.execute(r"""
        CREATE TEMP TABLE payments AS
        WITH features AS (
            SELECT DISCLAIMER AS disclaimer, EPOCH_SECONDS AS epoch,
                   to_timestamp(epoch)::DATE AS day,
                   ORDERING_TYPE || '2' || BENEFICIARY_TYPE AS flow,
                   ANOMALY_TYPE AS label, USD_AMOUNT AS amount, CURRENCY_CODE AS currency,
                   left(currency,1) IN ('A','E','I','O','U') AS starts_vowel,
                   substr(ORDERING_BIC8,5,2) AS sender_country,
                   substr(BENEFICIARY_BIC8,5,2) AS receiver_country,
                   ORDERING_ACCOUNT AS sender, BENEFICIARY_ACCOUNT AS receiver,
                   TRANSACTION_TYPE_CODE AS route, PARTICIPANT_COUNT AS participants,
                   TOTAL_DURATION AS duration, CURRENCY_CONVERSION_COUNT AS fx,
                   CONTINUITY_QFLAG = 'N' AS gap, contains(BIC8_PATH,'...') AS has_ellipsis,
                   len(list_filter(string_split(BIC8_PATH,';'), lambda x: len(x) = 8)) AS visible_bics,
                   regexp_matches(ORDERING_TOKENS,'<(business|company_keyword):') AS ord_business,
                   regexp_matches(BENEFICIARY_TOKENS,'<(business|company_keyword):') AS ben_business,
                   regexp_matches(ORDERING_TOKENS,'<(first_name|last_name):') AS ord_personal,
                   regexp_matches(BENEFICIARY_TOKENS,'<(first_name|last_name):') AS ben_personal,
                   coalesce(nullif(regexp_extract(ORDERING_TOKENS,'<country_code:([A-Z]{2})>',1),''),
                            nullif(regexp_extract(ORDERING_TOKENS,'<city:([A-Z]{2}):',1),''),
                            nullif(regexp_extract(ORDERING_TOKENS,'<country_name:([A-Z]{2}):',1),'')) AS ord_country_tag,
                   coalesce(nullif(regexp_extract(BENEFICIARY_TOKENS,'<country_code:([A-Z]{2})>',1),''),
                            nullif(regexp_extract(BENEFICIARY_TOKENS,'<city:([A-Z]{2}):',1),''),
                            nullif(regexp_extract(BENEFICIARY_TOKENS,'<country_name:([A-Z]{2}):',1),'')) AS ben_country_tag,
                   regexp_matches(sender, '^_FAKE_[A-Z]{2}[0-9]{6}0+[0-9]+$') AS ord_iban_eligible,
                   regexp_matches(receiver, '^_FAKE_[A-Z]{2}[0-9]{6}0+[0-9]+$') AS ben_iban_eligible,
                   ord_iban_eligible AND substr(sender,7,2) = sender_country
                       AND substr(sender,11,4) = left(ORDERING_BIC8,4) AS ord_iban_match,
                   ben_iban_eligible AND substr(receiver,7,2) = receiver_country
                       AND substr(receiver,11,4) = left(BENEFICIARY_BIC8,4) AS ben_iban_match
            FROM swift_csv
        ) SELECT * EXCLUDE (disclaimer), disclaimer IS NOT NULL AS has_disclaimer FROM features
    """)


def weekday_test(daily):
    # Seven day blocks retain the dependence between transactions on a given day.
    differences = []
    block = []
    for row in daily[1:-1]:
        if row["dow"] == 1:
            block = []
        block.append(row)
        if len(block) == 7 and row["dow"] == 7:
            differences.append(2 * sum(d["n"] for d in block[:5])
                               - 5 * sum(d["n"] for d in block[5:]))
    observed = abs(sum(differences))
    permutations = 2 ** len(differences)
    as_extreme = sum(abs(sum(sign * d for sign, d in zip(signs, differences))) >= observed
                     for signs in product((-1, 1), repeat=len(differences)))
    return {"full_weeks": len(differences), "weeks_with_lower_weekend": sum(d > 0 for d in differences),
            "two_sided_p": as_extreme / permutations}


def recall_test(strata):
    # Exact upper tail under independent Bernoulli outcomes at each matched baseline rate.
    probabilities = [1.0]
    expected_gaps = 0.0
    for cell in strata:
        baseline_rate = cell["baseline_gap_n"] / cell["baseline_n"]
        expected_gaps += cell["recall_n"] * baseline_rate
        for _ in range(cell["recall_n"]):
            probabilities.append(0.0)
            for k in range(len(probabilities) - 1, 0, -1):
                probabilities[k] = probabilities[k] * (1 - baseline_rate) + probabilities[k - 1] * baseline_rate
            probabilities[0] *= 1 - baseline_rate
    observed = sum(cell["recall_gap_n"] for cell in strata)
    return {"expected_gaps": expected_gaps, "observed_gaps": observed,
            "upper_tail_p": sum(probabilities[observed:])}


def weekly_sign_test(records, group, high, low, value, full_weeks):
    pairs = defaultdict(dict)
    for row in records:
        week = str(row["week"])[:10]
        if week in full_weeks:
            pairs[week][row[group]] = value(row)
    comparisons = [pair[high] - pair[low] for pair in pairs.values() if high in pair and low in pair]
    positive = sum(value > 0 for value in comparisons)
    negative = sum(value < 0 for value in comparisons)
    non_tied = positive + negative
    p = None
    if comparisons:
        tail = sum(comb(non_tied, k) for k in range(min(positive, negative) + 1))
        p = min(1.0, 2 * tail / 2 ** non_tied)
    return {"compared_weeks": len(comparisons), "higher_weeks": positive, "two_sided_p": p}


def weekly_tests(evidence):
    full_weeks = {str(row["day"]) for i, row in enumerate(evidence["daily"][1:-7], start=1)
                  if row["dow"] == 1 and evidence["daily"][i + 6]["dow"] == 7}
    fx = [row for row in evidence["currency_fx"] if not row["domestic"]]
    routing = [row for row in evidence["routing_by_week"] if not row["gap"]]
    return {
        "b2b_amount": weekly_sign_test(evidence["amount_by_week"], "flow", "B2B", "C2C",
                                       lambda row: row["median_usd"], full_weeks),
        "shared_zero_fx": weekly_sign_test(fx, "regime", "Shared modal", "Sender modal only",
                                          lambda row: row["zero_fx"] / row["n"], full_weeks),
        "vehicle_multiple_fx": weekly_sign_test(fx, "regime", "Neither modal", "Shared modal",
                                                lambda row: row["multiple_fx"] / row["n"], full_weeks),
        "covered_duration": weekly_sign_test(routing, "route", "Covered", "Indirect",
                                             lambda row: row["median_sec"], full_weeks),
        "duplicate_repeat": weekly_sign_test(evidence["duplicate"], "label", "DUPLICATE_PAYMENT", None,
                                             lambda row: row["repeat_1h"] / row["n"], full_weeks),
        "fat_finger_amount": weekly_sign_test(evidence["fat_finger"], "label", "FAT_FINGER_MISTAKE", None,
                                             lambda row: row["median_ratio"], full_weeks),
    }


def account_overlap(connection, draws=999):
    # Use temporary integer account indices. Export no account identifiers.
    events = rows(connection, """
        SELECT dense_rank() OVER (ORDER BY receiver) - 1 AS receiver_index, flow, label
        FROM payments WHERE label IN ('ROMANCE_SCAM','CEO_SCAM','ACCOUNT_REPLACEMENT_SCAM')
        ORDER BY receiver_index, flow, label
    """)
    groups = defaultdict(list)
    bits = {"ROMANCE_SCAM": 1, "CEO_SCAM": 2, "ACCOUNT_REPLACEMENT_SCAM": 4}
    for event in events:
        groups[event["flow"]].append((event["receiver_index"], bits[event["label"]]))
    account_count = len({event["receiver_index"] for event in events})

    def masks_for_labels(shuffle=None):
        masks = [0] * account_count
        for group in groups.values():
            labels = [bit for _, bit in group]
            if shuffle is not None:
                shuffle(labels)
            for (account, _), bit in zip(group, labels):
                masks[account] |= bit
        return masks

    observed_masks = masks_for_labels()
    observed = sum(mask.bit_count() >= 2 for mask in observed_masks)
    rng = Random(42)
    simulated = [sum(mask.bit_count() >= 2 for mask in masks_for_labels(rng.shuffle))
                 for _ in range(draws)]
    return {"labeled_rows": len(events), "beneficiaries": account_count,
            "multi_label_beneficiaries": observed,
            "three_label_beneficiaries": sum(mask == 7 for mask in observed_masks),
            "rows_on_multi_label_beneficiaries": sum(observed_masks[e["receiver_index"]].bit_count() >= 2
                                                    for e in events),
            "draws": draws, "null_mean": sum(simulated) / draws,
            "null_p025": sorted(simulated)[int(draws * 0.025)],
            "null_p975": sorted(simulated)[int(draws * 0.975)],
            "enrichment_p": (1 + sum(value >= observed for value in simulated)) / (draws + 1),
            "depletion_p": (1 + sum(value <= observed for value in simulated)) / (draws + 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to the extracted Swift CSV")
    parser.add_argument("--output", type=Path, default=Path("outputs/tables/person2_verification.json"))
    args = parser.parse_args()
    if not args.csv.is_file():
        parser.error(f"Swift CSV does not exist: {args.csv}")

    with duckdb.connect() as connection:
        connection.execute("SET memory_limit = '4GB'; SET threads = 2; SET TimeZone = 'UTC';")
        connection.execute("SET preserve_insertion_order = false;")
        print("Scanning the Swift CSV", flush=True)
        prepare_payments(connection, str(args.csv.resolve()))
        connection.execute("""
            CREATE TEMP VIEW currency_regimes AS
            WITH modal AS (
                SELECT sender_country AS country, mode(currency ORDER BY currency) AS currency
                FROM payments WHERE label IS NULL GROUP BY sender_country
            )
            SELECT flow, route, sender_country = receiver_country AS domestic, fx,
                   date_trunc('week', day) AS week,
                   CASE WHEN s.currency IS NULL OR b.currency IS NULL THEN 'Unmapped country'
                        WHEN p.currency = s.currency AND p.currency = b.currency THEN 'Shared modal'
                        WHEN p.currency = s.currency THEN 'Sender modal only'
                        WHEN p.currency = b.currency THEN 'Receiver modal only'
                        ELSE 'Neither modal' END AS regime
            FROM payments p LEFT JOIN modal s ON p.sender_country = s.country
                            LEFT JOIN modal b ON p.receiver_country = b.country
        """)
        connection.execute("""
            CREATE TEMP TABLE fat_finger_baselines AS
            SELECT sender, median(amount) AS baseline
            FROM payments
            WHERE label IS NULL AND sender IN (
                SELECT sender FROM payments WHERE label = 'FAT_FINGER_MISTAKE'
            ) GROUP BY sender HAVING count(*) >= 5
        """)
        evidence = {}
        for key, sql in QUERIES.items():
            print(f"Verifying {key}", flush=True)
            evidence[key] = rows(connection, sql)
        evidence["weekday_test"] = weekday_test(evidence["daily"])
        evidence["weekly_sign_tests"] = weekly_tests(evidence)
        evidence["recall_test"] = recall_test(evidence["recall_matched"])
        print("Checking beneficiary overlap against shuffled labels", flush=True)
        evidence["account_overlap"] = account_overlap(connection)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
