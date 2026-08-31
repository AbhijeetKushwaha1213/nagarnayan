import { useTraffic } from '@/services/hooks';
import { TRAFFIC_LEVEL_META } from '@/config/taxonomy';
import { MetricCard } from '@/components/analytics/MetricCard';
import { TrafficDensityChart, VehicleMixChart } from '@/components/analytics/charts';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { compactNumber } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';

export function TrafficIntelligence() {
  const { data, isLoading } = useTraffic();

  if (isLoading || !data) {
    return (
      <PageContainer className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px] rounded-md" />
          ))}
        </div>
        <Skeleton className="h-[320px] rounded-md" />
      </PageContainer>
    );
  }

  const peak = Math.max(...data.today.map((t) => t.density));
  const avg = Math.round(data.today.reduce((s, t) => s + t.density, 0) / data.today.length);
  const totalVehicles =
    data.vehicleMix.cars +
    data.vehicleMix.motorcycles +
    data.vehicleMix.buses +
    data.vehicleMix.trucks;

  return (
    <PageContainer className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Current Density" value={data.today.at(-1)?.density ?? 0} unit="idx" icon="gauge" tone="warning" />
        <MetricCard label="Peak Today" value={peak} unit="idx" icon="trending-up" tone="critical" hint="18:00" />
        <MetricCard label="Avg Density" value={avg} unit="idx" icon="activity" tone="info" />
        <MetricCard label="Vehicles Observed" value={compactNumber(totalVehicles)} icon="car-front" tone="neutral" hint="today" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelHeader title="Traffic Density — Today" subtitle="Aggregated across fleet observations" />
          <div className="h-[280px] p-3">
            <TrafficDensityChart data={data.today} />
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="Vehicle Classification" subtitle="Detected vehicle mix" />
          <div className="h-[280px] p-3">
            <VehicleMixChart data={data.vehicleMix} />
          </div>
        </Panel>
      </div>

      <Panel>
        <PanelHeader
          title="Congestion Hotspots"
          subtitle="Ranked by density & average delay"
          icon={(() => {
            const I = getIcon('map-pin');
            return <I size={15} />;
          })()}
        />
        <div className="divide-y divide-border-subtle">
          {data.hotspots.map((h) => {
            const meta = TRAFFIC_LEVEL_META[h.level];
            return (
              <div key={h.rank} className="flex items-center gap-4 px-4 py-3">
                <span className="tnum grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-muted text-[12px] font-bold text-ink-700">
                  {h.rank}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-ink-900">{h.location}</p>
                  <p className="text-[11px] text-ink-500">{h.zone}</p>
                </div>
                <div className="hidden w-40 sm:block">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${h.vehicleDensity}%`, backgroundColor: meta.color }}
                    />
                  </div>
                </div>
                <span className="tnum w-16 text-right text-[12px] font-semibold text-ink-700">
                  {h.avgDelayMin} min
                </span>
                <span
                  className="w-16 rounded-xs px-1.5 py-0.5 text-center text-[10px] font-bold uppercase text-white"
                  style={{ backgroundColor: meta.color }}
                >
                  {meta.label}
                </span>
              </div>
            );
          })}
        </div>
      </Panel>
    </PageContainer>
  );
}
