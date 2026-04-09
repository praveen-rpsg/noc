import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Server, Shield, AlertTriangle, Settings, Wifi, WifiOff, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { getBackendUrlSync, setBackendUrl, testBackendConnection, isElectron, initConfig } from '../services/config';
import { initializeApi } from '../services/api';

const AMEYA_LOGO_URL = "https://customer-assets.emergentagent.com/job_network-ops-ai/artifacts/vjap12f5_Atechlogo.jpeg";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  
  // Connection settings state
  const [showConnectionDialog, setShowConnectionDialog] = useState(false);
  const [backendUrl, setBackendUrlState] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [savingConnection, setSavingConnection] = useState(false);

  // Initialize backend URL
  useEffect(() => {
    const init = async () => {
      await initConfig();
      setBackendUrlState(getBackendUrlSync());
    };
    init();
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(loginForm.email, loginForm.password);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Login failed';
      // Check if it's a network error
      if (err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')) {
        setError('Cannot connect to server. Click the gear icon to configure backend URL.');
      } else {
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    
    if (registerForm.password !== registerForm.confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    setLoading(true);
    try {
      await register(registerForm.email, registerForm.password, registerForm.name);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Registration failed';
      if (err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')) {
        setError('Cannot connect to server. Click the gear icon to configure backend URL.');
      } else {
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);
    try {
      const isConnected = await testBackendConnection(backendUrl);
      setConnectionStatus(isConnected ? 'connected' : 'failed');
    } catch (error) {
      setConnectionStatus('failed');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSaveConnection = async () => {
    setSavingConnection(true);
    try {
      await setBackendUrl(backendUrl);
      await initializeApi();
      setShowConnectionDialog(false);
      setError('');
      // Force page reload to apply new backend URL
      window.location.reload();
    } catch (error) {
      console.error('Failed to save connection:', error);
    } finally {
      setSavingConnection(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center mb-4">
            <img 
              src={AMEYA_LOGO_URL} 
              alt="Ameya Technologies" 
              className="h-20 w-20 object-contain rounded-xl shadow-lg"
            />
          </div>
          <h1 className="text-3xl font-bold tracking-tight font-['Manrope'] text-foreground">ATECH NOC COMMANDER</h1>
          <p className="text-muted-foreground mt-2">AI-Powered Network Operation Center</p>
        </div>

        <Card className="border-border/60 shadow-xl">
          <Tabs defaultValue="login">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between mb-2">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="login" data-testid="login-tab">Login</TabsTrigger>
                  <TabsTrigger value="register" data-testid="register-tab">Register</TabsTrigger>
                </TabsList>
              </div>
            </CardHeader>

            <CardContent className="pt-6">
              {error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <TabsContent value="login" className="mt-0">
                <form onSubmit={handleLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="login-email">Email</Label>
                    <Input
                      id="login-email"
                      type="email"
                      placeholder="operator@noc.com"
                      value={loginForm.email}
                      onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                      required
                      data-testid="login-email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="login-password">Password</Label>
                    <Input
                      id="login-password"
                      type="password"
                      placeholder="••••••••"
                      value={loginForm.password}
                      onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                      required
                      data-testid="login-password"
                    />
                  </div>
                  <Button 
                    type="submit" 
                    className="w-full" 
                    disabled={loading}
                    data-testid="login-submit"
                  >
                    {loading ? 'Signing in...' : 'Sign In'}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="register" className="mt-0">
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="register-name">Full Name</Label>
                    <Input
                      id="register-name"
                      type="text"
                      placeholder="John Doe"
                      value={registerForm.name}
                      onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                      required
                      data-testid="register-name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="register-email">Email</Label>
                    <Input
                      id="register-email"
                      type="email"
                      placeholder="operator@noc.com"
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                      required
                      data-testid="register-email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="register-password">Password</Label>
                    <Input
                      id="register-password"
                      type="password"
                      placeholder="••••••••"
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                      required
                      data-testid="register-password"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="register-confirm">Confirm Password</Label>
                    <Input
                      id="register-confirm"
                      type="password"
                      placeholder="••••••••"
                      value={registerForm.confirmPassword}
                      onChange={(e) => setRegisterForm({ ...registerForm, confirmPassword: e.target.value })}
                      required
                      data-testid="register-confirm"
                    />
                  </div>
                  <Button 
                    type="submit" 
                    className="w-full" 
                    disabled={loading}
                    data-testid="register-submit"
                  >
                    {loading ? 'Creating account...' : 'Create Account'}
                  </Button>
                </form>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>

        {/* Server Configuration Button */}
        <div className="flex items-center justify-center gap-4 mt-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowConnectionDialog(true)}
            className="text-muted-foreground hover:text-foreground"
            data-testid="server-config-btn"
          >
            <Settings className="h-4 w-4 mr-2" />
            Server Settings
          </Button>
        </div>

        {/* Security badge */}
        <div className="flex items-center justify-center gap-2 mt-4 text-sm text-muted-foreground">
          <Shield className="h-4 w-4" />
          <span>Enterprise-grade security</span>
        </div>
      </div>

      {/* Connection Settings Dialog */}
      <Dialog open={showConnectionDialog} onOpenChange={setShowConnectionDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-blue-600" />
              Backend Server Configuration
            </DialogTitle>
            <DialogDescription>
              Configure the backend server URL to connect to your NOC Commander API
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="backend-url">Backend Server URL</Label>
              <div className="flex gap-2">
                <Input
                  id="backend-url"
                  value={backendUrl}
                  onChange={(e) => setBackendUrlState(e.target.value)}
                  placeholder="http://localhost:8001"
                  className="flex-1"
                  data-testid="backend-url-input"
                />
                <Button
                  variant="outline"
                  onClick={handleTestConnection}
                  disabled={testingConnection || !backendUrl}
                  data-testid="test-connection-btn"
                >
                  {testingConnection ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : connectionStatus === 'connected' ? (
                    <Wifi className="h-4 w-4 text-green-500" />
                  ) : connectionStatus === 'failed' ? (
                    <WifiOff className="h-4 w-4 text-red-500" />
                  ) : (
                    <Wifi className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Example: http://localhost:8001
              </p>
            </div>

            {connectionStatus && (
              <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                connectionStatus === 'connected' 
                  ? 'bg-green-50 text-green-700 border border-green-200' 
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {connectionStatus === 'connected' ? (
                  <>
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Connected successfully!</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4" />
                    <span>Connection failed. Check URL and ensure backend is running.</span>
                  </>
                )}
              </div>
            )}

            <div className="bg-slate-50 p-3 rounded-lg text-sm space-y-2">
              <p className="font-medium">Quick Setup:</p>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-xs">
                <li>Start backend: <code className="bg-slate-200 px-1 rounded">python server.py</code></li>
                <li>Enter URL: <code className="bg-slate-200 px-1 rounded">http://localhost:8001</code></li>
                <li>Click test button to verify connection</li>
                <li>Save and the page will reload</li>
              </ol>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConnectionDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSaveConnection} 
              disabled={savingConnection || !backendUrl}
              data-testid="save-connection-btn"
            >
              {savingConnection ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Saving...</>
              ) : (
                'Save & Reload'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
