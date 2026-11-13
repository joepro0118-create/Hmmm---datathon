# UMDAC Datathon 2026 — Team Action Plan & Remaining Deliverables

**Compliance Rule:** Strictly **100% internal Swift dataset features only** (`10,000,000` rows, `20` Appendix A.1 columns + `DISCLAIMER`). Zero external CSVs, GDP tables, timezone files, or APIs.

---

## 1. Current Project Status (What Is Already Built)

| Component | File / Path | Status | Details |
| :--- | :--- | :--- | :--- |
| **Repo & Git Safety** | [`.gitignore`](.gitignore) | Done | Blocks `*.csv`, `*.parquet`, `*.duckdb`, `*.wal`, `data/`; allows `outputs/charts/*.png`. |
| **PRD & Spec** | [`PRDDatathon.md`](PRDDatathon.md) | Done | 7 Feature Type Groups, judging rubric, and PDF page bounds. |
| **4GB Profiler & Sampler** | [`src/01_profile_and_mine.py`](src/01_profile_and_mine.py) | Done | Verified `10,000,000` rows, `0%` nulls on 19 core columns, `7,006` labeled anomalies across 6 classes. |
| **200K Stratified Sample** | `data/sample_200k.parquet` | Done | `25.6 MB` Parquet with all `7,006` anomaly rows + `192,994` stratified normal rows. |
| **Deep Causal & 10M Verification** | [`src/02_deep_rule_mining.py`](src/02_deep_rule_mining.py) | Done | Ran `max_depth=3` decision trees + full 10M-row DuckDB SQL verification across Groups 0–7. |
| **300 DPI Charts** | `outputs/charts/*.png` | **Not Built** | Folder is currently empty. |
| **Shared Rule Tracker (8-Col)** | `outputs/rule_tracker.md` (or `.csv`) | **Not Built** | Needs `[Confirmed]`/`[Partial]` tags, $p$-values, confounder checks, and Rejected Hypotheses log. |
| **Dashboard PDF** | `outputs/Dashboard_Swift_2026.pdf` | **Not Built** | Must be **5–15 pages** (target `10–12`), grouped by the 7 Feature Type Groups. |
| **Slide Deck PDF** | `outputs/SlideDeck_Swift_2026.pdf` | **Not Built** | Must be **10–20 slides** (target `12–14`), max **1 slide per Feature Type Group**. |

---

## 2. Person-by-Person Task Breakdown & Deliverables

### Person 1: Joe / Lead — *Lead Data & Rule Architect*
**Owned Groups:** Group 2 (Payment Values & Currency), Group 4 (Routing & Duration), Group 5 (Party Text & Tokens)

* **Already Completed:**
  * Workspace setup, `.gitignore`, `src/01_profile_and_mine.py`, `data/sample_200k.parquet`, and `src/02_deep_rule_mining.py`.
* **Remaining Tasks:**
  1. **Methodology & Out-of-Core Architecture Summary:** Document the DuckDB (`memory_limit = '4GB'`) + stratified `200k` Parquet (`max_depth=3` decision trees) + 10M-row SQL verification pipeline.
  2. **Data Cleaning & Sensitivity Log (Rubric 3.1):** Summarize Group 0 audit findings:
     * `DISCLAIMER` appears in `1 / 10,000,000` rows (confirming synthetic generator rules + NumPy + Faker).
     * `CONTINUITY_QFLAG = 'N'` (`767,204` rows) $\iff$ `'...'` in `BIC8_PATH` (`0` mismatches).
     * `PARTICIPANT_COUNT` = exact count of observable BIC8s in `BIC8_PATH` (`0` mismatches).
     * `~5.0%` start/end correspondent gateway mismatch (`498,399` start / `499,265` end).
  3. **AI & Tool Disclosure (Rubric 3.4):** List tools used (Python, DuckDB, scikit-learn, Matplotlib/Seaborn, AI coding assistant) and explicitly attest **zero external data** was used.
  4. **Final Export QA (with Person 3):** Verify Dashboard PDF is **5–15 pages** and Slide Deck PDF is **10–20 slides**.

* **Deliverables Owned by Person 1:**
  * `src/` codebase (already complete).
  * **Methodology, Data Cleaning & Sensitivity Log (3.1)** slide/section text.
  * **AI / Tool Disclosure (3.4)** slide/section text.

---

### Person 2: *Verification, Confounder & Anomaly Lead*
**Owned Groups:** Group 1 (Temporal & Clocks), Group 3 (Party Types `B` vs `C`), Group 6 (Account Graph), Group 7 (Anomaly & Fraud Signatures)

* **Already Completed:**
  * Full 10M-row SQL metrics for Groups 1, 3, 6, 7 are already computed in `src/02_deep_rule_mining.py`.
* **Remaining Tasks:**
  1. **Compute Formal $p$-Values & Confounder Controls:** Run Mann-Whitney U / Chi-Square tests on the `10M` / `200k` strata and verify every rule holds after controlling for confounders (e.g., `ORDERING_TYPE`, `CURRENCY_CODE`, domestic vs. cross-border).
  2. **Build the 8-Column Master Rule Verification Table:** Log all confirmed and partial rules using the exact rubric schema:
     1. Feature Type Group
     2. Status Tag (`[Confirmed]` vs. `[Partial / Uncertain]`)
     3. One-Sentence Headline Rule (Condition + Effect + Quantified Size vs. Baseline)
     4. Full 5-Part Specification (When it applies, what changes, by how much, $N$, boundary limits)
     5. Confounder Check & Alternative Tested
     6. Observed in Data vs. Economic Interpretation
     7. Full-4GB SQL Proof ($N$, median/rate, lift ratio, $p$-value)
     8. Chart File Path (`outputs/charts/...png`)
  3. **Write the Rejected Hypotheses & Edge-Case Audit:** Document negative/partial results rigorously:
     * *Rejected:* Currency first-letter consonant vs. vowel `3x` rule (actually `0.59x` consonant/vowel median; driven by `USD`/`EUR` starting with vowels, not a letter rule).
     * *Rejected:* `CONTINUITY_QFLAG = 'N'` (`'...'` gap) increases `TOTAL_DURATION` (false: holding hops fixed, `Direct` `'Y'` vs `'N'` median duration is identical at `39.0s`).
     * *Edge Case / Partial:* Beneficiary street address country matches `BENEFICIARY_BIC8` country only `0.98%` of the time (vs. `100.0%` for ordering party).
     * *Undocumented Discovery:* `CUSTOMER_RECALL` (`317` rows) is a 6th `ANOMALY_TYPE` not listed in Appendix A.1, marked by `+44%` higher path discontinuity (`11.04%` `QFLAG='N'`).
  4. **Phase 3 Rubric Compliance Audit:** Verify zero external data, zero raw-volume traps, and 1:1 linkage between claims and charts/tables.

* **Deliverables Owned by Person 2:**
  * **Master Rule Verification Table** (`outputs/rule_tracker.md`).
  * **Rejected Hypotheses & Edge-Case Audit** slide/section content.
  * **Phase 3 Compliance Sign-Off.**

---

### Person 3: *Visual Analytics & Narrative Lead*
**Owned Groups:** Cross-Group Visual Synthesis & Executive Storytelling (All 7 Feature Type Groups)

* **Remaining Tasks:**
  1. **Generate `300 DPI` Comparison Charts (`outputs/charts/*.png`):**
     * One clear point per chart, **1-sentence takeaway rule as chart title**, explicit comparison baseline, zero clutter.
     * Recommended chart set (9–11 PNGs):
       * `group1_temporal_weekday_local_clock.png` — Weekday vs. Weekend `-69.2%` drop & `+2h` Consumer (`C`) vs. Business (`B`) internal local clock shift.
       * `group2_currency_regimes_fx.png` — Shared home currency (`$5,164`–`$5,672`, `67%–69%` `0` FX) vs. Third-vehicle currency (`45%–48%` `>=2` FX, `Direct` drops to `48%–51%`).
       * `group3_party_flow_amounts.png` — 3-tier geometric scaling (`C2C` `$463` $\to$ `B2C/C2B` `$3,119–$3,229` $\to$ `B2B` `$22,888`, `49.4x` lift).
       * `group4_routing_duration_scaling.png` — `PARTICIPANT_COUNT = 2` (`Direct`) vs. `>=3` (`Indirect`/`Covered`), linear `+200s/hop` duration scaling, & `Covered` 3-hop `3.27x` latency penalty.
       * `group5_token_exclusivity_iban_stp.png` — 100% `B` vs. `C` token exclusion (`business` vs. `first/last_name`), 100% IBAN-to-BIC8 encoding, & missing-IBAN `+49%` STP delay (`82s` vs. `55s`).
       * `group6_account_fanout_mule_ring.png` — `1,068`-account cross-scam Money Mule Network (`352` shared mules capturing `56.8%` of fraud tx).
       * `group7_anomaly_signatures_6classes.png` — Multi-panel fingerprint of all **6** anomalies (`ROMANCE_SCAM`, `FAT_FINGER_MISTAKE`, `CEO_SCAM`, `DUPLICATE_PAYMENT`, `ACCOUNT_REPLACEMENT_SCAM`, `CUSTOMER_RECALL`).
       * `rejected_hypotheses_audit.png` — Visual proof of disproved Vowel/Consonant rule & `CONTINUITY_QFLAG` duration invariance.
  2. **Write Narrative Copy (Rubric 1.4, 2.1, 2.2):**
     * Crisp 1-sentence **Headline Rule** per group.
     * Strict separation of **"Observed in Data"** vs. **"Economic Interpretation"**.
     * **Two competing real-world explanations** for at least one key rule (e.g., *Why do `Covered` 3-hop payments take `288s` median vs. `88s` for `Indirect`? Explanation A: Dual-message MT103 + MT202COV reconciliation delay; Explanation B: High-value/domestic nostro-vostro liquidity batching*).
  3. **Assemble Dashboard PDF (`5–15` pages, target `10–12`):**
     * Overview/Title page + 1–2 pages per Feature Type Group (each stating the rule, $N$, effect size, $p$-value, and chart).
  4. **Assemble Slide Deck PDF (`10–20` slides, target `12–14`):**
     * Slide 1: Title & Executive Synthesis
     * Slide 2: Methodology, Data Cleaning & Sensitivity Log (from Person 1)
     * Slides 3–9: **1 slide per Feature Type Group** (strictly max 1 slide per group)
     * Slide 10: Rejected Hypotheses & Edge-Case Audit (from Person 2)
     * Slide 11: AI / Tool Disclosure & Zero-External-Data Attestation (from Person 1)
     * Slide 12: Final Takeaways & Operational Impact

* **Deliverables Owned by Person 3:**
  * `outputs/charts/*.png` (`300 DPI` charts)
  * **Dashboard PDF** (`5–15` pages)
  * **Slide Deck PDF** (`10–20` slides)

---

## 3. Quick Hand-Off Checklist

- [ ] **Person 2:** Generate `outputs/rule_tracker.md` with $p$-values, `[Confirmed]`/`[Partial]` tags, and Rejected Hypotheses log.
- [ ] **Person 3:** Generate `outputs/charts/*.png` (`300 DPI`) from verified 10M-row & 200k-row stats.
- [ ] **Person 1 + Person 2:** Supply Methodology/Data Cleaning (3.1), AI Disclosure (3.4), and Rejected Hypotheses text.
- [ ] **Person 3 + Person 1:** Build & export **Dashboard PDF (`5–15` pages)** and **Slide Deck PDF (`10–20` slides)**, then run final page-count & compliance check.
