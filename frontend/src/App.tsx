import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import ProtectedRoute from './components/auth/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const StudentListPage = lazy(() => import('./pages/StudentListPage'));
const StudentDetailPage = lazy(() => import('./pages/StudentDetailPage'));
const GradesPage = lazy(() => import('./pages/GradesPage'));
const FeedbackPage = lazy(() => import('./pages/FeedbackPage'));
const CounselingPage = lazy(() => import('./pages/CounselingPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppLayout>
              <Suspense fallback={<div className="p-4">불러오는 중...</div>}>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/students" element={<StudentListPage />} />
                  <Route path="/students/:studentId" element={<StudentDetailPage />} />
                  <Route path="/grades/:studentId" element={<GradesPage />} />
                  <Route path="/feedbacks" element={<FeedbackPage />} />
                  <Route path="/counselings" element={<CounselingPage />} />
                  <Route path="/notifications" element={<NotificationsPage />} />
                </Routes>
              </Suspense>
            </AppLayout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

export default App;
