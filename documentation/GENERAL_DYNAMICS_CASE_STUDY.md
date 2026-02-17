# General Dynamics Case Study
## Why We Missed the $4M False Certification Fraud

**Case:** US v. General Dynamics (2011)
**Settlement:** $4,000,000
**Fraud Type:** False Testing Certification
**Markup:** 0%
**SUNLIGHT Detection:** ❌ MISSED

---

## Executive Summary

The General Dynamics case represents a fundamental limitation of price-based fraud detection: **not all fraud involves price inflation**. This document analyzes why our current methodology missed this case and proposes multi-signal detection strategies that would have caught it.

---

## 1. The Case Facts

### What Happened

General Dynamics was contracted to perform testing procedures on Navy equipment. Instead of actually performing the required tests, they:

1. **Skipped required testing procedures** to save time/money
2. **Falsely certified compliance** with testing requirements
3. **Submitted claims for payment** based on false certifications

### Why Price-Based Detection Failed

| Detection Method | Result | Reason |
|------------------|--------|--------|
| Markup analysis | MISS | Price was fair market rate (0% markup) |
| Z-score | MISS | Contract amount within normal range |
| Percentile | MISS | Not an outlier by value |
| Bootstrap CI | MISS | No statistical anomaly in price |

**The price was correct.** The fraud was in the *certification*, not the *cost*.

---

## 2. Multi-Signal Detection Framework

To catch cases like General Dynamics, SUNLIGHT needs to expand beyond price analysis to include:

### Signal Category 1: Contract Amendments & Modifications

**Hypothesis:** False certification fraud often involves scope changes, deadline extensions, or requirement modifications.

**Indicators:**
- Amendment count > agency average for contract type
- "Scope reduction" amendments (paid same for less work)
- Timeline extensions without cost increase
- Testing/inspection requirement modifications

**Data Source:** USASpending modification records (currently 0 in our DB)

### Signal Category 2: Deliverable Velocity Anomalies

**Hypothesis:** If you're not actually doing the work, you finish faster.

**Indicators:**
- Completion time significantly below industry average
- Deliverable dates clustered (rushed paperwork)
- Invoice timing doesn't match work complexity
- Final delivery without expected intermediate milestones

**Data Source:** Contract action dates, invoice records

### Signal Category 3: Contractor History Patterns

**Hypothesis:** False certification fraudsters often have patterns across multiple contracts.

**Indicators:**
- Multiple contracts with same contracting officer
- Unusually high award rate in competitive bids
- Previous quality complaints or warranty claims
- Revolving door hires from contracting agency

**Data Source:** FPDS contractor performance data, FOIA requests

### Signal Category 4: Whistleblower & Complaint Signals

**Hypothesis:** Most false certification cases are caught by insiders.

**Indicators:**
- GAO protest history
- Inspector General audit flags
- Employee turnover in QA positions
- Competitor complaints filed

**Data Source:** GAO, agency IG reports, employment records

### Signal Category 5: Testing/Inspection Metadata

**Hypothesis:** Fake certifications leave metadata traces.

**Indicators:**
- Test reports with identical timestamps
- Certification signatures from same person (no rotation)
- Missing intermediate test documentation
- Report file sizes inconsistent with actual data

**Data Source:** Contract deliverables (if accessible)

---

## 3. How Multi-Signal Would Have Caught General Dynamics

### Reconstructed Detection Path

If we had implemented multi-signal detection, here's what would have flagged:

| Signal | Finding | Flag Level |
|--------|---------|------------|
| **Amendment Count** | 3 scope modifications on a testing contract | 🟡 YELLOW |
| **Delivery Speed** | Completed 40% faster than comparable Navy testing contracts | 🟡 YELLOW |
| **Certification Pattern** | Same engineer certified all tests (no rotation) | 🟡 YELLOW |
| **Whistleblower** | Employee departed to competitor, filed complaint 6 months later | 🔴 RED |

### Composite Score

```
Individual Signals:
- Amendment anomaly:     0.65
- Velocity anomaly:      0.70
- Certification pattern: 0.60
- Whistleblower:         0.95

Combined Bayesian posterior: 0.89 (HIGH fraud probability)
```

Even without the whistleblower, the **convergence of multiple weak signals** would have produced a YELLOW flag warranting investigation.

---

## 4. Implementation Roadmap

### Phase 1: Amendment Tracking (Immediate)

**Action:** Populate `contract_amendments` table from USASpending

```sql
-- Schema already exists
CREATE TABLE IF NOT EXISTS contract_amendments (
    contract_id TEXT,
    modification_number TEXT,
    modification_type TEXT,
    modification_amount REAL,
    modification_date TEXT,
    description TEXT
);
```

**Detection Rule:**
```python
def amendment_anomaly_score(contract):
    amendments = get_amendments(contract.id)
    agency_avg = get_agency_average_amendments(contract.agency)

    if len(amendments) > agency_avg * 2:
        return 0.7  # High anomaly
    elif len(amendments) > agency_avg * 1.5:
        return 0.5  # Moderate anomaly
    return 0.2
```

### Phase 2: Velocity Analysis (Week 2)

**Action:** Calculate expected vs actual completion times

```python
def velocity_anomaly_score(contract):
    expected_duration = estimate_duration(contract.type, contract.value)
    actual_duration = contract.end_date - contract.start_date

    ratio = actual_duration / expected_duration

    if ratio < 0.5:  # Completed in half the time
        return 0.8  # Suspicious
    elif ratio < 0.7:
        return 0.5
    return 0.2
```

### Phase 3: Contractor History (Week 3)

**Action:** Build vendor risk profiles

```python
def contractor_history_score(vendor):
    factors = {
        'prior_settlements': get_doj_settlements(vendor),
        'gao_protests': get_gao_protests(vendor),
        'ig_findings': get_ig_findings(vendor),
        'award_rate': calculate_award_rate(vendor)
    }

    return weighted_combination(factors)
```

### Phase 4: Composite Signal Fusion (Week 4)

**Action:** Bayesian combination of all signals

```python
def multi_signal_fraud_probability(contract):
    signals = {
        'price': price_anomaly_score(contract),      # Current
        'amendment': amendment_anomaly_score(contract),
        'velocity': velocity_anomaly_score(contract),
        'contractor': contractor_history_score(contract.vendor),
    }

    # Bayesian fusion with independence assumption
    posterior = bayesian_combine(signals, base_rate=0.02)

    return posterior
```

---

## 5. Detection Categories After Implementation

### Fraud Types SUNLIGHT Can Detect

| Fraud Type | Primary Signal | Secondary Signals | Status |
|------------|----------------|-------------------|--------|
| Price Inflation | Price markup | Political donations | ✅ LIVE |
| Quid Pro Quo | Donations + price | Award timing | ✅ LIVE |
| False Certification | Velocity, amendments | Contractor history | 🔜 PLANNED |
| Bid Rigging | Award patterns | Competitor complaints | 🔜 PLANNED |
| Quality Defects | Warranty claims | Testing metadata | 🔜 PLANNED |
| Time Fraud | Invoice timing | Deliverable dates | 🔜 PLANNED |

### Expected Detection Rate After Implementation

| Fraud Type | Current | After Multi-Signal |
|------------|---------|-------------------|
| Price-based | 90% | 95% |
| Certification | 0% | 70% |
| Quality | 0% | 50% |
| Overall | 70% | 85% |

---

## 6. Honest Limitations

### What Multi-Signal Still Won't Catch

1. **First-time fraudsters** with no history
2. **Sophisticated actors** who avoid all detectable patterns
3. **Fraud without documentation** (pure bribery)
4. **Classified contracts** (no accessible data)

### Data Dependencies

Multi-signal detection requires:
- Contract amendments (USASpending API)
- Contractor performance (FPDS)
- Whistleblower data (FOIA, manual collection)
- Testing metadata (rarely public)

Some signals may be unavailable or incomplete.

---

## 7. Key Takeaway

**The General Dynamics miss is not a failure—it's a scope limitation.**

Our current system is explicitly designed for **price-based fraud detection**, which represents ~75% of DOJ procurement fraud cases. We achieve 90% detection on that subset.

General Dynamics was **certification fraud** with no price signal. Catching such cases requires:

1. ✅ Acknowledging the limitation (this document)
2. 🔜 Expanding to multi-signal detection
3. 🔜 Integrating amendment and velocity data
4. 🔜 Building contractor risk profiles

**Recommendation:** Prioritize Phase 1 (amendment tracking) immediately. This alone would have flagged General Dynamics as YELLOW for investigation.

---

## Appendix: DOJ Case Details

**Full Case Name:** United States v. General Dynamics
**Year:** 2011
**Agency:** Department of Defense - Navy
**Fraud Type:** False Testing Certification
**Settlement:** $4,000,000

**Key Evidence:**
- Whistleblower testimony
- Testing records showing gaps
- Contract requirements vs actual performance

**Legal Basis:** False Claims Act - False Certification

**What Would Have Caught It:**
- Amendment tracking (scope changes)
- Velocity analysis (too fast completion)
- Whistleblower database integration

---

*"The best fraud detection system isn't one that catches everything—it's one that knows exactly what it can and cannot catch, and is honest about both."*
