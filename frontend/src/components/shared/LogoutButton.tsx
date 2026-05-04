import { LogOut } from 'lucide-react';
import { Button } from './Button';
import { useAuth } from '@/hooks/useAuth';

export function LogoutButton({ compact = false }: { compact?: boolean }) {
  const { logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    window.location.replace('/login');
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      icon={<LogOut size={16} />}
      onClick={handleLogout}
      className="text-xs md:text-sm"
    >
      {compact ? '' : '退出'}
    </Button>
  );
}
