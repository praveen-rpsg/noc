import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import axios from 'axios';
import { getApiUrl } from '../services/config';
import { getAuthHeader } from '../services/auth';
import { useAuth } from '../context/AuthContext';
import {
  Search,
  Wifi,
  Server,
  Router,
  Monitor,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
  Loader2,
  RefreshCw,
  Network,
  Shield,
  Terminal,
  Eye,
  AlertTriangle,
  Activity,
  Scan,
  Globe
} from 'lucide-react';

// Discovery Methods
const DISCOVERY_METHODS = [
  { id: 'arp_scan', name: 'ARP Scan', description: 'Layer 2 discovery (same subnet)', icon: Wifi },
  { id: 'ping_sweep', name: 'Ping Sweep', description: 'ICMP echo requests', icon: Activity },
  { id: 'snmp_discovery', name: 'SNMP Discovery', description: 'Query device info via SNMP', icon: Server },
  { id: 'port_scan', name: 'Port Scan', description: 'Scan common service ports', icon: Scan },
];

// Device type icons
const getDeviceIcon = (type) => {
  switch (type?.toLowerCase()) {
    case 'router': return Router;
    case 'switch': return Network;
    case 'server':
    case 'linux_server':
    case 'windows_server': return Server;
    case 'firewall': return Shield;
    default: return Monitor;
  }
};

export default function NetworkDiscoveryPage() {
  const { user } = useAuth();
  const [subnets, setSubnets] = useState([]);
  const [selectedSubnet, setSelectedSubnet] = useState('');
  const [customSubnet, setCustomSubnet] = useState('');
  const [selectedMethods, setSelectedMethods] = useState(['arp_scan', 'ping_sweep', 'snmp_discovery', 'port_scan']);
  const [snmpCommunities, setSnmpCommunities] = useState('public');
  const [loading, setLoading] = useState(false);
  
  // Jobs and requests
  const [pendingRequests, setPendingRequests] = useState([]);
  const [discoveryJobs, setDiscoveryJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  
  // Polling status
  const [pollingStatus, setPollingStatus] = useState({ running: false });
  
  // SSH Dialog
  const [showSSHDialog, setShowSSHDialog] = useState(false);
  const [sshTarget, setSSHTarget] = useState(null);
  const [sshCredentials, setSSHCredentials] = useState({ username: '', password: '' });
  const [sshConnecting, setSSHConnecting] = useState(false);
  const [sshSession, setSSHSession] = useState(null);
  const [sshCommand, setSSHCommand] = useState('');
  const [sshOutput, setSSHOutput] = useState('');

  const isAdmin = user?.role === 'admin';

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      const API = getApiUrl();
      const [subnetsRes, jobsRes, pollingRes] = await Promise.all([
        axios.get(`${API}/network/subnets`, { headers: getAuthHeader() }),
        axios.get(`${API}/network/discovery/jobs`, { headers: getAuthHeader() }),
        axios.get(`${API}/network/polling/status`, { headers: getAuthHeader() })
      ]);
      
      setSubnets(subnetsRes.data.subnets || []);
      setDiscoveryJobs(jobsRes.data || []);
      setPollingStatus(pollingRes.data);
      
      if (subnetsRes.data.subnets?.length > 0 && !selectedSubnet) {
        setSelectedSubnet(subnetsRes.data.subnets[0]);
      }

      if (isAdmin) {
        const pendingRes = await axios.get(`${API}/network/discovery/pending`, { headers: getAuthHeader() });
        setPendingRequests(pendingRes.data || []);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    }
  }, [isAdmin, selectedSubnet]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRequestDiscovery = async () => {
    setLoading(true);
    try {
      const API = getApiUrl();
      const subnet = customSubnet || selectedSubnet;
      
      await axios.post(`${API}/network/discovery/request`, {
        subnet,
        methods: selectedMethods,
        snmp_communities: snmpCommunities.split(',').map(c => c.trim())
      }, { headers: getAuthHeader() });
      
      toast.success('Discovery request submitted. Awaiting admin approval.');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit discovery request');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveRequest = async (requestId, approved) => {
    try {
      const API = getApiUrl();
      await axios.post(`${API}/network/discovery/approve`, {
        request_id: requestId,
        approved
      }, { headers: getAuthHeader() });
      
      toast.success(approved ? 'Discovery approved and started' : 'Discovery request rejected');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to process request');
    }
  };

  const handleTogglePolling = async () => {
    try {
      const API = getApiUrl();
      const endpoint = pollingStatus.running ? 'stop' : 'start';
      await axios.post(`${API}/network/polling/${endpoint}`, {}, { headers: getAuthHeader() });
      toast.success(pollingStatus.running ? 'Polling stopped' : 'Polling started');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to toggle polling');
    }
  };

  const handleSSHConnect = async () => {
    if (!sshTarget || !sshCredentials.username || !sshCredentials.password) {
      toast.error('Please enter credentials');
      return;
    }
    
    setSSHConnecting(true);
    try {
      const API = getApiUrl();
      const response = await axios.post(`${API}/network/ssh/connect`, {
        host: sshTarget.ip_address,
        username: sshCredentials.username,
        password: sshCredentials.password
      }, { headers: getAuthHeader() });
      
      setSSHSession(response.data.session_id);
      setSSHOutput('Connected successfully.\n');
      toast.success('SSH connected');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'SSH connection failed');
    } finally {
      setSSHConnecting(false);
    }
  };

  const handleSSHExecute = async () => {
    if (!sshSession || !sshCommand.trim()) return;
    
    try {
      const API = getApiUrl();
      const response = await axios.post(`${API}/network/ssh/execute`, {
        session_id: sshSession,
        command: sshCommand
      }, { headers: getAuthHeader() });
      
      setSSHOutput(prev => prev + `\n$ ${sshCommand}\n${response.data.output}${response.data.error ? '\nError: ' + response.data.error : ''}`);
      setSSHCommand('');
    } catch (error) {
      toast.error('Command execution failed');
    }
  };

  const handleSSHDisconnect = async () => {
    if (sshSession) {
      try {
        const API = getApiUrl();
        await axios.post(`${API}/network/ssh/disconnect?session_id=${sshSession}`, {}, { headers: getAuthHeader() });
      } catch (error) {
        console.error('Disconnect error:', error);
      }
    }
    setSSHSession(null);
    setSSHOutput('');
    setSSHCredentials({ username: '', password: '' });
    setShowSSHDialog(false);
  };

  const openSSHDialog = (device) => {
    setSSHTarget(device);
    setShowSSHDialog(true);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'running':
        return <Badge className="bg-blue-100 text-blue-700"><Loader2 className="h-3 w-3 animate-spin mr-1" />Running</Badge>;
      case 'completed':
        return <Badge className="bg-green-100 text-green-700"><CheckCircle2 className="h-3 w-3 mr-1" />Completed</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>;
      case 'pending_approval':
        return <Badge className="bg-yellow-100 text-yellow-700"><Clock className="h-3 w-3 mr-1" />Pending</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6" data-testid="network-discovery-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6 text-blue-600" />
            Network Discovery
          </h1>
          <p className="text-muted-foreground">Discover and monitor devices on your network</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          {isAdmin && (
            <Button 
              variant={pollingStatus.running ? "destructive" : "default"}
              onClick={handleTogglePolling}
            >
              {pollingStatus.running ? 'Stop Polling' : 'Start Polling'}
            </Button>
          )}
        </div>
      </div>

      <Tabs defaultValue="discover" className="space-y-4">
        <TabsList>
          <TabsTrigger value="discover">Discover</TabsTrigger>
          <TabsTrigger value="jobs">Jobs ({discoveryJobs.length})</TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="pending">
              Pending Approvals ({pendingRequests.length})
            </TabsTrigger>
          )}
        </TabsList>

        {/* Discover Tab */}
        <TabsContent value="discover" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Discovery Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-5 w-5 text-blue-600" />
                  Discovery Configuration
                </CardTitle>
                <CardDescription>
                  Configure and initiate network discovery scans
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Subnet Selection */}
                <div className="space-y-2">
                  <Label>Target Subnet</Label>
                  <div className="flex gap-2">
                    <select
                      value={selectedSubnet}
                      onChange={(e) => setSelectedSubnet(e.target.value)}
                      className="flex-1 px-3 py-2 border rounded-md"
                    >
                      {subnets.map(subnet => (
                        <option key={subnet} value={subnet}>{subnet}</option>
                      ))}
                    </select>
                  </div>
                  <div className="text-sm text-muted-foreground">Or enter custom:</div>
                  <Input
                    placeholder="192.168.1.0/24"
                    value={customSubnet}
                    onChange={(e) => setCustomSubnet(e.target.value)}
                  />
                </div>

                {/* Discovery Methods */}
                <div className="space-y-2">
                  <Label>Discovery Methods</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {DISCOVERY_METHODS.map(method => (
                      <div key={method.id} className="flex items-center space-x-2 p-2 border rounded-md">
                        <Checkbox
                          id={method.id}
                          checked={selectedMethods.includes(method.id)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedMethods([...selectedMethods, method.id]);
                            } else {
                              setSelectedMethods(selectedMethods.filter(m => m !== method.id));
                            }
                          }}
                        />
                        <Label htmlFor={method.id} className="flex items-center gap-1 text-sm cursor-pointer">
                          <method.icon className="h-4 w-4" />
                          {method.name}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SNMP Communities */}
                {selectedMethods.includes('snmp_discovery') && (
                  <div className="space-y-2">
                    <Label>SNMP Communities (comma-separated)</Label>
                    <Input
                      placeholder="public, private"
                      value={snmpCommunities}
                      onChange={(e) => setSnmpCommunities(e.target.value)}
                    />
                  </div>
                )}

                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-start gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div className="text-sm">
                    <p className="font-medium text-yellow-800">Admin Approval Required</p>
                    <p className="text-yellow-700">Network scans require administrator approval before execution.</p>
                  </div>
                </div>

                <Button 
                  className="w-full" 
                  onClick={handleRequestDiscovery}
                  disabled={loading || selectedMethods.length === 0}
                >
                  {loading ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-2" />Submitting...</>
                  ) : (
                    <><Search className="h-4 w-4 mr-2" />Request Discovery Scan</>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Polling Status */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5 text-green-600" />
                  Background Polling
                </CardTitle>
                <CardDescription>
                  Continuous SNMP monitoring of discovered devices
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                  <div>
                    <p className="font-medium">Polling Status</p>
                    <p className="text-sm text-muted-foreground">
                      {pollingStatus.running ? 'Active - polling every 30 seconds' : 'Inactive'}
                    </p>
                  </div>
                  <div className={`h-3 w-3 rounded-full ${pollingStatus.running ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
                </div>

                <div className="text-sm text-muted-foreground">
                  <p>Background polling will:</p>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    <li>Poll all SNMP-enabled devices every 30 seconds</li>
                    <li>Update device status (online/offline)</li>
                    <li>Collect performance metrics</li>
                    <li>Generate alerts for unreachable devices</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Jobs Tab */}
        <TabsContent value="jobs">
          <Card>
            <CardHeader>
              <CardTitle>Discovery Jobs</CardTitle>
            </CardHeader>
            <CardContent>
              {discoveryJobs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No discovery jobs yet
                </div>
              ) : (
                <div className="space-y-4">
                  {discoveryJobs.map(job => (
                    <div key={job.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{job.subnet}</span>
                          {getStatusBadge(job.status)}
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {job.devices_found} devices found
                        </span>
                      </div>
                      
                      {job.status === 'running' && (
                        <Progress value={job.progress} className="mb-2" />
                      )}
                      
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>Methods: {job.methods.join(', ')}</span>
                        <span>Started: {new Date(job.started_at).toLocaleString()}</span>
                        {job.approved_by && <span>Approved by: {job.approved_by}</span>}
                      </div>
                      
                      {job.error && (
                        <div className="mt-2 text-sm text-red-600">
                          Error: {job.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pending Approvals Tab (Admin Only) */}
        {isAdmin && (
          <TabsContent value="pending">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-orange-600" />
                  Pending Approval Requests
                </CardTitle>
              </CardHeader>
              <CardContent>
                {pendingRequests.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No pending requests
                  </div>
                ) : (
                  <div className="space-y-4">
                    {pendingRequests.map(request => (
                      <div key={request.id} className="border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <span className="font-medium">{request.subnet}</span>
                            <span className="ml-2 text-sm text-muted-foreground">
                              by {request.requested_by}
                            </span>
                          </div>
                          {getStatusBadge(request.status)}
                        </div>
                        
                        <div className="text-sm text-muted-foreground mb-3">
                          Methods: {request.methods.join(', ')}
                        </div>
                        
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleApproveRequest(request.id, true)}
                          >
                            <CheckCircle2 className="h-4 w-4 mr-1" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleApproveRequest(request.id, false)}
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            Reject
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* SSH Dialog */}
      <Dialog open={showSSHDialog} onOpenChange={setShowSSHDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              SSH Connection - {sshTarget?.ip_address}
            </DialogTitle>
            <DialogDescription>
              Connect to {sshTarget?.hostname || sshTarget?.ip_address} via SSH
            </DialogDescription>
          </DialogHeader>
          
          {!sshSession ? (
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Username</Label>
                  <Input
                    value={sshCredentials.username}
                    onChange={(e) => setSSHCredentials({...sshCredentials, username: e.target.value})}
                    placeholder="admin"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Password</Label>
                  <Input
                    type="password"
                    value={sshCredentials.password}
                    onChange={(e) => setSSHCredentials({...sshCredentials, password: e.target.value})}
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="bg-black text-green-400 font-mono text-sm p-4 rounded-lg h-64 overflow-auto">
                <pre>{sshOutput}</pre>
              </div>
              <div className="flex gap-2">
                <Input
                  value={sshCommand}
                  onChange={(e) => setSSHCommand(e.target.value)}
                  placeholder="Enter command..."
                  onKeyPress={(e) => e.key === 'Enter' && handleSSHExecute()}
                  className="font-mono"
                />
                <Button onClick={handleSSHExecute}>
                  <Play className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
          
          <DialogFooter>
            {!sshSession ? (
              <>
                <Button variant="outline" onClick={() => setShowSSHDialog(false)}>Cancel</Button>
                <Button onClick={handleSSHConnect} disabled={sshConnecting}>
                  {sshConnecting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Connect
                </Button>
              </>
            ) : (
              <Button variant="destructive" onClick={handleSSHDisconnect}>
                Disconnect
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
