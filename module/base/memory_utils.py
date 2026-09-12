import gc
import os
import sys
import psutil

from module.logger import logger


def get_process_rss(pid: int = None) -> int:
    """
    Get resident physical memory size (RSS) in bytes for a given process.

    Args:
        pid (int, optional): Process ID. Defaults to current process if None.

    Returns:
        int: Memory in bytes, or 0 if process cannot be queried.
    """
    try:
        if pid is None:
            p = psutil.Process()
        else:
            p = psutil.Process(pid)
        return p.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return 0


def empty_working_set(pid: int = None) -> bool:
    """
    Trim physical working set of a process using Win32 EmptyWorkingSet API.
    Safely degrades to False on non-Windows platforms or permission errors.

    Args:
        pid (int, optional): Process ID. Defaults to current process if None.

    Returns:
        bool: True if trimming succeeded, False otherwise.
    """
    if sys.platform != 'win32':
        return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
        psapi.EmptyWorkingSet.restype = wintypes.BOOL

        if pid is None or pid == os.getpid():
            handle = kernel32.GetCurrentProcess()
            return bool(psapi.EmptyWorkingSet(handle))
        else:
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_SET_QUOTA = 0x0100
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
            if not handle:
                return False
            try:
                return bool(psapi.EmptyWorkingSet(handle))
            finally:
                kernel32.CloseHandle(handle)
    except Exception as e:
        logger.debug(f'empty_working_set failed for pid={pid}: {e}')
        return False


def trim_memory(pid: int = None) -> dict:
    """
    Execute standard memory cleanup trilogy:
    1. gc.collect()
    2. empty_working_set()
    Returns memory statistics dictionary.

    Args:
        pid (int, optional): Process ID. Defaults to current process.

    Returns:
        dict: {
            'rss_before': int,
            'rss_after': int,
            'freed': int
        }
    """
    rss_before = get_process_rss(pid)
    gc.collect()
    empty_working_set(pid)
    rss_after = get_process_rss(pid)
    freed = max(0, rss_before - rss_after)

    return {
        'rss_before': rss_before,
        'rss_after': rss_after,
        'freed': freed
    }
