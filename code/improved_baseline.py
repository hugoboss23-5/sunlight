import sqlite3
import statistics
from typing import Dict, List

class ImprovedBaseline:
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def calculate_smart_baseline(self, target_contract: Dict) -> Dict:
        """Calculate baseline using similar contracts only"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get all contracts from same agency
        c.execute("""
            SELECT award_amount, description 
            FROM contracts 
            WHERE agency_name = ? AND award_amount > 0
        """, (target_contract['agency'],))
        
        all_contracts = [(row[0], row[1]) for row in c.fetchall()]
        conn.close()
        
        # Categorize target contract
        target_size = self.categorize_size(target_contract['amount'])
        target_type = self.categorize_type(target_contract.get('desc', ''))
        
        # Find similar contracts (same size category)
        similar_contracts = []
        for amount, desc in all_contracts:
            if self.categorize_size(amount) == target_size:
                similar_contracts.append(amount)
        
        if len(similar_contracts) < 5:
            # Not enough similar - use broader size range
            for amount, desc in all_contracts:
                size_cat = self.categorize_size(amount)
                # Allow one category above/below
                if abs(self.size_to_number(size_cat) - self.size_to_number(target_size)) <= 1:
                    similar_contracts.append(amount)
        
        if len(similar_contracts) < 3:
            return {
                'valid': False,
                'reason': 'Insufficient similar contracts for comparison',
                'sample_size': len(similar_contracts)
            }
        
        # Calculate statistics
        median = statistics.median(similar_contracts)
        mean = statistics.mean(similar_contracts)
        stdev = statistics.stdev(similar_contracts) if len(similar_contracts) > 1 else 0
        
        # Calculate z-score
        z_score = (target_contract['amount'] - mean) / stdev if stdev > 0 else 0
        
        # Calculate markup percentage
        markup = ((target_contract['amount'] - median) / median) * 100
        
        return {
            'valid': True,
            'baseline_median': median,
            'baseline_mean': mean,
            'baseline_stdev': stdev,
            'z_score': z_score,
            'markup_pct': markup,
            'sample_size': len(similar_contracts),
            'target_size_category': target_size,
            'comparison_method': 'same_size_category'
        }
    
    def categorize_size(self, amount: float) -> str:
        """Categorize contract by dollar amount"""
        if amount < 100000:
            return "MICRO"  # <$100K
        elif amount < 1000000:
            return "SMALL"  # $100K-$1M
        elif amount < 5000000:
            return "MEDIUM"  # $1M-$5M
        elif amount < 25000000:
            return "LARGE"  # $5M-$25M
        else:
            return "MEGA"  # >$25M
    
    def size_to_number(self, size: str) -> int:
        """Convert size category to number for comparison"""
        mapping = {"MICRO": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3, "MEGA": 4}
        return mapping.get(size, 2)
    
    def categorize_type(self, description: str) -> str:
        """Categorize contract by type"""
        desc = description.lower() if description else ""
        
        # Contract type keywords
        if any(kw in desc for kw in ['aircraft', 'aviation', 'aerospace', 'flight']):
            return "AEROSPACE"
        elif any(kw in desc for kw in ['it ', 'software', 'computer', 'data', 'cyber']):
            return "IT_SERVICES"
        elif any(kw in desc for kw in ['maintenance', 'repair', 'support']):
            return "MAINTENANCE"
        elif any(kw in desc for kw in ['research', 'development', 'r&d', 'prototype']):
            return "RD"
        elif any(kw in desc for kw in ['construction', 'building', 'facility']):
            return "CONSTRUCTION"
        else:
            return "OTHER"
    
    def test_all_high_value(self):
        """Test improved baseline on high-value contracts"""
        print("IMPROVED BASELINE ANALYSIS")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT contract_id, award_amount, vendor_name, agency_name, description
            FROM contracts
            WHERE award_amount > 10000000
            ORDER BY award_amount DESC
        """)
        
        for row in c.fetchall():
            contract = {
                'id': row[0],
                'amount': row[1],
                'vendor': row[2],
                'agency': row[3],
                'desc': row[4]
            }
            
            result = self.calculate_smart_baseline(contract)
            
            print(f"\n{contract['vendor']} - ${contract['amount']:,.0f}")
            print(f"Size Category: {self.categorize_size(contract['amount'])}")
            print(f"Type: {self.categorize_type(contract.get('desc', ''))}")
            
            if result['valid']:
                print(f"Smart Baseline: ${result['baseline_median']:,.0f} (n={result['sample_size']})")
                print(f"Z-Score: {result['z_score']:.2f}")
                print(f"Markup: {result['markup_pct']:.0f}%")
                
                if result['markup_pct'] > 300:
                    print("🚨 EXTREME OUTLIER (>300% markup)")
                elif result['markup_pct'] > 200:
                    print("🚩 SUSPICIOUS (>200% markup)")
                elif result['markup_pct'] > 100:
                    print("⚠️  HIGH (>100% markup)")
                else:
                    print("✅ WITHIN NORMAL RANGE")
            else:
                print(f"⚠️  {result['reason']}")
            
            print("-"*70)
        
        conn.close()

if __name__ == "__main__":
    baseline = ImprovedBaseline()
    baseline.test_all_high_value()
