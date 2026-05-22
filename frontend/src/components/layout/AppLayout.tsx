import { ReactNode, useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import FloatingTeacher from '../Chat/FloatingTeacher';

export default function AppLayout({ children }: { children: ReactNode }) {
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen flex overflow-hidden">
      {/* Desktop sidebar */}
      <div 
        className={`hidden md:block transition-all duration-300 ease-in-out flex-shrink-0 overflow-hidden bg-gray-100 ${
          desktopSidebarOpen ? 'w-56 border-r border-gray-200' : 'w-0'
        }`}
      >
        <div className="w-56 h-full">
          <Sidebar onToggle={() => setDesktopSidebarOpen(false)} />
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <div className="absolute inset-0 bg-black/30 transition-opacity" onClick={() => setMobileSidebarOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-56 bg-gray-100 shadow-lg border-r border-gray-200">
            <Sidebar onToggle={() => setMobileSidebarOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        <Header 
          onToggleMobile={() => setMobileSidebarOpen(v => !v)}
          onToggleDesktop={() => setDesktopSidebarOpen(v => !v)} 
        />
        <main className="p-6">{children}</main>
      </div>
      <FloatingTeacher />
    </div>
  );
}
