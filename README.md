# UMDAC Datathon 2026 — Swift Case Study (Preliminary Round)

**Full-Dataset Rule Discovery, Confounder Testing & Causal Verification across 10,000,000 Synthetic Payments (`4.95 GB`)**

> **Strict Compliance Attestation:** All analyses, country codes (`SUBSTR(BIC8, 5, 2)`), inferred home currencies (`MODE(CURRENCY_CODE)` per country), canonical Entity IDs, account graphs, and statistical tests were derived **exclusively from Swift's provided CSV dataset (`10,000,000` rows, `21` columns)**. Strictly **zero external CSVs, GDP tables, timezone databases, FX tables, or external APIs** were imported or joined. All full-dataset queries execute out-of-core in **DuckDB (`SET memory_limit = '4GB';`)**.

---

## 1. Primary Submission Deliverables

| Deliverable | Path | Size / Extent | Description |
| :--- | :--- | :---: | :--- |
| **Executive Analytics Dashboard** | [`outputs/Dashboard_Swift_2026.pdf`](outputs/Dashboard_Swift_2026.pdf) | **10 pages** (`5–15` limit) | Full 7-group analytics dashboard + negative results + final synthesis (mirror: [`outputs/dashboard/Swift_Dashboard_UMDAC2026.pdf`](outputs/dashboard/Swift_Dashboard_UMDAC2026.pdf)) |
| **Presentation Slide Deck** | [`outputs/SlideDeck_Swift_2026.pdf`](outputs/SlideDeck_Swift_2026.pdf) | **15 slides** (`10–20` limit) | Executive presentation (`<= 1` findings slide per Feature Type Group) with method, 7 groups, rejected hypotheses, competing mechanisms, and AI disclosure (mirror: [`outputs/presentation/Swift_Rule_Discovery_UMDAC2026 3.pptx.pdf`](outputs/presentation/Swift_Rule_Discovery_UMDAC2026%203.pptx.pdf)) |
| **Master Rule Verification Tracker** | [`outputs/rule_tracker.md`](outputs/rule_tracker.md) | 8-column rubric table | Verified findings (`G1.1`–`G7.4`), confounder controls, `p`-values, boundaries, and chart links (`11 Confirmed`, `1 Partial`) |
| **Methodology & Audit Logs** | [`outputs/PERSON1_HANDOFF_NOTES.md`](outputs/PERSON1_HANDOFF_NOTES.md) · [`outputs/PERSON2_AUDIT_NOTES.md`](outputs/PERSON2_AUDIT_NOTES.md) | Complete rubric logs | Section 3.1 Data Cleaning & Sensitivity Log, Section 3.4 Tool/AI Disclosure, causal upgrades, and 6-anomaly audit |

---

## 2. Summary of Verified Findings Across All 7 Feature Type Groups

All headline rules are verified on all **`10,000,000`** rows (`9,992,994` unlabeled + `7,006` labeled across **6** `ANOMALY_TYPE` categories, including the undocumented **`CUSTOMER_RECALL`** class of `317` rows).

| Rule ID | Feature Type Group | Status | Verified Finding Summary |
| :--- | :--- | :--- | :--- |
| **G1.1** | Timing & Clocks | **Confirmed** | UTC weekends average **`68.7%` fewer** payments/day (`42,781` vs `136,603` on 91 interior dates; `69.2%` across all dates); lower in all `13/13` full weeks (`p = 0.000244`) and all `1,805/1,805` corridor × flow cells. |
| **G2.1** | Currency & FX | **Confirmed** | Cross-border payments in both countries' inferred modal currency need `0` FX conversions **`68.73%`** of the time vs **`0.53%`** for sender-modal-only (`p = 0.000244`). |
| **G2.2** | Currency & FX | **Confirmed** | Cross-border payments in neither country's modal currency take `>= 2` FX steps **`1.57×`** as often (`44.64%` vs `28.49%`; `47.62%` vs `31.21%` same-country). |
| **G3.1** | Party Flows & Values | **Confirmed** | Median `B2B` amount (`$22,883.00`) is **`49.4×`** `C2C` (`$463.65`), with `B2C` (`$3,117.51`) and `C2B` (`$3,236.32`) between them (`1,686/1,686` country × currency cells; `13/13` weeks). |
| **G4.1** | Routing Structure | **Confirmed** | Deterministic topology: `100%` of `2`-participant rows (`6,323,280`) are `Direct`; `100%` of `>= 3`-participant rows (`3,676,720`) are `Indirect` or `Covered` (`0` violations in `10M` rows). |
| **G4.2** | Routing Duration | **Confirmed** | At `3` continuous participants, `Covered` median duration is **`288 s` vs `88 s`** (`3.27×`, higher in `71/72` matched strata and `13/13` weeks), while its mean (`810 s` vs `845 s`) and P75 (`987 s` vs `1,326 s`) are lower. |
| **G5.1** | Party Tokens | **Confirmed** | Strict entity-tag separation: `0` cross-type `<business:>`/`<company_keyword:>` vs `<first_name:>`/`<last_name:>` violations across `20M` party sides. |
| **G5.2** | Account Encoding | **Confirmed** | **`100%`** (`5,442,631/5,442,631` ordering; `5,405,035/5,405,035` beneficiary) of synthetic IBAN-like accounts encode exact country + 4-digit bank prefix of their BIC8; beneficiary address tokens match BIC country only **`0.98%`**. |
| **G6.1** | Account Graph | **Partial *(Mechanism Resolved)*** | Shuffling at the true **`2,094` `(sender, receiver)` pair level** yields mean **`353.1`** (`338–368`, `p = 0.901`), matching **`352`** observed multi-label beneficiaries (resolving the `401.6` row-shuffle artifact). Shared criminal ownership remains unproven; scam-pool beneficiaries still show `47–60%` pure-anomaly receivers with `0.00%` endpoint offset. |
| **G7.1** | Duplicate Payments | **Confirmed** | **`94.1%`** (`639/679`) match identically `<= 1 h` retrospectively (vs `0.00157%` unlabeled). Evaluated causally (`t_prev < t_focal`) across the `494` repeat arrivals (`seq_num >= 2`), recall is **`92.11%` (`455/494`) `<= 1 h`** (`85.05%` precision) and **`100.00%` `<= 2 h`**. |
| **G7.2** | Fat-Finger Mistakes | **Confirmed** | Median amount is **`86.1×`** sender median retrospectively (`N = 1,843`), strengthening to **`93.23×`** when measured strictly against **prior unlabeled payments (`epoch < t_focal`, `N = 1,721`, `66.41% >= 10×`)**. |
| **G7.3 / G7.4** | Scam Signatures | **Confirmed** | `ROMANCE_SCAM` (`2,476`): `100%` C-sender repeated pairs; `CEO_SCAM` (`945`) & `ACCOUNT_REPLACEMENT_SCAM` (`649`): `100%` single-use pairs into the scam pool (`0.00%` ben. offset, `648 s`/`454 s` `Direct` duration), separated by `CEO_SCAM`'s `100%` B-sender and **`8.20×` `B2C` amount inflation** (`$25,556` vs `$3,118`). |

### Four Rejected / Corrected Hypotheses (Slide 11 & Dashboard Page 9)
1. **Vowel vs. Consonant Currency Rule (`Reversed`):** Consonant median (`$2,761`) is lower than vowel median (`$4,674`); removing `EUR` and `USD` drops vowels to `$1,654` (`composition artifact`).
2. **Path Gap (`...`) Duration Penalty (`No effect`):** Holding hops fixed (`Direct`, `2` participants), `CONTINUITY_QFLAG = 'N'` (`39 s`) equals `'Y'` (`39 s`).
3. **Universal `+2h` Consumer Peak Lag (`Not universal`):** Holds in only `26/86` countries in chronological holdout (median lag `0 h`).
4. **Excess Beneficiary Scam Overlap (`Resolved Artifact`):** Row-level shuffling (`401.6`) broke `500` repeated `ROMANCE_SCAM` pairs (`4.95` tx/pair); pair-level shuffling (`353.1`, `p = 0.901`) matches `352` observed.

---

## 3. Repository Structure

```text
Hmmm-datathon/
├── .gitignore                              # Blocks >50MB raw CSVs/DuckDB files; allows summary CSVs, PNGs, sample parquet
├── README.md                               # Project overview, verified rules, and reproduction guide
├── PRDDatathon.md                          # Case study requirements & evaluation rubric
├── data/
│   └── sample_200k.parquet                 # 200k stratified sample (all 7,006 anomalies + 192,994 normal rows)
├── notebooks/                              # 10 visual exploration & chart generation notebooks
├── src/
│   ├── 01_profile_and_mine.py              # Schema, nulls, 10M profiling & 200k stratified Parquet builder
│   ├── 02_deep_rule_mining.py              # max_depth=3 decision trees + 10M DuckDB hypothesis verification
│   ├── 02b_export_person1_tables.py        # Group 0/2/4/5 lightweight CSV exporter (<200 rows/CSV)
│   ├── 03_verify_person2.py                # Full-10M statistical verification, matched strata, weekly sign tests & seed-42 overlap
│   └── 04_day1_causal_and_graph_upgrades.py# Causal (t < t_focal) G7 checks, pair-level G6 resolution, entity ID & scam-pool audit
└── outputs/
    ├── Dashboard_Swift_2026.pdf            # ★ Primary 10-page Dashboard submission PDF
    ├── SlideDeck_Swift_2026.pdf            # ★ Primary 15-slide Presentation submission PDF
    ├── rule_tracker.md                     # 8-column rubric master verification table
    ├── PERSON1_HANDOFF_NOTES.md            # Groups 0/2/4/5 IF->THEN rules + Rubric 3.1/3.4 logs
    ├── PERSON2_AUDIT_NOTES.md              # Rejected hypotheses, all 6 anomalies & sensitivity decisions
    ├── charts/                             # 300 DPI verification charts (incl. Day 1 causal/graph 3-panel PNG)
    ├── dashboard/                          # Individual dashboard PDF pages 1–10 + unified copy
    ├── presentation/                       # Presentation PDF source copy
    └── tables/                             # Strictly aggregated CSV & JSON verification summaries (0 raw tx rows)
```

---

## 4. End-to-End Reproduction

Requires **Python 3.12+** (`duckdb >= 2.0`, `pandas`, `pyarrow`, `scikit-learn`, `matplotlib`) and Swift's extracted CSV (`swift_umdac_datathon_2026_fictitious_payment_data.csv`):

```bash
# 1. Profile full 10M CSV and build 200k stratified sample (outputs data/sample_200k.parquet)
python src/01_profile_and_mine.py "<path-to-swift.csv>"

# 2. Run depth-3 decision trees on 200k sample + full 10M Group 0-7 SQL checks
python src/02_deep_rule_mining.py "<path-to-swift.csv>"

# 3. Export lightweight Group 0, 2, 4, 5 summary CSVs to outputs/tables/
python src/02b_export_person1_tables.py "<path-to-swift.csv>"

# 4. Run full 10M matched confounder verification & weekly sign tests (outputs person2_verification.json)
python src/03_verify_person2.py "<path-to-swift.csv>"

# 5. Run causal (t < t_focal) G7 checks, G6 pair-shuffle resolution & generate 300 DPI upgrade chart
python src/04_day1_causal_and_graph_upgrades.py "<path-to-swift.csv>"
```
