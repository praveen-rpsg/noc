import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { alertsApi, devicesApi } from '../services/api';
import { toast } from 'sonner';
import NetworkDiagnosticsModal from '../components/NetworkDiagnosticsModal';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  Search,
  RefreshCw,
  Filter,
  Eye,
  Brain,
  Loader2,
  ArrowUpRight,
  Activity
} from 'lucide-react';
import { format } from 'date-fns';

const SeverityBadge = ({ severity }) => {
  const styles = {
    critical: 'bg-red-600 text-white',
    high: 'bg-orange-500 text-white',
    medium: 'bg-amber-500 text-white',
    low: 'bg-blue-500 text-white',
    info: 'bg-slate-500 text-white',
  };

  return (
    <Badge className={`${styles[severity] || styles.info} capitalize`}>
      {severity}
    </Badge>
  );
};

const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-red-50 text-red-700 border-red-200',
    acknowledged: 'bg-amber-50 text-amber-700 border-amber-200',
    resolved: 'bg-green-50 text-green-700 border-green-200',
    suppressed: 'bg-slate-50 text-slate-700 border-slate-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.active} capitalize`}>
      {status}
    </Badge>
  );
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  
  // Context menu state
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, alert: null });
  const [isTroubleshootOpen, setIsTroubleshootOpen] = useState(false);
  const [troubleshootResult, setTroubleshootResult] = useState(null);
  const [troubleshootLoading, setTroubleshootLoading] = useState(false);
  
  // Network diagnostics state
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(false);
  const [diagnosticsTarget, setDiagnosticsTarget] = useState('');
  const [diagnosticsDeviceId, setDiagnosticsDeviceId] = useState(null);
  const [diagnosticsDeviceName, setDiagnosticsDeviceName] = useState(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const params = {};
      if (filterStatus !== 'all') params.status = filterStatus;
      if (filterSeverity !== 'all') params.severity = filterSeverity;
      const [alertsRes, devicesRes] = await Promise.all([
        alertsApi.getAll(params),
        devicesApi.getAll()
      ]);
      setAlerts(alertsRes.data);
      setDevices(devicesRes.data);
    } catch (error) {
      toast.error('Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterSeverity]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);
  
  // Close context menu on click outside
  useEffect(() => {
    const handleClick = () => setContextMenu({ visible: false, x: 0, y: 0, alert: null });
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  const handleContextMenu = (e, alert) => {
    e.preventDefault();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      alert
    });
  };

  const handleAiTroubleshoot = async (alert) => {
    setContextMenu({ visible: false, x: 0, y: 0, alert: null });
    setTroubleshootLoading(true);
    setTroubleshootResult(null);
    setIsTroubleshootOpen(true);
    
    try {
      const response = await alertsApi.aiTroubleshoot(alert.id);
      setTroubleshootResult({
        alert,
        ...response.data
      });
      toast.success('AI troubleshooting complete');
    } catch (error) {
      toast.error('Failed to run AI troubleshooting');
      setTroubleshootResult({
        alert,
        analysis: 'Error: Failed to get AI analysis. Please try again.',
        error: true
      });
    } finally {
      setTroubleshootLoading(false);
    }
  };

  // Open network diagnostics for an alert
  const openDiagnostics = (alert) => {
    setContextMenu({ visible: false, x: 0, y: 0, alert: null });
    
    // Get device IP from alert
    const device = devices.find(d => d.id === alert.device_id);
    
    setDiagnosticsTarget(device?.ip_address || '');
    setDiagnosticsDeviceId(alert.device_id);
    setDiagnosticsDeviceName(alert.device_name || device?.name);
    setIsDiagnosticsOpen(true);
  };

  const handleAcknowledge = async (alertId) => {
    try {
      await alertsApi.acknowledge(alertId);
      toast.success('Alert acknowledged');
      fetchAlerts();
    } catch (error) {
      toast.error('Failed to acknowledge alert');
    }
  };

  const handleResolve = async (alertId) => {
    try {
      await alertsApi.resolve(alertId);
      toast.success('Alert resolved');
      fetchAlerts();
    } catch (error) {
      toast.error('Failed to resolve alert');
    }
  };

  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch = alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.device_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const alertStats = {
    total: alerts.length,
    active: alerts.filter(a => a.status === 'active').length,
    critical: alerts.filter(a => a.severity === 'critical' && a.status === 'active').length,
    acknowledged: alerts.filter(a => a.status === 'acknowledged').length,
  };

  return (
    <div data-testid="alerts-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Alerts</h1>
          <p className="text-muted-foreground mt-1">Monitor and manage system alerts</p>
        </div>
        <Button variant="outline" onClick={fetchAlerts} data-testid="refresh-alerts-btn">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Bell className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{alertStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Alerts</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-50">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{alertStats.active}</p>
              <p className="text-sm text-muted-foreground">Active</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-100">
              <AlertTriangle className="h-6 w-6 text-red-700" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-700">{alertStats.critical}</p>
              <p className="text-sm text-muted-foreground">Critical</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-50">
              <Clock className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-600">{alertStats.acknowledged}</p>
              <p className="text-sm text-muted-foreground">Acknowledged</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search alerts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="alert-search"
              />
            </div>
            <Select value={filterSeverity} onValueChange={setFilterSeverity}>
              <SelectTrigger className="w-[180px]" data-testid="filter-severity">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[180px]" data-testid="filter-alert-status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="acknowledged">Acknowledged</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Severity</TableHead>
                  <TableHead>Alert</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Metric</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : filteredAlerts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10">
                      <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-2" />
                      <p className="text-muted-foreground">No alerts found</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAlerts.map((alert) => (
                    <TableRow 
                      key={alert.id} 
                      className="table-row-hover cursor-pointer" 
                      onContextMenu={(e) => handleContextMenu(e, alert)}
                      data-testid={`alert-row-${alert.id}`}
                    >
                      <TableCell>
                        <SeverityBadge severity={alert.severity} />
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{alert.title}</p>
                          <p className="text-xs text-muted-foreground truncate max-w-xs">{alert.description}</p>
                        </div>
                      </TableCell>
                      <TableCell>{alert.device_name}</TableCell>
                      <TableCell>
                        <StatusBadge status={alert.status} />
                      </TableCell>
                      <TableCell>
                        {alert.metric_name && (
                          <span className="text-sm">
                            {alert.metric_name}: {alert.metric_value?.toFixed(1)} 
                            <span className="text-muted-foreground"> / {alert.threshold}</span>
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {format(new Date(alert.created_at), 'MMM d, HH:mm')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {alert.status === 'active' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleAcknowledge(alert.id)}
                              data-testid={`ack-alert-${alert.id}`}
                            >
                              Acknowledge
                            </Button>
                          )}
                          {alert.status !== 'resolved' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleResolve(alert.id)}
                              className="text-green-600 hover:text-green-700"
                              data-testid={`resolve-alert-${alert.id}`}
                            >
                              Resolve
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Context Menu */}
      {contextMenu.visible && (
        <div 
          className="fixed z-50 bg-white rounded-lg shadow-lg border border-border/50 py-2 min-w-[200px]"
          style={{ 
            left: Math.min(contextMenu.x, window.innerWidth - 220),
            top: Math.min(contextMenu.y, window.innerHeight - 200)
          }}
          data-testid="alert-context-menu"
        >
          <button
            className="w-full px-4 py-2 text-left hover:bg-purple-50 flex items-center gap-2 text-sm"
            onClick={() => handleAiTroubleshoot(contextMenu.alert)}
            data-testid="context-menu-troubleshoot"
          >
            <Brain className="h-4 w-4 text-purple-600" />
            <span className="font-medium">AI Troubleshoot</span>
          </button>
          <button
            className="w-full px-4 py-2 text-left hover:bg-cyan-50 flex items-center gap-2 text-sm"
            onClick={() => openDiagnostics(contextMenu.alert)}
            data-testid="context-menu-diagnostics"
          >
            <Activity className="h-4 w-4 text-cyan-600" />
            <span>Network Diagnostics</span>
          </button>
          {contextMenu.alert?.status === 'active' && (
            <button
              className="w-full px-4 py-2 text-left hover:bg-amber-50 flex items-center gap-2 text-sm border-t border-border/30 mt-1 pt-2"
              onClick={() => {
                handleAcknowledge(contextMenu.alert.id);
                setContextMenu({ visible: false, x: 0, y: 0, alert: null });
              }}
              data-testid="context-menu-acknowledge"
            >
              <Eye className="h-4 w-4 text-amber-600" />
              <span>Acknowledge</span>
            </button>
          )}
          {contextMenu.alert?.status !== 'resolved' && (
            <button
              className="w-full px-4 py-2 text-left hover:bg-green-50 flex items-center gap-2 text-sm"
              onClick={() => {
                handleResolve(contextMenu.alert.id);
                setContextMenu({ visible: false, x: 0, y: 0, alert: null });
              }}
              data-testid="context-menu-resolve"
            >
              <CheckCircle className="h-4 w-4 text-green-600" />
              <span>Resolve</span>
            </button>
          )}
        </div>
      )}

      {/* AI Troubleshoot Modal */}
      <Dialog open={isTroubleshootOpen} onOpenChange={setIsTroubleshootOpen}>
        <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Brain className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <DialogTitle>AI Troubleshooting Report</DialogTitle>
                {troubleshootResult?.alert && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {troubleshootResult.alert.title} - {troubleshootResult.alert.device_name}
                  </p>
                )}
              </div>
            </div>
          </DialogHeader>
          
          <div className="mt-4">
            {troubleshootLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-12 w-12 animate-spin text-purple-600 mb-4" />
                <p className="text-lg font-medium">AI Agent is analyzing...</p>
                <p className="text-sm text-muted-foreground">Gathering alert data and generating troubleshooting report</p>
              </div>
            ) : troubleshootResult ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>Report ID: {troubleshootResult.report_id}</span>
                  <span>Generated: {troubleshootResult.created_at ? format(new Date(troubleshootResult.created_at), 'PPpp') : 'N/A'}</span>
                </div>
                
                {troubleshootResult.alert && (
                  <div className="flex gap-2">
                    <SeverityBadge severity={troubleshootResult.alert.severity} />
                    <StatusBadge status={troubleshootResult.alert.status} />
                  </div>
                )}
                
                <Card className={`${troubleshootResult.error ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
                  <CardContent className="p-4">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                      {troubleshootResult.analysis}
                    </pre>
                  </CardContent>
                </Card>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsTroubleshootOpen(false)}>
                    Close
                  </Button>
                </DialogFooter>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      {/* Network Diagnostics Modal */}
      <NetworkDiagnosticsModal
        isOpen={isDiagnosticsOpen}
        onClose={() => setIsDiagnosticsOpen(false)}
        defaultTarget={diagnosticsTarget}
        deviceId={diagnosticsDeviceId}
        deviceName={diagnosticsDeviceName}
      />
    </div>
  );
}
