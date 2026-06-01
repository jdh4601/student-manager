import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { SpeedInsights } from '@vercel/speed-insights/react';
import LoginPage from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import SignupPage from './pages/SignupPage';
import OAuthCallbackPage from './pages/OAuthCallbackPage';
import LandingPage from './pages/LandingPage';
import RootIndex from './pages/RootIndex';
import ProtectedRoute from './components/auth/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';
import SimpleLayout from './components/layout/SimpleLayout';
import StudentHomePage from './pages/StudentHomePage';
import ParentHomePage from './pages/ParentHomePage';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const StudentListPage = lazy(() => import('./pages/StudentListPage'));
const StudentDetailPage = lazy(() => import('./pages/StudentDetailPage'));
const GradesPage = lazy(() => import('./pages/GradesPage'));
const FeedbackPage = lazy(() => import('./pages/FeedbackPage'));
const CounselingPage = lazy(() => import('./pages/CounselingPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));

function App() {
  return (
    <>
      <SpeedInsights />
      <Toaster position="top-right" />
      <Routes>
      <Route path="/" element={<RootIndex /> } />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/oauth/google/callback" element={<OAuthCallbackPage />} />
      {/* Role-aware notifications page for all authenticated users */}
      <Route
        path="/notifications"
        element={
          <ProtectedRoute>
            <RoleAwareLayout>
              <NotificationsPage />
            </RoleAwareLayout>
          </ProtectedRoute>
        }
      />
      {/* Student & Parent dashboards (non-teacher layout) */}
      <Route
        path="/student"
        element={
          <ProtectedRoute roles={['student']}>
            <SimpleLayout>
              <StudentHomePage />
            </SimpleLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent"
        element={
          <ProtectedRoute roles={['parent']}>
            <SimpleLayout>
              <ParentHomePage />
            </SimpleLayout>
          </ProtectedRoute>
        }
      />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute roles={['teacher']}>
            <AppLayout>
              <Suspense fallback={<div className="p-4">불러오는 중...</div>}>
                <Routes>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  {/* Analytics merged into the dashboard; keep old links working */}
                  <Route path="/analytics" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/students" element={<StudentListPage />} />
                  <Route path="/students/:studentId" element={<StudentDetailPage />} />
                  <Route path="/grades/:studentId" element={<GradesPage />} />
                  <Route path="/feedbacks" element={<FeedbackPage />} />
                  <Route path="/counselings" element={<CounselingPage />} />
                  {/* notifications handled by top-level role-aware route */}
                </Routes>
              </Suspense>
            </AppLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
    </>
  );
}

export default App;

// Role-aware layout wrapper for top-level routes
import { useAuthStore } from './stores/authStore';
function RoleAwareLayout({ children }: { children: React.ReactNode }) {
  const role = useAuthStore((s) => s.user?.role);
  if (role === 'teacher') return <AppLayout>{children}</AppLayout>;
  return <SimpleLayout>{children}</SimpleLayout>;
}
