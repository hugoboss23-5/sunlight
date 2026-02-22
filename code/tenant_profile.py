"""
SUNLIGHT Tenant Jurisdiction Profile
======================================
Tenant-level configuration model that drives detection calibration,
UI localization, and locale formatting.

This module does NOT modify the statistical engine. It provides
configuration that is injected into the existing engine at scoring time.

Usage:
    profile = TenantProfile.from_preset("global_mdb_default", tenant_id="T001")
    profile.jurisdiction.country_code = "BF"
    profile.ui_locale.language_tag = "fr-FR"
    profile.save(db)  # persists to tenant config table

Integration with scoring:
    from tenant_profile import load_tenant_profile
    from calibration_config import CalibrationProfile

    tp = load_tenant_profile(db, tenant_id)
    cal = tp.to_calibration_profile()
    # pass cal to score_contract() as before
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InstitutionPreset(str, Enum):
    """
    Preset institution profiles. These map to detection_profile defaults.
    Each preset is a defensible, citable configuration — not a claim to
    encode national law.
    """
    GLOBAL_MDB_DEFAULT = "global_mdb_default"
    DOJ_CRIMINAL_STRICT = "doj_criminal_strict"
    SAI_AUDIT_PLANNING = "sai_audit_planning"
    AFDB_INTEGRITY = "afdb_integrity"
    ADB_ASIA_MDB = "adb_asia_mdb"
    WORLD_BANK_AFRICA = "world_bank_africa"
    EU_PROCUREMENT = "eu_procurement"
    IMF_FISCAL = "imf_fiscal"
    CUSTOM = "custom"


class EvidentiaryStandard(str, Enum):
    BEYOND_REASONABLE_DOUBT = "beyond_reasonable_doubt"
    CLEAR_AND_CONVINCING = "clear_and_convincing"
    BALANCE_OF_PROBABILITIES = "balance_of_probabilities"
    REASONABLE_SUSPICION = "reasonable_suspicion"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

@dataclass
class JurisdictionConfig:
    """Geographic and institutional context for the tenant."""
    continent: str = ""                          # e.g. "Africa", "Asia", "Europe"
    country_code: str = ""                       # ISO 3166-1 alpha-2 (e.g. "BF", "NG")
    institution_profile: str = "global_mdb_default"  # InstitutionPreset value
    preferred_currency: str = "USD"              # ISO 4217 (e.g. "XOF", "EUR", "NGN")


@dataclass
class DetectionProfileConfig:
    """
    Detection calibration parameters derived from the institution preset.
    These are INJECTED into the scoring engine via configuration —
    no algorithm changes.
    """
    profile_id: str = "global_mdb_default"
    label: str = "MDB Global Default"
    evidentiary_standard: str = "balance_of_probabilities"
    prior_fraud_rate: float = 0.10
    red_threshold: float = 0.65
    yellow_threshold: float = 0.35
    min_typologies_for_red: int = 2
    fdr_alpha: float = 0.05
    max_flags_per_1k: int = 200
    context_gating_rules: dict = field(default_factory=dict)
    caps: dict = field(default_factory=dict)  # e.g. {"max_red_per_vendor": 5}

    def validate(self) -> list[str]:
        warnings = []
        if not 0.01 <= self.prior_fraud_rate <= 0.50:
            warnings.append(f"prior_fraud_rate={self.prior_fraud_rate} outside [0.01, 0.50]")
        if self.red_threshold <= self.yellow_threshold:
            warnings.append(f"red_threshold must exceed yellow_threshold")
        if self.fdr_alpha > 0.10:
            warnings.append(f"fdr_alpha={self.fdr_alpha} unusually high")
        return warnings


@dataclass
class UILocaleConfig:
    """Locale and formatting preferences for the tenant UI."""
    language_tag: str = "en-US"       # BCP-47 (e.g. "fr-FR", "ar-SA", "es-MX")
    date_format: str = "YYYY-MM-DD"   # display hint; actual formatting via Intl
    number_format: str = "standard"   # "standard" uses Intl defaults for locale
    timezone: str = "UTC"             # IANA timezone (e.g. "Africa/Ouagadougou")
    direction: str = "ltr"            # "ltr" or "rtl" — derived from language_tag


# ---------------------------------------------------------------------------
# Preset Definitions
# ---------------------------------------------------------------------------
# Each preset maps an institution/context to defensible detection parameters.
# Source citations are in calibration_config.py.

PRESET_DEFAULTS: dict[str, dict] = {
    "global_mdb_default": {
        "detection": DetectionProfileConfig(
            profile_id="global_mdb_default",
            label="MDB Global Default",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.10,
            red_threshold=0.65,
            yellow_threshold=0.35,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=200,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "UTC"},
        "description": "World Bank-style posture. Balance of probabilities standard. "
                       "Blended 10% prior across borrower countries.",
    },
    "doj_criminal_strict": {
        "detection": DetectionProfileConfig(
            profile_id="doj_criminal_strict",
            label="DOJ Criminal Standard",
            evidentiary_standard="beyond_reasonable_doubt",
            prior_fraud_rate=0.03,
            red_threshold=0.72,
            yellow_threshold=0.38,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=150,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "America/New_York"},
        "description": "US DOJ prosecution-calibrated. Conservative 3% prior. "
                       "Highest evidentiary standard. Validated 100% recall on 10 DOJ cases.",
    },
    "sai_audit_planning": {
        "detection": DetectionProfileConfig(
            profile_id="sai_audit_planning",
            label="SAI Audit Planning",
            evidentiary_standard="reasonable_suspicion",
            prior_fraud_rate=0.15,
            red_threshold=0.55,
            yellow_threshold=0.28,
            min_typologies_for_red=1,
            fdr_alpha=0.08,
            max_flags_per_1k=300,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "UTC"},
        "description": "Supreme Audit Institution posture. Broad net for audit targeting. "
                       "Higher FDR alpha acceptable — false positives lead to audits, not sanctions.",
    },
    "afdb_integrity": {
        "detection": DetectionProfileConfig(
            profile_id="afdb_integrity",
            label="AfDB Integrity",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.20,
            red_threshold=0.60,
            yellow_threshold=0.32,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=250,
        ),
        "locale_defaults": {"language_tag": "fr-FR", "timezone": "Africa/Abidjan"},
        "description": "African Development Bank posture. 20% prior for Sub-Saharan Africa. "
                       "French default (AfDB HQ in Abidjan). Balance of probabilities.",
    },
    "world_bank_africa": {
        "detection": DetectionProfileConfig(
            profile_id="world_bank_africa",
            label="World Bank — Sub-Saharan Africa",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.20,
            red_threshold=0.60,
            yellow_threshold=0.32,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=250,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "UTC"},
        "description": "World Bank projects in Sub-Saharan Africa. 20% prior per OECD estimates.",
    },
    "adb_asia_mdb": {
        "detection": DetectionProfileConfig(
            profile_id="adb_asia_mdb",
            label="ADB Asia / Pacific",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.12,
            red_threshold=0.62,
            yellow_threshold=0.34,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=200,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "Asia/Manila"},
        "description": "Asian Development Bank posture. Moderate 12% prior. "
                       "Balance of probabilities. ADB HQ in Manila.",
    },
    "eu_procurement": {
        "detection": DetectionProfileConfig(
            profile_id="eu_procurement",
            label="EU Procurement",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.08,
            red_threshold=0.68,
            yellow_threshold=0.36,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=175,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "Europe/Brussels"},
        "description": "EU public procurement. Moderate 8% prior. "
                       "Aligned with OECD/OLAF methodology.",
    },
    "imf_fiscal": {
        "detection": DetectionProfileConfig(
            profile_id="imf_fiscal",
            label="IMF Fiscal Affairs",
            evidentiary_standard="balance_of_probabilities",
            prior_fraud_rate=0.12,
            red_threshold=0.62,
            yellow_threshold=0.33,
            min_typologies_for_red=2,
            fdr_alpha=0.05,
            max_flags_per_1k=200,
        ),
        "locale_defaults": {"language_tag": "en-US", "timezone": "America/New_York"},
        "description": "IMF fiscal governance indicator posture. "
                       "Focuses on aggregate risk patterns at agency/sector level.",
    },
}


# ---------------------------------------------------------------------------
# RTL Language Detection
# ---------------------------------------------------------------------------

RTL_LANGUAGES = {"ar", "he", "fa", "ur", "ps", "dv", "ks", "ku", "sd", "ug", "yi"}

def detect_direction(language_tag: str) -> str:
    """Detect text direction from BCP-47 language tag."""
    primary = language_tag.split("-")[0].lower()
    return "rtl" if primary in RTL_LANGUAGES else "ltr"


# ---------------------------------------------------------------------------
# Tenant Profile (top-level model)
# ---------------------------------------------------------------------------

@dataclass
class TenantProfile:
    """
    Complete tenant configuration for jurisdiction, detection, and UI locale.

    This is the single source of truth for how SUNLIGHT behaves for a
    given tenant — what calibration to use, what language to display,
    how to format numbers and dates.
    """
    tenant_id: str
    jurisdiction: JurisdictionConfig = field(default_factory=JurisdictionConfig)
    detection_profile: DetectionProfileConfig = field(default_factory=DetectionProfileConfig)
    ui_locale: UILocaleConfig = field(default_factory=UILocaleConfig)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_preset(
        cls,
        preset_name: str,
        tenant_id: str,
        overrides: Optional[dict] = None,
    ) -> TenantProfile:
        """
        Create a TenantProfile from a preset, optionally overriding fields.

        Args:
            preset_name: Key in PRESET_DEFAULTS
            tenant_id: Tenant identifier
            overrides: Optional dict of overrides, e.g.
                {"jurisdiction": {"country_code": "BF"},
                 "ui_locale": {"language_tag": "fr-FR"}}
        """
        if preset_name not in PRESET_DEFAULTS:
            available = ", ".join(sorted(PRESET_DEFAULTS.keys()))
            raise KeyError(f"Unknown preset '{preset_name}'. Available: {available}")

        preset = PRESET_DEFAULTS[preset_name]
        now = datetime.now(timezone.utc).isoformat()

        # Deep-copy detection config from preset
        det = preset["detection"]
        detection = DetectionProfileConfig(
            profile_id=det.profile_id,
            label=det.label,
            evidentiary_standard=det.evidentiary_standard,
            prior_fraud_rate=det.prior_fraud_rate,
            red_threshold=det.red_threshold,
            yellow_threshold=det.yellow_threshold,
            min_typologies_for_red=det.min_typologies_for_red,
            fdr_alpha=det.fdr_alpha,
            max_flags_per_1k=det.max_flags_per_1k,
            context_gating_rules=dict(det.context_gating_rules),
            caps=dict(det.caps),
        )

        locale_defaults = preset.get("locale_defaults", {})
        lang = locale_defaults.get("language_tag", "en-US")
        ui_locale = UILocaleConfig(
            language_tag=lang,
            timezone=locale_defaults.get("timezone", "UTC"),
            direction=detect_direction(lang),
        )

        profile = cls(
            tenant_id=tenant_id,
            jurisdiction=JurisdictionConfig(
                institution_profile=preset_name,
            ),
            detection_profile=detection,
            ui_locale=ui_locale,
            created_at=now,
            updated_at=now,
        )

        # Apply overrides
        if overrides:
            if "jurisdiction" in overrides:
                for k, v in overrides["jurisdiction"].items():
                    if hasattr(profile.jurisdiction, k):
                        setattr(profile.jurisdiction, k, v)
            if "detection_profile" in overrides:
                for k, v in overrides["detection_profile"].items():
                    if hasattr(profile.detection_profile, k):
                        setattr(profile.detection_profile, k, v)
            if "ui_locale" in overrides:
                for k, v in overrides["ui_locale"].items():
                    if hasattr(profile.ui_locale, k):
                        setattr(profile.ui_locale, k, v)
                # Recompute direction if language changed
                profile.ui_locale.direction = detect_direction(
                    profile.ui_locale.language_tag
                )

        return profile

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "jurisdiction": asdict(self.jurisdiction),
            "detection_profile": asdict(self.detection_profile),
            "ui_locale": asdict(self.ui_locale),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> TenantProfile:
        return cls(
            tenant_id=d["tenant_id"],
            jurisdiction=JurisdictionConfig(**d.get("jurisdiction", {})),
            detection_profile=DetectionProfileConfig(**d.get("detection_profile", {})),
            ui_locale=UILocaleConfig(**d.get("ui_locale", {})),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )

    def to_calibration_profile(self):
        """
        Convert to CalibrationProfile for engine injection.
        This is the bridge between tenant config and statistical engine.
        """
        # Import here to avoid circular dependency
        from calibration_config import CalibrationProfile
        det = self.detection_profile
        return CalibrationProfile(
            name=det.profile_id,
            description=det.label,
            base_rate=det.prior_fraud_rate,
            evidentiary_standard=det.evidentiary_standard,
            red_posterior_threshold=det.red_threshold,
            yellow_posterior_threshold=det.yellow_threshold,
            min_typologies_for_red=det.min_typologies_for_red,
            fdr_alpha=det.fdr_alpha,
            max_flags_per_1k=det.max_flags_per_1k,
        )

    def provenance_string(self) -> str:
        """For detection report audit trail."""
        d = self.detection_profile
        return (
            f"Tenant: {self.tenant_id} | "
            f"Profile: {d.profile_id} ({d.label}) | "
            f"Prior: {d.prior_fraud_rate:.1%} | "
            f"Standard: {d.evidentiary_standard} | "
            f"RED ≥ {d.red_threshold:.0%} | "
            f"YELLOW ≥ {d.yellow_threshold:.0%} | "
            f"Locale: {self.ui_locale.language_tag}"
        )


# ---------------------------------------------------------------------------
# DB Persistence (abstract — works with dict store, PostgreSQL, or SQLite)
# ---------------------------------------------------------------------------

class TenantProfileStore:
    """
    Abstract store for tenant profiles. In production, this wraps the
    PostgreSQL tenant_config table. For testing/demo, uses in-memory dict.
    """

    def __init__(self, backend: str = "memory"):
        self.backend = backend
        self._store: dict[str, dict] = {}

    def save(self, profile: TenantProfile) -> TenantProfile:
        """Persist tenant profile."""
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        self._store[profile.tenant_id] = profile.to_dict()
        return profile

    def load(self, tenant_id: str) -> Optional[TenantProfile]:
        """Load tenant profile. Returns None if not found."""
        data = self._store.get(tenant_id)
        if data is None:
            return None
        return TenantProfile.from_dict(data)

    def delete(self, tenant_id: str) -> bool:
        if tenant_id in self._store:
            del self._store[tenant_id]
            return True
        return False

    def list_tenants(self) -> list[str]:
        return list(self._store.keys())


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def list_presets() -> list[dict]:
    """List available presets with descriptions for API/UI."""
    return [
        {
            "preset_id": name,
            "label": preset["detection"].label,
            "description": preset["description"],
            "prior_fraud_rate": preset["detection"].prior_fraud_rate,
            "evidentiary_standard": preset["detection"].evidentiary_standard,
            "red_threshold": preset["detection"].red_threshold,
            "yellow_threshold": preset["detection"].yellow_threshold,
            "default_language": preset["locale_defaults"].get("language_tag", "en-US"),
            "default_timezone": preset["locale_defaults"].get("timezone", "UTC"),
        }
        for name, preset in PRESET_DEFAULTS.items()
    ]


def get_preset_description(preset_name: str) -> str:
    if preset_name in PRESET_DEFAULTS:
        return PRESET_DEFAULTS[preset_name]["description"]
    return ""
