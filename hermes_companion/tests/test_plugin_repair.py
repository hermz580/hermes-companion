import json
import pytest
from hermes_companion.plugin import install


def test_repair_preserves_config_and_can_restore(tmp_path):
    config = tmp_path / 'config.yaml'
    config.write_text('private-setting: preserved', encoding='utf-8')
    old = tmp_path / 'plugins' / 'hermes-companion'
    old.mkdir(parents=True)
    (old / 'plugin.yaml').write_text('old manifest')
    (old / '__init__.py').write_text('# old adapter')
    dest = install.build(str(tmp_path))
    manifest = json.loads((Path(dest) / 'bundle-manifest.json').read_text())
    assert manifest['files']['__init__.py']
    assert not list(Path(dest).rglob('*.pyc'))
    backups = list((tmp_path / 'plugin-backups').iterdir())
    assert len(backups) == 1
    install.restore_backup(str(tmp_path), str(backups[0]))
    assert (old / '__init__.py').read_text() == '# old adapter'
    assert config.read_text() == 'private-setting: preserved'


def test_invalid_stage_leaves_old_bundle_intact(tmp_path, monkeypatch):
    old = tmp_path / 'plugins' / 'hermes-companion'
    old.mkdir(parents=True)
    (old / '__init__.py').write_text('# preserved')
    def bad_stage(home):
        stage = Path(home) / 'plugins' / 'hermes-companion'
        stage.mkdir(parents=True)
        (stage / '__init__.py').write_text('invalid python here')
        return str(stage)
    monkeypatch.setattr(install, '_assemble', bad_stage)
    with pytest.raises(SyntaxError):
        install.build(str(tmp_path))
    assert (old / '__init__.py').read_text() == '# preserved'


def test_restore_rejects_unrelated_directory(tmp_path):
    with pytest.raises(ValueError):
        install.restore_backup(str(tmp_path), str(tmp_path.parent))

from pathlib import Path


def test_pair_repair_and_running_guard(tmp_path, monkeypatch):
    from hermes_companion.plugin import repair
    monkeypatch.setattr(repair, 'running_hermes', lambda: [123])
    with pytest.raises(RuntimeError):
        repair.repair(tmp_path)
    assert not (tmp_path / 'plugins').exists()
    monkeypatch.setattr(repair, 'running_hermes', lambda: [])
    assert repair.repair(tmp_path) == []
    assert len(repair.repair(tmp_path)) == 2
    assert (tmp_path / 'plugins/hermes-companion/bundle-manifest.json').exists()
    assert (tmp_path / 'plugins/hermes-companion-context/bundle-manifest.json').exists()
    assert not (tmp_path / '.companion-repair.lock').exists()


def test_pair_rolls_back_both_after_second_swap_fails(tmp_path, monkeypatch):
    from hermes_companion.plugin import repair
    monkeypatch.setattr(repair, 'running_hermes', lambda: [])
    for name in ('hermes-companion', 'hermes-companion-context'):
        old = tmp_path / 'plugins' / name
        old.mkdir(parents=True)
        (old / 'original').write_text(name)
    original_rename = Path.rename
    def fail_second(self, target):
        if '.companion-pair-' in str(self) and self.name == 'hermes-companion-context' and Path(target).parent == tmp_path / 'plugins':
            raise OSError('injected second swap failure')
        return original_rename(self, target)
    monkeypatch.setattr(Path, 'rename', fail_second)
    with pytest.raises(OSError):
        repair.repair(tmp_path)
    for name in ('hermes-companion', 'hermes-companion-context'):
        assert (tmp_path / 'plugins' / name / 'original').read_text() == name
