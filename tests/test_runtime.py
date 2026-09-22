"""Offline runtime checks; no credentials, agent processes, or cloud calls."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from agent_swarm import backend, runtime

# Load this checkout's experiment even while migration leaves a duplicate in
# the sibling repository. Never run main as part of loading the module.
CEDAR_PATH = Path(__file__).resolve().parents[1]/'experiments'/'cedar_coordination'/'run.py'
spec = importlib.util.spec_from_file_location('cedar_runtime_test_target', CEDAR_PATH)
cedar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cedar)


def result(stdout='', ok=True, stderr=''):
    return SimpleNamespace(stdout=stdout, ok=ok, stderr=stderr)


class RuntimeTests(unittest.TestCase):
    def test_launch_supports_arbitrary_agent_names_and_uids(self):
        sandbox = mock.Mock()
        sandbox.exec.return_value = result()
        names = ['atlas', 'birch_2', 'cobalt-3', 'delta']
        runtime.launch_agents(sandbox, names, first_uid=12001)
        command = sandbox.exec.call_args.args[0]
        self.assertEqual(command[:2], ['python3', '-c'])
        # Execute only the small launcher script with all process/file APIs mocked.
        with mock.patch('sys.argv', ['-c', *command[3:]]), \
             mock.patch('subprocess.Popen') as popen, \
             mock.patch('builtins.open', mock.mock_open()):
            exec(compile(command[2], '<launcher>', 'exec'), {})
        self.assertEqual(popen.call_count, len(names))
        for offset, call in enumerate(popen.call_args_list):
            self.assertEqual(call.args[0], ['python3', '/root/launch.py', names[offset], str(12001+offset)])
            self.assertTrue(call.kwargs['start_new_session'])

    def test_reject_invalid_names_before_dispatch(self):
        sandbox = mock.Mock()
        for names in ([], ['same', 'same'], ['../outside'], ['a; echo bad'], ['Mixed'], ['']):
            with self.subTest(names=names), self.assertRaises(ValueError):
                runtime.launch_agents(sandbox, names)
        sandbox.exec.assert_not_called()

    def test_poll_waits_for_every_agent_and_returns_exit_codes(self):
        sandbox = mock.Mock()
        partial = {'atlas-exit.json': {'exit_code': 0}}
        complete = dict(partial, **{'birch-exit.json': {'exit_code': 124}})
        sandbox.exec.side_effect = [result('{}'), result(json.dumps(partial)), result(json.dumps(complete))]
        with mock.patch.object(runtime.time, 'sleep') as sleep, contextlib.redirect_stdout(io.StringIO()):
            exits = runtime.wait_agents(sandbox, 2, 100, poll_seconds=3)
        self.assertEqual(exits, complete)
        self.assertEqual(sleep.call_args_list, [mock.call(3), mock.call(3)])

    def test_poll_deadline_and_command_failure(self):
        sandbox = mock.Mock()
        with mock.patch.object(runtime.time, 'monotonic', side_effect=[0, 46]):
            with self.assertRaises(TimeoutError):
                runtime.wait_agents(sandbox, 1, 0)
        sandbox.exec.assert_not_called()
        sandbox.exec.return_value = result(ok=False, stderr='read failed')
        with self.assertRaisesRegex(RuntimeError, 'read failed'):
            runtime.wait_agents(sandbox, 1, 1)

    def test_collection_attempts_all_archives_and_stops_after_failure(self):
        sandbox = mock.Mock()
        sandbox.export_directory.side_effect = [OSError('first archive failed'), None, None]
        summary = {}
        runtime.collect(sandbox, Path('/offline-output'), summary)
        self.assertEqual([c.args[0] for c in sandbox.export_directory.call_args_list],
                         ['/private-run', '/workspaces', '/home'])
        sandbox.stop.assert_called_once_with()
        self.assertEqual(summary['collection_errors'], ['first archive failed'])
        self.assertTrue(summary['sandbox_stop_requested'])

    def test_collection_records_stop_failure(self):
        sandbox = mock.Mock()
        sandbox.stop.side_effect = OSError('stop failed')
        summary = {}
        runtime.collect(sandbox, Path('/offline-output'), summary)
        self.assertEqual(summary['cleanup_error'], 'stop failed')
        self.assertNotIn('sandbox_stop_requested', summary)


class BackendTests(unittest.TestCase):
    def test_environment_key_does_not_read_provider_configuration(self):
        with mock.patch.dict(backend.os.environ, {'ZAI_CODING_PLAN_API_KEY': 'offline-test-key'}, clear=True), \
             mock.patch.object(Path, 'read_text', side_effect=AssertionError('unexpected file access')):
            self.assertEqual(backend.zai_key(), 'offline-test-key')

    def test_provider_configuration_fallback_selects_zai(self):
        fixture = {'config': {'providerConfigRules': {'providerRules': [
            {'providerId': 'other', 'config': {'access': {'apiKey': 'wrong'}}},
            {'providerId': 'zai-api', 'config': {'access': {'apiKey': 'offline-test-key'}}},
        ]}}}
        with mock.patch.dict(backend.os.environ, {}, clear=True), \
             mock.patch.object(Path, 'read_text', return_value=json.dumps(fixture)):
            self.assertEqual(backend.zai_key(), 'offline-test-key')

    def test_environment_load_order_preserves_shell_token(self):
        with mock.patch.dict(backend.os.environ, {'VERCEL_TOKEN': 'offline-test-token'}, clear=True), \
             mock.patch.object(backend, 'load_env') as load_env, \
             mock.patch.object(Path, 'read_text', side_effect=AssertionError('unexpected auth access')):
            backend.load_environment()
        self.assertEqual(load_env.call_args_list, [mock.call(backend.ROOT), mock.call(backend.MINIEVAL_ROOT)])


class CedarMigrationTests(unittest.TestCase):
    def test_original_prompt_and_briefs_preserved_exactly(self):
        # Fingerprint captured from the original minimal-eval Cedar run.py.
        # Deliberately independent of its former path after the experiment moves.
        source = json.dumps({'PROMPT': cedar.PROMPT, 'BRIEFS': cedar.BRIEFS}, sort_keys=True)
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         '288d0f5a4089c826a0add9a94ee8d4baddb1d12aaa006e9e13c991b8329291d7')

    def test_fake_sandbox_run_keeps_preflight_before_launch_and_collects(self):
        sandbox = mock.Mock()
        sandbox.sandbox_id = 'offline-sandbox'
        exits = {name+'-exit.json': {'exit_code': 0} for name in cedar.BRIEFS}
        history = []

        def execute(command, **kwargs):
            history.append(command)
            if command == ['cat', '/private-run/state.json']:
                return result(json.dumps({'release': {'receipt_id': 'offline-receipt'}}))
            if command[:2] == ['python3', '-c'] and "glob('*-exit.json')" in command[2]:
                return result(json.dumps(exits))
            return result()

        sandbox.exec.side_effect = execute
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root/'assets'
            assets.mkdir()
            (assets/'dependencies.json').write_text('{}')
            (assets/'zcode.cjs').write_text('// offline fixture')
            with mock.patch.object(cedar, 'ROOT', root), \
                 mock.patch.object(cedar, 'load_environment'), \
                 mock.patch.object(cedar, 'zai_key', return_value='offline-test-key'), \
                 mock.patch.object(cedar, 'zcode_files', return_value=assets), \
                 mock.patch.object(cedar, 'install_dependencies'), \
                 mock.patch.object(cedar, 'create_sandbox', return_value=sandbox), \
                 contextlib.redirect_stdout(io.StringIO()):
                cedar.main()
            summary = json.loads(next((root/'runs'/'cedar_coordination').glob('*/summary.json')).read_text())
            self.assertEqual(summary['status'], 'completed')
            self.assertTrue(summary['passed'])
            self.assertEqual(summary['model'], 'glm-5.3-flash')
            self.assertEqual(summary['agent_exits'], exits)
            self.assertTrue(summary['sandbox_stop_requested'])
        uploaded = sandbox.write_files.call_args.args[0]
        config = json.loads(uploaded['/root/launch.json'])
        self.assertEqual(config['prompt'], cedar.PROMPT)
        self.assertEqual(config['model'], 'glm-5.3-flash')
        for name, brief in cedar.BRIEFS.items():
            self.assertEqual(uploaded[f'/workspaces/{name}/HANDOVER.md'], brief)
        preflight_index = next(i for i, cmd in enumerate(history) if cmd[0] == 'setpriv')
        launch_index = next(i for i, cmd in enumerate(history) if cmd[:2] == ['python3', '-c'] and 'subprocess.Popen' in cmd[2])
        self.assertLess(preflight_index, launch_index)
        sandbox.stop.assert_called_once_with()
        self.assertEqual(sandbox.export_directory.call_count, 3)


if __name__ == '__main__':
    unittest.main()
