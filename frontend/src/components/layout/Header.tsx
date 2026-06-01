import { useAuthStore } from '../../stores/authStore';
import { logout } from '../../api/auth';
import NotificationBell from '../notifications/NotificationBell';

export default function Header({
  onToggleMobile = () => {},
  onToggleDesktop = () => {},
}: {
  onToggleMobile?: () => void;
  onToggleDesktop?: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const doLogout = useAuthStore((s) => s.logout);

  return (
    <header className="sticky top-0 z-10 flex h-16 w-full shrink-0 items-center justify-between border-b border-line bg-canvas/80 px-4 backdrop-blur-md sm:px-6">
      <div className="flex items-center gap-3">
        {/* Toggle Button for Mobile */}
        <button
          type="button"
          className="rounded-lg border border-line p-2 text-ink-soft transition-colors hover:bg-surface md:hidden"
          aria-label="Toggle mobile menu"
          onClick={onToggleMobile}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12h18M3 6h18M3 18h18" /></svg>
        </button>

        {/* Toggle Button for Desktop */}
        <button
          type="button"
          className="hidden rounded-lg border border-line p-2 text-ink-soft transition-colors hover:bg-surface md:block"
          aria-label="Toggle desktop menu"
          onClick={onToggleDesktop}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12h18M3 6h18M3 18h18" /></svg>
        </button>
      </div>

      <div className="flex items-center gap-3">
        <NotificationBell />
        <div className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-3 shadow-pill">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-clay-wash text-sm font-bold text-clay-ink">
            {user?.name?.[0] || 'U'}
          </div>
          <span className="hidden text-sm font-medium text-ink sm:block">{user?.name}</span>
        </div>
        <button
          className="rounded-full border border-line px-3.5 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:bg-surface hover:text-ink"
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
