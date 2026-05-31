import { ReactNode, useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import FloatingTeacher from '../Chat/FloatingTeacher';

export default function AppLayout({ children }: { children: ReactNode }) {
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen overflow-hidden bg-canvas">
      {/* Desktop sidebar */}
      <div
        className={`hidden flex-shrink-0 overflow-hidden bg-surface-soft transition-all duration-300 ease-in-out md:block ${
          desktopSidebarOpen ? 'w-60 border-r border-line' : 'w-0'
        }`}
      >
        <div className="h-full w-60">
          <Sidebar onToggle={() => setDesktopSidebarOpen(false)} />
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <div className="absolute inset-0 bg-ink/30 transition-opacity" onClick={() => setMobileSidebarOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-60 border-r border-line bg-surface-soft shadow-lg">
            <Sidebar onToggle={() => setMobileSidebarOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-y-auto">
        <Header
          onToggleMobile={() => setMobileSidebarOpen(v => !v)}
          onToggleDesktop={() => setDesktopSidebarOpen(v => !v)}
        />
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
      <FloatingTeacher />
    </div>
  );
}
