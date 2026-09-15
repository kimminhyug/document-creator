"""Product-scoped research entry point; execution never approves workflow gates."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

import ai_runner
import collect as collector
import flow
from collector.config import ROOT, load, need, read, scoped
from config_paths import entity_dir
from creator import digest, write_json
from md_contract import validate_artifact

RESEARCH_STAGES = ('intake', 'research_inventory', 'research_architecture',
                   'research_behavior', 'research_data', 'research_reconcile')


def configuration(product, environment):
    config = load(product, environment, root=ROOT)
    folder = entity_dir(ROOT, 'products', product)
    plan = read(folder / 'workflows/default.json')
    company = config['inputs']['company']
    workflow = read(scoped(ROOT / 'workflows', company['workflow'] + '.json'))
    need(tuple(s['id'] for s in workflow['stages'][:6]) == RESEARCH_STAGES,
         'unsupported research stage sequence')
    return config, plan, workflow


def plan_research(product, environment):
    config, plan, workflow = configuration(product, environment)
    team = {**read(ROOT / 'roles/senior-team.json')['members'], **plan.get('team', {})}
    return {'status': 'planned', 'product': product, 'environment': environment,
            'execution': 'dry_run', 'automatic_advance': False,
            'stages': [{'id': s['id'], 'role': s['role'],
                        'artifacts': [{'id': a['id'], 'kind': a['kind'], 'path': a['path'],
                                       'owner': a.get('agent', plan.get('document_teams', {}).get(
                                           a.get('document_type'), {}).get(s['role'], team[s['role']]))}
                                      for a in plan['artifacts'] if a['stage'] == s['id']]}
                       for s in workflow['stages'][:6]],
            'collection': {'requested': False, 'configured_pages': len(config['pages']),
                           'configured_queries': len((config['database'] or {}).get('queries', []))},
            'permissions': {'ai': 'requires_enabled_execution_config_and_explicit_execute',
                            'capture': 'explicit_collect; configured_origins_only',
                            'credential_environment_names': sorted(
                                [config['auth_state_env']] if config.get('auth_state_env') else
                                [config['login'][k] for k in ('username_env', 'password_env')]
                                if config.get('login') else []),
                            'database': 'read_only_approved_queries; explicit_with_db',
                            'database_environment_prefix': (config['database'] or {}).get('connection_env_prefix')},
            'unverified': ['evidence_not_collected', 'artifacts_not_reviewed']}


def bound_configuration(run, product=None, environment=None):
    run = scoped(ROOT / 'workspaces', str(Path(run).resolve()))
    binding = read(run / 'research.json')
    need(product is None or product == binding['product'], 'workspace product mismatch')
    need(environment is None or environment == binding['environment'], 'workspace environment mismatch')
    return configuration(binding['product'], binding['environment'])[0]


def run_state(run, config):
    # Reuse scoped containment and workflow's approved-input integrity checks.
    base = scoped(ROOT / 'workspaces', config['company'] + '/' + config['product'])
    run = scoped(base, str(Path(run).resolve()))
    need(run != base and run.parent == base, 'run must be a product workspace')
    state = read(run / 'state.json')
    need(state['company'] == config['company'] and state['product'] == config['product'],
         'workspace product mismatch')
    binding = read(run / 'research.json')
    need(binding['product'] == config['product'] and binding['environment'] == config['environment'],
         'workspace environment mismatch')
    flow.unchanged(run, state)
    return run, state, binding


def current_research(state):
    phase = state['phase']
    need(type(phase) is int and 0 <= phase < len(state['workflow']['stages']), 'invalid phase')
    stage = state['workflow']['stages'][phase]['id']
    need(phase < 6 and stage == RESEARCH_STAGES[phase], 'research boundary reached; no automatic outline')
    return stage


def status_research(run, config):
    run, state, binding = run_state(run, config)
    try:
        sources = flow.evidence_ids(run)
        source_status = 'verified'
    except (ValueError, OSError, KeyError, TypeError):
        sources = set()
        source_status = 'unverified'
    pending = []
    for record in state['artifacts']:
        if record['stage'] not in RESEARCH_STAGES:
            continue
        try:
            validate_artifact(run, record, state, sources)
        except (ValueError, OSError, KeyError, TypeError):
            pending.append({'artifact': record['id'], 'stage': record['stage'],
                            'status': 'unverified', 'owner': record['agent']})
    phase = state['phase']
    stage = state['workflow']['stages'][phase]['id'] if phase < len(state['workflow']['stages']) else None
    return {'status': 'pending', 'run': str(run), 'product': config['product'],
            'environment': config['environment'], 'current_stage': stage,
            'research_boundary_reached': phase >= 6, 'automatic_advance': False,
            'source_integrity': source_status, 'unverified': pending,
            'last_execution': binding.get('last_execution', 'not_executed'),
            'collection': binding.get('collection', {'status': 'not_collected'}),
            'next_action': 'manual_review_and_flow_advance' if phase < 6 else 'research_stopped'}


def collect_evidence(run, config, with_db):
    need(not with_db or config['database'], 'database collection not configured')
    # Collection credentials stay inside existing collector APIs; never print manifests.
    result = {'status': 'unverified', 'registered_files': 0, 'failed_items': 0,
              'visual_review': 'not_reviewed', 'with_db': with_db}
    try:
        runtime = read(ROOT / '.local/runtime.json')
        directory, manifest = asyncio.run(collector.collect(
            config, runtime, ROOT / 'output/collection', with_db=with_db))
        directory = Path(directory)
        for item in manifest['captures'] + manifest['queries']:
            if item['status'] != 'passed':
                result['failed_items'] += 1
                continue
            files = item.get('files', []) if 'files' in item else [item]
            for file in files:
                source = scoped(directory, file['path'])
                need(digest(source) == file['sha256'], 'collection file changed')
                sid = 'collected-' + hashlib.sha256(
                    (str(directory) + '/' + file['path']).encode()).hexdigest()[:40]
                existing = next((s for s in read(run / 'sources/evidence-index.json') if s['id'] == sid), None)
                if existing:
                    need(existing['sha256'] == file['sha256'] and
                         digest(scoped(run, existing['path'])) == file['sha256'], 'registered evidence differs')
                else:
                    flow.register_source(run, sid, source)
                result['registered_files'] += 1
        result['status'] = ('collected_unreviewed' if manifest['status'] == 'passed'
                            and result['registered_files'] else 'partial_failure')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        result['status'] = 'collection_failed'
    return result


def research(product, environment, action, run=None, execute=False, collect=False, with_db=False):
    need(not collect or execute, '--collect requires --execute')
    need(not with_db or collect, '--with-db requires --collect')
    need(action in ('run', 'resume'), 'unsupported research action')
    config = (bound_configuration(run, product, environment) if action == 'resume'
              else configuration(product, environment)[0])
    need(not with_db or config['database'], 'database collection not configured')
    if action == 'run':
        need(run is None, 'new research cannot reuse a run')
        run = flow.initialize(product)
        write_json(run / 'research.json', {'product': product, 'environment': environment})
    else:
        need(run is not None, 'resume requires run')
    run, state, binding = run_state(run, config)
    current_research(state)
    execution = read(ROOT / 'config/ai/execution.json')
    if collect:
        binding['collection'] = collect_evidence(run, config, with_db)
    # An unavailable adapter is a pending research task, never a completed investigation.
    if execute and execution.get('enabled') is not True:
        binding['last_execution'] = 'execution_disabled'
    else:
        try:
            _, latest, _ = run_state(run, config)
            current_research(latest)
            report = ai_runner.execute_stage(run, execution, execute=execute)
            binding['last_execution'] = report['status']
        except (OSError, ValueError, KeyError, TypeError):
            binding['last_execution'] = 'execution_failed'
    write_json(run / 'research.json', binding)
    return status_research(run, config)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    root = commands.add_parser('research')
    actions = root.add_subparsers(dest='action', required=True)
    for name in ('plan', 'run', 'status', 'resume'):
        a = actions.add_parser(name)
        a.add_argument('--product', required=name in ('plan', 'run'))
        a.add_argument('--environment', required=name in ('plan', 'run'))
        if name in ('status', 'resume'):
            a.add_argument('--run', required=True, type=Path)
        if name in ('run', 'resume'):
            a.add_argument('--execute', action='store_true')
            a.add_argument('--collect', action='store_true')
            a.add_argument('--with-db', action='store_true')
    args = p.parse_args(argv)
    try:
        need(sys.version_info[:2] == (3, 12), 'Python 3.12 required')
        if args.action == 'plan':
            result = plan_research(args.product, args.environment)
        elif args.action == 'status':
            config = bound_configuration(args.run, args.product, args.environment)
            result = status_research(args.run, config)
        else:
            result = research(args.product, args.environment, args.action,
                              getattr(args, 'run', None), args.execute, args.collect, args.with_db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        failed = result.get('last_execution') in ('failed', 'execution_failed', 'execution_disabled')
        failed |= result.get('collection', {}).get('status') in ('partial_failure', 'collection_failed')
        return 1 if failed else 0
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        print('ERROR: research configuration, workspace or runtime check failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
