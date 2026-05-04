import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Login } from '@/pages/Login';

const login = vi.fn();
const navigate = vi.fn();

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ login }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

describe('Login page', () => {
  it('validates empty credentials', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    await userEvent.click(screen.getByRole('button', { name: /登录/i }));

    expect(screen.getByText('请输入邮箱和密码')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('logs in and redirects to home', async () => {
    login.mockResolvedValueOnce(undefined);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByPlaceholderText('you@example.com'), 'alice@example.com');
    await userEvent.type(screen.getByPlaceholderText('至少 8 位密码'), 'Password123!');
    await userEvent.click(screen.getByRole('button', { name: /登录/i }));

    expect(login).toHaveBeenCalledWith('alice@example.com', 'Password123!');
    expect(navigate).toHaveBeenCalledWith('/', { replace: true });
  });
});
