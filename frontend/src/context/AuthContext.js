import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { initConfig, getApiUrl, getBackendUrlSync } from '../services/config';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('noc_token'));
  const [loading, setLoading] = useState(true);
  const [apiReady, setApiReady] = useState(false);
  
  // Initialize config and API URL
  useEffect(() => {
    const init = async () => {
      await initConfig();
      setApiReady(true);
    };
    init();
  }, []);

  const fetchUser = useCallback(async () => {
    try {
      const API = getApiUrl();
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      logout();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!apiReady) return;
    
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token, apiReady, fetchUser]);

  const login = async (email, password) => {
    const API = getApiUrl();
    const response = await axios.post(`${API}/auth/login`, { email, password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('noc_token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const register = async (email, password, name, role = 'operator') => {
    const API = getApiUrl();
    const response = await axios.post(`${API}/auth/register`, { email, password, name, role });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('noc_token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('noc_token');
    delete axios.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading: loading || !apiReady }}>
      {children}
    </AuthContext.Provider>
  );
};
