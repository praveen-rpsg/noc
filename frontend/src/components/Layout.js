import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Badge } from '../components/ui/badge';
import PendingActionsNotification from './PendingActionsNotification';
import { 
  LayoutDashboard, 
  Monitor, 
  AlertTriangle, 
  FileWarning, 
  Activity,
  Package,
  FileText,
  Settings,
  Target,
  LogOut,
  Menu,
  ChevronRight,
  Network,
  Terminal,
  Bell,
  Bot,
  AlertCircle,
  Cog
} from 'lucide-react';

const AMEYA_LOGO_URL = "https://customer-assets.emergentagent.com/job_network-ops-ai/artifacts/vjap12f5_Atechlogo.jpeg";

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/monitoring', label: 'Monitoring', icon: Monitor },
  { path: '/topology', label: 'Network Topology', icon: Network },
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/incidents', label: 'Incidents', icon: FileWarning },
  { path: '/performance', label: 'Performance', icon: Activity },
  { path: '/assets', label: 'Assets', icon: Package },
  { path: '/ssh-terminal', label: 'SSH Terminal', icon: Terminal },
  { path: '/agents', label: 'AI Agents', icon: Bot },
  { path: '/escalation', label: 'Escalation', icon: AlertCircle },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/configuration', label: 'Configuration', icon: Settings },
  { path: '/sla', label: 'SLA Management', icon: Target },
  { path: '/settings', label: 'Settings', icon: Cog },
];

export const Sidebar = ({ notificationCount = 0 }) => {
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
        {/* Header with Logo */}
        <div className="flex items-center justify-between p-4 border-b border-border/60">
          {!collapsed && (
            <div className="flex items-center gap-2">
              <img 
                src={AMEYA_LOGO_URL} 
                alt="Ameya Technologies" 
                className="h-10 w-10 object-contain rounded"
              />
              <div className="flex flex-col">
                <span className="font-bold text-sm tracking-tight font-['Manrope'] text-primary">ATECH</span>
                <span className="text-xs text-muted-foreground">NOC COMMANDER</span>
              </div>
            </div>
          )}
          {collapsed && (
            <img 
              src={AMEYA_LOGO_URL} 
              alt="Ameya Technologies" 
              className="h-8 w-8 object-contain rounded mx-auto"
            />
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
              const showBadge = item.path === '/alerts' && notificationCount > 0;
              
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.path.replace('/', '')}`}
                  className={`sidebar-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium relative ${
                    isActive 
                      ? 'bg-primary text-primary-foreground' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {!collapsed && <span>{item.label}</span>}
                  {showBadge && (
                    <Badge 
                      className="absolute right-2 bg-red-500 text-white text-xs px-1.5 py-0.5"
                    >
                      {notificationCount}
                    </Badge>
                  )}
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
  const [notificationCount, setNotificationCount] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    // Connect to WebSocket for real-time alerts
    const wsUrl = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://');
    if (!wsUrl) return;

    let ws;
    let reconnectTimeout;

    const connect = () => {
      ws = new WebSocket(`${wsUrl}/ws/alerts`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
        // Send periodic pings
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
        ws.pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'alert' || data.type === 'notification') {
            setNotificationCount(prev => prev + 1);
            // Show browser notification if permitted
            if (Notification.permission === 'granted') {
              new Notification('ATECH NOC Commander Alert', {
                body: data.data?.title || 'New alert received',
                icon: '/favicon.ico'
              });
            }
          }
        } catch (e) {
          console.error('WebSocket message parse error:', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        clearInterval(ws.pingInterval);
        // Reconnect after 5 seconds
        reconnectTimeout = setTimeout(connect, 5000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    // Request notification permission
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) {
        clearInterval(ws.pingInterval);
        ws.close();
      }
    };
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar notificationCount={notificationCount} />
      {/* Top bar with pending actions */}
      <div className="fixed top-4 right-6 z-50">
        <PendingActionsNotification />
      </div>
      <main 
        className="transition-all duration-300 ml-64"
      >
        <div className="p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
