import json
from pathlib import Path
import sys
import tempfile
import unittest
from ai_runner import execute_stage
from collector.config import read
from creator import write_json
from flow import initialize, register_source, advance, tasks, add_artifact
from md_contract import parse, write_artifact, metadata_path, validate_artifact


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.run = initialize('demo', base=self.base)

    def tearDown(self):
        self.temp.cleanup()

    def test_readable_markdown_and_nested_indexes(self):
        path = self.run / 'scope/scope-001.md'
        self.assertTrue(path.read_text(encoding='utf-8').startswith('# '))
        self.assertNotIn('sources', path.read_text(encoding='utf-8'))
        self.assertTrue(metadata_path(path).is_file())
        self.assertTrue((self.run / 'research/data/tables/INDEX.md').is_file())

    def test_sidecar_change_invalidates_approval(self):
        path = self.run / 'scope/scope-001.md'
        source = self.base / 'request.md'; source.write_text('문서 작성 요청', encoding='utf-8')
        register_source(self.run, 'request', source)
        meta, body = parse(path); meta.update(status='confirmed', sources=['request'])
        write_artifact(path, meta, body.replace('작성 필요', '요청 범위 확인'))
        advance(self.run, 'document-lead')
        meta['author'] = 'someone-else'; write_artifact(path, meta, body)
        with self.assertRaisesRegex(ValueError, 'changed'): tasks(self.run)

    def test_publish_cannot_skip_actual_output(self):
        state = read(self.run / 'state.json')
        record = next(r for r in state['artifacts'] if r['kind'] == 'publish')
        path = self.run / record['path']; meta, body = parse(path)
        meta.update(status='not_applicable', reason='건너뛰기')
        write_artifact(path, meta, body)
        with self.assertRaisesRegex(ValueError, 'cannot be skipped'):
            validate_artifact(self.run, record, state, set())

    def test_new_research_is_classified_and_indexed(self):
        record = {'id': 'api-inventory', 'kind': 'api', 'stage': 'research_data', 'path': 'research/data/apis/inventory.md', 'title': '재고 조회 API'}
        add_artifact(self.run, record, 'document-lead')
        self.assertTrue((self.run / record['path']).exists())
        self.assertIn('재고 조회 API', (self.run / 'research/data/apis/INDEX.md').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            add_artifact(self.run, record, 'document-lead')

    def adapter(self, code):
        worker = self.base / 'worker.py'; worker.write_text(code, encoding='utf-8')
        return {'enabled': True, 'workers': 2, 'timeout_seconds': 2, 'default': {'command': [sys.executable, str(worker)]}}

    def test_runner_dryrun_and_malformed_response_record_failure(self):
        self.assertEqual(execute_stage(self.run, {})['status'], 'dry_run')
        report = execute_stage(self.run, self.adapter('print("[]")'), True)
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(list((self.run / 'agent-runs').rglob('result.json')))
        self.assertFalse((self.run / '.flow.lock').exists())

    def test_runner_cannot_modify_another_owned_artifact(self):
        original = self.run / 'research/inventory/inventory-001.md'
        expected = original.read_bytes()
        config = self.adapter("import json,sys\nfrom pathlib import Path\nr=json.load(sys.stdin)\nPath('research/inventory/inventory-001.md').write_text('overwrite')\nprint(json.dumps({'status':'completed'}))")
        report = execute_stage(self.run, config, True)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(original.read_bytes(), expected)

    def test_runner_executes_and_imports_owned_draft(self):
        config = self.adapter("import json,sys\nfrom pathlib import Path\nr=json.load(sys.stdin)\np=Path(r['artifact'])\np.write_text(p.read_text(encoding='utf-8')+'\\n조사 진행 중\\n',encoding='utf-8')\nprint(json.dumps({'status':'completed'}))")
        report = execute_stage(self.run, config, True)
        self.assertEqual(report['results'][0]['status'], 'completed')
        self.assertEqual(report['errors'], ['ArtifactGateFailed'])
        self.assertIn('조사 진행 중', (self.run / 'scope/scope-001.md').read_text(encoding='utf-8'))

    def test_runner_timeout_and_missing_env_leave_failed_report(self):
        config = self.adapter('import time\ntime.sleep(10)'); config['timeout_seconds'] = 1
        self.assertEqual(execute_stage(self.run, config, True)['status'], 'failed')
        config['default']['pass_env'] = ['DOCUMENT_CREATOR_TEST_MISSING_VARIABLE']
        self.assertEqual(execute_stage(self.run, config, True)['status'], 'failed')
        self.assertFalse((self.run / '.flow.lock').exists())
