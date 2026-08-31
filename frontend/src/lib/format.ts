/**
 * Time + number formatting helpers.
 * Kept framework-agnostic so they can be reused across features.
 */

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

/** "2 minutes ago" style relative timestamp from an ISO string. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  const diffMs = then - now.getTime();
  const diffSec = Math.round(diffMs / 1000);
  const abs = Math.abs(diffSec);

  if (abs < 45) return 'just now';
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour');
  return rtf.format(Math.round(diffSec / 86400), 'day');
}

/** "10:32 AM" clock label. */
export function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/** "31 Aug, 10:32 AM" */
export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    day: '2-digit',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/** 0..1 → "94%" */
export function confidencePct(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function compactNumber(n: number): string {
  return new Intl.NumberFormat('en', { notation: 'compact' }).format(n);
}
