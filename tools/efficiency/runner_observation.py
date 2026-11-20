"""Observe the reviewed standard public-repository ARM runtime before costly CI.

This read-only bootstrap is runtime evidence, never release or business approval.
The ordinary keyword CPU/RAM selection and all acceptance gates remain separate.
"""
import json
import os
from pathlib import Path
import platform
import sys

from keyword_resources import observe as observe_resources, select as select_workers

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes

REPOSITORY = 'azrsk11-maker/BSRS_G-Ad_Codex-'
RUNNER = 'ubuntu-24.04-arm'
MAX_EVENT_BYTES = 1024*1024


def need(condition, code):
    if not condition:
        raise ValueError(code)


def read_event(path):
    with Path(path).open('rb') as stream:
        raw=stream.read(MAX_EVENT_BYTES+1)
    need(0<len(raw)<=MAX_EVENT_BYTES,'EVENT_BYTE_BOUND')
    event=parse_json_bytes(raw)
    need(type(event) is dict,'EVENT_OBJECT_REQUIRED')
    return event


def validate_observation(repository, *, system, machine, version, resources):
    need(type(repository) is dict and repository.get('full_name')==REPOSITORY and
         repository.get('private') is False and repository.get('visibility')=='public',
         'REVIEWED_PUBLIC_REPOSITORY_REQUIRED')
    need(system=='Linux' and machine=='aarch64','REVIEWED_LINUX_ARM_RUNTIME_REQUIRED')
    need(type(version) is tuple and len(version)==3 and all(type(v) is int and v>=0 for v in version)
         and version[:2]==(3,12),'REVIEWED_PYTHON_AST_VERSION_REQUIRED')
    selection=select_workers('auto',resources)
    return {'schema':'bsre-ci-runtime-observation-v1','scope':'STARTUP_OBSERVATION_NOT_RELEASE_ACCEPTANCE',
        'repository':REPOSITORY,'repository_visibility':'public','requested_runner_label':RUNNER,
        'system':system,'machine':machine,'python_version':'.'.join(map(str,version)),
        'startup_worker_selection':selection,'source_body_hash_or_verdict_cache':False,
        'release_authorized':False}


def main():
    try:
        event=read_event(os.environ['GITHUB_EVENT_PATH'])
        result=validate_observation(event.get('repository'),system=platform.system(),
            machine=platform.machine(),version=tuple(sys.version_info[:3]),resources=observe_resources())
    except (OSError,KeyError,ValueError,TypeError):
        # Event bodies, credentials, local paths and exception text are withheld.
        print('CI_RUNTIME_OBSERVATION '+json.dumps({'status':'REJECTED','release_authorized':False}))
        return 1
    print('CI_RUNTIME_OBSERVATION '+json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
