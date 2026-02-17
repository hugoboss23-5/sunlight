import requests
import sqlite3
import time

class AmendmentScraper:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
        self.init_amendment_table()
    
    def init_amendment_table(self):
        """Create table for amendment tracking"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS contract_amendments
                     (contract_id TEXT PRIMARY KEY,
                      base_amount REAL,
                      current_amount REAL,
                      modification_count INTEGER,
                      growth_percentage REAL,
                      last_modified_date TEXT)''')
        conn.commit()
        conn.close()
    
    def fetch_contract_history(self, award_id: str) -> dict:
        """Fetch full contract history including amendments from USAspending API"""
        
        # USAspending has a different endpoint for contract details
        url = f"https://api.usaspending.gov/api/v2/awards/{award_id}/"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self.parse_amendment_data(data)
            else:
                return None
        except Exception as e:
            return None
    
    def parse_amendment_data(self, data: dict) -> dict:
        """Extract amendment info from API response"""
        # This structure depends on actual API response
        # Will implement once we see real data
        
        # Expected fields:
        # - base_and_all_options_value (original)
        # - total_obligation (current)
        # - number_of_actions (modifications)
        
        return {
            'base_amount': 0,
            'current_amount': 0,
            'modification_count': 0
        }
    
    def analyze_existing_contracts(self):
        """Check our existing contracts for potential amendment patterns"""
        
        print("="*70)
        print("CONTRACT AMENDMENT ANALYSIS")
        print("="*70)
        print("\nNOTE: Current database doesn't have amendment data")
        print("We'll need to:")
        print("  1. Re-scrape with amendment fields")
        print("  2. OR use a different API endpoint for contract details")
        print()
        print("For now, let's identify contracts worth investigating for amendments:")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Find large contracts (likely to have amendments)
        c.execute("""
            SELECT contract_id, vendor_name, award_amount, agency_name
            FROM contracts
            WHERE award_amount > 10000000
            ORDER BY award_amount DESC
            LIMIT 20
        """)
        
        print("\nHIGH-VALUE CONTRACTS (Likely Amended):")
        print("-"*70)
        for row in c.fetchall():
            print(f"{row[1]}: ${row[2]:,.0f}")
            print(f"  Contract ID: {row[0]}")
            print(f"  Agency: {row[3]}")
            print(f"  ⚠️  Need to fetch amendment history from API")
            print()
        
        conn.close()

if __name__ == "__main__":
    scraper = AmendmentScraper()
    scraper.analyze_existing_contracts()
