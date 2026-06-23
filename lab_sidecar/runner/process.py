from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


STILL_ACTIVE = 259
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


@dataclass(frozen=True)
class ProcessProbe:
    is_running: bool
    exit_code: int | None = None
    exists: bool | None = None


def command_popen_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def worker_popen_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def probe_process(pid: int) -> ProcessProbe:
    if pid <= 0:
        return ProcessProbe(is_running=False, exists=False)
    if os.name == "nt":
        return _probe_process_windows(pid)
    return _probe_process_posix(pid)


def terminate_process_tree(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False


def _probe_process_posix(pid: int) -> ProcessProbe:
    try:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    except OSError:
        pass
    else:
        if waited_pid == pid:
            return ProcessProbe(is_running=False, exit_code=_posix_exit_code(status), exists=False)
        if waited_pid == 0:
            return ProcessProbe(is_running=True, exists=True)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return ProcessProbe(is_running=False, exists=False)
    except PermissionError:
        return ProcessProbe(is_running=True, exists=True)
    return ProcessProbe(is_running=True, exists=True)


def _posix_exit_code(status: int) -> int | None:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    return None


def _probe_process_windows(pid: int) -> ProcessProbe:
    kernel32 = getattr(ctypes, "WinDLL")("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ProcessProbe(is_running=False, exists=False)

    exit_code = ctypes.c_ulong()
    try:
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        if not ok:
            return ProcessProbe(is_running=False, exists=True)
        code = int(exit_code.value)
        if code == STILL_ACTIVE:
            return ProcessProbe(is_running=True, exists=True)
        return ProcessProbe(is_running=False, exit_code=code, exists=True)
    finally:
        kernel32.CloseHandle(handle)


def current_python_command() -> list[str]:
    return [sys.executable]
