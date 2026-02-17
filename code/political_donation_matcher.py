import requests
import sqlite3
from typing import Dict, List
import time

class DonationMatcher:
    def __init__(self, api_key: str = None, db_path: str = "data/sunlight.db"):
        self.api_key = api_key
        self.base_url = "http://www.opensecrets.org/api/"
        self.db_path = db_path
        self.init_donation_table()
    
    def init_donation_table(self):
        """Create table to store donation data"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS political_donations
                     (vendor_name TEXT,
                      recipient_name TEXT,
                      amount REAL,
                      date TEXT,
                      cycle TEXT,
                      source TEXT,
                      PRIMARY KEY (vendor_name, recipient_name, cycle))''')
        conn.commit()
        conn.close()
    
    def search_vendor_donations(self, vendor_name: str) -> List[Dict]:
        """Search for political donations by vendor"""
        
        if not self.api_key:
            print(f"⚠️  No API key - returning mock data for {vendor_name}")
            return self.get_mock_donations(vendor_name)
        
        # Clean vendor name for search
        search_name = vendor_name.replace(',', '').replace('.', '').split()[0]
        
        try:
            # OpenSecrets organization search
            params = {
                'method': 'getOrgs',
                'org': search_name,
                'apikey': self.api_key,
                'output': 'json'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Parse donation data
                # NOTE: Actual parsing depends on API response structure
                return self.parse_opensecrets_response(data, vendor_name)
            else:
                print(f"  API error {response.status_code}")
                return []
        
        except Exception as e:
            print(f"  Error: {e}")
            return []
    
    def get_mock_donations(self, vendor_name: str) -> List[Dict]:
        """Mock donation data for testing (until API key is added)"""
        
        # Known defense contractors with major political donations
        major_donors = {
            'BOEING': [
                {'recipient': 'Senate Armed Services Committee Members', 'amount': 2500000, 'cycle': '2020-2024'},
                {'recipient': 'House Appropriations Committee', 'amount': 1800000, 'cycle': '2020-2024'}
            ],
            'GENERAL DYNAMICS': [
                {'recipient': 'Defense Appropriations Subcommittee', 'amount': 1200000, 'cycle': '2020-2024'}
            ],
            'LOCKHEED': [
                {'recipient': 'Senate Defense Committee', 'amount': 3000000, 'cycle': '2020-2024'}
            ]
        }
        
        vendor_key = next((k for k in major_donors.keys() if k in vendor_name.upper()), None)
        
        if vendor_key:
            return [
                {
                    'vendor': vendor_name,
                    'recipient': d['recipient'],
                    'amount': d['amount'],
                    'cycle': d['cycle'],
                    'source': 'MOCK_DATA'
                }
                for d in major_donors[vendor_key]
            ]
        
        return []
    
    def parse_opensecrets_response(self, data: dict, vendor_name: str) -> List[Dict]:
        """Parse OpenSecrets API response"""
        # This will be implemented once we have real API responses
        # For now, return empty
        return []
    
    def save_donations(self, donations: List[Dict]):
        """Save donations to database"""
        if not donations:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        saved = 0
        
        for d in donations:
            try:
                c.execute('''INSERT OR REPLACE INTO political_donations VALUES (?,?,?,?,?,?)''',
                         (d['vendor'],
                          d['recipient'],
                          d['amount'],
                          d.get('date', ''),
                          d['cycle'],
                          d.get('source', 'opensecrets')))
                saved += 1
            except:
                pass
        
        conn.commit()
        conn.close()
        return saved
    
    def analyze_vendor_donations(self, vendor_name: str) -> Dict:
        """Analyze donation patterns for a vendor"""
        
        # Get donations
        donations = self.search_vendor_donations(vendor_name)
        
        if not donations:
            return {
                'vendor': vendor_name,
                'total_donations': 0,
                'recipients': [],
                'has_donations': False
            }
        
        # Save to DB
        self.save_donations(donations)
        
        total = sum(d['amount'] for d in donations)
        recipients = [d['recipient'] for d in donations]
        
        return {
            'vendor': vendor_name,
            'total_donations': total,
            'recipients': recipients,
            'donations': donations,
            'has_donations': True
        }
    
    def scan_all_flagged_vendors(self):
        """Scan all vendors with suspicious contracts"""
        print("="*70)
        print("POLITICAL DONATION ANALYSIS")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get vendors with high-value contracts
        c.execute("""
            SELECT DISTINCT vendor_name, COUNT(*) as count, SUM(award_amount) as total
            FROM contracts
            WHERE award_amount > 10000000
            GROUP BY vendor_name
            ORDER BY total DESC
        """)
        
        vendors = c.fetchall()
        conn.close()
        
        print(f"\nScanning {len(vendors)} high-value vendors for political donations...\n")
        
        results = []
        for vendor_name, count, total in vendors:
            print(f"Checking: {vendor_name}...", end=" ")
            
            analysis = self.analyze_vendor_donations(vendor_name)
            results.append(analysis)
            
            if analysis['has_donations']:
                print(f"✅ Found ${analysis['total_donations']:,.0f} in donations")
            else:
                print("No donations found")
            
            time.sleep(0.5)  # Rate limiting
        
        print("\n" + "="*70)
        print("DONATION SUMMARY")
        print("="*70)
        
        donors = [r for r in results if r['has_donations']]
        print(f"\nVendors with political donations: {len(donors)}/{len(results)}")
        
        if donors:
            print("\nTOP DONORS:")
            for r in sorted(donors, key=lambda x: x['total_donations'], reverse=True):
                print(f"\n{r['vendor']}")
                print(f"  Total: ${r['total_donations']:,.0f}")
                print(f"  Recipients: {', '.join(r['recipients'][:3])}")
        
        print("\n" + "="*70)
        return results

if __name__ == "__main__":
    # For now, run with mock data (no API key)
    matcher = DonationMatcher(api_key=None)
    matcher.scan_all_flagged_vendors()
