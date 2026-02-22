/**
 * SUNLIGHT Admin — Jurisdiction & Standards Panel
 * =================================================
 * Allows admins to:
 * 1. Select institution preset (World Bank, DOJ, SAI, AfDB, ADB)
 * 2. Set continent/country/currency/timezone
 * 3. Preview detection parameters before saving
 * 4. Save profile (applies tenant-wide)
 *
 * This component does NOT modify the statistical engine.
 * It sets configuration that is injected at scoring time.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useTenantProfile } from './TenantProfileContext';

// ─── Data ──────────────────────────────────────────────────────────────

const CONTINENTS = [
  { value: '', label: 'select' },
  { value: 'Africa', label: 'Africa' },
  { value: 'Asia', label: 'Asia' },
  { value: 'Europe', label: 'Europe' },
  { value: 'North America', label: 'North America' },
  { value: 'South America', label: 'South America' },
  { value: 'Oceania', label: 'Oceania' },
];

// Subset of ISO 4217 currencies relevant to MDB contexts
const CURRENCIES = [
  { code: 'USD', name: 'US Dollar' },
  { code: 'EUR', name: 'Euro' },
  { code: 'GBP', name: 'British Pound' },
  { code: 'XOF', name: 'CFA Franc BCEAO' },
  { code: 'XAF', name: 'CFA Franc BEAC' },
  { code: 'NGN', name: 'Nigerian Naira' },
  { code: 'KES', name: 'Kenyan Shilling' },
  { code: 'GHS', name: 'Ghanaian Cedi' },
  { code: 'ZAR', name: 'South African Rand' },
  { code: 'BRL', name: 'Brazilian Real' },
  { code: 'INR', name: 'Indian Rupee' },
  { code: 'BDT', name: 'Bangladeshi Taka' },
  { code: 'PHP', name: 'Philippine Peso' },
  { code: 'CNY', name: 'Chinese Yuan' },
  { code: 'JPY', name: 'Japanese Yen' },
  { code: 'CHF', name: 'Swiss Franc' },
  { code: 'AED', name: 'UAE Dirham' },
  { code: 'SAR', name: 'Saudi Riyal' },
  { code: 'EGP', name: 'Egyptian Pound' },
  { code: 'ETB', name: 'Ethiopian Birr' },
];

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'America/Mexico_City',
  'Europe/London',
  'Europe/Paris',
  'Europe/Brussels',
  'Europe/Berlin',
  'Africa/Abidjan',
  'Africa/Lagos',
  'Africa/Nairobi',
  'Africa/Ouagadougou',
  'Africa/Johannesburg',
  'Africa/Cairo',
  'Asia/Manila',
  'Asia/Kolkata',
  'Asia/Dhaka',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Dubai',
  'Asia/Riyadh',
  'Australia/Sydney',
];

const STANDARD_LABELS = {
  beyond_reasonable_doubt: 'Beyond Reasonable Doubt (~95%)',
  clear_and_convincing: 'Clear and Convincing (~75%)',
  balance_of_probabilities: 'Balance of Probabilities (~51%)',
  reasonable_suspicion: 'Reasonable Suspicion (~30%)',
};

// ─── Component ─────────────────────────────────────────────────────────

export default function JurisdictionPanel() {
  const { t } = useTranslation();
  const { profile, presets, updateProfile, applyPreset, fmt } = useTenantProfile();

  // Local state for form (allows editing before save)
  const [form, setForm] = useState({
    institution_profile: '',
    continent: '',
    country_code: '',
    preferred_currency: 'USD',
    timezone: 'UTC',
    // Detection overrides (null = use preset default)
    prior_fraud_rate: null,
    red_threshold: null,
    yellow_threshold: null,
  });
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' | 'error' | null
  const [showCustom, setShowCustom] = useState(false);

  // Initialize form from profile
  useEffect(() => {
    if (profile) {
      setForm({
        institution_profile: profile.jurisdiction?.institution_profile || 'global_mdb_default',
        continent: profile.jurisdiction?.continent || '',
        country_code: profile.jurisdiction?.country_code || '',
        preferred_currency: profile.jurisdiction?.preferred_currency || 'USD',
        timezone: profile.ui_locale?.timezone || 'UTC',
        prior_fraud_rate: null,
        red_threshold: null,
        yellow_threshold: null,
      });
    }
  }, [profile]);

  // Find the currently selected preset's detection defaults
  const selectedPreset = useMemo(() => {
    return presets.find(p => p.preset_id === form.institution_profile) || null;
  }, [presets, form.institution_profile]);

  // Preview values (preset defaults with any custom overrides)
  const preview = useMemo(() => {
    if (!selectedPreset) return profile?.detection_profile || {};
    return {
      prior_fraud_rate: form.prior_fraud_rate ?? selectedPreset.prior_fraud_rate,
      red_threshold: form.red_threshold ?? selectedPreset.red_threshold,
      yellow_threshold: form.yellow_threshold ?? selectedPreset.yellow_threshold,
      evidentiary_standard: selectedPreset.evidentiary_standard,
    };
  }, [selectedPreset, form, profile]);

  // Handle preset change
  const handlePresetChange = (presetId) => {
    setForm(prev => ({
      ...prev,
      institution_profile: presetId,
      // Reset custom overrides when switching preset
      prior_fraud_rate: null,
      red_threshold: null,
      yellow_threshold: null,
    }));
    setShowCustom(false);
    setSaveStatus(null);
  };

  // Handle save
  const handleSave = async () => {
    setSaving(true);
    setSaveStatus(null);

    try {
      const patch = {
        apply_preset: form.institution_profile,
        jurisdiction: {
          continent: form.continent,
          country_code: form.country_code,
          institution_profile: form.institution_profile,
          preferred_currency: form.preferred_currency,
        },
        ui_locale: {
          timezone: form.timezone,
        },
      };

      // Add custom detection overrides if set
      if (form.prior_fraud_rate !== null || form.red_threshold !== null || form.yellow_threshold !== null) {
        patch.detection_profile = {};
        if (form.prior_fraud_rate !== null) patch.detection_profile.prior_fraud_rate = form.prior_fraud_rate;
        if (form.red_threshold !== null) patch.detection_profile.red_threshold = form.red_threshold;
        if (form.yellow_threshold !== null) patch.detection_profile.yellow_threshold = form.yellow_threshold;
      }

      await updateProfile(patch);
      setSaveStatus('success');
    } catch (err) {
      console.error('Save failed:', err);
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  // ─── Styles ────────────────────────────────────────────────────────

  const styles = {
    panel: {
      maxWidth: 860,
      fontFamily: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
    },
    header: {
      marginBottom: 8,
      fontSize: 20,
      fontWeight: 600,
      color: '#1a1a2e',
      letterSpacing: '-0.01em',
    },
    description: {
      fontSize: 14,
      color: '#64748b',
      marginBottom: 28,
      lineHeight: 1.5,
    },
    section: {
      marginBottom: 32,
      padding: '24px 28px',
      background: '#ffffff',
      borderRadius: 10,
      border: '1px solid #e2e8f0',
    },
    sectionTitle: {
      fontSize: 15,
      fontWeight: 600,
      color: '#334155',
      marginBottom: 20,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
    },
    fieldGrid: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '16px 24px',
    },
    field: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    },
    label: {
      fontSize: 12,
      fontWeight: 600,
      color: '#64748b',
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
    },
    select: {
      padding: '10px 14px',
      borderRadius: 8,
      border: '1px solid #d1d5db',
      fontSize: 14,
      color: '#1a1a2e',
      background: '#ffffff',
      cursor: 'pointer',
      outline: 'none',
      transition: 'border-color 0.15s',
    },
    input: {
      padding: '10px 14px',
      borderRadius: 8,
      border: '1px solid #d1d5db',
      fontSize: 14,
      color: '#1a1a2e',
      outline: 'none',
      transition: 'border-color 0.15s',
    },
    presetCard: (isSelected) => ({
      padding: '14px 18px',
      borderRadius: 8,
      border: `2px solid ${isSelected ? '#2563eb' : '#e2e8f0'}`,
      background: isSelected ? '#eff6ff' : '#ffffff',
      cursor: 'pointer',
      transition: 'all 0.15s',
    }),
    presetName: {
      fontSize: 14,
      fontWeight: 600,
      color: '#1a1a2e',
    },
    presetMeta: {
      fontSize: 12,
      color: '#64748b',
      marginTop: 4,
    },
    preview: {
      padding: '20px 24px',
      background: '#f8fafc',
      borderRadius: 8,
      border: '1px solid #e2e8f0',
    },
    previewTitle: {
      fontSize: 13,
      fontWeight: 600,
      color: '#334155',
      marginBottom: 12,
    },
    previewGrid: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr',
      gap: 16,
    },
    previewItem: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    },
    previewLabel: {
      fontSize: 11,
      fontWeight: 600,
      color: '#94a3b8',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    },
    previewValue: {
      fontSize: 18,
      fontWeight: 700,
      color: '#1e293b',
    },
    button: (variant = 'primary') => ({
      padding: '12px 24px',
      borderRadius: 8,
      border: variant === 'primary' ? 'none' : '1px solid #d1d5db',
      background: variant === 'primary' ? '#1e40af' : '#ffffff',
      color: variant === 'primary' ? '#ffffff' : '#334155',
      fontSize: 14,
      fontWeight: 600,
      cursor: 'pointer',
      transition: 'all 0.15s',
      opacity: saving ? 0.6 : 1,
    }),
    status: (type) => ({
      padding: '10px 16px',
      borderRadius: 8,
      fontSize: 13,
      fontWeight: 500,
      background: type === 'success' ? '#ecfdf5' : '#fef2f2',
      color: type === 'success' ? '#065f46' : '#991b1b',
      border: `1px solid ${type === 'success' ? '#a7f3d0' : '#fecaca'}`,
    }),
    toggleLink: {
      fontSize: 13,
      color: '#2563eb',
      cursor: 'pointer',
      fontWeight: 500,
      background: 'none',
      border: 'none',
      padding: 0,
      textDecoration: 'underline',
    },
    disclaimer: {
      padding: '12px 16px',
      background: '#fffbeb',
      borderRadius: 8,
      border: '1px solid #fde68a',
      fontSize: 12,
      color: '#92400e',
      lineHeight: 1.5,
      marginTop: 24,
    },
  };

  return (
    <div style={styles.panel}>
      <h2 style={styles.header}>{t('admin.jurisdiction_panel')}</h2>
      <p style={styles.description}>{t('admin.jurisdiction_description')}</p>

      {/* ── Institution Profile Selector ───────────────────────────── */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>📋</span>
          <span>{t('admin.institution_profile')}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
          {presets.map(preset => (
            <div
              key={preset.preset_id}
              style={styles.presetCard(form.institution_profile === preset.preset_id)}
              onClick={() => handlePresetChange(preset.preset_id)}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && handlePresetChange(preset.preset_id)}
              aria-pressed={form.institution_profile === preset.preset_id}
            >
              <div style={styles.presetName}>{preset.label}</div>
              <div style={styles.presetMeta}>
                {t('admin.prior_fraud_rate')}: {(preset.prior_fraud_rate * 100).toFixed(0)}%
                {' · '}
                {STANDARD_LABELS[preset.evidentiary_standard] || preset.evidentiary_standard}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Region & Currency ──────────────────────────────────────── */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>🌍</span>
          <span>{t('admin.continent')} & {t('admin.country')}</span>
        </div>

        <div style={styles.fieldGrid}>
          <div style={styles.field}>
            <label style={styles.label}>{t('admin.continent')}</label>
            <select
              style={styles.select}
              value={form.continent}
              onChange={e => setForm(p => ({ ...p, continent: e.target.value }))}
            >
              {CONTINENTS.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          <div style={styles.field}>
            <label style={styles.label}>{t('admin.country')} (ISO 3166-1)</label>
            <input
              style={styles.input}
              type="text"
              maxLength={2}
              placeholder="e.g. BF, NG, BD"
              value={form.country_code}
              onChange={e => setForm(p => ({ ...p, country_code: e.target.value.toUpperCase() }))}
            />
          </div>

          <div style={styles.field}>
            <label style={styles.label}>{t('admin.preferred_currency')}</label>
            <select
              style={styles.select}
              value={form.preferred_currency}
              onChange={e => setForm(p => ({ ...p, preferred_currency: e.target.value }))}
            >
              {CURRENCIES.map(c => (
                <option key={c.code} value={c.code}>{c.code} — {c.name}</option>
              ))}
            </select>
          </div>

          <div style={styles.field}>
            <label style={styles.label}>{t('admin.timezone')}</label>
            <select
              style={styles.select}
              value={form.timezone}
              onChange={e => setForm(p => ({ ...p, timezone: e.target.value }))}
            >
              {TIMEZONES.map(tz => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ── Configuration Preview ──────────────────────────────────── */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>🎯</span>
          <span>{t('admin.preview_title')}</span>
        </div>
        <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
          {t('admin.preview_description')}
        </p>

        <div style={styles.preview}>
          <div style={styles.previewGrid}>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.prior_fraud_rate')}</span>
              <span style={styles.previewValue}>
                {((preview.prior_fraud_rate || 0) * 100).toFixed(0)}%
              </span>
            </div>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.red_threshold')}</span>
              <span style={{ ...styles.previewValue, color: '#dc2626' }}>
                ≥ {((preview.red_threshold || 0) * 100).toFixed(0)}%
              </span>
            </div>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.yellow_threshold')}</span>
              <span style={{ ...styles.previewValue, color: '#d97706' }}>
                ≥ {((preview.yellow_threshold || 0) * 100).toFixed(0)}%
              </span>
            </div>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.evidentiary_standard')}</span>
              <span style={{ fontSize: 13, fontWeight: 500, color: '#334155' }}>
                {t(`evidence_standard.${preview.evidentiary_standard}`) ||
                  STANDARD_LABELS[preview.evidentiary_standard] ||
                  preview.evidentiary_standard}
              </span>
            </div>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.fdr_alpha')}</span>
              <span style={styles.previewValue}>
                {selectedPreset?.fdr_alpha || profile?.detection_profile?.fdr_alpha || 0.05}
              </span>
            </div>
            <div style={styles.previewItem}>
              <span style={styles.previewLabel}>{t('admin.max_flags_per_1k')}</span>
              <span style={styles.previewValue}>
                ≤ {selectedPreset?.max_flags_per_1k || profile?.detection_profile?.max_flags_per_1k || 200}
              </span>
            </div>
          </div>
        </div>

        {/* Custom overrides toggle */}
        <div style={{ marginTop: 16 }}>
          <button
            style={styles.toggleLink}
            onClick={() => setShowCustom(!showCustom)}
          >
            {showCustom ? '▾' : '▸'} {t('admin.custom_overrides')}
          </button>
        </div>

        {showCustom && (
          <div style={{ ...styles.fieldGrid, marginTop: 16 }}>
            <div style={styles.field}>
              <label style={styles.label}>{t('admin.prior_fraud_rate')} (0.01–0.50)</label>
              <input
                style={styles.input}
                type="number"
                min={0.01}
                max={0.50}
                step={0.01}
                placeholder={selectedPreset?.prior_fraud_rate?.toString() || '0.10'}
                value={form.prior_fraud_rate ?? ''}
                onChange={e => setForm(p => ({
                  ...p,
                  prior_fraud_rate: e.target.value ? parseFloat(e.target.value) : null,
                }))}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>{t('admin.red_threshold')} (0.10–0.99)</label>
              <input
                style={styles.input}
                type="number"
                min={0.10}
                max={0.99}
                step={0.01}
                placeholder={selectedPreset?.red_threshold?.toString() || '0.65'}
                value={form.red_threshold ?? ''}
                onChange={e => setForm(p => ({
                  ...p,
                  red_threshold: e.target.value ? parseFloat(e.target.value) : null,
                }))}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>{t('admin.yellow_threshold')} (0.05–0.90)</label>
              <input
                style={styles.input}
                type="number"
                min={0.05}
                max={0.90}
                step={0.01}
                placeholder={selectedPreset?.yellow_threshold?.toString() || '0.35'}
                value={form.yellow_threshold ?? ''}
                onChange={e => setForm(p => ({
                  ...p,
                  yellow_threshold: e.target.value ? parseFloat(e.target.value) : null,
                }))}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Save ───────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <button
          style={styles.button('primary')}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? t('admin.saving') : t('admin.save_profile')}
        </button>

        <button
          style={styles.button('secondary')}
          onClick={() => handlePresetChange(form.institution_profile)}
          disabled={saving}
        >
          {t('admin.reset_to_preset')}
        </button>
      </div>

      {saveStatus && (
        <div style={styles.status(saveStatus)}>
          {saveStatus === 'success' ? t('admin.saved_success') : t('admin.saved_error')}
        </div>
      )}

      {/* ── Legal disclaimer ───────────────────────────────────────── */}
      <div style={styles.disclaimer}>
        ⚖️ {t('legal.risk_indicator_full')}
      </div>
    </div>
  );
}
