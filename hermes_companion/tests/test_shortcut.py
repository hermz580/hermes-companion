"""Desktop icon: `hermes-companion shortcut` opens Companion Home."""
import subprocess
import sys
from pathlib import Path

from hermes_companion.core import shortcut


def test_target_opens_home_without_a_console():
    target, args = shortcut.launch_target()
    assert args == ["-m", "hermes_companion", "home"]
    assert Path(target).name in ("pythonw.exe", Path(sys.executable).name)


def test_frozen_exe_opens_home(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert shortcut.launch_target() == (sys.executable, ["home"])


def test_icon_is_rendered_once(tmp_path):
    path = shortcut.icon_file(tmp_path)
    assert path.read_bytes()[:4] == b"\x00\x00\x01\x00"      # .ico header
    from PIL import Image
    assert (256, 256) in Image.open(path).info["sizes"]       # sharp on high-DPI desktops
    stamp = path.stat().st_mtime_ns
    assert shortcut.icon_file(tmp_path).stat().st_mtime_ns == stamp


def test_windows_passes_paths_by_environment_only(monkeypatch, tmp_path):
    monkeypatch.setattr(shortcut, "icon_file", lambda: tmp_path / "icon.ico")
    seen = {}

    def run(cmd, env, **kw):
        seen.update(cmd=cmd, env=env)
        return subprocess.CompletedProcess(cmd, 0, stdout="C:\\Users\\a b\\Desktop\\Hermes Companion.lnk\n", stderr="")

    path = shortcut._windows(run=run)
    assert str(path).endswith("Hermes Companion.lnk")
    assert seen["env"]["HC_ARGS"] == "-m hermes_companion home"
    assert seen["env"]["HC_ICON"] == str(tmp_path / "icon.ico")
    assert str(tmp_path) not in seen["cmd"][-1]           # never inside the script text


def test_windows_failure_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(shortcut, "icon_file", lambda: tmp_path / "icon.ico")
    fail = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="blocked")
    try:
        shortcut._windows(run=fail)
    except OSError as exc:
        assert "blocked" in str(exc)
    else:
        raise AssertionError("expected OSError")


def test_linux_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(shortcut, "icon_file", lambda: tmp_path / "icon.ico")
    path = shortcut._linux(tmp_path / "Desktop")
    text = path.read_text()
    assert "Name=Hermes Companion" in text and "hermes_companion home" in text
    assert path.stat().st_mode & 0o111


def test_cli_has_shortcut_command():
    from hermes_companion.cli.emit import build_parser, cmd_shortcut
    assert build_parser().parse_args(["shortcut"]).fn is cmd_shortcut
