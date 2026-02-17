"""
Statistical Rigor Enhancements
- Bootstrap confidence intervals
- FDR correction (Benjamini-Hochberg)
- Log-transform for non-normal data
- Proper sample size requirements
"""
import sqlite3
import numpy as np
from typing import Dict, List, Tuple
from scipy import stats

class StatisticalRigorV2:
    """Enhanced statistical methods addressing critique"""
    
    def __init__(self, db_path: str = "../data/sunlight.db"):
        self.db_path = db_path
        self.min_sample_size = 10  # Increased from 3
    
    def bootstrap_confidence_interval(
        self, 
        data: List[float], 
        target: float,
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Bootstrap CI for markup percentile
        Addresses: "With n=6, your 95% CI could span 100+ percentage points"
        """
        if len(data) < 3:
            return {'valid': False, 'reason': 'Insufficient data for bootstrap'}
        
        # Bootstrap resampling
        percentiles = []
        for _ in range(n_bootstrap):
            resample = np.random.choice(data, size=len(data), replace=True)
            # Calculate where target falls in resampled distribution
            percentile = stats.percentileofscore(resample, target)
            percentiles.append(percentile)
        
        # Calculate confidence interval
        alpha = 1 - confidence_level
        lower = np.percentile(percentiles, alpha/2 * 100)
        upper = np.percentile(percentiles, (1 - alpha/2) * 100)
        median_percentile = np.median(percentiles)
        
        return {
            'valid': True,
            'percentile_estimate': median_percentile,
            'ci_lower': lower,
            'ci_upper': upper,
            'confidence_level': confidence_level,
            'interpretation': f"Target is {median_percentile:.1f}th percentile (95% CI: [{lower:.1f}, {upper:.1f}])"
        }
    
    def fdr_correction(self, p_values: List[float], alpha: float = 0.10) -> List[bool]:
        """
        Benjamini-Hochberg FDR correction
        Addresses: "Testing 1,077 contracts... need FDR control"
        """
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_p_values = np.array(p_values)[sorted_indices]
        
        # BH critical values
        bh_critical_values = (np.arange(1, n + 1) / n) * alpha
        
        # Find largest i where p_(i) <= (i/n)*alpha
        significant = sorted_p_values <= bh_critical_values
        if not significant.any():
            return [False] * n
        
        threshold_index = np.where(significant)[0][-1]
        
        # Mark all p-values up to threshold as significant
        reject = np.zeros(n, dtype=bool)
        reject[sorted_indices[:threshold_index + 1]] = True
        
        return reject.tolist()
    
    def log_transform_comparison(self, data: List[float], target: float) -> Dict:
        """
        Log-transform prices before calculating z-scores
        Addresses: "Contract prices follow heavy-tailed distributions"
        """
        if len(data) < self.min_sample_size:
            return {'valid': False}
        
        # Log transform (add 1 to handle zeros)
        log_data = np.log1p(data)
        log_target = np.log1p(target)
        
        # Calculate stats on log scale
        mean_log = np.mean(log_data)
        std_log = np.std(log_data, ddof=1)
        z_score_log = (log_target - mean_log) / std_log if std_log > 0 else 0
        
        # Test for normality
        shapiro_stat, shapiro_p = stats.shapiro(log_data)
        
        return {
            'valid': True,
            'z_score_log': z_score_log,
            'is_normal': shapiro_p > 0.05,
            'shapiro_p_value': shapiro_p,
            'interpretation': f"Log-transformed z-score: {z_score_log:.2f}"
        }
    
    def logarithmic_binning(self, amount: float) -> str:
        """
        Finer-grained size categories for MEGA contracts
        Addresses: "$26M comparable to $500M? No."
        """
        if amount < 100000:
            return "MICRO"
        elif amount < 1000000:
            return "SMALL"
        elif amount < 5000000:
            return "MEDIUM"
        elif amount < 25000000:
            return "LARGE"
        elif amount < 50000000:
            return "MEGA-1"  # $25-50M
        elif amount < 100000000:
            return "MEGA-2"  # $50-100M
        else:
            return "MEGA-3"  # >$100M
    
    def calculate_base_rate_adjusted_probability(
        self,
        statistical_confidence: float,
        sensitivity: float = 0.70,
        specificity: float = 0.98,
        base_rate: float = 0.02
    ) -> Dict:
        """
        Bayesian adjustment for base rate
        Addresses: "Base rate neglect - even 99% accurate detector yields 50% FP"
        """
        # Bayes theorem
        # P(Fraud|Positive) = P(Positive|Fraud)*P(Fraud) / P(Positive)
        
        true_positive_rate = sensitivity
        false_positive_rate = 1 - specificity
        
        p_positive = (true_positive_rate * base_rate) + (false_positive_rate * (1 - base_rate))
        p_fraud_given_positive = (true_positive_rate * base_rate) / p_positive
        
        return {
            'posterior_probability': p_fraud_given_positive,
            'base_rate': base_rate,
            'sensitivity': sensitivity,
            'specificity': specificity,
            'interpretation': f"Given base rate {base_rate*100}%, actual fraud probability: {p_fraud_given_positive*100:.1f}%"
        }

if __name__ == "__main__":
    rigor = StatisticalRigorV2()
    
    # Test with Technica case
    comparison_data = [19011210, 28286423, 36888881, 40840821, 44473290, 58845137]
    target = 113655241
    
    print("STATISTICAL RIGOR V2 ANALYSIS")
    print("="*60)
    
    # Bootstrap CI
    bootstrap = rigor.bootstrap_confidence_interval(comparison_data, target)
    if bootstrap['valid']:
        print("\nBOOTSTRAP CONFIDENCE INTERVAL:")
        print(f"  {bootstrap['interpretation']}")
    
    # Log-transform
    log_result = rigor.log_transform_comparison(comparison_data, target)
    if log_result['valid']:
        print("\nLOG-TRANSFORMED ANALYSIS:")
        print(f"  {log_result['interpretation']}")
        print(f"  Data is normal after log-transform: {log_result['is_normal']}")
    
    # Base rate adjustment
    bayesian = rigor.calculate_base_rate_adjusted_probability(
        statistical_confidence=0.70,
        base_rate=0.02
    )
    print("\nBASE RATE ADJUSTED PROBABILITY:")
    print(f"  {bayesian['interpretation']}")
    
    # New binning
    print("\nIMPROVED SIZE BINNING:")
    print(f"  ${target:,.0f} → {rigor.logarithmic_binning(target)}")
