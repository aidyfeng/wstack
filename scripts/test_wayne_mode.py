import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'hooks' / 'wayne_mode.py'


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.base), HOME=str(self.base), USERPROFILE=str(self.base), APPDATA=str(self.base))
        if sys.platform == 'darwin':
            self.state = self.base / 'Library' / 'Application Support' / 'wstack' / 'wayne-mode'
        else:
            self.state = self.base / 'wstack' / 'wayne-mode'

    def call(self, sid='a', prompt='', event='UserPromptSubmit', client='codex', raw=None, script=SCRIPT, **extra):
        data = {'session_id': sid, 'prompt': prompt, 'hook_event_name': event, **extra}
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), client], input=json.dumps(data) if raw is None else raw, text=True, encoding='utf-8', capture_output=True, env=self.env, check=True)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def context(self, *args, **kwargs):
        return self.call(*args, **kwargs)['hookSpecificOutput']['additionalContext']

    def test_injection_and_snapshots(self):
        text = self.context(event='SessionStart')
        self.assertIn((ROOT / 'skills/wayne-mode/SKILL.md').read_text(encoding='utf-8'), text)
        self.assertIn(str(ROOT / 'skills/wayne-mode'), text)
        self.assertIn('当前会话：关闭', self.context(prompt=' /wayne-mode off\t'))
        self.assertIn('当前会话：关闭', self.context(prompt='/wayne-mode status'))
        self.assertIn('已关闭', self.context(event='SessionStart', source='resume'))
        self.assertIn('已关闭', self.context(event='SessionStart', source='compact'))
        self.assertIn('已关闭', self.context(prompt='普通消息'))
        self.assertIn('当前会话：关闭', self.context(prompt='/wayne-mode default on'))
        self.assertIn('# wayne-mode', self.context(prompt='/wstack:wayne-mode on'))
        self.assertIn('当前会话：开启', self.context(prompt='/wayne-mode default off'))
        self.assertIn('# wayne-mode', self.context(prompt='普通消息'))
        self.assertIn('已关闭', self.context(sid='b', event='SessionStart'))
        self.assertIn('当前会话：关闭', self.context(sid='b', prompt='/wayne-mode default on'))
        self.assertIn('已关闭', self.context(sid='b', prompt='普通消息'))
        self.assertIn('# wayne-mode', self.context(sid='c', event='SessionStart'))
        self.assertIn('# wayne-mode', self.context(client='claude', event='SessionStart'))
        for path in (self.state / 'sessions').iterdir():
            self.assertRegex(path.name, r'^(claude|codex)-[a-f0-9]{64}\.json$')
            self.assertEqual(set(json.loads(path.read_text(encoding='utf-8'))), {'enabled'})
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_strict_commands(self):
        for prompt in ('解释 /wayne-mode off', '/wayne-mode off\n', '```\n/wayne-mode off\n```', '/wayne-mode off 做任务', '/wayne-mode off extra', '/wayne-mode default off extra'):
            with self.subTest(prompt=prompt):
                self.assertNotIn('控制命令', self.context(prompt=prompt))
                self.assertIn('当前会话：开启', self.context(prompt='/wayne-mode status'))
        for prompt in ('/wayne-mode', '/wayne-mode nonsense', '/wayne-mode default maybe'):
            self.assertIn('用法：', self.context(prompt=prompt))
            self.assertIn('当前会话：开启', self.context(prompt='/wayne-mode status'))

    def test_fail_open(self):
        self.assertIn('systemMessage', self.call(raw='{'))
        self.assertIn('systemMessage', self.call(sid=None))
        self.state.mkdir(parents=True)
        for bad in ('{', '[]', '{"default": "true"}'):
            (self.state / 'config.json').write_text(bad, encoding='utf-8')
            self.assertIn('systemMessage', self.call())
        (self.state / 'config.json').unlink()
        sessions = self.state / 'sessions'
        sessions.mkdir()
        path = sessions / ('codex-' + hashlib.sha256(b'a').hexdigest() + '.json')
        for bad in ('{', '[]', '{"enabled": 1}'):
            path.write_text(bad, encoding='utf-8')
            self.assertIn('systemMessage', self.call())
        path.unlink()
        sessions.rmdir()
        sessions.write_text('阻止创建目录', encoding='utf-8')
        self.assertIn('systemMessage', self.call())
        copied = self.base / 'plugin' / 'hooks' / 'wayne_mode.py'
        copied.parent.mkdir(parents=True)
        shutil.copy(SCRIPT, copied)
        sessions.unlink()
        self.assertIn('systemMessage', self.call(script=copied))

    def test_manifest_commands(self):
        plugin = self.base / '插件 copy with spaces'
        shutil.copytree(ROOT / 'hooks', plugin / 'hooks')
        shutil.copytree(ROOT / 'skills' / 'wayne-mode', plugin / 'skills' / 'wayne-mode')
        env = dict(self.env, PLUGIN_ROOT=str(plugin), CLAUDE_PLUGIN_ROOT=str(plugin))
        for client in ('claude', 'codex'):
            if client == 'codex' and os.name == 'nt' and not shutil.which('py'):
                self.skipTest('Windows 未安装 py 启动器')
            hook = json.loads((plugin / 'hooks' / (client + '.json')).read_text(encoding='utf-8'))['hooks']['SessionStart'][0]['hooks'][0]
            command = hook['commandWindows'] if client == 'codex' and os.name == 'nt' else hook['command']
            data = {'session_id': 'manifest', 'hook_event_name': 'SessionStart'}
            result = subprocess.run(command, shell=True, input=json.dumps(data), text=True, encoding='utf-8', capture_output=True, cwd=self.base, env=env, check=True)
            self.assertEqual(result.stderr, '')
            context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
            self.assertIn((plugin / 'skills/wayne-mode/SKILL.md').read_text(encoding='utf-8'), context)
            self.assertIn(str(plugin / 'skills/wayne-mode'), context)
            digest = hashlib.sha256(b'manifest').hexdigest()
            self.assertTrue((self.state / 'sessions' / (client + '-' + digest + '.json')).exists())

    def test_paths_and_manifests(self):
        spec = importlib.util.spec_from_file_location('wayne_mode', SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with patch.object(mod.sys, 'platform', 'darwin'), patch.object(mod.Path, 'home', return_value=Path('/home/test')):
            self.assertEqual(mod.state_dir(), Path('/home/test/Library/Application Support/wstack/wayne-mode'))
        with patch.object(mod.sys, 'platform', 'win32'), patch.dict(os.environ, {'APPDATA': '/appdata'}):
            self.assertEqual(mod.state_dir(), Path('/appdata/wstack/wayne-mode'))
        root_manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        self.assertNotIn('com.openai', root_manifest.get('extensions', {}))
        interface = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))['interface']
        self.assertEqual(interface['displayName'], 'wstack')
        self.assertEqual(interface['logo'], './assets/logo.jpg')
        self.assertEqual(interface['composerIcon'], './assets/logo.jpg')
        self.assertIn('Instructions', interface['capabilities'])
        self.assertIn('Lifecycle hooks', interface['capabilities'])
        self.assertEqual(len(interface['defaultPrompt']), 3)
        self.assertFalse((ROOT / 'hooks/hooks.json').exists())
        for client in ('cursor', 'grok'):
            self.assertNotIn('hooks', json.loads((ROOT / f'.{client}-plugin/plugin.json').read_text(encoding='utf-8')))
        for client in ('claude', 'codex'):
            manifest = json.loads((ROOT / f'.{client}-plugin/plugin.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['hooks'], f'./hooks/{client}.json')
            hooks = json.loads((ROOT / f'hooks/{client}.json').read_text(encoding='utf-8'))['hooks']
            for event in ('SessionStart', 'UserPromptSubmit'):
                hook = hooks[event][0]['hooks'][0]
                self.assertEqual(hook['timeout'], 5)
                if client == 'codex':
                    self.assertEqual(hook['additionalContextLimit'], 8000)
                    self.assertIn('py -3', hook['commandWindows'])


if __name__ == '__main__':
    unittest.main()
