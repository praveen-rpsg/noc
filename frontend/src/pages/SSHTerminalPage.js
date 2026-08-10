import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { devicesApi } from '../services/api';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Terminal,
  Play,
  Trash2,
  RefreshCw,
  Server,
  Shield,
  Loader2,
  Send,
  Copy,
  Download
} from 'lucide-react';
import { getApiUrl } from '../services/config';
import { getAuthHeader } from '../services/auth';

const API = getApiUrl();

export default function SSHTerminalPage() {
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [command, setCommand] = useState('');
  const [output, setOutput] = useState([]);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const outputRef = useRef(null);

  const fetchDevices = async () => {
    try {
      const response = await devicesApi.getAll();
      // Filter devices that support SSH (servers, routers, switches, firewalls)
      const sshDevices = response.data.filter(d => 
        ['server', 'router', 'switch', 'firewall', 'virtual_machine', 'cloud_instance'].includes(d.type)
      );
      setDevices(sshDevices);
    } catch (error) {
      toast.error('Failed to fetch devices');
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  useEffect(() => {
    // Scroll to bottom when new output is added
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleConnect = async () => {
    if (!selectedDevice || !username || !password) {
      toast.error('Please fill in all connection details');
      return;
    }

    setConnecting(true);
    try {
      await axios.post(`${API}/ssh/connect`, {
        device_id: selectedDevice,
        username,
        password
      }, { headers: getAuthHeader() });
      setConnected(true);
      toast.success('SSH connection established');
      addOutput('system', `Connected to ${devices.find(d => d.id === selectedDevice)?.name}`);
    } catch (error) {
      const message = error.response?.data?.detail || 'Connection failed';
      toast.error(message);
      addOutput('error', message);
    } finally {
      setConnecting(false);
    }
  };

  const handleExecute = async () => {
    if (!command.trim()) return;
    if (!connected) {
      toast.error('Please connect to a device first');
      return;
    }

    const currentCommand = command;
    setCommand('');
    addOutput('command', currentCommand);
    setLoading(true);

    try {
      const response = await axios.post(`${API}/ssh/execute`, {
        device_id: selectedDevice,
        username,
        password,
        command: currentCommand
      }, { headers: getAuthHeader() });

      if (response.data.output) {
        addOutput('output', response.data.output);
      }
      if (response.data.error) {
        addOutput('error', response.data.error);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Command execution failed';
      addOutput('error', message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const addOutput = (type, text) => {
    const timestamp = new Date().toLocaleTimeString();
    setOutput(prev => [...prev, { type, text, timestamp }]);
  };

  const handleDisconnect = () => {
    setConnected(false);
    addOutput('system', 'Disconnected');
    toast.info('Disconnected from device');
  };

  const handleClear = () => {
    setOutput([]);
  };

  const handleCopyOutput = () => {
    const text = output.map(o => `[${o.timestamp}] ${o.text}`).join('\n');
    navigator.clipboard.writeText(text);
    toast.success('Output copied to clipboard');
  };

  const handleDownloadLog = () => {
    const text = output.map(o => `[${o.timestamp}] [${o.type.toUpperCase()}] ${o.text}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ssh-session-${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleExecute();
    }
  };

  const selectedDeviceInfo = devices.find(d => d.id === selectedDevice);

  return (
    <div data-testid="ssh-terminal-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">SSH Terminal</h1>
          <p className="text-muted-foreground mt-1">Remote access to network devices and servers</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Connection Panel */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Connection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Device</Label>
              <Select value={selectedDevice} onValueChange={setSelectedDevice} disabled={connected}>
                <SelectTrigger data-testid="ssh-device-select">
                  <SelectValue placeholder="Select device" />
                </SelectTrigger>
                <SelectContent>
                  {devices.map((device) => (
                    <SelectItem key={device.id} value={device.id}>
                      <div className="flex items-center gap-2">
                        <Server className="h-4 w-4" />
                        <span>{device.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {device.ip_address}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Username</Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                disabled={connected}
                data-testid="ssh-username"
              />
            </div>

            <div className="space-y-2">
              <Label>Password</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={connected}
                data-testid="ssh-password"
              />
            </div>

            {!connected ? (
              <Button 
                onClick={handleConnect} 
                className="w-full" 
                disabled={connecting || !selectedDevice}
                data-testid="ssh-connect-btn"
              >
                {connecting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Connect
                  </>
                )}
              </Button>
            ) : (
              <Button 
                onClick={handleDisconnect} 
                variant="destructive" 
                className="w-full"
                data-testid="ssh-disconnect-btn"
              >
                Disconnect
              </Button>
            )}

            {selectedDeviceInfo && (
              <div className="pt-4 border-t">
                <p className="text-xs text-muted-foreground mb-2">Device Info</p>
                <div className="text-sm space-y-1">
                  <p><span className="text-muted-foreground">Type:</span> {selectedDeviceInfo.type}</p>
                  <p><span className="text-muted-foreground">IP:</span> <code className="text-xs bg-muted px-1 rounded">{selectedDeviceInfo.ip_address}</code></p>
                  <p><span className="text-muted-foreground">Status:</span> 
                    <Badge variant="outline" className={`ml-1 ${selectedDeviceInfo.status === 'online' ? 'text-green-600' : 'text-red-600'}`}>
                      {selectedDeviceInfo.status}
                    </Badge>
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Terminal */}
        <Card className="lg:col-span-3 bg-white border-border/50">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Terminal
              {connected && (
                <Badge className="bg-green-500">Connected</Badge>
              )}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="icon" onClick={handleCopyOutput} title="Copy output">
                <Copy className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" onClick={handleDownloadLog} title="Download log">
                <Download className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" onClick={handleClear} title="Clear terminal">
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {/* Terminal Output */}
            <div 
              ref={outputRef}
              className="bg-slate-900 rounded-lg p-4 h-[400px] overflow-y-auto font-mono text-sm"
              data-testid="ssh-output"
            >
              {output.length === 0 ? (
                <div className="text-slate-500">
                  {connected 
                    ? 'Ready. Type a command and press Enter.'
                    : 'Connect to a device to start a session.'
                  }
                </div>
              ) : (
                output.map((entry) => (
                  <div key={entry.id || `${entry.timestamp}-${entry.type}`} className="mb-2">
                    <span className="text-slate-500 text-xs">[{entry.timestamp}]</span>
                    {entry.type === 'command' && (
                      <div className="text-green-400">
                        <span className="text-blue-400">$ </span>
                        {entry.text}
                      </div>
                    )}
                    {entry.type === 'output' && (
                      <pre className="text-slate-300 whitespace-pre-wrap">{entry.text}</pre>
                    )}
                    {entry.type === 'error' && (
                      <div className="text-red-400">{entry.text}</div>
                    )}
                    {entry.type === 'system' && (
                      <div className="text-amber-400">--- {entry.text} ---</div>
                    )}
                  </div>
                ))
              )}
              {loading && (
                <div className="flex items-center gap-2 text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Executing...
                </div>
              )}
            </div>

            {/* Command Input */}
            <div className="flex gap-2 mt-4">
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-mono">$</span>
                <Input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={connected ? "Enter command..." : "Connect first..."}
                  disabled={!connected || loading}
                  className="pl-8 font-mono"
                  data-testid="ssh-command-input"
                />
              </div>
              <Button 
                onClick={handleExecute} 
                disabled={!connected || loading || !command.trim()}
                data-testid="ssh-execute-btn"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>

            {/* Quick Commands */}
            {connected && (
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-xs text-muted-foreground">Quick commands:</span>
                {['ls -la', 'df -h', 'free -m', 'top -bn1 | head -20', 'uptime', 'whoami', 'hostname', 'ip addr'].map(cmd => (
                  <Button
                    key={cmd}
                    variant="outline"
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => { setCommand(cmd); }}
                  >
                    {cmd}
                  </Button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
