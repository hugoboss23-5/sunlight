import requests
import sqlite3
import time

class ProductionScraper:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        self.db_path = db_path
    
    def fetch_page(self, page: int, retries: int = 3) -> list:
        payload = {
            "filters": {
                "award_type_codes": ["A", "B", "C", "D"],
                "award_amounts": [{"lower_bound": 10000000}],
                "time_period": [{"start_date": "2020-01-01", "end_date": "2025-12-31"}]
            },
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description"],
            "limit": 100,
            "page": page,
            "sort": "Award Amount",
            "order": "desc"
        }
        
        for attempt in range(retries):
            try:
                response = requests.post(self.url, json=payload, timeout=30)
                response.raise_for_status()
                return response.json().get('results', [])
            except Exception as e:
                if attempt < retries - 1:
                    print(f" Retry {attempt+1}...", end="", flush=True)
                    time.sleep(5)
                else:
                    print(f" Failed after {retries} attempts", end="")
        return []
    
    def save_contracts(self, contracts: list) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(contracts)")
        columns = {col[1] for col in c.fetchall()}
        date_column = 'award_date' if 'award_date' in columns else 'start_date'
        
        saved = 0
        for contract in contracts:
            try:
                contract_id = str(contract.get('Award ID', ''))[:200]
                award_amount = float(contract.get('Award Amount', 0))
                
                if not contract_id or award_amount <= 0:
                    continue
                
                query = f'''INSERT OR REPLACE INTO contracts 
                            (contract_id, award_amount, vendor_name, agency_name, description, {date_column}) 
                            VALUES (?,?,?,?,?,?)'''
                
                c.execute(query,
                         (contract_id,
                          award_amount,
                          str(contract.get('Recipient Name', ''))[:200],
                          str(contract.get('Awarding Agency', ''))[:200],
                          str(contract.get('Description', ''))[:500],
                          str(contract.get('Start Date', ''))))
                saved += 1
                
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        return saved
    
    def scrape(self, target: int = 50000):
        print("="*70)
        print(f"PRODUCTION SCRAPER - Target: {target} contracts (AUTO-RETRY)")
        print("="*70)
        
        total_saved = 0
        page = 1
        start_time = time.time()
        consecutive_failures = 0
        
        while total_saved < target and page <= 500:
            print(f"Page {page}...", end=" ", flush=True)
            
            contracts = self.fetch_page(page)
            
            if not contracts:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    print(f"\n❌ 5 consecutive failures. Stopping.")
                    break
                print(f" | Failures: {consecutive_failures}/5")
                page += 1
                time.sleep(5)
                continue
            
            consecutive_failures = 0
            saved = self.save_contracts(contracts)
            total_saved += saved
            
            elapsed = time.time() - start_time
            rate = total_saved / elapsed if elapsed > 0 else 0
            eta_hours = (target - total_saved) / rate / 3600 if rate > 0 else 0
            
            print(f"✅ {saved} | Total: {total_saved:,}/{target:,} | {rate:.1f}/s | ETA: {eta_hours:.1f}h")
            
            if total_saved % 5000 == 0 and total_saved > 0:
                print(f"\n{'='*70}")
                print(f"CHECKPOINT: {total_saved:,} contracts | {elapsed/60:.1f} minutes")
                print(f"{'='*70}\n")
            
            page += 1
            time.sleep(1)
        
        print(f"\n{'='*70}")
        print(f"✅ SESSION COMPLETE: {total_saved:,} contracts in {elapsed/60:.1f} min")
        print(f"{'='*70}")

if __name__ == "__main__":
    scraper = ProductionScraper("data/sunlight.db")
    scraper.scrape(50000)
