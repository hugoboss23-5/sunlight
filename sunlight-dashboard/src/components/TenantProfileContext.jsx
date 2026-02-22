/**
 * SUNLIGHT Tenant Profile Context
 * =================================
 * Provides tenant profile, calibration settings, and locale formatters
 * to all child components via React context.
 *
 * Usage:
 *   // Wrap your app
 *   <TenantProfileProvider tenantId="T001">
 *     <App />
 *   </TenantProfileProvider>
 *
 *   // In any child component
 *   const { profile, fmt, isRTL, updateProfile } = useTenantProfile();
 *   <span>{fmt.currency(contract.value)}</span>
 *   <span>{fmt.date(contract.awardDate)}</span>
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { createTenantFormatter } from '../utils/localeFormat';
import { initLanguageFromProfile, isRTL as checkRTL } from '../i18n/i18n';

const TenantProfileContext = createContext(null);

// Default profile for demo/fallback
const DEFAULT_PROFILE = {
  tenant_id: 'demo',
  jurisdiction: {
    continent: '',
    country_code: '',
    institution_profile: 'global_mdb_default',
    preferred_currency: 'USD',
  },
  detection_profile: {
    profile_id: 'global_mdb_default',
    label: 'MDB Global Default',
    evidentiary_standard: 'balance_of_probabilities',
    prior_fraud_rate: 0.10,
    red_threshold: 0.65,
    yellow_threshold: 0.35,
    min_typologies_for_red: 2,
    fdr_alpha: 0.05,
    max_flags_per_1k: 200,
    context_gating_rules: {},
    caps: {},
  },
  ui_locale: {
    language_tag: 'en-US',
    date_format: 'YYYY-MM-DD',
    number_format: 'standard',
    timezone: 'UTC',
    direction: 'ltr',
  },
};

// API helpers
const API_BASE = import.meta.env?.VITE_API_URL || '';

async function fetchProfile(tenantId, authToken) {
  const resp = await fetch(`${API_BASE}/api/v2/tenants/${tenantId}/profile`, {
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'X-Tenant-ID': tenantId,
    },
  });
  if (!resp.ok) throw new Error(`Failed to fetch profile: ${resp.status}`);
  return resp.json();
}

async function patchProfile(tenantId, authToken, patch) {
  const resp = await fetch(`${API_BASE}/api/v2/tenants/${tenantId}/profile`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`,
      'X-Tenant-ID': tenantId,
    },
    body: JSON.stringify(patch),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail?.message || `Failed to update profile: ${resp.status}`);
  }
  return resp.json();
}

async function fetchPresets() {
  const resp = await fetch(`${API_BASE}/api/v2/presets`);
  if (!resp.ok) throw new Error(`Failed to fetch presets: ${resp.status}`);
  return resp.json();
}

/**
 * TenantProfileProvider
 *
 * Loads the tenant profile on mount, initializes i18n,
 * and provides profile + formatters to all children.
 */
export function TenantProfileProvider({
  children,
  tenantId = 'demo',
  authToken = '',
  demoMode = false,
}) {
  const { i18n } = useTranslation();
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [presets, setPresets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load profile on mount
  useEffect(() => {
    if (demoMode) {
      setProfile({ ...DEFAULT_PROFILE, tenant_id: tenantId });
      setLoading(false);
      return;
    }

    async function load() {
      try {
        setLoading(true);
        const [profileData, presetsData] = await Promise.all([
          fetchProfile(tenantId, authToken),
          fetchPresets(),
        ]);
        setProfile(profileData);
        setPresets(presetsData);

        // Initialize language from tenant profile
        initLanguageFromProfile(profileData.ui_locale?.language_tag);
      } catch (err) {
        console.error('Failed to load tenant profile:', err);
        setError(err.message);
        // Fall back to defaults
        setProfile({ ...DEFAULT_PROFILE, tenant_id: tenantId });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tenantId, authToken, demoMode]);

  // Update profile (persists to backend)
  const updateProfile = useCallback(async (patch) => {
    if (demoMode) {
      // In demo mode, just update local state
      setProfile(prev => ({
        ...prev,
        ...patch,
        jurisdiction: { ...prev.jurisdiction, ...patch.jurisdiction },
        detection_profile: { ...prev.detection_profile, ...patch.detection_profile },
        ui_locale: { ...prev.ui_locale, ...patch.ui_locale },
      }));
      return;
    }

    const updated = await patchProfile(tenantId, authToken, patch);
    setProfile(updated);

    // If language changed, update i18n
    if (patch.ui_locale?.language_tag) {
      const lang = patch.ui_locale.language_tag.split('-')[0];
      i18n.changeLanguage(lang);
    }

    return updated;
  }, [tenantId, authToken, demoMode, i18n]);

  // Apply preset
  const applyPreset = useCallback(async (presetId) => {
    return updateProfile({ apply_preset: presetId });
  }, [updateProfile]);

  // Create tenant formatter
  const fmt = createTenantFormatter(profile);

  const value = {
    profile,
    presets,
    loading,
    error,
    fmt,
    isRTL: checkRTL(profile.ui_locale?.language_tag || 'en'),
    updateProfile,
    applyPreset,
    demoMode,
  };

  return (
    <TenantProfileContext.Provider value={value}>
      {children}
    </TenantProfileContext.Provider>
  );
}

/**
 * Hook to access tenant profile context.
 */
export function useTenantProfile() {
  const ctx = useContext(TenantProfileContext);
  if (!ctx) {
    throw new Error('useTenantProfile must be used within TenantProfileProvider');
  }
  return ctx;
}

export { DEFAULT_PROFILE };
