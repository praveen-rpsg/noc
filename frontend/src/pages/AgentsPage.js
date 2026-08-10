import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Bot,
  Plus,
  Key,
  Server,
  RefreshCw,
  Copy,
  CheckCircle,
  XCircle,
  Loader2,
  Trash2,
  Settings
} from 'lucide-react';
import { getApiUrl } from '../services/config';
import { getAuthHeader } from '../services/auth';

const API = getApiUrl();

const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-green-50 text-green-700 border-green-200',
    inactive: 'bg-slate-50 text-slate-700 border-slate-200',
    suspended: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.active} capitalize`}>
      {status}
    </Badge>
  );
};

const CodeStatusBadge = ({ status }) => {
  const styles = {
    available: 'bg-green-50 text-green-700 border-green-200',
    activated: 'bg-blue-50 text-blue-700 border-blue-200',
    expired: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.available} capitalize`}>
      {status}
    </Badge>
  );
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [activationCodes, setActivationCodes] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [verifying, setVerifying] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    activation_code: ''
  });

  const fetchData = async () => {
    try {
      const headers = getAuthHeader();
      const [agentsRes, codesRes, devicesRes] = await Promise.all([
        axios.get(`${API}/agents`, { headers }),
        axios.get(`${API}/activation-codes`, { headers }),
        axios.get(`${API}/devices`, { headers })
      ]);
      setAgents(agentsRes.data);
      setActivationCodes(codesRes.data);
      setDevices(devicesRes.data);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateAgent = async () => {
    try {
      await axios.post(`${API}/agents`, formData, { headers: getAuthHeader() });
      toast.success('Agent created successfully');
      setIsCreateOpen(false);
      setFormData({ name: '', description: '', activation_code: '' });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create agent');
    }
  };

  const handleVerifyCode = async () => {
    if (!formData.activation_code) return;
    setVerifying(true);
    try {
      const response = await axios.post(`${API}/activation-codes/verify?code=${formData.activation_code}`, {}, { headers: getAuthHeader() });
      if (response.data.valid) {
        toast.success('Activation code is valid');
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      toast.error('Failed to verify code');
    } finally {
      setVerifying(false);
    }
  };

  const handleGenerateCodes = async () => {
    setGenerating(true);
    try {
      const response = await axios.post(`${API}/activation-codes/generate?count=200`, {}, { headers: getAuthHeader() });
      toast.success(`Generated ${response.data.codes.length} activation codes`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate codes');
    } finally {
      setGenerating(false);
    }
  };

  const handleAssignDevice = async (deviceId) => {
    if (!selectedAgent) return;
    try {
      await axios.post(`${API}/agents/${selectedAgent.id}/assign-device/${deviceId}`, {}, { headers: getAuthHeader() });
      toast.success('Device assigned');
      fetchData();
      // Update selected agent
      const updatedAgent = await axios.get(`${API}/agents/${selectedAgent.id}`, { headers: getAuthHeader() });
      setSelectedAgent(updatedAgent.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to assign device');
    }
  };

  const handleUnassignDevice = async (deviceId) => {
    if (!selectedAgent) return;
    try {
      await axios.post(`${API}/agents/${selectedAgent.id}/unassign-device/${deviceId}`, {}, { headers: getAuthHeader() });
      toast.success('Device unassigned');
      fetchData();
      const updatedAgent = await axios.get(`${API}/agents/${selectedAgent.id}`, { headers: getAuthHeader() });
      setSelectedAgent(updatedAgent.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to unassign device');
    }
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success('Code copied to clipboard');
  };

  const availableCodes = activationCodes.filter(c => c.status === 'available');
  const activatedCodes = activationCodes.filter(c => c.status === 'activated');

  return (
    <div data-testid="agents-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">AI Agents</h1>
          <p className="text-muted-foreground mt-1">Manage monitoring agents and activation codes</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-agent-btn">
                <Plus className="h-4 w-4 mr-2" />
                New Agent
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New AI Agent</DialogTitle>
                <DialogDescription>
                  Each agent can monitor up to 15 devices. Enter a valid activation code to create.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Agent Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="NOC Agent Alpha"
                    data-testid="agent-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Monitors core network infrastructure"
                    rows={2}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Activation Code</Label>
                  <div className="flex gap-2">
                    <Input
                      value={formData.activation_code}
                      onChange={(e) => setFormData({ ...formData, activation_code: e.target.value.toUpperCase() })}
                      placeholder="ATECH-XXXX-XXXX-XXXX"
                      className="font-mono"
                      data-testid="activation-code-input"
                    />
                    <Button variant="outline" onClick={handleVerifyCode} disabled={verifying}>
                      {verifying ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verify'}
                    </Button>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                <Button onClick={handleCreateAgent} data-testid="save-agent-btn">Create Agent</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Bot className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{agents.length}</p>
              <p className="text-sm text-muted-foreground">Active Agents</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-50">
              <Key className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{availableCodes.length}</p>
              <p className="text-sm text-muted-foreground">Available Codes</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-purple-50">
              <CheckCircle className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-600">{activatedCodes.length}</p>
              <p className="text-sm text-muted-foreground">Activated Codes</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-50">
              <Server className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-600">
                {agents.reduce((sum, a) => sum + (a.assigned_devices?.length || 0), 0)}
              </p>
              <p className="text-sm text-muted-foreground">Monitored Devices</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="agents">
        <TabsList>
          <TabsTrigger value="agents">AI Agents</TabsTrigger>
          <TabsTrigger value="codes">Activation Codes</TabsTrigger>
        </TabsList>

        <TabsContent value="agents" className="mt-4">
          <Card className="bg-white border-border/50">
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Agent Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Devices</TableHead>
                      <TableHead>Capacity</TableHead>
                      <TableHead>Activation Code</TableHead>
                      <TableHead>Created By</TableHead>
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
                    ) : agents.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-10 text-muted-foreground">
                          No agents created yet. Create one to start monitoring.
                        </TableCell>
                      </TableRow>
                    ) : (
                      agents.map((agent) => (
                        <TableRow key={agent.id} data-testid={`agent-row-${agent.id}`}>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div className="p-2 rounded-lg bg-blue-50">
                                <Bot className="h-5 w-5 text-blue-600" />
                              </div>
                              <div>
                                <p className="font-medium">{agent.name}</p>
                                <p className="text-xs text-muted-foreground">{agent.description || 'No description'}</p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell><StatusBadge status={agent.status} /></TableCell>
                          <TableCell>{agent.assigned_devices?.length || 0}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Progress 
                                value={((agent.assigned_devices?.length || 0) / 15) * 100} 
                                className="w-20 h-2"
                              />
                              <span className="text-sm text-muted-foreground">
                                {agent.assigned_devices?.length || 0}/15
                              </span>
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{agent.activation_code}</TableCell>
                          <TableCell>{agent.created_by}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => { setSelectedAgent(agent); setIsAssignOpen(true); }}
                            >
                              <Settings className="h-4 w-4 mr-1" />
                              Manage
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="codes" className="mt-4">
          <Card className="bg-white border-border/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg font-semibold">Activation Codes</CardTitle>
              {/* <Button onClick={handleGenerateCodes} disabled={generating}>
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-2" />
                    Generate 200 Codes
                  </>
                )}
              </Button> */}
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[400px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Activated By</TableHead>
                      <TableHead>Agent</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {activationCodes.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                          No activation codes. Click "Generate 200 Codes" to create.
                        </TableCell>
                      </TableRow>
                    ) : (
                      activationCodes.slice(0, 100).map((code) => (
                        <TableRow key={code.id}>
                          <TableCell className="font-mono">{code.code}</TableCell>
                          <TableCell><CodeStatusBadge status={code.status} /></TableCell>
                          <TableCell>{code.activated_by || '-'}</TableCell>
                          <TableCell>
                            {code.agent_id ? agents.find(a => a.id === code.agent_id)?.name || 'Unknown' : '-'}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="icon" onClick={() => copyCode(code.code)}>
                              <Copy className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Manage Agent Dialog */}
      <Dialog open={isAssignOpen} onOpenChange={setIsAssignOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Manage Agent: {selectedAgent?.name}</DialogTitle>
            <DialogDescription>
              Assign or unassign devices. Max 15 devices per agent.
            </DialogDescription>
          </DialogHeader>
          {selectedAgent && (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <span>Device Capacity</span>
                <div className="flex items-center gap-2">
                  <Progress 
                    value={((selectedAgent.assigned_devices?.length || 0) / 15) * 100} 
                    className="w-32 h-2"
                  />
                  <span className="font-mono">
                    {selectedAgent.assigned_devices?.length || 0}/15
                  </span>
                </div>
              </div>
              
              <div>
                <Label className="mb-2 block">Assigned Devices</Label>
                <div className="space-y-2 max-h-[150px] overflow-y-auto">
                  {selectedAgent.assigned_devices?.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No devices assigned</p>
                  ) : (
                    selectedAgent.assigned_devices?.map(deviceId => {
                      const device = devices.find(d => d.id === deviceId);
                      return device ? (
                        <div key={deviceId} className="flex items-center justify-between p-2 bg-green-50 rounded">
                          <span>{device.name} ({device.ip_address})</span>
                          <Button variant="ghost" size="sm" onClick={() => handleUnassignDevice(deviceId)}>
                            <XCircle className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      ) : null;
                    })
                  )}
                </div>
              </div>

              <div>
                <Label className="mb-2 block">Available Devices</Label>
                <div className="space-y-2 max-h-[150px] overflow-y-auto">
                  {devices.filter(d => !selectedAgent.assigned_devices?.includes(d.id)).map(device => (
                    <div key={device.id} className="flex items-center justify-between p-2 bg-muted rounded">
                      <span>{device.name} ({device.ip_address})</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleAssignDevice(device.id)}
                        disabled={(selectedAgent.assigned_devices?.length || 0) >= 15}
                      >
                        <Plus className="h-4 w-4 text-green-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
