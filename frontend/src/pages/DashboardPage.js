import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { dashboardApi, seedDemoData } from '../services/api';
import { toast } from 'sonner';
import {
  Server,
  AlertTriangle,
  FileWarning,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Database,
  Zap,
  Target,
  Timer,
  ExternalLink
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';

const StatusBadge = ({ status }) => {
  const styles = {
    online: 'bg-green-50 text-green-700 border-green-200',
    offline: 'bg-red-50 text-red-700 border-red-200',
    degraded: 'bg-amber-50 text-amber-700 border-amber-200',
    maintenance: 'bg-blue-50 text-blue-700 border-blue-200',
    active: 'bg-red-50 text-red-700 border-red-200',
    acknowledged: 'bg-amber-50 text-amber-700 border-amber-200',
    resolved: 'bg-green-50 text-green-700 border-green-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.online} capitalize`}>
      {status}
    </Badge>
  );
};

const SeverityBadge = ({ severity }) => {
  const styles = {
    critical: 'bg-red-600 text-white',
    high: 'bg-orange-500 text-white',
    medium: 'bg-amber-500 text-white',
    low: 'bg-blue-500 text-white',
    info: 'bg-slate-500 text-white',
  };

  return (
    <Badge className={`${styles[severity] || styles.low} capitalize`}>
      {severity}
    </Badge>
  );
};

const PriorityBadge = ({ priority }) => {
  const styles = {
    P1: 'bg-red-600 text-white',
    P2: 'bg-orange-500 text-white',
    P3: 'bg-amber-500 text-white',
    P4: 'bg-slate-500 text-white',
  };

  return (
    <Badge className={`${styles[priority] || styles.P4}`}>
      {priority}
    </Badge>
  );
};

const StatCard = ({ title, value, subtitle, icon: Icon, trend, trendValue, color = 'primary' }) => {
  const colorClasses = {
    primary: 'text-primary',
    success: 'text-green-600',
    warning: 'text-amber-600',
    danger: 'text-red-600',
    info: 'text-blue-600',
  };

  return (
    <Card className="stat-card bg-white border-border/50 shadow-sm hover:shadow-md transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className={`text-3xl font-bold mt-2 ${colorClasses[color]}`}>{value}</p>
            {subtitle && (
              <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
            )}
          </div>
          <div className={`p-3 rounded-xl bg-muted ${colorClasses[color]}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
        {trend && (
          <div className="flex items-center gap-1 mt-3">
            {trend === 'up' ? (
              <TrendingUp className="h-4 w-4 text-green-600" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-600" />
            )}
            <span className={`text-sm font-medium ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
              {trendValue}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [recentIncidents, setRecentIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const fetchData = async () => {
    try {
      const [statsRes, alertsRes, incidentsRes] = await Promise.all([
        dashboardApi.getStats(),
        dashboardApi.getRecentAlerts(5),
        dashboardApi.getRecentIncidents(5),
      ]);
      setStats(statsRes.data);
      setRecentAlerts(alertsRes.data);
      setRecentIncidents(incidentsRes.data);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSeedData = async () => {
    setSeeding(true);
    try {
      await seedDemoData();
      toast.success('Demo data seeded successfully!');
      fetchData();
    } catch (error) {
      toast.error('Failed to seed demo data');
    } finally {
      setSeeding(false);
    }
  };

  const pieColors = ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6'];

  const devicePieData = stats ? [
    { name: 'Online', value: stats.devices.online },
    { name: 'Offline', value: stats.devices.offline },
    { name: 'Degraded', value: stats.devices.degraded },
    { name: 'Maintenance', value: stats.devices.maintenance },
  ].filter(d => d.value > 0) : [];

  const mockPerformanceData = Array.from({ length: 24 }, (_, i) => ({
    time: `${String(i).padStart(2, '0')}:00`,
    cpu: Math.floor(Math.random() * 40) + 30,
    memory: Math.floor(Math.random() * 30) + 40,
    bandwidth: Math.floor(Math.random() * 50) + 200,
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]" data-testid="dashboard-loading">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div data-testid="dashboard-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Dashboard</h1>
          <p className="text-muted-foreground mt-1">ATECH NOC Commander - Network Operation Center Overview</p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            onClick={handleSeedData} 
            disabled={seeding}
            data-testid="seed-data-btn"
          >
            <Database className="h-4 w-4 mr-2" />
            {seeding ? 'Seeding...' : 'Seed Demo Data'}
          </Button>
          <Button variant="outline" onClick={fetchData} data-testid="refresh-btn">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Network Uptime"
          value={`${stats?.kpis?.uptime_percentage || 0}%`}
          subtitle="Last 30 days"
          icon={Activity}
          color="success"
          trend="up"
          trendValue="+0.2%"
        />
        <div 
          onClick={() => navigate('/alerts')} 
          className="cursor-pointer group"
          data-testid="alerts-link"
        >
          <Card className="stat-card bg-white border-border/50 shadow-sm hover:shadow-md hover:border-primary/50 transition-all">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                    Active Alerts
                    <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </p>
                  <p className={`text-3xl font-bold mt-2 ${stats?.alerts?.critical > 0 ? 'text-red-600' : 'text-amber-600'}`}>
                    {stats?.alerts?.active || 0}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">{stats?.alerts?.critical || 0} critical</p>
                </div>
                <div className={`p-3 rounded-xl bg-muted ${stats?.alerts?.critical > 0 ? 'text-red-600' : 'text-amber-600'}`}>
                  <AlertTriangle className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        <div 
          onClick={() => navigate('/incidents')} 
          className="cursor-pointer group"
          data-testid="incidents-link"
        >
          <Card className="stat-card bg-white border-border/50 shadow-sm hover:shadow-md hover:border-primary/50 transition-all">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                    Open Incidents
                    <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </p>
                  <p className={`text-3xl font-bold mt-2 ${stats?.incidents?.p1_open > 0 ? 'text-red-600' : 'text-primary'}`}>
                    {stats?.incidents?.open || 0}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">{stats?.incidents?.p1_open || 0} P1, {stats?.incidents?.p2_open || 0} P2</p>
                </div>
                <div className={`p-3 rounded-xl bg-muted ${stats?.incidents?.p1_open > 0 ? 'text-red-600' : 'text-primary'}`}>
                  <FileWarning className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        <div 
          onClick={() => navigate('/monitoring')} 
          className="cursor-pointer group"
          data-testid="devices-link"
        >
          <Card className="stat-card bg-white border-border/50 shadow-sm hover:shadow-md hover:border-primary/50 transition-all">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                    Total Devices
                    <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </p>
                  <p className="text-3xl font-bold mt-2 text-blue-600">{stats?.devices?.total || 0}</p>
                  <p className="text-sm text-muted-foreground mt-1">{stats?.devices?.online || 0} online</p>
                </div>
                <div className="p-3 rounded-xl bg-muted text-blue-600">
                  <Server className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-2 rounded-lg bg-blue-50">
              <Clock className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">MTTD</p>
              <p className="text-xl font-bold">{stats?.kpis?.mttd_minutes || 0} min</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-2 rounded-lg bg-green-50">
              <Timer className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">MTTR</p>
              <p className="text-xl font-bold">{stats?.kpis?.mttr_minutes || 0} min</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-2 rounded-lg bg-purple-50">
              <Target className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">SLA Compliance</p>
              <p className="text-xl font-bold">{stats?.kpis?.sla_compliance || 0}%</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-2 rounded-lg bg-amber-50">
              <Zap className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">FCR Rate</p>
              <p className="text-xl font-bold">{stats?.kpis?.fcr_rate || 0}%</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts and Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Performance Chart */}
        <Card className="lg:col-span-2 bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">System Performance (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockPerformanceData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#fff', 
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                    }} 
                  />
                  <Area 
                    type="monotone" 
                    dataKey="cpu" 
                    stroke="#3b82f6" 
                    fill="#3b82f6" 
                    fillOpacity={0.2}
                    name="CPU %"
                  />
                  <Area 
                    type="monotone" 
                    dataKey="memory" 
                    stroke="#22c55e" 
                    fill="#22c55e" 
                    fillOpacity={0.2}
                    name="Memory %"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Device Status Pie */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Device Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={devicePieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {devicePieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Alerts */}
        <Card className="bg-white border-border/50">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold">Recent Alerts</CardTitle>
            <Button variant="ghost" size="sm" className="text-muted-foreground">
              View All
            </Button>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[300px]">
              {recentAlerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mb-2 text-green-500" />
                  <p>No recent alerts</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentAlerts.map((alert) => (
                    <div 
                      key={alert.id} 
                      className="flex items-start justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                      data-testid={`alert-${alert.id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <SeverityBadge severity={alert.severity} />
                          <StatusBadge status={alert.status} />
                        </div>
                        <p className="font-medium text-sm truncate">{alert.title}</p>
                        <p className="text-xs text-muted-foreground">{alert.device_name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Recent Incidents */}
        <Card className="bg-white border-border/50">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold">Recent Incidents</CardTitle>
            <Button variant="ghost" size="sm" className="text-muted-foreground">
              View All
            </Button>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[300px]">
              {recentIncidents.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mb-2 text-green-500" />
                  <p>No recent incidents</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentIncidents.map((incident) => (
                    <div 
                      key={incident.id} 
                      className="flex items-start justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                      data-testid={`incident-${incident.id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <PriorityBadge priority={incident.priority} />
                          <StatusBadge status={incident.status} />
                        </div>
                        <p className="font-medium text-sm truncate">{incident.title}</p>
                        <p className="text-xs text-muted-foreground font-mono">{incident.ticket_number}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
