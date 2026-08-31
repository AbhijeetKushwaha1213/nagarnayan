import L from 'leaflet';
import { CATEGORY_META, SEVERITY_META } from '@/config/taxonomy';
import type { EventCategory, Severity } from '@/types/domain';

/**
 * Leaflet divIcon builders. Markers are colored by category, sized by severity,
 * and critical detections pulse so operators can triage at a glance.
 */

const SIZE: Record<Severity, number> = {
  critical: 20,
  high: 18,
  medium: 15,
  low: 13,
};

export function eventIcon(category: EventCategory, severity: Severity): L.DivIcon {
  const color = CATEGORY_META[category].color;
  const size = SIZE[severity];
  const pulse =
    severity === 'critical'
      ? `<span class="nn-marker__pulse" style="--pulse:${SEVERITY_META.critical.color}88"></span>`
      : '';
  return L.divIcon({
    className: 'nn-marker',
    html: `
      <div style="position:relative;width:${size}px;height:${size}px;">
        ${pulse}
        <span class="nn-marker__dot" style="background:${color}"></span>
      </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export function busIcon(heading: number, active: boolean): L.DivIcon {
  const color = active ? '#22d3ee' : '#64748b';
  const size = 26;
  return L.divIcon({
    className: 'nn-bus-marker',
    html: `
      <div style="width:${size}px;height:${size}px;position:relative;">
        <div style="
          position:absolute;inset:0;border-radius:6px;
          background:${color}1f;border:1.5px solid ${color};
          box-shadow:0 2px 8px -2px rgba(0,0,0,.6);
          display:grid;place-items:center;">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
               style="transform:rotate(${heading}deg);color:${color}">
            <path d="M12 3 L18 20 L12 16 L6 20 Z" fill="currentColor"/>
          </svg>
        </div>
      </div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}
