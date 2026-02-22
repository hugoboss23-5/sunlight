/**
 * SUNLIGHT UI Components — Language Selector & Legal Disclaimer
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES, useLanguage } from '../i18n/i18n';

// ─── Language Selector ─────────────────────────────────────────────────

/**
 * Dropdown language selector for the user menu.
 * Changes language at runtime without page reload.
 * Persists choice to localStorage.
 *
 * Usage:
 *   <LanguageSelector />
 *   <LanguageSelector compact />   // shows only language code
 */
export function LanguageSelector({ compact = false, style = {} }) {
  const { currentLanguage, changeLanguage, languages, isRTL } = useLanguage();

  const baseStyle = {
    padding: compact ? '6px 10px' : '8px 14px',
    borderRadius: 6,
    border: '1px solid #d1d5db',
    fontSize: compact ? 12 : 13,
    color: '#334155',
    background: '#ffffff',
    cursor: 'pointer',
    outline: 'none',
    fontFamily: "'DM Sans', system-ui, sans-serif",
    ...style,
  };

  return (
    <select
      value={currentLanguage.split('-')[0]}
      onChange={e => changeLanguage(e.target.value)}
      style={baseStyle}
      aria-label="Select language"
    >
      {languages.map(lang => (
        <option key={lang.code} value={lang.code}>
          {compact ? lang.code.toUpperCase() : `${lang.nativeName} (${lang.name})`}
        </option>
      ))}
    </select>
  );
}


// ─── Risk Disclaimer Banner ────────────────────────────────────────────

/**
 * Legal disclaimer component. MUST be shown on every flagged view.
 * Non-negotiable — "Risk indicator, not allegation" in every language.
 *
 * Usage:
 *   <RiskDisclaimer />
 *   <RiskDisclaimer variant="compact" />   // single line
 *   <RiskDisclaimer variant="banner" />    // full banner with explanation
 */
export function RiskDisclaimer({ variant = 'compact', style = {} }) {
  const { t } = useTranslation();

  if (variant === 'banner') {
    return (
      <div
        role="alert"
        style={{
          padding: '14px 20px',
          background: '#fffbeb',
          borderRadius: 8,
          border: '1px solid #fde68a',
          fontSize: 13,
          color: '#92400e',
          lineHeight: 1.6,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          ...style,
        }}
      >
        <span style={{ fontSize: 16, flexShrink: 0 }}>⚖️</span>
        <span>{t('legal.risk_indicator_full')}</span>
      </div>
    );
  }

  // Compact: single-line footer
  return (
    <div
      role="note"
      style={{
        padding: '8px 14px',
        background: '#fefce8',
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 500,
        color: '#a16207',
        letterSpacing: '0.02em',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        ...style,
      }}
    >
      <span>⚖️</span>
      <span>{t('legal.risk_indicator')}</span>
    </div>
  );
}


// ─── Calibration Badge ─────────────────────────────────────────────────

/**
 * Shows the active calibration profile as a badge.
 * Appears in case packets and detection reports.
 *
 * Usage:
 *   <CalibrationBadge profile={tenantProfile.detection_profile} />
 */
export function CalibrationBadge({ profile, style = {} }) {
  const { t } = useTranslation();

  if (!profile) return null;

  const standardLabel = t(`evidence_standard.${profile.evidentiary_standard}`) ||
    profile.evidentiary_standard;

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        background: '#f0f9ff',
        borderRadius: 6,
        border: '1px solid #bae6fd',
        fontSize: 11,
        color: '#0369a1',
        fontWeight: 500,
        ...style,
      }}
    >
      <span style={{ fontWeight: 700 }}>{profile.label || profile.profile_id}</span>
      <span style={{ color: '#64748b' }}>|</span>
      <span>{t('admin.prior_fraud_rate')}: {(profile.prior_fraud_rate * 100).toFixed(0)}%</span>
      <span style={{ color: '#64748b' }}>|</span>
      <span>{standardLabel}</span>
    </div>
  );
}
