# Product Requirements Document (PRD)

# UMDAC Datathon 2026 — Swift Payments Rule Discovery & Executive Analytics Suite

## 1. Document Overview & Strategic Objective

* **Event Context:** Universiti Malaya UMDAC Datathon 2026 (November 13, 2026), Case Study Preliminary Round sponsored by **Swift**.
* **Core Objective:** Reverse-engineer and statistically validate the hidden business rules, causal relationships, structural code rules, and macroeconomic/behavioral dynamics embedded within Swift's ~4GB artificial cross-border payment dataset.
* **Deliverable Format:** Two static, publication-grade PDF documents (**Dashboard PDF** and **Slide Deck PDF**) supported by an automated Python/DuckDB rule-discovery and visualization pipeline.

---

## 2. Target Audience & Stakeholder Alignment (Judging Panel)

The analytical outputs, governance framing, and visual hierarchy must satisfy six Swift judges across distinct functional lenses:

| Stakeholder | Role @ Swift | Primary Evaluation Lens |
| :--- | :--- | :--- |
| **Tom Jacobs** | Head of AI, Analytics & Automation | AI governance, explainability (SHAP), data structuring (ISO 20022), fraud/anomaly logic, and explicit documentation of **failure modes & edge cases**. |
| **Anthony Richelle** | AI Solutions Analyst | Practical payment innovation and direct translation of raw transaction data into actionable analyst insights. |
| **RJ Ho** | Lead Developer – SRE Chapter | Pipeline reliability, memory-safe execution on 4GB data, reproducibility, and null/edge-case resilience. |
| **Sheryl Chan** | Product & Go-to-Market Lead | Clear user persona framing (e.g., Bank Operations / Compliance Analyst) and operational relevance. |
| **Kelvin P.** | Market Analyst | Executive-ready storytelling, ISO 20022/payment corridor dynamics, and strategic takeaways. |
| **Madhavan (Madhi) S.** | Analytics Platform Team Lead | Clean visual hierarchy, intuitive grouping by feature type, and self-service readability across dashboard pages. |

---

## 3. Exact Dataset Schema & Domain Specifications (Appendix A.1)

The dataset represents a directed temporal pseudograph flattened into a ~4GB timestamped tabular format containing **20 exact fields**:

| Feature Name | Exact Definition & Analytical Role |
| :--- | :--- |
| `EPOCH_SECONDS` | Transaction timestamp in Unix epoch seconds (convertible to UTC and local sender/receiver times). |
| `CURRENCY_CODE` | ISO 4217 currency code (e.g., `GBP`, `EUR`, `USD`, `CNY`). |
| `USD_AMOUNT` | Transaction amount normalized to USD for cross-currency comparison. |
| `ORDERING_BIC8` | 8-character BIC of the ordering/sending bank (characters 5–6 = ISO country code). |
| `BENEFICIARY_BIC8` | 8-character BIC of the beneficiary/receiving bank (characters 5–6 = ISO country code). |
| `BIC8_PATH` | Semicolon-separated sequence of BIC8s across intermediary banks (`...` indicates an incomplete/hidden/discontinuous path). |
| `TOTAL_DURATION` | Total elapsed duration of the payment route in seconds from initiation to completion/observation end. |
| `CONTINUITY_QFLAG` | Full BIC path observability flag (`Y` = continuous observable path; `N` = path contains a gap or `...`). |
| `CURRENCY_CONVERSION_COUNT` | Number of FX conversion steps along the payment path (`0` = no conversion observed). |
| `PARTICIPANT_COUNT` | Total number of institutions/participants involved in the payment route. |
| `TRANSACTION_TYPE_CODE` | Payment routing category: `Direct` (sender-to-recipient), `Indirect` (intermediaries), or `Covered` (cover-payment-style route). |
| `ORDERING_ACCOUNT` | Anonymized ordering party account identifier (`synthetic_FAKE_#####`). |
| `BENEFICIARY_ACCOUNT` | Anonymized beneficiary party account identifier (`synthetic_FAKE_#####`). |
| `ORDERING_DETAILS` | Raw/semi-structured ordering party text (name, address, country, account hints, remittance info; may contain line breaks). |
| `ORDERING_TOKENS` | Engineered token summary of `ORDERING_DETAILS` (names, businesses, street addresses, IBANs, country codes, finance words, stop words, line breaks, character patterns). |
| `BENEFICIARY_DETAILS` | Raw/semi-structured beneficiary party text (name, address, country, account hints, free-text info; may contain line breaks). |
| `BENEFICIARY_TOKENS` | Engineered token summary of `BENEFICIARY_DETAILS` matching `ORDERING_TOKENS` semantics. |
| `ORDERING_TYPE` | Ordering party entity type: `B` = Business/corporate, `C` = Consumer/individual. |
| `BENEFICIARY_TYPE` | Beneficiary party entity type: `B` = Business/corporate, `C` = Consumer/individual. |
| `ANOMALY_TYPE` | Optional anomaly label: `ROMANCE_SCAM`, `CEO_SCAM`, `ACCOUNT_REPLACEMENT_SCAM`, `FAT_FINGER_MISTAKE`, or `DUPLICATE_PAYMENT`. |

### Exact Anomaly Taxonomy (Handout Page 4)
* `ROMANCE_SCAM`: Consumer (`C`) misled into repeatedly sending funds to another Consumer (`C`).
* `CEO_SCAM`: Business (`B`) induced to execute an illegitimate payment via spoofed/compromised executive instruction.
* `ACCOUNT_REPLACEMENT_SCAM`: Legitimate invoice intercepted where `BENEFICIARY_ACCOUNT` is swapped to a fraudster/mule account while party/remittance context remains consistent.
* `FAT_FINGER_MISTAKE`: User error where comma/decimal placement shifts `USD_AMOUNT` by orders of magnitude (e.g., 10x, 100x, 1000x).
* `DUPLICATE_PAYMENT`: Accidental repeat of an identical/near-identical payment due to Business (`B`) back-office race condition or two Consumers (`C`) paying the same invoice independently.

---

## 4. Data Constraints, Noise Exclusions & Generator Archetypes

* **Hard Noise & Confounder Exclusion Rule:**
  * Initial distributions are randomized; individual country population sizes, absolute import/export volumes, geographic city distributions, and ethnic name origins do **NOT** reflect reality.
  * **Constraint:** Never report marginal counts or raw volume rankings as insights. Express all findings strictly as **conditional relationships, lift ratios, probability shifts, or causal rules**.
* **Confirmed Generator Archetypes:**
  1. **Arbitrary / String-Pattern Rules:** e.g., payment value multipliers conditioned on currency code starting character (consonant vs. vowel) or token patterns.
  2. **Macroeconomic & Local-Timezone Behavioral Rules:** e.g., corporate (`B`) receipt concentration between 15:00–17:00 local time scaling with country GDP.
  3. **Banking & Swift Domain Standards:** Cover payment (`Covered` vs. `Direct`/`Indirect`) triggers, FX conversion counts, path continuity (`CONTINUITY_QFLAG`), and anomaly signatures.

---

## 5. Functional Requirements

### FR-1: Memory-Safe Full-Dataset Ingestion & Feature Grouping
* **FR-1.1:** Process the ~4GB dataset via out-of-core streaming (**DuckDB** with `memory_limit = '4GB'` or **Polars** lazy frames); never load the raw 4GB CSV into Pandas RAM.
* **FR-1.2:** Partition all 20 columns into **7 mutually exclusive Feature Type Groups**:
  1. **Temporal & Local Timezone Dynamics** (`EPOCH_SECONDS` + BIC country local time + GDP)
  2. **Payment Values & Currency Mechanics** (`USD_AMOUNT`, `CURRENCY_CODE`, `CURRENCY_CONVERSION_COUNT`)
  3. **Party Types & B2B / C2C / B2C Flows** (`ORDERING_TYPE`, `BENEFICIARY_TYPE`)
  4. **Routing Chains, Cover Payments & Duration** (`TRANSACTION_TYPE_CODE`, `BIC8_PATH`, `PARTICIPANT_COUNT`, `CONTINUITY_QFLAG`, `TOTAL_DURATION`)
  5. **Party Text & Token Structure** (`ORDERING_DETAILS`, `ORDERING_TOKENS`, `BENEFICIARY_DETAILS`, `BENEFICIARY_TOKENS`)
  6. **Account Graph & Repeat Behavior** (`ORDERING_ACCOUNT`, `BENEFICIARY_ACCOUNT`, `ORDERING_BIC8`, `BENEFICIARY_BIC8`)
  7. **Anomaly & Fraud Signatures** (`ANOMALY_TYPE` across all 5 categories)

### FR-2: Feature Enrichment & Meta-Feature Generation
* **FR-2.1 (BIC Country Extraction):** Extract `ordering_country = SUBSTR(ORDERING_BIC8, 5, 2)` and `beneficiary_country = SUBSTR(BENEFICIARY_BIC8, 5, 2)`.
* **FR-2.2 (String & Token Meta-Features):** Compute currency/BIC string properties (first letter vowel/consonant, character lengths, path hop count, `...` gap indicator) and parse token counts/flags from `ORDERING_TOKENS` and `BENEFICIARY_TOKENS`.
* **FR-2.3 (External Macro & Timezone Join):** Join extracted country codes to an external reference table providing **Country GDP, GDP per capita, Region, Timezone offset, and Default Currency** to compute exact **Sender Local Hour** and **Receiver Local Hour**.
* **FR-2.4 (Account & Velocity Features):** Compute inter-transaction time deltas (`EPOCH_SECONDS` gaps), amount ratios relative to sender historical median (for `FAT_FINGER_MISTAKE`), and same-invoice/beneficiary account switches (for `ACCOUNT_REPLACEMENT_SCAM`).

### FR-3: Causal Rule Discovery, Full-4GB Verification & Negative Results
* **FR-3.1 (Causal & Surrogate Rule Mining):** Train shallow Decision Trees (`max_depth=3` to `4`) and LightGBM + SHAP models on stratified 200,000-row samples—rotating each target (`USD_AMOUNT`, `TRANSACTION_TYPE_CODE`, `TOTAL_DURATION`, `CONTINUITY_QFLAG`, `ANOMALY_TYPE`)—to isolate explicit `IF -> THEN` generator logic beyond simple bivariate correlation.
* **FR-3.2 (Full-4GB Verification):** Validate every rule across **100% of the 4GB dataset** via DuckDB SQL queries, logging exact sample sizes ($N$), conditional medians/means, lift ratios, and $p$-values (Mann-Whitney U / Chi-Square).
* **FR-3.3 (Partial & Negative Result Documentation):** Explicitly document tested hypotheses that yielded null or partial results (e.g., spurious volume patterns disproved after controlling for randomization), as rigorously grounded negative results are explicitly rewarded by judges.

### FR-4: Publication-Grade PDF Deliverables
* **FR-4.1 (Dashboard PDF — Strictly 5 to 15 Pages):**
  * Organized by Feature Type Group (1–2 dashboard pages per group across the 7 groups = 7–14 pages).
  * Each dashboard page MUST state the reconstructed business rule(s) clearly and display at least one high-resolution (`300 DPI`) supporting chart with exact statistical proof ($N$, effect size, $p$-value).
* **FR-4.2 (Slide Deck PDF — Strictly 10 to 20 Slides Total):**
  * Includes Title/Intro, Methodology & Causal Verification Framework, at most **one slide per Feature Type Group** (7 slides), Partial/Negative Results & Edge-Case Audit (1–2 slides), and Executive Synthesis (12–14 slides total).
  * Each rule slide must restate the reconstructed rule, display/reference the supporting chart, and explain the underlying real-world economic/payment behavior.

---

## 6. Non-Functional Requirements & Judging Rubric Alignment

* **NFR-1 (Memory Safety):** Peak RAM usage MUST remain under **6 GB** on local Windows hardware during full-4GB DuckDB queries and chart rendering.
* **NFR-2 (Clarity Over Decoration):** Understanding and clarity of insights take strict priority over visual style; charts must use clean comparison baselines, direct annotations, and zero decorative clutter.
* **NFR-3 (Reproducibility):** All DuckDB SQL queries, enrichment lookup files, statistical verification logs, and chart scripts must be saved cleanly in `src/` and `outputs/charts/`.

| Judging Criterion | Weight | Acceptance Criteria |
| :--- | :--- | :--- |
| **Insight Quality** | **45%** | 10–14 distinct, non-trivial generator rules uncovered across all 7 Feature Type Groups; zero raw-volume false positives. |
| **Evidence, Method & Data Integrity** | **23%** | 100% full-4GB SQL verification ($N$, lift, $p$-value), causal confounder controls, and documented partial/negative results. |
| **Communication** | **20%** | Valid PDFs exported within strict page bounds: **5–15 pages** (Dashboard PDF) and **10–20 slides** with max 1 slide per feature group (Slide Deck PDF). |
| **Interpretation & Economic Reasoning** | **12%** | Every rule explicitly linked to cross-border payment mechanics (cover payments, FX cutoffs, liquidity, or fraud typologies). |