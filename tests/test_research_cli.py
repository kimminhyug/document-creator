import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import document
import flow
from collector.config import ROOT, load, read
from creator import digest, write_json
from md_contract import parse, write_artifact


class ResearchCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config, self.plan, self.workflow = document.configuration('demo', 'local')
        for name in ('config/ai', 'roles'):
            shutil.copytree(ROOT / name, self.root / name)
        self.initialize = flow.initialize
        self.patches = [patch.object(document, 'ROOT', self.root),
                        patch.object(document, 'configuration', return_value=(self.config, self.plan, self.workflow)),
                        patch.object(document.flow, 'initialize', side_effect=lambda product: self.initialize(
                            product, base=self.root / 'workspaces'))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def new_run(self):
        return Path(document.research('demo', 'local', 'run')['run'])

    def test_plan_is_readonly_and_lists_owned_paths(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        with patch.object(document.ai_runner, 'execute_stage') as execute, patch.object(document.collector, 'collect') as collect:
            result = document.plan_research('demo', 'local')
        self.assertEqual(len(result['stages']), 6)
        self.assertIn('owner', result['stages'][0]['artifacts'][0])
        self.assertIn('path', result['stages'][0]['artifacts'][0])
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        execute.assert_not_called(); collect.assert_not_called()

    def test_dry_run_initializes_without_launching_agents_or_collecting(self):
        with patch.object(document.ai_runner, 'run_process') as process, patch.object(document.collector, 'collect') as collect:
            result = document.research('demo', 'local', 'run')
        self.assertEqual(result['last_execution'], 'dry_run')
        self.assertEqual(result['status'], 'pending')
        self.assertTrue(result['unverified'])
        self.assertEqual(read(Path(result['run']) / 'state.json')['phase'], 0)
        process.assert_not_called(); collect.assert_not_called()

    def test_resume_restores_binding_and_retries_without_advancing(self):
        run = self.new_run()
        write_json(self.root / 'config/ai/execution.json', {'enabled': True})
        with patch.object(document.ai_runner, 'execute_stage', side_effect=[{'status': 'failed'}, {'status': 'passed'}]) as execute:
            first = document.research(None, None, 'resume', run, execute=True)
            second = document.research(None, None, 'resume', run, execute=True)
        self.assertEqual(first['last_execution'], 'failed')
        self.assertEqual(second['last_execution'], 'passed')
        self.assertEqual(second['status'], 'pending')
        self.assertEqual(read(run / 'state.json')['phase'], 0)
        self.assertEqual(execute.call_count, 2)

    def test_wrong_product_environment_and_escape_rejected(self):
        run = self.new_run()
        for product, env in [('other', None), (None, 'other')]:
            with self.assertRaises(ValueError):
                document.research(product, env, 'resume', run)
        with self.assertRaises(ValueError):
            document.bound_configuration(self.root.parent)

    def test_outline_is_hard_boundary(self):
        run = self.new_run(); state = read(run / 'state.json'); state['phase'] = 6
        write_json(run / 'state.json', state)
        with patch.object(document.ai_runner, 'execute_stage') as execute:
            with self.assertRaisesRegex(ValueError, 'boundary'):
                document.research(None, None, 'resume', run, execute=True)
        execute.assert_not_called()

    def test_approved_artifact_tampering_blocks_resume(self):
        run = self.new_run()
        source = self.root / 'request.md'; source.write_text('Approved scope', encoding='utf-8')
        flow.register_source(run, 'request', source)
        record = read(run / 'state.json')['artifacts'][0]; file = run / record['path']
        meta, body = parse(file); meta.update(status='confirmed', sources=['request'])
        write_artifact(file, meta, body.replace('작성 필요', 'Grounded scope'))
        flow.advance(run, 'document-lead')
        file.write_text(body + '\nchanged', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            document.research(None, None, 'resume', run)

    def test_collection_flags_require_explicit_execute_and_collect(self):
        for options in [{'collect': True}, {'with_db': True, 'execute': True}]:
            with self.assertRaises(ValueError):
                document.research('demo', 'local', 'run', **options)
        self.assertFalse((self.root / 'workspaces').exists())

    def test_disabled_execution_stays_pending(self):
        with patch.object(document.ai_runner, 'execute_stage') as execute:
            result = document.research('demo', 'local', 'run', execute=True)
        self.assertEqual(result['last_execution'], 'execution_disabled')
        self.assertEqual(result['status'], 'pending'); execute.assert_not_called()

    def test_partial_collection_registers_only_passed_and_same_hash_retry(self):
        run = self.new_run()
        directory = self.root / 'output/collection/demo/local/evidence'
        directory.mkdir(parents=True)
        good = directory / 'page.png'; good.write_bytes(b'test-evidence')
        (self.root / '.local').mkdir(); write_json(self.root / '.local/runtime.json', {})
        manifest = {'status': 'partial_failure', 'captures': [
            {'id': 'good', 'status': 'passed', 'files': [{'path': 'page.png', 'sha256': digest(good)}]},
            {'id': 'bad', 'status': 'failed', 'error': 'SECRET_DO_NOT_PRINT'}], 'queries': []}
        with patch.object(document.collector, 'collect', new=AsyncMock(return_value=(directory, manifest))):
            a = document.collect_evidence(run, self.config, False)
            b = document.collect_evidence(run, self.config, False)
        self.assertEqual(a['status'], 'partial_failure')
        self.assertEqual(b['registered_files'], 1)
        self.assertEqual(len(read(run / 'sources/evidence-index.json')), 1)
        self.assertNotIn('SECRET', json.dumps(a))

    def test_unavailable_collection_is_not_completed(self):
        run = self.new_run()
        result = document.collect_evidence(run, self.config, False)
        self.assertEqual(result['status'], 'collection_failed')
        self.assertEqual(result['registered_files'], 0)

    def test_status_is_readonly_and_cli_does_not_print_exception_secrets(self):
        run = self.new_run(); before = {str(p): digest(p) for p in run.rglob('*') if p.is_file()}
        with patch.object(document.ai_runner, 'execute_stage') as execute:
            document.status_research(run, self.config)
        self.assertEqual(before, {str(p): digest(p) for p in run.rglob('*') if p.is_file()})
        execute.assert_not_called()
        error = io.StringIO()
        with patch.object(document, 'configuration', side_effect=ValueError('SECRET_DO_NOT_PRINT')), contextlib.redirect_stderr(error):
            code = document.main(['research', 'plan', '--product', 'demo', '--environment', 'local'])
        self.assertEqual(code, 2); self.assertNotIn('SECRET', error.getvalue())


class ConfigurationIntegrationTests(unittest.TestCase):
    def test_real_loader_rejects_wrong_environment_and_unsafe_identifiers(self):
        for product, env in [('demo', 'missing'), ('../demo', 'local')]:
            with self.assertRaises((ValueError, OSError)):
                document.configuration(product, env)


if __name__ == '__main__':
    unittest.main()
