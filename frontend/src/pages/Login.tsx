import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Mail, Lock } from 'lucide-react';
import { Button, Card, Input } from '@/components/shared';
import { useAuth } from '@/hooks/useAuth';

const getRedirectPath = (state: unknown) => {
  const maybeState = state as { from?: { pathname?: string } } | null;
  const pathname = maybeState?.from?.pathname;
  return pathname && pathname !== '/login' && pathname !== '/register' ? pathname : '/';
};

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const normalizedEmail = email.trim();
    if (!normalizedEmail || !password) {
      setError('请输入邮箱和密码');
      return;
    }

    setIsSubmitting(true);
    setError('');
    try {
      await login(normalizedEmail, password);
      navigate(getRedirectPath(location.state), { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || err?.message || '登录失败，请检查邮箱和密码');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-yellow-50 via-orange-50/30 to-pink-50/50 dark:from-background-primary dark:via-background-primary dark:to-background-primary px-4">
      <Card className="w-full max-w-md p-8 bg-white/90 dark:bg-background-secondary">
        <div className="text-center mb-8">
          <img src="/logo.png" alt="蕉幻 Banana Slides Logo" className="h-14 w-auto mx-auto rounded-lg object-contain mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-foreground-primary">登录蕉幻</h1>
          <p className="text-sm text-gray-500 dark:text-foreground-tertiary mt-2">使用你的账号进入工作区</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="邮箱"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
          <Input
            label="密码"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="至少 8 位密码"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button type="submit" className="w-full" loading={isSubmitting} icon={<Lock size={18} />}>
            登录
          </Button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500 dark:text-foreground-tertiary">
          还没有账号？
          <Link to="/register" className="ml-1 text-banana-700 dark:text-banana hover:underline inline-flex items-center gap-1">
            <Mail size={14} />注册
          </Link>
        </div>
      </Card>
    </div>
  );
}
