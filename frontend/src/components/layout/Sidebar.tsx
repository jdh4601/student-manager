import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: '대시보드', end: true },
  { to: '/students', label: '학생 목록' },
  { to: '/feedbacks', label: '피드백' },
  { to: '/counselings', label: '상담 기록' },
  { to: '/notifications', label: '알림' },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-100 p-4 space-y-2 min-h-screen">
      <div className="font-bold text-gray-800 mb-4">Student Manager</div>
      <nav className="flex flex-col space-y-1">
        {NAV_ITEMS.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }: { isActive: boolean }) =>
              `px-3 py-2 rounded text-sm ${isActive ? 'bg-indigo-600 text-white font-medium' : 'text-gray-700 hover:bg-gray-200'}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
