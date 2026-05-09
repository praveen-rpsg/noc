import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { incidentsApi, devicesApi, agentExecApi } from '../services/api';
import { toast } from 'sonner';
import NetworkDiagnosticsModal from '../components/NetworkDiagnosticsModal';
import {
  FileWarning,
  Plus,
  Search,
  RefreshCw,
  Brain,
  Clock,
  CheckCircle,
  AlertTriangle,
  ArrowUpRight,
  Loader2,
  Wrench,
  X,
  Zap,
  Play,
  Terminal,
  Activity
} from 'lucide-react';
import { format } from 'date-fns';

const PriorityBadge = ({ priority }) => {
  const styles = {
    P1: 'bg-red-600 text-white',
    P2: 'bg-orange-500 text-white',
    P3: 'bg-amber-500 text-white',
    P4: 'bg-slate-500 text-white',
  };

  return (
    <Badge className={`${styles[priority] || styles.P4}`}>
      {priority}
    </Badge>
  );
};

const StatusBadge = ({ status }) => {
  const styles = {
    open: 'bg-red-50 text-red-700 border-red-200',
    in_progress: 'bg-blue-50 text-blue-700 border-blue-200',
    escalated: 'bg-purple-50 text-purple-700 border-purple-200',
    resolved: 'bg-green-50 text-green-700 border-green-200',
    closed: 'bg-slate-50 text-slate-700 border-slate-200',
  };

  return (
    <Badge variant="outline" className={`${styles[status] || styles.open} capitalize`}>
      {status.replace('_', ' ')}
    </Badge>
  );
};

const initialFormState = {
  title: '',
  description: '',
  priority: 'P3',
  category: 'Network',
  affected_devices: [],
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterPriority, setFilterPriority] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [formData, setFormData] = useState(initialFormState);
  const [aiLoading, setAiLoading] = useState(false);
  
  // Context menu state
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, incident: null });
  const [isTroubleshootOpen, setIsTroubleshootOpen] = useState(false);
  const [troubleshootResult, setTroubleshootResult] = useState(null);
  const [troubleshootLoading, setTroubleshootLoading] = useState(false);
  
  // Agent execution state
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const [agentExecution, setAgentExecution] = useState(null);
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false);
  
  // Network diagnostics state
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(false);
  const [diagnosticsTarget, setDiagnosticsTarget] = useState('');
  const [diagnosticsDeviceId, setDiagnosticsDeviceId] = useState(null);
  const [diagnosticsDeviceName, setDiagnosticsDeviceName] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [incidentsRes, devicesRes] = await Promise.all([
        incidentsApi.getAll(),
        devicesApi.getAll(),
      ]);
      setIncidents(incidentsRes.data);
      setDevices(devicesRes.data);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Close context menu on click outside
  useEffect(() => {
    const handleClick = () => setContextMenu({ visible: false, x: 0, y: 0, incident: null });
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  const handleContextMenu = (e, incident) => {
    e.preventDefault();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      incident
    });
  };

  // Run autonomous agent on incident
  const handleRunAgent = async (incident) => {
    setContextMenu({ visible: false, x: 0, y: 0, incident: null });
    setIsAgentRunning(true);
    setAgentExecution(null);
    setIsAgentPanelOpen(true);
    
    try {
      const response = await agentExecApi.runOnIncident(incident.id);
      setAgentExecution({
        incident,
        ...response.data
      });
      
      if (response.data.incident_resolved) {
        toast.success('Incident resolved by AI Agent!');
      } else if (response.data.pending_confirmations?.length > 0) {
        toast.info(`Agent requires ${response.data.pending_confirmations.length} confirmation(s) to proceed`);
      } else {
        toast.success('AI Agent execution complete');
      }
      
      fetchData(); // Refresh incidents
    } catch (error) {
      toast.error('Failed to run AI Agent');
      setAgentExecution({
        incident,
        error: true,
        execution_log: [{
          timestamp: new Date().toISOString(),
          message: `Error: ${error.response?.data?.detail || error.message}`,
          type: 'error'
        }]
      });
    } finally {
      setIsAgentRunning(false);
    }
  };

  // Open network diagnostics for an incident
  const openDiagnostics = async (incident) => {
    setContextMenu({ visible: false, x: 0, y: 0, incident: null });
    
    // Get the first affected device's IP if available
    let targetIp = '';
    let deviceId = null;
    let deviceName = null;
    
    if (incident.affected_devices?.length > 0) {
      const device = devices.find(d => d.id === incident.affected_devices[0]);
      if (device) {
        targetIp = device.ip_address;
        deviceId = device.id;
        deviceName = device.name;
      }
    }
    
    setDiagnosticsTarget(targetIp);
    setDiagnosticsDeviceId(deviceId);
    setDiagnosticsDeviceName(deviceName);
    setIsDiagnosticsOpen(true);
  };

  const handleAiTroubleshoot = async (incident) => {
    setContextMenu({ visible: false, x: 0, y: 0, incident: null });
    setTroubleshootLoading(true);
    setTroubleshootResult(null);
    setIsTroubleshootOpen(true);
    
    try {
      const response = await incidentsApi.aiTroubleshoot(incident.id);
      setTroubleshootResult({
        incident,
        ...response.data
      });
      toast.success('AI troubleshooting complete');
      fetchData(); // Refresh to get updated incident status
    } catch (error) {
      toast.error('Failed to run AI troubleshooting');
      setTroubleshootResult({
        incident,
        analysis: 'Error: Failed to get AI analysis. Please try again.',
        error: true
      });
    } finally {
      setTroubleshootLoading(false);
    }
  };

  const filteredIncidents = incidents.filter((incident) => {
    const matchesSearch = incident.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      incident.ticket_number.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPriority = filterPriority === 'all' || incident.priority === filterPriority;
    const matchesStatus = filterStatus === 'all' || incident.status === filterStatus;
    return matchesSearch && matchesPriority && matchesStatus;
  });

  const handleCreate = async () => {
    try {
      await incidentsApi.create(formData);
      toast.success('Incident created successfully');
      setIsCreateOpen(false);
      setFormData(initialFormState);
      fetchData();
    } catch (error) {
      toast.error('Failed to create incident');
    }
  };

  const handleStatusUpdate = async (incidentId, newStatus) => {
    try {
      await incidentsApi.update(incidentId, { status: newStatus });
      toast.success('Incident updated');
      fetchData();
      if (selectedIncident?.id === incidentId) {
        setSelectedIncident({ ...selectedIncident, status: newStatus });
      }
    } catch (error) {
      toast.error('Failed to update incident');
    }
  };

  const handleGetAiAnalysis = async (incidentId) => {
    setAiLoading(true);
    try {
      const response = await incidentsApi.getAiAnalysis(incidentId);
      toast.success('AI analysis completed');
      // Refresh incident to get updated ai_suggestions
      const updatedIncident = await incidentsApi.getOne(incidentId);
      setSelectedIncident(updatedIncident.data);
      fetchData();
    } catch (error) {
      toast.error('Failed to get AI analysis');
    } finally {
      setAiLoading(false);
    }
  };

  const openDetailDialog = async (incident) => {
    try {
      const response = await incidentsApi.getOne(incident.id);
      setSelectedIncident(response.data);
      setIsDetailOpen(true);
    } catch (error) {
      toast.error('Failed to load incident details');
    }
  };

  const incidentStats = {
    total: incidents.length,
    open: incidents.filter(i => i.status === 'open').length,
    inProgress: incidents.filter(i => i.status === 'in_progress').length,
    p1Open: incidents.filter(i => i.priority === 'P1' && i.status !== 'closed' && i.status !== 'resolved').length,
  };

  return (
    <div data-testid="incidents-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Incident Management</h1>
          <p className="text-muted-foreground mt-1">Track and resolve incidents with AI assistance</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-incident-btn">
              <Plus className="h-4 w-4 mr-2" />
              New Incident
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Create New Incident</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="Brief incident title"
                  data-testid="incident-title-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Detailed description of the incident..."
                  rows={4}
                  data-testid="incident-desc-input"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select value={formData.priority} onValueChange={(v) => setFormData({ ...formData, priority: v })}>
                    <SelectTrigger data-testid="incident-priority-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="P1">P1 - Critical</SelectItem>
                      <SelectItem value="P2">P2 - High</SelectItem>
                      <SelectItem value="P3">P3 - Medium</SelectItem>
                      <SelectItem value="P4">P4 - Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select value={formData.category} onValueChange={(v) => setFormData({ ...formData, category: v })}>
                    <SelectTrigger data-testid="incident-category-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Network">Network</SelectItem>
                      <SelectItem value="Server">Server</SelectItem>
                      <SelectItem value="Application">Application</SelectItem>
                      <SelectItem value="Security">Security</SelectItem>
                      <SelectItem value="Database">Database</SelectItem>
                      <SelectItem value="Storage">Storage</SelectItem>
                      <SelectItem value="Backup">Backup</SelectItem>
                      <SelectItem value="Other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} data-testid="save-incident-btn">Create Incident</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <FileWarning className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{incidentStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Incidents</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-50">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{incidentStats.open}</p>
              <p className="text-sm text-muted-foreground">Open</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Clock className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">{incidentStats.inProgress}</p>
              <p className="text-sm text-muted-foreground">In Progress</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-100">
              <AlertTriangle className="h-6 w-6 text-red-700" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-700">{incidentStats.p1Open}</p>
              <p className="text-sm text-muted-foreground">P1 Open</p>
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
                placeholder="Search by title or ticket number..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="incident-search"
              />
            </div>
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="P1">P1</SelectItem>
                <SelectItem value="P2">P2</SelectItem>
                <SelectItem value="P3">P3</SelectItem>
                <SelectItem value="P4">P4</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchData}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Incidents Table */}
      <Card className="bg-white border-border/50">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticket</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Category</TableHead>
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
                ) : filteredIncidents.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10">
                      <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-2" />
                      <p className="text-muted-foreground">No incidents found</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredIncidents.map((incident) => (
                    <TableRow 
                      key={incident.id} 
                      className="table-row-hover cursor-pointer" 
                      onClick={() => openDetailDialog(incident)}
                      onContextMenu={(e) => handleContextMenu(e, incident)}
                      data-testid={`incident-row-${incident.id}`}
                    >
                      <TableCell className="font-mono text-sm">{incident.ticket_number}</TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{incident.title}</p>
                          <p className="text-xs text-muted-foreground truncate max-w-xs">{incident.description}</p>
                        </div>
                      </TableCell>
                      <TableCell><PriorityBadge priority={incident.priority} /></TableCell>
                      <TableCell><StatusBadge status={incident.status} /></TableCell>
                      <TableCell>{incident.category}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {format(new Date(incident.created_at), 'MMM d, HH:mm')}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); openDetailDialog(incident); }}>
                          <ArrowUpRight className="h-4 w-4" />
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

      {/* Incident Detail Dialog */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <DialogTitle className="font-mono">{selectedIncident?.ticket_number}</DialogTitle>
              {selectedIncident && <PriorityBadge priority={selectedIncident.priority} />}
              {selectedIncident && <StatusBadge status={selectedIncident.status} />}
            </div>
          </DialogHeader>
          
          {selectedIncident && (
            <Tabs defaultValue="details" className="mt-4">
              <TabsList>
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="ai-analysis">AI Analysis</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="space-y-4 mt-4">
                <div>
                  <h3 className="text-lg font-semibold">{selectedIncident.title}</h3>
                  <p className="text-muted-foreground mt-2">{selectedIncident.description}</p>
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Category</p>
                    <p className="font-medium">{selectedIncident.category}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Created By</p>
                    <p className="font-medium">{selectedIncident.created_by}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Escalation Level</p>
                    <p className="font-medium">L{selectedIncident.escalation_level}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Created</p>
                    <p className="font-medium">{format(new Date(selectedIncident.created_at), 'PPpp')}</p>
                  </div>
                </div>

                <div className="flex gap-2 pt-4">
                  {selectedIncident.status === 'open' && (
                    <Button onClick={() => handleStatusUpdate(selectedIncident.id, 'in_progress')}>
                      Start Working
                    </Button>
                  )}
                  {selectedIncident.status === 'in_progress' && (
                    <>
                      <Button onClick={() => handleStatusUpdate(selectedIncident.id, 'escalated')} variant="outline">
                        Escalate
                      </Button>
                      <Button onClick={() => handleStatusUpdate(selectedIncident.id, 'resolved')} className="bg-green-600 hover:bg-green-700">
                        Resolve
                      </Button>
                    </>
                  )}
                  {selectedIncident.status === 'resolved' && (
                    <Button onClick={() => handleStatusUpdate(selectedIncident.id, 'closed')} variant="outline">
                      Close Incident
                    </Button>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="ai-analysis" className="space-y-4 mt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-semibold flex items-center gap-2">
                      <Brain className="h-5 w-5 text-purple-600" />
                      AI-Powered Troubleshooting
                    </h4>
                    <p className="text-sm text-muted-foreground">Get AI suggestions for root cause and resolution</p>
                  </div>
                  <Button 
                    onClick={() => handleGetAiAnalysis(selectedIncident.id)}
                    disabled={aiLoading}
                    data-testid="get-ai-analysis-btn"
                  >
                    {aiLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Brain className="h-4 w-4 mr-2" />
                        Get AI Analysis
                      </>
                    )}
                  </Button>
                </div>

                {selectedIncident.ai_suggestions ? (
                  <Card className="bg-purple-50 border-purple-200">
                    <CardContent className="p-4">
                      <div className="prose prose-sm max-w-none">
                        <pre className="whitespace-pre-wrap text-sm font-sans bg-white p-4 rounded-lg border">
                          {selectedIncident.ai_suggestions}
                        </pre>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="bg-muted/50">
                    <CardContent className="p-8 text-center text-muted-foreground">
                      <Brain className="h-12 w-12 mx-auto mb-2 text-muted-foreground/50" />
                      <p>No AI analysis yet. Click the button above to get AI-powered suggestions.</p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="timeline" className="mt-4">
                <div className="space-y-4">
                  <div className="flex gap-4">
                    <div className="w-3 h-3 rounded-full bg-green-500 mt-1.5" />
                    <div>
                      <p className="font-medium">Incident Created</p>
                      <p className="text-sm text-muted-foreground">
                        {format(new Date(selectedIncident.created_at), 'PPpp')}
                      </p>
                    </div>
                  </div>
                  {selectedIncident.resolved_at && (
                    <div className="flex gap-4">
                      <div className="w-3 h-3 rounded-full bg-blue-500 mt-1.5" />
                      <div>
                        <p className="font-medium">Incident Resolved</p>
                        <p className="text-sm text-muted-foreground">
                          {format(new Date(selectedIncident.resolved_at), 'PPpp')}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>

      {/* Context Menu */}
      {contextMenu.visible && (
        <div 
          className="fixed z-50 bg-white rounded-lg shadow-lg border border-border/50 py-2 min-w-[220px]"
          style={{ 
            left: Math.min(contextMenu.x, window.innerWidth - 240),
            top: Math.min(contextMenu.y, window.innerHeight - 180)
          }}
          data-testid="incident-context-menu"
        >
          <button
            className="w-full px-4 py-2 text-left hover:bg-green-50 flex items-center gap-2 text-sm font-medium border-b border-border/30 pb-2 mb-1"
            onClick={() => handleRunAgent(contextMenu.incident)}
            data-testid="context-menu-run-agent"
          >
            <Zap className="h-4 w-4 text-green-600" />
            <span className="text-green-700">Run AI Agent (Auto-Fix)</span>
          </button>
          <button
            className="w-full px-4 py-2 text-left hover:bg-purple-50 flex items-center gap-2 text-sm"
            onClick={() => handleAiTroubleshoot(contextMenu.incident)}
            data-testid="context-menu-troubleshoot"
          >
            <Brain className="h-4 w-4 text-purple-600" />
            <span>AI Analysis Only</span>
          </button>
          <button
            className="w-full px-4 py-2 text-left hover:bg-slate-50 flex items-center gap-2 text-sm"
            onClick={() => {
              openDetailDialog(contextMenu.incident);
              setContextMenu({ visible: false, x: 0, y: 0, incident: null });
            }}
            data-testid="context-menu-view-details"
          >
            <ArrowUpRight className="h-4 w-4 text-slate-600" />
            <span>View Details</span>
          </button>
          <button
            className="w-full px-4 py-2 text-left hover:bg-cyan-50 flex items-center gap-2 text-sm border-t border-border/30 mt-1 pt-2"
            onClick={() => openDiagnostics(contextMenu.incident)}
            data-testid="context-menu-diagnostics"
          >
            <Activity className="h-4 w-4 text-cyan-600" />
            <span>Network Diagnostics</span>
          </button>
          {contextMenu.incident?.status === 'open' && (
            <button
              className="w-full px-4 py-2 text-left hover:bg-blue-50 flex items-center gap-2 text-sm"
              onClick={() => {
                handleStatusUpdate(contextMenu.incident.id, 'in_progress');
                setContextMenu({ visible: false, x: 0, y: 0, incident: null });
              }}
              data-testid="context-menu-start-working"
            >
              <Wrench className="h-4 w-4 text-blue-600" />
              <span>Start Working</span>
            </button>
          )}
        </div>
      )}

      {/* AI Troubleshoot Modal */}
      <Dialog open={isTroubleshootOpen} onOpenChange={setIsTroubleshootOpen}>
        <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <Brain className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <DialogTitle>AI Troubleshooting Report</DialogTitle>
                  {troubleshootResult?.incident && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {troubleshootResult.incident.ticket_number} - {troubleshootResult.incident.title}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </DialogHeader>
          
          <div className="mt-4">
            {troubleshootLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-12 w-12 animate-spin text-purple-600 mb-4" />
                <p className="text-lg font-medium">AI Agent is analyzing...</p>
                <p className="text-sm text-muted-foreground">Gathering incident data and generating troubleshooting report</p>
              </div>
            ) : troubleshootResult ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>Report ID: {troubleshootResult.report_id}</span>
                  <span>Generated: {troubleshootResult.created_at ? format(new Date(troubleshootResult.created_at), 'PPpp') : 'N/A'}</span>
                </div>
                
                <Card className={`${troubleshootResult.error ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
                  <CardContent className="p-4">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                      {troubleshootResult.analysis}
                    </pre>
                  </CardContent>
                </Card>
                
                <div className="flex justify-end gap-2 pt-4">
                  <Button variant="outline" onClick={() => setIsTroubleshootOpen(false)}>
                    Close
                  </Button>
                  {troubleshootResult.incident && (
                    <Button onClick={() => {
                      setIsTroubleshootOpen(false);
                      openDetailDialog(troubleshootResult.incident);
                    }}>
                      View Incident
                    </Button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      {/* AI Agent Execution Panel */}
      <Dialog open={isAgentPanelOpen} onOpenChange={setIsAgentPanelOpen}>
        <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${isAgentRunning ? 'bg-green-100 animate-pulse' : 'bg-green-100'}`}>
                <Zap className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <DialogTitle>AI Agent Execution</DialogTitle>
                {agentExecution?.incident && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {agentExecution.incident.ticket_number} - {agentExecution.incident.title}
                  </p>
                )}
              </div>
            </div>
          </DialogHeader>
          
          <div className="mt-4">
            {isAgentRunning && !agentExecution ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-12 w-12 animate-spin text-green-600 mb-4" />
                <p className="text-lg font-medium">AI Agent is executing...</p>
                <p className="text-sm text-muted-foreground">Analyzing incident and taking corrective actions</p>
              </div>
            ) : agentExecution ? (
              <div className="space-y-4">
                {/* Status Badge */}
                <div className="flex items-center justify-between">
                  <Badge 
                    variant="outline" 
                    className={
                      agentExecution.status === 'completed' ? 'bg-green-50 text-green-700 border-green-200' :
                      agentExecution.status === 'waiting_confirmation' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                      agentExecution.status === 'failed' ? 'bg-red-50 text-red-700 border-red-200' :
                      'bg-blue-50 text-blue-700 border-blue-200'
                    }
                  >
                    {agentExecution.status?.replace(/_/g, ' ').toUpperCase() || 'UNKNOWN'}
                  </Badge>
                  {agentExecution.incident_resolved && (
                    <Badge className="bg-green-600 text-white">
                      <CheckCircle className="h-3 w-3 mr-1" />
                      RESOLVED
                    </Badge>
                  )}
                </div>

                {/* Root Cause */}
                {agentExecution.root_cause && (
                  <Card className="bg-slate-50 border-slate-200">
                    <CardContent className="p-4">
                      <p className="text-sm font-medium text-slate-600 mb-1">Root Cause Analysis</p>
                      <p className="text-sm">{agentExecution.root_cause}</p>
                    </CardContent>
                  </Card>
                )}

                {/* Pending Confirmations Alert */}
                {agentExecution.pending_confirmations?.length > 0 && (
                  <Card className="bg-amber-50 border-amber-200">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 text-amber-700 mb-2">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="font-medium">Actions Pending Your Confirmation</span>
                      </div>
                      <p className="text-sm text-amber-700">
                        {agentExecution.pending_confirmations.length} action(s) require your approval before they can be executed.
                        Check the notification bell in the top-right corner to approve or reject.
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Execution Log */}
                <div>
                  <p className="text-sm font-medium mb-2 flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Execution Log
                  </p>
                  <Card className="bg-slate-900 border-slate-700">
                    <CardContent className="p-4">
                      <ScrollArea className="h-64">
                        <div className="space-y-1 font-mono text-xs">
                          {agentExecution.execution_log?.map((log, idx) => (
                            <div 
                              key={log.id || `log-${log.timestamp || idx}`} 
                              className={`
                                ${log.type === 'error' ? 'text-red-400' : ''}
                                ${log.type === 'success' ? 'text-green-400' : ''}
                                ${log.type === 'warning' ? 'text-amber-400' : ''}
                                ${log.type === 'confirmation_required' ? 'text-amber-400' : ''}
                                ${log.type === 'info' ? 'text-slate-300' : ''}
                                ${log.type === 'analysis' ? 'text-purple-400' : ''}
                                ${log.type === 'executing' ? 'text-blue-400' : ''}
                                ${log.type === 'result' ? 'text-cyan-400' : ''}
                                ${!log.type ? 'text-slate-400' : ''}
                              `}
                            >
                              <span className="text-slate-500">[{log.timestamp ? format(new Date(log.timestamp), 'HH:mm:ss') : '--:--:--'}]</span> {log.message}
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>

                {/* Actions Summary */}
                {agentExecution.executed_actions?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Executed Actions ({agentExecution.executed_actions.length})</p>
                    <div className="space-y-2">
                      {agentExecution.executed_actions.map((action) => (
                        <div key={action.action_id || action.action_type} className="flex items-center gap-2 text-sm p-2 rounded bg-slate-50">
                          {action.success ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <X className="h-4 w-4 text-red-500" />
                          )}
                          <span className="capitalize">{action.action_type?.replace(/_/g, ' ')}</span>
                          {action.result?.simulated && (
                            <Badge variant="outline" className="text-xs">Simulated</Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <DialogFooter>
                  <Button 
                    variant="outline" 
                    onClick={() => {
                      if (agentExecution?.incident) {
                        openDiagnostics(agentExecution.incident);
                      }
                    }}
                    disabled={!agentExecution?.device_ip}
                  >
                    <Activity className="h-4 w-4 mr-2" />
                    Network Diagnostics
                  </Button>
                  <Button variant="outline" onClick={() => setIsAgentPanelOpen(false)}>
                    Close
                  </Button>
                  {agentExecution.incident && !agentExecution.incident_resolved && (
                    <Button onClick={() => handleRunAgent(agentExecution.incident)} disabled={isAgentRunning}>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Run Again
                    </Button>
                  )}
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
