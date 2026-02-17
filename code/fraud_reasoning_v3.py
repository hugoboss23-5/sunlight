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

class FraudReasoningV3:
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
        if any(kw in desc for kw in ['aircraft', 'aviation', 'aerospace']):
            return "AEROSPACE"
        elif any(kw in desc for kw in ['it ', 'software', 'computer']):
            return "IT"
        elif any(kw in desc for kw in ['maintenance', 'repair']):
            return "MAINTENANCE"
        elif any(kw in desc for kw in ['research', 'development']):
            return "R&D"
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
        
        # Get same size category
        similar = [a for a in amounts if self.categorize_size(a) == target_size]
        
        # If too few, expand to adjacent categories
        if len(similar) < 3:
            size_values = {"MICRO": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3, "MEGA": 4}
            target_val = size_values[target_size]
            
            similar = [a for a in amounts 
                      if abs(size_values[self.categorize_size(a)] - target_val) <= 1]
        
        # Absolute minimum
        if len(similar) < 3:
            return {'valid': False, 'reason': f'Only {len(similar)} comparable contracts'}
        
        median = statistics.median(similar)
        mean = statistics.mean(similar)
        stdev = statistics.stdev(similar) if len(similar) > 1 else 0
        
        z_score = (target['amount'] - mean) / stdev if stdev > 0 else 0
        markup = ((target['amount'] - median) / median) * 100
        
        # Reduce confidence if small sample
        sample_confidence_penalty = 0
        if len(similar) < 5:
            sample_confidence_penalty = 10
        if len(similar) < 10:
            sample_confidence_penalty = 5
        
        return {
            'valid': True,
            'median': median,
            'mean': mean,
            'stdev': stdev,
            'z_score': z_score,
            'markup': markup,
            'sample_size': len(similar),
            'confidence_penalty': sample_confidence_penalty
        }
    
    def analyze_contract(self, contract: Dict) -> FraudAssessment:
        reasoning = []
        legal_violations = []
        confidence_factors = []
        
        # SMART BASELINE
        baseline = self.calculate_smart_baseline(contract)
        
        if not baseline['valid']:
            return FraudAssessment(
                contract_id=contract['id'],
                vendor_name=contract['vendor'],
                amount=contract['amount'],
                confidence=0,
                tier="🟢 GREEN",
                reasoning=[baseline['reason']],
                legal_violations=[],
                evidence={}
            )
        
        # Price analysis
        reasoning.append(f"Amount: ${contract['amount']:,.0f} vs baseline ${baseline['median']:,.0f}")
        reasoning.append(f"Sample: n={baseline['sample_size']} | Markup: {baseline['markup']:.0f}% | Z-score: {baseline['z_score']:.2f}")
        
        contract_type = self.categorize_type(contract.get('desc', ''))
        reasoning.append(f"Type: {contract_type} | Size: {self.categorize_size(contract['amount'])}")
        
        # Flag logic
        if baseline['markup'] > 300 and baseline['z_score'] > 2.5:
            confidence_factors.append(95)
            legal_violations.append("False Claims Act - Extreme Price Inflation")
            reasoning.append("🚨 EXTREME: >300% markup AND >2.5σ")
        elif baseline['markup'] > 200 and baseline['z_score'] > 1.5:
            confidence_factors.append(85)
            legal_violations.append("False Claims Act - Price Inflation")
            reasoning.append("🚩 SUSPICIOUS: >200% markup AND >1.5σ")
            if contract_type in ["STANDARD", "IT"]:
                confidence_factors.append(90)
                reasoning.append("→ Standard services should justify >200% markup")
        elif baseline['markup'] > 150:
            confidence_factors.append(70)
            reasoning.append("⚠️  ELEVATED: >150% markup")
        
        # Vendor concentration
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM contracts WHERE vendor_name = ?", (contract['vendor'],))
        vendor_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM contracts")
        total = c.fetchone()[0]
        conn.close()
        
        concentration = (vendor_count / total) * 100
        if concentration > 25:
            reasoning.append(f"Vendor: {vendor_count} contracts ({concentration:.0f}% concentration)")
            legal_violations.append("Procurement Integrity Act - Competition")
            confidence_factors.append(75)
        
        # Calculate confidence with penalty
        base_confidence = int(sum(confidence_factors) / len(confidence_factors)) if confidence_factors else 0
        confidence = max(0, base_confidence - baseline.get('confidence_penalty', 0))
        
        # Tier
        if confidence >= 90 and len(legal_violations) >= 2:
            tier = "🔴 RED"
        elif confidence >= 80 and len(legal_violations) >= 1:
            tier = "🔴 RED"
        elif confidence >= 70:
            tier = "🟡 YELLOW"
        else:
            tier = "🟢 GREEN"
        
        return FraudAssessment(
            contract_id=contract['id'],
            vendor_name=contract['vendor'],
            amount=contract['amount'],
            confidence=confidence,
            tier=tier,
            reasoning=reasoning,
            legal_violations=legal_violations,
            evidence=baseline
        )
    
    def generate_report(self):
        print("="*70)
        print("SUNLIGHT V3 - SMART BASELINES + SMALL SAMPLE HANDLING")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT contract_id, award_amount, vendor_name, agency_name, description
            FROM contracts
            WHERE award_amount > 10000000
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
        print(f"  🔴 RED: {len(red)}")
        print(f"  🟡 YELLOW: {len(yellow)}")
        print()
        
        if red:
            print("🔴 RED TIER - HIGH CONFIDENCE")
            print("="*70)
            for i, a in enumerate(red, 1):
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f}")
                print(f"   Confidence: {a.confidence}%")
                for r in a.reasoning:
                    print(f"   {r}")
                if a.legal_violations:
                    print(f"   VIOLATIONS:")
                    for v in a.legal_violations:
                        print(f"   ⚖️  {v}")
                print("-"*70)
        else:
            print("🔴 RED: None (need more data or all contracts normal)")
        
        if yellow:
            print("\n🟡 YELLOW TIER")
            for a in yellow:
                print(f"  • {a.vendor_name} - ${a.amount:,.0f} ({a.confidence}%)")
        
        print(f"\n✅ {len(red)} high-confidence fraud indicators")

if __name__ == "__main__":
    engine = FraudReasoningV3()
    engine.generate_report()
