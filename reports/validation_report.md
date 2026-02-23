# SUNLIGHT DOJ Validation Report

**Date:** 2026-02-23
**Methodology Version:** 2.0.0
**Bootstrap Iterations:** 1,000

---

## Executive Summary

Validated SUNLIGHT scoring pipeline against **10 DOJ-prosecuted fraud cases** and **200 known-clean contracts**.

- **9** cases involve price-based fraud (detectable by statistical analysis)
- **1** case(s) involve non-price fraud (outside scope — e.g., false certification)

---

## Classification Metrics

| Metric | Value |
|---|---|
| **Precision** | 28.1% |
| **Recall** | 100.0% |
| **F1 Score** | 43.9% |
| **Accuracy** | 89.0% |
| **Specificity** | 88.5% |

---

## Confusion Matrix

| | Predicted Positive (RED/YELLOW) | Predicted Negative (GREEN/GRAY) |
|---|---|---|
| **Actual Fraud** (DOJ price cases) | TP = 9 | FN = 0 |
| **Actual Clean** (below-median) | FP = 23 | TN = 177 |

---

## Value-Weighted Metrics

| Metric | Value |
|---|---|
| Total fraud value (price cases) | $941,400,000 |
| Detected fraud value | $941,400,000 |
| **Value recall** | 100.0% |

---

## Per-Case Results

| Case | Vendor | Fraud Type | Markup | Tier | Detected |
|---|---|---|---|---|---|
| US_v_Oracle_2011 | Oracle Corporation | Price Inflation | 350% | RED | YES |
| US_v_Boeing_2006 | Boeing Company | Spare Parts Overcharging | 450% | RED | YES |
| US_v_DynCorp_2005 | DynCorp International | Labor Rate Inflation | 75% | YELLOW | YES |
| US_v_United_Technologies_2015 | United Technologies Corporation | Quid Pro Quo + Price Inflation | 250% | YELLOW | YES |
| US_v_General_Dynamics_2011 | General Dynamics | False Testing Certification | N/A | GREEN | NO |
| US_v_Lockheed_Martin_2012 | Lockheed Martin | Defective Parts + Price Inflation | 320% | RED | YES |
| US_v_Northrop_Grumman_2009 | Northrop Grumman | Conflict of Interest | 180% | YELLOW | YES |
| US_v_CACI_2010 | CACI International | Time Fraud + Price Inflation | 240% | YELLOW | YES |
| US_v_Raytheon_2014 | Raytheon Company | Defective Product | 150% | YELLOW | YES |
| US_v_BAE_Systems_2010 | BAE Systems | Labor Mischarging | 190% | YELLOW | YES |

---

## Per-Category Breakdown

| Fraud Category | Cases | Detected | Detection Rate |
|---|---|---|---|
| Conflict of Interest | 1 | 1 | 100% |
| Defective Parts + Price Inflation | 1 | 1 | 100% |
| Defective Product | 1 | 1 | 100% |
| False Testing Certification | 1 | 0 | 0% |
| Labor Mischarging | 1 | 1 | 100% |
| Labor Rate Inflation | 1 | 1 | 100% |
| Price Inflation | 1 | 1 | 100% |
| Quid Pro Quo + Price Inflation | 1 | 1 | 100% |
| Spare Parts Overcharging | 1 | 1 | 100% |
| Time Fraud + Price Inflation | 1 | 1 | 100% |

---

## Tier Distribution

### DOJ Cases

| Tier | Count |
|---|---|
| RED | 3 |
| YELLOW | 6 |
| GREEN | 1 |
| GRAY | 0 |

### Clean Contracts

| Tier | Count |
|---|---|
| RED | 4 |
| YELLOW | 19 |
| GREEN | 177 |
| GRAY | 0 |

---

## Methodology Notes

1. DOJ cases are scored using **synthesized contract amounts** that produce the documented markup relative to real comparable contracts from the database.
2. Clean contracts are **below-median, randomly sampled** from agencies with 10+ contracts.
3. Each case runs through the full `score_contract` + `assign_tier` pipeline path (Bootstrap CI, Bayesian posterior, z-scores).
4. **Non-price fraud** (e.g., General Dynamics false certification, 0% markup) is correctly excluded from precision/recall — SUNLIGHT is a price-anomaly detector, not a universal fraud detector.
5. FDR correction is **not applied** to individual DOJ case scoring (single-case mode). In production batch mode, FDR would further reduce false positives.
