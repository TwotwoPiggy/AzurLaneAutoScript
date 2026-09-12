import {app, BrowserWindow, Tray} from 'electron';

const RELOAD_COOLDOWN_MS = 10000;
let lastRecovery = 0;

/**
 * Setup GPU and renderer crash watchdog.
 * Intercepts child-process-gone (GPU TDR / out of memory) and render-process-gone,
 * smoothly reloads the window after a debounce and driver stabilization delay,
 * and notifies the user via Windows system tray balloon without terminating python backend.
 */
export function setupGpuRecoveryWatchdog(
  getWin: () => BrowserWindow | null,
  getTray: () => Tray | null
): void {
  // Listen for child process crashes (GPU, utility processes)
  app.on('child-process-gone', (event, details) => {
    console.warn(`[Watchdog] Child process gone: type=${details.type}, reason=${details.reason}, exitCode=${details.exitCode}`);

    if (details.type === 'GPU') {
      const now = Date.now();
      if (now - lastRecovery < RELOAD_COOLDOWN_MS) {
        console.warn(`[Watchdog] GPU crash recovery throttled (within ${RELOAD_COOLDOWN_MS}ms debounce cooldown).`);
        return;
      }
      lastRecovery = now;

      console.warn('[Watchdog] GPU process crashed (possible LiveKernelEvent 141 TDR). Scheduling smooth recovery in 500ms...');

      setTimeout(() => {
        const win = getWin();
        if (win && !win.isDestroyed()) {
          console.info('[Watchdog] Reloading renderer view following GPU process recovery.');
          win.reload();
        }

        const tray = getTray();
        if (tray && !tray.isDestroyed()) {
          try {
            tray.displayBalloon({
              iconType: 'warning',
              title: 'Alas 桌面客户端',
              content: '检测到系统图形驱动重置 (GPU TDR)，界面已自动平滑自愈恢复，后台任务持续运行。',
            });
          } catch (e) {
            console.error('[Watchdog] Failed to display tray balloon:', e);
          }
        }
      }, 500);
    }
  });

  // Watch for renderer process crash as fallback
  app.whenReady().then(() => {
    const attachRendererListener = () => {
      const win = getWin();
      if (win && !win.isDestroyed()) {
        win.webContents.on('render-process-gone', (event, details) => {
          console.warn(`[Watchdog] Render process gone: reason=${details.reason}, exitCode=${details.exitCode}`);
          if (details.reason !== 'clean-exit') {
            const now = Date.now();
            if (now - lastRecovery >= RELOAD_COOLDOWN_MS) {
              lastRecovery = now;
              setTimeout(() => {
                if (win && !win.isDestroyed()) {
                  console.info('[Watchdog] Reloading crashed renderer.');
                  win.reload();
                }
              }, 500);
            }
          }
        });
      } else {
        // If window is not ready yet, retry in 100ms
        setTimeout(attachRendererListener, 100);
      }
    };

    attachRendererListener();
  });
}
