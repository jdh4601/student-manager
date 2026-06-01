import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  /** Render a small clay accent tick above the value. */
  accent?: boolean;
}

export function StatCard({ label, value, hint, accent = false }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-line bg-surface px-5 py-4 shadow-card">
      <div className="flex items-center gap-2">
        {accent && <span className="h-1.5 w-1.5 rounded-full bg-clay" aria-hidden />}
        <span className="text-xs font-medium uppercase tracking-wide text-muted">
          {label}
        </span>
      </div>
      <div className="mt-2 font-display text-3xl font-semibold leading-none tracking-tight text-ink tnum">
        {value}
      </div>
      {hint && <div className="mt-1.5 text-xs text-ink-soft">{hint}</div>}
    </div>
  );
}
