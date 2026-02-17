# SUNLIGHT Minimum Viable Launch Definition

## Purpose
This document defines exactly what "launch" means for SUNLIGHT. It prevents scope creep, sets quality gates, and provides clear success criteria for April 2026.

---

## Launch Date
**Target:** April 15, 2026  
**Fallback:** June 1, 2026 (acceptable ONLY if quality gates cannot be met)

---

## Minimum Viable Deliverables

### 1. Evidence Packages: 3 Required (not 5)

| # | Contract | Vendor | Why Selected |
|---|----------|--------|--------------|
| 1 | 36C10G25K0180 + 36C10G24K0098 | OPTUM | Pattern evidence (2 contracts, same vendor) |
| 2 | DAAH0102CR190 | JVYS | Tightest confidence interval (251%-384%) |
| 3 | N0001916C0003 | BELL TEXTRON | Largest peer group (1,594 comparables) |

**Each package must include:**
- [ ] Contract details (ID, vendor, agency, amount, date, USASpending link)
- [ ] Plain-English statistical summary (using output template)
- [ ] Peer group definition and list
- [ ] 5-test results with explanations
- [ ] Legitimacy Checklist completed and signed
- [ ] Legal framework (False Claims Act citations)
- [ ] Investigative leads (if any found)
- [ ] Prosecutor recommendation

**Quality gate:** No package goes external until Legitimacy Checklist has two sign-offs.

---

### 2. Professor Endorsements: 1 Secured, 2 In Conversation

| Status | Requirement |
|--------|-------------|
| MUST HAVE | 1 signed endorsement letter |
| SHOULD HAVE | 2 professors reviewing methodology |
| NICE TO HAVE | 3 total endorsements |

**Endorsement = signed letter stating:**
> "I have reviewed SUNLIGHT's statistical methodology and find it to be rigorous, replicable, and appropriate for identifying procurement pricing anomalies."

**Quality gate:** Professor must pass conflict-of-interest screening before outreach.

---

### 3. Methodology Paper: Submitted to arXiv

| Component | Status |
|-----------|--------|
| Abstract | Required |
| Data description | Required |
| Peer-group matching algorithm | Required |
| 5-test methodology | Required |
| Validation results (90% DOJ detection) | Required |
| Limitations section | Required |
| Code appendix | Optional |

**Quality gate:** One statistics professor reviews before submission.

---

### 4. World Bank: Meeting Scheduled

| Milestone | Required for Launch? |
|-----------|---------------------|
| Meeting scheduled | YES |
| Meeting completed | NO |
| Contract signed | NO |
| LOI received | NO |

**Launch requires a confirmed meeting date, not a closed deal.**

---

### 5. Infrastructure: Operational

| Component | Status |
|-----------|--------|
| sunlight.db with clean data | ✅ Complete |
| bulletproof_analyzer.py | ✅ Complete |
| bulletproof_scraper.py | ✅ Complete |
| Data quality monitor | Ready to deploy |
| Vendor history script | Ready to deploy |

**Quality gate:** Run data quality monitor before any new analysis.

---

## NOT Required for Launch

These are v2.0 features, not launch blockers:

- [ ] Web interface / dashboard
- [ ] Real-time monitoring
- [ ] Automated alerts
- [ ] API access
- [ ] More than 3 evidence packages
- [ ] More than 1 professor endorsement
- [ ] World Bank contract signed
- [ ] Press coverage
- [ ] CORTEX orchestration layer
- [ ] Additional data sources beyond USASpending

---

## Launch Checklist

### Week of Feb 3-9
- [ ] Deploy data quality monitor, create baseline
- [ ] Run vendor history on OPTUM, JVYS, BELL TEXTRON
- [ ] Begin Evidence Package #1 (OPTUM - pattern case)
- [ ] Identify 3 target professors

### Week of Feb 10-16
- [ ] Complete Evidence Package #1
- [ ] Begin Evidence Package #2 (JVYS)
- [ ] Send professor outreach emails
- [ ] Draft methodology paper outline

### Week of Feb 17-23
- [ ] Complete Evidence Package #2
- [ ] Begin Evidence Package #3 (BELL TEXTRON)
- [ ] Follow up with professors
- [ ] Draft methodology paper

### Week of Feb 24 - Mar 2
- [ ] Complete Evidence Package #3
- [ ] Secure first professor endorsement
- [ ] Finalize methodology paper
- [ ] Submit to arXiv

### Week of Mar 3-9
- [ ] Begin World Bank outreach
- [ ] Second professor review
- [ ] Refine packages based on feedback

### Week of Mar 10-31
- [ ] Schedule World Bank meeting
- [ ] Prepare pitch materials
- [ ] Secure second endorsement (if possible)

### April 1-15
- [ ] World Bank meeting
- [ ] LAUNCH

---

## Decision Rules

### When to delay launch:
- Evidence package has unresolved Legitimacy Checklist item
- Zero professor endorsements secured
- Methodology paper not submitted
- Data quality monitor shows critical alerts

### When NOT to delay launch:
- Only 3 packages instead of 5
- Only 1 endorsement instead of 3
- World Bank meeting scheduled but not completed
- No press coverage
- No web interface

---

## Success Metrics (Post-Launch)

| Metric | Target | Timeframe |
|--------|--------|-----------|
| World Bank LOI | Signed | 60 days post-launch |
| Second institution meeting | Scheduled | 90 days post-launch |
| Zero false positive accusations | 100% | Ongoing |
| Methodology paper citations | 1+ | 6 months |

---

## Sign-Off

| Role | Name | Date |
|------|------|------|
| Project Lead | Rim | |
| Operations | Hugo | |
