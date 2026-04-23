import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { performanceApi, devicesApi } from '../services/api';
import { toast } from 'sonner';
import {
  Activity,
  Cpu,
  HardDrive,
  Wifi,
  RefreshCw,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts';
import { format } from 'date-fns';

const MetricCard = ({ title, value, unit, icon: Icon, trend, color = 'blue' }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <Card className="bg-white border-border/50">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
          {trend && (
            <div className={`flex items-center gap-1 text-sm ${trend > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {trend > 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              <span>{Math.abs(trend)}%</span>
            </div>
          )}
        </div>
        <div className="mt-3">
          <p className="text-2xl font-bold">{value}<span className="text-sm font-normal text-muted-foreground ml-1">{unit}</span></p>
          <p className="text-sm text-muted-foreground">{title}</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default function PerformancePage() {
  const [metrics, setMetrics] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDevice, setSelectedDevice] = useState('all');
  const [timeRange, setTimeRange] = useState('24');

  const fetchData = useCallback(async () => {
    try {
      const params = { hours: parseInt(timeRange) };
      if (selectedDevice !== 'all') params.device_id = selectedDevice;
      
      const [metricsRes, devicesRes] = await Promise.all([
        performanceApi.getMetrics(params),
        devicesApi.getAll(),
      ]);
      setMetrics(metricsRes.data);
      setDevices(devicesRes.data);
    } catch (error) {
      toast.error('Failed to fetch performance data');
    } finally {
      setLoading(false);
    }
  }, [selectedDevice, timeRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Process metrics for charts
  const chartData = metrics.slice(0, 100).reverse().map((m) => ({
    time: format(new Date(m.timestamp), 'HH:mm'),
    cpu: m.cpu_usage,
    memory: m.memory_usage,
    disk: m.disk_usage,
    bandwidth_in: m.bandwidth_in,
    bandwidth_out: m.bandwidth_out,
    latency: m.latency_ms,
  }));

  // Calculate averages
  const avgCpu = metrics.length > 0 
    ? (metrics.reduce((sum, m) => sum + m.cpu_usage, 0) / metrics.length).toFixed(1)
    : 0;
  const avgMemory = metrics.length > 0 
    ? (metrics.reduce((sum, m) => sum + m.memory_usage, 0) / metrics.length).toFixed(1)
    : 0;
  const avgDisk = metrics.length > 0 
    ? (metrics.reduce((sum, m) => sum + m.disk_usage, 0) / metrics.length).toFixed(1)
    : 0;
  const avgLatency = metrics.length > 0 
    ? (metrics.reduce((sum, m) => sum + m.latency_ms, 0) / metrics.length).toFixed(1)
    : 0;
  const totalBandwidth = metrics.length > 0 
    ? ((metrics.reduce((sum, m) => sum + m.bandwidth_in + m.bandwidth_out, 0)) / 1000).toFixed(1)
    : 0;

  return (
    <div data-testid="performance-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Performance Monitoring</h1>
          <p className="text-muted-foreground mt-1">System and network performance metrics</p>
        </div>
        <div className="flex gap-3">
          <Select value={selectedDevice} onValueChange={setSelectedDevice}>
            <SelectTrigger className="w-[200px]" data-testid="device-select">
              <SelectValue placeholder="Select Device" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Devices</SelectItem>
              {devices.map((device) => (
                <SelectItem key={device.id} value={device.id}>{device.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-[150px]" data-testid="time-range-select">
              <SelectValue placeholder="Time Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Last Hour</SelectItem>
              <SelectItem value="6">Last 6 Hours</SelectItem>
              <SelectItem value="24">Last 24 Hours</SelectItem>
              <SelectItem value="168">Last 7 Days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <MetricCard title="Avg CPU Usage" value={avgCpu} unit="%" icon={Cpu} color="blue" />
        <MetricCard title="Avg Memory Usage" value={avgMemory} unit="%" icon={Activity} color="green" />
        <MetricCard title="Avg Disk Usage" value={avgDisk} unit="%" icon={HardDrive} color="amber" />
        <MetricCard title="Avg Latency" value={avgLatency} unit="ms" icon={Activity} color="purple" />
        <MetricCard title="Total Bandwidth" value={totalBandwidth} unit="GB" icon={Wifi} color="blue" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU & Memory Chart */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">CPU & Memory Utilization</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" domain={[0, 100]} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#fff', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }} 
                    />
                    <Area 
                      type="monotone" 
                      dataKey="cpu" 
                      stroke="#3b82f6" 
                      fill="#3b82f6" 
                      fillOpacity={0.2}
                      name="CPU %"
                    />
                    <Area 
                      type="monotone" 
                      dataKey="memory" 
                      stroke="#22c55e" 
                      fill="#22c55e" 
                      fillOpacity={0.2}
                      name="Memory %"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Disk Usage Chart */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Disk Utilization</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" domain={[0, 100]} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#fff', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }} 
                    />
                    <Line 
                      type="monotone" 
                      dataKey="disk" 
                      stroke="#f59e0b" 
                      strokeWidth={2}
                      dot={false}
                      name="Disk %"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Bandwidth Chart */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Network Bandwidth</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#fff', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }} 
                    />
                    <Bar dataKey="bandwidth_in" fill="#3b82f6" name="Inbound (Mbps)" />
                    <Bar dataKey="bandwidth_out" fill="#22c55e" name="Outbound (Mbps)" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Latency Chart */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Network Latency</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: '#fff', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }} 
                    />
                    <Line 
                      type="monotone" 
                      dataKey="latency" 
                      stroke="#8b5cf6" 
                      strokeWidth={2}
                      dot={false}
                      name="Latency (ms)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
