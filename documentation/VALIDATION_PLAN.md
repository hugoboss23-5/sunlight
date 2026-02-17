# VALIDATION DATASET PLAN

## GOAL: 100 Contracts with Known Outcomes

### TARGET COMPOSITION:
- 50 Prosecuted Fraud Cases (TRUE POSITIVES to test)
- 50 Investigated but Cleared Cases (TRUE NEGATIVES to test)

---

## DATA SOURCES

### 1. PACER (Public Access to Court Electronic Records)
**What:** Actual court cases with fraud convictions  
**Cost:** $0.10/page (budget $50 for 500 pages)  
**Search terms:**
- "False Claims Act" + "procurement"
- "United States v." + contractor names
- 31 U.S.C. § 3729

### 2. DOJ Press Releases
**URL:** https://www.justice.gov/civil/press-releases  
**Filter:** Search "False Claims Act" + "contract fraud"  
**Advantage:** Free, includes settlement amounts and details

### 3. Inspector General Reports
**Sources:**
- DOD IG: https://www.dodig.mil/reports.html/
- GSA IG: https://www.gsaig.gov/
- NASA IG: https://oig.nasa.gov/

**Search:** "contractor fraud", "procurement irregularities"

### 4. Academic Papers
**Sources:**
- JSTOR, Google Scholar
- Search: "procurement fraud detection", "False Claims Act cases"
- Papers often include case appendices with details

### 5. GAO Reports
**URL:** https://www.gao.gov/  
**Search:** "contractor fraud", "procurement waste"  
**Contains:** Investigated but not prosecuted cases (our TRUE NEGATIVES)

---

## DATA COLLECTION TEMPLATE

For each case, collect:
```json
{
  "case_id": "US_v_Oracle_2011",
  "vendor": "Oracle Corporation",
  "contract_amount": 199500000,
  "agency": "Multiple Federal Agencies",
  "fraud_type": "Price Inflation",
  "markup_pct": 350,
  "outcome": "PROSECUTED",
  "settlement": 199500000,
  "year": 2011,
  "key_evidence": ["Whistleblower", "Internal emails", "Price comparison"],
  "contract_type": "Standard IT Software",
  "source": "DOJ_Press_Release_2011_08_01"
}
```

---

## WEEK 2 MILESTONES

**Monday-Tuesday:** Collect 25 prosecuted cases  
**Wednesday-Thursday:** Collect 25 cleared cases  
**Friday:** Run SUNLIGHT on all 50, measure performance  
**Weekend:** Document results, calculate sensitivity/specificity

---

## SUCCESS CRITERIA

**Minimum acceptable performance:**
- Sensitivity (true positive rate): >70%
- Specificity (true negative rate): >80%
- Positive Predictive Value: >50%

**If we fail these thresholds:** Major methodology revision needed

---

## CURRENT STATUS: 0/100 cases collected

**Next action:** Start with DOJ press releases (easiest source)
