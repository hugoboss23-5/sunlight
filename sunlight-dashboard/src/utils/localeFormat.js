/**
 * SUNLIGHT Locale Formatting Utilities
 * ======================================
 * All formatting uses browser-native Intl APIs for correctness.
 * No manual formatting logic — the browser handles locale rules.
 *
 * Every function takes locale/currency/timezone from the tenant profile,
 * ensuring consistent formatting across the entire UI.
 *
 * Usage:
 *   import { formatCurrency, formatDate, formatNumber, formatPercent } from './localeFormat';
 *
 *   formatCurrency(1500000, 'XOF', 'fr-FR')  → "1 500 000 XOF"
 *   formatCurrency(1500000, 'USD', 'en-US')  → "$1,500,000.00"
 *   formatDate(new Date(), 'fr-FR', 'Africa/Ouagadougou')  → "22 févr. 2026"
 *   formatPercent(0.72, 'en-US')  → "72%"
 */

// ---------------------------------------------------------------------------
// Currency
// ---------------------------------------------------------------------------

/**
 * Format a monetary amount in the tenant's currency and locale.
 *
 * @param {number} amount - The value to format
 * @param {string} currency - ISO 4217 code (e.g. 'USD', 'XOF', 'EUR', 'NGN')
 * @param {string} locale - BCP-47 tag (e.g. 'en-US', 'fr-FR')
 * @param {object} options - Override Intl.NumberFormat options
 * @returns {string} Formatted currency string
 */
export function formatCurrency(amount, currency = 'USD', locale = 'en-US', options = {}) {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
      ...options,
    }).format(amount);
  } catch {
    // Fallback if Intl doesn't support the currency
    return `${currency} ${amount.toLocaleString(locale)}`;
  }
}

/**
 * Format currency with full precision (for contract values in case packets).
 */
export function formatCurrencyPrecise(amount, currency = 'USD', locale = 'en-US') {
  return formatCurrency(amount, currency, locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Compact currency format for dashboards (e.g. "$1.5M", "1,5 Mrd XOF").
 */
export function formatCurrencyCompact(amount, currency = 'USD', locale = 'en-US') {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      notation: 'compact',
      compactDisplay: 'short',
      maximumSignificantDigits: 3,
    }).format(amount);
  } catch {
    return formatCurrency(amount, currency, locale);
  }
}


// ---------------------------------------------------------------------------
// Numbers
// ---------------------------------------------------------------------------

/**
 * Format a number in the tenant's locale.
 *
 * @param {number} value
 * @param {string} locale - BCP-47 tag
 * @param {object} options - Intl.NumberFormat options
 * @returns {string}
 */
export function formatNumber(value, locale = 'en-US', options = {}) {
  return new Intl.NumberFormat(locale, options).format(value);
}

/**
 * Format a number with compact notation (e.g. "42.6K", "1.2M").
 */
export function formatNumberCompact(value, locale = 'en-US') {
  return new Intl.NumberFormat(locale, {
    notation: 'compact',
    compactDisplay: 'short',
    maximumSignificantDigits: 3,
  }).format(value);
}


// ---------------------------------------------------------------------------
// Percentages
// ---------------------------------------------------------------------------

/**
 * Format a decimal as a percentage.
 *
 * @param {number} value - Decimal (e.g. 0.72 → "72%")
 * @param {string} locale - BCP-47 tag
 * @param {number} decimals - Decimal places (default 0)
 * @returns {string}
 */
export function formatPercent(value, locale = 'en-US', decimals = 0) {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a percentage that's already in 0-100 range (e.g. 72 → "72%").
 * Use this for values that come from the API as whole numbers.
 */
export function formatPercentWhole(value, locale = 'en-US', decimals = 0) {
  return formatPercent(value / 100, locale, decimals);
}


// ---------------------------------------------------------------------------
// Dates
// ---------------------------------------------------------------------------

/**
 * Format a date in the tenant's locale and timezone.
 *
 * @param {Date|string|number} date - Date value
 * @param {string} locale - BCP-47 tag
 * @param {string} timezone - IANA timezone (e.g. 'Africa/Ouagadougou')
 * @param {object} options - Override Intl.DateTimeFormat options
 * @returns {string}
 */
export function formatDate(date, locale = 'en-US', timezone = 'UTC', options = {}) {
  const d = date instanceof Date ? date : new Date(date);
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeZone: timezone,
    ...options,
  }).format(d);
}

/**
 * Format date with time.
 */
export function formatDateTime(date, locale = 'en-US', timezone = 'UTC') {
  const d = date instanceof Date ? date : new Date(date);
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timezone,
  }).format(d);
}

/**
 * Format date as short (e.g. "22/02/2026" or "02/22/2026").
 */
export function formatDateShort(date, locale = 'en-US', timezone = 'UTC') {
  const d = date instanceof Date ? date : new Date(date);
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'short',
    timeZone: timezone,
  }).format(d);
}

/**
 * Format date as ISO string (for audit trails — always UTC, no locale).
 */
export function formatDateISO(date) {
  const d = date instanceof Date ? date : new Date(date);
  return d.toISOString();
}

/**
 * Relative date formatting (e.g. "2 days ago", "il y a 3 jours").
 */
export function formatDateRelative(date, locale = 'en-US') {
  const d = date instanceof Date ? date : new Date(date);
  const now = new Date();
  const diffMs = now - d;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  try {
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
    if (diffDays === 0) return rtf.format(0, 'day');        // "today"
    if (diffDays === 1) return rtf.format(-1, 'day');       // "yesterday"
    if (diffDays < 7) return rtf.format(-diffDays, 'day');  // "3 days ago"
    if (diffDays < 30) return rtf.format(-Math.floor(diffDays / 7), 'week');
    if (diffDays < 365) return rtf.format(-Math.floor(diffDays / 30), 'month');
    return rtf.format(-Math.floor(diffDays / 365), 'year');
  } catch {
    // Fallback for browsers without RelativeTimeFormat
    return formatDate(d, locale);
  }
}


// ---------------------------------------------------------------------------
// Tenant Context Helper
// ---------------------------------------------------------------------------

/**
 * Create a bound formatter set from tenant profile.
 * This eliminates the need to pass locale/currency/timezone to every call.
 *
 * Usage:
 *   const fmt = createTenantFormatter(tenantProfile);
 *   fmt.currency(1500000)       → "$1,500,000"
 *   fmt.date(new Date())        → "Feb 22, 2026"
 *   fmt.percent(0.72)           → "72%"
 *   fmt.number(42593)           → "42,593"
 *
 * @param {object} tenantProfile - Tenant profile with ui_locale
 * @returns {object} Bound formatting functions
 */
export function createTenantFormatter(tenantProfile) {
  const locale = tenantProfile?.ui_locale?.language_tag || 'en-US';
  const currency = tenantProfile?.jurisdiction?.preferred_currency || 'USD';
  const timezone = tenantProfile?.ui_locale?.timezone || 'UTC';

  return {
    // Currency
    currency: (amount, opts) => formatCurrency(amount, currency, locale, opts),
    currencyPrecise: (amount) => formatCurrencyPrecise(amount, currency, locale),
    currencyCompact: (amount) => formatCurrencyCompact(amount, currency, locale),

    // Numbers
    number: (value, opts) => formatNumber(value, locale, opts),
    numberCompact: (value) => formatNumberCompact(value, locale),

    // Percentages
    percent: (value, decimals) => formatPercent(value, locale, decimals),
    percentWhole: (value, decimals) => formatPercentWhole(value, locale, decimals),

    // Dates
    date: (date, opts) => formatDate(date, locale, timezone, opts),
    dateTime: (date) => formatDateTime(date, locale, timezone),
    dateShort: (date) => formatDateShort(date, locale, timezone),
    dateRelative: (date) => formatDateRelative(date, locale),
    dateISO: (date) => formatDateISO(date),

    // Raw values for components that need them
    locale,
    currency: currency,
    timezone,
  };
}
