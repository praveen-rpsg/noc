import axios from 'axios';
import { getApiUrl, getBackendUrlSync, initConfig } from './config';
import { getAuthHeader } from './auth';

// Initialize API URL - will be updated after config loads
let API = `${getBackendUrlSync()}/api`;

// Function to reinitialize API after config loads
export const initializeApi = async () => {
  await initConfig();
  API = getApiUrl();
  return API;
};

// Helper to get current API URL
export const getAPI = () => API;

// Create axios instance that always uses current API URL and auth headers
const apiCall = (method, endpoint, options = {}) => {
  const url = `${API}${endpoint}`;
  const headers = { ...getAuthHeader(), ...options.headers };
  return axios({ method, url, headers, ...options });
};

// Devices API
export const devicesApi = {
  getAll: () => apiCall('get', '/devices'),
  getOne: (id) => apiCall('get', `/devices/${id}`),
  create: (data) => apiCall('post', '/devices', { data }),
  update: (id, data) => apiCall('put', `/devices/${id}`, { data }),
  delete: (id) => apiCall('delete', `/devices/${id}`),
};

// Alerts API
export const alertsApi = {
  getAll: (params) => apiCall('get', '/alerts', { params }),
  getOne: (id) => apiCall('get', `/alerts/${id}`),
  create: (data) => apiCall('post', '/alerts', { data }),
  acknowledge: (id) => apiCall('put', `/alerts/${id}/acknowledge`),
  resolve: (id) => apiCall('put', `/alerts/${id}/resolve`),
  aiTroubleshoot: (id) => apiCall('post', `/alerts/${id}/ai-troubleshoot`),
};

// Incidents API
export const incidentsApi = {
  getAll: (params) => apiCall('get', '/incidents', { params }),
  getOne: (id) => apiCall('get', `/incidents/${id}`),
  create: (data) => apiCall('post', '/incidents', { data }),
  update: (id, data) => apiCall('put', `/incidents/${id}`, { data }),
  getAiAnalysis: (id) => apiCall('post', `/incidents/${id}/ai-analysis`),
  aiTroubleshoot: (id) => apiCall('post', `/incidents/${id}/ai-troubleshoot`),
};

// Performance API
export const performanceApi = {
  getMetrics: (params) => apiCall('get', '/performance', { params }),
  createMetric: (data) => apiCall('post', '/performance', { data }),
};

// Assets API
export const assetsApi = {
  getAll: () => apiCall('get', '/assets'),
  getOne: (id) => apiCall('get', `/assets/${id}`),
  create: (data) => apiCall('post', '/assets', { data }),
  update: (id, data) => apiCall('put', `/assets/${id}`, { data }),
  delete: (id) => apiCall('delete', `/assets/${id}`),
};

// Reports API
export const reportsApi = {
  getAll: (params) => apiCall('get', '/reports', { params }),
  generate: (type, periodStart, periodEnd) => 
    apiCall('post', `/reports/generate?report_type=${type}&period_start=${periodStart}&period_end=${periodEnd}`),
};

// Config API
export const configApi = {
  getAll: (params) => apiCall('get', '/config', { params }),
  backup: (deviceId, configType, configData) => 
    apiCall('post', `/config/backup?device_id=${deviceId}&config_type=${configType}&config_data=${encodeURIComponent(configData)}`),
};

// SLA API
export const slaApi = {
  getAll: () => apiCall('get', '/sla'),
  getMetrics: () => apiCall('get', '/sla/metrics'),
};

// AI API
export const aiApi = {
  analyze: (context, query, incidentId) => 
    apiCall('post', '/ai/analyze', { data: { context, query, incident_id: incidentId } }),
  analyzeTraceroute: (target, output) => 
    apiCall('post', '/ai/traceroute-analysis', { data: { target, traceroute_output: output } }),
  analyzeLogs: (logs) => 
    apiCall('post', '/ai/log-analysis', { data: { logs } }),
};

// Dashboard API
export const dashboardApi = {
  getStats: () => apiCall('get', '/dashboard/stats'),
  getRecentAlerts: (limit = 10) => apiCall('get', `/dashboard/recent-alerts?limit=${limit}`),
  getRecentIncidents: (limit = 10) => apiCall('get', `/dashboard/recent-incidents?limit=${limit}`),
};

// Seed Demo Data
export const seedDemoData = () => apiCall('post', '/seed');

// Autonomous Agent Execution API
export const agentExecApi = {
  // Run agent on incident
  runOnIncident: (incidentId) => apiCall('post', `/agent-exec/run/${incidentId}`),
  
  // Get all executions
  getExecutions: (params) => apiCall('get', '/agent-exec/executions', { params }),
  
  // Get specific execution
  getExecution: (executionId) => apiCall('get', `/agent-exec/executions/${executionId}`),
  
  // Get pending actions requiring confirmation
  getPendingActions: () => apiCall('get', '/agent-exec/pending-actions'),
  
  // Get pending actions count
  getPendingCount: () => apiCall('get', '/agent-exec/pending-actions/count'),
  
  // Approve an action
  approveAction: (actionId) => apiCall('post', `/agent-exec/actions/${actionId}/approve`),
  
  // Reject an action
  rejectAction: (actionId, reason) => apiCall('post', `/agent-exec/actions/${actionId}/reject`, { params: { reason } }),
  
  // Get agent settings
  getSettings: () => apiCall('get', '/agent-exec/settings'),
  
  // Update agent settings
  updateSettings: (settings) => apiCall('put', '/agent-exec/settings', { data: settings }),
  
  // Get execution log for incident
  getExecutionLog: (incidentId) => apiCall('get', `/agent-exec/execution-log/${incidentId}`),
  
  // Network Diagnostics
  runPing: (target, count = 4, deviceId = null) => 
    apiCall('post', '/agent-exec/diagnostics/ping', { data: { target, count, device_id: deviceId } }),
  
  runTraceroute: (target, maxHops = 30, deviceId = null) => 
    apiCall('post', '/agent-exec/diagnostics/traceroute', { data: { target, max_hops: maxHops, device_id: deviceId } }),
  
  getDiagnosticsHistory: (params) => apiCall('get', '/agent-exec/diagnostics/history', { params }),
  
  // Routing Optimization
  getRoutingOptimization: () => apiCall('post', '/agent-exec/routing/optimize'),
  getRoutingHistory: (params) => apiCall('get', '/agent-exec/routing/history', { params }),
};
