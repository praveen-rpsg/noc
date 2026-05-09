import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import axios from 'axios';
import { getApiUrl } from '../services/config';
import { getAuthHeader } from '../services/auth';
import { useAuth } from '../context/AuthContext';
import {
  FileText,
  Search,
  Download,
  RefreshCw,
  Filter,
  Calendar,
  User,
  Activity,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Shield,
  Trash2,
  Eye,
  Clock,
  Server,
  Settings,
  Terminal,
  Bot,
  AlertTriangle
} from 'lucide-react';

// Action type icons
const ACTION_ICONS = {
  login: User,
  logout: User,
  user_create: User,
  user_update: User,
  user_delete: User,
  device_create: Server,
  device_update: Server,
  device_delete: Server,
  config_backup: FileText,
  config_restore: FileText,
  config_fetch: FileText,
  incident_create: AlertTriangle,
  incident_update: AlertTriangle,
  incident_resolve: CheckCircle2,
  alert_acknowledge: Activity,
  alert_resolve: CheckCircle2,
  ssh_connect: Terminal,
  ssh_command: Terminal,
  ai_agent_run: Bot,
  ai_action_approve: CheckCircle2,
  ai_action_reject: XCircle,
  aaa_auth: Shield,
  settings_update: Settings,
  system_action: Settings
};

// Action type colors
const ACTION_COLORS = {
  login: 'bg-blue-100 text-blue-700',
  logout: 'bg-slate-100 text-slate-700',
  user_create: 'bg-green-100 text-green-700',
  user_update: 'bg-yellow-100 text-yellow-700',
  user_delete: 'bg-red-100 text-red-700',
  device_create: 'bg-green-100 text-green-700',
  device_update: 'bg-yellow-100 text-yellow-700',
  device_delete: 'bg-red-100 text-red-700',
  config_backup: 'bg-purple-100 text-purple-700',
  config_restore: 'bg-orange-100 text-orange-700',
  config_fetch: 'bg-blue-100 text-blue-700',
  incident_create: 'bg-red-100 text-red-700',
  incident_update: 'bg-yellow-100 text-yellow-700',
  incident_resolve: 'bg-green-100 text-green-700',
  alert_acknowledge: 'bg-yellow-100 text-yellow-700',
  alert_resolve: 'bg-green-100 text-green-700',
  ssh_connect: 'bg-cyan-100 text-cyan-700',
  ssh_command: 'bg-cyan-100 text-cyan-700',
  ai_agent_run: 'bg-violet-100 text-violet-700',
  ai_action_approve: 'bg-green-100 text-green-700',
  ai_action_reject: 'bg-red-100 text-red-700',
  aaa_auth: 'bg-indigo-100 text-indigo-700',
  settings_update: 'bg-slate-100 text-slate-700',
  system_action: 'bg-slate-100 text-slate-700'
};

export default function AuditLogsPage() {
  const { user } = useAuth();
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 50;
  
  // Filters
  const [filters, setFilters] = useState({
    action_type: '',
    user_email: '',
    resource_type: '',
    start_date: '',
    end_date: '',
    success_only: null
  });
  
  // Action types for filter
  const [actionTypes, setActionTypes] = useState([]);
  
  // Detail dialog
  const [selectedLog, setSelectedLog] = useState(null);
  const [showDetailDialog, setShowDetailDialog] = useState(false);

  const isAdmin = user?.role === 'admin';

  // Fetch logs
  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const API = getApiUrl();
      const params = new URLSearchParams();
      params.append('page', page);
      params.append('limit', limit);
      
      if (filters.action_type) params.append('action_type', filters.action_type);
      if (filters.user_email) params.append('user_email', filters.user_email);
      if (filters.resource_type) params.append('resource_type', filters.resource_type);
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.success_only !== null) params.append('success_only', filters.success_only);
      
      const response = await axios.get(`${API}/audit/logs?${params}`, { headers: getAuthHeader() });
      setLogs(response.data.logs || []);
      setTotal(response.data.total || 0);
      setTotalPages(response.data.pages || 1);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/audit/logs/stats`, { headers: getAuthHeader() });
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }, []);

  // Fetch action types
  const fetchActionTypes = useCallback(async () => {
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/audit/action-types`, { headers: getAuthHeader() });
      setActionTypes(response.data || []);
    } catch (error) {
      console.error('Failed to fetch action types:', error);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      fetchLogs();
      fetchStats();
      fetchActionTypes();
    }
  }, [isAdmin, fetchLogs, fetchStats, fetchActionTypes]);

  // Export logs
  const handleExport = async (format) => {
    setExporting(true);
    try {
      const API = getApiUrl();
      const params = new URLSearchParams();
      params.append('format', format);
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      
      if (format === 'csv') {
        const response = await axios.get(`${API}/audit/logs/export?${params}`, {
          headers: getAuthHeader(),
          responseType: 'blob'
        });
        
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `audit_logs_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        const response = await axios.get(`${API}/audit/logs/export?${params}`, { headers: getAuthHeader() });
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `audit_logs_${new Date().toISOString().split('T')[0]}.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      }
      
      toast.success(`Exported as ${format.toUpperCase()}`);
    } catch (error) {
      toast.error('Failed to export logs');
    } finally {
      setExporting(false);
    }
  };

  // Cleanup old logs
  const handleCleanup = async () => {
    if (!window.confirm('This will delete audit logs older than 90 days. Continue?')) return;
    
    try {
      const API = getApiUrl();
      const response = await axios.delete(`${API}/audit/logs/cleanup`, { headers: getAuthHeader() });
      toast.success(`Cleaned up ${response.data.deleted_count} old logs`);
      fetchLogs();
      fetchStats();
    } catch (error) {
      toast.error('Failed to cleanup logs');
    }
  };

  // Reset filters
  const resetFilters = () => {
    setFilters({
      action_type: '',
      user_email: '',
      resource_type: '',
      start_date: '',
      end_date: '',
      success_only: null
    });
    setPage(1);
  };

  // Format timestamp
  const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    const date = new Date(ts);
    return date.toLocaleString();
  };

  // Get action icon
  const getActionIcon = (actionType) => {
    const Icon = ACTION_ICONS[actionType] || Activity;
    return <Icon className="h-4 w-4" />;
  };

  // Get action color
  const getActionColor = (actionType) => {
    return ACTION_COLORS[actionType] || 'bg-slate-100 text-slate-700';
  };

  // View log details
  const viewLogDetails = (log) => {
    setSelectedLog(log);
    setShowDetailDialog(true);
  };

  // Access check
  if (!isAdmin) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center gap-4 text-muted-foreground">
              <Shield className="h-12 w-12" />
              <p className="text-lg">Admin access required</p>
              <p className="text-sm">You don't have permission to view audit logs</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" data-testid="audit-logs-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6 text-blue-600" />
            Audit Logs
          </h1>
          <p className="text-muted-foreground">Track all user and system actions for compliance</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => { fetchLogs(); fetchStats(); }}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => handleExport('csv')} disabled={exporting}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
          <Button variant="outline" onClick={() => handleExport('json')} disabled={exporting}>
            <Download className="h-4 w-4 mr-2" />
            Export JSON
          </Button>
          <Button variant="outline" onClick={handleCleanup} className="text-red-600 hover:text-red-700">
            <Trash2 className="h-4 w-4 mr-2" />
            Cleanup
          </Button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600">{stats.total_logs?.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Total Logs</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">{stats.today_logs?.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Today's Actions</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-red-600">{stats.failed_actions?.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Failed Actions</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-purple-600">{stats.retention_days}</div>
                <div className="text-sm text-muted-foreground">Retention Days</div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            <div className="space-y-1">
              <Label className="text-xs">Action Type</Label>
              <Select value={filters.action_type || "all"} onValueChange={(v) => setFilters({...filters, action_type: v === "all" ? "" : v})}>
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {actionTypes.map(type => (
                    <SelectItem key={type} value={type}>{type.replace(/_/g, ' ')}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">User Email</Label>
              <Input
                value={filters.user_email}
                onChange={(e) => setFilters({...filters, user_email: e.target.value})}
                placeholder="Search user..."
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Resource Type</Label>
              <Select value={filters.resource_type || "all"} onValueChange={(v) => setFilters({...filters, resource_type: v === "all" ? "" : v})}>
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="device">Device</SelectItem>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="incident">Incident</SelectItem>
                  <SelectItem value="alert">Alert</SelectItem>
                  <SelectItem value="backup">Backup</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Start Date</Label>
              <Input
                type="date"
                value={filters.start_date}
                onChange={(e) => setFilters({...filters, start_date: e.target.value})}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">End Date</Label>
              <Input
                type="date"
                value={filters.end_date}
                onChange={(e) => setFilters({...filters, end_date: e.target.value})}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={() => { setPage(1); fetchLogs(); }} className="flex-1">
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
              <Button variant="outline" onClick={resetFilters}>Reset</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Audit Logs ({total.toLocaleString()})</span>
            <div className="flex items-center gap-2 text-sm font-normal">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span>Page {page} of {totalPages}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No audit logs found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="text-left px-4 py-3 text-sm font-medium">Timestamp</th>
                    <th className="text-left px-4 py-3 text-sm font-medium">Action</th>
                    <th className="text-left px-4 py-3 text-sm font-medium">User</th>
                    <th className="text-left px-4 py-3 text-sm font-medium">Description</th>
                    <th className="text-left px-4 py-3 text-sm font-medium">Resource</th>
                    <th className="text-left px-4 py-3 text-sm font-medium">Status</th>
                    <th className="text-right px-4 py-3 text-sm font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {logs.map(log => (
                    <tr key={log.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3 text-sm">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-muted-foreground" />
                          {formatTimestamp(log.timestamp)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={getActionColor(log.action_type)}>
                          {getActionIcon(log.action_type)}
                          <span className="ml-1">{log.action_type?.replace(/_/g, ' ')}</span>
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div>
                          <div className="font-medium">{log.user_name || 'System'}</div>
                          <div className="text-xs text-muted-foreground">{log.user_email || '-'}</div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm max-w-md truncate">
                        {log.description}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {log.resource_type && (
                          <div>
                            <Badge variant="outline" className="text-xs">{log.resource_type}</Badge>
                            {log.resource_name && (
                              <div className="text-xs text-muted-foreground mt-1">{log.resource_name}</div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {log.success ? (
                          <Badge className="bg-green-100 text-green-700">
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Success
                          </Badge>
                        ) : (
                          <Badge className="bg-red-100 text-red-700">
                            <XCircle className="h-3 w-3 mr-1" />
                            Failed
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewLogDetails(log)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={showDetailDialog} onOpenChange={setShowDetailDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Audit Log Details</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-muted-foreground">Timestamp</Label>
                  <p className="font-medium">{formatTimestamp(selectedLog.timestamp)}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Action Type</Label>
                  <Badge className={getActionColor(selectedLog.action_type)}>
                    {selectedLog.action_type?.replace(/_/g, ' ')}
                  </Badge>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">User</Label>
                  <p className="font-medium">{selectedLog.user_name || 'System'}</p>
                  <p className="text-sm text-muted-foreground">{selectedLog.user_email || '-'}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  <p>{selectedLog.success ? '✅ Success' : '❌ Failed'}</p>
                </div>
              </div>
              
              <div>
                <Label className="text-xs text-muted-foreground">Description</Label>
                <p className="font-medium">{selectedLog.description}</p>
              </div>
              
              {selectedLog.resource_type && (
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">Resource Type</Label>
                    <p>{selectedLog.resource_type}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Resource ID</Label>
                    <p className="text-sm font-mono">{selectedLog.resource_id || '-'}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Resource Name</Label>
                    <p>{selectedLog.resource_name || '-'}</p>
                  </div>
                </div>
              )}
              
              {selectedLog.error_message && (
                <div>
                  <Label className="text-xs text-muted-foreground">Error Message</Label>
                  <p className="text-red-600">{selectedLog.error_message}</p>
                </div>
              )}
              
              {selectedLog.details && Object.keys(selectedLog.details).length > 0 && (
                <div>
                  <Label className="text-xs text-muted-foreground">Additional Details</Label>
                  <pre className="mt-1 p-3 bg-slate-100 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(selectedLog.details, null, 2)}
                  </pre>
                </div>
              )}
              
              {selectedLog.ip_address && (
                <div>
                  <Label className="text-xs text-muted-foreground">IP Address</Label>
                  <p>{selectedLog.ip_address}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDetailDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
