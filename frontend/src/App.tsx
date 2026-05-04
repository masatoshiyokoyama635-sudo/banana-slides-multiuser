import { useEffect, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Home } from './pages/Home';
import { Landing } from './pages/Landing';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { useProjectStore } from './store/useProjectStore';
import { useToast, AccessCodeGuard, AuthGuard } from './components/shared';
import { AuthProvider, useAuth } from './hooks/useAuth';

function ProtectedRoute({ children }: { children: ReactNode }) {
  return (
    <AccessCodeGuard>
      <AuthGuard>{children}</AuthGuard>
    </AccessCodeGuard>
  );
}

function AppRoutes() {
  const { currentProject, syncProject, error, setError } = useProjectStore();
  const { show, ToastContainer } = useToast();
  const { isAuthenticated } = useAuth();

  // 恢复项目状态
  useEffect(() => {
    const savedProjectId = localStorage.getItem('currentProjectId');
    if (isAuthenticated && savedProjectId && !currentProject) {
      syncProject();
    }
  }, [isAuthenticated, currentProject, syncProject]);

  // 显示全局错误
  useEffect(() => {
    if (error) {
      show({ message: error, type: 'error' });
      setError(null);
    }
  }, [error, setError, show]);

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/landing" element={<Landing />} />
        <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/project/:projectId/outline" element={<ProtectedRoute><OutlineEditor /></ProtectedRoute>} />
        <Route path="/project/:projectId/detail" element={<ProtectedRoute><DetailEditor /></ProtectedRoute>} />
        <Route path="/project/:projectId/preview" element={<ProtectedRoute><SlidePreview /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastContainer />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

