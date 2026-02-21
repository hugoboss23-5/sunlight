#!/usr/bin/env python3
"""
SUNLIGHT DOJ Cases Expansion Tool
====================================

Manage and expand the prosecuted_cases.json dataset used for
calibrating SUNLIGHT's fraud detection thresholds.

Commands:
    --stats              Show summary statistics of the current dataset
    --search <term>      Search cases by vendor, agency, or fraud type
    --add                Interactive prompt to add a new DOJ case
    --validate           Validate all cases have required fields and consistent data

Usage:
    python scripts/expand_doj_cases.py --stats
    python scripts/expand_doj_cases.py --search "Oracle"
    python scripts/expand_doj_cases.py --add
    python scripts/expand_doj_cases.py --validate
"""

import argparse
import json
import os
import sys
from datetime import datetime


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CASES_PATH = os.path.join(REPO_ROOT, 'prosecuted_cases.json')

REQUIRED_FIELDS = [
    'case_id', 'vendor', 'contract_amount', 'agency',
    'fraud_type', 'markup_pct', 'outcome', 'year',
]

OPTIONAL_FIELDS = [
    'settlement', 'key_evidence', 'contract_type',
    'description', 'legal_basis', 'source',
]

VALID_OUTCOMES = ['PROSECUTED', 'SETTLED', 'CONVICTED', 'PENDING', 'PLEA_DEAL']
VALID_FRAUD_TYPES = [
    'Price Inflation', 'Bid Rigging', 'Kickbacks', 'False Claims',
    'Defective Pricing', 'Product Substitution', 'Cost Mischarging',
    'Bribery', 'Wire Fraud', 'Conspiracy',
]


def load_cases(path):
    """Load prosecuted cases from JSON file."""
    if not os.path.exists(path):
        print(f'ERROR: Cases file not found: {path}')
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    return data


def save_cases(path, data):
    """Save prosecuted cases to JSON file."""
    data['total_cases'] = len(data['cases'])
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'Saved {data["total_cases"]} cases to {path}')


def cmd_stats(data):
    """Show summary statistics."""
    cases = data['cases']
    n = len(cases)

    print()
    print('=' * 60)
    print('  DOJ Prosecuted Cases — Statistics')
    print('=' * 60)
    print()
    print(f'  Total cases:     {n}')
    print(f'  Dataset created: {data.get("created", "unknown")}')
    print(f'  Source:           {data.get("source", "unknown")}')
    print()

    # By fraud type
    fraud_types = {}
    for c in cases:
        ft = c.get('fraud_type', 'Unknown')
        fraud_types[ft] = fraud_types.get(ft, 0) + 1
    print('  By Fraud Type:')
    for ft, count in sorted(fraud_types.items(), key=lambda x: -x[1]):
        print(f'    {ft:<30s} {count}')

    # By agency
    agencies = {}
    for c in cases:
        ag = c.get('agency', 'Unknown')
        agencies[ag] = agencies.get(ag, 0) + 1
    print()
    print('  By Agency:')
    for ag, count in sorted(agencies.items(), key=lambda x: -x[1]):
        print(f'    {ag:<40s} {count}')

    # By outcome
    outcomes = {}
    for c in cases:
        oc = c.get('outcome', 'Unknown')
        outcomes[oc] = outcomes.get(oc, 0) + 1
    print()
    print('  By Outcome:')
    for oc, count in sorted(outcomes.items(), key=lambda x: -x[1]):
        print(f'    {oc:<20s} {count}')

    # Markup stats
    markups = [c['markup_pct'] for c in cases if c.get('markup_pct')]
    if markups:
        print()
        print('  Markup Statistics:')
        print(f'    Min:    {min(markups):.0f}%')
        print(f'    Max:    {max(markups):.0f}%')
        print(f'    Mean:   {sum(markups)/len(markups):.0f}%')
        print(f'    Median: {sorted(markups)[len(markups)//2]:.0f}%')

    # Contract amount stats
    amounts = [c['contract_amount'] for c in cases if c.get('contract_amount')]
    if amounts:
        print()
        print('  Contract Amount Statistics:')
        print(f'    Min:    ${min(amounts):>14,.0f}')
        print(f'    Max:    ${max(amounts):>14,.0f}')
        print(f'    Total:  ${sum(amounts):>14,.0f}')

    # Year range
    years = [c['year'] for c in cases if c.get('year')]
    if years:
        print()
        print(f'  Year range: {min(years)} - {max(years)}')

    print()
    print('=' * 60)


def cmd_search(data, term):
    """Search cases by vendor, agency, fraud type, or description."""
    cases = data['cases']
    term_lower = term.lower()
    matches = []

    for c in cases:
        searchable = ' '.join([
            str(c.get('vendor', '')),
            str(c.get('agency', '')),
            str(c.get('fraud_type', '')),
            str(c.get('description', '')),
            str(c.get('case_id', '')),
        ]).lower()
        if term_lower in searchable:
            matches.append(c)

    print()
    print(f'  Search: "{term}" — {len(matches)} match(es)')
    print()

    if not matches:
        print('  No matches found.')
        return

    for c in matches:
        print(f'  {c["case_id"]}')
        print(f'    Vendor:   {c.get("vendor", "?")}')
        print(f'    Agency:   {c.get("agency", "?")}')
        print(f'    Amount:   ${c.get("contract_amount", 0):,.0f}')
        print(f'    Markup:   {c.get("markup_pct", 0):.0f}%')
        print(f'    Type:     {c.get("fraud_type", "?")}')
        print(f'    Outcome:  {c.get("outcome", "?")}')
        print(f'    Year:     {c.get("year", "?")}')
        if c.get('description'):
            desc = c['description'][:120]
            print(f'    Desc:     {desc}...' if len(c['description']) > 120 else f'    Desc:     {desc}')
        print()


def cmd_add(data, cases_path):
    """Interactively add a new DOJ case."""
    print()
    print('=' * 60)
    print('  Add New DOJ Prosecuted Case')
    print('=' * 60)
    print()

    case = {}

    # Required fields
    case['case_id'] = input('  Case ID (e.g. US_v_VendorName_2024): ').strip()
    if not case['case_id']:
        print('  Aborted: case_id is required.')
        return

    # Check for duplicate
    existing_ids = {c['case_id'] for c in data['cases']}
    if case['case_id'] in existing_ids:
        print(f'  ERROR: Case ID "{case["case_id"]}" already exists.')
        return

    case['vendor'] = input('  Vendor name: ').strip()
    amount_str = input('  Contract amount (USD, no commas): ').strip()
    try:
        case['contract_amount'] = float(amount_str)
    except ValueError:
        print(f'  ERROR: Invalid amount "{amount_str}"')
        return

    case['agency'] = input('  Agency: ').strip()

    print(f'  Fraud types: {", ".join(VALID_FRAUD_TYPES)}')
    case['fraud_type'] = input('  Fraud type: ').strip()

    markup_str = input('  Markup percentage (e.g. 150 for 150%): ').strip()
    try:
        case['markup_pct'] = float(markup_str)
    except ValueError:
        print(f'  ERROR: Invalid markup "{markup_str}"')
        return

    print(f'  Outcomes: {", ".join(VALID_OUTCOMES)}')
    case['outcome'] = input('  Outcome: ').strip()

    year_str = input('  Year: ').strip()
    try:
        case['year'] = int(year_str)
    except ValueError:
        print(f'  ERROR: Invalid year "{year_str}"')
        return

    # Optional fields
    settlement_str = input('  Settlement amount (USD, blank to skip): ').strip()
    if settlement_str:
        try:
            case['settlement'] = float(settlement_str)
        except ValueError:
            pass

    evidence = input('  Key evidence (comma-separated, blank to skip): ').strip()
    if evidence:
        case['key_evidence'] = [e.strip() for e in evidence.split(',')]

    case['contract_type'] = input('  Contract type (blank to skip): ').strip() or None
    case['description'] = input('  Description (blank to skip): ').strip() or None
    case['legal_basis'] = input('  Legal basis (blank to skip): ').strip() or None
    case['source'] = input('  Source/URL (blank to skip): ').strip() or None

    # Remove None values
    case = {k: v for k, v in case.items() if v is not None}

    # Confirm
    print()
    print('  New case:')
    print(json.dumps(case, indent=4))
    confirm = input('\n  Add this case? (y/N): ').strip()
    if confirm.lower() != 'y':
        print('  Aborted.')
        return

    data['cases'].append(case)
    save_cases(cases_path, data)
    print(f'  Added case "{case["case_id"]}" — total now {len(data["cases"])}')


def cmd_validate(data):
    """Validate all cases for completeness and consistency."""
    cases = data['cases']
    errors = []
    warnings = []

    print()
    print('=' * 60)
    print('  DOJ Cases Validation')
    print('=' * 60)
    print()

    case_ids = set()
    for i, c in enumerate(cases):
        prefix = f'  Case {i+1}'

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in c or c[field] is None or c[field] == '':
                errors.append(f'{prefix}: Missing required field "{field}"')

        # Check for duplicate case_id
        cid = c.get('case_id', f'UNNAMED_{i}')
        if cid in case_ids:
            errors.append(f'{prefix}: Duplicate case_id "{cid}"')
        case_ids.add(cid)

        # Validate amounts
        if c.get('contract_amount', 0) <= 0:
            errors.append(f'{prefix} ({cid}): Invalid contract_amount <= 0')

        if c.get('markup_pct', 0) <= 0:
            warnings.append(f'{prefix} ({cid}): markup_pct <= 0')

        # Validate year range
        year = c.get('year', 0)
        if year < 1990 or year > datetime.now().year + 1:
            warnings.append(f'{prefix} ({cid}): Unusual year {year}')

        # Check outcome
        outcome = c.get('outcome', '')
        if outcome and outcome not in VALID_OUTCOMES:
            warnings.append(f'{prefix} ({cid}): Non-standard outcome "{outcome}"')

        # Check fraud type
        fraud_type = c.get('fraud_type', '')
        if fraud_type and fraud_type not in VALID_FRAUD_TYPES:
            warnings.append(f'{prefix} ({cid}): Non-standard fraud_type "{fraud_type}"')

    # Report
    if errors:
        print(f'  ERRORS ({len(errors)}):')
        for e in errors:
            print(f'    {e}')
        print()

    if warnings:
        print(f'  WARNINGS ({len(warnings)}):')
        for w in warnings:
            print(f'    {w}')
        print()

    if not errors and not warnings:
        print('  All cases valid. No errors or warnings.')

    print()
    print(f'  Summary: {len(cases)} cases, {len(errors)} errors, {len(warnings)} warnings')

    if errors:
        print('  VALIDATION: FAIL')
        return False
    else:
        print('  VALIDATION: PASS')
        return True


def main():
    parser = argparse.ArgumentParser(description='SUNLIGHT DOJ Cases Expansion Tool')
    parser.add_argument('--cases', default=DEFAULT_CASES_PATH,
                        help='Path to prosecuted_cases.json')
    parser.add_argument('--stats', action='store_true', help='Show dataset statistics')
    parser.add_argument('--search', type=str, default=None,
                        help='Search cases by term')
    parser.add_argument('--add', action='store_true',
                        help='Interactively add a new case')
    parser.add_argument('--validate', action='store_true',
                        help='Validate all cases')

    args = parser.parse_args()

    if not any([args.stats, args.search, args.add, args.validate]):
        parser.print_help()
        sys.exit(0)

    data = load_cases(args.cases)

    if args.stats:
        cmd_stats(data)

    if args.search:
        cmd_search(data, args.search)

    if args.validate:
        ok = cmd_validate(data)
        if not ok:
            sys.exit(1)

    if args.add:
        cmd_add(data, args.cases)


if __name__ == '__main__':
    main()
