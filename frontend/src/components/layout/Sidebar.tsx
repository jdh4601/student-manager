import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/dashboard', label: '대시보드', end: true },
  { to: '/analytics', label: '분석' },
  { to: '/students', label: '학생 목록' },
  { to: '/feedbacks', label: '피드백' },
  { to: '/counselings', label: '상담 기록' },
  { to: '/notifications', label: '알림' },
];

export default function Sidebar({ onToggle }: { onToggle?: () => void }) {
  return (
    <aside className="w-full p-4 space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between px-2 pb-2">
        <div className="font-extrabold text-xl tracking-tight text-gray-900 select-none whitespace-nowrap">
          ClassFlow
        </div>
        <button onClick={onToggle} className="md:hidden text-gray-500 hover:text-gray-900 p-1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
      
      <nav className="flex flex-col space-y-1 flex-1">
        {NAV_ITEMS.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => {
              if (window.innerWidth < 768 && onToggle) {
                onToggle();
              }
            }}
            className={({ isActive }) =>
              `px-4 py-2.5 rounded-lg text-sm transition-colors duration-200 whitespace-nowrap ${
                isActive 
                  ? 'bg-blue-600 text-white font-semibold shadow-sm' 
                  : 'text-gray-700 hover:bg-gray-200 font-medium'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
