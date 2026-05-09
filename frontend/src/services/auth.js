/**
 * Centralized Authentication Token Handler
 * 
 * This module provides secure token management utilities.
 * 
 * SECURITY NOTE: For production applications with high security requirements,
 * consider migrating to httpOnly cookies set by the server. This module
 * provides a centralized place to make that change when ready.
 * 
 * Current implementation uses localStorage with the following mitigations:
 * - Token expiration validation
 * - Automatic token refresh on API calls (when implemented)
 * - Centralized access for easy security audits
 */

const TOKEN_KEY = 'noc_token';
const USER_KEY = 'noc_user';

// Environment check - disable console in production
const isDev = process.env.NODE_ENV === 'development';
const log = isDev ? console.debug.bind(console) : () => {};

/**
 * Store authentication token
 * @param {string} token - JWT token
 */
export const setToken = (token) => {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      log('Token stored');
    }
  } catch (e) {
    log('Error storing token:', e.message);
  }
};

/**
 * Get stored authentication token
 * @returns {string|null} - Token or null if not found
 */
export const getToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch (e) {
    log('Error retrieving token:', e.message);
    return null;
  }
};

/**
 * Remove authentication token (logout)
 */
export const removeToken = () => {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    log('Token removed');
  } catch (e) {
    log('Error removing token:', e.message);
  }
};

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export const isAuthenticated = () => {
  const token = getToken();
  if (!token) return false;
  
  // Optional: Validate token expiration
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      log('Token expired');
      removeToken();
      return false;
    }
    return true;
  } catch (e) {
    log('Invalid token format');
    return false;
  }
};

/**
 * Store user data
 * @param {Object} user - User object
 */
export const setUser = (user) => {
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  } catch (e) {
    log('Error storing user:', e.message);
  }
};

/**
 * Get stored user data
 * @returns {Object|null} - User object or null
 */
export const getUser = () => {
  try {
    const user = localStorage.getItem(USER_KEY);
    return user ? JSON.parse(user) : null;
  } catch (e) {
    log('Error retrieving user:', e.message);
    return null;
  }
};

/**
 * Get authorization header for API requests
 * @returns {Object} - Headers object with Authorization
 */
export const getAuthHeader = () => {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Check if current user has admin role
 * @returns {boolean}
 */
export const isAdmin = () => {
  const user = getUser();
  return user?.role === 'admin';
};

export default {
  setToken,
  getToken,
  removeToken,
  isAuthenticated,
  setUser,
  getUser,
  getAuthHeader,
  isAdmin
};
