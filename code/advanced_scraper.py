import requests, sqlite3, json, time
from typing import List, Dict
from datetime import datetime

class SunlightScraper:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.base_url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS contracts (contract_id TEXT PRIMARY KEY, award_amount REAL, vendor_name TEXT, agency_name TEXT, description TEXT, start_date TEXT, created_at TEXT)''')
        conn.commit()
        conn.close()
    
    def fetch_page(self, page: int) -> List[Dict]:
        payload = {"filters": {"award_type_codes": ["A", "B", "C", "D"], "time_period": [{"start_date": "2023-01-01", "end_date": "2024-12-31"}]}, "limit": 100, "page": page}
        for attempt in range(3):
            try:
                response = requests.post(self.base_url, json=payload, timeout=30)
                response.raise_for_status()
                return response.json().get('results', [])
            except Exception as e:
                print(f"Attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2: time.sleep(2)
        return []
    
    def save_contracts(self, contracts: List[Dict]) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        saved = 0
        for contract in contracts:
            try:
                c.execute('''INSERT OR REPLACE INTO contracts VALUES (?,?,?,?,?,?,?)''', (str(contract.get('Award ID', '')), float(contract.get('Award Amount', 0)), str(contract.get('Recipient Name', ''))[:200], str(contract.get('Awarding Agency', ''))[:200], str(contract.get('Description', ''))[:500], str(contract.get('Start Date', '')), datetime.now().isoformat()))
                saved += 1
            except: pass
        conn.commit()
        conn.close()
        return saved
    
    def scrape(self, target: int = 1000):
        print(f"SUNLIGHT SCRAPER - Target: {target} contracts")
        total_saved = 0
        page = 1
        while total_saved < target:
            print(f"Page {page} - Fetching...", end=" ")
            contracts = self.fetch_page(page)
            if not contracts: break
            saved = self.save_contracts(contracts)
            total_saved += saved
            print(f"Saved {saved} (Total: {total_saved})")
            page += 1
            time.sleep(1)
            if len(contracts) < 100: break
        print(f"COMPLETE: {total_saved} contracts")

if __name__ == "__main__":
    SunlightScraper().scrape(1000)
