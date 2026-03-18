import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { devicesApi } from '../services/api';
import { toast } from 'sonner';
import {
  Server,
  Router,
  Shield,
  Cloud,
  Wifi,
  HardDrive,
  Plus,
  Search,
  RefreshCw,
  MoreVertical,
  Pencil,
  Trash2,
  Eye
} from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';

const deviceTypeIcons = {
  router: Router,
  switch: Server,
  firewall: Shield,
  load_balancer: HardDrive,
  server: Server,
  virtual_machine: Cloud,
  cloud_instance: Cloud,
  access_point: Wifi,
};

const StatusBadge = ({ status }) => {
  const styles = {
    online: 'bg-green-50 text-green-700 border-green-200',
    offline: 'bg-red-50 text-red-700 border-red-200',
    degraded: 'bg-amber-50 text-amber-700 border-amber-200',
    maintenance: 'bg-blue-50 text-blue-700 border-blue-200',
    unknown: 'bg-slate-50 text-slate-700 border-slate-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.unknown} capitalize`}>
      <span className={`w-2 h-2 rounded-full mr-1.5 ${
        status === 'online' ? 'bg-green-500 status-online' : 
        status === 'offline' ? 'bg-red-500' : 
        status === 'degraded' ? 'bg-amber-500' : 'bg-slate-500'
      }`} />
      {status}
    </Badge>
  );
};

const DeviceTypeIcon = ({ type }) => {
  const Icon = deviceTypeIcons[type] || Server;
  return <Icon className="h-5 w-5 text-muted-foreground" />;
};

const initialFormState = {
  name: '',
  type: 'server',
  ip_address: '',
  location: '',
  vendor: '',
  model: '',
  serial_number: '',
  firmware_version: '',
  tags: [],
};

export default function MonitoringPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isViewOpen, setIsViewOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [formData, setFormData] = useState(initialFormState);

  const fetchDevices = async () => {
    try {
      const response = await devicesApi.getAll();
      setDevices(response.data);
    } catch (error) {
      toast.error('Failed to fetch devices');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  const filteredDevices = devices.filter((device) => {
    const matchesSearch = device.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      device.ip_address.includes(searchQuery) ||
      device.location.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || device.type === filterType;
    const matchesStatus = filterStatus === 'all' || device.status === filterStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  const handleCreate = async () => {
    try {
      await devicesApi.create(formData);
      toast.success('Device created successfully');
      setIsCreateOpen(false);
      setFormData(initialFormState);
      fetchDevices();
    } catch (error) {
      toast.error('Failed to create device');
    }
  };

  const handleEdit = async () => {
    try {
      await devicesApi.update(selectedDevice.id, formData);
      toast.success('Device updated successfully');
      setIsEditOpen(false);
      setSelectedDevice(null);
      fetchDevices();
    } catch (error) {
      toast.error('Failed to update device');
    }
  };

  const handleDelete = async (device) => {
    if (window.confirm(`Are you sure you want to delete ${device.name}?`)) {
      try {
        await devicesApi.delete(device.id);
        toast.success('Device deleted successfully');
        fetchDevices();
      } catch (error) {
        toast.error('Failed to delete device');
      }
    }
  };

  const openEditDialog = (device) => {
    setSelectedDevice(device);
    setFormData({
      name: device.name,
      type: device.type,
      ip_address: device.ip_address,
      location: device.location,
      vendor: device.vendor || '',
      model: device.model || '',
      serial_number: device.serial_number || '',
      firmware_version: device.firmware_version || '',
      tags: device.tags || [],
    });
    setIsEditOpen(true);
  };

  const openViewDialog = (device) => {
    setSelectedDevice(device);
    setIsViewOpen(true);
  };

  const deviceStats = {
    total: devices.length,
    online: devices.filter(d => d.status === 'online').length,
    offline: devices.filter(d => d.status === 'offline').length,
    degraded: devices.filter(d => d.status === 'degraded').length,
  };

  return (
    <div data-testid="monitoring-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Device Monitoring</h1>
          <p className="text-muted-foreground mt-1">Monitor and manage network infrastructure</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-device-btn">
              <Plus className="h-4 w-4 mr-2" />
              Add Device
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Add New Device</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Device Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Core-Router-01"
                    data-testid="device-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                    <SelectTrigger data-testid="device-type-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="router">Router</SelectItem>
                      <SelectItem value="switch">Switch</SelectItem>
                      <SelectItem value="firewall">Firewall</SelectItem>
                      <SelectItem value="load_balancer">Load Balancer</SelectItem>
                      <SelectItem value="server">Server</SelectItem>
                      <SelectItem value="virtual_machine">Virtual Machine</SelectItem>
                      <SelectItem value="cloud_instance">Cloud Instance</SelectItem>
                      <SelectItem value="access_point">Access Point</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>IP Address</Label>
                  <Input
                    value={formData.ip_address}
                    onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                    placeholder="10.0.1.1"
                    data-testid="device-ip-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Location</Label>
                  <Input
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    placeholder="DC-East"
                    data-testid="device-location-input"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Vendor</Label>
                  <Input
                    value={formData.vendor}
                    onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                    placeholder="Cisco"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Input
                    value={formData.model}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                    placeholder="ASR 9000"
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} data-testid="save-device-btn">Save Device</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Server className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{deviceStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Devices</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-50">
              <Server className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{deviceStats.online}</p>
              <p className="text-sm text-muted-foreground">Online</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-50">
              <Server className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{deviceStats.offline}</p>
              <p className="text-sm text-muted-foreground">Offline</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-50">
              <Server className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-600">{deviceStats.degraded}</p>
              <p className="text-sm text-muted-foreground">Degraded</p>
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
                placeholder="Search by name, IP, or location..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="device-search"
              />
            </div>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-[180px]" data-testid="filter-type">
                <SelectValue placeholder="Device Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="router">Router</SelectItem>
                <SelectItem value="switch">Switch</SelectItem>
                <SelectItem value="firewall">Firewall</SelectItem>
                <SelectItem value="server">Server</SelectItem>
                <SelectItem value="cloud_instance">Cloud Instance</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[180px]" data-testid="filter-status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="online">Online</SelectItem>
                <SelectItem value="offline">Offline</SelectItem>
                <SelectItem value="degraded">Degraded</SelectItem>
                <SelectItem value="maintenance">Maintenance</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchDevices}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Devices Table */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Device</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>IP Address</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>CPU</TableHead>
                  <TableHead>Memory</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : filteredDevices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10 text-muted-foreground">
                      No devices found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredDevices.map((device) => (
                    <TableRow key={device.id} className="table-row-hover" data-testid={`device-row-${device.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <DeviceTypeIcon type={device.type} />
                          <div>
                            <p className="font-medium">{device.name}</p>
                            <p className="text-xs text-muted-foreground">{device.vendor} {device.model}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="capitalize">{device.type.replace('_', ' ')}</TableCell>
                      <TableCell className="font-mono text-sm">{device.ip_address}</TableCell>
                      <TableCell>{device.location}</TableCell>
                      <TableCell><StatusBadge status={device.status} /></TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-muted rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full ${device.cpu_usage > 80 ? 'bg-red-500' : device.cpu_usage > 60 ? 'bg-amber-500' : 'bg-green-500'}`}
                              style={{ width: `${device.cpu_usage}%` }}
                            />
                          </div>
                          <span className="text-sm">{Math.round(device.cpu_usage)}%</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-muted rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full ${device.memory_usage > 80 ? 'bg-red-500' : device.memory_usage > 60 ? 'bg-amber-500' : 'bg-green-500'}`}
                              style={{ width: `${device.memory_usage}%` }}
                            />
                          </div>
                          <span className="text-sm">{Math.round(device.memory_usage)}%</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openViewDialog(device)}>
                              <Eye className="h-4 w-4 mr-2" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openEditDialog(device)}>
                              <Pencil className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDelete(device)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Device</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Device Name</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="router">Router</SelectItem>
                    <SelectItem value="switch">Switch</SelectItem>
                    <SelectItem value="firewall">Firewall</SelectItem>
                    <SelectItem value="load_balancer">Load Balancer</SelectItem>
                    <SelectItem value="server">Server</SelectItem>
                    <SelectItem value="virtual_machine">Virtual Machine</SelectItem>
                    <SelectItem value="cloud_instance">Cloud Instance</SelectItem>
                    <SelectItem value="access_point">Access Point</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>IP Address</Label>
                <Input
                  value={formData.ip_address}
                  onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Location</Label>
                <Input
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>Cancel</Button>
            <Button onClick={handleEdit}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Dialog */}
      <Dialog open={isViewOpen} onOpenChange={setIsViewOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Device Details</DialogTitle>
          </DialogHeader>
          {selectedDevice && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="p-4 rounded-xl bg-muted">
                  <DeviceTypeIcon type={selectedDevice.type} />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{selectedDevice.name}</h3>
                  <p className="text-muted-foreground capitalize">{selectedDevice.type.replace('_', ' ')}</p>
                </div>
                <div className="ml-auto">
                  <StatusBadge status={selectedDevice.status} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">IP Address</p>
                  <p className="font-mono">{selectedDevice.ip_address}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Location</p>
                  <p>{selectedDevice.location}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Vendor</p>
                  <p>{selectedDevice.vendor || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Model</p>
                  <p>{selectedDevice.model || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">CPU Usage</p>
                  <p>{Math.round(selectedDevice.cpu_usage)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Memory Usage</p>
                  <p>{Math.round(selectedDevice.memory_usage)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Uptime</p>
                  <p>{selectedDevice.uptime_hours} hours</p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
