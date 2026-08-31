/**
 * Primary navigation model. Route components are lazy-mapped in App.tsx.
 * `icon` values are lucide-react component names resolved by the Sidebar.
 */
export interface NavItem {
  label: string;
  to: string;
  icon: string;
  /** optional short group heading rendered above this item */
  section?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Command Center', to: '/', icon: 'layout-dashboard', section: 'Operations' },
  { label: 'Live Map', to: '/map', icon: 'map' },
  { label: 'Road Intelligence', to: '/road', icon: 'construction', section: 'Intelligence' },
  { label: 'Traffic Intelligence', to: '/traffic', icon: 'car-front' },
  { label: 'Infrastructure', to: '/infrastructure', icon: 'traffic-cone' },
  { label: 'Safety & Incidents', to: '/safety', icon: 'shield-alert' },
  { label: 'Fleet Coverage', to: '/fleet', icon: 'bus', section: 'Fleet & Insights' },
  { label: 'Analytics', to: '/analytics', icon: 'line-chart' },
  { label: 'Alerts', to: '/alerts', icon: 'bell' },
  { label: 'System Settings', to: '/settings', icon: 'settings', section: 'System' },
];
