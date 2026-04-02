import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
  Volume2, 
  VolumeX, 
  Settings,
  AlertTriangle
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Label } from './ui/label';
import { Switch } from './ui/switch';

// Voice Alert Context
const VoiceAlertContext = createContext(null);

export const useVoiceAlert = () => {
  const context = useContext(VoiceAlertContext);
  if (!context) {
    throw new Error('useVoiceAlert must be used within VoiceAlertProvider');
  }
  return context;
};

// Voice types available
const VOICE_TYPES = {
  MALE: 'male',
  FEMALE: 'female',
};

// Alert severity levels
const ALERT_SEVERITY = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
};

export function VoiceAlertProvider({ children }) {
  const [isMuted, setIsMuted] = useState(() => {
    const saved = localStorage.getItem('voiceAlertMuted');
    return saved ? JSON.parse(saved) : false;
  });
  const [voiceType, setVoiceType] = useState(() => {
    return localStorage.getItem('voiceAlertType') || VOICE_TYPES.FEMALE;
  });
  const [volume, setVolume] = useState(() => {
    const saved = localStorage.getItem('voiceAlertVolume');
    return saved ? parseFloat(saved) : 1.0;
  });
  const [rate, setRate] = useState(() => {
    const saved = localStorage.getItem('voiceAlertRate');
    return saved ? parseFloat(saved) : 1.0;
  });
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lastAlert, setLastAlert] = useState(null);
  const [alertQueue, setAlertQueue] = useState([]);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Load available voices
  useEffect(() => {
    const loadVoices = () => {
      const availableVoices = window.speechSynthesis?.getVoices() || [];
      setVoices(availableVoices);
      
      // Select appropriate voice based on type preference
      if (availableVoices.length > 0) {
        const preferredVoice = findPreferredVoice(availableVoices, voiceType);
        setSelectedVoice(preferredVoice);
      }
    };

    loadVoices();
    
    // Chrome loads voices asynchronously
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, [voiceType]);

  // Save preferences to localStorage
  useEffect(() => {
    localStorage.setItem('voiceAlertMuted', JSON.stringify(isMuted));
  }, [isMuted]);

  useEffect(() => {
    localStorage.setItem('voiceAlertType', voiceType);
  }, [voiceType]);

  useEffect(() => {
    localStorage.setItem('voiceAlertVolume', volume.toString());
  }, [volume]);

  useEffect(() => {
    localStorage.setItem('voiceAlertRate', rate.toString());
  }, [rate]);

  // Find preferred voice based on type
  const findPreferredVoice = (voiceList, type) => {
    const isFemale = type === VOICE_TYPES.FEMALE;
    
    // Try to find English voices first
    const englishVoices = voiceList.filter(v => v.lang.startsWith('en'));
    
    // Common female/male voice name patterns
    const femalePatterns = ['female', 'woman', 'samantha', 'victoria', 'karen', 'moira', 'tessa', 'fiona', 'zira'];
    const malePatterns = ['male', 'man', 'daniel', 'alex', 'tom', 'david', 'james', 'mark'];
    
    const patterns = isFemale ? femalePatterns : malePatterns;
    
    // Search in English voices first
    for (const voice of englishVoices) {
      const nameLower = voice.name.toLowerCase();
      if (patterns.some(p => nameLower.includes(p))) {
        return voice;
      }
    }
    
    // If no match, return first English voice or any available voice
    return englishVoices[0] || voiceList[0];
  };

  // Process alert queue
  useEffect(() => {
    if (!isSpeaking && alertQueue.length > 0 && !isMuted) {
      const [nextAlert, ...rest] = alertQueue;
      setAlertQueue(rest);
      speakAlert(nextAlert);
    }
  }, [alertQueue, isSpeaking, isMuted]);

  // Speak an alert
  const speakAlert = useCallback((alertData) => {
    if (!window.speechSynthesis || isMuted) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(alertData.message);
    
    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }
    
    utterance.volume = volume;
    utterance.rate = rate;
    utterance.pitch = voiceType === VOICE_TYPES.FEMALE ? 1.2 : 0.9;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
    setLastAlert(alertData);
  }, [selectedVoice, volume, rate, voiceType, isMuted]);

  // Queue an alert
  const queueAlert = useCallback((message, severity = ALERT_SEVERITY.HIGH, deviceName = null) => {
    const alertData = {
      id: Date.now(),
      message: buildAlertMessage(message, severity, deviceName),
      severity,
      deviceName,
      timestamp: new Date().toISOString(),
    };

    if (isMuted) {
      setLastAlert(alertData);
      return;
    }

    setAlertQueue(prev => [...prev, alertData]);
  }, [isMuted]);

  // Build alert message
  const buildAlertMessage = (message, severity, deviceName) => {
    let prefix = '';
    switch (severity) {
      case ALERT_SEVERITY.CRITICAL:
        prefix = 'Critical alert! ';
        break;
      case ALERT_SEVERITY.HIGH:
        prefix = 'Warning! ';
        break;
      case ALERT_SEVERITY.MEDIUM:
        prefix = 'Attention. ';
        break;
      default:
        prefix = '';
    }

    const deviceInfo = deviceName ? `Device ${deviceName}. ` : '';
    return `${prefix}${deviceInfo}${message}`;
  };

  // Announce network failure
  const announceNetworkFailure = useCallback((deviceName, failureType, details = '') => {
    const messages = {
      'device_down': `has gone offline. Immediate attention required.`,
      'high_cpu': `is experiencing high CPU usage. ${details}`,
      'high_memory': `is experiencing high memory usage. ${details}`,
      'packet_loss': `is experiencing packet loss. ${details}`,
      'latency': `is experiencing high latency. ${details}`,
      'link_down': `link is down. ${details}`,
      'routing_loop': `detected a routing loop. ${details}`,
      'stp_loop': `detected a spanning tree loop. ${details}`,
      'unreachable': `is unreachable. ${details}`,
    };

    const message = messages[failureType] || `has an issue: ${failureType}`;
    queueAlert(message, ALERT_SEVERITY.CRITICAL, deviceName);
  }, [queueAlert]);

  // Announce traceroute issue
  const announceTracerouteIssue = useCallback((target, issues) => {
    if (issues && issues.length > 0) {
      const message = `Traceroute to ${target} detected ${issues.length} issue${issues.length > 1 ? 's' : ''}. ${issues[0]}`;
      queueAlert(message, ALERT_SEVERITY.HIGH);
    }
  }, [queueAlert]);

  // Test voice
  const testVoice = useCallback(() => {
    const testMessage = "This is a test of the NOC Commander voice alert system.";
    speakAlert({ message: testMessage, severity: ALERT_SEVERITY.MEDIUM });
  }, [speakAlert]);

  // Stop speaking
  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    setAlertQueue([]);
  }, []);

  const value = {
    isMuted,
    setIsMuted,
    voiceType,
    setVoiceType,
    volume,
    setVolume,
    rate,
    setRate,
    voices,
    selectedVoice,
    setSelectedVoice,
    isSettingsOpen,
    setIsSettingsOpen,
    lastAlert,
    isSpeaking,
    queueAlert,
    announceNetworkFailure,
    announceTracerouteIssue,
    testVoice,
    stopSpeaking,
    VOICE_TYPES,
    ALERT_SEVERITY,
  };

  return (
    <VoiceAlertContext.Provider value={value}>
      {children}
    </VoiceAlertContext.Provider>
  );
}

// Voice Alert Controls Component (for header)
export function VoiceAlertControls() {
  const {
    isMuted,
    setIsMuted,
    isSpeaking,
    stopSpeaking,
    setIsSettingsOpen,
    lastAlert,
  } = useVoiceAlert();

  return (
    <div className="flex items-center gap-2">
      {/* Mute/Unmute Button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => {
          if (isSpeaking) {
            stopSpeaking();
          }
          setIsMuted(!isMuted);
        }}
        className={`relative ${isMuted ? 'text-muted-foreground' : 'text-foreground'}`}
        data-testid="voice-alert-toggle"
        title={isMuted ? 'Unmute voice alerts' : 'Mute voice alerts'}
      >
        {isMuted ? (
          <VolumeX className="h-5 w-5" />
        ) : (
          <Volume2 className={`h-5 w-5 ${isSpeaking ? 'animate-pulse text-green-500' : ''}`} />
        )}
        {lastAlert && !isMuted && (
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full" />
        )}
      </Button>

      {/* Settings Button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsSettingsOpen(true)}
        data-testid="voice-settings-btn"
        title="Voice alert settings"
      >
        <Settings className="h-4 w-4" />
      </Button>
    </div>
  );
}

// Voice Settings Dialog
export function VoiceSettingsDialog() {
  const {
    isMuted,
    setIsMuted,
    voiceType,
    setVoiceType,
    volume,
    setVolume,
    rate,
    setRate,
    voices,
    selectedVoice,
    setSelectedVoice,
    isSettingsOpen,
    setIsSettingsOpen,
    testVoice,
    VOICE_TYPES,
  } = useVoiceAlert();

  // Filter voices by language
  const englishVoices = voices.filter(v => v.lang.startsWith('en'));

  return (
    <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            Voice Alert Settings
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Enable/Disable */}
          <div className="flex items-center justify-between">
            <Label htmlFor="voice-enabled" className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Voice Alerts Enabled
            </Label>
            <Switch
              id="voice-enabled"
              checked={!isMuted}
              onCheckedChange={(checked) => setIsMuted(!checked)}
            />
          </div>

          {/* Voice Type Selection */}
          <div className="space-y-2">
            <Label>Voice Type</Label>
            <Select value={voiceType} onValueChange={setVoiceType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={VOICE_TYPES.FEMALE}>Female Voice</SelectItem>
                <SelectItem value={VOICE_TYPES.MALE}>Male Voice</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Specific Voice Selection */}
          {englishVoices.length > 0 && (
            <div className="space-y-2">
              <Label>Specific Voice</Label>
              <Select 
                value={selectedVoice?.name || ''} 
                onValueChange={(name) => {
                  const voice = voices.find(v => v.name === name);
                  if (voice) setSelectedVoice(voice);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Auto-select" />
                </SelectTrigger>
                <SelectContent>
                  {englishVoices.map((voice) => (
                    <SelectItem key={voice.name} value={voice.name}>
                      {voice.name} ({voice.lang})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Volume */}
          <div className="space-y-2">
            <Label>Volume: {Math.round(volume * 100)}%</Label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Speech Rate */}
          <div className="space-y-2">
            <Label>Speech Rate: {rate}x</Label>
            <input
              type="range"
              min="0.5"
              max="2"
              step="0.1"
              value={rate}
              onChange={(e) => setRate(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Test Button */}
          <Button onClick={testVoice} className="w-full" disabled={isMuted}>
            <Volume2 className="h-4 w-4 mr-2" />
            Test Voice Alert
          </Button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setIsSettingsOpen(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default VoiceAlertProvider;
