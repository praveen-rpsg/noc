import React, { useState, useEffect, useCallback } from 'react';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import axios from 'axios';
import { getApiUrl } from '../services/config';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Monitor,
  Bell,
  Activity,
  Network,
  FileText,
  Target,
  Clock,
  Plus,
  Save,
  RotateCcw,
  Settings,
  Trash2,
  Move,
  Maximize2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Server,
  Loader2,
  Lock,
  Globe
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

const getAuthHeader = () => {
  const token = localStorage.getItem('noc_token');
  return { Authorization: `Bearer ${token}` };
};

// Widget definitions
const AVAILABLE_WIDGETS = [
  { id: 'device_status', name: 'Device Status Summary', icon: Monitor, minW: 2, minH: 2, defaultW: 3, defaultH: 2 },
  { id: 'active_alerts', name: 'Active Alerts Chart', icon: Bell, minW: 2, minH: 2, defaultW: 4, defaultH: 3 },
  { id: 'incident_trends', name: 'Incident Trends', icon: TrendingUp, minW: 3, minH: 2, defaultW: 4, defaultH: 3 },
  { id: 'topology_mini', name: 'Network Topology Mini-Map', icon: Network, minW: 3, minH: 3, defaultW: 4, defaultH: 4 },
  { id: 'performance_metrics', name: 'Performance Metrics', icon: Activity, minW: 2, minH: 2, defaultW: 4, defaultH: 3 },
  { id: 'recent_activity', name: 'Recent Activity Feed', icon: Clock, minW: 2, minH: 3, defaultW: 3, defaultH: 4 },
  { id: 'sla_compliance', name: 'SLA Compliance', icon: Target, minW: 2, minH: 2, defaultW: 3, defaultH: 2 },
  { id: 'custom_metric', name: 'Custom Metric Card', icon: FileText, minW: 1, minH: 1, defaultW: 2, defaultH: 2 },
];

// Default layout
const DEFAULT_LAYOUT = [
  { i: 'device_status_1', x: 0, y: 0, w: 3, h: 2, widgetType: 'device_status' },
  { i: 'active_alerts_1', x: 3, y: 0, w: 4, h: 3, widgetType: 'active_alerts' },
  { i: 'sla_compliance_1', x: 7, y: 0, w: 3, h: 2, widgetType: 'sla_compliance' },
  { i: 'incident_trends_1', x: 0, y: 2, w: 4, h: 3, widgetType: 'incident_trends' },
  { i: 'recent_activity_1', x: 7, y: 2, w: 3, h: 4, widgetType: 'recent_activity' },
  { i: 'performance_metrics_1', x: 4, y: 3, w: 3, h: 3, widgetType: 'performance_metrics' },
];

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

// Widget Components
const DeviceStatusWidget = ({ data }) => {
  const stats = data || { online: 0, offline: 0, warning: 0, total: 0 };
  return (
    <div className="h-full flex flex-col justify-center">
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-green-50 p-3 rounded-lg text-center">
          <div className="text-2xl font-bold text-green-600">{stats.online}</div>
          <div className="text-xs text-green-700">Online</div>
        </div>
        <div className="bg-red-50 p-3 rounded-lg text-center">
          <div className="text-2xl font-bold text-red-600">{stats.offline}</div>
          <div className="text-xs text-red-700">Offline</div>
        </div>
        <div className="bg-yellow-50 p-3 rounded-lg text-center">
          <div className="text-2xl font-bold text-yellow-600">{stats.warning}</div>
          <div className="text-xs text-yellow-700">Warning</div>
        </div>
        <div className="bg-blue-50 p-3 rounded-lg text-center">
          <div className="text-2xl font-bold text-blue-600">{stats.total}</div>
          <div className="text-xs text-blue-700">Total</div>
        </div>
      </div>
    </div>
  );
};

const ActiveAlertsWidget = ({ data }) => {
  const chartData = data || [
    { name: 'Critical', value: 5 },
    { name: 'Warning', value: 12 },
    { name: 'Info', value: 8 },
  ];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={60}
          paddingAngle={5}
          dataKey="value"
          label={({ name, value }) => `${name}: ${value}`}
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
};

const IncidentTrendsWidget = ({ data }) => {
  const chartData = data || [
    { date: 'Mon', opened: 4, closed: 2 },
    { date: 'Tue', opened: 3, closed: 5 },
    { date: 'Wed', opened: 6, closed: 4 },
    { date: 'Thu', opened: 2, closed: 3 },
    { date: 'Fri', opened: 5, closed: 6 },
    { date: 'Sat', opened: 1, closed: 2 },
    { date: 'Sun', opened: 2, closed: 1 },
  ];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Area type="monotone" dataKey="opened" stackId="1" stroke="#ef4444" fill="#fecaca" name="Opened" />
        <Area type="monotone" dataKey="closed" stackId="2" stroke="#10b981" fill="#bbf7d0" name="Closed" />
      </AreaChart>
    </ResponsiveContainer>
  );
};

const TopologyMiniWidget = ({ data }) => {
  return (
    <div className="h-full flex items-center justify-center bg-slate-50 rounded-lg">
      <div className="text-center">
        <Network className="h-12 w-12 text-blue-500 mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">Network Topology</p>
        <p className="text-xs text-muted-foreground">{data?.nodes || 0} nodes • {data?.connections || 0} links</p>
        <Button variant="link" size="sm" className="mt-2" onClick={() => window.location.href = '/topology'}>
          View Full Map
        </Button>
      </div>
    </div>
  );
};

const PerformanceMetricsWidget = ({ data }) => {
  const chartData = data || [
    { time: '00:00', cpu: 45, memory: 62, network: 30 },
    { time: '04:00', cpu: 52, memory: 58, network: 45 },
    { time: '08:00', cpu: 78, memory: 71, network: 65 },
    { time: '12:00', cpu: 85, memory: 75, network: 72 },
    { time: '16:00', cpu: 72, memory: 68, network: 58 },
    { time: '20:00', cpu: 55, memory: 60, network: 40 },
  ];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 10 }} />
        <Line type="monotone" dataKey="cpu" stroke="#3b82f6" name="CPU %" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="memory" stroke="#10b981" name="Memory %" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="network" stroke="#f59e0b" name="Network %" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
};

const RecentActivityWidget = ({ data }) => {
  const activities = data || [
    { id: 1, type: 'alert', message: 'High CPU on Server-01', time: '2 min ago', severity: 'warning' },
    { id: 2, type: 'incident', message: 'Incident #123 resolved', time: '5 min ago', severity: 'success' },
    { id: 3, type: 'device', message: 'Router-Core went offline', time: '10 min ago', severity: 'critical' },
    { id: 4, type: 'alert', message: 'Memory threshold exceeded', time: '15 min ago', severity: 'warning' },
    { id: 5, type: 'system', message: 'Backup completed', time: '30 min ago', severity: 'info' },
  ];
  
  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <XCircle className="h-4 w-4 text-red-500" />;
      case 'warning': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'success': return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      default: return <Clock className="h-4 w-4 text-blue-500" />;
    }
  };
  
  return (
    <ScrollArea className="h-full">
      <div className="space-y-2 pr-2">
        {activities.map(activity => (
          <div key={activity.id} className="flex items-start gap-2 p-2 bg-slate-50 rounded-lg">
            {getSeverityIcon(activity.severity)}
            <div className="flex-1 min-w-0">
              <p className="text-sm truncate">{activity.message}</p>
              <p className="text-xs text-muted-foreground">{activity.time}</p>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

const SLAComplianceWidget = ({ data }) => {
  const sla = data || { compliance: 98.5, target: 99.9, trend: 'up' };
  return (
    <div className="h-full flex flex-col justify-center items-center">
      <div className="text-4xl font-bold text-blue-600">{sla.compliance}%</div>
      <div className="text-sm text-muted-foreground">SLA Compliance</div>
      <div className="flex items-center gap-1 mt-2">
        <span className="text-xs">Target: {sla.target}%</span>
        {sla.compliance >= sla.target ? (
          <Badge className="bg-green-100 text-green-700">On Track</Badge>
        ) : (
          <Badge className="bg-red-100 text-red-700">Below Target</Badge>
        )}
      </div>
    </div>
  );
};

const CustomMetricWidget = ({ data, config }) => {
  return (
    <div className="h-full flex flex-col justify-center items-center">
      <div className="text-3xl font-bold text-blue-600">{config?.value || data?.value || '0'}</div>
      <div className="text-sm text-muted-foreground">{config?.label || 'Custom Metric'}</div>
    </div>
  );
};

// Widget renderer
const renderWidget = (widgetType, data, config) => {
  switch (widgetType) {
    case 'device_status': return <DeviceStatusWidget data={data} />;
    case 'active_alerts': return <ActiveAlertsWidget data={data} />;
    case 'incident_trends': return <IncidentTrendsWidget data={data} />;
    case 'topology_mini': return <TopologyMiniWidget data={data} />;
    case 'performance_metrics': return <PerformanceMetricsWidget data={data} />;
    case 'recent_activity': return <RecentActivityWidget data={data} />;
    case 'sla_compliance': return <SLAComplianceWidget data={data} />;
    case 'custom_metric': return <CustomMetricWidget data={data} config={config} />;
    default: return <div className="text-center text-muted-foreground">Unknown widget</div>;
  }
};

export default function DashboardEditorPage() {
  const { user } = useAuth();
  const [layout, setLayout] = useState(DEFAULT_LAYOUT);
  const [editMode, setEditMode] = useState(false);
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [dashboardData, setDashboardData] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [useGlobalLayout, setUseGlobalLayout] = useState(false);
  const [widgetConfigs, setWidgetConfigs] = useState({});
  
  const isAdmin = user?.role === 'admin';

  // Fetch dashboard data and layout
  const fetchDashboardData = useCallback(async () => {
    try {
      const API = getApiUrl();
      const [statsRes, layoutRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`, { headers: getAuthHeader() }),
        axios.get(`${API}/dashboard/layout`, { headers: getAuthHeader() })
      ]);
      
      setDashboardData(statsRes.data);
      
      if (layoutRes.data?.layout) {
        setLayout(layoutRes.data.layout);
        setUseGlobalLayout(layoutRes.data.is_global || false);
        setWidgetConfigs(layoutRes.data.widget_configs || {});
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleLayoutChange = (newLayout) => {
    if (editMode) {
      const updatedLayout = newLayout.map(item => {
        const existing = layout.find(l => l.i === item.i);
        return { ...item, widgetType: existing?.widgetType };
      });
      setLayout(updatedLayout);
    }
  };

  const handleSaveLayout = async (saveAsGlobal = false) => {
    setSaving(true);
    try {
      const API = getApiUrl();
      await axios.post(`${API}/dashboard/layout`, {
        layout,
        widget_configs: widgetConfigs,
        is_global: saveAsGlobal
      }, { headers: getAuthHeader() });
      
      toast.success(saveAsGlobal ? 'Global layout saved' : 'Layout saved');
      setEditMode(false);
    } catch (error) {
      toast.error('Failed to save layout');
    } finally {
      setSaving(false);
    }
  };

  const handleResetLayout = () => {
    setLayout(DEFAULT_LAYOUT);
    setWidgetConfigs({});
    toast.info('Layout reset to default');
  };

  const handleAddWidget = (widgetDef) => {
    const newId = `${widgetDef.id}_${Date.now()}`;
    const newWidget = {
      i: newId,
      x: 0,
      y: Infinity,
      w: widgetDef.defaultW,
      h: widgetDef.defaultH,
      minW: widgetDef.minW,
      minH: widgetDef.minH,
      widgetType: widgetDef.id
    };
    setLayout([...layout, newWidget]);
    setShowAddWidget(false);
    toast.success(`Added ${widgetDef.name}`);
  };

  const handleRemoveWidget = (widgetId) => {
    setLayout(layout.filter(item => item.i !== widgetId));
    const newConfigs = { ...widgetConfigs };
    delete newConfigs[widgetId];
    setWidgetConfigs(newConfigs);
    toast.info('Widget removed');
  };

  const getWidgetTitle = (widgetType) => {
    const widget = AVAILABLE_WIDGETS.find(w => w.id === widgetType);
    return widget?.name || 'Widget';
  };

  const getWidgetIcon = (widgetType) => {
    const widget = AVAILABLE_WIDGETS.find(w => w.id === widgetType);
    const Icon = widget?.icon || LayoutDashboard;
    return <Icon className="h-4 w-4" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-6" data-testid="dashboard-editor">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <LayoutDashboard className="h-6 w-6 text-blue-600" />
            Dashboard
            {editMode && <Badge variant="outline" className="ml-2">Edit Mode</Badge>}
          </h1>
          <p className="text-muted-foreground">
            {editMode ? 'Drag and resize widgets to customize your dashboard' : 'Your personalized NOC overview'}
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          {editMode ? (
            <>
              <Button variant="outline" onClick={() => setShowAddWidget(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Widget
              </Button>
              <Button variant="outline" onClick={handleResetLayout}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset
              </Button>
              <Button variant="outline" onClick={() => setEditMode(false)}>
                Cancel
              </Button>
              <Button onClick={() => handleSaveLayout(false)} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                Save
              </Button>
              {isAdmin && (
                <Button variant="secondary" onClick={() => handleSaveLayout(true)} disabled={saving}>
                  <Globe className="h-4 w-4 mr-2" />
                  Save as Global
                </Button>
              )}
            </>
          ) : (
            <Button onClick={() => setEditMode(true)}>
              <Settings className="h-4 w-4 mr-2" />
              Edit Dashboard
            </Button>
          )}
        </div>
      </div>

      {/* Global layout indicator */}
      {useGlobalLayout && !editMode && (
        <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Lock className="h-4 w-4" />
          Using global layout set by administrator
        </div>
      )}

      {/* Dashboard Grid */}
      <GridLayout
        className="layout"
        layout={layout}
        cols={12}
        rowHeight={80}
        width={1200}
        onLayoutChange={handleLayoutChange}
        isDraggable={editMode}
        isResizable={editMode}
        draggableHandle=".widget-drag-handle"
      >
        {layout.map(item => (
          <div key={item.i} className="bg-white rounded-lg shadow-sm border overflow-hidden">
            <Card className="h-full flex flex-col">
              <CardHeader className={`py-2 px-3 flex-shrink-0 ${editMode ? 'widget-drag-handle cursor-move bg-slate-50' : ''}`}>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    {getWidgetIcon(item.widgetType)}
                    {getWidgetTitle(item.widgetType)}
                  </CardTitle>
                  {editMode && (
                    <div className="flex items-center gap-1">
                      <Move className="h-4 w-4 text-muted-foreground" />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                        onClick={() => handleRemoveWidget(item.i)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex-1 p-3 overflow-hidden">
                {renderWidget(item.widgetType, dashboardData[item.widgetType], widgetConfigs[item.i])}
              </CardContent>
            </Card>
          </div>
        ))}
      </GridLayout>

      {/* Add Widget Dialog */}
      <Dialog open={showAddWidget} onOpenChange={setShowAddWidget}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add Widget</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-4">
            {AVAILABLE_WIDGETS.map(widget => (
              <div
                key={widget.id}
                className="border rounded-lg p-3 cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
                onClick={() => handleAddWidget(widget)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <widget.icon className="h-5 w-5 text-blue-600" />
                  <span className="font-medium text-sm">{widget.name}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Min size: {widget.minW}x{widget.minH}
                </p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
