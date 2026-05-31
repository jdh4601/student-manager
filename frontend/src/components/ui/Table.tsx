import type { ReactNode } from 'react';

/**
 * Shared table styling for the warm-clay design system. Use the class
 * constants on a regular `<table>` so bespoke cells (selects, badges,
 * buttons) stay flexible, while the card frame / header / row rhythm
 * are unified across pages.
 */
export const tableHeadClass =
  'border-b border-line bg-surface-soft text-xs font-semibold uppercase tracking-wide text-muted';
export const tableBodyClass = 'divide-y divide-line text-ink';
export const tableRowClass =
  'even:bg-surface-soft/40 transition-colors hover:bg-clay-wash/40';
export const thClass = 'px-4 py-3 text-center font-semibold';
export const tdClass = 'px-4 py-3 text-center align-middle';

interface TableCardProps {
  children: ReactNode;
  className?: string;
}

/** Card frame for a flush table (rounded-2xl, hairline border, soft shadow). */
export function TableCard({ children, className = '' }: TableCardProps) {
  return (
    <div
      className={`overflow-x-auto rounded-2xl border border-line bg-surface shadow-card ${className}`}
    >
      {children}
    </div>
  );
}
