import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { 
  LayoutDashboard, 
  Monitor, 
  AlertTriangle, 
  FileWarning, 
  Activity,
  Package,
  FileText,
  Settings,
  Shield,
  Target,
  LogOut,
  Menu,
  X,
  ChevronRight,
  Server,
  Bell
} from 'lucide-react';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/monitoring', label: 'Monitoring', icon: Monitor },
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/incidents', label: 'Incidents', icon: FileWarning },
  { path: '/performance', label: 'Performance', icon: Activity },
  { path: '/assets', label: 'Assets', icon: Package },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/configuration', label: 'Configuration', icon: Settings },
  { path: '/sla', label: 'SLA Management', icon: Target },
];

export const Sidebar = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <aside 
      data-testid="sidebar"
      className={`fixed left-0 top-0 h-full bg-white border-r border-border/60 shadow-sm z-40 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border/60">
          {!collapsed && (
            <div className="flex items-center gap-2">
              <Server className="h-6 w-6 text-primary" />
              <span className="font-bold text-lg tracking-tight font-['Manrope']">NOC Commander</span>
            </div>
          )}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => setCollapsed(!collapsed)}
            data-testid="sidebar-toggle"
            className="hover:bg-muted"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-4">
          <nav className="space-y-1 px-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.path.replace('/', '')}`}
                  className={`sidebar-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {!collapsed && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>
        </ScrollArea>

        {/* User section */}
        <div className="border-t border-border/60 p-4">
          {!collapsed && user && (
            <div className="mb-3">
              <p className="text-sm font-medium truncate">{user.name}</p>
              <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
            </div>
          )}
          <Button
            variant="ghost"
            size={collapsed ? "icon" : "default"}
            onClick={logout}
            data-testid="logout-btn"
            className="w-full justify-start gap-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          >
            <LogOut className="h-4 w-4" />
            {!collapsed && <span>Logout</span>}
          </Button>
        </div>
      </div>
    </aside>
  );
};

export const MainLayout = ({ children }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main 
        className={`transition-all duration-300 ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}
        style={{ marginLeft: '256px' }}
      >
        <div className="p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
