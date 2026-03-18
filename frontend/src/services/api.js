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
  create: (data) => axios.post(`${API}/alerts`, data),
  acknowledge: (id) => axios.put(`${API}/alerts/${id}/acknowledge`),
  resolve: (id) => axios.put(`${API}/alerts/${id}/resolve`),
};

// Incidents API
export const incidentsApi = {
  getAll: (params) => axios.get(`${API}/incidents`, { params }),
  getOne: (id) => axios.get(`${API}/incidents/${id}`),
  create: (data) => axios.post(`${API}/incidents`, data),
  update: (id, data) => axios.put(`${API}/incidents/${id}`, data),
  getAiAnalysis: (id) => axios.post(`${API}/incidents/${id}/ai-analysis`),
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
