import { ModuleStub } from '@/components/layout/Page';

export function Settings() {
  return (
    <ModuleStub
      icon="settings"
      title="System Settings"
      description="Configure detection thresholds, camera assignments, alert routing and integration with the central FastAPI backend."
      bullets={[
        'AI confidence thresholds per event category',
        'Alert routing to maintenance & traffic departments',
        'Fleet & camera registration / health policies',
        'Backend API + WebSocket connection settings',
        'Operator roles and access control',
      ]}
    />
  );
}
