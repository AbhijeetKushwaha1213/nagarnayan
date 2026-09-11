/**
 * Primary navigation model. Route components are mapped in App.tsx.
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
  { label: 'Dashboard', to: '/', icon: 'layout-dashboard', section: 'Operations' },
  { label: 'Urban Events', to: '/events', icon: 'alert-triangle' },
  { label: 'Alert Queue', to: '/alerts', icon: 'bell' },
  { label: 'Fleet & Cameras', to: '/fleet', icon: 'bus' },
  { label: 'GIS Event Map', to: '/map', icon: 'map', section: 'Mapping' },
  { label: 'System Settings', to: '/settings', icon: 'settings', section: 'System' },
];
