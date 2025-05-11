import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { extractErrorMessage } from '../utils/errorHandler';

const AuthContext = createContext(null);

// Create axios instance with base configuration
const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true
});

// Add request interceptor to add token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));

  const checkToken = async (token) => {
    console.log('Checking token validity...');
    try {
      const response = await api.get('/users/me', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      console.log('User data received:', response.data);
      setUser(response.data);
      setIsAuthenticated(true);
      return true;
    } catch (error) {
      console.error('Token validation failed:', error);
      localStorage.removeItem('token');
      setToken(null);
      setIsAuthenticated(false);
      setUser(null);
      return false;
    }
  };

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    console.log('Initial token check:', storedToken ? 'Token exists' : 'No token');
    
    if (storedToken) {
      setToken(storedToken);
      checkToken(storedToken)
        .then(isValid => {
          console.log('Token validation result:', isValid ? 'Valid' : 'Invalid');
          setLoading(false);
        })
        .catch(error => {
          console.error('Token validation error:', error);
          setLoading(false);
        });
    } else {
      console.log('No token found, setting loading to false');
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    console.log('Attempting login...');
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token } = response.data;
      console.log('Login successful, token received');
      localStorage.setItem('token', access_token);
      setToken(access_token);
      
      // Get user info after successful login
      const userResponse = await api.get('/users/me', {
        headers: {
          Authorization: `Bearer ${access_token}`
        }
      });
      console.log('User data received after login:', userResponse.data);
      setUser(userResponse.data);
      setIsAuthenticated(true);
      return true;
    } catch (error) {
      console.error('Login error:', error);
      throw new Error(extractErrorMessage(error));
    }
  };

  const register = async (email, password) => {
    try {
      const response = await api.post('/register', {
        email,
        password,
      });
      const { access_token } = response.data;
      localStorage.setItem('token', access_token);
      setToken(access_token);
      
      // Get user info after successful registration
      const userResponse = await api.get('/users/me', {
        headers: {
          Authorization: `Bearer ${access_token}`
        }
      });
      setUser(userResponse.data);
      setIsAuthenticated(true);
      return true;
    } catch (error) {
      console.error('Registration error:', error);
      throw new Error(extractErrorMessage(error));
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setIsAuthenticated(false);
    setUser(null);
  };

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
    api,
    token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}; 