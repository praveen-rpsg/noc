import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { reportsApi } from '../services/api';
import { getToken } from '../services/auth';
import { toast } from 'sonner';
import {
  FileText,
  Download,
  RefreshCw,
  Calendar,
  BarChart3,
  PieChart,
  TrendingUp,
  Loader2,
  FileDown,
  FileSpreadsheet,
  Eye
} from 'lucide-react';
import { format, subDays } from 'date-fns';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function ReportsPage() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedReportType, setSelectedReportType] = useState('daily_health');
  const [downloadingId, setDownloadingId] = useState(null);
  const [previewReport, setPreviewReport] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const fetchReports = async () => {
    try {
      const response = await reportsApi.getAll();
      setReports(response.data);
    } catch (error) {
      toast.error('Failed to fetch reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleGenerateReport = async () => {
    setGenerating(true);
    try {
      const periodEnd = format(new Date(), 'yyyy-MM-dd');
      const periodStart = format(subDays(new Date(), 7), 'yyyy-MM-dd');
      
      await reportsApi.generate(selectedReportType, periodStart, periodEnd);
      toast.success('Report generated successfully');
      fetchReports();
    } catch (error) {
      toast.error('Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPDF = async (reportId, reportTitle) => {
    setDownloadingId(reportId);
    try {
      const token = getToken();
      const response = await fetch(`${BACKEND_URL}/api/reports/${reportId}/download/pdf`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportTitle.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('PDF downloaded successfully');
    } catch (error) {
      toast.error('Failed to download PDF');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDownloadCSV = async (reportId, reportTitle) => {
    setDownloadingId(reportId);
    try {
      const token = getToken();
      const response = await fetch(`${BACKEND_URL}/api/reports/${reportId}/download/csv`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportTitle.replace(/\s+/g, '_')}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('CSV downloaded successfully');
    } catch (error) {
      toast.error('Failed to download CSV');
    } finally {
      setDownloadingId(null);
    }
  };

  const handlePreviewReport = (report) => {
    setPreviewReport(report);
    setPreviewOpen(true);
  };

  const reportTypes = [
    { value: 'daily_health', label: 'Daily Health Check', icon: BarChart3 },
    { value: 'incident_summary', label: 'Incident Summary', icon: FileText },
    { value: 'sla_compliance', label: 'SLA Compliance', icon: TrendingUp },
    { value: 'device_inventory', label: 'Device Inventory', icon: PieChart },
    { value: 'performance_metrics', label: 'Performance Metrics', icon: BarChart3 },
    { value: 'backup_status', label: 'Backup Status', icon: FileDown },
  ];

  const getReportIcon = (type) => {
    const found = reportTypes.find(r => r.value === type);
    const Icon = found?.icon || FileText;
    return <Icon className="h-5 w-5" />;
  };

  const renderReportContent = (content, reportType) => {
    if (!content) return null;
    
    // Enhanced Daily Health Report
    if (reportType === 'daily_health' && content.device_health) {
      return (
        <div className="space-y-6">
          {/* Summary Section */}
          {content.summary && (
            <div className="bg-slate-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-3">Health Summary</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{content.summary.total_devices}</div>
                  <div className="text-xs text-muted-foreground">Total Devices</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{content.summary.online_devices}</div>
                  <div className="text-xs text-muted-foreground">Online</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-red-600">{content.summary.critical_alerts}</div>
                  <div className="text-xs text-muted-foreground">Critical Alerts</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{content.summary.health_score}%</div>
                  <div className="text-xs text-muted-foreground">Health Score</div>
                </div>
              </div>
            </div>
          )}
          
          {/* Device Health Table */}
          <div>
            <h4 className="font-semibold mb-3">Device Health Details</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="text-left p-2">Device</th>
                    <th className="text-left p-2">IP Address</th>
                    <th className="text-center p-2">CPU %</th>
                    <th className="text-center p-2">Memory %</th>
                    <th className="text-center p-2">Traffic In/Out</th>
                    <th className="text-center p-2">Interfaces (Up/Total)</th>
                    <th className="text-center p-2">Free Ports</th>
                    <th className="text-center p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {content.device_health?.slice(0, 10).map((device, idx) => (
                    <tr key={device.device_name || idx} className="border-b">
                      <td className="p-2 font-medium">{device.device_name}</td>
                      <td className="p-2">{device.ip_address}</td>
                      <td className={`p-2 text-center ${device.cpu_status === 'Critical' ? 'text-red-600 font-bold' : device.cpu_status === 'Warning' ? 'text-amber-600' : ''}`}>
                        {device.cpu_usage_percent}%
                      </td>
                      <td className={`p-2 text-center ${device.memory_status === 'Critical' ? 'text-red-600 font-bold' : device.memory_status === 'Warning' ? 'text-amber-600' : ''}`}>
                        {device.memory_usage_percent}%
                      </td>
                      <td className="p-2 text-center">{device.traffic_in_mbps}/{device.traffic_out_mbps} Mbps</td>
                      <td className="p-2 text-center">{device.interfaces_up}/{device.total_interfaces}</td>
                      <td className="p-2 text-center text-green-600">{device.free_interfaces}</td>
                      <td className="p-2 text-center">
                        <Badge className={device.status === 'online' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                          {device.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          
          {/* Recommendations */}
          {content.recommendations?.length > 0 && (
            <div className="bg-amber-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-2 text-amber-800">Recommendations</h4>
              <ul className="list-disc list-inside text-sm text-amber-700 space-y-1">
                {content.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    }
    
    // Enhanced Incident Report
    if (reportType === 'incident_summary' && content.incidents) {
      return (
        <div className="space-y-6">
          {/* Summary */}
          {content.summary && (
            <div className="bg-slate-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-3">Incident Summary</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{content.summary.total_incidents}</div>
                  <div className="text-xs text-muted-foreground">Total Incidents</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-amber-600">{content.summary.open_incidents}</div>
                  <div className="text-xs text-muted-foreground">Open</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-red-600">{content.summary.hardware_issues}</div>
                  <div className="text-xs text-muted-foreground">Hardware Issues</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{content.summary.potential_ios_bugs}</div>
                  <div className="text-xs text-muted-foreground">Potential Bugs</div>
                </div>
              </div>
            </div>
          )}
          
          {/* Incidents Table */}
          <div>
            <h4 className="font-semibold mb-3">Incident Details</h4>
            <div className="space-y-4">
              {content.incidents?.slice(0, 10).map((incident, idx) => (
                <div key={incident.incident_id || idx} className="border rounded-lg p-4 bg-white">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="font-semibold">{incident.title}</span>
                      <Badge className={`ml-2 ${incident.priority === 'P1' ? 'bg-red-500' : incident.priority === 'P2' ? 'bg-orange-500' : 'bg-blue-500'}`}>
                        {incident.priority}
                      </Badge>
                    </div>
                    <Badge variant="outline">{incident.status}</Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm mb-3">
                    <div><span className="text-muted-foreground">Date:</span> {incident.incident_date}</div>
                    <div><span className="text-muted-foreground">Time:</span> {incident.incident_time}</div>
                    <div><span className="text-muted-foreground">IP:</span> {incident.ip_address}</div>
                    <div><span className="text-muted-foreground">Device:</span> {incident.device_name}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded text-sm mb-2">
                    <div className="font-medium mb-1">Fault Details:</div>
                    <p className="text-muted-foreground">{incident.fault_details}</p>
                  </div>
                  <div className="bg-blue-50 p-3 rounded text-sm mb-2">
                    <div className="font-medium mb-1 text-blue-800">Suggested RCA:</div>
                    <p className="text-blue-700">{incident.suggested_rca}</p>
                  </div>
                  <div className="flex gap-4 text-sm">
                    <div><span className="text-muted-foreground">Hardware Replacement:</span> <span className={incident.hardware_replacement_required === 'Possible' ? 'text-amber-600 font-medium' : ''}>{incident.hardware_replacement_required}</span></div>
                    <div><span className="text-muted-foreground">IOS Bug:</span> <span className={incident.ios_bug_report !== 'N/A' ? 'text-purple-600 font-medium' : ''}>{incident.ios_bug_report}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }
    
    // Enhanced Device Inventory Report
    if (reportType === 'device_inventory' && content.inventory) {
      return (
        <div className="space-y-6">
          {/* Summary */}
          {content.summary && (
            <div className="bg-slate-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-3">Inventory Summary</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{content.summary.total_assets}</div>
                  <div className="text-xs text-muted-foreground">Total Assets</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{content.summary.active_assets}</div>
                  <div className="text-xs text-muted-foreground">Active</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-red-600">{content.summary.warranty_expired}</div>
                  <div className="text-xs text-muted-foreground">Warranty Expired</div>
                </div>
                <div className="text-center p-3 bg-white rounded-lg">
                  <div className="text-2xl font-bold text-amber-600">{content.summary.warranty_expiring_soon}</div>
                  <div className="text-xs text-muted-foreground">Expiring Soon</div>
                </div>
              </div>
            </div>
          )}
          
          {/* Inventory Table */}
          <div>
            <h4 className="font-semibold mb-3">Asset Inventory</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="text-left p-2">Asset Tag</th>
                    <th className="text-left p-2">Name</th>
                    <th className="text-left p-2">IP Address</th>
                    <th className="text-left p-2">Model</th>
                    <th className="text-left p-2">OEM</th>
                    <th className="text-left p-2">Location</th>
                    <th className="text-center p-2">Warranty</th>
                  </tr>
                </thead>
                <tbody>
                  {content.inventory?.slice(0, 15).map((item, idx) => (
                    <tr key={item.asset_id || idx} className="border-b">
                      <td className="p-2 font-mono text-xs">{item.asset_tag}</td>
                      <td className="p-2 font-medium">{item.name}</td>
                      <td className="p-2">{item.ip_address}</td>
                      <td className="p-2">{item.model}</td>
                      <td className="p-2">{item.oem_vendor}</td>
                      <td className="p-2">{item.location}</td>
                      <td className="p-2 text-center">
                        <Badge className={
                          item.warranty_status === 'Active' ? 'bg-green-100 text-green-700' :
                          item.warranty_status === 'Expiring Soon' ? 'bg-amber-100 text-amber-700' :
                          item.warranty_status === 'Expired' ? 'bg-red-100 text-red-700' :
                          'bg-slate-100 text-slate-700'
                        }>
                          {item.warranty_status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          
          {/* Warranty Alerts */}
          {content.warranty_alerts?.length > 0 && (
            <div className="bg-red-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-2 text-red-800">Warranty Alerts ({content.warranty_alerts.length} assets)</h4>
              <ul className="text-sm text-red-700 space-y-1">
                {content.warranty_alerts.slice(0, 5).map((item, idx) => (
                  <li key={idx}>• {item.name} ({item.asset_tag}) - {item.warranty_status}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    }
    
    // Default rendering for other report types
    return (
      <div className="space-y-4">
        {Object.entries(content).map(([key, value]) => (
          <div key={key} className="border-b pb-3">
            <h4 className="font-medium text-sm text-muted-foreground capitalize mb-2">
              {key.replace(/_/g, ' ')}
            </h4>
            {typeof value === 'object' ? (
              Array.isArray(value) ? (
                <ul className="list-disc list-inside text-sm space-y-1">
                  {value.map((item, idx) => (
                    <li key={typeof item === 'object' && item.id ? item.id : `${key}-item-${idx}`}>{typeof item === 'object' ? JSON.stringify(item) : item}</li>
                  ))}
                </ul>
              ) : (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {Object.entries(value).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground capitalize">{k.replace(/_/g, ' ')}:</span>
                      <span className="font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )
            ) : (
              <p className="text-sm">{String(value)}</p>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div data-testid="reports-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope']">Reports</h1>
          <p className="text-muted-foreground mt-1">Generate, view, and download operational reports</p>
        </div>
        <Button variant="outline" onClick={fetchReports}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Report Generator */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Generate Report</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">Report Type</label>
              <Select value={selectedReportType} onValueChange={setSelectedReportType}>
                <SelectTrigger data-testid="report-type-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {reportTypes.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      <div className="flex items-center gap-2">
                        <type.icon className="h-4 w-4" />
                        {type.label}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button 
              onClick={handleGenerateReport} 
              disabled={generating}
              data-testid="generate-report-btn"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  Generate Report
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Report Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-500">
                <BarChart3 className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-blue-700">Daily Health</p>
                <p className="text-2xl font-bold text-blue-900">
                  {reports.filter(r => r.type === 'daily_health').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-purple-500">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-purple-700">Incident Summary</p>
                <p className="text-2xl font-bold text-purple-900">
                  {reports.filter(r => r.type === 'incident_summary').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-500">
                <TrendingUp className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-green-700">SLA Compliance</p>
                <p className="text-2xl font-bold text-green-900">
                  {reports.filter(r => r.type === 'sla_compliance').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Reports Table */}
      <Card className="bg-white border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Generated Reports</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[400px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Report</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Generated By</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : reports.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">
                      No reports generated yet
                    </TableCell>
                  </TableRow>
                ) : (
                  reports.map((report) => (
                    <TableRow key={report.id} className="table-row-hover" data-testid={`report-row-${report.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-muted">
                            {getReportIcon(report.type)}
                          </div>
                          <span className="font-medium">{report.title}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {report.type.replace('_', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {report.period_start} - {report.period_end}
                      </TableCell>
                      <TableCell>{report.generated_by}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {format(new Date(report.created_at), 'MMM d, HH:mm')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handlePreviewReport(report)}
                            title="Preview Report"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handleDownloadPDF(report.id, report.title)}
                            disabled={downloadingId === report.id}
                            title="Download PDF"
                          >
                            {downloadingId === report.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <FileDown className="h-4 w-4 text-red-500" />
                            )}
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handleDownloadCSV(report.id, report.title)}
                            disabled={downloadingId === report.id}
                            title="Download CSV"
                          >
                            <FileSpreadsheet className="h-4 w-4 text-green-500" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Report Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {previewReport && getReportIcon(previewReport.type)}
              {previewReport?.title}
            </DialogTitle>
          </DialogHeader>
          {previewReport && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>Type: <Badge variant="outline" className="capitalize ml-1">{previewReport.type.replace('_', ' ')}</Badge></span>
                <span>Period: {previewReport.period_start} - {previewReport.period_end}</span>
              </div>
              <div className="border rounded-lg p-4 bg-muted/30">
                {renderReportContent(previewReport.content, previewReport.type)}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewOpen(false)}>Close</Button>
            <Button onClick={() => handleDownloadPDF(previewReport?.id, previewReport?.title)}>
              <FileDown className="h-4 w-4 mr-2" />
              Download PDF
            </Button>
            <Button variant="secondary" onClick={() => handleDownloadCSV(previewReport?.id, previewReport?.title)}>
              <FileSpreadsheet className="h-4 w-4 mr-2" />
              Download CSV
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
