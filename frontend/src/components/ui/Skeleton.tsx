import { cn } from '@/lib/cn';

/** Small skeleton block for loading states. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded bg-slate-200/80', className)}
    />
  );
}
