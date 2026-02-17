"""
Enhanced Legal Framework - Post-Escobar Compliant
Addresses materiality, scienter, and affirmative defenses
"""
import sqlite3
from typing import Dict, List

class LegalFrameworkV2:
    """
    Post-Escobar FCA compliance:
    - Materiality: Did fraud affect government decision?
    - Scienter: Evidence of intent
    - Affirmative defenses: Legitimate sole-source, urgency, etc.
    """
    
    def __init__(self, db_path: str = "../data/sunlight.db"):
        self.db_path = db_path
    
    def assess_materiality(self, contract: Dict) -> Dict:
        """
        Materiality indicators (post-Escobar):
        - Government complained post-performance
        - Requested refunds
        - Terminated for default
        - Filed disputes
        """
        
        # TODO: Need government complaint/dispute data
        # For now, use proxy indicators
        
        materiality_score = 0
        evidence = []
        
        # Proxy 1: Extremely high markup suggests material impact
        if contract.get('markup_pct', 0) > 400:
            materiality_score += 30
            evidence.append("Extreme price deviation (>400%) likely material to payment decision")
        
        # Proxy 2: Pattern across multiple contracts
        vendor_contracts = self.get_vendor_contract_count(contract['vendor'])
        if vendor_contracts > 5:
            materiality_score += 20
            evidence.append(f"Pattern across {vendor_contracts} contracts suggests systematic issue")
        
        # TODO: Add when data available:
        # - Government performance complaints
        # - Contract terminations
        # - Refund requests
        # - Dispute filings
        
        return {
            'materiality_score': materiality_score,
            'evidence': evidence,
            'data_gaps': [
                'Government complaint records needed',
                'Contract performance evaluations needed',
                'Dispute/termination data needed'
            ]
        }
    
    def assess_scienter(self, contract: Dict) -> Dict:
        """
        Scienter (intent) indicators:
        - Pattern of overcharging (not isolated incident)
        - Deceptive descriptions
        - Concealment attempts
        """
        
        scienter_score = 0
        evidence = []
        
        # Indicator 1: Pattern evidence
        vendor_high_price_count = self.count_vendor_high_price_contracts(
            contract['vendor']
        )
        if vendor_high_price_count >= 3:
            scienter_score += 40
            evidence.append(f"Vendor has {vendor_high_price_count} high-markup contracts (suggests knowing behavior)")
        
        # Indicator 2: Deceptive description
        if self.check_description_mismatch(contract):
            scienter_score += 30
            evidence.append("Description uses specialized language for standard items")
        
        # TODO: Add when data available:
        # - Internal communications (FOIA)
        # - Pricing methodology documents
        # - Comparable quotes from vendor
        # - Amendment patterns (low initial bid → massive amendments)
        
        return {
            'scienter_score': scienter_score,
            'evidence': evidence,
            'data_gaps': [
                'Internal vendor communications needed (FOIA)',
                'Amendment history needed',
                'Vendor pricing methodology needed'
            ]
        }
    
    def check_affirmative_defenses(self, contract: Dict) -> Dict:
        """
        Legitimate reasons for high prices (FAR-based):
        - Sole-source justified (FAR 6.302)
        - Urgent/emergency (FAR 6.302-2)
        - Unique expertise (FAR 6.302-3)
        - Small business set-aside
        """
        
        defenses = []
        should_exclude = False
        
        # Check 1: Sole-source indicators (from description)
        desc = (contract.get('description', '') or '').lower()
        if any(kw in desc for kw in ['sole source', 'proprietary', 'patent', 'unique']):
            defenses.append("Possible legitimate sole-source (proprietary technology)")
            # Don't auto-exclude, but flag for manual review
        
        # Check 2: Emergency/urgency
        if any(kw in desc for kw in ['urgent', 'emergency', 'immediate', 'critical']):
            defenses.append("Possible emergency procurement (FAR 6.302-2)")
        
        # Check 3: R&D/specialized
        if any(kw in desc for kw in ['research', 'development', 'experimental', 'prototype']):
            defenses.append("R&D contract (higher variance expected)")
            should_exclude = True  # Don't flag R&D for price
        
        # TODO: Add when data available:
        # - J&A (Justification & Approval) documents
        # - Small business status
        # - Contract vehicle type (IDIQ vs FFP)
        
        return {
            'defenses': defenses,
            'should_exclude': should_exclude,
            'data_gaps': [
                'J&A documents needed',
                'Small business status needed',
                'Contract vehicle data needed'
            ]
        }
    
    def get_vendor_contract_count(self, vendor: str) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM contracts WHERE vendor_name = ?", (vendor,))
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def count_vendor_high_price_contracts(self, vendor: str, threshold: float = 200) -> int:
        """Count how many contracts this vendor has with >threshold% markup"""
        # TODO: Need to calculate markup for all vendor contracts
        # Placeholder for now
        return 0
    
    def check_description_mismatch(self, contract: Dict) -> bool:
        """
        Check if description uses specialized jargon for standard work
        (Obfuscation tactic)
        """
        desc = (contract.get('description', '') or '').lower()
        
        # Jargon indicators
        jargon_words = ['quantum', 'blockchain', 'ai-powered', 'neural', 'advanced', 'next-generation']
        jargon_count = sum(1 for word in jargon_words if word in desc)
        
        # Standard work indicators
        standard_words = ['support', 'maintenance', 'installation', 'configuration']
        standard_count = sum(1 for word in standard_words if word in desc)
        
        # If high jargon + standard work = suspicious obfuscation
        return jargon_count >= 2 and standard_count >= 1

if __name__ == "__main__":
    framework = LegalFrameworkV2()
    
    # Test case: Technica
    test_contract = {
        'vendor': 'TECHNICA CORPORATION',
        'amount': 113655241,
        'markup_pct': 156,
        'description': 'Advanced cybersecurity support services'
    }
    
    print("LEGAL FRAMEWORK V2 ANALYSIS")
    print("="*60)
    
    materiality = framework.assess_materiality(test_contract)
    print("\nMATERIALITY ASSESSMENT:")
    print(f"  Score: {materiality['materiality_score']}/100")
    for e in materiality['evidence']:
        print(f"  • {e}")
    print("  Data Gaps:")
    for gap in materiality['data_gaps']:
        print(f"    - {gap}")
    
    scienter = framework.assess_scienter(test_contract)
    print("\nSCIENTER (INTENT) ASSESSMENT:")
    print(f"  Score: {scienter['scienter_score']}/100")
    for e in scienter['evidence']:
        print(f"  • {e}")
    
    defenses = framework.check_affirmative_defenses(test_contract)
    print("\nAFFIRMATIVE DEFENSES:")
    if defenses['defenses']:
        for d in defenses['defenses']:
            print(f"  • {d}")
    print(f"  Should exclude from flagging: {defenses['should_exclude']}")
