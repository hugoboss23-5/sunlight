import sqlite3
from typing import List, Dict, Tuple
from collections import defaultdict

class PriceAnalyzer:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def get_contracts_by_agency(self) -> Dict[str, List[Dict]]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT contract_id, award_amount, vendor_name, agency_name, description FROM contracts WHERE award_amount > 0")
        
        by_agency = defaultdict(list)
        for row in c.fetchall():
            contract = {
                'id': row[0],
                'amount': row[1],
                'vendor': row[2],
                'agency': row[3],
                'desc': row[4]
            }
            by_agency[row[3]].append(contract)
        
        conn.close()
        return dict(by_agency)
    
    def find_price_anomalies(self) -> List[Dict]:
        print("SUNLIGHT PRICE COMPARISON ANALYSIS")
        print("="*50)
        
        by_agency = self.get_contracts_by_agency()
        anomalies = []
        
        for agency, contracts in by_agency.items():
            if len(contracts) < 3:
                continue
            
            amounts = [c['amount'] for c in contracts]
            avg = sum(amounts) / len(amounts)
            
            for contract in contracts:
                if contract['amount'] > avg * 2:
                    markup = ((contract['amount'] - avg) / avg) * 100
                    anomalies.append({
                        'contract': contract,
                        'agency': agency,
                        'avg_agency_contract': avg,
                        'markup_pct': markup,
                        'sample_size': len(contracts)
                    })
        
        anomalies.sort(key=lambda x: x['markup_pct'], reverse=True)
        
        print(f"\nFound {len(anomalies)} price anomalies\n")
        print("TOP 10 SUSPICIOUS CONTRACTS:")
        print("-"*50)
        
        for i, anom in enumerate(anomalies[:10], 1):
            c = anom['contract']
            print(f"\n{i}. {c['vendor']}")
            print(f"   Contract Amount: ${c['amount']:,.0f}")
            print(f"   Agency Average: ${anom['avg_agency_contract']:,.0f}")
            print(f"   Markup: {anom['markup_pct']:.0f}% above average")
            print(f"   Sample: {anom['sample_size']} contracts in {anom['agency']}")
            print(f"   RED FLAG: Price is {anom['markup_pct']/100 + 1:.1f}x the agency average")
        
        return anomalies

if __name__ == "__main__":
    analyzer = PriceAnalyzer()
    analyzer.find_price_anomalies()
