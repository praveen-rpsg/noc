import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { configApi, devicesApi } from '../services/api';
import { toast } from 'sonner';
import {
  Settings,
  Save,
  RefreshCw,
  FileCode,
  CheckCircle,
  XCircle,
  Shield,
  Loader2
} from 'lucide-react';
import { format } from 'date-fns';

export default function ConfigurationPage() {
  const [configs, setConfigs] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [configType, setConfigType] = useState('running');
  const [configData, setConfigData] = useState('');

  const fetchData = async () => {
    try {
      const [configsRes, devicesRes] = await Promise.all([
        configApi.getAll(),
        devicesApi.getAll(),
      ]);
      setConfigs(configsRes.data);
      setDevices(devicesRes.data);
    } catch (error) {
      toast.error('Failed to fetch configuration data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleBackup = async () => {
    if (!selectedDevice || !configData) {
      toast.error('Please select a device and enter configuration');
      return;
    }
    
    setSaving(true);
    try {
      await configApi.backup(selectedDevice, configType, configData);
      toast.success('Configuration backed up successfully');
      setConfigData('');
      fetchData();
    } catch (error) {
      toast.error('Failed to backup configuration');
    } finally {
      setSaving(false);
    }
  };

  const configStats = {
    total: configs.length,
    compliant: configs.filter(c => c.is_compliant).length,
    nonCompliant: configs.filter(c => !c.is_compliant).length,
  };

  return (
    <div data-testid="configuration-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Configuration Management</h1>
          <p className="text-muted-foreground mt-1">Backup and manage device configurations</p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <FileCode className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{configStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Backups</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-50">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{configStats.compliant}</p>
              <p className="text-sm text-muted-foreground">Compliant</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-50">
              <XCircle className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{configStats.nonCompliant}</p>
              <p className="text-sm text-muted-foreground">Non-Compliant</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Backup Form */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Save className="h-5 w-5" />
            Backup Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Device</label>
              <Select value={selectedDevice} onValueChange={setSelectedDevice}>
                <SelectTrigger data-testid="config-device-select">
                  <SelectValue placeholder="Select device" />
                </SelectTrigger>
                <SelectContent>
                  {devices.map((device) => (
                    <SelectItem key={device.id} value={device.id}>
                      {device.name} ({device.ip_address})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Configuration Type</label>
              <Select value={configType} onValueChange={setConfigType}>
                <SelectTrigger data-testid="config-type-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="running">Running Config</SelectItem>
                  <SelectItem value="startup">Startup Config</SelectItem>
                  <SelectItem value="backup">Full Backup</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Configuration Data</label>
            <Textarea
              value={configData}
              onChange={(e) => setConfigData(e.target.value)}
              placeholder="Paste configuration here..."
              rows={10}
              className="font-mono text-sm"
              data-testid="config-data-input"
            />
          </div>
          <Button onClick={handleBackup} disabled={saving} data-testid="backup-config-btn">
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Backup Configuration
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Configuration History */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Configuration History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[400px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Device</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Compliance</TableHead>
                  <TableHead>Backed Up By</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : configs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">
                      No configuration backups yet
                    </TableCell>
                  </TableRow>
                ) : (
                  configs.map((config) => (
                    <TableRow key={config.id} className="table-row-hover" data-testid={`config-row-${config.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Settings className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{config.device_name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="capitalize">{config.config_type}</TableCell>
                      <TableCell>
                        <Badge variant="outline">v{config.version}</Badge>
                      </TableCell>
                      <TableCell>
                        {config.is_compliant ? (
                          <Badge className="bg-green-50 text-green-700 border-green-200">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Compliant
                          </Badge>
                        ) : (
                          <Badge className="bg-red-50 text-red-700 border-red-200">
                            <XCircle className="h-3 w-3 mr-1" />
                            Non-Compliant
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>{config.created_by}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {format(new Date(config.backup_date), 'MMM d, HH:mm')}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
