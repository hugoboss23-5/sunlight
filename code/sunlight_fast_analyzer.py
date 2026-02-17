import sqlite3
import json
from datetime import datetime
import numpy as np

class FastSunlightAnalyzer:
    """Optimized analyzer for 42K+ contracts - uses batch processing"""
    
    def __init__(self, db_path: str = "data/sunlight.db"):
        self.db_path = db_path
    
    def analyze_all(self, min_amount: int = 5000000):
        print("="*70)
        print("SUNLIGHT FAST ANALYZER - Optimized for 42K+ Contracts")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        print(f"Loading contracts >${min_amount/1000000:.0f}M...")
        c.execute("""SELECT contract_id, award_amount, vendor_name, agency_name, 
                            description, start_date
                     FROM contracts 
                     WHERE award_amount >= ?
                     ORDER BY award_amount DESC""", (min_amount,))
        
        all_contracts = c.fetchall()
        total = len(all_contracts)
        print(f"Loaded {total:,} contracts\n")
        
        print("Calculating agency baselines...")
        agency_baselines = {}
        c.execute("SELECT DISTINCT agency_name FROM contracts WHERE award_amount >= ?", (min_amount,))
        agencies = [row[0] for row in c.fetchall()]
        
        for agency in agencies:
            c.execute("""SELECT award_amount FROM contracts 
                        WHERE agency_name = ? AND award_amount >= ?""", 
                     (agency, min_amount))
            amounts = [row[0] for row in c.fetchall() if row[0] and row[0] > 0]
            if amounts:
                agency_baselines[agency] = {
                    'median': np.median(amounts),
                    'mean': np.mean(amounts),
                    'std': np.std(amounts),
                    'count': len(amounts)
                }
        
        print(f"Calculated baselines for {len(agency_baselines)} agencies\n")
        
        red_flags = []
        yellow_flags = []
        green = []
        
        print("Analyzing contracts...")
        for i, contract in enumerate(all_contracts):
            contract_id, amount, vendor, agency, desc, date = contract
            
            if (i + 1) % 1000 == 0:
                print(f"Progress: {i+1:,}/{total:,} ({(i+1)/total*100:.1f}%) | RED: {len(red_flags):,} | YELLOW: {len(yellow_flags):,}")
            
            baseline = agency_baselines.get(agency)
            if not baseline or baseline['count'] < 10:
                continue
            
            median_amount = baseline['median']
            if median_amount <= 0:
                continue
                
            markup_pct = ((amount - median_amount) / median_amount) * 100
            
            percentile = 0
            if baseline['std'] > 0:
                z_score = (amount - baseline['mean']) / baseline['std']
                if z_score > 3:
                    percentile = 99.9
                elif z_score > 2:
                    percentile = 97.7
                elif z_score > 1:
                    percentile = 84.1
                else:
                    percentile = 50
            
            result = {
                'contract_id': contract_id,
                'amount': amount,
                'vendor': vendor,
                'agency': agency,
                'date': date,
                'markup_pct': round(markup_pct, 1),
                'percentile': round(percentile, 1),
                'baseline_median': median_amount,
                'baseline_count': baseline['count']
            }
            
            if markup_pct > 300 and percentile > 95:
                result['tier'] = 'RED'
                result['reasoning'] = f"Markup: {markup_pct:.0f}% (>{baseline['count']} comparables) | {percentile:.0f}th percentile"
                red_flags.append(result)
            elif markup_pct > 75 and percentile > 90:
                result['tier'] = 'YELLOW'
                result['reasoning'] = f"Markup: {markup_pct:.0f}% | {percentile:.0f}th percentile"
                yellow_flags.append(result)
            else:
                result['tier'] = 'GREEN'
                green.append(result)
        
        conn.close()
        
        print(f"\n{'='*70}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*70}")
        print(f"Total analyzed: {total:,}")
        print(f"RED flags: {len(red_flags):,} ({len(red_flags)/total*100:.1f}%)")
        print(f"YELLOW flags: {len(yellow_flags):,} ({len(yellow_flags)/total*100:.1f}%)")
        print(f"GREEN: {len(green):,} ({len(green)/total*100:.1f}%)")
        print(f"{'='*70}\n")
        
        output = {
            'analysis_date': datetime.now().isoformat(),
            'total_contracts': total,
            'red_count': len(red_flags),
            'yellow_count': len(yellow_flags),
            'green_count': len(green),
            'red_flags': red_flags[:200],
            'yellow_flags': yellow_flags[:500]
        }
        
        with open('fast_analysis_results.json', 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Results saved to: fast_analysis_results.json")
        
        if red_flags:
            print(f"\nTOP 10 RED FLAGS:")
            print(f"{'='*70}")
            for i, flag in enumerate(red_flags[:10], 1):
                print(f"{i}. {flag['contract_id']}")
                print(f"   Amount: ${flag['amount']/1000000:.1f}M")
                print(f"   Vendor: {flag['vendor'][:50]}")
                print(f"   {flag['reasoning']}")
                print()
        
        return output

if __name__ == "__main__":
    analyzer = FastSunlightAnalyzer("data/sunlight.db")
    results = analyzer.analyze_all(min_amount=5000000)
