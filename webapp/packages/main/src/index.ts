import {app, Menu, Tray, BrowserWindow, ipcMain, globalShortcut} from 'electron';
import {URL} from 'url';
import {PyShell} from '/@/pyshell';
import {webuiArgs, webuiPath, dpiScaling} from '/@/config';

const path = require('path');

const isSingleInstance = app.requestSingleInstanceLock();

if (!isSingleInstance) {
  app.quit();
  process.exit(0);
}

// DESK-01 & DESK-04: 移除全局软件光栅化，定向优先使用低功耗集成显卡（Intel HD 4600），并限制 V8 堆内存
app.commandLine.appendSwitch('force_low_power_gpu', 'true');
app.commandLine.appendSwitch('disable-gpu-process-crash-limit');
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=128');

// Install "Vue.js devtools"
if (import.meta.env.MODE === 'development') {
  app.whenReady()
    .then(() => import('electron-devtools-installer'))
    .then(({default: installExtension, VUEJS3_DEVTOOLS}) => installExtension(VUEJS3_DEVTOOLS, {
      loadExtensionOptions: {
        allowFileAccess: true,
      },
    }))
    .catch(e => console.error('Failed install extension:', e));
}

/**
 * Load deploy settings and start Alas web server.
 */
let alas = new PyShell(webuiPath, webuiArgs);
alas.end(function (err: string) {
  // if (err) throw err;
});


let mainWindow: BrowserWindow | null = null;

const createWindow = async () => {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 880,
    show: false, // Use 'ready-to-show' event to show window
    frame: false,
    icon: path.join(__dirname, './buildResources/icon.ico'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,   // Spectron tests can't work with contextIsolation: true
      nativeWindowOpen: true,
      // preload: join(__dirname, '../../preload/dist/index.cjs'),
    },
  });

  /**
   * If you install `show: true` then it can cause issues when trying to close the window.
   * Use `show: false` and listener events `ready-to-show` to fix these issues.
   *
   * @see https://github.com/electron/electron/issues/25012
   */
  mainWindow.on('ready-to-show', () => {
    mainWindow?.show();

    // Hide menu
    const {Menu} = require('electron');
    Menu.setApplicationMenu(null);

    if (import.meta.env.MODE === 'development') {
      mainWindow?.webContents.openDevTools();
    }
  });

  // DESK-02: 动态帧率调控与后台节能
  const applyFrameRate = (fps: number) => {
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.setFrameRate(fps);
      }
    } catch (e) {
      console.warn('Failed to set frame rate:', e);
    }
  };

  mainWindow.on('focus', function () {
    applyFrameRate(60);
    // Dev tools
    globalShortcut.register('Ctrl+Shift+I', function () {
      if (mainWindow?.webContents.isDevToolsOpened()) {
        mainWindow?.webContents.closeDevTools()
      } else {
        mainWindow?.webContents.openDevTools()
      }
    });
    // Refresh
    globalShortcut.register('Ctrl+R', function () {
      mainWindow?.reload()
    });
    globalShortcut.register('Ctrl+Shift+R', function () {
      mainWindow?.reload()
    });
  });

  mainWindow.on('blur', function () {
    globalShortcut.unregisterAll();
    // 窗口失焦时降频至 5 FPS，消除后台无谓渲染能耗
    applyFrameRate(5);
  });

  mainWindow.on('minimize', function () {
    // 窗口最小化时降频至 1 FPS，极致降低 CPU 与显存活动
    applyFrameRate(1);
  });

  mainWindow.on('restore', function () {
    applyFrameRate(30);
  });

  mainWindow.on('hide', function () {
    applyFrameRate(1);
  });

  mainWindow.on('show', function () {
    applyFrameRate(30);
  });

  // DESK-03: 渲染进程崩溃与白屏容灾平滑重启
  mainWindow.webContents.on('render-process-gone', (event, details) => {
    console.error(`Electron render process gone: ${details.reason}, exitCode: ${details.exitCode}`);
    if (details.reason !== 'clean-exit') {
      setTimeout(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          console.info('Attempting to reload main window after render process crash...');
          loadURL();
        }
      }, 1500);
    }
  });

  // Minimize, maximize, close window.
  ipcMain.on('window-tray', function () {
    mainWindow?.hide();
    applyFrameRate(1);
  });
  ipcMain.on('window-min', function () {
    mainWindow?.minimize();
  });
  ipcMain.on('window-max', function () {
    mainWindow?.isMaximized() ? mainWindow?.restore() : mainWindow?.maximize();
  });
  ipcMain.on('window-close', function () {
    alas.kill(function () {
      mainWindow?.close();
    })
  });

  // Tray
  const tray = new Tray(path.join(__dirname, 'icon.png'));
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show',
      click: function () {
        mainWindow?.show();
      }
    },
    {
      label: 'Hide',
      click: function () {
        mainWindow?.hide();
      }
    },
    {
      label: 'Exit',
      click: function () {
        alas.kill(function () {
          mainWindow?.close();
        })
      }
    }
  ]);
  tray.setToolTip('Alas');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    mainWindow?.isVisible() ? mainWindow?.hide() : mainWindow?.show()
  });
  tray.on('right-click', () => {
    tray.popUpContextMenu(contextMenu)
  });
};


// No DPI scaling
if (!dpiScaling) {
  app.commandLine.appendSwitch('high-dpi-support', '1');
  app.commandLine.appendSwitch('force-device-scale-factor', '1');
}


function loadURL() {
  /**
   * URL for main window.
   * Vite dev server for development.
   * `file://../renderer/index.html` for production and test
   */
  const pageUrl = import.meta.env.MODE === 'development' && import.meta.env.VITE_DEV_SERVER_URL !== undefined
    ? import.meta.env.VITE_DEV_SERVER_URL
    : new URL('../renderer/dist/index.html', 'file://' + __dirname).toString();

  mainWindow?.loadURL(pageUrl);
}


alas.on('stderr', function (message: string) {
  /**
   * Receive logs, judge if Alas is ready
   * For starlette backend, there will have:
   * `INFO:     Uvicorn running on http://0.0.0.0:22267 (Press CTRL+C to quit)`
   * Or backend has started already
   * `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 22267): `
   */
  if (message.includes('Application startup complete') || message.includes('bind on address')) {
    alas.removeAllListeners('stderr');
    loadURL()
  }
});


app.on('second-instance', () => {
  // Someone tried to run a second instance, we should focus our window.
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    if (!mainWindow.isVisible()) mainWindow.show();
    mainWindow.focus();
  }
});


app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});


// DESK-03: 监听 GPU 进程崩溃与容灾降级，避免崩溃导致 Alas 强制退出
let gpuCrashCount = 0;
app.on('child-process-gone', (event, details) => {
  if (details.type === 'GPU') {
    gpuCrashCount++;
    console.warn(`Electron GPU process crashed (${details.reason}), count: ${gpuCrashCount}`);
    if (gpuCrashCount > 3) {
      console.error('GPU process crashed repeatedly (>3), safe fallback to software rasterization.');
      app.disableHardwareAcceleration();
    }
  }
});

app.whenReady()
  .then(createWindow)
  .catch((e) => console.error('Failed create window:', e));


// Auto-updates
if (import.meta.env.PROD) {
  app.whenReady()
    .then(() => import('electron-updater'))
    .then(({autoUpdater}) => autoUpdater.checkForUpdatesAndNotify())
    .catch((e) => console.error('Failed check updates:', e));
}

