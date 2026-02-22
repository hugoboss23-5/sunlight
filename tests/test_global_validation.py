"""
Tests for SUNLIGHT Global Validation Modules
=============================================
Tests calibration_config.py and mdb_validation.py

Run with: pytest test_global_validation.py -v
"""

import json
import os
import tempfile
import pytest

from calibration_config import (
    CalibrationProfile,
    PROFILES,
    EVIDENTIARY_STANDARDS,
    get_profile,
    list_profiles,
    create_tenant_profile,
    get_prior_for_context,
    get_tier_thresholds,
    get_fdr_params,
    get_bootstrap_params,
    provenance_string,
    save_profile_to_file,
    load_profile_from_file,
)

from mdb_validation import (
    MDBSanctionedEntity,
    MDBValidationCase,
    classify_practice_type,
    infer_sector_from_name,
    infer_region_from_country,
    generate_synthetic_contract_params,
    entities_to_validation_cases,
    run_validation,
)


# =========================================================================
# CalibrationProfile Tests
# =========================================================================

class TestCalibrationProfile:
    """Test CalibrationProfile dataclass and methods."""

    def test_default_profile_creation(self):
        profile = CalibrationProfile(name="test")
        assert profile.name == "test"
        assert profile.base_rate == 0.03
        assert profile.evidentiary_standard == "balance_of_probabilities"
        assert profile.fdr_alpha == 0.05
        assert profile.bootstrap_n_resamples == 10_000

    def test_validate_good_profile(self):
        profile = CalibrationProfile(
            name="test",
            base_rate=0.10,
            red_posterior_threshold=0.65,
            yellow_posterior_threshold=0.35,
        )
        warnings = profile.validate()
        assert len(warnings) == 0

    def test_validate_bad_base_rate(self):
        profile = CalibrationProfile(name="test", base_rate=0.80)
        warnings = profile.validate()
        assert any("base_rate" in w for w in warnings)

    def test_validate_inverted_thresholds(self):
        profile = CalibrationProfile(
            name="test",
            red_posterior_threshold=0.30,
            yellow_posterior_threshold=0.50,
        )
        warnings = profile.validate()
        assert any("red_threshold" in w for w in warnings)

    def test_validate_bad_evidentiary_standard(self):
        profile = CalibrationProfile(name="test", evidentiary_standard="vibes")
        warnings = profile.validate()
        assert any("evidentiary_standard" in w for w in warnings)

    def test_validate_high_fdr(self):
        profile = CalibrationProfile(name="test", fdr_alpha=0.20)
        warnings = profile.validate()
        assert any("fdr_alpha" in w for w in warnings)

    def test_validate_low_bootstrap(self):
        profile = CalibrationProfile(name="test", bootstrap_n_resamples=100)
        warnings = profile.validate()
        assert any("bootstrap" in w for w in warnings)

    def test_to_dict_roundtrip(self):
        profile = CalibrationProfile(
            name="roundtrip_test",
            base_rate=0.15,
            red_posterior_threshold=0.60,
        )
        d = profile.to_dict()
        restored = CalibrationProfile.from_dict(d)
        assert restored.name == profile.name
        assert restored.base_rate == profile.base_rate
        assert restored.red_posterior_threshold == profile.red_posterior_threshold

    def test_to_json(self):
        profile = CalibrationProfile(name="json_test")
        j = profile.to_json()
        data = json.loads(j)
        assert data["name"] == "json_test"
        assert isinstance(data["base_rate"], float)

    def test_summary_string(self):
        profile = CalibrationProfile(name="summary_test", base_rate=0.20)
        s = profile.summary()
        assert "summary_test" in s
        assert "20.0%" in s

    def test_file_save_load_roundtrip(self):
        profile = CalibrationProfile(
            name="file_test",
            base_rate=0.18,
            description="Test file roundtrip",
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            save_profile_to_file(profile, path)
            loaded = load_profile_from_file(path)
            assert loaded.name == "file_test"
            assert loaded.base_rate == 0.18
        finally:
            os.unlink(path)


# =========================================================================
# Preset Profiles Tests
# =========================================================================

class TestPresetProfiles:
    """Test the preset calibration profiles."""

    def test_all_profiles_exist(self):
        expected = [
            "doj_federal",
            "world_bank_global",
            "world_bank_africa",
            "afdb",
            "eu_procurement",
            "sai_developing",
            "imf_fiscal",
        ]
        for name in expected:
            assert name in PROFILES, f"Missing profile: {name}"

    def test_all_profiles_validate(self):
        for name, profile in PROFILES.items():
            warnings = profile.validate()
            assert len(warnings) == 0, f"Profile {name} has warnings: {warnings}"

    def test_doj_has_lowest_prior(self):
        doj = PROFILES["doj_federal"]
        for name, profile in PROFILES.items():
            if name != "doj_federal":
                assert profile.base_rate >= doj.base_rate, (
                    f"{name} has lower prior ({profile.base_rate}) "
                    f"than DOJ ({doj.base_rate})"
                )

    def test_africa_has_higher_prior_than_global(self):
        africa = PROFILES["world_bank_africa"]
        globe = PROFILES["world_bank_global"]
        assert africa.base_rate > globe.base_rate

    def test_sai_has_lowest_red_threshold(self):
        """SAIs use broader net for audit planning."""
        sai = PROFILES["sai_developing"]
        for name, profile in PROFILES.items():
            if name != "sai_developing":
                assert sai.red_posterior_threshold <= profile.red_posterior_threshold, (
                    f"SAI red threshold ({sai.red_posterior_threshold}) "
                    f"should be ≤ {name} ({profile.red_posterior_threshold})"
                )

    def test_all_profiles_have_citations(self):
        for name, profile in PROFILES.items():
            assert len(profile.source_citations) > 0, (
                f"Profile {name} missing source citations"
            )

    def test_all_profiles_have_descriptions(self):
        for name, profile in PROFILES.items():
            assert len(profile.description) > 20, (
                f"Profile {name} has insufficient description"
            )

    def test_evidentiary_standards_coverage(self):
        standards_used = set(p.evidentiary_standard for p in PROFILES.values())
        # At least 3 different standards should be represented
        assert len(standards_used) >= 3


# =========================================================================
# Access Functions Tests
# =========================================================================

class TestAccessFunctions:
    """Test profile access and creation functions."""

    def test_get_profile_valid(self):
        profile = get_profile("doj_federal")
        assert profile.name == "doj_federal"

    def test_get_profile_invalid(self):
        with pytest.raises(KeyError) as exc_info:
            get_profile("nonexistent_profile")
        assert "nonexistent_profile" in str(exc_info.value)

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) == len(PROFILES)
        assert all("name" in p for p in profiles)
        assert all("base_rate" in p for p in profiles)

    def test_create_tenant_profile(self):
        tenant = create_tenant_profile(
            "TENANT001",
            base_profile="world_bank_global",
            overrides={"base_rate": 0.18},
        )
        assert tenant.name == "tenant_TENANT001"
        assert tenant.base_rate == 0.18
        # Should inherit non-overridden values from base
        assert tenant.fdr_alpha == PROFILES["world_bank_global"].fdr_alpha

    def test_create_tenant_profile_no_overrides(self):
        tenant = create_tenant_profile("TENANT002", base_profile="afdb")
        assert tenant.base_rate == PROFILES["afdb"].base_rate


# =========================================================================
# Integration Helper Tests
# =========================================================================

class TestIntegrationHelpers:
    """Test functions designed for integration with institutional_pipeline.py."""

    def test_get_prior_for_context(self):
        profile = get_profile("world_bank_africa")
        prior = get_prior_for_context(profile)
        assert prior == 0.20

    def test_get_tier_thresholds(self):
        profile = get_profile("doj_federal")
        thresholds = get_tier_thresholds(profile)
        assert "red" in thresholds
        assert "yellow" in thresholds
        assert "min_typ_red" in thresholds
        assert thresholds["red"] > thresholds["yellow"]

    def test_get_fdr_params(self):
        profile = get_profile("sai_developing")
        params = get_fdr_params(profile)
        assert params["alpha"] == 0.08  # SAI has higher FDR alpha

    def test_get_bootstrap_params(self):
        profile = get_profile("doj_federal")
        params = get_bootstrap_params(profile)
        assert params["ci_level"] == 0.95
        assert params["n_resamples"] == 10_000

    def test_provenance_string(self):
        profile = get_profile("world_bank_africa")
        prov = provenance_string(profile)
        assert "world_bank_africa" in prov
        assert "20.0%" in prov
        assert "balance_of_probabilities" in prov


# =========================================================================
# MDB Validation Tests
# =========================================================================

class TestMDBClassifiers:
    """Test entity classification functions."""

    def test_classify_fraud(self):
        assert classify_practice_type("Fraudulent Practice") == "fraud"
        assert classify_practice_type("fraud, corruption") == "fraud"

    def test_classify_corruption(self):
        assert classify_practice_type("Corrupt Practice") == "corruption"

    def test_classify_collusion(self):
        assert classify_practice_type("Collusive Practice") == "collusion"

    def test_classify_coercion(self):
        assert classify_practice_type("Coercive Practice") == "coercion"

    def test_classify_obstruction(self):
        assert classify_practice_type("Obstructive Practice") == "obstruction"

    def test_classify_default(self):
        assert classify_practice_type("unknown text") == "fraud"

    def test_infer_sector_construction(self):
        assert infer_sector_from_name("ABC Construction Ltd") == "construction"
        assert infer_sector_from_name("Travaux Publics SA") == "construction"

    def test_infer_sector_health(self):
        assert infer_sector_from_name("MedTech Health Supplies") == "health"

    def test_infer_sector_it(self):
        assert infer_sector_from_name("Digital Technology Solutions") == "IT"

    def test_infer_sector_general(self):
        assert infer_sector_from_name("XYZ Corporation") == "general"

    def test_infer_region_africa(self):
        assert infer_region_from_country("ng") == "Sub-Saharan Africa"
        assert infer_region_from_country("bf") == "Sub-Saharan Africa"
        assert infer_region_from_country("ke") == "Sub-Saharan Africa"

    def test_infer_region_south_asia(self):
        assert infer_region_from_country("bd") == "South Asia"
        assert infer_region_from_country("in") == "South Asia"

    def test_infer_region_latin_america(self):
        assert infer_region_from_country("br") == "Latin America & Caribbean"

    def test_infer_region_multi_country(self):
        # Multi-country entity — should pick the first matching region
        result = infer_region_from_country("ng;gh")
        assert result == "Sub-Saharan Africa"


class TestSyntheticContractGeneration:
    """Test synthetic contract parameter generation."""

    def test_fraud_params(self):
        params = generate_synthetic_contract_params("fraud")
        assert params["price_inflation_factor"] >= 1.8
        assert "Price Anomaly" in params["expected_typologies"]
        assert params["contract_value_usd"] > 0

    def test_corruption_params(self):
        params = generate_synthetic_contract_params("corruption")
        assert params["price_inflation_factor"] >= 1.5
        assert params["vendor_concentration_pct"] > 0.30

    def test_collusion_params(self):
        params = generate_synthetic_contract_params("collusion")
        assert params["vendor_concentration_pct"] > 0.30
        assert "Vendor Concentration" in params["expected_typologies"]

    def test_all_practice_types_generate(self):
        for pt in ["fraud", "corruption", "collusion", "coercion", "obstruction"]:
            params = generate_synthetic_contract_params(pt)
            assert params["contract_value_usd"] > 0
            assert len(params["expected_typologies"]) > 0


class TestValidationCaseCreation:
    """Test entity → validation case conversion."""

    def test_entities_to_cases(self):
        entities = {
            "world_bank": [
                MDBSanctionedEntity(
                    entity_id="WB001",
                    entity_name="Test Construction Co",
                    entity_type="Company",
                    source_mdb="world_bank",
                    country="ng",
                    grounds="Fraudulent Practice",
                ),
                MDBSanctionedEntity(
                    entity_id="WB002",
                    entity_name="Test Person",
                    entity_type="Person",
                    source_mdb="world_bank",
                    country="bd",
                    grounds="Corrupt Practice",
                ),
            ]
        }

        # Companies only — should exclude the Person
        cases = entities_to_validation_cases(entities, companies_only=True)
        assert len(cases) == 1
        assert cases[0].entity_name == "Test Construction Co"
        assert cases[0].sector == "construction"
        assert cases[0].region == "Sub-Saharan Africa"

    def test_max_per_source_limit(self):
        entities = {
            "world_bank": [
                MDBSanctionedEntity(
                    entity_id=f"WB{i:03d}",
                    entity_name=f"Company {i}",
                    entity_type="Company",
                    source_mdb="world_bank",
                    country="ng",
                    grounds="Fraud",
                )
                for i in range(100)
            ]
        }
        cases = entities_to_validation_cases(entities, max_per_source=10)
        assert len(cases) == 10


class TestValidationRunner:
    """Test the validation runner (with stub engine)."""

    def test_run_validation_basic(self):
        cases = [
            MDBValidationCase(
                case_id="TEST-001",
                entity_name="Test Fraudulent Corp",
                source_mdb="world_bank",
                country="ng",
                region="Sub-Saharan Africa",
                practice_type="fraud",
                price_inflation_factor=2.5,
                expected_tier="RED",
                expected_typologies=["Price Anomaly"],
            ),
        ]
        results = run_validation(cases)
        assert results["total_cases"] == 1
        assert results["detected"] == 1
        assert results["recall"] == 1.0

    def test_run_validation_aggregation(self):
        cases = [
            MDBValidationCase(
                case_id=f"TEST-{i:03d}",
                entity_name=f"Corp {i}",
                source_mdb="world_bank" if i < 3 else "afdb",
                country="ng",
                region="Sub-Saharan Africa",
                practice_type="fraud",
                price_inflation_factor=2.0 + i * 0.1,
                expected_tier="RED",
                expected_typologies=["Price Anomaly"],
            )
            for i in range(5)
        ]
        results = run_validation(cases)
        assert results["total_cases"] == 5
        assert "world_bank" in results["by_source"]
        assert "afdb" in results["by_source"]
        assert "fraud" in results["by_practice"]
        assert "Sub-Saharan Africa" in results["by_region"]


# =========================================================================
# Evidentiary Standards Tests
# =========================================================================

class TestEvidentiaryStandards:
    """Test evidentiary standard definitions."""

    def test_all_standards_have_required_fields(self):
        for name, standard in EVIDENTIARY_STANDARDS.items():
            assert "description" in standard
            assert "implied_confidence" in standard
            assert "used_by" in standard
            assert len(standard["used_by"]) > 0

    def test_confidence_ordering(self):
        """Criminal > civil > balance > suspicion."""
        standards = EVIDENTIARY_STANDARDS
        assert (
            standards["beyond_reasonable_doubt"]["implied_confidence"]
            > standards["clear_and_convincing"]["implied_confidence"]
            > standards["balance_of_probabilities"]["implied_confidence"]
            > standards["reasonable_suspicion"]["implied_confidence"]
        )

    def test_world_bank_uses_balance(self):
        balance = EVIDENTIARY_STANDARDS["balance_of_probabilities"]
        assert "World Bank Sanctions Board" in balance["used_by"]

    def test_afdb_uses_balance(self):
        balance = EVIDENTIARY_STANDARDS["balance_of_probabilities"]
        assert "African Development Bank" in balance["used_by"]
