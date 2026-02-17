#!/usr/bin/env python3
"""
SUNLIGHT False Positive Rate Analysis
"""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "brain" / "SUNLIGHT" / "data" / "sunlight.db"

def connect_db():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH)

def get_high_competition_contracts(conn, limit=100):
    """Get contracts with high competition (>=5 bids)"""
    query = """
    SELECT contract_id, award_amount, vendor_name, agency_name
    FROM contracts_clean
    WHERE num_offers >= 5
      AND extent_competed = 'FULL AND OPEN COMPETITION'
      AND award_amount > 0
    ORDER BY RANDOM()
    LIMIT ?
    """
    cursor = conn.cursor()
    cursor.execute(query, (limit,))
    return cursor.fetchall()

def main():
    print("SUNLIGHT False Positive Rate Analysis")
    print("=" * 80)
    
    print(f"\nConnecting to database: {DB_PATH}")
    conn = connect_db()
    if not conn:
        return
    print("✓ Connected successfully")
    
    print("\nRetrieving high-competition contracts (likely legitimate)...")
    contracts = get_high_competition_contracts(conn, limit=100)
    print(f"✓ Found {len(contracts)} contracts with 5+ competitive bids")
    
    print("\nSample contracts:")
    for i, contract in enumerate(contracts[:5], 1):
        print(f"  {i}. {contract[2]} - ${contract[1]:,.2f} ({contract[3]})")
    
    print("\n" + "=" * 80)
    print("SUCCESS: Script can access your database and find legitimate contracts")
    print("Next: Integrate with bulletproof_analyzer.py to test these contracts")
    print("=" * 80)
    
    conn.close()

if __name__ == "__main__":
    main()
