import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import * as api from '@/api/endpoints';
import type { User } from '@/types';
import { useProjectStore } from '@/store/useProjectStore';
import { useExportTasksStore } from '@/store/useExportTasksStore';

type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  checkSession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const clearUserScopedState = (resetProjectState: () => void, clearExportTasks: () => void) => {
  [
    'currentProjectId',
    'renovationTaskId',
    'home-draft-content',
    'home-draft-tab',
    'banana-available-extra-fields',
    'banana-detail-level',
    'descReqOpen',
    'outlineReqOpen',
  ].forEach((key) => localStorage.removeItem(key));
  sessionStorage.removeItem('banana-settings');
  resetProjectState();
  clearExportTasks();
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('checking');
  const authVersionRef = useRef(0);
  const resetProjectState = useProjectStore(state => state.resetUserScopedState);
  const clearExportTasks = useExportTasksStore(state => state.clearAll);

  const bumpAuthVersion = useCallback(() => {
    authVersionRef.current += 1;
    return authVersionRef.current;
  }, []);

  const markUnauthenticated = useCallback(() => {
    bumpAuthVersion();
    clearUserScopedState(resetProjectState, clearExportTasks);
    setUser(null);
    setStatus('unauthenticated');
  }, [resetProjectState, clearExportTasks, bumpAuthVersion]);

  const checkSession = useCallback(async () => {
    const requestVersion = authVersionRef.current;
    setStatus('checking');
    try {
      const response = await api.getCurrentUser();
      if (requestVersion !== authVersionRef.current) {
        return;
      }
      const session = response.data;
      if (session?.authenticated && session.user) {
        setUser(session.user);
        setStatus('authenticated');
      } else {
        markUnauthenticated();
      }
    } catch {
      if (requestVersion !== authVersionRef.current) {
        return;
      }
      markUnauthenticated();
    }
  }, [markUnauthenticated]);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  useEffect(() => {
    const handleAuthRequired = () => markUnauthenticated();
    window.addEventListener('banana-auth-required', handleAuthRequired);
    return () => window.removeEventListener('banana-auth-required', handleAuthRequired);
  }, [markUnauthenticated]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login({ email, password });
    if (!response.data?.user) {
      throw new Error(response.error || 'Login failed');
    }
    bumpAuthVersion();
    clearUserScopedState(resetProjectState, clearExportTasks);
    setUser(response.data.user);
    setStatus('authenticated');
  }, [resetProjectState, clearExportTasks, bumpAuthVersion]);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const response = await api.register({ email, password, name });
    if (!response.data?.user) {
      throw new Error(response.error || 'Registration failed');
    }
    bumpAuthVersion();
    clearUserScopedState(resetProjectState, clearExportTasks);
    setUser(response.data.user);
    setStatus('authenticated');
  }, [resetProjectState, clearExportTasks, bumpAuthVersion]);

  const logout = useCallback(async () => {
    bumpAuthVersion();
    try {
      await api.logout();
    } finally {
      clearUserScopedState(resetProjectState, clearExportTasks);
      setUser(null);
      setStatus('unauthenticated');
    }
  }, [resetProjectState, clearExportTasks, bumpAuthVersion]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    status,
    isAuthenticated: status === 'authenticated',
    checkSession,
    login,
    register,
    logout,
  }), [user, status, checkSession, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
