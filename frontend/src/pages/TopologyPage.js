import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Network,
  RefreshCw,
  Server,
  Router,
  Shield,
  Cloud,
  HardDrive,
  Wifi,
  ZoomIn,
  ZoomOut
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const StatusBadge = ({ status }) => {
  const styles = {
    online: 'bg-green-500',
    offline: 'bg-red-500',
    degraded: 'bg-amber-500',
    maintenance: 'bg-blue-500',
    unknown: 'bg-slate-500',
  };

  return (
    <span className={`inline-block w-3 h-3 rounded-full ${styles[status] || styles.unknown}`} />
  );
};

const getDeviceIcon = (type) => {
  const icons = {
    router: Router,
    switch: Server,
    firewall: Shield,
    load_balancer: HardDrive,
    server: Server,
    virtual_machine: Cloud,
    cloud_instance: Cloud,
    access_point: Wifi,
  };
  return icons[type] || Server;
};

const getDeviceColor = (type, status) => {
  if (status === 'offline') return '#ef4444';
  if (status === 'degraded') return '#f59e0b';
  
  const colors = {
    router: '#3b82f6',
    switch: '#8b5cf6',
    firewall: '#ef4444',
    load_balancer: '#06b6d4',
    server: '#22c55e',
    virtual_machine: '#14b8a6',
    cloud_instance: '#f97316',
    access_point: '#6366f1',
  };
  return colors[type] || '#64748b';
};

export default function TopologyPage() {
  const canvasRef = useRef(null);
  const [topology, setTopology] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const fetchTopology = async () => {
    try {
      const response = await axios.get(`${API}/topology/data`);
      setTopology(response.data);
    } catch (error) {
      toast.error('Failed to fetch topology data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTopology();
  }, []);

  const drawTopology = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || topology.nodes.length === 0) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Calculate node positions based on location groups
    const locationGroups = {};
    topology.nodes.forEach(node => {
      const loc = node.location || 'Unknown';
      if (!locationGroups[loc]) {
        locationGroups[loc] = [];
      }
      locationGroups[loc].push(node);
    });

    const locations = Object.keys(locationGroups);
    const locationSpacing = width / (locations.length + 1);
    const nodePositions = {};

    locations.forEach((loc, locIndex) => {
      const nodes = locationGroups[loc];
      const x = locationSpacing * (locIndex + 1);
      const nodeSpacing = height / (nodes.length + 1);
      
      nodes.forEach((node, nodeIndex) => {
        nodePositions[node.id] = {
          x: x + (Math.random() - 0.5) * 50,
          y: nodeSpacing * (nodeIndex + 1),
          node
        };
      });
    });

    // Draw links
    topology.links.forEach(link => {
      const source = nodePositions[link.source];
      const target = nodePositions[link.target];
      if (!source || !target) return;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      
      // Different colors for link types
      const linkColors = {
        core: '#3b82f6',
        server: '#22c55e',
        cloud: '#f97316',
        wan: '#8b5cf6',
        edge: '#64748b'
      };
      ctx.strokeStyle = linkColors[link.type] || '#94a3b8';
      ctx.lineWidth = link.type === 'wan' ? 3 : 2;
      
      if (link.type === 'wan') {
        ctx.setLineDash([5, 5]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
    });

    // Draw nodes
    Object.values(nodePositions).forEach(({ x, y, node }) => {
      const color = getDeviceColor(node.type, node.status);
      const isSelected = selectedNode?.id === node.id;
      
      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, isSelected ? 28 : 24, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      
      if (isSelected) {
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      // Draw status indicator
      const statusColors = {
        online: '#22c55e',
        offline: '#ef4444',
        degraded: '#f59e0b',
        maintenance: '#3b82f6',
      };
      ctx.beginPath();
      ctx.arc(x + 16, y - 16, 6, 0, Math.PI * 2);
      ctx.fillStyle = statusColors[node.status] || '#64748b';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw node label
      ctx.fillStyle = '#1e293b';
      ctx.font = '11px Public Sans, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.name, x, y + 40);
      
      // Draw IP
      ctx.fillStyle = '#64748b';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(node.ip, x, y + 52);
    });

    // Store positions for click detection
    canvas.nodePositions = nodePositions;

    ctx.restore();
  }, [topology, selectedNode, zoom, pan]);

  useEffect(() => {
    drawTopology();
  }, [drawTopology]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left - pan.x) / zoom;
      const y = (e.clientY - rect.top - pan.y) / zoom;

      if (canvas.nodePositions) {
        for (const pos of Object.values(canvas.nodePositions)) {
          const dx = x - pos.x;
          const dy = y - pos.y;
          if (Math.sqrt(dx * dx + dy * dy) < 24) {
            setSelectedNode(pos.node);
            return;
          }
        }
      }
      setSelectedNode(null);
    };

    canvas.addEventListener('click', handleClick);
    return () => canvas.removeEventListener('click', handleClick);
  }, [zoom, pan]);

  // Handle canvas resize
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = 600;
        drawTopology();
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawTopology]);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 2));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.5));

  const deviceStats = {
    total: topology.nodes.length,
    online: topology.nodes.filter(n => n.status === 'online').length,
    offline: topology.nodes.filter(n => n.status === 'offline').length,
    degraded: topology.nodes.filter(n => n.status === 'degraded').length,
  };

  return (
    <div data-testid="topology-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Network Topology</h1>
          <p className="text-muted-foreground mt-1">Visual representation of network infrastructure</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={handleZoomOut} data-testid="zoom-out">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={handleZoomIn} data-testid="zoom-in">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={fetchTopology} data-testid="refresh-topology">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Network className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{deviceStats.total}</p>
              <p className="text-sm text-muted-foreground">Total Nodes</p>
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

      {/* Topology Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3 bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Network Map</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center h-[600px]">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="relative bg-slate-50 rounded-lg overflow-hidden">
                <canvas 
                  ref={canvasRef} 
                  className="w-full cursor-pointer"
                  style={{ height: '600px' }}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Legend and Selected Node Info */}
        <div className="space-y-4">
          <Card className="bg-white border-border/50">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">Legend</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-[#3b82f6]" />
                <span className="text-sm">Router</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-[#8b5cf6]" />
                <span className="text-sm">Switch</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-[#ef4444]" />
                <span className="text-sm">Firewall</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-[#22c55e]" />
                <span className="text-sm">Server</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full bg-[#f97316]" />
                <span className="text-sm">Cloud Instance</span>
              </div>
              <div className="border-t pt-3 mt-3">
                <p className="text-xs text-muted-foreground mb-2">Status Indicators</p>
                <div className="flex items-center gap-2">
                  <StatusBadge status="online" />
                  <span className="text-sm">Online</span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status="offline" />
                  <span className="text-sm">Offline</span>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status="degraded" />
                  <span className="text-sm">Degraded</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {selectedNode && (
            <Card className="bg-white border-border/50">
              <CardHeader>
                <CardTitle className="text-lg font-semibold">Selected Device</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedNode.status} />
                  <span className="font-medium">{selectedNode.name}</span>
                </div>
                <div className="text-sm space-y-1">
                  <p><span className="text-muted-foreground">Type:</span> {selectedNode.type}</p>
                  <p><span className="text-muted-foreground">IP:</span> <code className="text-xs bg-muted px-1 rounded">{selectedNode.ip}</code></p>
                  <p><span className="text-muted-foreground">Location:</span> {selectedNode.location}</p>
                  <p><span className="text-muted-foreground">Status:</span> <Badge variant="outline" className="capitalize">{selectedNode.status}</Badge></p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
