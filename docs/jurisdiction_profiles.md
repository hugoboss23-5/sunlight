# Jurisdiction Profiles

## Overview

SUNLIGHT uses **jurisdiction profiles** to configure detection calibration, evidentiary standards, and UI formatting per tenant. A jurisdiction profile is a tenant-level configuration that drives three things:

1. **Detection calibration** — Bayesian prior, tier thresholds, FDR alpha, caps
2. **UI locale** — language, date/number formatting, timezone, RTL support
3. **Jurisdiction context** — continent, country, currency, institution type

Profiles do NOT modify the statistical engine. They inject configuration parameters at scoring time.

## Presets

SUNLIGHT ships with 8 institutional presets. Each is grounded in published data:

| Preset | Prior | Standard | RED ≥ | Use Case |
|--------|-------|----------|-------|----------|
| `global_mdb_default` | 10% | Balance of probabilities | 65% | World Bank-style MDB projects globally |
| `doj_criminal_strict` | 3% | Beyond reasonable doubt | 72% | US federal procurement, DOJ-calibrated |
| `sai_audit_planning` | 15% | Reasonable suspicion | 55% | Supreme Audit Institutions, broad audit targeting |
| `afdb_integrity` | 20% | Balance of probabilities | 60% | AfDB projects in Sub-Saharan Africa |
| `world_bank_africa` | 20% | Balance of probabilities | 60% | World Bank projects in Sub-Saharan Africa |
| `adb_asia_mdb` | 12% | Balance of probabilities | 62% | Asian Development Bank projects |
| `eu_procurement` | 8% | Balance of probabilities | 68% | EU member state procurement |
| `imf_fiscal` | 12% | Balance of probabilities | 62% | IMF fiscal governance indicators |

## API

### List presets

```
GET /api/v2/presets
```

Returns all available presets with their default parameters.

### Get tenant profile

```
GET /api/v2/tenants/{tenant_id}/profile
Headers: Authorization: Bearer <token>, X-Tenant-ID: <tenant_id>
```

Returns the current profile. Creates a default (`global_mdb_default`) if none exists.

### Update tenant profile

```
PATCH /api/v2/tenants/{tenant_id}/profile
Headers: Authorization: Bearer <token>, X-Tenant-ID: <tenant_id>
Content-Type: application/json
```

Body:
```json
{
  "apply_preset": "afdb_integrity",
  "jurisdiction": {
    "continent": "Africa",
    "country_code": "BF",
    "preferred_currency": "XOF"
  },
  "ui_locale": {
    "language_tag": "fr-FR",
    "timezone": "Africa/Ouagadougou"
  },
  "detection_profile": {
    "prior_fraud_rate": 0.22
  }
}
```

Workflow:
1. If `apply_preset` is set, reset to that preset first
2. Apply field-level overrides
3. Validate detection parameters
4. Persist tenant-wide

## Evidentiary Standards

| Standard | Confidence | Used By |
|----------|-----------|---------|
| Beyond reasonable doubt | ~95% | DOJ, federal courts |
| Clear and convincing | ~75% | US civil courts, SEC |
| Balance of probabilities | ~51% | World Bank, AfDB, ADB, IDB, EBRD |
| Reasonable suspicion | ~30% | SAIs, national audit offices |

## Architecture

### Data flow

```
Admin selects preset → Profile saved to DB → Scoring engine reads profile →
Prior/thresholds injected at score time → Detection report includes provenance
```

### Multi-tenant isolation

Profiles are stored in the `tenant_profiles` table with PostgreSQL Row-Level Security. Each tenant can only read/write their own profile. The `profile_id` is recorded in every detection report's audit trail.

### Configuration injection (not algorithm modification)

The engine's `score_contract()` function accepts a calibration profile parameter. Changing the profile changes:
- The Bayesian prior (base rate)
- The posterior threshold for RED/YELLOW tier assignment
- The FDR alpha for multiple testing correction
- The max flags/1K target

It does NOT change: the bootstrap CI methodology, the Bayesian update formula, the FDR correction procedure, or the typology definitions.

## Important Notes

- **Presets are not claims about national law.** They are defensible statistical calibrations grounded in published institutional data (OECD estimates, MDB sanctions standards).
- **Continent/country is a convenience selector.** It maps to a preset and sets locale defaults. It does not imply we encode jurisdiction-specific legal standards.
- **Custom overrides are possible** but presets are recommended. Custom values are validated (prior must be 0.01–0.50, red_threshold must exceed yellow_threshold).
- **Every detection report includes a provenance string** showing the active profile, prior, standard, and thresholds. This is a non-negotiable audit trail requirement.
