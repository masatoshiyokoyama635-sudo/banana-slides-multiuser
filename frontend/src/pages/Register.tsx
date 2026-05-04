import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus } from 'lucide-react';
import { Button, Card, Input } from '@/components/shared';
import { useAuth } from '@/hooks/useAuth';

export function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [name, setName] = useState('');
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
    if (password.length < 8) {
      setError('密码至少需要 8 位');
      return;
    }

    setIsSubmitting(true);
    setError('');
    try {
      await register(normalizedEmail, password, name.trim() || undefined);
      navigate('/', { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || err?.message || '注册失败，请稍后重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-yellow-50 via-orange-50/30 to-pink-50/50 dark:from-background-primary dark:via-background-primary dark:to-background-primary px-4">
      <Card className="w-full max-w-md p-8 bg-white/90 dark:bg-background-secondary">
        <div className="text-center mb-8">
          <img src="/logo.png" alt="蕉幻 Banana Slides Logo" className="h-14 w-auto mx-auto rounded-lg object-contain mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-foreground-primary">注册蕉幻</h1>
          <p className="text-sm text-gray-500 dark:text-foreground-tertiary mt-2">创建账号后即可保存自己的项目和 API Key</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="昵称（可选）"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="怎么称呼你"
          />
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
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="至少 8 位密码"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button type="submit" className="w-full" loading={isSubmitting} icon={<UserPlus size={18} />}>
            注册并登录
          </Button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500 dark:text-foreground-tertiary">
          已有账号？
          <Link to="/login" className="ml-1 text-banana-700 dark:text-banana hover:underline">
            去登录
          </Link>
        </div>
      </Card>
    </div>
  );
}
