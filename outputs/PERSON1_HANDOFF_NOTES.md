# Person 1 (Lead Data & Rule Architect) — Verified Handoff Notes & Rubric Logs
**Competition:** Universiti Malaya UMDAC Datathon 2026 — Swift Case Study (Preliminary Round)  
**Owner:** Person 1 (Joe — Lead Data & Rule Architect)  
**Verification Scope:** 100% Full-Dataset SQL Verification (`N = 10,000,000` rows, `4.95 GB` CSV) via DuckDB (`SET memory_limit = '4GB';`)  
**Compliance Status:** **100% Internal Dataset Features Only** — Zero external CSVs, GDP tables, timezone files, or APIs used.

---

## 1. Exported Lightweight Summary Tables (`outputs/tables/*.csv`)
All four summary tables contain **strictly aggregated metrics (`<200` rows per file, `0` raw transaction rows)** so Teammate 2 (Visual Analytics Lead) and Teammate 3 (Report & Executive Narrative Lead) can pull them directly from Git without downloading the `4.95 GB` raw dataset:

1. **`outputs/tables/group0_data_cleaning_audit.csv`** (`37` rows): Full 10M-row schema & null audit, the 1-row `DISCLAIMER` finding, `CUSTOMER_RECALL` (6th anomaly class) count, `PARTICIPANT_COUNT` vs. `BIC8_PATH` exact mathematical equivalence, `CONTINUITY_QFLAG = 'N'` $\leftrightarrow$ `'...'` equivalence, and the `~5.0%` respondent endpoint offset.
2. **`outputs/tables/group2_currency_regimes.csv`** (`61` rows): Full 10M-row breakdowns of Domestic vs. Cross-Border $\times$ Internal Currency Regimes (`1_Both_Home_Curr`, `2_Sender_Home_Curr`, `3_Receiver_Home_Curr`, `4_Third_Vehicle_Curr`), the 24-stratum `Party Flow x Scope x Currency Regime` matrix, the 3-tier party flow geometric value ladder (`C2C` $\to$ `B2C`/`C2B` $\to$ `B2B`), the disproved Vowel vs. Consonant starting-letter archetype, and Top 25 currencies.
3. **`outputs/tables/group4_routing_and_duration.csv`** (`55` rows): Full 10M-row hop-by-hop (`PARTICIPANT_COUNT = 2..13+`) routing and `TOTAL_DURATION` profiles across `Direct`, `Indirect`, and `Covered` separated by `CONTINUITY_QFLAG` (`'Y'` vs. `'N'`), multi-hop `Covered` vs. `Indirect` triggers, and `USD_AMOUNT` bracket routing shares.
4. **`outputs/tables/group5_token_rules.csv`** (`31` rows): Full 10M-row verification of `ORDERING_TYPE x BENEFICIARY_TYPE` entity token mutual exclusion (`100.0000%`), `100.0000%` IBAN-to-BIC8 country and 4-digit bank code encoding (`5,442,631/5,442,631` ordering; `5,405,035/5,405,035` beneficiary), Sender (`100.0000%`, `8,837,452/8,837,452`) vs. Beneficiary (`0.9837%`, `87,555/8,900,322`) address-token-to-BIC8 country asymmetry, the 16-cell Missing-IBAN STP duration penalty table, and token signatures across all 6 anomaly classes.

---

## 2. Verified Person 1 `IF -> THEN` Generator Rules (Groups 0, 2, 4, 5)
Every rule below follows the mandatory 5-part rubric structure (**Condition + Effect + Size + Scope + Boundary Limits**) and has been verified on all `10,000,000` rows.

### Group 0: Structural Integrity & Routing Topology Invariants

* **Rule G0.1 — Observable BIC8 Hop-Count Equivalence (`[Confirmed]`):**
  * **Condition (`IF`):** A transaction is recorded with any `BIC8_PATH` string and `CONTINUITY_QFLAG` $\in \{\text{'Y'}, \text{'N'}\}$.
  * **Effect (`THEN`):** `PARTICIPANT_COUNT` equals the **exact number of observable (non-`'...'`) 8-character BIC8 codes** in `BIC8_PATH`:
    $$\text{PARTICIPANT\_COUNT} = N_{\text{semicolon-delimited elements}} - N_{\text{'\dots' tokens}}$$
    Furthermore, `(CONTINUITY_QFLAG = 'N')` is **100% equivalent** to `(BIC8_PATH LIKE '%...%')`.
  * **Size & Statistical Support:** `100.0000%` exact match across `N = 10,000,000` rows (`0` mismatches out of `10,000,000` for both formulas; `CONTINUITY_QFLAG = 'Y'` in `9,232,796` rows [`92.33%`] and `'N'` in `767,204` rows [`7.67%`]).
  * **Scope:** Global (`100%` of normal and anomalous transactions across all corridors and transaction types).
  * **Boundary Limits:** When `CONTINUITY_QFLAG = 'N'` (`767,204` rows), raw semicolon element count (`ARRAY_LENGTH(STRING_SPLIT(BIC8_PATH, ';'))`) exceeds `PARTICIPANT_COUNT` by `+1` (`705,533` rows with one `'...'` token) or `+2` (`61,671` rows with two `'...'` tokens). Naive hop counting without subtracting `'...'` tokens overstates `PARTICIPANT_COUNT` in `100%` of `QFLAG = 'N'` rows.

* **Rule G0.2 — Respondent Bank Endpoint Offset (`[Confirmed]`):**
  * **Condition (`IF`):** We compare the first observable institution in `BIC8_PATH` (`SPLIT_PART(BIC8_PATH, ';', 1)`) against `ORDERING_BIC8`, or the last observable institution (`RIGHT(BIC8_PATH, 8)`) against `BENEFICIARY_BIC8`.
  * **Effect (`THEN`):** Exactly **`4.984%`** of transactions initiate their `BIC8_PATH` at a sender correspondent/respondent BIC8 different from `ORDERING_BIC8`, and **`4.993%`** terminate at a receiver correspondent/respondent BIC8 different from `BENEFICIARY_BIC8` (`0` rows ever start or end with `'...'`).
  * **Size & Statistical Support:** Sender offset: `n = 498,399 / 10,000,000` (`4.9840%`); Receiver offset: `n = 499,265 / 10,000,000` (`4.9927%`).
  * **Scope:** Uniform `~4.8%–5.4%` rate across all normal `Direct`, `Indirect`, and `Covered` routes.
  * **Boundary Limits:** Drops to **`0.00%`** on both endpoints in `ROMANCE_SCAM` (`n = 2,476`), and drops to **`0.00%` on the beneficiary endpoint** in `CEO_SCAM` (`n = 945`) and `ACCOUNT_REPLACEMENT_SCAM` (`n = 649`).

---

### Group 2: Payment Values, Party Hierarchy & Internal Currency Regimes

* **Rule G2.1 — Three-Tier Geometric Party-Flow Value Scaling (`[Confirmed]`):**
  * **Condition (`IF`):** A transaction belongs to party flow `C2C` (`C->C`), mixed retail-commercial flow (`B2C` or `C2B`), or wholesale corporate flow `B2B` (`B->B`).
  * **Effect (`THEN`):** Baseline `USD_AMOUNT` scales geometrically across three distinct tiers by a factor of **`~6.8x–7.3x` per tier** (`49.42x` total median lift from `C2C` to `B2B`).
  * **Size & Statistical Support:** Verified on `N = 10,000,000` rows (and shallow Decision Tree `R^2 = 0.2350` on `LOG10(USD_AMOUNT)`):
    * **Tier 1 (`C2C`, `n = 1,514,758`, `15.15%`):** Median **`\$463.17`** (`mean = \$8,311.40`).
    * **Tier 2 (`B2C`, `n = 5,603,692`, `56.04%` & `C2B`, `n = 610,605`, `6.11%`):** Median **`\$3,119.00`** (`6.73x` `C2C`) and **`\$3,229.06`** (`6.97x` `C2C`).
    * **Tier 3 (`B2B`, `n = 2,270,945`, `22.71%`):** Median **`\$22,887.71`** (`7.34x` `B2C` / **`49.42x` `C2C`**, `mean = \$310,506.47`).
  * **Scope:** Holds across all 24 `Party Flow x Corridor Scope x Currency Regime` strata.
  * **Boundary Limits:** Violated in `FAT_FINGER_MISTAKE` (`n = 1,940`, median `\$260,241.23`, `70.55x` sender's normal median) and `ROMANCE_SCAM` (`n = 2,476`, restricted to `C2C`/`C2B` with median `\$109.45`, `0.24x` normal `C2C`).

* **Rule G2.2 — Internal Home-Currency vs. Third-Party Vehicle-Currency Regime Rule (`[Confirmed]`):**
  * **Condition (`IF`):** Each country's internal home currency is defined strictly from Swift's dataset as `home_curr(c) = MODE(CURRENCY_CODE)` for `SUBSTR(ORDERING_BIC8, 5, 2) = c`, classifying transactions into:
    1. `1_Both_Home_Curr` (`CURRENCY_CODE == ord_home_curr == ben_home_curr`, e.g., domestic or Eurozone-to-Eurozone `EUR`),
    2. `2_Sender_Home_Curr` (`CURRENCY_CODE == ord_home_curr != ben_home_curr`, `74.81%` of all traffic),
    3. `3_Receiver_Home_Curr` (`CURRENCY_CODE == ben_home_curr != ord_home_curr`, `4.23%` of all traffic), or
    4. `4_Third_Vehicle_Curr` (`CURRENCY_CODE != ord_home_curr` and `!= ben_home_curr`, `6.32%` of all traffic).
  * **Effect (`THEN`):**
    1. **Value Premium:** Shared-home-currency transfers carry a **`+49.8%` to `+64.5%` higher median `USD_AMOUNT`** (`\$5,164.11` cross-border / `\$5,672.28` domestic) than cross-border sender-home (`\$3,448.35`) or receiver-home (`\$3,125.40`) transfers across every party flow (`B2B` domestic shared-home median reaches **`\$36,453.53`** vs. `\$18,570.32` cross-border receiver-home).
    2. **FX Conversion Shift:** Moving from `1_Both_Home_Curr` to `2_Sender_Home_Curr` collapses `0-FX` settlement from **`68.73%` to `0.53%`** and shifts `70.33%` of traffic to `1` FX conversion (`mean_fx = 1.431`).
    3. **Vehicle-Currency Multi-Hop Surge:** Using a `4_Third_Vehicle_Curr` drives `2+` FX conversions up to **`44.64%`** (cross-border) and **`47.62%`** (domestic), and forces **`49.36%` (cross-border) to `52.47%` (domestic)** of transactions off `Direct` onto multi-hop (`Indirect` + `Covered`) chains (vs. `35.87%` baseline).
  * **Size & Statistical Support:** Verified across all `N = 10,000,000` rows (`6` aggregate regimes and `24` party-flow sub-strata in `outputs/tables/group2_currency_regimes.csv`).
  * **Scope:** Global normal and anomalous traffic.
  * **Boundary Limits:** In domestic corridors where sender and receiver share the same country (`711,116` rows), regimes `2_Sender_Home_Curr` and `3_Receiver_Home_Curr` are structurally empty (`0` rows) because `ord_home_curr == ben_home_curr`.

* **Rule G2.3 — Handout Illustrative Archetype Test: Vowel vs. Consonant `CURRENCY_CODE` (`[Rejected / Confounder Disproved]`):**
  * **Condition (`IF`):** `CURRENCY_CODE` starts with a vowel (`A, E, I, O, U`, `55.11%` of rows) vs. a consonant (`44.89%` of rows).
  * **Effect (`THEN`):** Contrary to the handout's illustrative example ("consonant currencies are 3x larger"), consonant-initial currencies actually have a **`40.9%` lower median `USD_AMOUNT`** (`\$2,761.23`, `mean = \$76,493.57`) than vowel-initial currencies (`\$4,673.98`, `mean = \$114,074.55`; vowel-to-consonant ratio = `1.69x`).
  * **Size & Statistical Support:** `N = 10,000,000` rows (`5,510,907` vowel vs. `4,489,093` consonant).
  * **Scope & Confounder Proof:** The apparent vowel premium is a **composition artifact**: `EUR` (`31.99%` of dataset, median `\$4,603.62`) and `USD` (`17.03%`, median `\$6,373.37`) start with vowels and account for `88.9%` of all vowel transactions, whereas individual currency medians are governed by corridor wealth and currency regimes (`KYD` [consonant] = `\$9,137.57`, `SGD` [consonant] = `\$6,404.81`, `DKK` [consonant] = `\$6,270.08`, `CHF` [consonant] = `\$6,098.55` vs. `UAH` [vowel] = `\$221.91`, `INR` [vowel] = `\$354.85`).

---

### Group 4: Routing Topology (`Direct` / `Indirect` / `Covered`) & `TOTAL_DURATION` Mechanics

* **Rule G4.1 — Deterministic Hop-Count Partition & Multi-Hop `Covered` vs. `Indirect` Triggers (`[Confirmed]`):**
  * **Condition (`IF`):** A transaction is routed through the network (`Direct`, `Indirect`, or `Covered`).
  * **Effect (`THEN`):**
    1. **Hard Topological Split:** `PARTICIPANT_COUNT == 2` maps **100.0000%** to `Direct` (`6,323,280` rows, `63.23%`), while `PARTICIPANT_COUNT >= 3` maps **100.0000%** to multi-hop (`Indirect` `3,260,758` rows [`32.61%`] or `Covered` `415,962` rows [`4.16%`], i.e., `11.31%` of all multi-hop traffic).
    2. **`Covered` vs. `Indirect` Selection Triggers (at `PARTICIPANT_COUNT >= 3`):** Compared to `Indirect`, `Covered` routing is triggered at **`1.96x` higher domestic corridor share** (`12.56%` of `Covered` is domestic vs. `6.41%` of `Indirect`), **`1.57x` higher shared-home-currency share** (`21.17%` vs. `13.45%`), and **`+17.9%` higher median `USD_AMOUNT`** (`\$4,250.80` vs. `\$3,604.77`; `Covered` share of multi-hop rises from `9.58%` below `\$100` to `11.87%` at `\$100k–\$1M`).
  * **Size & Statistical Support:** Verified across all `N = 10,000,000` rows (`0` hop-rule violations; `3,676,720` multi-hop rows).
  * **Scope:** Global normal traffic.
  * **Boundary Limits:** `Covered` routing is nearly absent (`0.12%`–`0.74%`, a **`6x–35x` suppression**) in `ROMANCE_SCAM` (`0.12%`), `ACCOUNT_REPLACEMENT_SCAM` (`0.46%`), and `CEO_SCAM` (`0.74%`) vs. `4.16%` in normal traffic.

* **Rule G4.2 — Linear Per-Hop FX & Mean Duration Scaling with 3-Hop `Covered` Settlement Penalty (`[Confirmed]`):**
  * **Condition (`IF`):** `PARTICIPANT_COUNT` increases from `2` (`Direct`) to `3..13+` (`Indirect` and `Covered`).
  * **Effect (`THEN`):**
    1. **Overall Route Latency:** Median `TOTAL_DURATION` jumps **`7.21x`** from `Direct` (`39.0s`, `mean = 663.31s`) to `Indirect` (`281.0s`, `mean = 961.73s`) and **`9.82x`** to `Covered` (`383.0s`, `mean = 925.16s`).
    2. **3-Hop `Covered` Penalty:** At `PARTICIPANT_COUNT = 3` (which represents `63.2%` of all multi-hop volume), `Covered` median duration is **`288.0s` (`QFLAG='Y'`) / `284.0s` (`QFLAG='N'`)** versus **`88.0s` (`QFLAG='Y'`) / `80.0s` (`QFLAG='N'`)** for `Indirect` — a **`3.27x` (`+200s`) median latency penalty** caused by parallel MT103 + MT202 COV cover settlement.
    3. **Additive Per-Hop Scaling (`Hops 3..13`):** Each additional participant hop adds **`+0.85` mean FX conversions** (`0.84` at 2 hops $\to$ `1.71` at 3 $\to$ `2.56` at 4 $\to$ `3.41` at 5 $\to$ `7.62` at 10) and **`+200s` to `+220s` in mean `TOTAL_DURATION`** (`663s` at 2 hops $\to$ `845s` at 3 $\to$ `1,046s` at 4 $\to$ `1,244s` at 5 $\to$ `2,277s` at 10), accompanied by a strict minimum duration floor (`min_dur_sec`: `2s, 3s, 4s, 6s, 7s, 11s, 18s, 25s, 52s...`).
  * **Size & Statistical Support:** Verified across all `N = 10,000,000` rows in `outputs/tables/group4_routing_and_duration.csv`.
  * **Boundary Limits:** At `PARTICIPANT_COUNT >= 4`, `Indirect` and `Covered` median durations converge (`411.0s` vs. `444.0s` at 4 hops; `590.0s` vs. `590.0s` at 5 hops).

* **Rule G4.3 — `CONTINUITY_QFLAG` Telemetry Truncation Duration Invariance (`[Confirmed Negative Result]`):**
  * **Condition (`IF`):** `TRANSACTION_TYPE_CODE` and `PARTICIPANT_COUNT` are held constant while comparing `CONTINUITY_QFLAG = 'Y'` vs. `CONTINUITY_QFLAG = 'N'` (`BIC8_PATH` contains `'...'`).
  * **Effect (`THEN`):** `CONTINUITY_QFLAG = 'N'` causes **zero settlement duration penalty** (e.g., at `Direct` 2-hop: `39.0s` median / `663.25s` mean for `'Y'` [`n = 6,008,014`] vs. `39.0s` median / `664.46s` mean for `'N'` [`n = 315,266`]; at `Covered` 3-hop: `288.0s` median for `'Y'` vs. `284.0s` for `'N'`). Rather than causing delay, `CONTINUITY_QFLAG = 'N'` is **triggered by hop count**, rising from `4.99%` on 2-hop `Direct` routes to **`12.29%` on `Indirect`** and **`12.32%` on `Covered`** (`2.47x` lift).
  * **Size & Statistical Support:** Verified across all `N = 10,000,000` rows (`outputs/tables/group4_routing_and_duration.csv`).
  * **Scope & Boundary Limits:** Holds across all normal traffic; in anomalous traffic, `CUSTOMER_RECALL` (`n = 317`) exhibits an elevated `CONTINUITY_QFLAG = 'N'` rate of **`11.04%`** (`88.96%` `'Y'`) vs. `7.67%` baseline.

---

### Group 5: Party Details, Token Structure & IBAN/BIC8 Encoding Rules

* **Rule G5.1 — 100% Mutual Exclusion of Entity Name Tokens Across `B` vs. `C` (`[Confirmed]`):**
  * **Condition (`IF`):** A party has `ORDERING_TYPE` or `BENEFICIARY_TYPE` equal to `'B'` (Business) vs. `'C'` (Consumer/Individual).
  * **Effect (`THEN`):** Business tokens (`<business:N>`, `~85.3%–85.9%`; `<company_keyword:N>`, `~26.2%–26.6%`) and personal name tokens (`<first_name:N>`, `~57.0%–58.0%`; `<last_name:N>`, `~86.1%–86.4%`) are **100.0000% mutually exclusive**:
    * `'B'` parties have **`0.0000%`** `<first_name:>` and **`0.0000%`** `<last_name:>` tags (`0` rows out of `7,874,637` B-senders and `2,881,550` B-beneficiaries).
    * `'C'` parties have **`0.0000%`** `<business:>` and **`0.0000%`** `<company_keyword:>` tags (`0` rows out of `2,125,363` C-senders and `7,118,450` C-beneficiaries).
  * **Size & Statistical Support:** `100.0000%` deterministic separation across all `N = 10,000,000` rows (`outputs/tables/group5_token_rules.csv`).
  * **Scope:** Global (`100%` of normal and anomalous rows).
  * **Boundary Limits:** Approximately `~14.2%` of `'B'` parties and `~13.7%` of `'C'` parties omit explicit name lines (using account + BIC8 or `<other_words:>` lines), so presence of `<business:>` vs. `<last_name:>` is a `100%`-precision classifier covering `~86%` of rows per side.

* **Rule G5.2 — 100% Deterministic IBAN-to-BIC8 Country & Bank Code Encoding + Address-Locale Asymmetry (`[Confirmed]`):**
  * **Condition (`IF`):**
    1. `ORDERING_ACCOUNT` or `BENEFICIARY_ACCOUNT` follows the structured IBAN pattern `^_FAKE_([A-Z]{2})\d{2}(\d{4})0+\d+$` (`5,442,631` ordering accounts [`54.43%`] and `5,405,035` beneficiary accounts [`54.05%`]), OR
    2. `ORDERING_TOKENS` (`8,837,452` rows [`88.37%`]) / `BENEFICIARY_TOKENS` (`8,900,322` rows [`89.00%`]) contains an explicit ISO country code tag (`<country_code:XX>`, `<city:XX:...>`, or `<country_name:XX:...>`).
  * **Effect (`THEN`):**
    1. **IBAN-to-BIC8 Exact Match (`100.0000%`):** The 2-letter IBAN country code matches `SUBSTR(BIC8, 5, 2)` **100.0000% of the time**, and the 4-digit IBAN bank code matches `SUBSTR(BIC8, 1, 4)` **100.0000% of the time** on both sender (`5,442,631 / 5,442,631`) and beneficiary (`5,405,035 / 5,405,035`) sides.
    2. **Sender vs. Beneficiary Address-Locale Asymmetry (`100.0000%` vs. `0.9837%`):** On the sender side, the address token country matches `SUBSTR(ORDERING_BIC8, 5, 2)` **100.0000% of the time** (`8,837,452 / 8,837,452`). On the beneficiary side, the Faker address generator samples a random locale independent of `BENEFICIARY_BIC8`, matching `SUBSTR(BENEFICIARY_BIC8, 5, 2)` in only **`0.9837%`** of rows (`87,555 / 8,900,322`)!
  * **Size & Statistical Support:** Verified across all `N = 10,000,000` rows in `outputs/tables/group5_token_rules.csv`.
  * **Scope & Boundary Limits:** Because `99.02%` of transactions have a beneficiary street/city country token that differs from `BENEFICIARY_BIC8[5:6]`, analysts **must never flag beneficiary address-vs-BIC8 country mismatch as fraud** (doing so yields a `99%` false-positive rate!).

* **Rule G5.3 — Missing-IBAN & Unstructured Street-Address STP Latency Penalty (`[Confirmed]`):**
  * **Condition (`IF`):** A normal transaction lacks both sender and beneficiary `<iban:>` tokens (`ord_has_iban = False` AND `ben_has_iban = False`) AND contains a beneficiary `<street:>` address without a structured country tag (`ben_has_street = True` AND `ben_has_country = False`).
  * **Effect (`THEN`):** Median `TOTAL_DURATION` spikes to **`82.0s`** (`mean = 816.88s`), compared to **`49.0s–55.0s`** (`mean = 726.99s–763.48s`) when `ben_has_iban = True` and `ben_has_country = True` — a **`+49.1%` to `+67.3%` median Straight-Through Processing (STP) manual-repair delay**.
  * **Size & Statistical Support:** `n = 29,111` rows in the penalty cell vs. `n = 2,549,680` rows in the structured `ben_has_iban = True & ben_has_country = True` cells across `9,992,994` normal rows (`outputs/tables/group5_token_rules.csv`).
  * **Scope & Boundary Limits:** In fraudulent anomalies, missing `<iban:>` tags are even more extreme: in `ROMANCE_SCAM` (`n = 2,476`), `ord_has_iban` collapses from `50.49%` to **`17.61%`** (`0.35x` normal) and median duration jumps **`20.5x` to `1,148.0s`**; in `CEO_SCAM` (`n = 945`) and `ACCOUNT_REPLACEMENT_SCAM` (`n = 649`), `ben_has_iban` drops from `49.78%` to **`36.30%`** and **`36.83%`**, with median durations jumping to **`741.0s` (`13.2x`)** and **`571.0s` (`10.2x`)**.

---

## 3. Data Cleaning & Edge-Case Audit Log (Rubric Section 3.1)

| Audit Dimension | Full-10M-Row Verification Result | Analytical & Pipeline Handling |
| :--- | :--- | :--- |
| **1. Schema & Undocumented 21st Column (`DISCLAIMER`)** | Dataset contains **21 columns** (`10,000,000` rows): the 20 columns in Appendix A.1 plus a leading `DISCLAIMER` column. `DISCLAIMER` is `NULL` in `9,999,999` rows and populated in **exactly `1` row (`0.00001%`, `ANOMALY_TYPE IS NULL`)** with Swift's synthetic generator disclosure (*"generated exclusively through hard-coded rules, NumPy 'random number' calls and the Python Faker library"*). | Retained in raw schema audit (`group0_data_cleaning_audit.csv`); excluded from predictive feature matrices. Confirms our rule-mining methodology aligns 100% with the true data-generating process. |
| **2. Undocumented 6th Anomaly Class (`CUSTOMER_RECALL`)** | While Appendix A.1 lists 5 anomaly categories, full-dataset profiling uncovered **`6` non-null `ANOMALY_TYPE` categories** totaling `7,006` rows (`0.0701%`): `ROMANCE_SCAM` (`2,476`), `FAT_FINGER_MISTAKE` (`1,940`), `CEO_SCAM` (`945`), `DUPLICATE_PAYMENT` (`679`), `ACCOUNT_REPLACEMENT_SCAM` (`649`), and **`CUSTOMER_RECALL` (`317` rows, `0.0032%`)**. | Included all `317` `CUSTOMER_RECALL` rows in `data/sample_200k.parquet` and profiled all 6 classes across Groups 0–7 so zero anomalous rows are dropped or misclassified as normal. |
| **3. Null & Boundary Value Check** | `0` nulls (`0.0000%`) across all 19 core columns (`EPOCH_SECONDS` through `BENEFICIARY_TYPE`). `0` rows with `USD_AMOUNT <= 0` or `NaN` (`min = \$0.01`, `max = \$15,664,132,213.09`). `0` rows with `TOTAL_DURATION <= 0` (`min = 2s`, `max = 21,649s`). `0` rows with `LENGTH(BIC8) != 8`. | No row deletions or synthetic imputations required; `LOG10(USD_AMOUNT)` and `LOG10(TOTAL_DURATION)` transforms are well-defined across 100% of rows. |
| **4. `BIC8_PATH` Ellipsis (`'...'`) & `PARTICIPANT_COUNT`** | In `767,204` rows (`7.6720%`), `CONTINUITY_QFLAG = 'N'` and `BIC8_PATH` contains `1` (`705,533` rows) or `2` (`61,671` rows) `'...'` placeholder tokens. Naive semicolon splitting overcounts participants in those rows. | Verified exact invariant across all `10,000,000` rows: `PARTICIPANT_COUNT = N_semicolon_elements - N_ellipsis_tokens` (`0` mismatches). Used `PARTICIPANT_COUNT` directly for hop-count modeling. |
| **5. Respondent Endpoint Offset (`~5.0%`)** | `SPLIT_PART(BIC8_PATH, ';', 1) != ORDERING_BIC8` in `498,399` rows (`4.9840%`) and `RIGHT(BIC8_PATH, 8) != BENEFICIARY_BIC8` in `499,265` rows (`4.9927%`). | Logged as a structural correspondent/respondent bank feature rather than data corruption; noted its `0.00%` drop in `ROMANCE_SCAM`, `CEO_SCAM`, and `ACCOUNT_REPLACEMENT_SCAM`. |
| **6. Beneficiary Faker Address Locale Asymmetry** | Beneficiary address country tags match `SUBSTR(BENEFICIARY_BIC8, 5, 2)` in only `0.9803%` of rows (vs. `100.0000%` on the sender side and `100.0000%` for IBAN country codes). | Derived sender/receiver corridor countries strictly from `SUBSTR(ORDERING_BIC8, 5, 2)` and `SUBSTR(BENEFICIARY_BIC8, 5, 2)` (`100%` populated and structurally consistent with IBANs). |

---

## 4. Mandatory Tool & AI Disclosure Log (Rubric Section 3.4)

* **Data Compliance Attestation:**  
  In strict compliance with the competition prompt (*"Use only the dataset provided by Swift"*), **100% of features, country codes (`SUBSTR(BIC8, 5, 2)`), internal home currencies (`MODE(CURRENCY_CODE)` per country), local diurnal clock offsets (`16 - peak_utc_hour_B`), account graphs, and token features were derived exclusively from the 21 columns inside `swift_umdac_datathon_2026_fictitious_payment_data.csv`**. Zero external CSVs, GDP tables, timezone databases, or external APIs were downloaded, imported, or joined.
* **Software & Analytical Tools Used:**
  * **Python (`3.13`):** Core scripting language for reproducible pipeline execution (`src/01_profile_and_mine.py`, `src/02_deep_rule_mining.py`, `src/02b_export_person1_tables.py`).
  * **DuckDB (`2.0.0`, `SET memory_limit = '4GB';`):** Out-of-core columnar SQL engine used to query, aggregate, and verify all hypotheses across the full `4.95 GB` (`10,000,000`-row) CSV without loading the full dataset into Pandas RAM.
  * **pandas & PyArrow:** Used for handling the `200,000`-row stratified sample (`data/sample_200k.parquet`, containing all `7,006` anomaly rows + `192,994` normal rows) and formatting the lightweight `<200`-row summary CSVs in `outputs/tables/`.
  * **scikit-learn (`DecisionTreeRegressor`, `DecisionTreeClassifier`, `max_depth=3`):** Used on `data/sample_200k.parquet` for interpretable white-box rule discovery prior to full `10,000,000`-row SQL verification.
* **AI Tools Disclosure:**
  * **Google Antigravity IDE & Gemini:** Used for DuckDB SQL query synthesis, memory-bounded out-of-core script scaffolding (`SET memory_limit = '4GB';`), shallow decision-tree feature engineering, and structuring the `IF -> THEN` rule documentation and audit logs. All statistical figures and rule boundaries were deterministically computed and verified by executing Python/DuckDB scripts directly against the `10,000,000`-row dataset.

---

## 5. Day 1 Causal & Account-Graph Upgrades (`src/04_day1_causal_and_graph_upgrades.py`)
Verified across all `10,000,000` rows using strictly internal Swift features (`outputs/tables/group6_7_causal_and_graph_upgrades.csv`, `outputs/tables/day1_causal_verification.json`, and `outputs/charts/g6_g7_day1_causal_and_pair_benchmark.png`):
* **G6.1 Pair-Level Overlap Resolution:** Shuffling across the **`2,094` distinct `(sender, receiver)` pairs** within party flow (`999` draws, `seed = 42`) yields mean **`353.09` (`95%` range `338–368`, two-sided `p = 0.901`)**, matching `352` observed multi-label beneficiaries exactly and explaining the `401.6` row-level shuffle inflation (splitting `500` repeated `ROMANCE_SCAM` pairs).
* **G6.2 Canonical Entity ID Architecture (`10M` Rows):** Ordering entities map `1:1` to accounts (`391,132` `ORDERING_ACCOUNT` strings = `391,132` Entity IDs), whereas beneficiary entities hold `5.72x` accounts across banks (`2,590,877` `BENEFICIARY_ACCOUNT` strings across `452,783` Entity IDs), structurally explaining the `0.98%` Faker address-to-BIC8 match and `1.66%` normal 24h same-amount account switching.
* **G7.1 Causal `DUPLICATE_PAYMENT` (`t_prev < t_focal`):** Evaluating strictly prior-only detection across the **`494` repeat arrivals (`seq_num >= 2`, excluding `185` initial seed tx)** achieves **`455/494` (`92.11%`) recall ≤ 1 h (`85.05%` precision)** and **`494/494` (`100.00%`) recall ≤ 2 h** (`max prev_gap = 6,940 s`, `75.08%` precision).
* **G7.2 Causal `FAT_FINGER_MISTAKE` (`epoch < t_focal`):** Using only prior unlabeled payments (`≥5` prior tx, `N = 1,721 / 1,940`), the causal median multiplier strengthens from `86.1×` (retrospective) to **`93.23×`** (`66.41%` `≥ 10×`, `48.98%` `≥ 100×`).
* **G7.4 `CEO_SCAM` vs. `ACCOUNT_REPLACEMENT_SCAM` Structural Separation:** Both use `100.0%` single-tx pairs (`945/945` and `649/649`) into the `1,068`-account scam pool (`47.0%–48.4%` pure-anomaly receivers, `0.00%` beneficiary respondent offset, `36.3%–36.8%` `<iban:>`, `648 s` / `454 s` `Direct` duration), cleanly separated by `CEO_SCAM`'s `100%` B-sender + `8.20×` `B2C` amount inflation (`\$25,556` vs `\$3,118` normal).
