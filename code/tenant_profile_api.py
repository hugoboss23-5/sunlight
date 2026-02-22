"""
SUNLIGHT API v2 — Tenant Profile Endpoints
============================================
GET/PATCH /api/v2/tenants/{tenant_id}/profile
GET /api/v2/presets

These endpoints manage the jurisdiction profile that drives detection
calibration and UI localization per tenant.

Integration: Mount this router in your main FastAPI app:
    from tenant_profile_api import router as profile_router
    app.include_router(profile_router)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field

from tenant_profile import (
    TenantProfile,
    TenantProfileStore,
    JurisdictionConfig,
    DetectionProfileConfig,
    UILocaleConfig,
    PRESET_DEFAULTS,
    list_presets,
    detect_direction,
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v2", tags=["tenant-profile"])

# In production, this is replaced with PostgreSQL-backed store
_store = TenantProfileStore(backend="memory")


def get_store() -> TenantProfileStore:
    return _store


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class JurisdictionPatch(BaseModel):
    continent: Optional[str] = None
    country_code: Optional[str] = None
    institution_profile: Optional[str] = None
    preferred_currency: Optional[str] = None


class DetectionProfilePatch(BaseModel):
    profile_id: Optional[str] = None
    label: Optional[str] = None
    evidentiary_standard: Optional[str] = None
    prior_fraud_rate: Optional[float] = Field(None, ge=0.01, le=0.50)
    red_threshold: Optional[float] = Field(None, ge=0.10, le=0.99)
    yellow_threshold: Optional[float] = Field(None, ge=0.05, le=0.90)
    min_typologies_for_red: Optional[int] = Field(None, ge=1, le=5)
    fdr_alpha: Optional[float] = Field(None, ge=0.01, le=0.20)
    max_flags_per_1k: Optional[int] = Field(None, ge=50, le=500)
    context_gating_rules: Optional[dict] = None
    caps: Optional[dict] = None


class UILocalePatch(BaseModel):
    language_tag: Optional[str] = None
    date_format: Optional[str] = None
    number_format: Optional[str] = None
    timezone: Optional[str] = None


class ProfilePatchRequest(BaseModel):
    """PATCH body for updating tenant profile. All fields optional."""
    apply_preset: Optional[str] = None  # If set, apply preset first, then overrides
    jurisdiction: Optional[JurisdictionPatch] = None
    detection_profile: Optional[DetectionProfilePatch] = None
    ui_locale: Optional[UILocalePatch] = None


class ProfileResponse(BaseModel):
    tenant_id: str
    jurisdiction: dict
    detection_profile: dict
    ui_locale: dict
    created_at: str
    updated_at: str
    provenance: str  # Audit trail string


class PresetResponse(BaseModel):
    preset_id: str
    label: str
    description: str
    prior_fraud_rate: float
    evidentiary_standard: str
    red_threshold: float
    yellow_threshold: float
    default_language: str
    default_timezone: str


# ---------------------------------------------------------------------------
# Auth dependency stub
# ---------------------------------------------------------------------------

async def verify_tenant_access(
    tenant_id: str,
    authorization: str = Header(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> str:
    """
    Verify the caller has access to this tenant. In production, this
    validates the API key and checks RBAC for the tenant.

    For now, just verify tenant_id matches the header.
    """
    if x_tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="X-Tenant-ID header does not match requested tenant"
        )
    return tenant_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/presets", response_model=list[PresetResponse])
async def list_available_presets():
    """
    List all available jurisdiction presets.
    No auth required — presets are not tenant-specific.
    """
    return list_presets()


@router.get("/presets/{preset_id}")
async def get_preset_detail(preset_id: str):
    """Get full details of a specific preset."""
    if preset_id not in PRESET_DEFAULTS:
        raise HTTPException(404, f"Preset '{preset_id}' not found")

    preset = PRESET_DEFAULTS[preset_id]
    det = preset["detection"]
    return {
        "preset_id": preset_id,
        "label": det.label,
        "description": preset["description"],
        "detection_profile": {
            "prior_fraud_rate": det.prior_fraud_rate,
            "evidentiary_standard": det.evidentiary_standard,
            "red_threshold": det.red_threshold,
            "yellow_threshold": det.yellow_threshold,
            "min_typologies_for_red": det.min_typologies_for_red,
            "fdr_alpha": det.fdr_alpha,
            "max_flags_per_1k": det.max_flags_per_1k,
        },
        "locale_defaults": preset["locale_defaults"],
    }


@router.get(
    "/tenants/{tenant_id}/profile",
    response_model=ProfileResponse,
)
async def get_tenant_profile(
    tenant_id: str,
    store: TenantProfileStore = Depends(get_store),
):
    """
    Get the current jurisdiction profile for a tenant.
    Returns defaults (global_mdb_default) if no profile is set.
    """
    profile = store.load(tenant_id)
    if profile is None:
        # Auto-create with default preset
        profile = TenantProfile.from_preset("global_mdb_default", tenant_id)
        store.save(profile)

    data = profile.to_dict()
    data["provenance"] = profile.provenance_string()
    return data


@router.patch(
    "/tenants/{tenant_id}/profile",
    response_model=ProfileResponse,
)
async def update_tenant_profile(
    tenant_id: str,
    patch: ProfilePatchRequest,
    store: TenantProfileStore = Depends(get_store),
):
    """
    Update the jurisdiction profile for a tenant.

    Workflow:
    1. If apply_preset is set, reset profile to that preset first.
    2. Then apply any field-level overrides from jurisdiction/detection_profile/ui_locale.
    3. Validate detection_profile thresholds.
    4. Persist and return.
    """
    # Load existing or create default
    profile = store.load(tenant_id)
    if profile is None:
        profile = TenantProfile.from_preset("global_mdb_default", tenant_id)

    # Step 1: Apply preset if requested
    if patch.apply_preset:
        if patch.apply_preset not in PRESET_DEFAULTS:
            raise HTTPException(
                400,
                f"Unknown preset '{patch.apply_preset}'. "
                f"Available: {', '.join(sorted(PRESET_DEFAULTS.keys()))}"
            )
        # Preserve tenant_id and created_at
        created = profile.created_at
        profile = TenantProfile.from_preset(patch.apply_preset, tenant_id)
        profile.created_at = created

    # Step 2: Apply field overrides
    if patch.jurisdiction:
        for field_name, value in patch.jurisdiction.model_dump(exclude_none=True).items():
            setattr(profile.jurisdiction, field_name, value)

    if patch.detection_profile:
        for field_name, value in patch.detection_profile.model_dump(exclude_none=True).items():
            setattr(profile.detection_profile, field_name, value)

    if patch.ui_locale:
        for field_name, value in patch.ui_locale.model_dump(exclude_none=True).items():
            setattr(profile.ui_locale, field_name, value)
        # Recompute direction
        profile.ui_locale.direction = detect_direction(profile.ui_locale.language_tag)

    # Step 3: Validate
    warnings = profile.detection_profile.validate()
    if warnings:
        raise HTTPException(
            422,
            detail={
                "message": "Invalid detection profile configuration",
                "warnings": warnings,
            }
        )

    # Step 4: Persist
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    store.save(profile)

    data = profile.to_dict()
    data["provenance"] = profile.provenance_string()
    return data


# ---------------------------------------------------------------------------
# SQL Migration (for production PostgreSQL deployment)
# ---------------------------------------------------------------------------

MIGRATION_SQL = """
-- Migration: Add tenant_profiles table
-- Run after existing tenant tables are in place

CREATE TABLE IF NOT EXISTS tenant_profiles (
    tenant_id       TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    profile_data    JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS policy: tenants can only read/write their own profile
ALTER TABLE tenant_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_profile_isolation ON tenant_profiles
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_tenant_profiles_tenant
    ON tenant_profiles(tenant_id);

-- Audit trigger
CREATE OR REPLACE FUNCTION update_tenant_profile_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tenant_profile_updated
    BEFORE UPDATE ON tenant_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_tenant_profile_timestamp();

COMMENT ON TABLE tenant_profiles IS
    'Tenant jurisdiction profiles: detection calibration + UI locale + jurisdiction config. '
    'profile_data is JSONB containing jurisdiction, detection_profile, and ui_locale objects.';
"""
