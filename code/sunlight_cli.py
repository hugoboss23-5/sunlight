#!/usr/bin/env python3
"""
SUNLIGHT CLI — Procurement Integrity Scanner

Point at a country's OCDS data. Get scored, tiered, explained risk intelligence.

Usage:
    # Scan UK procurement data (live API)
    python sunlight_cli.py --country GB --limit 500

    # Scan from local file
    python sunlight_cli.py --file data/colombia_releases.json --country CO

    # Scan from directory of JSON files
    python sunlight_cli.py --dir data/paraguay/ --country PY

    # Export results
    python sunlight_cli.py --country GB --limit 1000 --csv output.csv --json output.json

    # Just show country profile
    python sunlight_cli.py --country GB --limit 500 --profile-only

    # List available sources
    python sunlight_cli.py --list-sources
"""

import argparse
import json
import logging
import sys
import os
from datetime import datetime, timezone

from ocds_field_extractor import extract_release
from cri_indicators import IndicatorResult
from batch_pipeline import BatchPipeline, JurisdictionConfig, JURISDICTION_CONFIGS
from ocds_fetcher import (
    OCDSFetcher, OCDS_SOURCES, OCDSSource,
    load_releases_from_file, load_releases_from_directory,
)


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                     ☀  SUNLIGHT  ☀                           ║
║           Procurement Integrity Infrastructure               ║
║                                                               ║
║   OCDS in → Scored risk intelligence out                     ║
║   Fazekas CRI methodology • Bayesian evidence weights        ║
╚═══════════════════════════════════════════════════════════════╝
""")


def list_sources():
    print("\nAvailable OCDS data sources:\n")
    for code, src in OCDS_SOURCES.items():
        cfg = JURISDICTION_CONFIGS.get(code)
        currency = cfg.currency if cfg else "?"
        print(f"  {code}  {src.country_name:<25} {src.base_url}")
        print(f"       {src.notes}")
        print(f"       Currency: {currency}  |  Page size: {src.page_size}")
        print()


def print_top_risks(scores, n=15):
    """Print top risk contracts in a table."""
    ranked = sorted(scores, key=lambda x: (x.cri_score or 0, x.combined_lr), reverse=True)
    top = ranked[:n]

    print(f"\n{'═' * 100}")
    print(f"  TOP {n} HIGHEST-RISK CONTRACTS")
    print(f"{'═' * 100}")
    print(f"  {'TIER':<6} {'CRI':>5} {'LR':>7} {'FLAGS':>5} {'VALUE':>12} {'METHOD':<10} {'BUYER':<20} {'OCID'}")
    print(f"  {'─' * 94}")

    for s in top:
        cri_str = f"{s.cri_score:.2f}" if s.cri_score is not None else "  — "
        lr_str = f"{s.combined_lr:.1f}"
        value_str = f"{s.award_value:>10,.0f}" if s.award_value else "         —"
        method = (s.procurement_method or "—")[:10]
        buyer = (s.buyer_name or s.buyer_id or "—")[:20]

        # Color tier
        tier = s.cri_tier
        if tier == "RED":
            tier_display = f"\033[91m{tier:<6}\033[0m"
        elif tier == "YELLOW":
            tier_display = f"\033[93m{tier:<6}\033[0m"
        elif tier == "GREEN":
            tier_display = f"\033[92m{tier:<6}\033[0m"
        else:
            tier_display = f"\033[90m{tier:<6}\033[0m"

        print(f"  {tier_display} {cri_str:>5} {lr_str:>7} {s.n_indicators_flagged:>3}/{s.n_indicators_available:<1} {value_str} {method:<10} {buyer:<20} {s.ocid}")

        # Print explanations for RED contracts
        if tier == "RED" and s.explanations:
            for exp in s.explanations[:3]:
                print(f"         ↳ {exp}")

    print()


def print_indicator_breakdown(scores):
    """Print indicator-level statistics."""
    print(f"\n{'═' * 70}")
    print(f"  INDICATOR BREAKDOWN")
    print(f"{'═' * 70}")

    indicators = [
        ("single_bidding_flag", "Single Bidding"),
        ("tender_period_flag", "Short Tender Period"),
        ("procedure_type_flag", "Non-Competitive Procedure"),
        ("decision_period_flag", "Abnormal Decision Period"),
        ("amendment_flag", "Suspicious Amendments"),
        ("buyer_concentration_flag", "Buyer Concentration"),
    ]

    print(f"  {'Indicator':<30} {'Flagged':>8} {'Clean':>8} {'No Data':>8} {'Flag Rate':>10}")
    print(f"  {'─' * 66}")

    for attr, label in indicators:
        flagged = sum(1 for s in scores if getattr(s, attr) == 1)
        clean = sum(1 for s in scores if getattr(s, attr) == 0)
        gray = sum(1 for s in scores if getattr(s, attr) is None)
        rate = flagged / (flagged + clean) if (flagged + clean) > 0 else 0
        print(f"  {label:<30} {flagged:>8} {clean:>8} {gray:>8} {rate:>9.1%}")

    print()


def print_buyer_risk_table(profile, n=10):
    """Print top risk buyers."""
    if not profile.top_risk_buyers:
        return

    print(f"\n{'═' * 70}")
    print(f"  TOP RISK BUYERS (by average CRI)")
    print(f"{'═' * 70}")
    print(f"  {'Buyer ID':<30} {'Avg CRI':>8} {'Contracts':>10}")
    print(f"  {'─' * 50}")

    for buyer in profile.top_risk_buyers[:n]:
        print(f"  {buyer['buyer_id']:<30} {buyer['avg_cri']:>8.3f} {buyer['n_contracts']:>10}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="SUNLIGHT — Procurement Integrity Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --country GB --limit 500
  %(prog)s --file releases.json --country CO
  %(prog)s --country GB --limit 1000 --csv results.csv
  %(prog)s --list-sources
        """,
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--country", "-c", help="Country code to fetch from live API")
    input_group.add_argument("--file", "-f", help="Local JSON file with OCDS releases")
    input_group.add_argument("--dir", "-d", help="Directory of JSON files")
    input_group.add_argument("--list-sources", action="store_true", help="List available OCDS sources")

    # Fetch options
    parser.add_argument("--limit", "-n", type=int, default=500, help="Max releases to fetch (default: 500)")

    # Output options
    parser.add_argument("--csv", help="Export results to CSV")
    parser.add_argument("--json", help="Export results to JSON")
    parser.add_argument("--profile-only", action="store_true", help="Only show country profile")
    parser.add_argument("--top", type=int, default=15, help="Number of top risks to show (default: 15)")

    # Config
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.list_sources:
        list_sources()
        return

    if not (args.country or args.file or args.dir):
        parser.print_help()
        print("\nError: Specify --country, --file, or --dir")
        sys.exit(1)

    print_banner()

    # Determine jurisdiction config
    country = args.country
    if args.file or args.dir:
        if not country:
            print("Warning: No --country specified for local file. Using defaults.")
            country = "XX"

    config = JURISDICTION_CONFIGS.get(country, JurisdictionConfig(
        country_code=country or "XX",
        country_name=country or "Unknown",
    ))

    # Load data
    print(f"Loading OCDS data for {config.country_name} ({config.country_code})...")

    if args.file:
        releases = load_releases_from_file(args.file)
        print(f"Loaded {len(releases)} releases from {args.file}")
    elif args.dir:
        releases = load_releases_from_directory(args.dir)
        print(f"Loaded {len(releases)} releases from {args.dir}")
    else:
        fetcher = OCDSFetcher(country)
        print(f"Fetching from: {fetcher.source.base_url}")
        releases = fetcher.fetch(limit=args.limit)
        print(f"Fetched {len(releases)} releases")

    if not releases:
        print("No releases found. Nothing to analyze.")
        sys.exit(0)

    # Run pipeline
    print(f"\nRunning SUNLIGHT analysis pipeline...")
    pipeline = BatchPipeline(config)
    pipeline.analyze(releases)
    print(f"✓ Scored {len(pipeline.scores)} contracts\n")

    # Output
    if pipeline.profile:
        print(pipeline.profile.summary())

    if not args.profile_only:
        print_indicator_breakdown(pipeline.scores)
        print_buyer_risk_table(pipeline.profile, n=args.top)
        print_top_risks(pipeline.scores, n=args.top)

    # Export
    if args.csv:
        pipeline.export_csv(args.csv)
        print(f"✓ CSV exported to {args.csv}")

    if args.json:
        pipeline.export_json(args.json)
        print(f"✓ JSON exported to {args.json}")

    # Summary line
    if pipeline.profile:
        p = pipeline.profile
        print(f"\n{'═' * 70}")
        print(f"  SUNLIGHT SCAN COMPLETE")
        print(f"  {p.total_contracts} contracts | {p.red_count} RED | {p.yellow_count} YELLOW | {p.green_count} GREEN | {p.gray_count} GRAY")
        if p.mean_cri is not None:
            print(f"  Mean CRI: {p.mean_cri:.3f} | Median CRI: {p.median_cri:.3f}")
        print(f"{'═' * 70}")


if __name__ == "__main__":
    main()
