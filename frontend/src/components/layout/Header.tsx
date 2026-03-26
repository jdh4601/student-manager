import { useAuthStore } from '../../stores/authStore';
import { logout } from '../../api/auth';
import NotificationBell from '../notifications/NotificationBell';

export default function Header({ onToggleSidebar }: { onToggleSidebar?: () => void }) {
  const user = useAuthStore((s) => s.user);
  const doLogout = useAuthStore((s) => s.logout);
  return (
    <header className="h-12 border-b flex items-center justify-between px-4 gap-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="md:hidden p-1.5 rounded border text-gray-600"
          aria-label="메뉴 열기"
          onClick={onToggleSidebar}
        >
          ☰
        </button>
        <div className="font-semibold truncate">Student Manager</div>
      </div>
      <div className="flex items-center gap-3">
        <NotificationBell />
        <span className="text-sm text-gray-600">{user?.name}</span>
        <button
          className="text-sm px-2 py-1 border rounded"
          onClick={async () => {
            await logout();
            doLogout();
            window.location.href = '/login';
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}
