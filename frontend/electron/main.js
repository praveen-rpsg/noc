const { app, BrowserWindow, Menu, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const url = require('url');
const fs = require('fs');

// Keep a global reference of the window object
let mainWindow;

// Check if running in development
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

// Configuration file path for storing backend URL
const configPath = path.join(app.getPath('userData'), 'config.json');

// Default configuration
const defaultConfig = {
  backendUrl: 'http://localhost:8001'
};

// Load or create configuration
function loadConfig() {
  try {
    if (fs.existsSync(configPath)) {
      const data = fs.readFileSync(configPath, 'utf8');
      return { ...defaultConfig, ...JSON.parse(data) };
    }
  } catch (error) {
    console.error('Error loading config:', error);
  }
  return defaultConfig;
}

// Save configuration
function saveConfig(config) {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    return true;
  } catch (error) {
    console.error('Error saving config:', error);
    return false;
  }
}

// Get current config
let appConfig = defaultConfig;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'ATECH NOC Commander',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
    },
    backgroundColor: '#0f172a', // Dark background matching app theme
    show: false, // Don't show until ready
  });

  // Load the app
  if (isDev) {
    // In development, load from the dev server
    mainWindow.loadURL('http://localhost:3000');
    // Open DevTools in development
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load the built app
    mainWindow.loadFile(path.join(__dirname, '../build/index.html'));
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Emitted when the window is closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Create application menu
  createMenu();
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Incident',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.send('menu-action', 'new-incident');
          },
        },
        { type: 'separator' },
        {
          label: 'Settings',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            mainWindow.webContents.send('navigate', '/settings');
          },
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Alt+F4',
          click: () => {
            app.quit();
          },
        },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Dashboard',
          accelerator: 'CmdOrCtrl+1',
          click: () => mainWindow.webContents.send('navigate', '/'),
        },
        {
          label: 'Monitoring',
          accelerator: 'CmdOrCtrl+2',
          click: () => mainWindow.webContents.send('navigate', '/monitoring'),
        },
        {
          label: 'Incidents',
          accelerator: 'CmdOrCtrl+3',
          click: () => mainWindow.webContents.send('navigate', '/incidents'),
        },
        {
          label: 'Alerts',
          accelerator: 'CmdOrCtrl+4',
          click: () => mainWindow.webContents.send('navigate', '/alerts'),
        },
        {
          label: 'Network Topology',
          accelerator: 'CmdOrCtrl+5',
          click: () => mainWindow.webContents.send('navigate', '/topology'),
        },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'NOC Tools',
      submenu: [
        {
          label: 'SSH Terminal',
          accelerator: 'CmdOrCtrl+T',
          click: () => mainWindow.webContents.send('navigate', '/ssh'),
        },
        {
          label: 'Network Diagnostics',
          accelerator: 'CmdOrCtrl+D',
          click: () => mainWindow.webContents.send('menu-action', 'open-diagnostics'),
        },
        { type: 'separator' },
        {
          label: 'Run AI Agent',
          accelerator: 'CmdOrCtrl+Shift+A',
          click: () => mainWindow.webContents.send('menu-action', 'run-ai-agent'),
        },
        {
          label: 'Voice Alerts Settings',
          click: () => mainWindow.webContents.send('menu-action', 'voice-settings'),
        },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About ATECH NOC Commander',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About ATECH NOC Commander',
              message: 'ATECH NOC Commander',
              detail: `Version: ${app.getVersion()}\n\nAI-Powered Network Operation Center Tool\nby Ameya Technology\n\nFeatures:\n- 24x7 Network Monitoring\n- AI-Powered Incident Resolution\n- Voice Alerts\n- Network Diagnostics\n- Routing Optimization`,
            });
          },
        },
        { type: 'separator' },
        {
          label: 'Documentation',
          click: () => {
            shell.openExternal('https://github.com/your-repo/atech-noc-commander');
          },
        },
        {
          label: 'Report Issue',
          click: () => {
            shell.openExternal('https://github.com/your-repo/atech-noc-commander/issues');
          },
        },
      ],
    },
  ];

  // macOS specific menu adjustments
  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    });
  }

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// IPC Handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-platform', () => {
  return process.platform;
});

// Backend URL configuration handlers
ipcMain.handle('get-backend-url', () => {
  return appConfig.backendUrl;
});

ipcMain.handle('set-backend-url', (event, url) => {
  appConfig.backendUrl = url;
  saveConfig(appConfig);
  return true;
});

ipcMain.handle('get-config', () => {
  return appConfig;
});

ipcMain.on('show-notification', (event, { title, body }) => {
  const { Notification } = require('electron');
  if (Notification.isSupported()) {
    new Notification({ title, body }).show();
  }
});

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  // Load configuration before creating window
  appConfig = loadConfig();
  
  createWindow();

  app.on('activate', () => {
    // On macOS, re-create a window when dock icon is clicked
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  // On macOS, apps stay active until Cmd+Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Handle certificate errors (for development with self-signed certs)
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  if (isDev) {
    // In development, ignore certificate errors
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});

// Security: Prevent navigation to external URLs
app.on('web-contents-created', (event, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);
    if (parsedUrl.origin !== 'http://localhost:3000' && !navigationUrl.startsWith('file://')) {
      event.preventDefault();
    }
  });
});
