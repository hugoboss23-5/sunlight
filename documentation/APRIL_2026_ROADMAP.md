# SUNLIGHT April 2026 Launch Roadmap
## From Prototype to Institutional-Grade Fraud Detection

**Target Launch:** April 15, 2026
**Current Date:** January 28, 2026
**Time Remaining:** 11 weeks

---

## Executive Summary

### Current State (January 28, 2026)

| Metric | Status | Target |
|--------|--------|--------|
| Contracts in DB | 977 | 50,000+ |
| DOJ Case Detection | 90% (9/10) | 95% |
| RED Flags Generated | 126 | 3-5 bulletproof |
| Statistical Rigor | ✅ Bootstrap + Bayesian | ✅ Complete |
| Professor Endorsements | 0 | 2-3 |
| Published Methodology | Draft | Peer-reviewed |
| Political Donations | 4 records | 10,000+ |
| Contract Amendments | 0 records | Full coverage |

### Launch Requirements

1. **3-5 bulletproof RED cases** (95%+ prosecutable)
2. **Professor endorsements** (statistics, law, former prosecutor)
3. **Published methodology paper** (working paper minimum)
4. **Production system** (50K+ contracts, automated updates)

---

## Critical Launch Blockers

### 🚨 BLOCKER 1: Insufficient Comparable Data

**Problem:** Only 977 contracts limits comparison accuracy
**Impact:** Bootstrap CIs are wide; prosecutors want tighter bounds
**Solution:** Scale to 50K+ contracts via USASpending bulk download
**Owner:** Engineering
**Deadline:** February 14

### 🚨 BLOCKER 2: No Academic Validation

**Problem:** Zero professor endorsements
**Impact:** Institutional credibility gap; World Bank/IMF won't engage
**Solution:** Cold outreach + methodology paper submission
**Owner:** Founder
**Deadline:** March 15

### 🚨 BLOCKER 3: Political Donation Data Gap

**Problem:** Only 4 donation records (mock data)
**Impact:** Quid pro quo detection unreliable
**Solution:** FEC API integration + OpenSecrets bulk data
**Owner:** Data Engineering
**Deadline:** February 28

### 🚨 BLOCKER 4: No Contract Amendment Tracking

**Problem:** 0 amendments tracked
**Impact:** Cannot detect General Dynamics-style certification fraud
**Solution:** USASpending modifications API integration
**Owner:** Engineering
**Deadline:** March 7

### 🚨 BLOCKER 5: Case Selection Not Complete

**Problem:** 126 RED flags, need to identify 3-5 "bulletproof" ones
**Impact:** Cannot demonstrate to prosecutors without perfect cases
**Solution:** Manual review + additional evidence gathering
**Owner:** Analyst
**Deadline:** February 21

---

## Week-by-Week Milestones

### WEEK 1: January 27 - February 2
**Theme: Foundation Lock**

| Task | Owner | Acceptance Criteria | Status |
|------|-------|---------------------|--------|
| Complete institutional statistical rigor module | Engineering | Bootstrap CIs, Bayesian priors, FDR correction working | ✅ DONE |
| Run full analysis on current DB | Engineering | Tier distribution documented | ✅ DONE |
| Identify top 10 RED flag candidates | Analyst | List with preliminary evidence | 🔄 IN PROGRESS |
| Draft methodology paper outline | Founder | 10-page outline with sections | ⬜ TODO |

**THIS WEEK CRITICAL:**
- [ ] Select 10 RED flag candidates from 126 for deep review
- [ ] Begin methodology paper outline
- [ ] Set up USASpending bulk download pipeline

---

### WEEK 2: February 3-9
**Theme: Data Scale-Up Begins**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| USASpending bulk download (2020-2025) | Engineering | 50K+ contracts in DB |
| Re-run analysis on expanded DB | Engineering | Updated tier distribution |
| Deep review of top 10 RED candidates | Analyst | 5 candidates with full evidence packages |
| Methodology paper Section 1-2 draft | Founder | Bootstrap methodology written |

**Acceptance Criteria - Week 2:**
- [ ] Database contains >20,000 contracts
- [ ] Bootstrap analysis re-run on full dataset
- [ ] 5 RED candidates have complete evidence packages

---

### WEEK 3: February 10-16
**Theme: Evidence Packages**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| FEC political donation API integration | Engineering | 10K+ donation records |
| Complete 50K contract target | Engineering | 50,000 contracts in sunlight.db |
| Build prosecutor evidence package template | Analyst | Template approved by legal advisor |
| Methodology paper Section 3-4 draft | Founder | DOJ validation section written |

**Acceptance Criteria - Week 3:**
- [ ] Political donations table has >5,000 real records
- [ ] 50,000+ contracts in database
- [ ] Evidence package template finalized

---

### WEEK 4: February 17-23
**Theme: Bulletproof Case Selection**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Final selection: 3-5 bulletproof RED cases | Analyst | Cases survive 10-point checklist |
| Contract amendments API integration | Engineering | Amendments populated for RED cases |
| Academic outreach begins | Founder | 5 professors contacted |
| Methodology paper complete draft | Founder | Full 20-page draft ready |

**Bulletproof Case Checklist:**
- [ ] Bootstrap CI lower bound > 200%
- [ ] Bayesian posterior > 70%
- [ ] Survives FDR correction
- [ ] Has political donation linkage (if available)
- [ ] 3+ legal citations applicable
- [ ] Comparable contracts clearly documented
- [ ] No obvious legitimate explanation
- [ ] Vendor has no prior settlement (novel case)
- [ ] Contract value > $5M (material)
- [ ] Agency is federal (not state/local)

---

### WEEK 5: February 24 - March 2
**Theme: Academic Engagement**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Submit methodology paper to SSRN | Founder | Working paper posted |
| First professor meeting scheduled | Founder | Meeting on calendar |
| Full evidence packages for 3-5 cases | Analyst | PDF packages ready |
| Velocity analysis module | Engineering | Delivery time anomaly detection |

**Acceptance Criteria - Week 5:**
- [ ] Methodology paper on SSRN
- [ ] At least 1 professor meeting scheduled
- [ ] 3 bulletproof cases fully documented

---

### WEEK 6: March 3-9
**Theme: Multi-Signal Integration**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Amendment anomaly detection live | Engineering | Flags scope reductions |
| Velocity anomaly detection live | Engineering | Flags fast completions |
| First professor feedback received | Founder | Written feedback on methodology |
| Contractor history module | Engineering | Prior settlement lookup working |

**Acceptance Criteria - Week 6:**
- [ ] Multi-signal detection (price + amendments + velocity) operational
- [ ] At least 1 professor has reviewed methodology
- [ ] Detection rate on DOJ cases: 95%+

---

### WEEK 7: March 10-16
**Theme: Academic Validation Push**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Second professor meeting | Founder | Statistics expert engaged |
| Law professor outreach | Founder | False Claims Act expert contacted |
| Automated daily data updates | Engineering | Cron job running |
| UI prototype for case review | Engineering | Basic web interface |

**Acceptance Criteria - Week 7:**
- [ ] 2 professors have reviewed methodology
- [ ] Daily automated data refresh working
- [ ] Basic UI for case browsing

---

### WEEK 8: March 17-23
**Theme: Prosecutor Preparation**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Former prosecutor consultation | Founder | Meeting with ex-DOJ attorney |
| Evidence package review by legal | Legal | Packages pass legal review |
| Methodology paper revision | Founder | Incorporate professor feedback |
| API documentation | Engineering | External API documented |

**Acceptance Criteria - Week 8:**
- [ ] Former prosecutor has reviewed 3 cases
- [ ] Evidence packages legally vetted
- [ ] Methodology paper revised based on feedback

---

### WEEK 9: March 24-30
**Theme: Endorsement Collection**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| First endorsement letter secured | Founder | Signed letter from professor |
| Production deployment prep | Engineering | Cloud infrastructure ready |
| Press materials drafted | Marketing | Press release, fact sheet |
| Demo video recorded | Founder | 3-minute explainer |

**Acceptance Criteria - Week 9:**
- [ ] At least 1 signed endorsement letter
- [ ] Production environment ready
- [ ] Marketing materials drafted

---

### WEEK 10: March 31 - April 6
**Theme: Soft Launch Prep**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Second endorsement letter | Founder | 2 total endorsements |
| Soft launch to 10 beta users | Product | Beta access granted |
| Incorporate beta feedback | Engineering | Critical bugs fixed |
| Final methodology paper | Founder | Submit to journal |

**Acceptance Criteria - Week 10:**
- [ ] 2 endorsement letters secured
- [ ] 10 beta users actively testing
- [ ] No critical bugs in production

---

### WEEK 11: April 7-13
**Theme: Launch Week**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Third endorsement (stretch) | Founder | 3 total endorsements |
| Press outreach | Marketing | 5 journalists briefed |
| Final launch checklist | All | All items green |
| Launch announcement prep | Founder | Blog post, social media ready |

**Launch Checklist:**
- [ ] 50K+ contracts in database
- [ ] 3-5 bulletproof RED cases documented
- [ ] 2+ professor endorsements
- [ ] Methodology paper published (SSRN minimum)
- [ ] Production system stable
- [ ] Legal review complete
- [ ] Press materials ready

---

### WEEK 12: April 14-20
**Theme: LAUNCH**

**April 15, 2026: Public Launch**

| Task | Owner | Acceptance Criteria |
|------|-------|---------------------|
| Public announcement | Founder | Press release distributed |
| Website live | Engineering | Public access enabled |
| First media coverage | Marketing | At least 1 article published |
| Outreach to World Bank/IMF | BD | Intro emails sent |

---

## Resource Requirements

### Engineering (1 FTE)
- USASpending bulk download pipeline
- FEC API integration
- Amendment tracking
- Multi-signal detection modules
- Production deployment

### Data/Analysis (0.5 FTE)
- Case deep dives
- Evidence package creation
- Data quality validation

### Founder (Full time)
- Academic outreach
- Methodology paper
- Prosecutor consultations
- Endorsement collection

### External
- Legal review: $5-10K (one-time)
- Cloud infrastructure: $500/month
- Academic advisor (if paid): $2-5K

---

## Risk Mitigation

### Risk: No Professor Endorsements

**Mitigation:**
1. Start outreach NOW (this week)
2. Target 10 professors, expect 20% response rate
3. Offer co-authorship on methodology paper
4. Fallback: Practitioner endorsements (former prosecutors, IGs)

### Risk: Bulletproof Cases Don't Survive Scrutiny

**Mitigation:**
1. Start with 10 candidates, expect 50% attrition
2. Get early feedback from legal advisor
3. Have backup cases ready
4. Accept that 3 strong > 5 weak

### Risk: Data Scale-Up Delays

**Mitigation:**
1. Start bulk download this week
2. Have fallback: prioritize high-value contracts only
3. Incremental loading (don't wait for 50K)

### Risk: Competitor Launches First

**Mitigation:**
1. Focus on differentiation (statistical rigor, endorsements)
2. Launch MVP earlier if needed
3. Open-source methodology to establish priority

---

## This Week's Action Items

### MUST DO (by February 2)

1. **Select top 10 RED flag candidates** from current 126
   - Criteria: CI lower > 200%, value > $5M, has donations
   - Output: Ranked list with preliminary notes

2. **Begin methodology paper outline**
   - Sections: Intro, Data, Methods, Validation, Results, Limitations
   - Output: Google Doc with section headers and 1-2 sentences each

3. **Set up USASpending bulk download**
   - Target: 2020-2025 contracts > $100K
   - Output: Script tested, first batch downloading

4. **Identify 5 target professors**
   - Look for: Statistics (bootstrap experts), Law (FCA scholars)
   - Output: List with emails and research interests

5. **Document current system architecture**
   - Output: Architecture diagram for methodology paper

### SHOULD DO (if time permits)

- Draft press release outline
- Research FEC API documentation
- Identify former prosecutors for outreach

---

## Success Metrics

### Launch Day (April 15)

| Metric | Target | Stretch |
|--------|--------|---------|
| Contracts in DB | 50,000 | 100,000 |
| RED Cases Documented | 3 | 5 |
| Professor Endorsements | 2 | 3 |
| Detection Rate (DOJ cases) | 95% | 100% |
| False Positive Rate | <5% | <2% |
| Methodology Paper | SSRN | Journal submitted |

### Week 1 After Launch

| Metric | Target |
|--------|--------|
| Media mentions | 3 |
| Inbound inquiries | 10 |
| Beta user signups | 50 |
| World Bank/IMF contact | Meeting scheduled |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Jan 28 | Bootstrap + Bayesian as core methodology | Survives academic scrutiny, court-defensible |
| Jan 28 | 300% CI lower for RED (extreme) | Matches DOJ prosecution patterns |
| Jan 28 | Multi-signal detection for v2 | General Dynamics case shows need |
| TBD | Academic vs practitioner endorsements | Depends on professor response rate |

---

*"Eleven weeks. Three bulletproof cases. Two endorsements. One launch."*

**Next checkpoint:** February 2, 2026
**Owner:** [Founder name]
**Last updated:** January 28, 2026
