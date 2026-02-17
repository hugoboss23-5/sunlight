#!/usr/bin/env python3
"""
SUNLIGHT - USAspending.gov Data Loader
Loads contracts >$1M into sunlight.db
"""

import csv
import sqlite3
import glob
import os
from datetime import datetime

# Configuration
RAW_DIR = os.path.expanduser("~/brain/SUNLIGHT/data/raw")
DB_PATH = os.path.expanduser("~/brain/SUNLIGHT/data/sunlight.db")
MIN_AMOUNT = 1_000_000  # $1M minimum

# Column mapping from USAspending to our schema
COLUMNS = {
    'contract_id': 'contract_award_unique_key',
    'award_amount': 'current_total_value_of_award',
    'vendor_name': 'recipient_name',
    'agency_name': 'awarding_agency_name',
    'description': 'transaction_description',
    'start_date': 'period_of_performance_start_date',
    'end_date': 'period_of_performance_current_end_date',
    'award_type': 'award_type_code',
    'num_offers': 'number_of_offers_received',
    'extent_competed': 'extent_competed'
}

def create_table(conn):
    """Create contracts_clean table if not exists"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contracts_clean (
            contract_id TEXT PRIMARY KEY,
            award_amount REAL,
            vendor_name TEXT,
            agency_name TEXT,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            award_type TEXT,
            num_offers INTEGER,
            extent_competed TEXT
        )
    """)
    conn.commit()

def safe_float(val):
    """Safely convert to float"""
    try:
        if val is None or val == '':
            return 0.0
        return float(val)
    except:
        return 0.0

def safe_int(val):
    """Safely convert to int"""
    try:
        if val is None or val == '':
            return 0
        return int(float(val))
    except:
        return 0

def process_file(filepath, conn, seen_ids):
    """Process a single CSV file"""
    filename = os.path.basename(filepath)
    inserted = 0
    skipped_amount = 0
    skipped_dup = 0
    
    print(f"Processing: {filename}")
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        
        batch = []
        for row in reader:
            try:
                # Get award amount
                amount = safe_float(row.get('current_total_value_of_award', 0))
                
                # Skip if below threshold
                if amount < MIN_AMOUNT:
                    skipped_amount += 1
                    continue
                
                # Get contract ID
                contract_id = row.get('contract_award_unique_key', '')
                if not contract_id or contract_id in seen_ids:
                    skipped_dup += 1
                    continue
                
                seen_ids.add(contract_id)
                
                # Extract fields
                record = (
                    contract_id,
                    amount,
                    row.get('recipient_name', '')[:200],  # Truncate long names
                    row.get('awarding_agency_name', '')[:200],
                    row.get('transaction_description', '')[:500],
                    row.get('period_of_performance_start_date', ''),
                    row.get('period_of_performance_current_end_date', ''),
                    row.get('award_type_code', ''),
                    safe_int(row.get('number_of_offers_received', 0)),
                    row.get('extent_competed', '')
                )
                
                batch.append(record)
                
                # Insert in batches of 1000
                if len(batch) >= 1000:
                    conn.executemany("""
                        INSERT OR IGNORE INTO contracts_clean 
                        (contract_id, award_amount, vendor_name, agency_name, 
                         description, start_date, end_date, award_type, 
                         num_offers, extent_competed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    inserted += len(batch)
                    batch = []
                    
            except Exception as e:
                continue
        
        # Insert remaining
        if batch:
            conn.executemany("""
                INSERT OR IGNORE INTO contracts_clean 
                (contract_id, award_amount, vendor_name, agency_name, 
                 description, start_date, end_date, award_type, 
                 num_offers, extent_competed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            inserted += len(batch)
        
        conn.commit()
    
    print(f"  → Inserted: {inserted:,} | Skipped (<$1M): {skipped_amount:,} | Duplicates: {skipped_dup:,}")
    return inserted

def main():
    print("=" * 60)
    print("SUNLIGHT - USAspending.gov Data Loader")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Minimum amount: ${MIN_AMOUNT:,}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    create_table(conn)
    
    # Get existing IDs to avoid duplicates
    print("Loading existing contract IDs...")
    existing = conn.execute("SELECT contract_id FROM contracts_clean").fetchall()
    seen_ids = set(row[0] for row in existing)
    print(f"Found {len(seen_ids):,} existing contracts")
    print()
    
    # Find all CSV files
    csv_files = sorted(glob.glob(os.path.join(RAW_DIR, "FY202*.csv")))
    print(f"Found {len(csv_files)} CSV files to process")
    print()
    
    # Process each file
    total_inserted = 0
    for filepath in csv_files:
        inserted = process_file(filepath, conn, seen_ids)
        total_inserted += inserted
    
    # Final count
    count = conn.execute("SELECT COUNT(*) FROM contracts_clean").fetchone()[0]
    
    print()
    print("=" * 60)
    print("LOAD COMPLETE")
    print("=" * 60)
    print(f"New contracts added: {total_inserted:,}")
    print(f"Total contracts in database: {count:,}")
    print()
    
    # Show sample
    print("Sample of loaded contracts:")
    print("-" * 60)
    for row in conn.execute("""
        SELECT vendor_name, agency_name, award_amount 
        FROM contracts_clean 
        ORDER BY award_amount DESC 
        LIMIT 5
    """):
        print(f"  ${row[2]/1e6:.1f}M | {row[0][:30]} | {row[1][:30]}")
    
    conn.close()

if __name__ == "__main__":
    main()
