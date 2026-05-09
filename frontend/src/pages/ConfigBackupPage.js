import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import axios from 'axios';
import { getApiUrl } from '../services/config';
import { getAuthHeader } from '../services/auth';
import { useAuth } from '../context/AuthContext';
import {
  FileText,
  Download,
  RefreshCw,
  Server,
  History,
  Loader2,
  Eye,
  GitCompare,
  Upload,
  Trash2,
  Clock,
  CheckCircle2,
  XCircle,
  HardDrive,
  Database,
  AlertTriangle,
  Play,
  Search
} from 'lucide-react';

export default function ConfigBackupPage() {
  const { user } = useAuth();
  const [devices, setDevices] = useState([]);
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backupsLoading, setBackupsLoading] = useState(false);
  
  // Selected device
  const [selectedDevice, setSelectedDevice] = useState(null);
  
  // Dialogs
  const [showFetchDialog, setShowFetchDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [showRestoreDialog, setShowRestoreDialog] = useState(false);
  const [showCredentialsDialog, setShowCredentialsDialog] = useState(false);
  
  // Current data
  const [currentConfig, setCurrentConfig] = useState(null);
  const [selectedBackup, setSelectedBackup] = useState(null);
  const [diffResult, setDiffResult] = useState(null);
  const [compareBackupId, setCompareBackupId] = useState('');
  
  // Credentials
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    port: 22
  });
  
  // Action states
  const [fetching, setFetching] = useState(false);
  const [backing, setBacking] = useState(false);
  const [restoring, setRestoring] = useState(false);
  
  // Pending action
  const [pendingAction, setPendingAction] = useState(null);
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch devices
  const fetchDevices = useCallback(async () => {
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/devices`, { headers: getAuthHeader() });
      // Filter to devices that support config backup (routers, switches, firewalls)
      const configDevices = (response.data || []).filter(d => 
        ['router', 'switch', 'firewall', 'load_balancer'].includes(d.type)
      );
      setDevices(configDevices);
    } catch (error) {
      console.error('Failed to fetch devices:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch backups for selected device
  const fetchBackups = useCallback(async () => {
    if (!selectedDevice) return;
    
    setBackupsLoading(true);
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/backup/devices/${selectedDevice.id}/backups`, { headers: getAuthHeader() });
      setBackups(response.data || []);
    } catch (error) {
      console.error('Failed to fetch backups:', error);
    } finally {
      setBackupsLoading(false);
    }
  }, [selectedDevice]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  useEffect(() => {
    if (selectedDevice) {
      fetchBackups();
    }
  }, [selectedDevice, fetchBackups]);

  // Open credentials dialog for action
  const promptCredentials = (action, device = null) => {
    setPendingAction(action);
    if (device) setSelectedDevice(device);
    setCredentials({ username: '', password: '', port: 22 });
    setShowCredentialsDialog(true);
  };

  // Execute action after credentials
  const executeWithCredentials = async () => {
    setShowCredentialsDialog(false);
    
    if (pendingAction === 'fetch') {
      await handleFetchConfig();
    } else if (pendingAction === 'backup') {
      await handleCreateBackup();
    } else if (pendingAction === 'restore') {
      await handleRestore();
    }
  };

  // Fetch current config
  const handleFetchConfig = async () => {
    if (!selectedDevice) return;
    
    setFetching(true);
    setShowFetchDialog(true);
    setCurrentConfig(null);
    
    try {
      const API = getApiUrl();
      const response = await axios.post(
        `${API}/backup/devices/${selectedDevice.id}/fetch`,
        credentials.username ? credentials : null,
        { headers: getAuthHeader() }
      );
      
      if (response.data.success) {
        setCurrentConfig(response.data);
        toast.success('Configuration fetched successfully');
      } else {
        toast.error(response.data.error || 'Failed to fetch config');
        setShowFetchDialog(false);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to fetch configuration');
      setShowFetchDialog(false);
    } finally {
      setFetching(false);
    }
  };

  // Create backup
  const handleCreateBackup = async () => {
    if (!selectedDevice) return;
    
    setBacking(true);
    try {
      const API = getApiUrl();
      const response = await axios.post(
        `${API}/backup/devices/${selectedDevice.id}/backup`,
        credentials.username ? { credentials, backup_type: 'manual' } : { backup_type: 'manual' },
        { headers: getAuthHeader() }
      );
      
      toast.success(`Backup v${response.data.version} created successfully`);
      fetchBackups();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create backup');
    } finally {
      setBacking(false);
    }
  };

  // View backup
  const handleViewBackup = async (backup) => {
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/backup/backups/${backup.id}`, { headers: getAuthHeader() });
      setSelectedBackup(response.data);
      setShowViewDialog(true);
    } catch (error) {
      toast.error('Failed to load backup');
    }
  };

  // Compare backups
  const handleCompare = async () => {
    if (!selectedBackup || !compareBackupId) return;
    
    try {
      const API = getApiUrl();
      const response = await axios.get(
        `${API}/backup/backups/${selectedBackup.id}/diff/${compareBackupId}`,
        { headers: getAuthHeader() }
      );
      setDiffResult(response.data);
      setShowDiffDialog(true);
    } catch (error) {
      toast.error('Failed to compare backups');
    }
  };

  // Restore backup
  const handleRestore = async () => {
    if (!selectedDevice || !selectedBackup) return;
    
    setRestoring(true);
    try {
      const API = getApiUrl();
      const response = await axios.post(
        `${API}/backup/devices/${selectedDevice.id}/restore/${selectedBackup.id}`,
        credentials.username ? credentials : null,
        { headers: getAuthHeader() }
      );
      
      if (response.data.success) {
        toast.success('Configuration restored successfully');
        setShowRestoreDialog(false);
      } else {
        toast.error(response.data.error || 'Restore failed');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to restore configuration');
    } finally {
      setRestoring(false);
    }
  };

  // Delete backup
  const handleDeleteBackup = async (backupId) => {
    if (!window.confirm('Are you sure you want to delete this backup?')) return;
    
    try {
      const API = getApiUrl();
      await axios.delete(`${API}/backup/backups/${backupId}`, { headers: getAuthHeader() });
      toast.success('Backup deleted');
      fetchBackups();
    } catch (error) {
      toast.error('Failed to delete backup');
    }
  };

  // Format timestamp
  const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    return new Date(ts).toLocaleString();
  };

  // Format size
  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Filter devices
  const filteredDevices = devices.filter(d => 
    d.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.ip_address?.includes(searchQuery) ||
    d.vendor?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6" data-testid="config-backup-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6 text-blue-600" />
            Configuration Backup & Restore
          </h1>
          <p className="text-muted-foreground">Backup and restore device configurations with multi-vendor support</p>
        </div>
        <Button variant="outline" onClick={fetchDevices}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Devices List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Network Devices
            </CardTitle>
            <CardDescription>Select a device to manage backups</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search devices..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <ScrollArea className="h-[500px]">
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : filteredDevices.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No network devices found
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredDevices.map(device => (
                    <div
                      key={device.id}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedDevice?.id === device.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-border hover:border-blue-300 hover:bg-slate-50'
                      }`}
                      onClick={() => setSelectedDevice(device)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{device.name}</div>
                          <div className="text-sm text-muted-foreground">{device.ip_address}</div>
                        </div>
                        <div className="text-right">
                          <Badge variant="outline" className="text-xs">{device.vendor || 'Unknown'}</Badge>
                          <div className="text-xs text-muted-foreground mt-1">{device.type}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Backups Panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <History className="h-5 w-5" />
                  Configuration Backups
                  {selectedDevice && (
                    <Badge className="ml-2">{selectedDevice.name}</Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  {selectedDevice ? `Backups for ${selectedDevice.name}` : 'Select a device to view backups'}
                </CardDescription>
              </div>
              {selectedDevice && (
                <div className="flex items-center gap-2">
                  <Button variant="outline" onClick={() => promptCredentials('fetch')}>
                    <Eye className="h-4 w-4 mr-2" />
                    View Current
                  </Button>
                  <Button onClick={() => promptCredentials('backup')}>
                    <Download className="h-4 w-4 mr-2" />
                    Create Backup
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!selectedDevice ? (
              <div className="text-center py-12 text-muted-foreground">
                <Server className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a device from the list to manage its configuration backups</p>
              </div>
            ) : backupsLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            ) : backups.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No backups found for this device</p>
                <p className="text-sm mt-2">Click "Create Backup" to save the current configuration</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="text-left px-4 py-3 text-sm font-medium">Version</th>
                      <th className="text-left px-4 py-3 text-sm font-medium">Created</th>
                      <th className="text-left px-4 py-3 text-sm font-medium">Type</th>
                      <th className="text-left px-4 py-3 text-sm font-medium">Created By</th>
                      <th className="text-left px-4 py-3 text-sm font-medium">Size</th>
                      <th className="text-right px-4 py-3 text-sm font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {backups.map(backup => (
                      <tr key={backup.id} className="hover:bg-slate-50/50">
                        <td className="px-4 py-3">
                          <Badge className="bg-blue-100 text-blue-700">v{backup.version}</Badge>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            {formatTimestamp(backup.created_at)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline">{backup.backup_type}</Badge>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {backup.created_by || 'System'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {formatSize(backup.size_bytes)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewBackup(backup)}
                              title="View backup"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setSelectedBackup(backup);
                                setShowRestoreDialog(true);
                              }}
                              title="Restore"
                            >
                              <Upload className="h-4 w-4 text-orange-500" />
                            </Button>
                            {user?.role === 'admin' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteBackup(backup.id)}
                                title="Delete"
                                className="text-red-500 hover:text-red-700"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Credentials Dialog */}
      <Dialog open={showCredentialsDialog} onOpenChange={setShowCredentialsDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>SSH Credentials</DialogTitle>
            <DialogDescription>
              Enter SSH credentials for {selectedDevice?.name}. Leave blank to use stored credentials.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Username</Label>
              <Input
                value={credentials.username}
                onChange={(e) => setCredentials({...credentials, username: e.target.value})}
                placeholder="admin"
              />
            </div>
            <div className="space-y-2">
              <Label>Password</Label>
              <Input
                type="password"
                value={credentials.password}
                onChange={(e) => setCredentials({...credentials, password: e.target.value})}
                placeholder="••••••••"
              />
            </div>
            <div className="space-y-2">
              <Label>SSH Port</Label>
              <Input
                type="number"
                value={credentials.port}
                onChange={(e) => setCredentials({...credentials, port: parseInt(e.target.value)})}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCredentialsDialog(false)}>Cancel</Button>
            <Button onClick={executeWithCredentials}>
              <Play className="h-4 w-4 mr-2" />
              Connect & Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Fetch Config Dialog */}
      <Dialog open={showFetchDialog} onOpenChange={setShowFetchDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Current Configuration - {selectedDevice?.name}</DialogTitle>
          </DialogHeader>
          {fetching ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin mb-4" />
              <p>Fetching configuration from device...</p>
            </div>
          ) : currentConfig ? (
            <ScrollArea className="h-[500px]">
              <pre className="text-xs bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto">
                {currentConfig.config}
              </pre>
            </ScrollArea>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No configuration data
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowFetchDialog(false)}>Close</Button>
            {currentConfig && (
              <Button onClick={handleCreateBackup} disabled={backing}>
                {backing ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Download className="h-4 w-4 mr-2" />}
                Save as Backup
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Backup Dialog */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>
              Backup v{selectedBackup?.version} - {selectedBackup?.device_name}
            </DialogTitle>
          </DialogHeader>
          <div className="flex items-center gap-4 mb-4">
            <div>
              <Label className="text-xs text-muted-foreground">Created</Label>
              <p className="text-sm">{formatTimestamp(selectedBackup?.created_at)}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Size</Label>
              <p className="text-sm">{formatSize(selectedBackup?.size_bytes)}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Created By</Label>
              <p className="text-sm">{selectedBackup?.created_by}</p>
            </div>
            <div className="flex-1" />
            <div className="flex items-center gap-2">
              <Select value={compareBackupId} onValueChange={setCompareBackupId}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Compare with..." />
                </SelectTrigger>
                <SelectContent>
                  {backups.filter(b => b.id !== selectedBackup?.id).map(b => (
                    <SelectItem key={b.id} value={b.id}>v{b.version}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={handleCompare} disabled={!compareBackupId}>
                <GitCompare className="h-4 w-4 mr-2" />
                Compare
              </Button>
            </div>
          </div>
          <ScrollArea className="h-[400px]">
            <pre className="text-xs bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto">
              {selectedBackup?.config_data}
            </pre>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowViewDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Diff Dialog */}
      <Dialog open={showDiffDialog} onOpenChange={setShowDiffDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Configuration Comparison</DialogTitle>
          </DialogHeader>
          {diffResult && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <Badge>v{diffResult.backup1?.version} ({formatTimestamp(diffResult.backup1?.created_at)})</Badge>
                <span className="text-muted-foreground">vs</span>
                <Badge>v{diffResult.backup2?.version} ({formatTimestamp(diffResult.backup2?.created_at)})</Badge>
              </div>
              {diffResult.changes_detected ? (
                <ScrollArea className="h-[400px]">
                  <pre className="text-xs bg-slate-900 p-4 rounded-lg overflow-x-auto font-mono">
                    {diffResult.diff.split('\n').map((line, i) => (
                      <div
                        key={`diff-line-${i}-${line.slice(0, 10)}`}
                        className={
                          line.startsWith('+') ? 'text-green-400' :
                          line.startsWith('-') ? 'text-red-400' :
                          line.startsWith('@') ? 'text-blue-400' :
                          'text-slate-400'
                        }
                      >
                        {line}
                      </div>
                    ))}
                  </pre>
                </ScrollArea>
              ) : (
                <div className="text-center py-8">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                  <p>No differences found between these backups</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDiffDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Restore Confirmation Dialog */}
      <Dialog open={showRestoreDialog} onOpenChange={setShowRestoreDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-600">
              <AlertTriangle className="h-5 w-5" />
              Restore Configuration
            </DialogTitle>
            <DialogDescription>
              This will restore the configuration from backup v{selectedBackup?.version} to {selectedDevice?.name}.
              This action may cause network disruption.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-sm">
              <ul className="list-disc list-inside space-y-1 text-orange-800">
                <li>Current configuration will be overwritten</li>
                <li>Device may need to reboot</li>
                <li>Network connectivity may be temporarily affected</li>
                <li>It is recommended to create a backup before restoring</li>
              </ul>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRestoreDialog(false)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => promptCredentials('restore')}
              disabled={restoring}
            >
              {restoring ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
              Restore Configuration
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
