"""Own one gated Python process tree without changing host process settings.

Windows job membership is established before the child can import tests/spawn.
POSIX descendants inherit one new session/group, killed on timeout and cleanup.
Only the Windows job also contains descendants if this supervisor is killed.
"""
import ctypes
import json
import os
import signal
import subprocess
import time


IS_WINDOWS = os.name == "nt"
GATE = "KEYWORD_OWNED_TREE_V1"


class ContainmentError(OSError):
    """The child was not allowed to execute without process-tree containment."""


class WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("minimum", ctypes.c_size_t),
                        ("maximum", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Limits(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.SetInformationJobObject.restype = w.BOOL
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.AssignProcessToJobObject.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        # NULL security attributes: unnamed handle, not inheritable by children.
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ContainmentError(ctypes.get_last_error(), "Cannot create owned process job")
        limits = Limits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise ContainmentError(error, "Cannot enforce owned process job")

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ContainmentError(ctypes.get_last_error(), "Cannot assign gated process to owned job")

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            self.api.CloseHandle(handle)


def terminate_tree(process, job):
    if job is not None:
        job.close()
    else:
        try:
            os.killpg(process.pid, getattr(signal, "SIGKILL", 9))
        except ProcessLookupError:
            pass


def run_owned(args, *, cwd, timeout, deadline=None):
    """Like captured subprocess.run, but child must consume the startup gate.

    One deadline includes containment setup, spawn and all descendant work.
    Reaping after that deadline cannot make the acceptance outcome successful.
    """
    deadline = min(deadline, time.monotonic() + timeout) if deadline is not None else time.monotonic() + timeout
    if deadline <= time.monotonic():
        raise subprocess.TimeoutExpired(args, timeout)
    job = WindowsJob() if IS_WINDOWS else None
    process = None
    assigned = False
    try:
        process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True, start_new_session=not IS_WINDOWS)
        if job is not None:
            job.assign(process)
        assigned = True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, timeout)
        gate = (json.dumps({"gate": GATE, "deadline": deadline}) + "\n").encode("ascii")
        try:
            stdout, stderr = process.communicate(input=gate, timeout=remaining)
        except subprocess.TimeoutExpired:
            terminate_tree(process, job)
            stdout, stderr = process.communicate(timeout=5)
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr) from None
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(args, process.returncode,
                                          stdout.decode("utf-8", errors="replace"),
                                          stderr.decode("utf-8", errors="replace"))
    finally:
        if process is not None:
            if assigned:
                terminate_tree(process, job)
            else:
                # Assignment failed: the gate has not been released. A job cannot
                # kill this unassigned process, so terminate and reap it directly.
                process.kill()
            if process.poll() is None:
                process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        if job is not None:
            job.close()
