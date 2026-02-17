"""
SUNLIGHT Master Fraud Detection Engine
Combines all detection layers with transparent reasoning
"""
import sqlite3
import statistics
from typing import Dict, List
from dataclasses import dataclass, asdict
import json

@dataclass
class FraudAssessment:
    contract_id: str
    vendor_name: str
    amount: float
    agency: str
    confidence: int
    tier: str
    reasoning: List[str]
    legal_violations: List[str]
    evidence: Dict
    has_political_donations: bool
    donation_amount: float
    
    def to_json(self):
        return asdict(self)

class SunlightMasterAnalyzer:
    """
    Master fraud detection engine combining:
    - Price analysis (statistical comparison)
    - Political donations (quid pro quo indicators)
    - Legal framework (DOJ prosecution standards)
    - Pattern analysis (vendor concentration)
    """
    
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
        self.load_legal_framework()
    
    def load_legal_framework(self):
        """Load DOJ prosecution thresholds"""
        try:
            with open('knowledge_base/legal_framework/prosecuted_cases.json', 'r') as f:
                data = json.load(f)
                self.price_thresholds = data['patterns']['price_thresholds']
        except:
            # Default thresholds if file not found
            self.price_thresholds = {
                'high_risk': 300,
                'medium_risk': 200,
                'investigation_worthy': 150
            }
    
    def categorize_size(self, amount: float) -> str:
        """Categorize contract by dollar size"""
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
    
    def categorize_type(self, description: str) -> tuple:
        """Categorize contract type and determine markup tolerance"""
        desc = (description or "").lower()
        
        # R&D / Specialized (high tolerance)
        if any(kw in desc for kw in ['research', 'development', 'r&d', 'prototype', 'experimental']):
            return ("R&D", "HIGH_TOLERANCE")
        elif any(kw in desc for kw in ['custom', 'specialized', 'unique', 'classified']):
            return ("SPECIALIZED", "HIGH_TOLERANCE")
        
        # Standard items (strict scrutiny)
        elif any(kw in desc for kw in ['it ', 'software', 'computer', 'technology', 'information']):
            return ("STANDARD_IT", "STRICT")
        elif any(kw in desc for kw in ['maintenance', 'repair', 'support', 'service']):
            return ("STANDARD_SERVICE", "STRICT")
        elif any(kw in desc for kw in ['supplies', 'equipment', 'parts', 'materials']):
            return ("STANDARD_GOODS", "STRICT")
        
        # Aerospace (medium tolerance)
        elif any(kw in desc for kw in ['aircraft', 'aviation', 'aerospace', 'flight']):
            return ("AEROSPACE", "MEDIUM_TOLERANCE")
        
        return ("UNKNOWN", "MEDIUM_TOLERANCE")
    
    def calculate_baseline(self, contract: Dict) -> Dict:
        """Calculate statistical baseline using comparable contracts"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        target_size = self.categorize_size(contract['amount'])
        
        # Get all contracts from same agency
        c.execute("""SELECT award_amount FROM contracts 
                    WHERE agency_name = ? AND award_amount > 0""", 
                 (contract['agency'],))
        amounts = [row[0] for row in c.fetchall()]
        conn.close()
        
        # Filter to similar size
        similar = [a for a in amounts if self.categorize_size(a) == target_size]
        
        # Expand if too few
        if len(similar) < 3:
            size_map = {"MICRO": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3, "MEGA": 4}
            target_val = size_map[target_size]
            similar = [a for a in amounts 
                      if abs(size_map[self.categorize_size(a)] - target_val) <= 1]
        
        if len(similar) < 3:
            return {'valid': False, 'reason': 'Insufficient comparable contracts'}
        
        median = statistics.median(similar)
        mean = statistics.mean(similar)
        stdev = statistics.stdev(similar) if len(similar) > 1 else 0
        
        z_score = (contract['amount'] - mean) / stdev if stdev > 0 else 0
        markup = ((contract['amount'] - median) / median) * 100
        
        return {
            'valid': True,
            'median': median,
            'mean': mean,
            'stdev': stdev,
            'z_score': z_score,
            'markup_pct': markup,
            'sample_size': len(similar),
            'size_category': target_size
        }
    
    def check_political_donations(self, vendor_name: str) -> Dict:
        """Check if vendor has political donations"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""SELECT SUM(amount), COUNT(*), GROUP_CONCAT(recipient_name, ', ')
                        FROM political_donations 
                        WHERE vendor_name = ?""", (vendor_name,))
            row = c.fetchone()
            
            if row and row[0]:
                return {
                    'has_donations': True,
                    'total_amount': row[0],
                    'recipient_count': row[1],
                    'recipients': row[2]
                }
        except:
            pass
        finally:
            conn.close()
        
        return {'has_donations': False, 'total_amount': 0}
    
    def check_vendor_pattern(self, vendor_name: str) -> Dict:
        """Check for vendor concentration patterns"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*), SUM(award_amount) FROM contracts WHERE vendor_name = ?", 
                 (vendor_name,))
        vendor_stats = c.fetchone()
        
        c.execute("SELECT COUNT(*) FROM contracts")
        total_contracts = c.fetchone()[0]
        
        conn.close()
        
        count = vendor_stats[0]
        total_value = vendor_stats[1] or 0
        concentration = (count / total_contracts * 100) if total_contracts > 0 else 0
        
        return {
            'contract_count': count,
            'total_value': total_value,
            'concentration_pct': concentration,
            'is_concentrated': concentration > 20  # >20% is suspicious
        }
    
    def analyze_contract(self, contract: Dict) -> FraudAssessment:
        """Complete fraud analysis with transparent reasoning"""
        
        reasoning = []
        legal_violations = []
        confidence_factors = []
        
        # BASELINE ANALYSIS
        baseline = self.calculate_baseline(contract)
        
        if not baseline['valid']:
            return FraudAssessment(
                contract_id=contract['id'],
                vendor_name=contract['vendor'],
                amount=contract['amount'],
                agency=contract['agency'],
                confidence=0,
                tier="🟢 GREEN",
                reasoning=[baseline['reason']],
                legal_violations=[],
                evidence={},
                has_political_donations=False,
                donation_amount=0
            )
        
        # CONTRACT TYPE
        contract_type, tolerance = self.categorize_type(contract.get('desc', ''))
        
        reasoning.append(f"Contract: ${contract['amount']:,.0f}")
        reasoning.append(f"Baseline: ${baseline['median']:,.0f} (n={baseline['sample_size']}, {baseline['size_category']})")
        reasoning.append(f"Markup: {baseline['markup_pct']:.0f}% | Z-score: {baseline['z_score']:.2f}")
        reasoning.append(f"Type: {contract_type} ({tolerance})")
        
        # PRICE FRAUD DETECTION
        markup = baseline['markup_pct']
        
        if tolerance == "STRICT":
            if markup > 300:
                confidence_factors.append(90)
                legal_violations.append("False Claims Act § 3729 - Extreme Price Inflation")
                reasoning.append("🚨 EXTREME: >300% markup on standard item (DOJ high-risk)")
            elif markup > 200:
                confidence_factors.append(80)
                legal_violations.append("False Claims Act § 3729 - Price Inflation")
                reasoning.append("🚩 HIGH: >200% markup on standard item (DOJ medium-risk)")
            elif markup > 150:
                confidence_factors.append(70)
                reasoning.append("⚠️  ELEVATED: >150% markup (investigation-worthy)")
        
        elif tolerance == "MEDIUM_TOLERANCE":
            if markup > 400:
                confidence_factors.append(85)
                legal_violations.append("False Claims Act § 3729 - Extreme Price Inflation")
                reasoning.append("🚨 EXTREME: >400% markup (unusual even for aerospace)")
            elif markup > 250:
                confidence_factors.append(75)
                reasoning.append("🚩 HIGH: >250% markup")
        
        # HIGH_TOLERANCE (R&D) - more lenient
        else:
            if markup > 500:
                confidence_factors.append(75)
                reasoning.append("🚩 HIGH: >500% markup (high even for R&D)")
        
        # POLITICAL DONATIONS
        donations = self.check_political_donations(contract['vendor'])
        
        if donations['has_donations']:
            reasoning.append(f"💰 Political Donations: ${donations['total_amount']:,.0f}")
            if donations.get('recipients'):
                reasoning.append(f"   Recipients: {donations['recipients'][:100]}")
            
            # Donations + price inflation = major red flag
            if len(confidence_factors) > 0:
                legal_violations.append("Anti-Kickback Act § 8702 - Quid Pro Quo Indicator")
                confidence_factors.append(85)
                reasoning.append("→ Price inflation + political donations = quid pro quo pattern")
        
        # VENDOR CONCENTRATION
        pattern = self.check_vendor_pattern(contract['vendor'])
        
        if pattern['is_concentrated']:
            reasoning.append(f"📊 Concentration: {pattern['contract_count']} contracts ({pattern['concentration_pct']:.0f}%)")
            legal_violations.append("Procurement Integrity Act § 2105 - Competition Concerns")
            confidence_factors.append(70)
        
        # CALCULATE FINAL CONFIDENCE
        final_confidence = int(sum(confidence_factors) / len(confidence_factors)) if confidence_factors else 0
        
        # TIER ASSIGNMENT (Conservative)
        if final_confidence >= 85 and len(legal_violations) >= 2:
            tier = "🔴 RED"
        elif final_confidence >= 80 and donations['has_donations']:
            tier = "🔴 RED"  # Donations + high price = RED
        elif final_confidence >= 70:
            tier = "🟡 YELLOW"
        else:
            tier = "🟢 GREEN"
        
        return FraudAssessment(
            contract_id=contract['id'],
            vendor_name=contract['vendor'],
            amount=contract['amount'],
            agency=contract['agency'],
            confidence=final_confidence,
            tier=tier,
            reasoning=reasoning,
            legal_violations=legal_violations,
            evidence=baseline,
            has_political_donations=donations['has_donations'],
            donation_amount=donations['total_amount']
        )
    
    def analyze_all(self, min_amount: float = 5000000):
        """Analyze all contracts above threshold"""
        print("="*70)
        print("SUNLIGHT MASTER FRAUD ANALYZER")
        print("="*70)
        print(f"Analyzing contracts >${min_amount/1000000:.0f}M")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT contract_id, award_amount, vendor_name, agency_name, description
            FROM contracts
            WHERE award_amount > ?
            ORDER BY award_amount DESC
        """, (min_amount,))
        
        assessments = []
        for row in c.fetchall():
            contract = {
                'id': row[0],
                'amount': row[1],
                'vendor': row[2],
                'agency': row[3],
                'desc': row[4]
            }
            assessment = self.analyze_contract(contract)
            assessments.append(assessment)
        
        conn.close()
        
        # Categorize
        red = [a for a in assessments if '🔴' in a.tier]
        yellow = [a for a in assessments if '🟡' in a.tier]
        green = [a for a in assessments if '🟢' in a.tier]
        
        print(f"\nRESULTS:")
        print(f"  🔴 RED (High Confidence): {len(red)}")
        print(f"  🟡 YELLOW (Investigation-Worthy): {len(yellow)}")
        print(f"  🟢 GREEN (Normal/Insufficient Data): {len(green)}")
        print()
        
        # RED TIER REPORT
        if red:
            print("🔴 RED TIER - HIGH CONFIDENCE FRAUD INDICATORS")
            print("="*70)
            for i, a in enumerate(red, 1):
                self.print_assessment(a, i)
        else:
            print("🔴 RED: None (conservative thresholds - need more evidence layers)")
        
        # YELLOW TIER REPORT
        if yellow:
            print("\n🟡 YELLOW TIER - INVESTIGATION-WORTHY")
            print("="*70)
            for i, a in enumerate(yellow[:10], 1):
                self.print_assessment(a, i, brief=True)
        
        print(f"\n✅ Analysis complete: {len(red)} RED + {len(yellow)} YELLOW cases")
        print("="*70)
        
        return assessments
    
    def print_assessment(self, assessment: FraudAssessment, index: int, brief: bool = False):
        """Print fraud assessment"""
        print(f"\n{index}. {assessment.vendor_name} - ${assessment.amount:,.0f}")
        print(f"   Agency: {assessment.agency}")
        print(f"   Confidence: {assessment.confidence}%")
        
        if assessment.has_political_donations:
            print(f"   💰 Political Donations: ${assessment.donation_amount:,.0f}")
        
        if not brief:
            print(f"\n   REASONING:")
            for r in assessment.reasoning:
                print(f"   {r}")
            
            if assessment.legal_violations:
                print(f"\n   LEGAL VIOLATIONS:")
                for v in assessment.legal_violations:
                    print(f"   ⚖️  {v}")
        else:
            for r in assessment.reasoning[:3]:
                print(f"   {r}")
        
        print("-"*70)
    
    def export_json(self, assessments: List[FraudAssessment], filename: str = "fraud_analysis.json"):
        """Export analysis to JSON"""
        data = {
            'analysis_date': '2026-01-21',
            'total_analyzed': len(assessments),
            'methodology': 'Multi-layer fraud detection (price, donations, patterns)',
            'results': [a.to_json() for a in assessments]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n📄 Exported to {filename}")

if __name__ == "__main__":
    analyzer = SunlightMasterAnalyzer()
    results = analyzer.analyze_all(min_amount=5000000)
    analyzer.export_json(results)
