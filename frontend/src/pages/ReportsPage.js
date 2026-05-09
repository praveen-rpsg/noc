import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { reportsApi } from '../services/api';
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
      const token = localStorage.getItem('noc_token');
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
      const token = localStorage.getItem('noc_token');
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

  const renderReportContent = (content) => {
    if (!content) return null;
    
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
                {renderReportContent(previewReport.content)}
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
