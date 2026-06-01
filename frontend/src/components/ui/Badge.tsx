import type { ReactNode } from 'react';

type Variant = 'neutral' | 'accent' | 'positive' | 'negative';

const VARIANTS: Record<Variant, string> = {
  neutral: 'bg-surface-soft text-ink-soft',
  accent: 'bg-clay-wash text-clay-ink',
  positive: 'bg-positive/10 text-positive',
  negative: 'bg-negative/10 text-negative',
};

interface BadgeProps {
  children: ReactNode;
  variant?: Variant;
  className?: string;
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
