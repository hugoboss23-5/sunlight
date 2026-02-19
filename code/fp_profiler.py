"""
SUNLIGHT False Positive Profiler
=================================

One-time diagnostic: profiles the false positives from evaluation to identify
which signals drive false flags. Helps tune assign_tier() thresholds.

Usage:
    python fp_profiler.py --db data/sunlight.db --cases prosecuted_cases.json
"""

import json
import os
import sys
import sqlite3
import numpy as np
from collections import Counter
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))

from institutional_statistical_rigor import BootstrapAnalyzer
from institutional_pipeline import (
    score_contract, assign_tier, derive_contract_seed,
)
from doj_validation import (
    load_doj_cases, build_agency_cache, map_doj_agency,
    synthesize_doj_contract, get_clean_contracts,
)


def profile_false_positives(db_path: str, cases_path: str,
                            run_seed: int = 42, n_bootstrap: int = 1000,
                            n_clean: int = 200) -> Dict:
    """Score clean contracts and profile those incorrectly flagged."""
    agency_cache = build_agency_cache(db_path)
    config = {'confidence_level': 0.95, 'min_comparables': 3}
    ba = BootstrapAnalyzer(n_iterations=n_bootstrap)

    np.random.seed(run_seed)
    clean_contracts = get_clean_contracts(db_path, agency_cache, n=n_clean)

    fps = []
    tns = []
    for contract in clean_contracts:
        seed = derive_contract_seed(run_seed, contract['contract_id'])
        score = score_contract(contract, seed, config, ba)
        tier, priority = assign_tier(score, score.get('raw_pvalue', 1.0), False)

        entry = {
            'contract_id': contract['contract_id'],
            'agency': contract.get('agency_name', ''),
            'amount': contract['award_amount'],
            'tier': tier,
            'markup_ci_lower': score.get('markup_ci_lower', 0) or 0,
            'markup_ci_upper': score.get('markup_ci_upper', 0) or 0,
            'bayesian_posterior': score.get('bayesian_posterior', 0) or 0,
            'percentile_ci_lower': score.get('percentile_ci_lower', 0) or 0,
            'markup_pct': score.get('markup_pct', 0) or 0,
            'comparable_count': score.get('comparable_count', 0),
        }

        # Reconstruct which signals fired
        ci = entry['markup_ci_lower']
        post = entry['bayesian_posterior']
        pci = entry['percentile_ci_lower']
        signals = []
        if ci > 300: signals.append('ci>300')
        elif ci > 200: signals.append('ci>200')
        elif ci > 150: signals.append('ci>150')
        elif ci > 75: signals.append('ci>75')
        if pci > 95: signals.append('pci>95')
        elif pci > 90: signals.append('pci>90')
        elif pci > 75: signals.append('pci>75')
        if post > 0.80: signals.append('post>0.80')
        elif post > 0.50: signals.append('post>0.50')
        elif post > 0.20: signals.append('post>0.20')
        entry['signals'] = signals

        if tier in ('RED', 'YELLOW'):
            fps.append(entry)
        else:
            tns.append(entry)

    # --- Analysis ---
    print(f"\n{'='*70}")
    print(f"FALSE POSITIVE PROFILER")
    print(f"{'='*70}")
    print(f"Clean contracts scored: {len(clean_contracts)}")
    print(f"False positives (RED/YELLOW): {len(fps)}")
    print(f"True negatives (GREEN/GRAY):  {len(tns)}")
    print(f"FP rate: {len(fps)/len(clean_contracts)*100:.1f}%")

    # Signal frequency among FPs
    print(f"\n--- Signal frequency among FPs ---")
    signal_counts = Counter()
    for fp in fps:
        for s in fp['signals']:
            signal_counts[s] += 1
    for signal, count in signal_counts.most_common():
        print(f"  {signal:12s}: {count:3d} ({count/len(fps)*100:.0f}%)")

    # Agency breakdown
    print(f"\n--- FPs by agency ---")
    agency_counts = Counter(fp['agency'] for fp in fps)
    for agency, count in agency_counts.most_common(10):
        print(f"  {agency:40s}: {count:3d}")

    # Value range breakdown
    print(f"\n--- FPs by contract value ---")
    ranges = [
        ('< $1M', 0, 1e6),
        ('$1M - $5M', 1e6, 5e6),
        ('$5M - $25M', 5e6, 25e6),
        ('$25M - $100M', 25e6, 100e6),
        ('> $100M', 100e6, float('inf')),
    ]
    for label, lo, hi in ranges:
        count = sum(1 for fp in fps if lo <= fp['amount'] < hi)
        if count > 0:
            print(f"  {label:15s}: {count:3d}")

    # Markup CI analysis
    print(f"\n--- Markup CI lower among FPs ---")
    ci_vals = [fp['markup_ci_lower'] for fp in fps]
    if ci_vals:
        print(f"  Min:    {min(ci_vals):.1f}%")
        print(f"  Median: {np.median(ci_vals):.1f}%")
        print(f"  Max:    {max(ci_vals):.1f}%")
        print(f"  ci <= 0: {sum(1 for v in ci_vals if v <= 0)} contracts")
        print(f"  ci <= 10: {sum(1 for v in ci_vals if v <= 10)} contracts")
        print(f"  ci <= 25: {sum(1 for v in ci_vals if v <= 25)} contracts")

    # Posterior analysis
    print(f"\n--- Bayesian posterior among FPs ---")
    post_vals = [fp['bayesian_posterior'] for fp in fps]
    if post_vals:
        print(f"  Min:    {min(post_vals):.4f}")
        print(f"  Median: {np.median(post_vals):.4f}")
        print(f"  Max:    {max(post_vals):.4f}")
        print(f"  Only post>0.20 (no other signal): "
              f"{sum(1 for fp in fps if fp['signals'] == ['post>0.20'])}")

    # Percentile CI analysis
    print(f"\n--- Percentile CI lower among FPs ---")
    pci_vals = [fp['percentile_ci_lower'] for fp in fps]
    if pci_vals:
        print(f"  Min:    {min(pci_vals):.1f}")
        print(f"  Median: {np.median(pci_vals):.1f}")
        print(f"  Max:    {max(pci_vals):.1f}")
        print(f"  75 < pci <= 85: {sum(1 for v in pci_vals if 75 < v <= 85)}")
        print(f"  pci > 85: {sum(1 for v in pci_vals if v > 85)}")

    # Impact simulation: what if we removed post>0.20?
    print(f"\n--- Impact simulation ---")
    fp_without_post20 = []
    for fp in fps:
        remaining = [s for s in fp['signals'] if s != 'post>0.20']
        if remaining:  # Still has other signals
            fp_without_post20.append(fp)
    print(f"  Remove post>0.20: {len(fps)} -> {len(fp_without_post20)} FPs "
          f"(-{len(fps)-len(fp_without_post20)})")

    # What if we also raised pci threshold to 85?
    fp_without_post20_pci85 = []
    for fp in fps:
        remaining = [s for s in fp['signals']
                     if s != 'post>0.20' and s != 'pci>75']
        if remaining:
            fp_without_post20_pci85.append(fp)
    print(f"  + Raise pci>75 to pci>85: -> {len(fp_without_post20_pci85)} FPs "
          f"(-{len(fps)-len(fp_without_post20_pci85)})")

    # What if we also add ci>0 gate for YELLOW?
    fp_with_ci_gate = []
    for fp in fp_without_post20_pci85:
        if fp['markup_ci_lower'] > 0:
            fp_with_ci_gate.append(fp)
    print(f"  + Add ci>0 gate for YELLOW: -> {len(fp_with_ci_gate)} FPs "
          f"(-{len(fps)-len(fp_with_ci_gate)})")

    print(f"{'='*70}\n")

    return {
        'n_clean': len(clean_contracts),
        'n_fp': len(fps),
        'n_tn': len(tns),
        'signal_counts': dict(signal_counts),
        'fps': fps,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SUNLIGHT FP Profiler")
    parser.add_argument('--db', default='data/sunlight.db')
    parser.add_argument('--cases', default='prosecuted_cases.json')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--bootstrap', type=int, default=1000)
    parser.add_argument('--clean', type=int, default=200)
    args = parser.parse_args()

    db = args.db
    if not os.path.exists(db):
        db = '../data/sunlight.db'
    cases = args.cases
    if not os.path.exists(cases):
        cases = '../prosecuted_cases.json'

    profile_false_positives(db, cases, run_seed=args.seed,
                            n_bootstrap=args.bootstrap, n_clean=args.clean)
