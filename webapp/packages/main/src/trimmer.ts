import {app} from 'electron';

/**
 * Win32 Process Tree Working Set Memory Trimmer.
 *
 * Traverses Electron main process, all renderer processes, GPU process,
 * and utility processes via app.getAppMetrics(), invoking Win32 EmptyWorkingSet
 * via Koffi (Node-API FFI) to force Windows to swap out inactive memory pages.
 *
 * Includes graceful degradation if Koffi is unavailable or if platform is non-Windows.
 */
export class Win32MemoryTrimmer {
  private openProcessFn: any = null;
  private emptyWorkingSetFn: any = null;
  private closeHandleFn: any = null;
  private available: boolean = false;

  constructor() {
    if (process.platform !== 'win32') {
      this.available = false;
      return;
    }

    try {
      const koffi = require('koffi');
      const kernel32 = koffi.load('kernel32.dll');
      const psapi = koffi.load('psapi.dll');

      // HANDLE OpenProcess(DWORD dwDesiredAccess, BOOL bInheritHandle, DWORD dwProcessId)
      this.openProcessFn = kernel32.func('OpenProcess', 'void *', ['uint32', 'bool', 'uint32']);
      // BOOL CloseHandle(HANDLE hObject)
      this.closeHandleFn = kernel32.func('CloseHandle', 'bool', ['void *']);
      // BOOL EmptyWorkingSet(HANDLE hProcess)
      this.emptyWorkingSetFn = psapi.func('EmptyWorkingSet', 'bool', ['void *']);

      this.available = true;
      console.info('[Win32MemoryTrimmer] Win32 PSAPI EmptyWorkingSet bindings initialized successfully via Koffi.');
    } catch (err) {
      console.warn('[Win32MemoryTrimmer] Koffi / Win32 FFI failed to load; memory trimming will degrade gracefully:', err);
      this.available = false;
    }
  }

  /**
   * Check if Win32 memory trimming capability is available.
   */
  public isAvailable(): boolean {
    return this.available;
  }

  /**
   * Trim working set across the entire Electron process tree.
   * Scans main process and all child processes (renderers, GPU, workers).
   */
  public trimAllProcesses(): void {
    if (!this.available) {
      return;
    }

    const pids = new Set<number>();
    pids.add(process.pid);

    try {
      const metrics = app.getAppMetrics();
      for (const m of metrics) {
        if (m.pid) {
          pids.add(m.pid);
        }
      }
    } catch (err) {
      console.warn('[Win32MemoryTrimmer] Error querying app.getAppMetrics():', err);
    }

    // PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_SET_QUOTA (0x0100) = 0x0500
    const desiredAccess = 0x0500;
    let trimmedCount = 0;

    for (const pid of pids) {
      try {
        const handle = this.openProcessFn(desiredAccess, false, pid);
        if (handle) {
          const success = this.emptyWorkingSetFn(handle);
          if (success) {
            trimmedCount++;
          }
          this.closeHandleFn(handle);
        }
      } catch {
        // Suppress individual process access permission errors (e.g. elevated or exiting processes)
      }
    }

    console.info(`[Win32MemoryTrimmer] Working set trimmed for ${trimmedCount}/${pids.size} processes.`);
  }
}
