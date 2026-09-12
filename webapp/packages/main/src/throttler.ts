import {BrowserWindow} from 'electron';
import {Win32MemoryTrimmer} from './trimmer';

const BLUR_DEBOUNCE_MS = 500;
const IDLE_TRIM_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

/**
 * Window Power & Frame Rate Throttling State Machine.
 *
 * Implements 3 tiers of frame throttling and pipeline suspension:
 * - Active Foreground (focus): 30 FPS, background throttling off, responsive UI.
 * - Inactive / Blurred (blur): 5 FPS with 500ms debounce, background throttling on.
 * - Minimized / Tray (minimize / hide): 1 FPS, background throttling on, instant memory trimming.
 *
 * Additionally schedules a 10-minute periodic memory trim while window remains inactive/hidden.
 */
export class WindowPowerThrottler {
  private win: BrowserWindow;
  private trimmer: Win32MemoryTrimmer;
  private blurTimer: NodeJS.Timeout | null = null;
  private idleTrimInterval: NodeJS.Timeout | null = null;
  private currentFps: number = 30;

  constructor(win: BrowserWindow, trimmer: Win32MemoryTrimmer) {
    this.win = win;
    this.trimmer = trimmer;
  }

  /**
   * Handle window gaining focus or restoring to foreground.
   * Instantly cancels any pending blur debounce, stops idle trim interval,
   * and restores full 30 FPS composition rate.
   */
  public handleFocus(): void {
    if (this.blurTimer) {
      clearTimeout(this.blurTimer);
      this.blurTimer = null;
    }

    this.stopIdleTrimTimer();
    this.setThrottling(30, false);
  }

  /**
   * Handle window losing focus.
   * Debounces for 500ms to avoid oscillation during brief Alt+Tab switching.
   * If still unfocused after 500ms, lowers frame rate to 5 FPS and arms idle trim interval.
   */
  public handleBlur(): void {
    if (this.blurTimer) {
      clearTimeout(this.blurTimer);
    }

    this.blurTimer = setTimeout(() => {
      this.blurTimer = null;
      if (!this.win.isDestroyed() && !this.win.isFocused()) {
        console.info('[WindowPowerThrottler] Window unfocused for >500ms. Throttling to 5 FPS.');
        this.setThrottling(5, true);
        this.startIdleTrimTimer();
      }
    }, BLUR_DEBOUNCE_MS);
  }

  /**
   * Handle window minimize, hide, or send-to-tray.
   * Drops frame rate to 1 FPS immediately, suspends background compositing,
   * triggers an immediate working set memory trim, and arms the 10-minute idle trim interval.
   */
  public handleMinimizeOrHide(): void {
    if (this.blurTimer) {
      clearTimeout(this.blurTimer);
      this.blurTimer = null;
    }

    console.info('[WindowPowerThrottler] Window minimized or hidden to tray. Throttling to 1 FPS and trimming memory.');
    this.setThrottling(1, true);
    this.trimmer.trimAllProcesses();
    this.startIdleTrimTimer();
  }

  /**
   * Apply frame rate and background throttling settings to WebContents.
   */
  private setThrottling(fps: number, backgroundThrottling: boolean): void {
    if (this.win.isDestroyed()) {
      return;
    }

    this.currentFps = fps;

    try {
      this.win.webContents.setBackgroundThrottling(backgroundThrottling);
    } catch (err) {
      console.warn('[WindowPowerThrottler] Failed to setBackgroundThrottling:', err);
    }

    try {
      this.win.webContents.setFrameRate(fps);
    } catch (err) {
      console.warn('[WindowPowerThrottler] Failed to setFrameRate:', err);
    }

    try {
      this.win.webContents.send('power-state-change', {fps, backgroundThrottling});
    } catch {
      // Ignore if renderer not ready to receive IPC
    }
  }

  /**
   * Start 10-minute periodic idle trimming interval while window remains unfocused or hidden.
   */
  private startIdleTrimTimer(): void {
    if (this.idleTrimInterval) {
      return;
    }

    this.idleTrimInterval = setInterval(() => {
      if (this.win.isDestroyed()) {
        this.stopIdleTrimTimer();
        return;
      }

      const isInactive = !this.win.isVisible() || this.win.isMinimized() || !this.win.isFocused();
      if (isInactive) {
        console.info('[WindowPowerThrottler] 10-minute idle threshold reached while inactive. Running periodic memory trim.');
        this.trimmer.trimAllProcesses();
      }
    }, IDLE_TRIM_INTERVAL_MS);
  }

  /**
   * Stop periodic idle trimming interval.
   */
  private stopIdleTrimTimer(): void {
    if (this.idleTrimInterval) {
      clearInterval(this.idleTrimInterval);
      this.idleTrimInterval = null;
    }
  }

  /**
   * Cleanup all timers when window is being destroyed.
   */
  public destroy(): void {
    if (this.blurTimer) {
      clearTimeout(this.blurTimer);
      this.blurTimer = null;
    }
    this.stopIdleTrimTimer();
  }
}
