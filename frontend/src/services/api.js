import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Devices API
export const devicesApi = {
  getAll: () => axios.get(`${API}/devices`),
  getOne: (id) => axios.get(`${API}/devices/${id}`),
  create: (data) => axios.post(`${API}/devices`, data),
  update: (id, data) => axios.put(`${API}/devices/${id}`, data),
  delete: (id) => axios.delete(`${API}/devices/${id}`),
};

// Alerts API
export const alertsApi = {
  getAll: (params) => axios.get(`${API}/alerts`, { params }),
  getOne: (id) => axios.get(`${API}/alerts/${id}`),
  create: (data) => axios.post(`${API}/alerts`, data),
  acknowledge: (id) => axios.put(`${API}/alerts/${id}/acknowledge`),
  resolve: (id) => axios.put(`${API}/alerts/${id}/resolve`),
  aiTroubleshoot: (id) => axios.post(`${API}/alerts/${id}/ai-troubleshoot`),
};

// Incidents API
export const incidentsApi = {
  getAll: (params) => axios.get(`${API}/incidents`, { params }),
  getOne: (id) => axios.get(`${API}/incidents/${id}`),
  create: (data) => axios.post(`${API}/incidents`, data),
  update: (id, data) => axios.put(`${API}/incidents/${id}`, data),
  getAiAnalysis: (id) => axios.post(`${API}/incidents/${id}/ai-analysis`),
  aiTroubleshoot: (id) => axios.post(`${API}/incidents/${id}/ai-troubleshoot`),
};

// Performance API
export const performanceApi = {
  getMetrics: (params) => axios.get(`${API}/performance`, { params }),
  createMetric: (data) => axios.post(`${API}/performance`, data),
};

// Assets API
export const assetsApi = {
  getAll: () => axios.get(`${API}/assets`),
  getOne: (id) => axios.get(`${API}/assets/${id}`),
  create: (data) => axios.post(`${API}/assets`, data),
  update: (id, data) => axios.put(`${API}/assets/${id}`, data),
  delete: (id) => axios.delete(`${API}/assets/${id}`),
};

// Reports API
export const reportsApi = {
  getAll: (params) => axios.get(`${API}/reports`, { params }),
  generate: (type, periodStart, periodEnd) => 
    axios.post(`${API}/reports/generate?report_type=${type}&period_start=${periodStart}&period_end=${periodEnd}`),
};

// Config API
export const configApi = {
  getAll: (params) => axios.get(`${API}/config`, { params }),
  backup: (deviceId, configType, configData) => 
    axios.post(`${API}/config/backup?device_id=${deviceId}&config_type=${configType}&config_data=${encodeURIComponent(configData)}`),
};

// SLA API
export const slaApi = {
  getAll: () => axios.get(`${API}/sla`),
  getMetrics: () => axios.get(`${API}/sla/metrics`),
};

// AI API
export const aiApi = {
  analyze: (context, query, incidentId) => 
    axios.post(`${API}/ai/analyze`, { context, query, incident_id: incidentId }),
  analyzeTraceroute: (target, output) => 
    axios.post(`${API}/ai/traceroute-analysis`, { target, traceroute_output: output }),
  analyzeLogs: (logs) => 
    axios.post(`${API}/ai/log-analysis`, { logs }),
};

// Dashboard API
export const dashboardApi = {
  getStats: () => axios.get(`${API}/dashboard/stats`),
  getRecentAlerts: (limit = 10) => axios.get(`${API}/dashboard/recent-alerts?limit=${limit}`),
  getRecentIncidents: (limit = 10) => axios.get(`${API}/dashboard/recent-incidents?limit=${limit}`),
};

// Seed Demo Data
export const seedDemoData = () => axios.post(`${API}/seed`);

// Autonomous Agent Execution API
export const agentExecApi = {
  // Run agent on incident
  runOnIncident: (incidentId) => axios.post(`${API}/agent-exec/run/${incidentId}`),
  
  // Get all executions
  getExecutions: (params) => axios.get(`${API}/agent-exec/executions`, { params }),
  
  // Get specific execution
  getExecution: (executionId) => axios.get(`${API}/agent-exec/executions/${executionId}`),
  
  // Get pending actions requiring confirmation
  getPendingActions: () => axios.get(`${API}/agent-exec/pending-actions`),
  
  // Get pending actions count
  getPendingCount: () => axios.get(`${API}/agent-exec/pending-actions/count`),
  
  // Approve an action
  approveAction: (actionId) => axios.post(`${API}/agent-exec/actions/${actionId}/approve`),
  
  // Reject an action
  rejectAction: (actionId, reason) => axios.post(`${API}/agent-exec/actions/${actionId}/reject`, null, { params: { reason } }),
  
  // Get agent settings
  getSettings: () => axios.get(`${API}/agent-exec/settings`),
  
  // Update agent settings
  updateSettings: (settings) => axios.put(`${API}/agent-exec/settings`, settings),
  
  // Get execution log for incident
  getExecutionLog: (incidentId) => axios.get(`${API}/agent-exec/execution-log/${incidentId}`),
  
  // Network Diagnostics
  runPing: (target, count = 4, deviceId = null) => 
    axios.post(`${API}/agent-exec/diagnostics/ping`, { target, count, device_id: deviceId }),
  
  runTraceroute: (target, maxHops = 30, deviceId = null) => 
    axios.post(`${API}/agent-exec/diagnostics/traceroute`, { target, max_hops: maxHops, device_id: deviceId }),
  
  getDiagnosticsHistory: (params) => axios.get(`${API}/agent-exec/diagnostics/history`, { params }),
};
