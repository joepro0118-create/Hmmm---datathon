# Person 2 Evidence and Edge Cases

[Rule tracker](rule_tracker.md) · [Aggregate results](tables/person2_verification.json) · [Reproduction script](../src/03_verify_person2.py)

## Copy for the rejected hypotheses and edge cases slide

**Currency initials were sensitive to the currency mix.** The handout’s hypothetical 3× consonant premium was absent. Across all 10 million payments, consonant-initial currencies had a median of $2,761.23 (4,489,093 rows) versus $4,673.98 for vowel-initial currencies (5,510,907 rows). Excluding EUR and USD reduced the vowel median to $1,654.09 (609,277 rows), reversing the comparison. The letter is fixed within currency, which limits any attempt to isolate its effect from currency identity. Evidence in `currency_initial`.

**A path gap did not add to the typical Direct payment duration.** With two participants and a Direct route, the median was 39 s with a gap (315,266 rows) and 39 s with a continuous path (6,008,014 rows). Mean durations were 664.46 s and 663.25 s. The 75th percentiles were 883 s and 877 s. Treat this as a result about the median in this stratum. At three participants the gap-bearing medians were lower by 4 s for Covered and 8 s for Indirect. Evidence in `routing`.

**The reuse of beneficiaries across scam labels did not exceed the activity benchmark.** The 352 beneficiaries with multiple labels accounted for 56.8% of the three selected scam labels. The benchmark preserved each beneficiary’s event count and party-flow mix and gave about 402 overlapping beneficiaries on average. This weakens the proposed excess-overlap story. Evidence in `account_overlap`.

**The two-hour consumer peak lag did not generalize across countries.** On the later half of the full UTC dates, consumers peaked exactly two hours after business senders in 26 of 86 eligible ordering-bank countries. Their peak was later in 40 countries, with a median signed lag of 0 hours. The business peak repeated its earlier-half hour in 56 countries. The comparison uses 5,095,953 later-half unlabeled payments and requires at least 1,000 payments in each country’s three relevant country, entity and period cells. Hours are measured relative to UTC peaks. Evidence in `timing_peaks_holdout`.

**`CUSTOMER_RECALL` is the sixth observed label.** There are 317 records, with path gaps in 35 (11.04%) versus 766,663/9,992,994 (7.67%) unlabeled payments. Applying the unlabeled gap rates to the same route types and participant counts as the recalls gives 24.98 expected gaps (7.88%). The observed rate is 1.40× that expectation. Mark the gap signature **Partial**. The one-sided, unadjusted p-value is 0.0264 under independent outcomes and fixed matched rates. Several route cells contain very few recalls, and the handout supplies no definition for this label. Evidence in `recall_matched` and `recall_test`.

## Evidence for all six anomaly labels

For the Group 7 dashboard or findings slide, prioritize the duplicate and fat-finger comparisons and use the rest of this table as supporting evidence. The counts cover all 7,006 labels. The named keys refer to the aggregate results and the corresponding SQL or test in the reproduction script.

| Label | Records | Verified signature and comparison | Boundary |
| --- | ---: | --- | --- |
| `ROMANCE_SCAM` | 2,476 | Every row has a consumer sender and belongs to a sender–receiver pair with at least two romance labels. Unlabeled repeat rates in the same flow were 753/1,512,382 for C2C and 54/609,762 for C2B. `romance_pairs` | 665 rows have business-typed beneficiaries. Pair repetition is measured over the entire file. |
| `FAT_FINGER_MISTAKE` | 1,940 | On 1,843 eligible rows, the median was 86.1× the sender’s median unlabeled amount, versus 1.0× on 1,811,362 unlabeled rows from the same sender pool. `fat_finger` | 97 labeled rows lack five unlabeled reference payments. The retrospective baseline includes future payments and does not identify a corrected amount. |
| `CEO_SCAM` | 945 | All senders are businesses versus 7,870,850/9,992,994 among unlabeled payments. At fixed party flow, median duration was 601.5 s versus 55 s for B2B (262 vs 2,269,885 rows), and 751 s versus 56 s for B2C (683 vs 5,600,965). `anomaly_profile` | The business-sender constraint is exact. Duration is descriptive and could reflect routing mix. No executive instructions are present in the fields analyzed. |
| `DUPLICATE_PAYMENT` | 679 | 639/679 have the same sender, beneficiary, currency and amount within one hour, versus 157/9,992,994 unlabeled payments. `duplicate` | Within 60 s only 36/679 match. The full-history comparison can match either an earlier or later payment. |
| `ACCOUNT_REPLACEMENT_SCAM` | 649 | The proposed exact-amount switch proxy is weak. A different beneficiary on an equal sender, currency and amount within 24 h appears in 8/649 labeled rows (1.23%) versus 165,624/9,992,994 unlabeled rows (1.66%). At seven days the comparison is 10/649 (1.54%) versus 213,786/9,992,994 (2.14%). `replacement` | This is a symmetric time-window check on an exact-amount proxy. Invoice identity or a genuine account substitution is unverified. |
| `CUSTOMER_RECALL` | 317 | 35 path gaps versus 24.98 expected after matching route type and participant count. `recall_matched`, `recall_test` | Exploratory association with a small label class. The label’s generating mechanism is unknown. |

## Data handling and sensitivity

| Decision | Reason and effect on interpretation |
| --- | --- |
| Keep all 10,000,000 records for the schema, route and label audits. | The file has 21 fields. The extra `DISCLAIMER` is present once and is used only for its presence count. No nonpositive, nonfinite or missing amounts were found. Labeled rows are kept as a separate comparison where anomaly injection could change results. |
| Drop the first and last UTC dates only for the weekday comparison. | The edge dates have 6,161 and 2,311 records. The interior gives 68.7% fewer transactions per weekend day, versus 69.2% with all dates. Removing labeled rows gives 68.7% on the interior dates. Report UTC times. |
| Use `PARTICIPANT_COUNT` and match on route when comparing path gaps. | In all 767,204 gap-bearing rows, ellipses indicate omitted path information. The count of visible eight-character BICs matches `PARTICIPANT_COUNT` on every row. The number of hidden institutions remains unknown. |
| Infer currency modes from unlabeled outgoing records. | Modes are estimated for ordering-bank countries using the Swift file, with alphabetical tie handling. Two rows with an unmapped country stay visible in the output and fall outside modal-currency comparisons. |
| Keep repeated payments in the duplicate analysis. | Deduplicating would remove the pattern being measured. The 60 s, 1 h and 24 h windows show how the number of labeled and unlabeled matches changes. |
| Use medians and interquartile ranges for skewed amounts or durations. | Outliers are retained. The mean and upper quartile are reported for three-participant Covered versus Indirect routes because they change the interpretation of the median. |
| Use the BIC country for corridors. | The address-token country matched the BIC country on 8,837,452/8,837,452 eligible sender sides and 87,555/8,900,322 eligible beneficiary sides (0.98%). This mismatch is common in the synthetic file and is unsuitable on its own as a fraud indicator. |

## Evidence sign-off for the submission

- **Pass for this handoff.** Findings trace to named queries and aggregate values. The verification used the supplied Swift CSV as its sole data input. The 200,000-row stratified sample was not used to estimate prevalence or test headline rules. The evidence exports contain aggregate counts, rates, durations and medians, with no raw text or account identifiers.
- **Pass for claim language.** The tracker quantifies conditional comparisons. Confirmed means reproduced in this file under the stated conditions. Economic explanations remain hypotheses, and the Group 4 duration comparison includes two competing explanations.
- **Disclosure.** Person 2 used Python 3.12, DuckDB 2.0.0 with `SET memory_limit = '4GB'` and two threads, and OpenAI Codex to draft and review the SQL and documentation. The verification builds on the existing team queries and Joe’s handoff. The configured DuckDB limit was verified. Peak Windows process memory was not measured. See Joe’s notes for the tools and AI used in his phase.
- **Pending final PDF sign-off.** Once Person 3 exports both PDFs, confirm each headline points to a readable chart or calculation, each chart uses the tracker’s population and baseline, the dashboard has 5–15 views, and the deck has 10–20 slides with at most one findings slide per group. Use the proposed chart paths in the tracker as a handoff reference.
