import { useMemo, useState } from 'react';
import { useEvents, useTrends } from '@/services/hooks';
import { CATEGORY_META } from '@/config/taxonomy';
import { CATEGORY_ORDER } from '@/mock/city';
import { MetricCard } from '@/components/analytics/MetricCard';
import { CategoryBarChart, TrendChart } from '@/components/analytics/charts';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { cn } from '@/lib/cn';

const RANGES = ['Today', 'Last 7 Days', 'Last 30 Days', 'Custom'] as const;

export function Analytics() {
  const { data: trends } = useTrends();
  const { data: events } = useEvents();
  const [range, setRange] = useState<(typeof RANGES)[number]>('Last 7 Days');

  const byCategory = useMemo(() => {
    return CATEGORY_ORDER.map((c) => ({
      name: CATEGORY_META[c].label,
      value: (events ?? []).filter((e) => e.category === c).length,
      color: CATEGORY_META[c].color,
    }));
  }, [events]);

  const topLocations = useMemo(() => {
    const map = new Map<string, number>();
    (events ?? []).forEach((e) =>
      map.set(e.location.address, (map.get(e.location.address) ?? 0) + 1),
    );
    return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [events]);

  const totalDetections = trends?.reduce(
    (s, t) => s + t.potholes + t.traffic + t.infrastructure + t.safety,
    0,
  );

  return (
    <PageContainer className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRange(r)}
            className={cn(
              'rounded-sm border px-3 py-1.5 text-[12px] font-medium transition-colors',
              range === r
                ? 'border-command-900 bg-command-900 text-white'
                : 'border-border-subtle bg-surface text-ink-600 hover:bg-surface-muted',
            )}
          >
            {r}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-ink-400">Showing aggregated fleet intelligence</span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Total Detections" value={totalDetections ?? '—'} icon="activity" tone="info" hint={range.toLowerCase()} />
        <MetricCard label="Road Defect Trend" value="+12%" icon="trending-up" tone="warning" delta={{ value: 'vs prev', direction: 'up', positive: false }} />
        <MetricCard label="Avg Resolution" value="4.2" unit="hrs" icon="clock" tone="healthy" />
        <MetricCard label="High-Risk Zones" value={topLocations.length} icon="map-pin" tone="critical" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelHeader title="Event Trends" subtitle="Detections by category over time" />
          <div className="h-[300px] p-3">
            {trends ? <TrendChart data={trends} /> : <Skeleton className="h-full" />}
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="By Category" subtitle="Current distribution" />
          <div className="h-[300px] p-3">
            <CategoryBarChart data={byCategory} />
          </div>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Most Problematic Roads" subtitle="Locations with the most detections" />
        <div className="divide-y divide-border-subtle">
          {topLocations.map(([address, count], i) => (
            <div key={address} className="flex items-center gap-4 px-4 py-2.5">
              <span className="tnum w-5 text-[12px] font-bold text-ink-400">{i + 1}</span>
              <span className="flex-1 text-[13px] font-medium text-ink-900">{address}</span>
              <div className="hidden w-48 sm:block">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-brand-500"
                    style={{ width: `${(count / topLocations[0][1]) * 100}%` }}
                  />
                </div>
              </div>
              <span className="tnum w-16 text-right text-[12px] font-semibold text-ink-700">
                {count} events
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </PageContainer>
  );
}
