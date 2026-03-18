import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Network,
  RefreshCw,
  Server,
  ZoomIn,
  ZoomOut,
  Move,
  Lock,
  Unlock,
  ExternalLink,
  Settings
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

// 3D colorful gradient colors for device types
const getDevice3DColors = (type, status) => {
  if (status === 'offline') {
    return {
      gradient1: '#ef4444',
      gradient2: '#dc2626',
      shadow: 'rgba(239, 68, 68, 0.4)',
      glow: 'rgba(239, 68, 68, 0.6)'
    };
  }
  if (status === 'degraded') {
    return {
      gradient1: '#f59e0b',
      gradient2: '#d97706',
      shadow: 'rgba(245, 158, 11, 0.4)',
      glow: 'rgba(245, 158, 11, 0.6)'
    };
  }
  
  const colorSchemes = {
    router: {
      gradient1: '#60a5fa',
      gradient2: '#2563eb',
      shadow: 'rgba(37, 99, 235, 0.4)',
      glow: 'rgba(96, 165, 250, 0.6)'
    },
    switch: {
      gradient1: '#a78bfa',
      gradient2: '#7c3aed',
      shadow: 'rgba(124, 58, 237, 0.4)',
      glow: 'rgba(167, 139, 250, 0.6)'
    },
    firewall: {
      gradient1: '#f87171',
      gradient2: '#dc2626',
      shadow: 'rgba(220, 38, 38, 0.4)',
      glow: 'rgba(248, 113, 113, 0.6)'
    },
    load_balancer: {
      gradient1: '#22d3ee',
      gradient2: '#0891b2',
      shadow: 'rgba(8, 145, 178, 0.4)',
      glow: 'rgba(34, 211, 238, 0.6)'
    },
    server: {
      gradient1: '#4ade80',
      gradient2: '#16a34a',
      shadow: 'rgba(22, 163, 74, 0.4)',
      glow: 'rgba(74, 222, 128, 0.6)'
    },
    virtual_machine: {
      gradient1: '#2dd4bf',
      gradient2: '#0d9488',
      shadow: 'rgba(13, 148, 136, 0.4)',
      glow: 'rgba(45, 212, 191, 0.6)'
    },
    cloud_instance: {
      gradient1: '#fb923c',
      gradient2: '#ea580c',
      shadow: 'rgba(234, 88, 12, 0.4)',
      glow: 'rgba(251, 146, 60, 0.6)'
    },
    access_point: {
      gradient1: '#818cf8',
      gradient2: '#4f46e5',
      shadow: 'rgba(79, 70, 229, 0.4)',
      glow: 'rgba(129, 140, 248, 0.6)'
    },
  };
  return colorSchemes[type] || colorSchemes.server;
};

export default function TopologyPage() {
  const canvasRef = useRef(null);
  const [topology, setTopology] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [nodePositions, setNodePositions] = useState({});
  const [isDragging, setIsDragging] = useState(false);
  const [draggedNode, setDraggedNode] = useState(null);
  const [isLocked, setIsLocked] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [lastPanPoint, setLastPanPoint] = useState({ x: 0, y: 0 });
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [deviceUrls, setDeviceUrls] = useState({});
  const [editingDeviceUrl, setEditingDeviceUrl] = useState('');

  const fetchTopology = async () => {
    try {
      const response = await axios.get(`${API}/topology/data`);
      setTopology(response.data);
      
      // Load saved device URLs from localStorage
      const savedUrls = localStorage.getItem('deviceUrls');
      if (savedUrls) {
        setDeviceUrls(JSON.parse(savedUrls));
      }
    } catch (error) {
      toast.error('Failed to fetch topology data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTopology();
  }, []);

  // Initialize node positions when topology loads
  useEffect(() => {
    if (topology.nodes.length === 0) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const width = canvas.width || 800;
    const height = canvas.height || 600;
    
    // Load saved positions from localStorage
    const savedPositions = localStorage.getItem('topologyPositions');
    if (savedPositions) {
      const parsed = JSON.parse(savedPositions);
      // Check if saved positions match current nodes
      const savedNodeIds = Object.keys(parsed);
      const currentNodeIds = topology.nodes.map(n => n.id);
      const allMatch = currentNodeIds.every(id => savedNodeIds.includes(id));
      
      if (allMatch) {
        setNodePositions(parsed);
        return;
      }
    }
    
    // Calculate initial positions based on location groups
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
    const newPositions = {};

    locations.forEach((loc, locIndex) => {
      const nodes = locationGroups[loc];
      const x = locationSpacing * (locIndex + 1);
      const nodeSpacing = height / (nodes.length + 1);
      
      nodes.forEach((node, nodeIndex) => {
        newPositions[node.id] = {
          x: x + (Math.random() - 0.5) * 30,
          y: nodeSpacing * (nodeIndex + 1),
        };
      });
    });

    setNodePositions(newPositions);
    localStorage.setItem('topologyPositions', JSON.stringify(newPositions));
  }, [topology.nodes]);

  // Draw 3D colorful node
  const draw3DNode = useCallback((ctx, x, y, node, isSelected, size) => {
    const colors = getDevice3DColors(node.type, node.status);
    
    // Draw shadow
    ctx.beginPath();
    ctx.ellipse(x + 4, y + size + 8, size * 0.8, size * 0.3, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
    ctx.fill();
    
    // Draw glow effect
    const glowGradient = ctx.createRadialGradient(x, y, 0, x, y, size * 1.5);
    glowGradient.addColorStop(0, colors.glow);
    glowGradient.addColorStop(1, 'transparent');
    ctx.beginPath();
    ctx.arc(x, y, size * 1.5, 0, Math.PI * 2);
    ctx.fillStyle = glowGradient;
    ctx.fill();
    
    // Draw main 3D sphere with gradient
    const sphereGradient = ctx.createRadialGradient(x - size * 0.3, y - size * 0.3, 0, x, y, size);
    sphereGradient.addColorStop(0, '#ffffff');
    sphereGradient.addColorStop(0.2, colors.gradient1);
    sphereGradient.addColorStop(0.7, colors.gradient2);
    sphereGradient.addColorStop(1, colors.shadow);
    
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fillStyle = sphereGradient;
    ctx.fill();
    
    // Draw highlight
    ctx.beginPath();
    ctx.arc(x - size * 0.25, y - size * 0.25, size * 0.35, 0, Math.PI * 2);
    const highlightGradient = ctx.createRadialGradient(
      x - size * 0.25, y - size * 0.25, 0,
      x - size * 0.25, y - size * 0.25, size * 0.35
    );
    highlightGradient.addColorStop(0, 'rgba(255, 255, 255, 0.8)');
    highlightGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = highlightGradient;
    ctx.fill();
    
    // Draw selection ring
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(x, y, size + 6, 0, Math.PI * 2);
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 3;
      ctx.stroke();
      
      // Animated pulse effect
      ctx.beginPath();
      ctx.arc(x, y, size + 10, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.3)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    
    // Draw device type icon inside the sphere
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    
    const iconSize = size * 0.5;
    
    switch (node.type) {
      case 'router':
        // Router icon - circle with arrows
        ctx.beginPath();
        ctx.arc(x, y, iconSize * 0.6, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x - iconSize, y);
        ctx.lineTo(x + iconSize, y);
        ctx.moveTo(x, y - iconSize);
        ctx.lineTo(x, y + iconSize);
        ctx.stroke();
        break;
        
      case 'switch':
        // Switch icon - rectangle with ports
        ctx.strokeRect(x - iconSize * 0.8, y - iconSize * 0.4, iconSize * 1.6, iconSize * 0.8);
        for (let i = 0; i < 4; i++) {
          ctx.fillRect(x - iconSize * 0.6 + i * iconSize * 0.4, y - iconSize * 0.2, iconSize * 0.15, iconSize * 0.4);
        }
        break;
        
      case 'firewall':
        // Firewall icon - wall pattern
        ctx.strokeRect(x - iconSize * 0.6, y - iconSize * 0.7, iconSize * 1.2, iconSize * 1.4);
        ctx.beginPath();
        ctx.moveTo(x - iconSize * 0.6, y - iconSize * 0.2);
        ctx.lineTo(x + iconSize * 0.6, y - iconSize * 0.2);
        ctx.moveTo(x - iconSize * 0.6, y + iconSize * 0.3);
        ctx.lineTo(x + iconSize * 0.6, y + iconSize * 0.3);
        ctx.moveTo(x, y - iconSize * 0.7);
        ctx.lineTo(x, y - iconSize * 0.2);
        ctx.moveTo(x - iconSize * 0.3, y - iconSize * 0.2);
        ctx.lineTo(x - iconSize * 0.3, y + iconSize * 0.3);
        ctx.stroke();
        break;
        
      case 'server':
      case 'virtual_machine':
        // Server icon - stacked rectangles
        ctx.strokeRect(x - iconSize * 0.5, y - iconSize * 0.6, iconSize, iconSize * 0.35);
        ctx.strokeRect(x - iconSize * 0.5, y - iconSize * 0.15, iconSize, iconSize * 0.35);
        ctx.strokeRect(x - iconSize * 0.5, y + iconSize * 0.3, iconSize, iconSize * 0.35);
        // LED indicators
        ctx.fillRect(x + iconSize * 0.25, y - iconSize * 0.5, iconSize * 0.1, iconSize * 0.15);
        ctx.fillRect(x + iconSize * 0.25, y - iconSize * 0.05, iconSize * 0.1, iconSize * 0.15);
        ctx.fillRect(x + iconSize * 0.25, y + iconSize * 0.4, iconSize * 0.1, iconSize * 0.15);
        break;
        
      case 'cloud_instance':
        // Cloud icon
        ctx.beginPath();
        ctx.arc(x - iconSize * 0.3, y + iconSize * 0.1, iconSize * 0.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + iconSize * 0.2, y, iconSize * 0.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + iconSize * 0.3, y + iconSize * 0.25, iconSize * 0.35, 0, Math.PI * 2);
        ctx.fill();
        break;
        
      case 'load_balancer':
        // Load balancer icon - triangle with lines
        ctx.beginPath();
        ctx.moveTo(x, y - iconSize * 0.6);
        ctx.lineTo(x + iconSize * 0.6, y + iconSize * 0.5);
        ctx.lineTo(x - iconSize * 0.6, y + iconSize * 0.5);
        ctx.closePath();
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x - iconSize * 0.3, y);
        ctx.lineTo(x + iconSize * 0.3, y);
        ctx.moveTo(x - iconSize * 0.4, y + iconSize * 0.25);
        ctx.lineTo(x + iconSize * 0.4, y + iconSize * 0.25);
        ctx.stroke();
        break;
        
      case 'access_point':
        // Access point icon - antenna with waves
        ctx.beginPath();
        ctx.moveTo(x, y + iconSize * 0.5);
        ctx.lineTo(x, y - iconSize * 0.1);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y + iconSize * 0.5, iconSize * 0.2, 0, Math.PI * 2);
        ctx.fill();
        // Waves
        ctx.beginPath();
        ctx.arc(x, y - iconSize * 0.2, iconSize * 0.3, Math.PI * 1.2, Math.PI * 1.8);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y - iconSize * 0.2, iconSize * 0.5, Math.PI * 1.15, Math.PI * 1.85);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y - iconSize * 0.2, iconSize * 0.7, Math.PI * 1.1, Math.PI * 1.9);
        ctx.stroke();
        break;
        
      default:
        // Default - simple circle
        ctx.beginPath();
        ctx.arc(x, y, iconSize * 0.5, 0, Math.PI * 2);
        ctx.fill();
    }
    
    // Draw status indicator
    const statusColors = {
      online: '#22c55e',
      offline: '#ef4444',
      degraded: '#f59e0b',
      maintenance: '#3b82f6',
    };
    ctx.beginPath();
    ctx.arc(x + size * 0.7, y - size * 0.7, 8, 0, Math.PI * 2);
    ctx.fillStyle = statusColors[node.status] || '#64748b';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Draw URL indicator if device has a configured URL
    if (deviceUrls[node.id]) {
      ctx.beginPath();
      ctx.arc(x - size * 0.7, y - size * 0.7, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#3b82f6';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }, [deviceUrls]);

  const drawTopology = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || topology.nodes.length === 0 || Object.keys(nodePositions).length === 0) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Draw links with gradient
    topology.links.forEach(link => {
      const source = nodePositions[link.source];
      const target = nodePositions[link.target];
      if (!source || !target) return;

      // Create gradient along the link
      const gradient = ctx.createLinearGradient(source.x, source.y, target.x, target.y);
      
      const linkColors = {
        core: ['#3b82f6', '#60a5fa'],
        server: ['#22c55e', '#4ade80'],
        cloud: ['#f97316', '#fb923c'],
        wan: ['#8b5cf6', '#a78bfa'],
        edge: ['#64748b', '#94a3b8']
      };
      
      const colors = linkColors[link.type] || linkColors.edge;
      gradient.addColorStop(0, colors[0]);
      gradient.addColorStop(1, colors[1]);
      
      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = gradient;
      ctx.lineWidth = link.type === 'wan' ? 4 : 3;
      
      if (link.type === 'wan') {
        ctx.setLineDash([8, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    });

    // Draw nodes with 3D effect
    topology.nodes.forEach(node => {
      const pos = nodePositions[node.id];
      if (!pos) return;
      
      const isSelected = selectedNode?.id === node.id;
      const size = isSelected ? 34 : 28;
      
      draw3DNode(ctx, pos.x, pos.y, node, isSelected, size);
      
      // Draw node label with background
      const labelY = pos.y + size + 18;
      ctx.font = 'bold 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      
      // Label background
      const labelWidth = ctx.measureText(node.name).width + 12;
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.roundRect(pos.x - labelWidth / 2, labelY - 10, labelWidth, 16, 4);
      ctx.fill();
      
      // Label text
      ctx.fillStyle = '#1e293b';
      ctx.fillText(node.name, pos.x, labelY);
      
      // Draw IP below label
      ctx.fillStyle = '#64748b';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(node.ip, pos.x, labelY + 14);
    });

    ctx.restore();
  }, [topology, selectedNode, zoom, pan, nodePositions, draw3DNode]);

  useEffect(() => {
    drawTopology();
  }, [drawTopology]);

  // Mouse event handlers
  const getCanvasCoords = useCallback((e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - pan.x) / zoom,
      y: (e.clientY - rect.top - pan.y) / zoom
    };
  }, [zoom, pan]);

  const findNodeAtPosition = useCallback((x, y) => {
    for (const node of topology.nodes) {
      const pos = nodePositions[node.id];
      if (!pos) continue;
      const dx = x - pos.x;
      const dy = y - pos.y;
      if (Math.sqrt(dx * dx + dy * dy) < 35) {
        return node;
      }
    }
    return null;
  }, [topology.nodes, nodePositions]);

  const handleMouseDown = useCallback((e) => {
    const coords = getCanvasCoords(e);
    const node = findNodeAtPosition(coords.x, coords.y);
    
    if (node && !isLocked) {
      setDraggedNode(node);
      setIsDragging(true);
      setSelectedNode(node);
    } else if (!node) {
      // Start panning
      setIsPanning(true);
      setLastPanPoint({ x: e.clientX, y: e.clientY });
    }
  }, [getCanvasCoords, findNodeAtPosition, isLocked]);

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    if (isDragging && draggedNode && !isLocked) {
      const coords = getCanvasCoords(e);
      setNodePositions(prev => {
        const newPositions = {
          ...prev,
          [draggedNode.id]: { x: coords.x, y: coords.y }
        };
        localStorage.setItem('topologyPositions', JSON.stringify(newPositions));
        return newPositions;
      });
    } else if (isPanning) {
      const dx = e.clientX - lastPanPoint.x;
      const dy = e.clientY - lastPanPoint.y;
      setPan(prev => ({ x: prev.x + dx, y: prev.y + dy }));
      setLastPanPoint({ x: e.clientX, y: e.clientY });
    } else {
      // Update cursor
      const coords = getCanvasCoords(e);
      const node = findNodeAtPosition(coords.x, coords.y);
      canvas.style.cursor = node && !isLocked ? 'grab' : 'default';
    }
  }, [isDragging, draggedNode, isPanning, lastPanPoint, isLocked, getCanvasCoords, findNodeAtPosition]);

  const handleMouseUp = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setDraggedNode(null);
    }
    setIsPanning(false);
  }, [isDragging]);

  const handleDoubleClick = useCallback((e) => {
    const coords = getCanvasCoords(e);
    const node = findNodeAtPosition(coords.x, coords.y);
    
    if (node) {
      const url = deviceUrls[node.id];
      if (url) {
        window.open(url, '_blank');
      } else {
        setSelectedNode(node);
        setEditingDeviceUrl(deviceUrls[node.id] || `https://${node.ip}/`);
        setConfigDialogOpen(true);
      }
    }
  }, [getCanvasCoords, findNodeAtPosition, deviceUrls]);

  // Canvas resize handler
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

  // Attach event listeners
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);
    canvas.addEventListener('dblclick', handleDoubleClick);

    return () => {
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('mouseleave', handleMouseUp);
      canvas.removeEventListener('dblclick', handleDoubleClick);
    };
  }, [handleMouseDown, handleMouseMove, handleMouseUp, handleDoubleClick]);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 2));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.5));
  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleSaveDeviceUrl = () => {
    if (selectedNode) {
      const newUrls = {
        ...deviceUrls,
        [selectedNode.id]: editingDeviceUrl
      };
      setDeviceUrls(newUrls);
      localStorage.setItem('deviceUrls', JSON.stringify(newUrls));
      toast.success(`URL saved for ${selectedNode.name}`);
      setConfigDialogOpen(false);
    }
  };

  const handleOpenDeviceUrl = () => {
    if (selectedNode && deviceUrls[selectedNode.id]) {
      window.open(deviceUrls[selectedNode.id], '_blank');
    }
  };

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
          <p className="text-muted-foreground mt-1">Interactive network visualization - drag nodes to rearrange</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant={isLocked ? "default" : "outline"} 
            size="icon" 
            onClick={() => setIsLocked(!isLocked)}
            title={isLocked ? "Unlock editing" : "Lock editing"}
          >
            {isLocked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="icon" onClick={handleZoomOut} data-testid="zoom-out">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={handleZoomIn} data-testid="zoom-in">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={handleResetView} title="Reset view">
            <Move className="h-4 w-4" />
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
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold">Network Map</CardTitle>
            <div className="text-sm text-muted-foreground">
              {isLocked ? '🔒 Locked' : '🔓 Drag nodes to rearrange • Double-click to open device URL'}
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center h-[600px]">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="relative bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg overflow-hidden border">
                <canvas 
                  ref={canvasRef} 
                  className="w-full"
                  style={{ height: '600px', cursor: isDragging ? 'grabbing' : 'default' }}
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
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 shadow-md" />
                <span className="text-sm">Router</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-purple-400 to-purple-600 shadow-md" />
                <span className="text-sm">Switch</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-red-400 to-red-600 shadow-md" />
                <span className="text-sm">Firewall</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-green-400 to-green-600 shadow-md" />
                <span className="text-sm">Server</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 shadow-md" />
                <span className="text-sm">Cloud Instance</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-cyan-400 to-cyan-600 shadow-md" />
                <span className="text-sm">Load Balancer</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-400 to-indigo-600 shadow-md" />
                <span className="text-sm">Access Point</span>
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
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-lg font-semibold">Selected Device</CardTitle>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => {
                    setEditingDeviceUrl(deviceUrls[selectedNode.id] || `https://${selectedNode.ip}/`);
                    setConfigDialogOpen(true);
                  }}
                >
                  <Settings className="h-4 w-4" />
                </Button>
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
                {deviceUrls[selectedNode.id] && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full mt-2"
                    onClick={handleOpenDeviceUrl}
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Device Config
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Device URL Configuration Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Configure Device URL</DialogTitle>
          </DialogHeader>
          {selectedNode && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
                <StatusBadge status={selectedNode.status} />
                <div>
                  <p className="font-medium">{selectedNode.name}</p>
                  <p className="text-sm text-muted-foreground">{selectedNode.ip}</p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="device-url">Configuration URL</Label>
                <Input
                  id="device-url"
                  value={editingDeviceUrl}
                  onChange={(e) => setEditingDeviceUrl(e.target.value)}
                  placeholder="https://device-ip/config"
                />
                <p className="text-xs text-muted-foreground">
                  Enter the URL to the device's configuration page. Double-click the device on the map to open this URL.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveDeviceUrl}>Save URL</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
