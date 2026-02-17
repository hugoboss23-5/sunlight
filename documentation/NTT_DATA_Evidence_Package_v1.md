# SUNLIGHT Evidence Package #3
## NTT DATA FEDERAL SERVICES, INC.

**Classification:** YELLOW FLAG - Statistical Anomaly Detected  
**Generated:** February 2, 2026  
**Methodology Version:** 1.0

---

## Executive Summary

A USAID contract worth **$470.5 million** awarded to NTT DATA FEDERAL SERVICES, INC. exhibits extreme statistical deviation from both agency peers and the vendor's own contracting history. This contract represents a **526% markup** above the USAID peer median and a **Z-score of 8.74** - one of the highest anomaly scores in our database.

**Key Finding:** Unlike single-contract vendors, NTT DATA is an established federal contractor with **9 contracts** in our database. This $470M award is **3x larger than their next biggest contract** ($151.8M), making it a clear outlier even within their own portfolio.

---

## Contract Details

| Field | Value |
|-------|-------|
| **Contract ID** | 72MC1019M00011 |
| **Vendor** | NTT DATA FEDERAL SERVICES, INC. |
| **Agency** | Agency for International Development (USAID) |
| **Award Amount** | $470,511,408.97 |
| **Start Date** | May 1, 2019 |
| **End Date** | January 31, 2026 |
| **Duration** | 6.75 years |
| **Description** | THIS IS TO ESTABLISH FUNDING FOR THE NEW O&M CONTRACT IN THE AMOUNT OF $4,254,495.93 FROM MAY 1, 2019 - JULY 31, 2019. |
| **Number of Offers** | 0 (reported) |
| **Extent Competed** | None (reported) |

### Critical Observation: Description Mismatch

The contract description references **$4.25 million** for a 3-month period, yet the total award is **$470.5 million**. This 110x discrepancy between described scope and actual award warrants immediate scrutiny.

---

## Statistical Analysis

### Peer Group Definition
- **Agency:** Agency for International Development (USAID)
- **Time Window:** 2017-2021 (±2 years from contract date)
- **Peer Count:** 51 contracts

### Statistical Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Percentile** | 100.0th | Largest USAID contract in peer group |
| **Z-Score** | 8.74 | 8.74 standard deviations above mean |
| **Markup vs Median** | 526.4% | 6.3x the typical USAID contract |
| **95% Confidence Interval** | 495.4% - 606.6% | Markup range with statistical confidence |
| **Peer Median** | $75,107,996.75 | Typical USAID contract value |
| **Peer Mean** | $88,040,658.16 | Average USAID contract value |
| **Posterior Fraud Probability** | 26.9% | Bayesian estimate after base rate adjustment |

### Statistical Significance

- **Z-Score of 8.74** is extraordinary - corresponds to p < 0.000001
- This is the **highest Z-score** among our top 3 cases
- Contract is **statistically anomalous** at 99.9999% confidence level
- Probability of occurring by chance: less than 1 in 1,000,000

---

## Red Flags Identified

### 1. Extreme Statistical Outlier
- Z-score of 8.74 is nearly off the charts
- 100th percentile - literally the largest USAID contract in peer window
- 6.3x larger than the typical USAID award

### 2. Description-Amount Mismatch
The contract description states:
> "FUNDING FOR THE NEW O&M CONTRACT IN THE AMOUNT OF $4,254,495.93 FROM MAY 1, 2019 - JULY 31, 2019"

Yet the total award is **$470,511,408.97** - a 110x discrepancy. Either:
- The description was never updated after massive modifications
- The original scope bears no relation to actual spending
- Administrative error obscures true contract nature

### 3. No Competition Reported
- **Number of Offers:** 0
- **Extent Competed:** None
- Nearly half a billion dollars awarded without competitive bidding

### 4. Anomalous Within Vendor's Own Portfolio
NTT DATA's federal contract history:

| Contract | Amount | Agency |
|----------|--------|--------|
| **72MC1019M00011** | **$470.5M** | **USAID** ← OUTLIER |
| HHSM500201600012U | $151.8M | HHS |
| HHSD2002010372090003 | $123.6M | HHS |
| 140D0419F0075 | $82.9M | Interior |
| DJJ16PSSE2683 | $79.6M | DOJ |
| HSBP1016J00526 | $77.2M | DHS |
| 15BNAS20FV5F10003 | $58.3M | DOJ |
| 47QFPA19F0043 | $57.9M | GSA |
| 140D0419F0084 | $51.7M | Interior |

The USAID contract is **3.1x larger** than their next biggest award. This vendor typically operates in the $50-150M range.

---

## Dual Anomaly Analysis

This case is unique because the contract is anomalous on **two independent dimensions**:

### 1. Agency Peer Comparison
- 100th percentile among 51 USAID contracts
- Z-score: 8.74
- Markup: 526% above USAID median

### 2. Vendor Portfolio Comparison
- 3.1x larger than vendor's next biggest contract
- NTT DATA's typical contract: ~$90M average
- This contract: $470.5M

**When a contract is an outlier both for the agency AND for the vendor, the probability of legitimate explanation decreases significantly.**

---

## Peer Comparison

### USAID Contracts 2017-2021 (n=51)
```
├── Median:  $75.1M
├── Mean:    $88.0M
├── This Contract: $470.5M ← 100th percentile
└── Markup:  526% above median
```

### NTT DATA Portfolio (n=9)
```
├── Average (excl. outlier): $85.4M
├── Next Largest: $151.8M
├── This Contract: $470.5M ← 3.1x next largest
└── Internal Markup: 210% above their own average
```

---

## Methodology Notes

### Peer Group Selection
Contracts compared against same-agency awards within ±2 years of award date. This ensures comparison against relevant operational context and budget cycles.

### Statistical Thresholds
- **YELLOW Flag:** Z-score ≥ 3.0 OR percentile ≥ 97th
- **RED Flag:** Multiple corroborating signals required
- Conservative approach minimizes false positives

### Limitations
- Analysis based on publicly available USAspending.gov data
- Some contract modifications may not be reflected
- Industry-specific pricing factors not fully modeled
- This is statistical flagging, not accusation of wrongdoing

---

## Recommended Actions

1. **FOIA Request:** Obtain complete procurement file for 72MC1019M00011
2. **Modification History:** Request all contract modifications to explain $4.25M → $470.5M growth
3. **Justification Review:** Obtain sole-source justification for non-competitive award
4. **Scope Analysis:** Compare actual deliverables against O&M description
5. **USAID IG Referral:** Consider referral to USAID Office of Inspector General
6. **Vendor Interview:** Request explanation for contract size relative to their portfolio

---

## Data Sources

- **Contract Data:** USAspending.gov (accessed January 2026)
- **Statistical Analysis:** SUNLIGHT Fraud Detection System v1.0
- **Peer Group:** 51 USAID contracts, 2017-2021
- **Vendor Portfolio:** 9 NTT DATA contracts in database

---

## Classification Justification

This contract receives YELLOW classification based on:

| Criterion | Threshold | Actual | Met? |
|-----------|-----------|--------|------|
| Z-Score | ≥ 3.0 | 8.74 | ✓ |
| Percentile | ≥ 97th | 100th | ✓ |
| Peer Count | ≥ 20 | 51 | ✓ |
| Vendor Portfolio Outlier | — | 3.1x next largest | ✓ |
| Description Mismatch | — | 110x discrepancy | ✓ |

**Confidence Level:** VERY HIGH - Multiple independent statistical tests plus qualitative red flags confirm anomaly.

---

## Comparison to Other SUNLIGHT Cases

| Case | Vendor | Amount | Z-Score | Key Factor |
|------|--------|--------|---------|------------|
| #1 | REMOTE MEDICINE INC. | $483.8M | 7.93 | Single-contract vendor |
| #2 | COVENANT AVIATION | $480.1M | 5.05 | Single-contract, no competition |
| **#3** | **NTT DATA FEDERAL** | **$470.5M** | **8.74** | **Highest Z-score, dual anomaly** |

NTT DATA has the **highest statistical anomaly score** of our top 3 cases, despite being an established contractor with a track record.

---

*SUNLIGHT Project - Making Corruption Impossible to Hide*

**Disclaimer:** This analysis identifies statistical anomalies for further investigation. Statistical deviation alone does not constitute evidence of fraud or wrongdoing. All findings should be verified through appropriate legal and regulatory channels.
