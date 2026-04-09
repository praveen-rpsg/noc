// Configuration service for handling backend URL
// Works in both browser and Electron environments

// Check if running in Electron
const isElectron = () => {
  return window.electronAPI?.isElectron === true;
};

// Default backend URL from environment or fallback
const DEFAULT_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Local storage key for browser-based config
const CONFIG_STORAGE_KEY = 'noc_config';

// Get stored config from localStorage (for browser mode)
const getStoredConfig = () => {
  try {
    const stored = localStorage.getItem(CONFIG_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Error reading stored config:', e);
  }
  return null;
};

// Save config to localStorage (for browser mode)
const saveStoredConfig = (config) => {
  try {
    localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config));
  } catch (e) {
    console.error('Error saving config:', e);
  }
};

// Get the backend URL
export const getBackendUrl = async () => {
  if (isElectron()) {
    try {
      const url = await window.electronAPI.getBackendUrl();
      return url || DEFAULT_BACKEND_URL;
    } catch (e) {
      console.error('Error getting backend URL from Electron:', e);
      return DEFAULT_BACKEND_URL;
    }
  }
  
  // Browser mode - use environment variable or stored config
  const stored = getStoredConfig();
  return stored?.backendUrl || DEFAULT_BACKEND_URL;
};

// Set the backend URL
export const setBackendUrl = async (url) => {
  if (isElectron()) {
    try {
      await window.electronAPI.setBackendUrl(url);
      return true;
    } catch (e) {
      console.error('Error setting backend URL in Electron:', e);
      return false;
    }
  }
  
  // Browser mode - save to localStorage
  const stored = getStoredConfig() || {};
  stored.backendUrl = url;
  saveStoredConfig(stored);
  return true;
};

// Get backend URL synchronously (uses cached value or default)
let cachedBackendUrl = DEFAULT_BACKEND_URL;

export const getBackendUrlSync = () => {
  return cachedBackendUrl;
};

// Initialize the config - call this on app startup
export const initConfig = async () => {
  cachedBackendUrl = await getBackendUrl();
  return cachedBackendUrl;
};

// Get the API base URL
export const getApiUrl = () => {
  return `${cachedBackendUrl}/api`;
};

// Check if we're in Electron
export { isElectron };

// Test backend connectivity
export const testBackendConnection = async (url) => {
  try {
    const response = await fetch(`${url}/api/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(5000)
    });
    return response.ok;
  } catch (e) {
    console.error('Backend connection test failed:', e);
    return false;
  }
};
