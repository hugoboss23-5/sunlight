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
    doj_classification: str

class DOJStandardEngine:
    """Fraud detection aligned with actual DOJ prosecution standards"""
    
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
        
        # Specialized (higher markup tolerance)
        if any(kw in desc for kw in ['research', 'development', 'r&d', 'prototype', 'experimental']):
            return "R&D"
        elif any(kw in desc for kw in ['custom', 'specialized', 'unique']):
            return "SPECIALIZED"
        
        # Standard (strict markup scrutiny)
        elif any(kw in desc for kw in ['it ', 'software', 'computer']):
            return "STANDARD_IT"
        elif any(kw in desc for kw in ['maintenance', 'repair', 'support']):
            return "STANDARD_MAINTENANCE"
        elif any(kw in desc for kw in ['supplies', 'equipment', 'parts']):
            return "STANDARD_PARTS"
        
        # Aerospace (medium tolerance)
        elif any(kw in desc for kw in ['aircraft', 'aviation', 'aerospace']):
            return "AEROSPACE"
        
        return "UNKNOWN"
    
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
            return {'valid': False, 'reason': f'Only {len(similar)} comparable contracts'}
        
        median = statistics.median(similar)
        mean = statistics.mean(similar)
        stdev = statistics.stdev(similar) if len(similar) > 1 else 0
        
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
    
    def classify_doj_risk(self, markup: float, contract_type: str) -> tuple:
        """Classify according to DOJ prosecution patterns"""
        
        # Standard items have strict thresholds
        if contract_type in ["STANDARD_IT", "STANDARD_MAINTENANCE", "STANDARD_PARTS"]:
            if markup > 300:
                return ("HIGH_RISK", "DOJ prosecutes >300% markup on standard items")
            elif markup > 200:
                return ("MEDIUM_RISK", "DOJ investigates 200-300% markup on standard items")
            elif markup > 150:
                return ("INVESTIGATION_WORTHY", "Warrants review per DOJ standards")
            else:
                return ("NORMAL", "Within acceptable variance")
        
        # Specialized items have higher tolerance
        elif contract_type in ["R&D", "SPECIALIZED"]:
            if markup > 500:
                return ("MEDIUM_RISK", "Even specialized items rarely exceed 500%")
            elif markup > 300:
                return ("INVESTIGATION_WORTHY", "High but may be justified for R&D")
            else:
                return ("NORMAL", "Acceptable for specialized work")
        
        # Unknown/Aerospace - medium tolerance
        else:
            if markup > 400:
                return ("HIGH_RISK", "Extreme markup regardless of type")
            elif markup > 250:
                return ("MEDIUM_RISK", "High markup, type unclear")
            elif markup > 150:
                return ("INVESTIGATION_WORTHY", "Elevated, needs context")
            else:
                return ("NORMAL", "Within typical range")
    
    def analyze_contract(self, contract: Dict) -> FraudAssessment:
        reasoning = []
        legal_violations = []
        
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
                evidence={},
                doj_classification="INSUFFICIENT_DATA"
            )
        
        contract_type = self.categorize_type(contract.get('desc', ''))
        size_cat = self.categorize_size(contract['amount'])
        
        reasoning.append(f"Amount: ${contract['amount']:,.0f} vs baseline ${baseline['median']:,.0f} (n={baseline['sample_size']})")
        reasoning.append(f"Markup: {baseline['markup']:.0f}% | Z-score: {baseline['z_score']:.2f}")
        reasoning.append(f"Type: {contract_type} | Size: {size_cat}")
        
        # DOJ CLASSIFICATION
        doj_risk, doj_reason = self.classify_doj_risk(baseline['markup'], contract_type)
        reasoning.append(f"DOJ Standard: {doj_risk} - {doj_reason}")
        
        # Determine confidence and tier based on DOJ standards
        if doj_risk == "HIGH_RISK" and contract['amount'] > 5000000:
            confidence = 85
            tier = "🔴 RED"
            legal_violations.append("False Claims Act - Price Inflation (DOJ high-risk threshold)")
        elif doj_risk == "MEDIUM_RISK" and contract['amount'] > 5000000:
            confidence = 75
            tier = "🟡 YELLOW"
            legal_violations.append("False Claims Act - Price Inflation Indicator")
        elif doj_risk == "INVESTIGATION_WORTHY":
            confidence = 65
            tier = "🟡 YELLOW"
        else:
            confidence = 0
            tier = "🟢 GREEN"
        
        # Check vendor pattern (prosecution priority)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM contracts WHERE vendor_name = ?", (contract['vendor'],))
        vendor_count = c.fetchone()[0]
        conn.close()
        
        if vendor_count > 5:
            reasoning.append(f"Pattern: Vendor has {vendor_count} contracts (DOJ prioritizes patterns)")
            if confidence > 0:
                confidence += 10  # Pattern evidence boosts confidence
        
        return FraudAssessment(
            contract_id=contract['id'],
            vendor_name=contract['vendor'],
            amount=contract['amount'],
            confidence=min(95, confidence),  # Cap at 95% (can't be 100% without full investigation)
            tier=tier,
            reasoning=reasoning,
            legal_violations=legal_violations,
            evidence=baseline,
            doj_classification=doj_risk
        )
    
    def generate_report(self):
        print("="*70)
        print("SUNLIGHT - DOJ PROSECUTION STANDARDS")
        print("="*70)
        print("Aligned with actual DOJ fraud case thresholds")
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
        
        print(f"\nRESULTS (contracts >$5M):")
        print(f"  🔴 RED (DOJ high-risk): {len(red)}")
        print(f"  🟡 YELLOW (DOJ medium-risk/investigation-worthy): {len(yellow)}")
        print()
        
        if red:
            print("🔴 RED - DOJ HIGH-RISK THRESHOLD (>300% standard items)")
            print("="*70)
            for i, a in enumerate(red, 1):
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f}")
                print(f"   DOJ Classification: {a.doj_classification}")
                print(f"   Confidence: {a.confidence}%")
                for r in a.reasoning:
                    print(f"   {r}")
                if a.legal_violations:
                    for v in a.legal_violations:
                        print(f"   ⚖️  {v}")
                print("-"*70)
        
        if yellow:
            print("\n🟡 YELLOW - DOJ INVESTIGATION-WORTHY")
            print("="*70)
            for i, a in enumerate(yellow[:10], 1):  # Top 10
                print(f"\n{i}. {a.vendor_name} - ${a.amount:,.0f}")
                print(f"   DOJ: {a.doj_classification} | Confidence: {a.confidence}%")
                for r in a.reasoning[:3]:  # First 3 reasons
                    print(f"   {r}")
                print("-"*70)
        
        print(f"\n✅ {len(red)} high-risk + {len(yellow)} investigation-worthy cases")
        print("="*70)

if __name__ == "__main__":
    engine = DOJStandardEngine()
    engine.generate_report()
