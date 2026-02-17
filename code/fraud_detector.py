import sqlite3
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class FraudIndicator:
    contract_id: str
    vendor_name: str
    amount: float
    risk_score: int
    flags: List[str]
    evidence: List[str]

class FraudDetector:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def get_contracts(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT contract_id, award_amount, vendor_name, agency_name, description FROM contracts")
        contracts = []
        for row in c.fetchall():
            contracts.append({'id': row[0], 'amount': row[1], 'vendor': row[2], 'agency': row[3], 'desc': row[4]})
        conn.close()
        return contracts
    
    def detect_price_outliers(self, contracts: List[Dict]) -> List[FraudIndicator]:
        amounts = [c['amount'] for c in contracts if c['amount'] > 0]
        if len(amounts) < 10:
            return []
        
        median = statistics.median(amounts)
        stdev = statistics.stdev(amounts)
        
        outliers = []
        for c in contracts:
            if c['amount'] > median + (3 * stdev):
                z_score = (c['amount'] - median) / stdev if stdev > 0 else 0
                outliers.append(FraudIndicator(
                    contract_id=c['id'],
                    vendor_name=c['vendor'],
                    amount=c['amount'],
                    risk_score=min(100, int(z_score * 20)),
                    flags=['PRICE_OUTLIER'],
                    evidence=[f'Amount ${c["amount"]:,.0f} is {z_score:.1f} std devs above median ${median:,.0f}']
                ))
        return outliers
    
    def detect_vendor_concentration(self, contracts: List[Dict]) -> Dict[str, int]:
        vendor_counts = {}
        for c in contracts:
            vendor = c['vendor']
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        
        suspicious = {v: count for v, count in vendor_counts.items() if count >= 3}
        return suspicious
    
    def analyze(self) -> Tuple[List[FraudIndicator], Dict]:
        print("🔍 SUNLIGHT FRAUD DETECTION")
        print("="*50)
        
        contracts = self.get_contracts()
        print(f"📊 Analyzing {len(contracts)} contracts...")
        
        outliers = self.detect_price_outliers(contracts)
        concentration = self.detect_vendor_concentration(contracts)
        
        print(f"\n🚩 FINDINGS:")
        print(f"  Price Outliers: {len(outliers)}")
        print(f"  Vendor Concentration: {len(concentration)} vendors")
        
        print(f"\n💰 TOP PRICE OUTLIERS:")
        for i, outlier in enumerate(sorted(outliers, key=lambda x: x.risk_score, reverse=True)[:10], 1):
            print(f"  {i}. {outlier.vendor_name}")
            print(f"     Amount: ${outlier.amount:,.0f}")
            print(f"     Risk: {outlier.risk_score}/100")
            print(f"     Evidence: {outlier.evidence[0]}")
            print()
        
        print(f"🏢 VENDOR CONCENTRATION (3+ contracts):")
        for vendor, count in sorted(concentration.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {vendor}: {count} contracts")
        
        return outliers, concentration

if __name__ == "__main__":
    detector = FraudDetector()
    detector.analyze()
