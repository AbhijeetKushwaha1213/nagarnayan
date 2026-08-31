import { SEVERITY_META, STATUS_META } from '@/config/taxonomy';
import type { EventStatus, Severity } from '@/types/domain';
import { cn } from '@/lib/cn';

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
  /** dot-only compact form */
  dot?: boolean;
}

export function SeverityBadge({ severity, className, dot }: SeverityBadgeProps) {
  const meta = SEVERITY_META[severity];
  if (dot) {
    return (
      <span
        className={cn('inline-block h-2 w-2 rounded-full', className)}
        style={{ backgroundColor: meta.color }}
        title={meta.label}
      />
    );
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-xs px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
        className,
      )}
      style={{ color: meta.color, backgroundColor: meta.soft }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
      {meta.label}
    </span>
  );
}

export function StatusBadge({
  status,
  className,
}: {
  status: EventStatus;
  className?: string;
}) {
  const meta = STATUS_META[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-xs px-1.5 py-0.5 text-[10px] font-medium',
        className,
      )}
      style={{ color: meta.color, backgroundColor: meta.soft }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
      {meta.label}
    </span>
  );
}
