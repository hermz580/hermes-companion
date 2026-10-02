"""Package both plugins and load them through Hermes's real local loader."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[1]
HERMES_SOURCE = Path(os.environ.get(
    'HERMES_AGENT_SOURCE',
    Path.home() / 'AppData' / 'Local' / 'hermes' / 'hermes-agent'))


def _load_installer(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_installed_plugins_pass_real_manifest_and_loader_validation(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    monkeypatch.delenv('HERMES_SAFE_MODE', raising=False)
    (tmp_path / 'config.yaml').write_text(yaml.safe_dump({
        'plugins': {'enabled': ['hermes-companion', 'hermes-companion-context']},
    }), encoding='utf-8')

    observer = _load_installer(REPO / 'plugin' / 'install.py', 'observer_installer')
    context = _load_installer(REPO / 'plugin_context' / 'install.py', 'context_installer')
    observer.build(str(tmp_path))
    context.build(str(tmp_path))

    monkeypatch.syspath_prepend(str(HERMES_SOURCE))
    from hermes_cli.plugins import PluginManager, VALID_HOOKS

    manager = PluginManager(scope_key=str(tmp_path))
    manager.discover_and_load()
    for name, expected_hook in (
        ('hermes-companion', 'pre_tool_call'),
        ('hermes-companion-context', 'pre_llm_call'),
    ):
        loaded = manager._plugins[name]
        assert loaded.enabled is True, loaded.error
        assert expected_hook in loaded.hooks_registered
        assert set(loaded.manifest.provides_hooks) <= VALID_HOOKS
        assert loaded.manifest.path.startswith(str(tmp_path / 'plugins'))

    # Exercise the installed observer through its real loaded module. This is
    # a local hook call only: no agent loop and no model/provider call.
    observer_loaded = manager._plugins['hermes-companion']
    observer_loaded.module.on_session_start(session_id='loader-proof-session')
    observer_loaded.module.on_pre_tool_call(
        tool_name='terminal', args={'command': 'PRIVATE-COMMAND'},
        session_id='loader-proof-session', task_id='task-1')
    event_path = tmp_path / 'companion' / 'events.jsonl'
    key_path = tmp_path / 'companion' / 'event-auth.key'
    from hermes_companion.core.event_auth import verify_record
    lines = event_path.read_text(encoding='utf-8').splitlines()
    records = [verify_record(json.loads(line), key_path.read_bytes()) for line in lines]
    assert all(record['session_id'] == 'loader-proof-session' for record in records)
    assert 'PRIVATE-COMMAND' not in event_path.read_text(encoding='utf-8')

    # Force the installed context plugin's lazy bundled-package import after
    # evicting the observer's bundled package, proving it is self-contained.
    context_loaded = manager._plugins['hermes-companion-context']
    saved_path = list(sys.path)
    saved_modules = {
        name: module for name, module in sys.modules.items()
        if name == 'hermes_companion' or name.startswith('hermes_companion.')
    }
    try:
        for module_name in saved_modules:
            del sys.modules[module_name]
        observer_dir = str(tmp_path / 'plugins' / 'hermes-companion')
        while observer_dir in sys.path:
            sys.path.remove(observer_dir)
        assert callable(context_loaded.module._load_adapter())
    finally:
        for module_name in list(sys.modules):
            if module_name == 'hermes_companion' or module_name.startswith('hermes_companion.'):
                del sys.modules[module_name]
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path
