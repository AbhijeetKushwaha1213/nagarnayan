import type { ReactNode } from 'react';
import { getIcon } from '@/components/ui/icons';
import { cn } from '@/lib/cn';

export function PageContainer({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn('p-5', className)}>{children}</div>;
}

interface SectionTitleProps {
  title: string;
  hint?: string;
  action?: ReactNode;
  className?: string;
}

export function SectionTitle({ title, hint, action, className }: SectionTitleProps) {
  return (
    <div className={cn('mb-3 flex items-end justify-between gap-3', className)}>
      <div>
        <h2 className="text-[13px] font-semibold uppercase tracking-wide text-ink-700">
          {title}
        </h2>
        {hint ? <p className="mt-0.5 text-[12px] text-ink-500">{hint}</p> : null}
      </div>
      {action}
    </div>
  );
}

/** Placeholder for modules that share the shell but aren't built out yet. */
export function ModuleStub({
  icon,
  title,
  description,
  bullets,
}: {
  icon: string;
  title: string;
  description: string;
  bullets: string[];
}) {
  const Icon = getIcon(icon);
  return (
    <PageContainer>
      <div className="mx-auto mt-6 max-w-2xl rounded-md border border-dashed border-border-strong bg-surface p-8 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-lg bg-brand-50 text-brand-600">
          <Icon size={26} />
        </span>
        <h2 className="mt-4 text-[18px] font-semibold tracking-tight text-ink-900">
          {title}
        </h2>
        <p className="mx-auto mt-1.5 max-w-md text-[13px] leading-relaxed text-ink-500">
          {description}
        </p>
        <div className="mx-auto mt-5 max-w-md space-y-2 text-left">
          {bullets.map((b) => (
            <div
              key={b}
              className="flex items-start gap-2 rounded-sm bg-surface-muted px-3 py-2 text-[12px] text-ink-700"
            >
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
              {b}
            </div>
          ))}
        </div>
        <div className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-warning-soft px-3 py-1 text-[11px] font-semibold text-warning">
          <span className="h-1.5 w-1.5 rounded-full bg-warning" />
          Module coming online
        </div>
      </div>
    </PageContainer>
  );
}
