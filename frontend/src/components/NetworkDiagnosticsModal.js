import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ScrollArea } from './ui/scroll-area';
import { agentExecApi } from '../services/api';
import { toast } from 'sonner';
import { useVoiceAlert } from './VoiceAlertService';
import {
  Activity,
  ArrowRight,
  CheckCircle,
  XCircle,
  Clock,
  MapPin,
  Server,
  Wifi,
  Globe,
  AlertTriangle,
  Loader2,
  Play,
  RefreshCw,
  Network,
  Brain,
  Settings
} from 'lucide-react';

const HopTypeIcon = ({ type }) => {
  const icons = {
    gateway: Wifi,
    router: Server,
    backbone: Globe,
    exchange: Activity,
    cdn: Globe,
    datacenter: Server,
    destination: MapPin,
  };
  const Icon = icons[type] || Server;
  return <Icon className="h-4 w-4" />;
};

export default function NetworkDiagnosticsModal({ 
  isOpen, 
  onClose, 
  defaultTarget = '',
  deviceId = null,
  deviceName = null,
  onShowOnTopology = null  // Callback to show path on topology
}) {
  const navigate = useNavigate();
  const { announceNetworkFailure, announceTracerouteIssue, isMuted } = useVoiceAlert();
  const [activeTab, setActiveTab] = useState('ping');
  const [target, setTarget] = useState(defaultTarget);
  const [pingResult, setPingResult] = useState(null);
  const [tracerouteResult, setTracerouteResult] = useState(null);
  const [pingLoading, setPingLoading] = useState(false);
  const [tracerouteLoading, setTracerouteLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  
  // Routing optimization state
  const [routingOptimization, setRoutingOptimization] = useState(null);
  const [routingLoading, setRoutingLoading] = useState(false);

  const runPing = useCallback(async (targetOverride, silent = false) => {
    const pingTarget = targetOverride || target;
    if (!pingTarget) {
      toast.error('Please enter a target IP or hostname');
      return;
    }
    
    setPingLoading(true);
    try {
      const response = await agentExecApi.runPing(pingTarget, 4, deviceId);
      setPingResult(response.data);
      
      // Voice alert for unreachable or high packet loss
      if (response.data.status === 'unreachable') {
        announceNetworkFailure(deviceName || pingTarget, 'unreachable', 'Device is not responding to ping.');
      } else if (response.data.packet_loss_percent > 50) {
        announceNetworkFailure(deviceName || pingTarget, 'packet_loss', `${response.data.packet_loss_percent}% packet loss detected.`);
      }
      
      if (!silent) {
        toast.success(`Ping to ${pingTarget} completed`);
      }
    } catch (error) {
      if (!silent) {
        toast.error('Failed to run ping');
      }
      setPingResult(null);
    } finally {
      setPingLoading(false);
    }
  }, [deviceId, deviceName, announceNetworkFailure, target]);

  const runTraceroute = useCallback(async (targetOverride) => {
    const traceTarget = targetOverride || target;
    if (!traceTarget) {
      toast.error('Please enter a target IP or hostname');
      return;
    }
    
    setTracerouteLoading(true);
    try {
      const response = await agentExecApi.runTraceroute(traceTarget, 30, deviceId);
      setTracerouteResult(response.data);
      
      // Voice alert for traceroute issues
      if (response.data.issues_detected?.length > 0) {
        announceTracerouteIssue(traceTarget, response.data.issues_detected);
      }
      
      toast.success(`Traceroute to ${traceTarget} completed`);
    } catch (error) {
      toast.error('Failed to run traceroute');
      setTracerouteResult(null);
    } finally {
      setTracerouteLoading(false);
    }
  }, [deviceId, announceTracerouteIssue, target]);

  // Auto-run diagnostics when modal opens with a target
  useEffect(() => {
    if (isOpen && defaultTarget) {
      setTarget(defaultTarget);
      runPing(defaultTarget);
      runTraceroute(defaultTarget);
    }
  }, [isOpen, defaultTarget, runPing, runTraceroute]);

  // Auto-refresh ping every 5 seconds if enabled
  useEffect(() => {
    let interval;
    if (autoRefresh && target && !pingLoading) {
      interval = setInterval(() => {
        runPing(target, true);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh, target, pingLoading, runPing]);

  const runRoutingOptimization = async () => {
    setRoutingLoading(true);
    try {
      const response = await agentExecApi.getRoutingOptimization();
      setRoutingOptimization(response.data);
      toast.success('Routing optimization analysis complete');
    } catch (error) {
      toast.error('Failed to get routing optimization');
      setRoutingOptimization(null);
    } finally {
      setRoutingLoading(false);
    }
  };

  const handleShowOnTopology = () => {
    if (tracerouteResult?.hops) {
      // Store traceroute data in sessionStorage for the topology page
      sessionStorage.setItem('highlightedPath', JSON.stringify({
        target: target,
        hops: tracerouteResult.hops,
        timestamp: new Date().toISOString()
      }));
      onClose();
      navigate('/topology?showPath=true');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'reachable': return 'bg-green-500';
      case 'unreachable': return 'bg-red-500';
      case 'degraded': return 'bg-amber-500';
      default: return 'bg-slate-500';
    }
  };

  const getLatencyColor = (latency) => {
    if (!latency) return 'text-slate-400';
    if (latency < 20) return 'text-green-600';
    if (latency < 50) return 'text-amber-600';
    if (latency < 100) return 'text-orange-600';
    return 'text-red-600';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Activity className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <DialogTitle>Network Diagnostics</DialogTitle>
                {deviceName && (
                  <p className="text-sm text-muted-foreground mt-1">
                    Device: {deviceName}
                  </p>
                )}
              </div>
            </div>
          </div>
        </DialogHeader>

        {/* Target Input */}
        <div className="flex items-end gap-4 py-4 border-b">
          <div className="flex-1">
            <Label htmlFor="target">Target IP / Hostname</Label>
            <Input
              id="target"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="e.g., 8.8.8.8 or google.com"
              className="mt-1"
            />
          </div>
          <Button 
            onClick={() => { runPing(); runTraceroute(); }}
            disabled={pingLoading || tracerouteLoading}
          >
            {(pingLoading || tracerouteLoading) ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Run All
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="ping" className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Ping Status
              {pingResult && (
                <div className={`w-2 h-2 rounded-full ${getStatusColor(pingResult.status)}`} />
              )}
            </TabsTrigger>
            <TabsTrigger value="traceroute" className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              Traceroute Map
              {tracerouteResult && (
                <Badge variant="outline" className="ml-1 text-xs">
                  {tracerouteResult.total_hops} hops
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="routing" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Routing AI
            </TabsTrigger>
          </TabsList>

          {/* Ping Tab */}
          <TabsContent value="ping" className="flex-1 overflow-hidden">
            <div className="space-y-4">
              {/* Controls */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => runPing()}
                    disabled={pingLoading}
                  >
                    {pingLoading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-2" />
                    )}
                    Refresh
                  </Button>
                  <Button
                    size="sm"
                    variant={autoRefresh ? "default" : "outline"}
                    onClick={() => setAutoRefresh(!autoRefresh)}
                  >
                    {autoRefresh ? "Stop Auto-Refresh" : "Auto-Refresh (5s)"}
                  </Button>
                </div>
                {pingResult && (
                  <Badge 
                    variant="outline" 
                    className={pingResult.status === 'reachable' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}
                  >
                    {pingResult.status.toUpperCase()}
                  </Badge>
                )}
              </div>

              {pingLoading && !pingResult ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
                  <p className="text-muted-foreground">Running ping diagnostic...</p>
                </div>
              ) : pingResult ? (
                <div className="space-y-4">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold">{pingResult.packets_received}/{pingResult.packets_sent}</p>
                        <p className="text-xs text-muted-foreground">Packets Received</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <p className={`text-2xl font-bold ${pingResult.packet_loss_percent > 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {pingResult.packet_loss_percent}%
                        </p>
                        <p className="text-xs text-muted-foreground">Packet Loss</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <p className={`text-2xl font-bold ${getLatencyColor(pingResult.avg_latency_ms)}`}>
                          {pingResult.avg_latency_ms?.toFixed(1) || '-'}ms
                        </p>
                        <p className="text-xs text-muted-foreground">Avg Latency</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold">
                          {pingResult.min_latency_ms?.toFixed(1) || '-'} - {pingResult.max_latency_ms?.toFixed(1) || '-'}ms
                        </p>
                        <p className="text-xs text-muted-foreground">Min - Max</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Ping Results Grid */}
                  <Card>
                    <CardContent className="p-4">
                      <p className="text-sm font-medium mb-3">Ping Results</p>
                      <div className="grid grid-cols-4 gap-2">
                        {pingResult.ping_results?.map((ping) => (
                          <div 
                            key={`ping-${ping.seq}`}
                            className={`p-3 rounded-lg border text-center ${
                              ping.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                            }`}
                          >
                            <div className="flex items-center justify-center mb-1">
                              {ping.success ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              ) : (
                                <XCircle className="h-4 w-4 text-red-600" />
                              )}
                            </div>
                            <p className="text-xs font-mono">
                              {ping.success ? `${ping.latency_ms}ms` : 'Timeout'}
                            </p>
                            <p className="text-xs text-muted-foreground">seq={ping.seq}</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Enter a target and click "Run All" to start diagnostics</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Traceroute Tab */}
          <TabsContent value="traceroute" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[400px]">
              <div className="space-y-4 pr-4">
                {/* Controls */}
                <div className="flex items-center justify-between">
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => runTraceroute()}
                    disabled={tracerouteLoading}
                  >
                    {tracerouteLoading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-2" />
                    )}
                    Refresh
                  </Button>
                  {tracerouteResult && (
                    <Badge 
                      variant="outline" 
                      className={
                        tracerouteResult.path_quality === 'good' ? 'bg-green-50 text-green-700' :
                        tracerouteResult.path_quality === 'degraded' ? 'bg-amber-50 text-amber-700' :
                        'bg-red-50 text-red-700'
                      }
                    >
                      Path Quality: {tracerouteResult.path_quality?.toUpperCase()}
                    </Badge>
                  )}
                </div>

                {tracerouteLoading && !tracerouteResult ? (
                  <div className="flex flex-col items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
                    <p className="text-muted-foreground">Running traceroute...</p>
                  </div>
                ) : tracerouteResult ? (
                  <div className="space-y-4">
                    {/* Issues Alert */}
                    {tracerouteResult.issues_detected?.length > 0 && (
                      <Card className="bg-amber-50 border-amber-200">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-2 text-amber-700 mb-2">
                            <AlertTriangle className="h-4 w-4" />
                            <span className="font-medium">Issues Detected</span>
                          </div>
                          <ul className="text-sm text-amber-700 space-y-1">
                            {tracerouteResult.issues_detected.map((issue, idx) => (
                              <li key={`issue-${idx}-${issue.slice(0, 20)}`}>• {issue}</li>
                            ))}
                          </ul>
                        </CardContent>
                      </Card>
                    )}

                    {/* Visual Traceroute Map */}
                    <Card>
                      <CardContent className="p-4">
                        <p className="text-sm font-medium mb-4">Route Path Visualization</p>
                        <div className="space-y-0">
                          {tracerouteResult.hops?.map((hop) => (
                            <div key={`hop-${hop.hop_number}`} className="relative">
                              {/* Connection Line */}
                              {hop.hop_number > 1 && (
                                <div className="absolute left-5 -top-3 w-0.5 h-6 bg-gradient-to-b from-blue-400 to-blue-600" />
                              )}
                              
                              {/* Hop Node */}
                              <div className={`flex items-center gap-4 p-3 rounded-lg transition-colors ${
                                hop.is_destination ? 'bg-green-50 border border-green-200' :
                                hop.status === 'timeout' ? 'bg-red-50 border border-red-200' :
                                'bg-slate-50 border border-slate-200'
                              }`}>
                                {/* Hop Number Circle */}
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm ${
                                  hop.is_destination ? 'bg-green-500' :
                                  hop.status === 'timeout' ? 'bg-red-500' :
                                  'bg-blue-500'
                                }`}>
                                  {hop.hop}
                                </div>
                                
                                {/* Hop Info */}
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <HopTypeIcon type={hop.type} />
                                    <span className="font-medium">
                                      {hop.hostname || (hop.status === 'timeout' ? '* * *' : 'Unknown')}
                                    </span>
                                    {hop.is_destination && (
                                      <Badge className="bg-green-500 text-white text-xs">DESTINATION</Badge>
                                    )}
                                  </div>
                                  <p className="text-sm text-muted-foreground font-mono">
                                    {hop.ip || 'No response'}
                                  </p>
                                </div>
                                
                                {/* Latency */}
                                <div className="text-right">
                                  {hop.status === 'timeout' ? (
                                    <Badge variant="outline" className="bg-red-50 text-red-700">
                                      Timeout
                                    </Badge>
                                  ) : (
                                    <>
                                      <p className={`font-bold ${getLatencyColor(hop.avg_latency)}`}>
                                        {hop.avg_latency?.toFixed(1)}ms
                                      </p>
                                      <p className="text-xs text-muted-foreground">
                                        {hop.latency_1?.toFixed(1)} / {hop.latency_2?.toFixed(1)} / {hop.latency_3?.toFixed(1)}
                                      </p>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Summary */}
                    <div className="grid grid-cols-3 gap-4">
                      <Card>
                        <CardContent className="p-4 text-center">
                          <p className="text-2xl font-bold">{tracerouteResult.total_hops}</p>
                          <p className="text-xs text-muted-foreground">Total Hops</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4 text-center">
                          <p className={`text-2xl font-bold ${getLatencyColor(tracerouteResult.total_latency_ms)}`}>
                            {tracerouteResult.total_latency_ms?.toFixed(1) || '-'}ms
                          </p>
                          <p className="text-xs text-muted-foreground">Total Latency</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4 text-center">
                          {tracerouteResult.destination_reached ? (
                            <CheckCircle className="h-8 w-8 mx-auto text-green-500" />
                          ) : (
                            <XCircle className="h-8 w-8 mx-auto text-red-500" />
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {tracerouteResult.destination_reached ? 'Reached' : 'Not Reached'}
                          </p>
                        </CardContent>
                      </Card>
                    </div>
                    
                    {/* Show on Topology Button */}
                    <Button 
                      className="w-full mt-4"
                      variant="outline"
                      onClick={handleShowOnTopology}
                    >
                      <Network className="h-4 w-4 mr-2" />
                      Show Path on Network Topology
                    </Button>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <MapPin className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Enter a target and click "Run All" to trace the route</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Routing Optimization Tab */}
          <TabsContent value="routing" className="flex-1 overflow-hidden">
            <ScrollArea className="h-[400px]">
              <div className="space-y-4 pr-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    AI-powered routing protocol optimization suggestions
                  </p>
                  <Button 
                    onClick={runRoutingOptimization}
                    disabled={routingLoading}
                  >
                    {routingLoading ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Brain className="h-4 w-4 mr-2" />
                    )}
                    Analyze Network
                  </Button>
                </div>

                {routingLoading ? (
                  <div className="flex flex-col items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-purple-600 mb-4" />
                    <p className="text-muted-foreground">Analyzing network topology...</p>
                  </div>
                ) : routingOptimization ? (
                  <div className="space-y-4">
                    {/* Network Summary */}
                    <Card className="bg-slate-50">
                      <CardContent className="p-4">
                        <p className="text-sm font-medium mb-2">Network Summary</p>
                        <div className="grid grid-cols-4 gap-2 text-center">
                          <div>
                            <p className="text-lg font-bold">{routingOptimization.network_summary?.total_devices || 0}</p>
                            <p className="text-xs text-muted-foreground">Total Devices</p>
                          </div>
                          <div>
                            <p className="text-lg font-bold">{routingOptimization.network_summary?.routers || 0}</p>
                            <p className="text-xs text-muted-foreground">Routers</p>
                          </div>
                          <div>
                            <p className="text-lg font-bold">{routingOptimization.network_summary?.switches || 0}</p>
                            <p className="text-xs text-muted-foreground">Switches</p>
                          </div>
                          <div>
                            <p className="text-lg font-bold">{routingOptimization.network_summary?.locations?.length || 0}</p>
                            <p className="text-xs text-muted-foreground">Locations</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Recommended Protocol */}
                    {routingOptimization.optimization?.recommended_protocol && (
                      <Card className="bg-purple-50 border-purple-200">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Settings className="h-5 w-5 text-purple-600" />
                            <p className="font-medium text-purple-800">Recommended Protocol</p>
                          </div>
                          <p className="text-2xl font-bold text-purple-700 mb-2">
                            {routingOptimization.optimization.recommended_protocol.primary}
                          </p>
                          <p className="text-sm text-purple-700">
                            {routingOptimization.optimization.recommended_protocol.rationale}
                          </p>
                          {routingOptimization.optimization.recommended_protocol.alternative && (
                            <p className="text-xs text-purple-600 mt-2">
                              Alternative: {routingOptimization.optimization.recommended_protocol.alternative}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Network Assessment */}
                    {routingOptimization.optimization?.network_assessment && (
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm font-medium mb-2">Network Assessment</p>
                          <div className="flex gap-2 mb-2">
                            <Badge variant="outline">Size: {routingOptimization.optimization.network_assessment.size}</Badge>
                            <Badge variant="outline">Complexity: {routingOptimization.optimization.network_assessment.complexity}</Badge>
                          </div>
                          {routingOptimization.optimization.network_assessment.current_challenges?.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-medium mb-1">Challenges:</p>
                              <ul className="text-xs text-muted-foreground space-y-1">
                                {routingOptimization.optimization.network_assessment.current_challenges.map((c, i) => (
                                  <li key={`challenge-${i}-${c.slice(0, 15)}`}>• {c}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Implementation Priority */}
                    {routingOptimization.optimization?.implementation_priority?.length > 0 && (
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm font-medium mb-2">Implementation Priority</p>
                          <div className="space-y-2">
                            {routingOptimization.optimization.implementation_priority.map((item) => (
                              <div key={`priority-${item.priority}-${item.action?.slice(0, 15)}`} className="flex items-center gap-3 p-2 bg-slate-50 rounded">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                                  item.impact === 'high' ? 'bg-red-500' :
                                  item.impact === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                                }`}>
                                  {item.priority}
                                </div>
                                <div className="flex-1">
                                  <p className="text-sm">{item.action}</p>
                                  <Badge variant="outline" className="text-xs mt-1">
                                    {item.impact} impact
                                  </Badge>
                                </div>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Raw Analysis if no structured data */}
                    {routingOptimization.optimization?.raw_analysis && (
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm font-medium mb-2">Analysis</p>
                          <pre className="text-xs whitespace-pre-wrap bg-slate-50 p-3 rounded">
                            {routingOptimization.optimization.raw_analysis}
                          </pre>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Click "Analyze Network" to get AI-powered routing optimization suggestions</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
