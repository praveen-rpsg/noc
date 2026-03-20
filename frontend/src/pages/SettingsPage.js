import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Settings,
  Mail,
  Network,
  Shield,
  Plus,
  Trash2,
  Edit,
  TestTube,
  Save,
  Eye,
  EyeOff,
  Server,
  CheckCircle2,
  XCircle,
  Loader2,
  Cloud,
  Database,
  Monitor,
  Key,
  HardDrive,
  Play,
  Calendar
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeader = () => {
  const token = localStorage.getItem('noc_token');
  return { Authorization: `Bearer ${token}` };
};

// Generic CRUD Hook
const useSettingsConfig = (endpoint) => {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchConfigs = async () => {
    try {
      const response = await axios.get(`${API}/settings/${endpoint}`, { headers: getAuthHeader() });
      setConfigs(response.data || []);
    } catch (error) {
      console.error(`Failed to fetch ${endpoint}:`, error);
    } finally {
      setLoading(false);
    }
  };

  const createConfig = async (data) => {
    const response = await axios.post(`${API}/settings/${endpoint}`, data, { headers: getAuthHeader() });
    await fetchConfigs();
    return response.data;
  };

  const updateConfig = async (id, data) => {
    const response = await axios.put(`${API}/settings/${endpoint}/${id}`, data, { headers: getAuthHeader() });
    await fetchConfigs();
    return response.data;
  };

  const deleteConfig = async (id) => {
    await axios.delete(`${API}/settings/${endpoint}/${id}`, { headers: getAuthHeader() });
    await fetchConfigs();
  };

  useEffect(() => { fetchConfigs(); }, []);

  return { configs, loading, fetchConfigs, createConfig, updateConfig, deleteConfig };
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('email');
  
  // Email Configuration State
  const [emailConfig, setEmailConfig] = useState({
    smtp_server: 'smtp.office365.com',
    smtp_port: 587,
    username: '',
    password: '',
    sender_email: '',
    sender_name: 'ATECH NOC Commander',
    use_tls: true
  });
  const [emailLoading, setEmailLoading] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [showPassword, setShowPassword] = useState({});

  // Use hooks for different config types
  const snmpCommunity = useSettingsConfig('snmp/community');
  const snmpV3 = useSettingsConfig('snmp/v3');
  const openstack = useSettingsConfig('openstack');
  const oracle = useSettingsConfig('oracle');
  const vcenter = useSettingsConfig('vcenter');
  const aaa = useSettingsConfig('aaa');
  const backup = useSettingsConfig('backup');

  // Dialog states
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});

  // Fetch Email Configuration
  useEffect(() => {
    const fetchEmailConfig = async () => {
      try {
        const response = await axios.get(`${API}/settings/email`, { headers: getAuthHeader() });
        if (response.data) {
          setEmailConfig(prev => ({ ...prev, ...response.data, password: '' }));
        }
      } catch (error) {}
    };
    fetchEmailConfig();
  }, []);

  // Save Email Configuration
  const handleSaveEmailConfig = async () => {
    if (!emailConfig.username || !emailConfig.sender_email) {
      toast.error('Username and Sender Email are required');
      return;
    }
    setEmailLoading(true);
    try {
      await axios.post(`${API}/settings/email`, emailConfig, { headers: getAuthHeader() });
      toast.success('Email configuration saved successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save email configuration');
    } finally {
      setEmailLoading(false);
    }
  };

  // Test Email
  const handleTestEmail = async () => {
    if (!testEmail) {
      toast.error('Please enter a test email address');
      return;
    }
    try {
      await axios.post(`${API}/settings/email/test?test_email=${encodeURIComponent(testEmail)}`, {}, { headers: getAuthHeader() });
      toast.success('Test email sent successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send test email');
    }
  };

  // Generic form handlers
  const openCreateDialog = (type, defaultData = {}) => {
    setDialogType(type);
    setEditingItem(null);
    setFormData(defaultData);
    setDialogOpen(true);
  };

  const openEditDialog = (type, item) => {
    setDialogType(type);
    setEditingItem(item);
    setFormData({ ...item });
    setDialogOpen(true);
  };

  const handleSaveForm = async () => {
    try {
      let hook;
      switch (dialogType) {
        case 'snmp_community': hook = snmpCommunity; break;
        case 'snmp_v3': hook = snmpV3; break;
        case 'openstack': hook = openstack; break;
        case 'oracle': hook = oracle; break;
        case 'vcenter': hook = vcenter; break;
        case 'aaa': hook = aaa; break;
        case 'backup': hook = backup; break;
        default: return;
      }

      if (editingItem) {
        await hook.updateConfig(editingItem.id, formData);
        toast.success('Configuration updated');
      } else {
        await hook.createConfig(formData);
        toast.success('Configuration created');
      }
      setDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save configuration');
    }
  };

  const handleDeleteConfig = async (type, id) => {
    if (!window.confirm('Are you sure you want to delete this configuration?')) return;
    try {
      let hook;
      switch (type) {
        case 'snmp_community': hook = snmpCommunity; break;
        case 'snmp_v3': hook = snmpV3; break;
        case 'openstack': hook = openstack; break;
        case 'oracle': hook = oracle; break;
        case 'vcenter': hook = vcenter; break;
        case 'aaa': hook = aaa; break;
        case 'backup': hook = backup; break;
        default: return;
      }
      await hook.deleteConfig(id);
      toast.success('Configuration deleted');
    } catch (error) {
      toast.error('Failed to delete configuration');
    }
  };

  const handleTriggerBackup = async (configId) => {
    try {
      await axios.post(`${API}/settings/backup/${configId}/trigger`, {}, { headers: getAuthHeader() });
      toast.success('Backup triggered successfully');
      backup.fetchConfigs();
    } catch (error) {
      toast.error('Failed to trigger backup');
    }
  };

  // Config card component
  const ConfigCard = ({ config, type, icon: Icon, iconColor, children }) => (
    <div className="border rounded-lg p-4 flex items-start justify-between hover:bg-muted/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${iconColor}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h4 className="font-medium">{config.name}</h4>
            {config.is_active && <Badge className="bg-green-500">Active</Badge>}
          </div>
          {children}
        </div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="icon" onClick={() => openEditDialog(type, config)}>
          <Edit className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={() => handleDeleteConfig(type, config.id)}>
          <Trash2 className="h-4 w-4 text-red-500" />
        </Button>
      </div>
    </div>
  );

  const renderDialogContent = () => {
    switch (dialogType) {
      case 'snmp_community':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="DC1-Routers" />
              </div>
              <div className="space-y-2">
                <Label>Version</Label>
                <Select value={formData.version || 'v2c'} onValueChange={(v) => setFormData({...formData, version: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="v1">SNMPv1</SelectItem>
                    <SelectItem value="v2c">SNMPv2c</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Community String *</Label>
              <Input type="password" value={formData.community_string || ''} onChange={(e) => setFormData({...formData, community_string: e.target.value})} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>IP Range (CIDR)</Label>
                <Input value={formData.ip_range || ''} onChange={(e) => setFormData({...formData, ip_range: e.target.value})} placeholder="192.168.1.0/24" />
              </div>
              <div className="space-y-2">
                <Label>Location</Label>
                <Input value={formData.location || ''} onChange={(e) => setFormData({...formData, location: e.target.value})} placeholder="Datacenter 1" />
              </div>
            </div>
          </div>
        );

      case 'openstack':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="Production OpenStack" />
              </div>
              <div className="space-y-2">
                <Label>Auth URL *</Label>
                <Input value={formData.auth_url || ''} onChange={(e) => setFormData({...formData, auth_url: e.target.value})} placeholder="http://openstack:5000/v3" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Username *</Label>
                <Input value={formData.username || ''} onChange={(e) => setFormData({...formData, username: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Password *</Label>
                <Input type="password" value={formData.password || ''} onChange={(e) => setFormData({...formData, password: e.target.value})} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Project Name *</Label>
                <Input value={formData.project_name || ''} onChange={(e) => setFormData({...formData, project_name: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Region</Label>
                <Input value={formData.region_name || ''} onChange={(e) => setFormData({...formData, region_name: e.target.value})} />
              </div>
            </div>
            <div className="border-t pt-4">
              <Label className="mb-3 block">Services to Monitor</Label>
              <div className="grid grid-cols-4 gap-3">
                {['nova', 'neutron', 'cinder', 'keystone', 'glance', 'heat', 'swift'].map(svc => (
                  <div key={svc} className="flex items-center gap-2">
                    <Switch checked={formData[`monitor_${svc}`] !== false} onCheckedChange={(c) => setFormData({...formData, [`monitor_${svc}`]: c})} />
                    <Label className="capitalize">{svc}</Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      case 'oracle':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="Production DB" />
              </div>
              <div className="space-y-2">
                <Label>Host *</Label>
                <Input value={formData.host || ''} onChange={(e) => setFormData({...formData, host: e.target.value})} placeholder="db.example.com" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Port</Label>
                <Input type="number" value={formData.port || 1521} onChange={(e) => setFormData({...formData, port: parseInt(e.target.value)})} />
              </div>
              <div className="space-y-2">
                <Label>Service Name *</Label>
                <Input value={formData.service_name || ''} onChange={(e) => setFormData({...formData, service_name: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Username *</Label>
                <Input value={formData.username || ''} onChange={(e) => setFormData({...formData, username: e.target.value})} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Password *</Label>
              <Input type="password" value={formData.password || ''} onChange={(e) => setFormData({...formData, password: e.target.value})} />
            </div>
            <div className="border-t pt-4">
              <Label className="mb-3 block">Metrics to Monitor</Label>
              <div className="grid grid-cols-4 gap-3">
                {['tablespace', 'sessions', 'locks', 'performance', 'asm', 'dataguard', 'rman'].map(m => (
                  <div key={m} className="flex items-center gap-2">
                    <Switch checked={formData[`monitor_${m}`] !== false} onCheckedChange={(c) => setFormData({...formData, [`monitor_${m}`]: c})} />
                    <Label className="capitalize">{m}</Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      case 'vcenter':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="vCenter Production" />
              </div>
              <div className="space-y-2">
                <Label>Host *</Label>
                <Input value={formData.host || ''} onChange={(e) => setFormData({...formData, host: e.target.value})} placeholder="vcenter.example.com" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Port</Label>
                <Input type="number" value={formData.port || 443} onChange={(e) => setFormData({...formData, port: parseInt(e.target.value)})} />
              </div>
              <div className="space-y-2">
                <Label>Username *</Label>
                <Input value={formData.username || ''} onChange={(e) => setFormData({...formData, username: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Password *</Label>
                <Input type="password" value={formData.password || ''} onChange={(e) => setFormData({...formData, password: e.target.value})} />
              </div>
            </div>
            <div className="border-t pt-4">
              <Label className="mb-3 block">Resources to Monitor</Label>
              <div className="grid grid-cols-3 gap-3">
                {['vms', 'esxi_hosts', 'datastores', 'clusters', 'networks', 'resource_pools'].map(r => (
                  <div key={r} className="flex items-center gap-2">
                    <Switch checked={formData[`monitor_${r}`] !== false} onCheckedChange={(c) => setFormData({...formData, [`monitor_${r}`]: c})} />
                    <Label className="capitalize">{r.replace('_', ' ')}</Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      case 'aaa':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="Primary RADIUS" />
              </div>
              <div className="space-y-2">
                <Label>Server Type *</Label>
                <Select value={formData.server_type || 'radius'} onValueChange={(v) => setFormData({...formData, server_type: v, primary_port: v === 'radius' ? 1812 : 49})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="radius">RADIUS</SelectItem>
                    <SelectItem value="tacacs">TACACS+</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Primary Host *</Label>
                <Input value={formData.primary_host || ''} onChange={(e) => setFormData({...formData, primary_host: e.target.value})} placeholder="radius.example.com" />
              </div>
              <div className="space-y-2">
                <Label>Primary Port</Label>
                <Input type="number" value={formData.primary_port || (formData.server_type === 'tacacs' ? 49 : 1812)} onChange={(e) => setFormData({...formData, primary_port: parseInt(e.target.value)})} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Secondary Host</Label>
                <Input value={formData.secondary_host || ''} onChange={(e) => setFormData({...formData, secondary_host: e.target.value})} placeholder="radius-backup.example.com" />
              </div>
              <div className="space-y-2">
                <Label>Secondary Port</Label>
                <Input type="number" value={formData.secondary_port || ''} onChange={(e) => setFormData({...formData, secondary_port: parseInt(e.target.value)})} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Shared Secret *</Label>
              <Input type="password" value={formData.shared_secret || ''} onChange={(e) => setFormData({...formData, shared_secret: e.target.value})} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <Switch checked={formData.use_for_login !== false} onCheckedChange={(c) => setFormData({...formData, use_for_login: c})} />
                <Label>Use for NOC Login</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={formData.use_for_device_auth !== false} onCheckedChange={(c) => setFormData({...formData, use_for_device_auth: c})} />
                <Label>Use for Device Auth</Label>
              </div>
            </div>
          </div>
        );

      case 'backup':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={formData.name || ''} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="Nightly Config Backup" />
              </div>
              <div className="space-y-2">
                <Label>Backup Type *</Label>
                <Select value={formData.backup_type || 'scp'} onValueChange={(v) => setFormData({...formData, backup_type: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tftp">TFTP</SelectItem>
                    <SelectItem value="scp">SCP</SelectItem>
                    <SelectItem value="ssh_command">SSH Command</SelectItem>
                    <SelectItem value="api">API-based</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {(formData.backup_type === 'tftp' || formData.backup_type === 'scp') && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Server Host</Label>
                  <Input value={formData.server_host || ''} onChange={(e) => setFormData({...formData, server_host: e.target.value})} placeholder="backup.example.com" />
                </div>
                <div className="space-y-2">
                  <Label>Server Path</Label>
                  <Input value={formData.server_path || ''} onChange={(e) => setFormData({...formData, server_path: e.target.value})} placeholder="/backups/network" />
                </div>
                {formData.backup_type === 'scp' && (
                  <>
                    <div className="space-y-2">
                      <Label>Username</Label>
                      <Input value={formData.server_username || ''} onChange={(e) => setFormData({...formData, server_username: e.target.value})} />
                    </div>
                    <div className="space-y-2">
                      <Label>Password</Label>
                      <Input type="password" value={formData.server_password || ''} onChange={(e) => setFormData({...formData, server_password: e.target.value})} />
                    </div>
                  </>
                )}
              </div>
            )}
            {formData.backup_type === 'ssh_command' && (
              <div className="space-y-2">
                <Label>SSH Command</Label>
                <Textarea value={formData.ssh_command || ''} onChange={(e) => setFormData({...formData, ssh_command: e.target.value})} placeholder="show running-config" rows={2} />
              </div>
            )}
            {formData.backup_type === 'api' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>API Endpoint</Label>
                  <Input value={formData.api_endpoint || ''} onChange={(e) => setFormData({...formData, api_endpoint: e.target.value})} placeholder="https://api.example.com/backup" />
                </div>
                <div className="space-y-2">
                  <Label>API Key</Label>
                  <Input type="password" value={formData.api_key || ''} onChange={(e) => setFormData({...formData, api_key: e.target.value})} />
                </div>
              </div>
            )}
            <div className="border-t pt-4">
              <Label className="mb-3 block">Schedule</Label>
              <div className="grid grid-cols-3 gap-4">
                <div className="flex items-center gap-2">
                  <Switch checked={formData.schedule_enabled === true} onCheckedChange={(c) => setFormData({...formData, schedule_enabled: c})} />
                  <Label>Enable Schedule</Label>
                </div>
                {formData.schedule_enabled && (
                  <>
                    <div className="space-y-2">
                      <Label>Frequency</Label>
                      <Select value={formData.schedule_frequency || 'daily'} onValueChange={(v) => setFormData({...formData, schedule_frequency: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">Daily</SelectItem>
                          <SelectItem value="weekly">Weekly</SelectItem>
                          <SelectItem value="monthly">Monthly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Time (HH:MM)</Label>
                      <Input type="time" value={formData.schedule_time || '02:00'} onChange={(e) => setFormData({...formData, schedule_time: e.target.value})} />
                    </div>
                  </>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Retention (days)</Label>
              <Input type="number" value={formData.retention_days || 30} onChange={(e) => setFormData({...formData, retention_days: parseInt(e.target.value)})} />
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const getDialogTitle = () => {
    const titles = {
      snmp_community: 'SNMP Community String',
      snmp_v3: 'SNMP v3 Configuration',
      openstack: 'OpenStack Configuration',
      oracle: 'Oracle Database Configuration',
      vcenter: 'vCenter Configuration',
      aaa: 'AAA Server Configuration',
      backup: 'Backup Configuration'
    };
    return `${editingItem ? 'Edit' : 'Add'} ${titles[dialogType] || 'Configuration'}`;
  };

  return (
    <div data-testid="settings-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Settings</h1>
          <p className="text-muted-foreground mt-1">Configure integrations, monitoring, and system settings</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <ScrollArea className="w-full">
          <TabsList className="inline-flex h-10 w-full justify-start">
            <TabsTrigger value="email" className="flex items-center gap-2"><Mail className="h-4 w-4" />Email</TabsTrigger>
            <TabsTrigger value="snmp" className="flex items-center gap-2"><Network className="h-4 w-4" />SNMP</TabsTrigger>
            <TabsTrigger value="openstack" className="flex items-center gap-2"><Cloud className="h-4 w-4" />OpenStack</TabsTrigger>
            <TabsTrigger value="oracle" className="flex items-center gap-2"><Database className="h-4 w-4" />Oracle</TabsTrigger>
            <TabsTrigger value="vcenter" className="flex items-center gap-2"><Monitor className="h-4 w-4" />vCenter</TabsTrigger>
            <TabsTrigger value="aaa" className="flex items-center gap-2"><Key className="h-4 w-4" />AAA</TabsTrigger>
            <TabsTrigger value="backup" className="flex items-center gap-2"><HardDrive className="h-4 w-4" />Backup</TabsTrigger>
          </TabsList>
        </ScrollArea>

        {/* Email Tab */}
        <TabsContent value="email">
          <Card className="bg-white border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Mail className="h-5 w-5 text-blue-600" />Office 365 Email Configuration</CardTitle>
              <CardDescription>Configure SMTP settings for email notifications and escalation alerts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>SMTP Server</Label>
                  <Input value={emailConfig.smtp_server} onChange={(e) => setEmailConfig({...emailConfig, smtp_server: e.target.value})} placeholder="smtp.office365.com" />
                </div>
                <div className="space-y-2">
                  <Label>SMTP Port</Label>
                  <Input type="number" value={emailConfig.smtp_port} onChange={(e) => setEmailConfig({...emailConfig, smtp_port: parseInt(e.target.value)})} />
                </div>
                <div className="space-y-2">
                  <Label>Username (Email)</Label>
                  <Input value={emailConfig.username} onChange={(e) => setEmailConfig({...emailConfig, username: e.target.value})} placeholder="noc@company.com" />
                </div>
                <div className="space-y-2">
                  <Label>Password</Label>
                  <Input type="password" value={emailConfig.password} onChange={(e) => setEmailConfig({...emailConfig, password: e.target.value})} placeholder="App password" />
                </div>
                <div className="space-y-2">
                  <Label>Sender Email</Label>
                  <Input value={emailConfig.sender_email} onChange={(e) => setEmailConfig({...emailConfig, sender_email: e.target.value})} placeholder="noc-alerts@company.com" />
                </div>
                <div className="space-y-2">
                  <Label>Sender Name</Label>
                  <Input value={emailConfig.sender_name} onChange={(e) => setEmailConfig({...emailConfig, sender_name: e.target.value})} />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={emailConfig.use_tls} onCheckedChange={(c) => setEmailConfig({...emailConfig, use_tls: c})} />
                <Label>Use TLS Encryption</Label>
              </div>
              <div className="border-t pt-6 flex items-end gap-4">
                <div className="flex-1">
                  <Label className="mb-2 block">Test Email</Label>
                  <Input value={testEmail} onChange={(e) => setTestEmail(e.target.value)} placeholder="Enter email to test" />
                </div>
                <Button variant="outline" onClick={handleTestEmail}><TestTube className="h-4 w-4 mr-2" />Send Test</Button>
                <Button onClick={handleSaveEmailConfig} disabled={emailLoading}>
                  {emailLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Save Configuration
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* SNMP Tab */}
        <TabsContent value="snmp">
          <div className="space-y-6">
            <Card className="bg-white border-border/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2"><Network className="h-5 w-5 text-purple-600" />SNMP Community Strings (v1/v2c)</CardTitle>
                  <CardDescription>Configure community strings for device groups</CardDescription>
                </div>
                <Button onClick={() => openCreateDialog('snmp_community', {version: 'v2c'})}><Plus className="h-4 w-4 mr-2" />Add</Button>
              </CardHeader>
              <CardContent>
                {snmpCommunity.loading ? (
                  <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                ) : snmpCommunity.configs.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">No SNMP community strings configured</div>
                ) : (
                  <div className="space-y-3">
                    {snmpCommunity.configs.map(config => (
                      <ConfigCard key={config.id} config={config} type="snmp_community" icon={Network} iconColor="bg-purple-500">
                        <p className="text-sm text-muted-foreground">Version: {config.version?.toUpperCase()} | IP Range: {config.ip_range || 'All'}</p>
                      </ConfigCard>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card className="bg-white border-border/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5 text-green-600" />SNMP v3 Configuration</CardTitle>
                  <CardDescription>Secure SNMP with authentication and privacy</CardDescription>
                </div>
                <Button onClick={() => openCreateDialog('snmp_v3', {security_level: 'authPriv', auth_protocol: 'SHA', priv_protocol: 'AES'})}><Plus className="h-4 w-4 mr-2" />Add</Button>
              </CardHeader>
              <CardContent>
                {snmpV3.configs.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">No SNMP v3 configurations</div>
                ) : (
                  <div className="space-y-3">
                    {snmpV3.configs.map(config => (
                      <ConfigCard key={config.id} config={config} type="snmp_v3" icon={Shield} iconColor="bg-green-500">
                        <p className="text-sm text-muted-foreground">User: {config.username} | Security: {config.security_level}</p>
                      </ConfigCard>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* OpenStack Tab */}
        <TabsContent value="openstack">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Cloud className="h-5 w-5 text-orange-600" />OpenStack Configuration</CardTitle>
                <CardDescription>Monitor OpenStack services: Nova, Neutron, Cinder, Keystone, Glance, Heat, Swift</CardDescription>
              </div>
              <Button onClick={() => openCreateDialog('openstack', {monitor_nova: true, monitor_neutron: true, monitor_cinder: true, monitor_keystone: true, monitor_glance: true, monitor_heat: true, monitor_swift: true})}><Plus className="h-4 w-4 mr-2" />Add</Button>
            </CardHeader>
            <CardContent>
              {openstack.configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No OpenStack configurations</div>
              ) : (
                <div className="space-y-3">
                  {openstack.configs.map(config => (
                    <ConfigCard key={config.id} config={config} type="openstack" icon={Cloud} iconColor="bg-orange-500">
                      <p className="text-sm text-muted-foreground">URL: {config.auth_url} | Project: {config.project_name}</p>
                    </ConfigCard>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Oracle Tab */}
        <TabsContent value="oracle">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Database className="h-5 w-5 text-red-600" />Oracle Database Configuration</CardTitle>
                <CardDescription>Monitor tablespace, sessions, locks, performance, ASM, DataGuard, RMAN</CardDescription>
              </div>
              <Button onClick={() => openCreateDialog('oracle', {port: 1521, monitor_tablespace: true, monitor_sessions: true, monitor_locks: true, monitor_performance: true})}><Plus className="h-4 w-4 mr-2" />Add</Button>
            </CardHeader>
            <CardContent>
              {oracle.configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No Oracle configurations</div>
              ) : (
                <div className="space-y-3">
                  {oracle.configs.map(config => (
                    <ConfigCard key={config.id} config={config} type="oracle" icon={Database} iconColor="bg-red-500">
                      <p className="text-sm text-muted-foreground">Host: {config.host}:{config.port} | Service: {config.service_name}</p>
                    </ConfigCard>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* vCenter Tab */}
        <TabsContent value="vcenter">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Monitor className="h-5 w-5 text-blue-600" />VMware vCenter Configuration</CardTitle>
                <CardDescription>Monitor VMs, ESXi hosts, datastores, clusters, networks</CardDescription>
              </div>
              <Button onClick={() => openCreateDialog('vcenter', {port: 443, monitor_vms: true, monitor_esxi_hosts: true, monitor_datastores: true, monitor_clusters: true})}><Plus className="h-4 w-4 mr-2" />Add</Button>
            </CardHeader>
            <CardContent>
              {vcenter.configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No vCenter configurations</div>
              ) : (
                <div className="space-y-3">
                  {vcenter.configs.map(config => (
                    <ConfigCard key={config.id} config={config} type="vcenter" icon={Monitor} iconColor="bg-blue-500">
                      <p className="text-sm text-muted-foreground">Host: {config.host}:{config.port}</p>
                    </ConfigCard>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* AAA Tab */}
        <TabsContent value="aaa">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Key className="h-5 w-5 text-yellow-600" />AAA Server Configuration</CardTitle>
                <CardDescription>Configure RADIUS and TACACS+ authentication servers</CardDescription>
              </div>
              <Button onClick={() => openCreateDialog('aaa', {server_type: 'radius', primary_port: 1812, use_for_login: true, use_for_device_auth: true})}><Plus className="h-4 w-4 mr-2" />Add</Button>
            </CardHeader>
            <CardContent>
              {aaa.configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No AAA server configurations</div>
              ) : (
                <div className="space-y-3">
                  {aaa.configs.map(config => (
                    <ConfigCard key={config.id} config={config} type="aaa" icon={Key} iconColor="bg-yellow-500">
                      <p className="text-sm text-muted-foreground">{config.server_type?.toUpperCase()} | Primary: {config.primary_host}:{config.primary_port}</p>
                    </ConfigCard>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Backup Tab */}
        <TabsContent value="backup">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><HardDrive className="h-5 w-5 text-indigo-600" />Backup Configuration</CardTitle>
                <CardDescription>Configure backup schedules for devices and applications (TFTP, SCP, SSH, API)</CardDescription>
              </div>
              <Button onClick={() => openCreateDialog('backup', {backup_type: 'scp', retention_days: 30})}><Plus className="h-4 w-4 mr-2" />Add</Button>
            </CardHeader>
            <CardContent>
              {backup.configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No backup configurations</div>
              ) : (
                <div className="space-y-3">
                  {backup.configs.map(config => (
                    <div key={config.id} className="border rounded-lg p-4 flex items-start justify-between hover:bg-muted/30 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-lg bg-indigo-500">
                          <HardDrive className="h-5 w-5 text-white" />
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium">{config.name}</h4>
                            <Badge variant="outline">{config.backup_type?.toUpperCase()}</Badge>
                            {config.schedule_enabled && <Badge className="bg-blue-500"><Calendar className="h-3 w-3 mr-1" />{config.schedule_frequency}</Badge>}
                            {config.is_active && <Badge className="bg-green-500">Active</Badge>}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {config.server_host && `Server: ${config.server_host}`}
                            {config.last_status && ` | Last: ${config.last_status}`}
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="icon" onClick={() => handleTriggerBackup(config.id)} title="Trigger Backup">
                          <Play className="h-4 w-4 text-green-500" />
                        </Button>
                        <Button variant="outline" size="icon" onClick={() => openEditDialog('backup', config)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="icon" onClick={() => handleDeleteConfig('backup', config.id)}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Generic Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{getDialogTitle()}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{renderDialogContent()}</div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveForm}><Save className="h-4 w-4 mr-2" />{editingItem ? 'Update' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
