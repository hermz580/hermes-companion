"""Repair both installed bundles after closing Hermes; preserve configuration."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import tempfile
from uuid import uuid4


def running_hermes():
    import psutil
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info['name'] or '').lower()
            args = ' '.join(proc.info['cmdline'] or []).lower()
            if name in {'hermes.exe', 'hermes-agent.exe'} or (
                name.startswith('python') and ('hermes_cli' in args or 'hermes-agent' in args)):
                active.append(proc.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return active


def repair(home):
    from .install import build as observer
    from ..plugin_context.install import build as context
    home = Path(home).resolve()
    active = running_hermes()
    if active:
        raise RuntimeError('Close Hermes before repair; active process IDs: ' + ', '.join(map(str, active)))
    home.mkdir(parents=True, exist_ok=True)
    # Exclusive operation marker: never overwrite a concurrent/unfinished repair.
    marker = home / '.companion-repair.lock'
    with marker.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    try:
        with tempfile.TemporaryDirectory(prefix='.companion-pair-', dir=home) as staging:
            observer(staging)
            context(staging)
            if running_hermes():
                raise RuntimeError('Hermes started during staging. Close it and retry.')
            backups = home / 'plugin-backups'
            backups.mkdir(exist_ok=True)
            (home / 'plugins').mkdir(exist_ok=True)
            swapped = []
            try:
                for name in ('hermes-companion', 'hermes-companion-context'):
                    dest = home / 'plugins' / name
                    if dest.is_symlink():
                        raise RuntimeError('Refusing a symlinked plugin directory')
                    backup = backups / (name + '-' + uuid4().hex)
                    previous = dest.exists()
                    if previous:
                        dest.rename(backup)
                    swapped.append((dest, backup, previous))
                    (Path(staging) / 'plugins' / name).rename(dest)
            except BaseException:
                for dest, backup, previous in reversed(swapped):
                    if dest.exists():
                        dest.rename(backups / (dest.name + '-failed-' + uuid4().hex))
                    if previous:
                        backup.rename(dest)
                raise
            return [str(backup) for _, backup, previous in swapped if previous]
    finally:
        marker.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', default=os.environ.get('HERMES_HOME') or str(Path.home() / 'AppData/Local/hermes'))
    args = parser.parse_args()
    try:
        backups = repair(args.home)
    except (RuntimeError, OSError) as exc:
        print(f'Repair not applied: {exc}')
        return 2
    print('Both plugin bundles repaired. Configuration and personal data preserved.')
    for path in backups:
        print('Backup: ' + path)
    print('Restart Hermes to load the repaired bundles.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
