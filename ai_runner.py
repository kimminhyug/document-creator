"""Configurable CLI agents with isolated working copies and bounded process output."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

from collector.config import ROOT, need, read
from creator import digest, write_json
from flow import tasks, advance, unchanged, evidence_ids, locked
from md_contract import metadata_path, validate_artifact
from indexes import refresh


def snapshot(run):
    return {p.relative_to(run).as_posix(): digest(p) for p in run.rglob('*')
            if p.is_file() and not p.is_symlink() and 'agent-runs' not in p.parts and p.name != '.flow.lock'}


def run_process(command, request, cwd, env, timeout):
    output = bytearray()
    overflow = threading.Event()
    kwargs = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    with tempfile.TemporaryFile() as input_file:
        input_file.write(json.dumps(request, ensure_ascii=False).encode('utf-8')); input_file.seek(0)
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=input_file, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **kwargs)
        def consume():
            try:
                while chunk := process.stdout.read(65536):
                    if len(output) + len(chunk) > 1024 * 1024:
                        overflow.set(); return
                    output.extend(chunk)
            except OSError:
                return
        reader = threading.Thread(target=consume, daemon=True); reader.start()
        deadline = time.monotonic() + timeout
        failure = None
        try:
            while process.poll() is None:
                if overflow.is_set() or time.monotonic() >= deadline:
                    failure = 'ResponseTooLarge' if overflow.is_set() else 'Timeout'
                    break
                time.sleep(.05)
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    try: subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True, timeout=5)
                    except subprocess.TimeoutExpired: pass
                else:
                    import signal
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                if process.poll() is None: process.kill()
            process.wait(timeout=5)
            reader.join(timeout=1)
            if reader.is_alive(): failure = failure or 'OutputPipeNotClosed'
            else: process.stdout.close()
        need(not failure and not overflow.is_set(), failure or 'ResponseTooLarge')
        need(process.returncode == 0, 'AgentExited')
    response = json.loads(output)
    need(isinstance(response, dict) and response.get('status') == 'completed', 'InvalidAgentResponse')


def execute_stage(run, config, execute=False):
    run = Path(run).resolve()
    with locked(run):
        state = read(run / 'state.json'); unchanged(run, state)
        packets = tasks(run)
        stage = state['workflow']['stages'][state['phase']]
        records = [a for a in state['artifacts'] if a['stage'] == stage['id']]
        jobs = [(r, config.get('agents', {}).get(r['agent'], config.get('roles', {}).get(r['role'], config.get('default', {})))) for r in records]
        if not execute:
            return {'status':'dry_run','phase':stage['id'],'tasks':[{'artifact':r['path'],'agent':r['agent'],'configured':bool(a.get('command'))} for r,a in jobs]}
        need(config.get('enabled') is True, 'agent execution disabled')
        workers=config.get('workers',2); timeout=config.get('timeout_seconds',300)
        need(type(workers) is int and 1 <= workers <= 8, 'workers must be 1..8')
        need(type(timeout) is int and 1 <= timeout <= 3600, 'timeout must be 1..3600')
        runtime=read(ROOT/'.local/runtime.json') if (ROOT/'.local/runtime.json').exists() else {}
        before=snapshot(run)
        out=run/'agent-runs'/(stage['id']+'-'+uuid4().hex[:8]);out.mkdir(parents=True)
        # This is isolation for accidental cross-writes, not an OS security sandbox.
        def invoke(job):
            record, adapter=job
            result={'artifact':record['path'],'agent':record['agent'],'status':'failed'}
            try:
                with tempfile.TemporaryDirectory(prefix='document-agent-') as tmp:
                    copy=Path(tmp)/'workspace'
                    shutil.copytree(run,copy,ignore=shutil.ignore_patterns('.flow.lock','agent-runs'),symlinks=True)
                    need(not any(p.is_symlink() for p in copy.rglob('*')), 'WorkspaceSymlink')
                    initial=snapshot(copy)
                    allowed=[record['path'],metadata_path(copy/record['path'],copy).relative_to(copy).as_posix()]
                    values={'root':str(ROOT),'run':str(copy),'artifact':str(copy/record['path']),'task':str(copy/packets.relative_to(run)/(record['id']+'.md'))}
                    command=adapter.get('command',[])
                    need(isinstance(command,list) and command and all(isinstance(s,str) for s in command), 'MissingCommand')
                    command=[runtime.get(s[8:],'') if s.startswith('runtime:') else s.format_map(values) for s in command]
                    need(command[0], 'MissingExecutable')
                    env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','APPDATA','LOCALAPPDATA','PATHEXT'}}
                    for name in adapter.get('pass_env',[]):
                        need(isinstance(name,str) and name in os.environ,'MissingEnvironment')
                        env[name]=os.environ[name]
                    request={'protocol':'document-agent/v1','workspace':str(copy),'artifact':record['path'],'metadata':allowed[1], 'prompt':(Path(values['task'])).read_text(encoding='utf-8'),'index':'INDEX.md','allowed_write_paths':allowed}
                    run_process(command,request,copy,env,timeout)
                    final=snapshot(copy)
                    changed={p for p in initial.keys()|final.keys() if initial.get(p)!=final.get(p)}
                    need(changed <= set(allowed),'OwnershipViolation')
                    need(all((copy/p).is_file() and not (copy/p).is_symlink() for p in allowed),'OwnedFileMissing')
                    result.update(status='completed',files={p:(copy/p).read_bytes() for p in allowed})
            except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):
                result['error']='AgentFailed'
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results=list(pool.map(invoke,jobs))
        after=snapshot(run)
        violations=sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))
        passed=not violations and all(r['status']=='completed' for r in results)
        if not violations:
            for result in results:
                for name,data in result.get('files',{}).items(): (run/name).write_bytes(data)
        for result in results: result.pop('files',None)
        errors=[]
        if passed:
            try:
                sources=evidence_ids(run)
                for record,_ in jobs: validate_artifact(run,record,state,sources)
            except (ValueError,KeyError,OSError):
                passed=False;errors.append('ArtifactGateFailed')
        report={'status':'passed' if passed else 'failed','phase':stage['id'],'results':results,'unexpected_writes':violations,'errors':errors,'automatic_retry':False}
        write_json(out/'result.json',report);refresh(run)
        return report


def main():
    need(sys.version_info[:2]==(3,12),'Python 3.12 required')
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);p.add_argument('--config',type=Path,default=ROOT/'config/ai/execution.json');p.add_argument('--execute',action='store_true');p.add_argument('--advance',action='store_true');p.add_argument('--until-complete',action='store_true')
    args=p.parse_args();config=read(args.config)
    while True:
        report=execute_stage(args.run,config,args.execute);print(json.dumps(report,ensure_ascii=False,indent=2))
        if report['status']!='passed' or not(args.advance or args.until_complete):return 1 if report['status']=='failed' else 0
        state=read(args.run/'state.json');stage=state['workflow']['stages'][state['phase']]
        advance(args.run,state['team'][stage['role']])
        if not args.until_complete or state['phase']+1==len(state['workflow']['stages']):return 0

if __name__=='__main__':sys.exit(main())
