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
  Loader2
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeader = () => {
  const token = localStorage.getItem('noc_token');
  return { Authorization: `Bearer ${token}` };
};

export default function SettingsPage() {
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
  const [emailTestLoading, setEmailTestLoading] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [showEmailPassword, setShowEmailPassword] = useState(false);

  // SNMP Community Strings State
  const [snmpConfigs, setSnmpConfigs] = useState([]);
  const [snmpLoading, setSnmpLoading] = useState(true);
  const [snmpDialogOpen, setSnmpDialogOpen] = useState(false);
  const [editingSnmp, setEditingSnmp] = useState(null);
  const [snmpForm, setSnmpForm] = useState({
    name: '',
    community_string: '',
    version: 'v2c',
    ip_range: '',
    device_types: [],
    location: '',
    description: ''
  });
  const [snmpTestDialogOpen, setSnmpTestDialogOpen] = useState(false);
  const [snmpTestIp, setSnmpTestIp] = useState('');
  const [snmpTestLoading, setSnmpTestLoading] = useState(false);
  const [snmpTestResult, setSnmpTestResult] = useState(null);
  const [testingSnmpId, setTestingSnmpId] = useState(null);

  // SNMP v3 State
  const [snmpv3Configs, setSnmpv3Configs] = useState([]);
  const [snmpv3DialogOpen, setSnmpv3DialogOpen] = useState(false);
  const [editingSnmpv3, setEditingSnmpv3] = useState(null);
  const [snmpv3Form, setSnmpv3Form] = useState({
    name: '',
    security_level: 'authPriv',
    username: '',
    auth_protocol: 'SHA',
    auth_password: '',
    priv_protocol: 'AES',
    priv_password: '',
    ip_range: '',
    device_types: [],
    location: '',
    description: ''
  });

  const deviceTypeOptions = [
    'router', 'switch', 'firewall', 'load_balancer', 
    'server', 'virtual_machine', 'cloud_instance', 'access_point'
  ];

  // Fetch Email Configuration
  const fetchEmailConfig = async () => {
    try {
      const response = await axios.get(`${API}/settings/email`, { headers: getAuthHeader() });
      if (response.data) {
        setEmailConfig(prev => ({
          ...prev,
          ...response.data,
          password: '' // Don't pre-fill password
        }));
      }
    } catch (error) {
      // No config exists yet, use defaults
    }
  };

  // Fetch SNMP Community Strings
  const fetchSnmpConfigs = async () => {
    try {
      const response = await axios.get(`${API}/settings/snmp/community`, { headers: getAuthHeader() });
      setSnmpConfigs(response.data);
    } catch (error) {
      toast.error('Failed to fetch SNMP configurations');
    } finally {
      setSnmpLoading(false);
    }
  };

  // Fetch SNMP v3 Configurations
  const fetchSnmpv3Configs = async () => {
    try {
      const response = await axios.get(`${API}/settings/snmp/v3`, { headers: getAuthHeader() });
      setSnmpv3Configs(response.data);
    } catch (error) {
      toast.error('Failed to fetch SNMP v3 configurations');
    }
  };

  useEffect(() => {
    fetchEmailConfig();
    fetchSnmpConfigs();
    fetchSnmpv3Configs();
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

  // Test Email Configuration
  const handleTestEmail = async () => {
    if (!testEmail) {
      toast.error('Please enter a test email address');
      return;
    }

    setEmailTestLoading(true);
    try {
      const response = await axios.post(
        `${API}/settings/email/test?test_email=${encodeURIComponent(testEmail)}`,
        {},
        { headers: getAuthHeader() }
      );
      toast.success(response.data.message);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send test email');
    } finally {
      setEmailTestLoading(false);
    }
  };

  // Save SNMP Community String
  const handleSaveSnmpConfig = async () => {
    if (!snmpForm.name || !snmpForm.community_string) {
      toast.error('Name and Community String are required');
      return;
    }

    try {
      if (editingSnmp) {
        await axios.put(`${API}/settings/snmp/community/${editingSnmp.id}`, snmpForm, { headers: getAuthHeader() });
        toast.success('SNMP configuration updated');
      } else {
        await axios.post(`${API}/settings/snmp/community`, snmpForm, { headers: getAuthHeader() });
        toast.success('SNMP configuration created');
      }
      setSnmpDialogOpen(false);
      setEditingSnmp(null);
      resetSnmpForm();
      fetchSnmpConfigs();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save SNMP configuration');
    }
  };

  // Delete SNMP Community String
  const handleDeleteSnmpConfig = async (configId) => {
    if (!window.confirm('Are you sure you want to delete this SNMP configuration?')) return;

    try {
      await axios.delete(`${API}/settings/snmp/community/${configId}`, { headers: getAuthHeader() });
      toast.success('SNMP configuration deleted');
      fetchSnmpConfigs();
    } catch (error) {
      toast.error('Failed to delete SNMP configuration');
    }
  };

  // Test SNMP Community String
  const handleTestSnmp = async () => {
    if (!snmpTestIp) {
      toast.error('Please enter a target IP address');
      return;
    }

    setSnmpTestLoading(true);
    setSnmpTestResult(null);
    try {
      const response = await axios.post(
        `${API}/settings/snmp/community/${testingSnmpId}/test?target_ip=${encodeURIComponent(snmpTestIp)}`,
        {},
        { headers: getAuthHeader() }
      );
      setSnmpTestResult(response.data);
    } catch (error) {
      setSnmpTestResult({ success: false, message: error.response?.data?.detail || 'Test failed' });
    } finally {
      setSnmpTestLoading(false);
    }
  };

  // Save SNMP v3 Configuration
  const handleSaveSnmpv3Config = async () => {
    if (!snmpv3Form.name || !snmpv3Form.username) {
      toast.error('Name and Username are required');
      return;
    }

    try {
      if (editingSnmpv3) {
        await axios.put(`${API}/settings/snmp/v3/${editingSnmpv3.id}`, snmpv3Form, { headers: getAuthHeader() });
        toast.success('SNMP v3 configuration updated');
      } else {
        await axios.post(`${API}/settings/snmp/v3`, snmpv3Form, { headers: getAuthHeader() });
        toast.success('SNMP v3 configuration created');
      }
      setSnmpv3DialogOpen(false);
      setEditingSnmpv3(null);
      resetSnmpv3Form();
      fetchSnmpv3Configs();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save SNMP v3 configuration');
    }
  };

  // Delete SNMP v3 Configuration
  const handleDeleteSnmpv3Config = async (configId) => {
    if (!window.confirm('Are you sure you want to delete this SNMP v3 configuration?')) return;

    try {
      await axios.delete(`${API}/settings/snmp/v3/${configId}`, { headers: getAuthHeader() });
      toast.success('SNMP v3 configuration deleted');
      fetchSnmpv3Configs();
    } catch (error) {
      toast.error('Failed to delete SNMP v3 configuration');
    }
  };

  const resetSnmpForm = () => {
    setSnmpForm({
      name: '',
      community_string: '',
      version: 'v2c',
      ip_range: '',
      device_types: [],
      location: '',
      description: ''
    });
  };

  const resetSnmpv3Form = () => {
    setSnmpv3Form({
      name: '',
      security_level: 'authPriv',
      username: '',
      auth_protocol: 'SHA',
      auth_password: '',
      priv_protocol: 'AES',
      priv_password: '',
      ip_range: '',
      device_types: [],
      location: '',
      description: ''
    });
  };

  const openEditSnmpDialog = (config) => {
    setEditingSnmp(config);
    setSnmpForm({
      name: config.name,
      community_string: '', // Don't pre-fill
      version: config.version || 'v2c',
      ip_range: config.ip_range || '',
      device_types: config.device_types || [],
      location: config.location || '',
      description: config.description || ''
    });
    setSnmpDialogOpen(true);
  };

  const openEditSnmpv3Dialog = (config) => {
    setEditingSnmpv3(config);
    setSnmpv3Form({
      name: config.name,
      security_level: config.security_level || 'authPriv',
      username: config.username,
      auth_protocol: config.auth_protocol || 'SHA',
      auth_password: '', // Don't pre-fill
      priv_protocol: config.priv_protocol || 'AES',
      priv_password: '', // Don't pre-fill
      ip_range: config.ip_range || '',
      device_types: config.device_types || [],
      location: config.location || '',
      description: config.description || ''
    });
    setSnmpv3DialogOpen(true);
  };

  return (
    <div data-testid="settings-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Settings</h1>
          <p className="text-muted-foreground mt-1">Configure email notifications and SNMP settings</p>
        </div>
      </div>

      <Tabs defaultValue="email" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 lg:w-[500px]">
          <TabsTrigger value="email" className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Email (O365)
          </TabsTrigger>
          <TabsTrigger value="snmp" className="flex items-center gap-2">
            <Network className="h-4 w-4" />
            SNMP v1/v2c
          </TabsTrigger>
          <TabsTrigger value="snmpv3" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            SNMP v3
          </TabsTrigger>
        </TabsList>

        {/* Email Configuration Tab */}
        <TabsContent value="email">
          <Card className="bg-white border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-blue-600" />
                Office 365 Email Configuration
              </CardTitle>
              <CardDescription>
                Configure SMTP settings for sending email notifications and escalation alerts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="smtp_server">SMTP Server</Label>
                  <Input
                    id="smtp_server"
                    value={emailConfig.smtp_server}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_server: e.target.value })}
                    placeholder="smtp.office365.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp_port">SMTP Port</Label>
                  <Input
                    id="smtp_port"
                    type="number"
                    value={emailConfig.smtp_port}
                    onChange={(e) => setEmailConfig({ ...emailConfig, smtp_port: parseInt(e.target.value) })}
                    placeholder="587"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="username">Username (Email)</Label>
                  <Input
                    id="username"
                    value={emailConfig.username}
                    onChange={(e) => setEmailConfig({ ...emailConfig, username: e.target.value })}
                    placeholder="noc@yourcompany.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password / App Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showEmailPassword ? 'text' : 'password'}
                      value={emailConfig.password}
                      onChange={(e) => setEmailConfig({ ...emailConfig, password: e.target.value })}
                      placeholder="Enter password or app password"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-2 top-1/2 -translate-y-1/2"
                      onClick={() => setShowEmailPassword(!showEmailPassword)}
                    >
                      {showEmailPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sender_email">Sender Email (From)</Label>
                  <Input
                    id="sender_email"
                    value={emailConfig.sender_email}
                    onChange={(e) => setEmailConfig({ ...emailConfig, sender_email: e.target.value })}
                    placeholder="noc-alerts@yourcompany.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sender_name">Sender Name</Label>
                  <Input
                    id="sender_name"
                    value={emailConfig.sender_name}
                    onChange={(e) => setEmailConfig({ ...emailConfig, sender_name: e.target.value })}
                    placeholder="ATECH NOC Commander"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="use_tls"
                  checked={emailConfig.use_tls}
                  onCheckedChange={(checked) => setEmailConfig({ ...emailConfig, use_tls: checked })}
                />
                <Label htmlFor="use_tls">Use TLS Encryption</Label>
              </div>

              <div className="border-t pt-6">
                <h4 className="font-medium mb-4">Test Email Configuration</h4>
                <div className="flex gap-3">
                  <Input
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="Enter email address to send test"
                    className="max-w-sm"
                  />
                  <Button variant="outline" onClick={handleTestEmail} disabled={emailTestLoading}>
                    {emailTestLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <TestTube className="h-4 w-4 mr-2" />
                    )}
                    Send Test Email
                  </Button>
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveEmailConfig} disabled={emailLoading}>
                  {emailLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save Email Configuration
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* SNMP v1/v2c Tab */}
        <TabsContent value="snmp">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Network className="h-5 w-5 text-purple-600" />
                  SNMP Community Strings
                </CardTitle>
                <CardDescription>
                  Configure SNMP v1/v2c community strings for different device groups
                </CardDescription>
              </div>
              <Button onClick={() => { resetSnmpForm(); setEditingSnmp(null); setSnmpDialogOpen(true); }}>
                <Plus className="h-4 w-4 mr-2" />
                Add Community String
              </Button>
            </CardHeader>
            <CardContent>
              {snmpLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : snmpConfigs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Network className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No SNMP community strings configured</p>
                  <p className="text-sm">Add your first community string to enable SNMP discovery</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {snmpConfigs.map((config) => (
                    <div key={config.id} className="border rounded-lg p-4 flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium">{config.name}</h4>
                          <Badge variant="outline">{config.version?.toUpperCase() || 'v2c'}</Badge>
                          {config.is_active && <Badge className="bg-green-500">Active</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Community: <code className="bg-muted px-1 rounded">{config.community_string}</code>
                        </p>
                        {config.ip_range && (
                          <p className="text-sm text-muted-foreground">IP Range: {config.ip_range}</p>
                        )}
                        {config.location && (
                          <p className="text-sm text-muted-foreground">Location: {config.location}</p>
                        )}
                        {config.device_types?.length > 0 && (
                          <div className="flex gap-1 flex-wrap mt-2">
                            {config.device_types.map((type) => (
                              <Badge key={type} variant="secondary" className="text-xs">{type}</Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => {
                            setTestingSnmpId(config.id);
                            setSnmpTestIp('');
                            setSnmpTestResult(null);
                            setSnmpTestDialogOpen(true);
                          }}
                          title="Test SNMP"
                        >
                          <TestTube className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="icon" onClick={() => openEditSnmpDialog(config)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="icon" onClick={() => handleDeleteSnmpConfig(config.id)}>
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

        {/* SNMP v3 Tab */}
        <TabsContent value="snmpv3">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-green-600" />
                  SNMP v3 Configuration
                </CardTitle>
                <CardDescription>
                  Configure SNMP v3 with authentication and privacy for enhanced security
                </CardDescription>
              </div>
              <Button onClick={() => { resetSnmpv3Form(); setEditingSnmpv3(null); setSnmpv3DialogOpen(true); }}>
                <Plus className="h-4 w-4 mr-2" />
                Add SNMP v3 Config
              </Button>
            </CardHeader>
            <CardContent>
              {snmpv3Configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No SNMP v3 configurations</p>
                  <p className="text-sm">Add SNMP v3 for secure device monitoring</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {snmpv3Configs.map((config) => (
                    <div key={config.id} className="border rounded-lg p-4 flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium">{config.name}</h4>
                          <Badge variant="outline">{config.security_level}</Badge>
                          {config.is_active && <Badge className="bg-green-500">Active</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Username: <code className="bg-muted px-1 rounded">{config.username}</code>
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Auth: {config.auth_protocol} | Privacy: {config.priv_protocol}
                        </p>
                        {config.ip_range && (
                          <p className="text-sm text-muted-foreground">IP Range: {config.ip_range}</p>
                        )}
                        {config.location && (
                          <p className="text-sm text-muted-foreground">Location: {config.location}</p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="icon" onClick={() => openEditSnmpv3Dialog(config)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="icon" onClick={() => handleDeleteSnmpv3Config(config.id)}>
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

      {/* SNMP Community String Dialog */}
      <Dialog open={snmpDialogOpen} onOpenChange={setSnmpDialogOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>{editingSnmp ? 'Edit' : 'Add'} SNMP Community String</DialogTitle>
            <DialogDescription>
              Configure SNMP v1/v2c community string for device monitoring
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="snmp-name">Configuration Name *</Label>
                <Input
                  id="snmp-name"
                  value={snmpForm.name}
                  onChange={(e) => setSnmpForm({ ...snmpForm, name: e.target.value })}
                  placeholder="e.g., DC1-Routers"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="snmp-version">SNMP Version</Label>
                <Select value={snmpForm.version} onValueChange={(v) => setSnmpForm({ ...snmpForm, version: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="v1">SNMPv1</SelectItem>
                    <SelectItem value="v2c">SNMPv2c</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="community-string">Community String *</Label>
              <Input
                id="community-string"
                type="password"
                value={snmpForm.community_string}
                onChange={(e) => setSnmpForm({ ...snmpForm, community_string: e.target.value })}
                placeholder="Enter community string"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ip-range">IP Range (CIDR)</Label>
                <Input
                  id="ip-range"
                  value={snmpForm.ip_range}
                  onChange={(e) => setSnmpForm({ ...snmpForm, ip_range: e.target.value })}
                  placeholder="e.g., 192.168.1.0/24"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={snmpForm.location}
                  onChange={(e) => setSnmpForm({ ...snmpForm, location: e.target.value })}
                  placeholder="e.g., Datacenter 1"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Device Types (optional)</Label>
              <div className="flex flex-wrap gap-2">
                {deviceTypeOptions.map((type) => (
                  <Badge
                    key={type}
                    variant={snmpForm.device_types.includes(type) ? 'default' : 'outline'}
                    className="cursor-pointer"
                    onClick={() => {
                      const types = snmpForm.device_types.includes(type)
                        ? snmpForm.device_types.filter(t => t !== type)
                        : [...snmpForm.device_types, type];
                      setSnmpForm({ ...snmpForm, device_types: types });
                    }}
                  >
                    {type}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={snmpForm.description}
                onChange={(e) => setSnmpForm({ ...snmpForm, description: e.target.value })}
                placeholder="Optional description"
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSnmpDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveSnmpConfig}>
              <Save className="h-4 w-4 mr-2" />
              {editingSnmp ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* SNMP Test Dialog */}
      <Dialog open={snmpTestDialogOpen} onOpenChange={setSnmpTestDialogOpen}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle>Test SNMP Connection</DialogTitle>
            <DialogDescription>
              Enter a device IP to test the SNMP community string
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="test-ip">Target Device IP</Label>
              <Input
                id="test-ip"
                value={snmpTestIp}
                onChange={(e) => setSnmpTestIp(e.target.value)}
                placeholder="e.g., 192.168.1.1"
              />
            </div>
            {snmpTestResult && (
              <div className={`p-4 rounded-lg ${snmpTestResult.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'} border`}>
                <div className="flex items-center gap-2 mb-2">
                  {snmpTestResult.success ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  <span className={`font-medium ${snmpTestResult.success ? 'text-green-700' : 'text-red-700'}`}>
                    {snmpTestResult.success ? 'Connection Successful' : 'Connection Failed'}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{snmpTestResult.message}</p>
                {snmpTestResult.device_description && (
                  <p className="text-sm mt-2">
                    <span className="font-medium">Device:</span> {snmpTestResult.device_description}
                  </p>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSnmpTestDialogOpen(false)}>Close</Button>
            <Button onClick={handleTestSnmp} disabled={snmpTestLoading}>
              {snmpTestLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <TestTube className="h-4 w-4 mr-2" />
              )}
              Test Connection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* SNMP v3 Dialog */}
      <Dialog open={snmpv3DialogOpen} onOpenChange={setSnmpv3DialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>{editingSnmpv3 ? 'Edit' : 'Add'} SNMP v3 Configuration</DialogTitle>
            <DialogDescription>
              Configure SNMP v3 with authentication and privacy settings
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="v3-name">Configuration Name *</Label>
                <Input
                  id="v3-name"
                  value={snmpv3Form.name}
                  onChange={(e) => setSnmpv3Form({ ...snmpv3Form, name: e.target.value })}
                  placeholder="e.g., Secure-Core-Devices"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="v3-security">Security Level</Label>
                <Select value={snmpv3Form.security_level} onValueChange={(v) => setSnmpv3Form({ ...snmpv3Form, security_level: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="noAuthNoPriv">No Auth, No Privacy</SelectItem>
                    <SelectItem value="authNoPriv">Auth, No Privacy</SelectItem>
                    <SelectItem value="authPriv">Auth + Privacy</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="v3-username">Username *</Label>
              <Input
                id="v3-username"
                value={snmpv3Form.username}
                onChange={(e) => setSnmpv3Form({ ...snmpv3Form, username: e.target.value })}
                placeholder="SNMP v3 username"
              />
            </div>
            {snmpv3Form.security_level !== 'noAuthNoPriv' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="v3-auth-protocol">Auth Protocol</Label>
                  <Select value={snmpv3Form.auth_protocol} onValueChange={(v) => setSnmpv3Form({ ...snmpv3Form, auth_protocol: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MD5">MD5</SelectItem>
                      <SelectItem value="SHA">SHA</SelectItem>
                      <SelectItem value="SHA224">SHA-224</SelectItem>
                      <SelectItem value="SHA256">SHA-256</SelectItem>
                      <SelectItem value="SHA384">SHA-384</SelectItem>
                      <SelectItem value="SHA512">SHA-512</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="v3-auth-password">Auth Password</Label>
                  <Input
                    id="v3-auth-password"
                    type="password"
                    value={snmpv3Form.auth_password}
                    onChange={(e) => setSnmpv3Form({ ...snmpv3Form, auth_password: e.target.value })}
                    placeholder="Authentication password"
                  />
                </div>
              </div>
            )}
            {snmpv3Form.security_level === 'authPriv' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="v3-priv-protocol">Privacy Protocol</Label>
                  <Select value={snmpv3Form.priv_protocol} onValueChange={(v) => setSnmpv3Form({ ...snmpv3Form, priv_protocol: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DES">DES</SelectItem>
                      <SelectItem value="3DES">3DES</SelectItem>
                      <SelectItem value="AES">AES-128</SelectItem>
                      <SelectItem value="AES192">AES-192</SelectItem>
                      <SelectItem value="AES256">AES-256</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="v3-priv-password">Privacy Password</Label>
                  <Input
                    id="v3-priv-password"
                    type="password"
                    value={snmpv3Form.priv_password}
                    onChange={(e) => setSnmpv3Form({ ...snmpv3Form, priv_password: e.target.value })}
                    placeholder="Privacy/encryption password"
                  />
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="v3-ip-range">IP Range (CIDR)</Label>
                <Input
                  id="v3-ip-range"
                  value={snmpv3Form.ip_range}
                  onChange={(e) => setSnmpv3Form({ ...snmpv3Form, ip_range: e.target.value })}
                  placeholder="e.g., 10.0.0.0/8"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="v3-location">Location</Label>
                <Input
                  id="v3-location"
                  value={snmpv3Form.location}
                  onChange={(e) => setSnmpv3Form({ ...snmpv3Form, location: e.target.value })}
                  placeholder="e.g., Core Network"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Device Types (optional)</Label>
              <div className="flex flex-wrap gap-2">
                {deviceTypeOptions.map((type) => (
                  <Badge
                    key={type}
                    variant={snmpv3Form.device_types.includes(type) ? 'default' : 'outline'}
                    className="cursor-pointer"
                    onClick={() => {
                      const types = snmpv3Form.device_types.includes(type)
                        ? snmpv3Form.device_types.filter(t => t !== type)
                        : [...snmpv3Form.device_types, type];
                      setSnmpv3Form({ ...snmpv3Form, device_types: types });
                    }}
                  >
                    {type}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="v3-description">Description</Label>
              <Textarea
                id="v3-description"
                value={snmpv3Form.description}
                onChange={(e) => setSnmpv3Form({ ...snmpv3Form, description: e.target.value })}
                placeholder="Optional description"
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSnmpv3DialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveSnmpv3Config}>
              <Save className="h-4 w-4 mr-2" />
              {editingSnmpv3 ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
