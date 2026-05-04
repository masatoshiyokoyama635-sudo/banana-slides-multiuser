import { Navigate, useLocation } from 'react-router-dom';
import { Loading } from './Loading';
import { useAuth } from '@/hooks/useAuth';
import type { ReactNode } from 'react';

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status, isAuthenticated } = useAuth();
  const location = useLocation();

  if (status === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-primary">
        <Loading message="加载中..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
