export function fmt(n) {
  if (n == null) return '\u2014';
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
  return '$' + n.toLocaleString();
}

export function fmtNum(n) {
  if (n == null) return '\u2014';
  return n.toLocaleString();
}

export function fmtPct(n) {
  if (n == null) return '\u2014';
  return n.toFixed(1) + '%';
}

export function tierClass(tier) {
  return { RED: 'red', YELLOW: 'yellow', GREEN: 'green', GRAY: 'gray' }[tier] || 'gray';
}

export function confColor(score) {
  if (score >= 70) return 'red';
  if (score >= 40) return 'amber';
  return 'green';
}

// Named aliases for clarity
export const formatCurrency = fmt;
export const formatPercentage = fmtPct;

export function formatDate(iso) {
  if (!iso) return '\u2014';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}
