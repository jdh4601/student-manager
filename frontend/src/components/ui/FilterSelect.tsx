import type { ReactNode } from 'react';

interface Option {
  value: string;
  label: string;
}

interface FilterSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder: string;
  ariaLabel: string;
  disabled?: boolean;
  icon?: ReactNode;
}

/** Pill-shaped, chevron-suffixed select styled to match the warm-clay system. */
export function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
  ariaLabel,
  disabled = false,
  icon,
}: FilterSelectProps) {
  return (
    <div
      className={`group relative inline-flex items-center rounded-full border border-line bg-surface pl-3.5 pr-9 shadow-pill transition-colors ${
        disabled ? 'opacity-50' : 'hover:border-clay-soft'
      }`}
    >
      {icon && <span className="mr-1.5 text-muted">{icon}</span>}
      <select
        aria-label={ariaLabel}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer appearance-none bg-transparent py-2 text-sm font-medium text-ink focus:outline-none disabled:cursor-not-allowed"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-3.5 h-3.5 w-3.5 text-muted"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        aria-hidden
      >
        <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}
