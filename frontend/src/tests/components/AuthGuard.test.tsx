import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthGuard } from '@/components/shared/AuthGuard';

const mockUseAuth = vi.fn();

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('AuthGuard', () => {
  it('renders children for authenticated users', () => {
    mockUseAuth.mockReturnValue({ status: 'authenticated', isAuthenticated: true });

    render(
      <MemoryRouter>
        <AuthGuard>
          <div>Protected content</div>
        </AuthGuard>
      </MemoryRouter>
    );

    expect(screen.getByText('Protected content')).toBeInTheDocument();
  });

  it('does not render children while checking auth state', () => {
    mockUseAuth.mockReturnValue({ status: 'checking', isAuthenticated: false });

    render(
      <MemoryRouter>
        <AuthGuard>
          <div>Protected content</div>
        </AuthGuard>
      </MemoryRouter>
    );

    expect(screen.queryByText('Protected content')).not.toBeInTheDocument();
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });
});
