import {
  CategoryWorkspace,
  countAll,
  countCritical,
  countNew,
  countResolved,
} from '@/components/workspace/CategoryWorkspace';

export function RoadIntelligence() {
  return (
    <CategoryWorkspace
      categories={['road', 'waterlogging']}
      tableTitle="Road Defect Register"
      tableIcon="construction"
      metrics={[
        { label: 'Total Defects', compute: countAll, icon: 'construction', tone: 'neutral' },
        { label: 'Critical', compute: countCritical, icon: 'siren', tone: 'critical' },
        { label: 'Newly Detected', compute: countNew, icon: 'activity', tone: 'warning', hint: 'last 30 min' },
        { label: 'Resolved', compute: countResolved, icon: 'check-circle', tone: 'healthy' },
      ]}
    />
  );
}
