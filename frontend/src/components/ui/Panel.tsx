import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

/** Base content surface — the primary building block of the light dashboard. */
export function Panel({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-md border border-border-subtle bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)]',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

interface PanelHeaderProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function PanelHeader({
  title,
  subtitle,
  icon,
  action,
  className,
}: PanelHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3',
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        {icon ? <span className="text-ink-400">{icon}</span> : null}
        <div className="min-w-0">
          <h3 className="truncate text-[13px] font-semibold tracking-tight text-ink-900">
            {title}
          </h3>
          {subtitle ? (
            <p className="truncate text-[11px] text-ink-500">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
