import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { getIcon } from '@/components/ui/icons';

export type MetricTone = 'neutral' | 'info' | 'warning' | 'critical' | 'healthy';

const TONE: Record<MetricTone, { fg: string; bg: string }> = {
  neutral: { fg: 'text-ink-700', bg: 'bg-slate-100 text-ink-500' },
  info: { fg: 'text-info', bg: 'bg-info-soft text-info' },
  warning: { fg: 'text-warning', bg: 'bg-warning-soft text-warning' },
  critical: { fg: 'text-critical', bg: 'bg-critical-soft text-critical' },
  healthy: { fg: 'text-healthy', bg: 'bg-healthy-soft text-healthy' },
};

interface MetricCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  icon?: string;
  tone?: MetricTone;
  hint?: ReactNode;
  delta?: { value: string; direction: 'up' | 'down'; positive?: boolean };
  className?: string;
}

/** Concise operational metric tile. */
export function MetricCard({
  label,
  value,
  unit,
  icon,
  tone = 'neutral',
  hint,
  delta,
  className,
}: MetricCardProps) {
  const t = TONE[tone];
  const Icon = icon ? getIcon(icon) : null;
  const DeltaIcon = delta
    ? getIcon(delta.direction === 'up' ? 'arrow-up-right' : 'arrow-down-right')
    : null;
  const deltaColor = delta
    ? delta.positive
      ? 'text-healthy'
      : 'text-critical'
    : '';

  return (
    <div
      className={cn(
        'rounded-md border border-border-subtle bg-surface px-4 py-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]',
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
          {label}
        </span>
        {Icon ? (
          <span className={cn('grid h-6 w-6 place-items-center rounded', t.bg)}>
            <Icon size={13} strokeWidth={2.2} />
          </span>
        ) : null}
      </div>

      <div className="mt-2 flex items-baseline gap-1.5">
        <span className={cn('tnum text-[26px] font-semibold leading-none tracking-tight', t.fg)}>
          {value}
        </span>
        {unit ? <span className="text-[12px] font-medium text-ink-400">{unit}</span> : null}
      </div>

      <div className="mt-1.5 flex items-center gap-2">
        {delta && DeltaIcon ? (
          <span className={cn('flex items-center gap-0.5 text-[11px] font-semibold', deltaColor)}>
            <DeltaIcon size={12} />
            {delta.value}
          </span>
        ) : null}
        {hint ? <span className="text-[11px] text-ink-400">{hint}</span> : null}
      </div>
    </div>
  );
}
