"""Read-only, bounded CPU/RAM selection for independent keyword workers."""
import os
from pathlib import Path

MAX_WORKERS = 4
MEMORY_PER_WORKER = 2 * 1024**3


def available_memory():
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            class Status(ctypes.Structure):
                _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ('total_physical','available_physical','total_page','available_page',
                     'total_virtual','available_virtual','extended_virtual')]
            status=Status();status.length=ctypes.sizeof(status)
            call=ctypes.WinDLL('kernel32',use_last_error=True).GlobalMemoryStatusEx
            call.argtypes=[ctypes.POINTER(Status)];call.restype=wintypes.BOOL
            return status.available_physical if call(ctypes.byref(status)) else None
        with Path('/proc/meminfo').open('rb') as stream:
            body=stream.read(8192).decode('ascii')
        available=next(int(line.split()[1])*1024 for line in body.splitlines() if line.startswith('MemAvailable:'))
        limit_path=Path('/sys/fs/cgroup/memory.max');used_path=Path('/sys/fs/cgroup/memory.current')
        if limit_path.is_file() and used_path.is_file():
            limit=limit_path.read_text(encoding='ascii').strip()
            if limit!='max':
                available=min(available,max(0,int(limit)-int(used_path.read_text(encoding='ascii'))))
        return available
    except (OSError,ValueError,StopIteration,AttributeError):
        return None


def observe():
    cpus=os.cpu_count() or 1
    try:
        if hasattr(os,'sched_getaffinity'):
            cpus=min(cpus,len(os.sched_getaffinity(0)))
    except OSError:
        cpus=1
    try:
        quota=Path('/sys/fs/cgroup/cpu.max')
        if quota.is_file():
            amount,period=quota.read_text(encoding='ascii').split()
            if amount!='max':
                cpus=min(cpus,max(1,int(amount)//int(period)))
    except (OSError,ValueError,ZeroDivisionError):
        cpus=1
    return {'cpu_count':max(1,cpus),'memory_available_bytes':available_memory()}


def select(mode='auto', observation=None):
    if mode not in ('auto','1','2','3','4'):
        raise ValueError('Unsupported worker selection')
    seen=observe() if observation is None else observation
    cpus=seen['cpu_count'];memory=seen['memory_available_bytes']
    if type(cpus) is not int or not 1<=cpus<=65536 or (memory is not None and (type(memory) is not int or memory<0)):
        raise ValueError('Invalid resource observation')
    capacity=max(1,min(MAX_WORKERS,cpus,0 if memory is None else memory//MEMORY_PER_WORKER))
    workers=capacity if mode=='auto' else int(mode)
    # Explicit one/two-worker mode preserves the previous bounded CLI behavior.
    # More parallelism requires observed CPU and available-memory headroom.
    if workers>2 and workers>capacity:
        raise ValueError('Insufficient observed capacity for requested workers')
    return {'mode':mode,'selected_workers':workers,'maximum_workers':MAX_WORKERS,
            'memory_per_worker_bytes':MEMORY_PER_WORKER,**seen}


def valid_selection(value, workers):
    try:
        if not isinstance(value,dict) or type(workers) is not int:
            return False
        expected=select(value['mode'],{k:value[k] for k in ('cpu_count','memory_available_bytes')})
        return value==expected and workers==expected['selected_workers']
    except (ValueError,KeyError,TypeError):
        return False
