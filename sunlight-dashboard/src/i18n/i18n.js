/**
 * SUNLIGHT i18n Configuration
 * ============================
 * Uses i18next + react-i18next for full localization.
 *
 * Architecture:
 * - Translation files in /i18n/locales/<lang>.json
 * - Adding a new language: drop a JSON file, add to SUPPORTED_LANGUAGES
 * - Runtime switching: call changeLanguage(lang) — no reload needed
 * - RTL: detected from language tag, applied via dir attribute on <html>
 * - Fallback: en (English)
 *
 * Usage in components:
 *   import { useTranslation } from 'react-i18next';
 *   const { t } = useTranslation();
 *   <p>{t('legal.risk_indicator')}</p>
 *   <p>{t('risk_inbox.showing', { count: 42, total: 1000 })}</p>
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Translation assets
import en from './locales/en.json';
import fr from './locales/fr.json';
import ar from './locales/ar.json';
import es from './locales/es.json';

// ---------------------------------------------------------------------------
// Supported Languages
// ---------------------------------------------------------------------------
// To add a new language:
// 1. Create /i18n/locales/<code>.json (copy en.json as template)
// 2. Add the import above
// 3. Add entry to SUPPORTED_LANGUAGES and resources below
// That's it. No other code changes needed.

export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English',  nativeName: 'English',   dir: 'ltr' },
  { code: 'fr', name: 'French',   nativeName: 'Français',  dir: 'ltr' },
  { code: 'ar', name: 'Arabic',   nativeName: 'العربية',   dir: 'rtl' },
  { code: 'es', name: 'Spanish',  nativeName: 'Español',   dir: 'ltr' },
  // Future:
  // { code: 'pt', name: 'Portuguese', nativeName: 'Português', dir: 'ltr' },
  // { code: 'zh', name: 'Chinese',    nativeName: '中文',      dir: 'ltr' },
];

// RTL language codes
const RTL_LANGUAGES = new Set(['ar', 'he', 'fa', 'ur', 'ps', 'dv', 'ku', 'sd']);

/**
 * Check if a language code is RTL.
 */
export function isRTL(langCode) {
  const primary = langCode.split('-')[0].toLowerCase();
  return RTL_LANGUAGES.has(primary);
}

/**
 * Apply document direction based on language.
 * Call this whenever language changes.
 */
export function applyDocumentDirection(langCode) {
  const dir = isRTL(langCode) ? 'rtl' : 'ltr';
  document.documentElement.setAttribute('dir', dir);
  document.documentElement.setAttribute('lang', langCode);
}

// ---------------------------------------------------------------------------
// i18next Initialization
// ---------------------------------------------------------------------------

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
      ar: { translation: ar },
      es: { translation: es },
    },

    // Default language
    lng: 'en',
    fallbackLng: 'en',

    // Namespace config
    defaultNS: 'translation',

    // Interpolation
    interpolation: {
      escapeValue: false, // React already escapes
    },

    // Key handling
    keySeparator: '.',     // Nested keys: 'legal.risk_indicator'
    nsSeparator: false,    // Disable namespace separator

    // React-specific
    react: {
      useSuspense: false,  // Don't suspend on missing translations
    },

    // Debug (disable in production)
    debug: false,
  });

// Apply initial direction
applyDocumentDirection(i18n.language);

// Update direction on language change
i18n.on('languageChanged', (lng) => {
  applyDocumentDirection(lng);
});

export default i18n;


// ---------------------------------------------------------------------------
// Language Switcher Hook
// ---------------------------------------------------------------------------

/**
 * Hook for changing the UI language at runtime.
 *
 * Usage:
 *   const { currentLanguage, changeLanguage, languages } = useLanguage();
 *   <select onChange={e => changeLanguage(e.target.value)}>
 *     {languages.map(l => <option key={l.code} value={l.code}>{l.nativeName}</option>)}
 *   </select>
 */
export function useLanguage() {
  return {
    currentLanguage: i18n.language,
    changeLanguage: (code) => {
      i18n.changeLanguage(code);
      // Persist to localStorage for user preference
      try { localStorage.setItem('sunlight_language', code); } catch {}
    },
    languages: SUPPORTED_LANGUAGES,
    isRTL: isRTL(i18n.language),
  };
}

/**
 * Initialize language from tenant profile or user preference.
 * Call once on app load.
 *
 * Priority: user override > tenant default > browser > en
 */
export function initLanguageFromProfile(tenantLanguageTag) {
  // Check user override
  let saved;
  try { saved = localStorage.getItem('sunlight_language'); } catch {}

  const lang = saved || tenantLanguageTag?.split('-')[0] || 'en';

  if (SUPPORTED_LANGUAGES.some(l => l.code === lang)) {
    i18n.changeLanguage(lang);
  }
}
