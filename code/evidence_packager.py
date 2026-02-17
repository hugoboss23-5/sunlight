import sqlite3
from typing import Dict, List
import json
from datetime import datetime

class EvidencePackager:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def get_contract_details(self, contract_id: str) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM contracts WHERE contract_id = ?", (contract_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        return {
            'contract_id': row[0],
            'award_amount': row[1],
            'vendor_name': row[2],
            'agency_name': row[3],
            'description': row[4],
            'start_date': row[5]
        }
    
    def calculate_agency_baseline(self, agency: str) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT award_amount FROM contracts WHERE agency_name = ? AND award_amount > 0", (agency,))
        amounts = [row[0] for row in c.fetchall()]
        conn.close()
        
        if not amounts:
            return {}
        
        avg = sum(amounts) / len(amounts)
        return {
            'average': avg,
            'sample_size': len(amounts),
            'agency': agency
        }
    
    def generate_evidence_package(self, vendor_name: str) -> Dict:
        """Generate complete evidence package for vendor"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM contracts WHERE vendor_name = ? ORDER BY award_amount DESC", (vendor_name,))
        contracts = []
        
        for row in c.fetchall():
            contracts.append({
                'contract_id': row[0],
                'amount': row[1],
                'agency': row[3],
                'description': row[4],
                'date': row[5]
            })
        
        conn.close()
        
        if not contracts:
            return {}
        
        # Calculate vendor statistics
        total_value = sum(c['amount'] for c in contracts)
        avg_contract = total_value / len(contracts)
        
        # Get agency baseline
        agency = contracts[0]['agency']
        baseline = self.calculate_agency_baseline(agency)
        
        # Calculate markup
        markup = 0
        if baseline and baseline['average'] > 0:
            markup = ((avg_contract - baseline['average']) / baseline['average']) * 100
        
        return {
            'vendor': vendor_name,
            'contract_count': len(contracts),
            'total_value': total_value,
            'average_contract': avg_contract,
            'agency_baseline': baseline.get('average', 0),
            'markup_percentage': markup,
            'contracts': contracts[:5],  # Top 5
            'red_flags': self.identify_red_flags(contracts, baseline, markup),
            'generated_at': datetime.now().isoformat()
        }
    
    def identify_red_flags(self, contracts: List[Dict], baseline: Dict, markup: float) -> List[str]:
        flags = []
        
        if len(contracts) >= 5:
            flags.append(f"VENDOR_CONCENTRATION: Won {len(contracts)} contracts")
        
        if markup > 200:
            flags.append(f"PRICE_INFLATION: {markup:.0f}% above agency average")
        
        if baseline.get('sample_size', 0) > 10:
            flags.append(f"STATISTICAL_SIGNIFICANCE: Based on {baseline['sample_size']} contract sample")
        
        return flags
    
    def generate_all_packages(self):
        print("EVIDENCE PACKAGE GENERATOR")
        print("="*50)
        
        # Get top vendors
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT vendor_name, COUNT(*) as count, SUM(award_amount) as total
            FROM contracts
            GROUP BY vendor_name
            HAVING count >= 3
            ORDER BY total DESC
            LIMIT 5
        """)
        
        packages = []
        for row in c.fetchall():
            vendor = row[0]
            package = self.generate_evidence_package(vendor)
            packages.append(package)
            
            print(f"\n{'='*50}")
            print(f"VENDOR: {package['vendor']}")
            print(f"{'='*50}")
            print(f"Contract Count: {package['contract_count']}")
            print(f"Total Value: ${package['total_value']:,.0f}")
            print(f"Average Contract: ${package['average_contract']:,.0f}")
            print(f"Agency Baseline: ${package['agency_baseline']:,.0f}")
            print(f"Markup: {package['markup_percentage']:.0f}%")
            print(f"\nRED FLAGS:")
            for flag in package['red_flags']:
                print(f"  🚩 {flag}")
            
            print(f"\nTOP CONTRACTS:")
            for i, contract in enumerate(package['contracts'][:3], 1):
                print(f"  {i}. ${contract['amount']:,.0f} - {contract['date']}")
        
        conn.close()
        
        # Save to JSON
        with open('evidence_packages.json', 'w') as f:
            json.dump(packages, f, indent=2)
        
        print(f"\n{'='*50}")
        print(f"✅ Evidence packages saved to evidence_packages.json")
        
        return packages

if __name__ == "__main__":
    packager = EvidencePackager()
    packager.generate_all_packages()
