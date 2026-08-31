import {
  CategoryWorkspace,
  countAll,
  countCritical,
  countNew,
  countResolved,
} from '@/components/workspace/CategoryWorkspace';

export function Infrastructure() {
  return (
    <CategoryWorkspace
      categories={['infrastructure']}
      tableTitle="Infrastructure Deficiencies"
      tableIcon="traffic-cone"
      metrics={[
        { label: 'Total Issues', compute: countAll, icon: 'traffic-cone', tone: 'neutral' },
        { label: 'High Severity', compute: countCritical, icon: 'alert-triangle', tone: 'warning' },
        { label: 'Newly Detected', compute: countNew, icon: 'activity', tone: 'info', hint: 'last 30 min' },
        { label: 'Resolved', compute: countResolved, icon: 'check-circle', tone: 'healthy' },
      ]}
    />
  );
}
