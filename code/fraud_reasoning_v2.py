import sqlite3
import json
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

class FraudReasoningV2:
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
        
        similar = [a for a in amounts if self.categorize_size(a) == target_size]
        
        if len(similar) < 5:
            return {'valid': False, 'reason': 'Insufficient data'}
        
        median = statistics.median(similar)
        mean = statistics.mean(similar)
        stdev = statistics.stdev(similar)
        
        z_score = (target['amount'] - mean) / stdev if stdev > 0 else 0
        markup = ((target['amount'] - median) / median) * 100
        
        return {
            'valid': True,
            'median': median,
            'mean': mean,
            'stdev': stdev,
            'z_score': z_score,
            'markup': markup,
            'sample_size': len(similar)
        }
    
    def analyze_contract(self, contract: Dict) -> FraudAssessment:
        reasoning = []
        legal_violations = []
        confidence_factors = []
        
        # SMART BASELINE ANALYSIS
        baseline = self.calculate_smart_baseline(contract)
        
        if not baseline['valid']:
            return FraudAssessment(
                contract_id=contract['id'],
                vendor_name=contract['vendor'],
                amount=contract['amount'],
                confidence=0,
                tier="🟢 GREEN",
                reasoning=["Insufficient data for comparison"],
                legal_violations=[],
                evidence={}
            )
        
        # Analyze price
        reasoning.append(f"Price: ${contract['amount']:,.0f} vs baseline ${baseline['median']:,.0f} (n={baseline['sample_size']})")
        reasoning.append(f"Markup: {baseline['markup']:.0f}% | Z-Score: {baseline['z_score']:.2f}")
        
        # Check contract type
        contract_type = self.categorize_type(contract.get('desc', ''))
        reasoning.append(f"Type: {contract_type}")
        
        # Determine if suspicious
        if baseline['markup'] > 300 and baseline['z_score'] > 2.5:
            confidence_factors.append(95)
            legal_violations.append("False Claims Act - Extreme Price Inflation")
            reasoning.append("→ EXTREME: >300% markup AND >2.5 std deviations")
        elif baseline['markup'] > 200 and baseline['z_score'] > 1.5:
            confidence_factors.append(85)
            legal_violations.append("False Claims Act - Price Inflation")
            reasoning.append("→ SUSPICIOUS: >200% markup AND >1.5 std deviations")
            if contract_type == "STANDARD":
                confidence_factors.append(90)
                reasoning.append("→ Standard services should not exceed 200% without justification")
        elif baseline['markup'] > 150 and baseline['z_score'] > 1.0:
            confidence_factors.append(70)
            reasoning.append("→ ELEVATED: >150% markup, warrants review")
        
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
            reasoning.append(f"Vendor won {vendor_count} contracts ({concentration:.0f}% concentration)")
            legal_violations.append("Procurement Integrity Act - Competition Concerns")
            confidence_factors.append(75)
        
        # Calculate final confidence
        confidence = int(sum(confidence_factors) / len(confidence_factors)) if confidence_factors else 0
        
        # Determine tier
        if confidence >= 90 and len(legal_violations) >= 2:
            tier = "🔴 RED"
        elif confidence >= 85 and len(legal_violations) >= 1:
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
        print("SUNLIGHT FRAUD ANALYSIS V2 - SMART BASELINES")
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
        green = [a for a in assessments if '🟢' in a.tier]
        
        print(f"\nTIER SUMMARY:")
        print(f"  🔴 RED (High Confidence): {len(red)}")
        print(f"  🟡 YELLOW (Medium): {len(yellow)}")
        print(f"  🟢 GREEN (Normal/Need Data): {len(green)}")
        print()
        
        if red:
            print("="*70)
            print("🔴 RED TIER: HIGH CONFIDENCE FRAUD INDICATORS")
            print("="*70)
            for i, a in enumerate(red, 1):
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f}")
                print(f"   Confidence: {a.confidence}%")
                for r in a.reasoning:
                    print(f"   • {r}")
                if a.legal_violations:
                    print(f"   VIOLATIONS:")
                    for v in a.legal_violations:
                        print(f"   ⚖️  {v}")
                print("-"*70)
        
        if yellow:
            print("\n🟡 YELLOW TIER: MEDIUM CONFIDENCE")
            print("="*70)
            for i, a in enumerate(yellow, 1):
                print(f"{i}. {a.vendor_name} - ${a.amount:,.0f} (Confidence: {a.confidence}%)")
        
        print(f"\n✅ Analysis complete: {len(red)} high-confidence cases")
        print("="*70)

if __name__ == "__main__":
    engine = FraudReasoningV2()
    engine.generate_report()
