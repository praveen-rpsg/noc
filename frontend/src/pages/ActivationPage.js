import React, { useState } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Key, Shield, CheckCircle2, AlertTriangle, Loader2, Server } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { getBackendUrlSync, setBackendUrl, testBackendConnection, initConfig } from '../services/config';
import { initializeApi } from '../services/api';

const AMEYA_LOGO_URL = "https://customer-assets.emergentagent.com/job_network-ops-ai/artifacts/vjap12f5_Atechlogo.jpeg";

export default function ActivationPage({ onActivated }) {
  const [activationCode, setActivationCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  
  // Server settings
  const [showServerSettings, setShowServerSettings] = useState(false);
  const [backendUrl, setBackendUrlState] = useState(getBackendUrlSync());
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);

  const formatActivationCode = (value) => {
    // Remove non-alphanumeric characters except hyphens
    let cleaned = value.toUpperCase().replace(/[^A-Z0-9-]/g, '');
    
    // Auto-format as ATECH-XXXX-XXXX-XXXX
    if (!cleaned.startsWith('ATECH-') && cleaned.length > 0) {
      if (cleaned.startsWith('ATECH')) {
        cleaned = 'ATECH-' + cleaned.substring(5);
      }
    }
    
    return cleaned;
  };

  const handleActivate = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const API_URL = getBackendUrlSync();
      const response = await fetch(`${API_URL}/api/license/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activation_code: activationCode.trim() })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Activation failed');
      }

      setSuccess(true);
      setTimeout(() => {
        onActivated && onActivated();
      }, 2000);
    } catch (err) {
      if (err.message?.includes('fetch') || err.name === 'TypeError') {
        setError('Cannot connect to server. Click "Server Settings" to configure backend URL.');
      } else {
        setError(err.message || 'Activation failed');
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
    await setBackendUrl(backendUrl);
    await initializeApi();
    setShowServerSettings(false);
    window.location.reload();
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md border-green-200 shadow-xl">
          <CardContent className="pt-8 pb-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-green-700 mb-2">Activation Successful!</h2>
            <p className="text-muted-foreground">Your NOC Commander is now activated.</p>
            <p className="text-sm text-muted-foreground mt-2">Redirecting to login...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

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
          <CardHeader className="text-center pb-2">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <Key className="h-6 w-6 text-blue-600" />
            </div>
            <CardTitle className="text-xl">Application Activation</CardTitle>
            <CardDescription>
              Enter your activation code to unlock the full application
            </CardDescription>
          </CardHeader>

          <CardContent className="pt-4">
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleActivate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="activation-code">Activation Code</Label>
                <Input
                  id="activation-code"
                  type="text"
                  placeholder="ATECH-XXXX-XXXX-XXXX"
                  value={activationCode}
                  onChange={(e) => setActivationCode(formatActivationCode(e.target.value))}
                  className="font-mono text-center tracking-wider"
                  maxLength={19}
                  required
                  data-testid="activation-code-input"
                />
                <p className="text-xs text-muted-foreground text-center">
                  Format: ATECH-XXXX-XXXX-XXXX
                </p>
              </div>

              <Button 
                type="submit" 
                className="w-full" 
                disabled={loading || activationCode.length < 19}
                data-testid="activate-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Activating...
                  </>
                ) : (
                  <>
                    <Key className="h-4 w-4 mr-2" />
                    Activate Application
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 pt-4 border-t">
              <p className="text-sm text-muted-foreground text-center mb-3">
                Need an activation code? Contact your administrator.
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowServerSettings(true)}
                className="w-full text-muted-foreground"
                data-testid="server-settings-btn"
              >
                <Server className="h-4 w-4 mr-2" />
                Server Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Security badge */}
        <div className="flex items-center justify-center gap-2 mt-6 text-sm text-muted-foreground">
          <Shield className="h-4 w-4" />
          <span>Enterprise-grade security</span>
        </div>
      </div>

      {/* Server Settings Dialog */}
      <Dialog open={showServerSettings} onOpenChange={setShowServerSettings}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-blue-600" />
              Backend Server Configuration
            </DialogTitle>
            <DialogDescription>
              Configure the backend server URL
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
                />
                <Button
                  variant="outline"
                  onClick={handleTestConnection}
                  disabled={testingConnection}
                >
                  {testingConnection ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Test'
                  )}
                </Button>
              </div>
            </div>

            {connectionStatus && (
              <div className={`p-3 rounded-lg text-sm ${
                connectionStatus === 'connected' 
                  ? 'bg-green-50 text-green-700 border border-green-200' 
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {connectionStatus === 'connected' 
                  ? '✓ Connected successfully!' 
                  : '✗ Connection failed'}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowServerSettings(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveConnection}>
              Save & Reload
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
