import requests
import sqlite3
import time

class ScaleScraper:
    def __init__(self, db_path: str = "../data/sunlight.db"):
        self.url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        self.db_path = db_path
    
    def scrape_to_target(self, target: int = 1000):
        """Scale database to target number of contracts"""
        
        # Check current count
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM contracts")
        current = c.fetchone()[0]
        conn.close()
        
        print(f"Current contracts: {current}")
        print(f"Target: {target}")
        needed = target - current
        
        if needed <= 0:
            print("✅ Already at target!")
            return
        
        print(f"Need to scrape: {needed} more contracts")
        pages_needed = (needed // 100) + 1
        
        print(f"Scraping {pages_needed} pages...")
        
        # Calculate starting page (avoid duplicates)
        start_page = (current // 100) + 1
        
        total_saved = 0
        for page in range(start_page, start_page + pages_needed):
            print(f"Page {page}...", end=" ", flush=True)
            
            payload = {
                "filters": {
                    "award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": "2023-01-01", "end_date": "2024-12-31"}]
                },
                "fields": ["Award ID", "Recipient Name", "Award Amount", 
                          "Awarding Agency", "Start Date", "Description"],
                "limit": 100,
                "page": page
            }
            
            try:
                response = requests.post(self.url, json=payload, timeout=30)
                response.raise_for_status()
                contracts = response.json().get('results', [])
                
                if not contracts:
                    print("No data")
                    break
                
                saved = self.save_contracts(contracts)
                total_saved += saved
                print(f"✅ {saved} saved (Total: {current + total_saved})")
                
                time.sleep(1)
                
                if current + total_saved >= target:
                    print(f"✅ Target reached!")
                    break
                    
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        print(f"\n✅ COMPLETE: {current + total_saved} total contracts")
    
    def save_contracts(self, contracts: list) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        saved = 0
        
        for contract in contracts:
            try:
                c.execute('''INSERT OR REPLACE INTO contracts 
                            (contract_id, award_amount, vendor_name, agency_name, description, start_date) 
                            VALUES (?,?,?,?,?,?)''',
                         (str(contract.get('Award ID', ''))[:200],
                          float(contract.get('Award Amount', 0)),
                          str(contract.get('Recipient Name', ''))[:200],
                          str(contract.get('Awarding Agency', ''))[:200],
                          str(contract.get('Description', ''))[:500],
                          str(contract.get('Start Date', ''))))
                saved += 1
            except:
                pass
        
        conn.commit()
        conn.close()
        return saved

if __name__ == "__main__":
    scraper = ScaleScraper()
    scraper.scrape_to_target(1000)
