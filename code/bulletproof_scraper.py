import requests
import sqlite3
import time
from datetime import datetime

class BulletproofScraper:
    """
    SUNLIGHT BULLETPROOF SCRAPER
    Gets clean, comparable contracts for prosecutable fraud detection
    """
    
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        self.db_path = db_path
        self.session = requests.Session()
    
    def fetch_page(self, page: int, min_amount: int = 10000000, max_amount: int = 500000000) -> list:
        """Fetch clean contract data"""
        payload = {
            "filters": {
                "award_type_codes": ["A", "B", "C", "D"],
                "award_amounts": [
                    {"lower_bound": min_amount, "upper_bound": max_amount}
                ],
                "time_period": [{"start_date": "2020-01-01", "end_date": "2025-12-31"}]
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Awarding Agency",
                "Start Date",
                "End Date",
                "Description",
                "Award Type",
                "Number of Offers Received",
                "Extent Competed"
            ],
            "limit": 100,
            "page": page,
            "sort": "Award Amount",
            "order": "desc"
        }
        
        for attempt in range(3):
            try:
                response = self.session.post(self.url, json=payload, timeout=30)
                response.raise_for_status()
                return response.json().get('results', [])
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
                else:
                    print(f" Failed: {e}", end="")
        return []
    
    def save_contracts(self, contracts: list) -> int:
        """Save contracts with metadata"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""CREATE TABLE IF NOT EXISTS contracts_clean (
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
        )""")
        
        saved = 0
        for contract in contracts:
            try:
                contract_id = str(contract.get('Award ID', ''))[:200]
                award_amount = float(contract.get('Award Amount', 0))
                
                if not contract_id or award_amount <= 0:
                    continue
                
                start = contract.get('Start Date', '')
                end = contract.get('End Date', '')
                
                c.execute("""INSERT OR REPLACE INTO contracts_clean 
                            (contract_id, award_amount, vendor_name, agency_name, 
                             description, start_date, end_date, award_type, 
                             num_offers, extent_competed) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                         (contract_id,
                          award_amount,
                          str(contract.get('Recipient Name', ''))[:200],
                          str(contract.get('Awarding Agency', ''))[:200],
                          str(contract.get('Description', ''))[:500],
                          start,
                          end,
                          str(contract.get('Award Type', '')),
                          int(contract.get('Number of Offers Received', 0) or 0),
                          str(contract.get('Extent Competed', ''))))
                saved += 1
                
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        return saved
    
    def scrape(self, target: int = 10000):
        """Main scraping loop"""
        print("="*70)
        print("SUNLIGHT BULLETPROOF SCRAPER")
        print("="*70)
        print(f"Target: {target:,} clean contracts")
        print(f"Range: $10M-$500M (prosecution sweet spot)")
        print(f"Years: 2020-2025 (recent, verifiable)")
        print("="*70 + "\n")
        
        total_saved = 0
        page = 1
        start_time = time.time()
        consecutive_failures = 0
        
        while total_saved < target and page <= 100:
            print(f"Page {page}...", end=" ", flush=True)
            
            contracts = self.fetch_page(page)
            
            if not contracts:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    print(f"\n5 consecutive failures. Stopping.")
                    break
                print(f" Empty | Failures: {consecutive_failures}/5")
                page += 1
                time.sleep(5)
                continue
            
            consecutive_failures = 0
            saved = self.save_contracts(contracts)
            total_saved += saved
            
            elapsed = time.time() - start_time
            rate = total_saved / elapsed if elapsed > 0 else 0
            eta_min = (target - total_saved) / rate / 60 if rate > 0 else 0
            
            print(f"✅ {saved} | Total: {total_saved:,}/{target:,} | {rate:.1f}/s | ETA: {eta_min:.0f}min")
            
            if total_saved % 1000 == 0 and total_saved > 0:
                print(f"\nCHECKPOINT: {total_saved:,} contracts\n")
            
            page += 1
            time.sleep(1)
        
        elapsed_total = time.time() - start_time
        print(f"\n{'='*70}")
        print(f"✅ COMPLETE: {total_saved:,} clean contracts in {elapsed_total/60:.1f} min")
        print(f"{'='*70}")

if __name__ == "__main__":
    scraper = BulletproofScraper("data/sunlight.db")
    scraper.scrape(target=10000)
