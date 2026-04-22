import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, FolderOpen, Upload, Scissors,
  Settings, LogOut, Film
} from 'lucide-react';

export default function Sidebar() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/projects', icon: FolderOpen, label: 'Projects' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <Film size={24} />
        </div>
        <div>
          <h2>Video-Use</h2>
          <span className="text-xs text-muted">Auto Video Editor</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'active' : ''}`
            }
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-avatar">
            {user.username?.charAt(0)?.toUpperCase() || 'U'}
          </div>
          <div className="sidebar-user-info">
            <span className="sidebar-username">{user.username || 'User'}</span>
          </div>
          <button onClick={handleLogout} className="btn-icon sidebar-logout" title="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <style>{`
        .sidebar {
          position: fixed;
          left: 0;
          top: 0;
          bottom: 0;
          width: var(--sidebar-width);
          background: var(--bg-secondary);
          border-right: 1px solid var(--border-primary);
          display: flex;
          flex-direction: column;
          z-index: 100;
          padding: 0;
        }
        .sidebar-brand {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 24px 20px;
          border-bottom: 1px solid var(--border-primary);
        }
        .sidebar-logo {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: var(--gradient-primary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }
        .sidebar-brand h2 {
          font-size: 1.1rem;
          font-weight: 800;
          color: var(--text-primary);
          line-height: 1.2;
        }
        .sidebar-nav {
          flex: 1;
          padding: 16px 12px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .sidebar-link {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          border-radius: var(--radius-sm);
          color: var(--text-secondary);
          font-size: 0.9rem;
          font-weight: 500;
          transition: all var(--transition-fast);
          text-decoration: none;
        }
        .sidebar-link:hover {
          background: var(--bg-input);
          color: var(--text-primary);
        }
        .sidebar-link.active {
          background: var(--gradient-subtle);
          color: var(--text-accent);
          border: 1px solid var(--border-accent);
        }
        .sidebar-footer {
          padding: 16px;
          border-top: 1px solid var(--border-primary);
        }
        .sidebar-user {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .sidebar-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--gradient-primary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 0.8rem;
          font-weight: 700;
          flex-shrink: 0;
        }
        .sidebar-user-info {
          flex: 1;
          min-width: 0;
        }
        .sidebar-username {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .sidebar-logout {
          color: var(--text-muted);
          background: none;
          border: none;
          cursor: pointer;
          padding: 6px;
          border-radius: var(--radius-sm);
          transition: all var(--transition-fast);
        }
        .sidebar-logout:hover {
          color: var(--color-error);
          background: rgba(239, 68, 68, 0.1);
        }
        @media (max-width: 768px) {
          .sidebar { display: none; }
        }
      `}</style>
    </aside>
  );
}
