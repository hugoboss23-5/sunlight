import sqlite3
import statistics
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class FraudAssessment:
    contract_id: str
    vendor_name: str
    amount: float
    confidence: int
    tier: str
    reasoning: List[str]
    legal_violations: List[str]
    evidence: Dict
    has_donations: bool
    donation_amount: float

class FraudWithDonations:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def categorize_size(self, amount: float) -> str:
        if amount < 100000:
            return "MICRO"
        elif amount < 1000000:
            return "SMALL"
        elif amount < 5000000:
            return "MEDIUM"
        elif amount < 25000000:
            return "LARGE"
        else:
            return "MEGA"
    
    def categorize_type(self, desc: str) -> str:
        desc = desc.lower() if desc else ""
        
        if any(kw in desc for kw in ['research', 'development', 'r&d']):
            return "R&D"
        elif any(kw in desc for kw in ['it ', 'software', 'computer', 'technology']):
            return "STANDARD_IT"
        elif any(kw in desc for kw in ['maintenance', 'repair', 'support']):
            return "STANDARD_MAINTENANCE"
        elif any(kw in desc for kw in ['aircraft', 'aviation', 'aerospace']):
            return "AEROSPACE"
        else:
            return "STANDARD"
    
    def calculate_smart_baseline(self, target: Dict) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        target_size = self.categorize_size(target['amount'])
        
        c.execute("SELECT award_amount FROM contracts WHERE agency_name = ? AND award_amount > 0", 
                 (target['agency'],))
        amounts = [row[0] for row in c.fetchall()]
        conn.close()
        
        similar = [a for a in amounts if self.categorize_size(a) == target_size]
        
        if len(similar) < 3:
            size_values = {"MICRO": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3, "MEGA": 4}
            target_val = size_values[target_size]
            similar = [a for a in amounts 
                      if abs(size_values[self.categorize_size(a)] - target_val) <= 1]
        
        if len(similar) < 3:
            return {'valid': False}
        
        median = statistics.median(similar)
        mean = statistics.mean(similar)
        stdev = statistics.stdev(similar) if len(similar) > 1 else 0
        z_score = (target['amount'] - mean) / stdev if stdev > 0 else 0
        markup = ((target['amount'] - median) / median) * 100
        
        return {
            'valid': True,
            'median': median,
            'markup': markup,
            'z_score': z_score,
            'sample_size': len(similar)
        }
    
    def get_vendor_donations(self, vendor_name: str) -> Dict:
        """Check if vendor has political donations"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT SUM(amount), COUNT(*) FROM political_donations WHERE vendor_name = ?", 
                 (vendor_name,))
        row = c.fetchone()
        conn.close()
        
        if row and row[0]:
            return {'has_donations': True, 'total': row[0], 'count': row[1]}
        return {'has_donations': False, 'total': 0, 'count': 0}
    
    def analyze_contract(self, contract: Dict) -> FraudAssessment:
        reasoning = []
        legal_violations = []
        confidence_boost = 0
        
        baseline = self.calculate_smart_baseline(contract)
        
        if not baseline['valid']:
            return FraudAssessment(
                contract_id=contract['id'],
                vendor_name=contract['vendor'],
                amount=contract['amount'],
                confidence=0,
                tier="🟢 GREEN",
                reasoning=["Insufficient comparison data"],
                legal_violations=[],
                evidence={},
                has_donations=False,
                donation_amount=0
            )
        
        contract_type = self.categorize_type(contract.get('desc', ''))
        
        reasoning.append(f"Amount: ${contract['amount']:,.0f} vs baseline ${baseline['median']:,.0f}")
        reasoning.append(f"Markup: {baseline['markup']:.0f}% | Z-score: {baseline['z_score']:.2f} | n={baseline['sample_size']}")
        reasoning.append(f"Type: {contract_type}")
        
        # BASE CONFIDENCE from price
        base_confidence = 0
        
        if baseline['markup'] > 300 and contract_type.startswith("STANDARD"):
            base_confidence = 85
            legal_violations.append("False Claims Act - Extreme Price Inflation")
            reasoning.append("🚨 >300% markup on standard item (DOJ high-risk)")
        elif baseline['markup'] > 200 and contract_type.startswith("STANDARD"):
            base_confidence = 75
            legal_violations.append("False Claims Act - Price Inflation")
            reasoning.append("🚩 >200% markup on standard item (DOJ medium-risk)")
        elif baseline['markup'] > 150:
            base_confidence = 65
            reasoning.append("⚠️  >150% markup (investigation-worthy)")
        
        # CHECK POLITICAL DONATIONS
        donations = self.get_vendor_donations(contract['vendor'])
        
        if donations['has_donations']:
            reasoning.append(f"💰 POLITICAL DONATIONS: ${donations['total']:,.0f} to {donations['count']} recipients")
            legal_violations.append("Anti-Kickback Act - Political Donation Pattern")
            
            # Donations + price inflation = MAJOR RED FLAG
            if base_confidence >= 65:
                confidence_boost = 15
                reasoning.append("→ Price inflation + political donations = quid pro quo indicator")
        
        final_confidence = min(95, base_confidence + confidence_boost)
        
        # TIER DETERMINATION
        if final_confidence >= 85 and len(legal_violations) >= 2:
            tier = "🔴 RED"
        elif final_confidence >= 80 and donations['has_donations']:
            tier = "🔴 RED"  # Donations + high price = RED even at 80%
        elif final_confidence >= 65:
            tier = "🟡 YELLOW"
        else:
            tier = "🟢 GREEN"
        
        return FraudAssessment(
            contract_id=contract['id'],
            vendor_name=contract['vendor'],
            amount=contract['amount'],
            confidence=final_confidence,
            tier=tier,
            reasoning=reasoning,
            legal_violations=legal_violations,
            evidence=baseline,
            has_donations=donations['has_donations'],
            donation_amount=donations['total']
        )
    
    def generate_report(self):
        print("="*70)
        print("SUNLIGHT - PRICE + POLITICAL DONATIONS ANALYSIS")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT contract_id, award_amount, vendor_name, agency_name, description
            FROM contracts
            WHERE award_amount > 5000000
            ORDER BY award_amount DESC
        """)
        
        assessments = []
        for row in c.fetchall():
            contract = {'id': row[0], 'amount': row[1], 'vendor': row[2], 'agency': row[3], 'desc': row[4]}
            assessment = self.analyze_contract(contract)
            assessments.append(assessment)
        
        conn.close()
        
        red = [a for a in assessments if '🔴' in a.tier]
        yellow = [a for a in assessments if '🟡' in a.tier]
        
        print(f"\nRESULTS:")
        print(f"  🔴 RED (High Confidence): {len(red)}")
        print(f"  🟡 YELLOW (Investigation-Worthy): {len(yellow)}")
        print()
        
        if red:
            print("🔴 RED TIER - HIGH CONFIDENCE FRAUD INDICATORS")
            print("="*70)
            for i, a in enumerate(red, 1):
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f}")
                print(f"   Confidence: {a.confidence}%")
                if a.has_donations:
                    print(f"   💰 Political Donations: ${a.donation_amount:,.0f}")
                for r in a.reasoning:
                    print(f"   {r}")
                if a.legal_violations:
                    print(f"   VIOLATIONS:")
                    for v in a.legal_violations:
                        print(f"   ⚖️  {v}")
                print("-"*70)
        else:
            print("🔴 RED: None with current data")
        
        if yellow:
            print("\n🟡 YELLOW TIER")
            print("="*70)
            for i, a in enumerate(yellow[:5], 1):
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f} ({a.confidence}%)")
                if a.has_donations:
                    print(f"   💰 Donations: ${a.donation_amount:,.0f}")
                for r in a.reasoning[:3]:
                    print(f"   {r}")
        
        print(f"\n✅ {len(red)} high-confidence cases + {len(yellow)} investigation-worthy")
        print("="*70)

if __name__ == "__main__":
    engine = FraudWithDonations()
    engine.generate_report()
