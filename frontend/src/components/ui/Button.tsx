import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

const VARIANTS: Record<Variant, string> = {
  primary: 'border border-transparent bg-clay text-white hover:bg-clay-ink',
  ghost: 'border border-line bg-surface text-ink hover:bg-surface-soft',
  danger: 'border border-negative/30 bg-surface text-negative hover:bg-negative/10',
};

const SIZES: Record<Size, string> = {
  sm: 'px-2.5 py-1.5 text-sm',
  md: 'px-3.5 py-2 text-sm',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Optional leading icon (svg). */
  icon?: ReactNode;
}

/** Shared button for the warm-clay design system. rounded-lg, clay primary. */
export function Button({
  variant = 'ghost',
  size = 'sm',
  icon,
  className = '',
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-clay-soft disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
