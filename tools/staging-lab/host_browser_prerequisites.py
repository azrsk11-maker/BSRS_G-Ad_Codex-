"""Informational, non-root host namespace probe; never start WordPress/browser.

Uses only preinstalled util-linux/Python. No installs, network connections,
host policy changes, secrets, application data or acceptance authority.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

CHECKS = ('uid_preserved', 'nonroot', 'user_namespace_changed',
          'network_namespace_changed', 'mount_namespace_changed',
          'no_new_privileges', 'loopback_only_interfaces',
          'no_nonloopback_ipv4_routes', 'no_nonloopback_ipv6_routes')
CHILD = r'''
import json,os,re,sys
from pathlib import Path
parent=json.loads(sys.argv[1])
ns=lambda name:os.readlink('/proc/self/ns/'+name)
status=Path('/proc/self/status').read_text()
interfaces={line.split(':',1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines() if ':' in line}
ipv4=[line.split() for line in Path('/proc/net/route').read_text().splitlines()[1:] if line.strip()]
ipv6=[line.split() for line in Path('/proc/net/ipv6_route').read_text().splitlines() if line.strip()]
print(json.dumps({
 'uid_preserved':os.getuid()==parent['uid'] and os.geteuid()==parent['euid'],
 'nonroot':os.getuid()!=0 and os.geteuid()!=0,
 'user_namespace_changed':ns('user')!=parent['user'],
 'network_namespace_changed':ns('net')!=parent['net'],
 'mount_namespace_changed':ns('mnt')!=parent['mnt'],
 'no_new_privileges':bool(re.search(r'^NoNewPrivs:\s*1$',status,re.M)),
 'loopback_only_interfaces':interfaces=={'lo'},
 'no_nonloopback_ipv4_routes':all(row[0]=='lo' for row in ipv4),
 'no_nonloopback_ipv6_routes':all(row[-1]=='lo' for row in ipv6),
}))
'''


def _binary(name):
    for folder in ('/usr/bin', '/bin'):
        path = Path(folder) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def _baseline():
    return {'uid': os.getuid(), 'euid': os.geteuid(),
            **{name: os.readlink('/proc/self/ns/' + name) for name in ('user', 'net', 'mnt')}}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate probe field')
        result[key] = value
    return result


def observe():
    receipt = {'version': 1, 'phase': 'host_browser_prerequisites',
               'scope': 'INFORMATIONAL_HOST_NAMESPACE_OBSERVATION_ONLY',
               'status': 'NOT_OBSERVED', 'checks': {},
               'browser_started': False, 'wordpress_started': False,
               'browser_runtime_accepted': False, 'host_security_settings_changed': False,
               'existing_container_controls_changed': False,
               'outbound_connections_attempted': 0, 'software_installed': False,
               'production_changes': False, 'release_authorized': False}
    if sys.platform != 'linux':
        return dict(receipt, status='UNSUPPORTED_PLATFORM')
    if os.getuid() == 0 or os.geteuid() == 0:
        return dict(receipt, status='ROOT_EXECUTION_REJECTED')
    setpriv, unshare = _binary('setpriv'), _binary('unshare')
    if not setpriv or not unshare:
        return dict(receipt, status='COMMAND_UNAVAILABLE')
    try:
        baseline = _baseline()
        # No --fork or shell: wrappers exec the single read-only Python probe.
        command = [setpriv, '--no-new-privs', unshare, '--user',
                   '--map-current-user', '--net', '--mount', sys.executable,
                   '-I', '-c', CHILD, json.dumps(baseline, sort_keys=True)]
        process = subprocess.run(command, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                                 timeout=3, check=False, start_new_session=True)
    except subprocess.TimeoutExpired:
        return dict(receipt, status='TIMED_OUT')
    except OSError:
        return dict(receipt, status='PROBE_START_OR_METADATA_FAILED')
    if len(process.stdout) + len(process.stderr) > 8192:
        return dict(receipt, status='OVERSIZED_CHILD_OUTPUT')
    if process.returncode != 0:
        return dict(receipt, status='DENIED_OR_FAILED', exit_code=process.returncode,
                    operation_not_permitted_reported=b'Operation not permitted' in process.stderr)
    try:
        checks = json.loads(process.stdout.decode('utf-8'), object_pairs_hook=_unique)
        if (not isinstance(checks, dict) or set(checks) != set(CHECKS) or
                any(type(value) is not bool for value in checks.values())):
            raise ValueError('Incomplete or invalid probe fields')
    except (UnicodeError, ValueError):
        return dict(receipt, status='MALFORMED_CHILD_OUTPUT')
    return dict(receipt, status='NAMESPACE_PREREQUISITES_OBSERVED' if all(checks.values())
                else 'NAMESPACE_INVARIANT_NOT_VERIFIED', checks=checks)


if __name__ == '__main__':
    # An informational result never substitutes for browser acceptance or the
    # mandatory isolated-container checks, including on a compatible host.
    print(json.dumps(observe(), sort_keys=True))
