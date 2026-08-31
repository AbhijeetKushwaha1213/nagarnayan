import { useMemo, useState } from 'react';
import { useEvents } from '@/services/hooks';
import { CATEGORY_META } from '@/config/taxonomy';
import { EventDetailPanel } from '@/components/events/EventDetailPanel';
import { SeverityBadge, StatusBadge } from '@/components/events/badges';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { PageContainer } from '@/components/layout/Page';
import { timeAgo } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';

export function Alerts() {
  const { data: events } = useEvents();
  const [selectedId, setSelectedId] = useState<string | undefined>();

  const alerts = useMemo(
    () =>
      (events ?? []).filter(
        (e) =>
          (e.severity === 'critical' || e.severity === 'high') &&
          e.status !== 'resolved' &&
          e.status !== 'dismissed',
      ),
    [events],
  );
  const selected = events?.find((e) => e.id === selectedId) ?? null;
  const Siren = getIcon('siren');

  return (
    <PageContainer>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Priority Alert Queue"
            subtitle={`${alerts.length} unresolved critical & high-severity detections`}
            icon={<Siren size={15} />}
          />
          <div className="divide-y divide-border-subtle">
            {alerts.map((e) => {
              const cat = CATEGORY_META[e.category];
              const Icon = getIcon(cat.icon);
              return (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => setSelectedId(e.id)}
                  className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-muted ${
                    e.id === selectedId ? 'bg-brand-50/70' : ''
                  }`}
                >
                  <span
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-md"
                    style={{ backgroundColor: `${cat.color}14`, color: cat.color }}
                  >
                    <Icon size={16} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-ink-900">{e.title}</span>
                      <SeverityBadge severity={e.severity} />
                    </div>
                    <p className="text-[11px] text-ink-500">
                      {e.location.address} · {e.source.busLabel}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <StatusBadge status={e.status} />
                    <span className="tnum text-[10px] text-ink-400">{timeAgo(e.timestamp)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </Panel>

        <Panel className="h-[560px] overflow-hidden">
          <EventDetailPanel event={selected} onClose={() => setSelectedId(undefined)} />
        </Panel>
      </div>
    </PageContainer>
  );
}
