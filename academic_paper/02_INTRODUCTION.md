# 2. INTRODUCTION

## 2.1 The Scale of Procurement Fraud

Government procurement fraud represents one of the most significant drains on public resources worldwide. In the United States alone, federal procurement spending exceeds $600 billion annually (USAspending.gov, 2024). Studies estimate that 10-25% of procurement budgets are lost to fraud, waste, and abuse, suggesting losses of $60-150 billion per year in the U.S. federal system alone.

The problem extends far beyond financial loss. Every dollar stolen through procurement fraud is a dollar not spent on education, healthcare, infrastructure, or public services.

## 2.2 Why Existing Methods Fail

Traditional government auditing faces several fundamental limitations:

**Volume Problem:** Federal agencies process over 7 million contract actions annually. The Government Accountability Office can audit only 2-3% of contracts, creating a 97% "dark zone."

**Single-Source Limitation:** Most audits rely on data from the awarding agency itself. If fraud is systemic or involves collusion, internal data will not reveal it.

**Reactive Approach:** Traditional audits respond to whistleblower complaints rather than proactively identifying suspicious patterns.

**Manual Process:** Human auditors review contracts one at a time, making comprehensive analysis impossible at scale.

## 2.3 Our Contribution

This paper presents SUNLIGHT, a multi-source fraud detection system designed to address these limitations while maintaining transparency and legal rigor.

**Key contributions:**
- Multi-source integration (USAspending, OpenSecrets, FPDS)
- Statistical rigor (size-adjusted baselines, confidence intervals)
- Legal alignment (DOJ prosecution thresholds)
- Full transparency (open source, verifiable)
- Conservative classification (admits uncertainty)

## 2.4 Research Questions

**RQ1:** Can statistical analysis of public procurement data identify fraud indicators consistent with DOJ prosecution patterns?

**RQ2:** Does multi-source integration improve detection accuracy compared to single-source approaches?

**RQ3:** Can a transparent, rules-based system achieve sufficient rigor for actual investigations?

## 2.5 Ethical Considerations

We prioritize:
- Presumption of innocence (flag patterns, not guilt)
- Full transparency (show all work)
- Conservative thresholds (avoid false accusations)
- No individual targeting (focus on contracts)

## 2.6 Paper Organization

Section 3 reviews related work. Section 4 details methodology. Section 5 describes implementation. Section 6 presents results. Section 7 discusses implications and limitations. Section 8 concludes.
