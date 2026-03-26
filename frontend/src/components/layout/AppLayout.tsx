import { ReactNode, useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

export default function AppLayout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const closeSidebar = () => setSidebarOpen(false);
  return (
    <div className="min-h-screen flex">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <div className="absolute inset-0 bg-black/30" onClick={closeSidebar} />
          <div className="absolute inset-y-0 left-0 w-64 bg-white shadow-lg">
            <Sidebar />
          </div>
        </div>
      )}
      <div className="flex-1 flex flex-col min-w-0">
        <Header onToggleSidebar={() => setSidebarOpen((v) => !v)} />
        <main className="p-4">{children}</main>
      </div>
    </div>
  );
}
