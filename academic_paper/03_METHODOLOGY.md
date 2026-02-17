# 3. METHODOLOGY

## 3.1 Data Sources

### 3.1.1 USAspending.gov
Primary data source for federal contracts. Fields extracted:
- Award ID, Recipient Name, Award Amount
- Awarding Agency, Start Date, Description

### 3.1.2 OpenSecrets.org
Political donation data for quid pro quo detection.

### 3.1.3 Planned Sources
- FPDS (amendments, bid competition)
- Local databases (case studies)
- PACER (validation dataset)

## 3.2 Statistical Baseline Calculation

### 3.2.1 Size Categorization
Contracts categorized into five tiers:
- MICRO (<$100K), SMALL ($100K-$1M)
- MEDIUM ($1M-$5M), LARGE ($5M-$25M)
- MEGA (>$25M)

**Rationale:** Different size categories have different pricing dynamics.

### 3.2.2 Type Classification
- STRICT SCRUTINY: Standard IT, maintenance, supplies
- MEDIUM TOLERANCE: Aerospace, construction
- HIGH TOLERANCE: R&D, prototypes, classified

### 3.2.3 Baseline Calculation
For each contract C:
1. Find comparable set S (same agency, same size)
2. Calculate: median(S), mean(S), stdev(S)
3. Compute: markup% = ((C - median) / median) × 100
4. Compute: z-score = (C - mean) / stdev

## 3.3 Fraud Indicators

### 3.3.1 Price Inflation
Based on DOJ prosecuted cases:
- **High Risk:** >300% markup (standard items)
- **Medium Risk:** 200-300% markup
- **Investigation-Worthy:** >150% markup

### 3.3.2 Political Quid Pro Quo
- Vendor donation to official with procurement authority
- Contract awarded within 90 days
- Official on relevant committee

### 3.3.3 Vendor Concentration
- >20% of contracts in jurisdiction
- Suggests non-competitive bidding

## 3.4 Confidence Scoring

Combine multiple indicators:
1. Price inflation severity
2. Contract type strictness
3. Political donation presence
4. Vendor concentration
5. Sample size adequacy

Final confidence = mean(active_factors) - sample_penalty
Capped at 95% (investigation still needed)

## 3.5 Three-Tier Classification

### 🔴 RED (80-95% confidence)
- Multiple indicators (2+)
- Standard items
- Recommend immediate IG investigation

### 🟡 YELLOW (65-80% confidence)  
- Single strong indicator
- Warrants auditor review

### 🟢 GREEN (<65% confidence)
- Insufficient evidence
- Normal or need more data

## 3.6 Legal Framework Alignment

Each indicator maps to specific statutes:
- Price Inflation → False Claims Act (31 U.S.C. § 3729)
- Quid Pro Quo → Anti-Kickback Act (41 U.S.C. § 8702)
- Concentration → Procurement Integrity Act (41 U.S.C. § 2105)

## 3.7 Evidence Packages

Each flagged contract includes:
- Statistical analysis (baseline, markup, z-score)
- Contract type classification
- All fraud indicators present
- Legal framework applicable
- Similar prosecuted cases
- Confidence calculation
- Source links

## 3.8 Validation Approach

1. Test on known fraud cases (Oracle, Boeing)
2. Statistical validation (false positive rate)
3. Expert review (professors, accountants)
4. Reproducibility (open source code)

## 3.9 Ethical Safeguards

- Frame as "exhibits indicators" not "is fraud"
- Show all calculations
- Disclose limitations
- Conservative bias (err toward not flagging)

## 3.10 Limitations

**Current:**
- Limited sample (477 contracts)
- No amendment data
- No bid competition data
- Text-based classification (imperfect)

**Future Improvements:**
- FPDS integration
- Vendor network mapping
- Real-time monitoring
- International expansion
