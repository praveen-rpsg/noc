import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Progress } from '../components/ui/progress';
import { slaApi } from '../services/api';
import { toast } from 'sonner';
import {
  Target,
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from 'recharts';

const SLAStatusBadge = ({ met }) => {
  if (met === null || met === undefined) {
    return <Badge variant="outline" className="bg-slate-50 text-slate-700">Pending</Badge>;
  }
  return met ? (
    <Badge className="bg-green-50 text-green-700 border-green-200">
      <CheckCircle className="h-3 w-3 mr-1" />
      Met
    </Badge>
  ) : (
    <Badge className="bg-red-50 text-red-700 border-red-200">
      <XCircle className="h-3 w-3 mr-1" />
      Breached
    </Badge>
  );
};

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

export default function SLAPage() {
  const [records, setRecords] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [recordsRes, metricsRes] = await Promise.all([
        slaApi.getAll(),
        slaApi.getMetrics(),
      ]);
      setRecords(recordsRes.data);
      setMetrics(metricsRes.data);
    } catch (error) {
      toast.error('Failed to fetch SLA data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const pieData = metrics ? [
    { name: 'Met', value: metrics.response_sla_compliance, color: '#22c55e' },
    { name: 'Breached', value: 100 - metrics.response_sla_compliance, color: '#ef4444' },
  ] : [];

  const slaTargets = [
    { priority: 'P1', response: 15, resolution: 60 },
    { priority: 'P2', response: 30, resolution: 240 },
    { priority: 'P3', response: 60, resolution: 480 },
    { priority: 'P4', response: 120, resolution: 1440 },
  ];

  return (
    <div data-testid="sla-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">SLA Management</h1>
          <p className="text-muted-foreground mt-1">Track Service Level Agreement compliance</p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-50">
              <Target className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{metrics?.total_tracked || 0}</p>
              <p className="text-sm text-muted-foreground">Total Tracked</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-50">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{metrics?.response_sla_compliance?.toFixed(1) || 0}%</p>
              <p className="text-sm text-muted-foreground">Response SLA</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-purple-50">
              <Clock className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-600">{metrics?.resolution_sla_compliance?.toFixed(1) || 0}%</p>
              <p className="text-sm text-muted-foreground">Resolution SLA</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white border-border/50">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 rounded-xl bg-amber-50">
              <TrendingUp className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-600">{metrics?.overall_compliance?.toFixed(1) || 0}%</p>
              <p className="text-sm text-muted-foreground">Overall Compliance</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SLA Compliance Chart */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Response SLA Compliance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] flex items-center justify-center">
              {loading ? (
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={2}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        {/* SLA Targets */}
        <Card className="bg-white border-border/50">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">SLA Targets by Priority</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {slaTargets.map((target) => (
                <div key={target.priority} className="flex items-center gap-4">
                  <PriorityBadge priority={target.priority} />
                  <div className="flex-1 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Response: </span>
                      <span className="font-medium">{target.response} min</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Resolution: </span>
                      <span className="font-medium">{target.resolution > 60 ? `${Math.round(target.resolution / 60)}h` : `${target.resolution} min`}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SLA Records Table */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">SLA Tracking Records</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[400px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Incident</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Response Target</TableHead>
                  <TableHead>Actual Response</TableHead>
                  <TableHead>Response SLA</TableHead>
                  <TableHead>Resolution Target</TableHead>
                  <TableHead>Actual Resolution</TableHead>
                  <TableHead>Resolution SLA</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : records.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-10 text-muted-foreground">
                      No SLA records yet
                    </TableCell>
                  </TableRow>
                ) : (
                  records.map((record) => (
                    <TableRow key={record.id} className="table-row-hover" data-testid={`sla-row-${record.id}`}>
                      <TableCell className="font-mono text-sm">{record.incident_id.slice(0, 8)}...</TableCell>
                      <TableCell><PriorityBadge priority={record.priority} /></TableCell>
                      <TableCell>{record.response_time_target_mins} min</TableCell>
                      <TableCell>
                        {record.actual_response_time_mins !== null ? `${record.actual_response_time_mins} min` : '-'}
                      </TableCell>
                      <TableCell><SLAStatusBadge met={record.response_sla_met} /></TableCell>
                      <TableCell>{record.resolution_time_target_mins > 60 ? `${Math.round(record.resolution_time_target_mins / 60)}h` : `${record.resolution_time_target_mins} min`}</TableCell>
                      <TableCell>
                        {record.actual_resolution_time_mins !== null ? `${record.actual_resolution_time_mins} min` : '-'}
                      </TableCell>
                      <TableCell><SLAStatusBadge met={record.resolution_sla_met} /></TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
