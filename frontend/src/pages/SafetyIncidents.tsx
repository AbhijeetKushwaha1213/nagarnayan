import {
  CategoryWorkspace,
  countAll,
  countCritical,
  countNew,
  countResolved,
} from '@/components/workspace/CategoryWorkspace';

export function SafetyIncidents() {
  return (
    <CategoryWorkspace
      categories={['safety', 'incident']}
      tableTitle="Safety & Incident Log"
      tableIcon="shield-alert"
      showFleet
      metrics={[
        { label: 'Open Events', compute: countAll, icon: 'shield-alert', tone: 'neutral' },
        { label: 'Critical', compute: countCritical, icon: 'siren', tone: 'critical' },
        { label: 'New', compute: countNew, icon: 'activity', tone: 'warning', hint: 'last 30 min' },
        { label: 'Resolved', compute: countResolved, icon: 'check-circle', tone: 'healthy' },
      ]}
    />
  );
}
