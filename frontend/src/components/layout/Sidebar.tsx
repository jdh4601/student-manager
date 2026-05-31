import { NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  icon: ReactNode;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

const I = ({ d }: { d: string }) => (
  <svg
    className="h-[18px] w-[18px] shrink-0"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    <path d={d} />
  </svg>
);

const NAV_GROUPS: NavGroup[] = [
  {
    heading: '개요',
    items: [
      {
        to: '/dashboard',
        label: '대시보드',
        end: true,
        icon: <I d="M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z" />,
      },
    ],
  },
  {
    heading: '관리',
    items: [
      {
        to: '/students',
        label: '학생 목록',
        icon: <I d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm13 10v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" />,
      },
      {
        to: '/feedbacks',
        label: '피드백',
        icon: <I d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" />,
      },
      {
        to: '/counselings',
        label: '상담 기록',
        icon: <I d="M9 11H5a2 2 0 0 0-2 2v7h6m4-9h6a2 2 0 0 1 2 2v7h-6m-6 0h6m-6 0V7a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v13" />,
      },
      {
        to: '/notifications',
        label: '알림',
        icon: <I d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />,
      },
    ],
  },
];

export default function Sidebar({ onToggle }: { onToggle?: () => void }) {
  return (
    <aside className="flex h-full w-full flex-col px-3 py-5">
      <div className="mb-5 flex items-center justify-between px-3">
        <div className="flex items-center gap-2 select-none">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-clay text-sm font-bold text-white">
            C
          </span>
          <span className="text-[17px] font-bold tracking-tight text-ink">ClassFlow</span>
        </div>
        <button
          onClick={onToggle}
          className="p-1 text-muted hover:text-ink md:hidden"
          aria-label="사이드바 닫기"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.heading} className="flex flex-col gap-1">
            <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
              {group.heading}
            </p>
            {group.items.map(({ to, label, end, icon }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => {
                  if (window.innerWidth < 768 && onToggle) onToggle();
                }}
                className={({ isActive }) =>
                  `group flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors duration-150 ${
                    isActive
                      ? 'bg-surface font-semibold text-ink shadow-pill'
                      : 'font-medium text-ink-soft hover:bg-surface/70 hover:text-ink'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span className={isActive ? 'text-clay' : 'text-muted group-hover:text-ink-soft'}>
                      {icon}
                    </span>
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
