"""A desktop icon that opens Companion Home: ``hermes-companion shortcut``.

Windows gets ``Hermes Companion.lnk`` on the desktop (the real Desktop folder,
OneDrive-redirected or not), made with the built-in WScript.Shell through
PowerShell, so no extra packages are needed. It starts Home with
``pythonw`` (or the one-file .exe itself), so no console window opens.
Linux gets a ``hermes-companion.desktop`` launcher. The icon is Nyamekra's
head, rendered once next to the saved settings.

Paths reach PowerShell through environment variables, never inside the
script text, so a folder name with quotes or spaces can't break it.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NAME = "Hermes Companion"
COMMENT = "Open Companion Home: start, choose and tune your companion"

_PS_SCRIPT = (
    "$d = [Environment]::GetFolderPath('Desktop'); "
    "$p = Join-Path $d ($env:HC_NAME + '.lnk'); "
    "$l = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
    "$l.TargetPath = $env:HC_TARGET; $l.Arguments = $env:HC_ARGS; "
    "$l.WorkingDirectory = $env:HC_DIR; $l.IconLocation = $env:HC_ICON; "
    "$l.Description = $env:HC_COMMENT; $l.Save(); Write-Output $p"
)


def launch_target() -> tuple[str, list[str]]:
    """The program and arguments that open Home without a console window."""
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return str(exe), ["home"]
    quiet = exe.with_name("pythonw.exe")
    return str(quiet if quiet.exists() else exe), ["-m", "hermes_companion", "home"]


def icon_file(folder: Path | None = None) -> Path:
    """Nyamekra's head as a multi-size .ico (rendered once, reused after)."""
    from hermes_companion.core.settings import settings_path
    path = (folder or settings_path().parent) / "icon.ico"
    if not path.exists():
        from hermes_companion.renderer.smooth import FrameRenderer
        path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        img = FrameRenderer("nyamekra").frame("idle_bob", 0.2).crop((40, 2, 160, 122))
        img = img.resize((256, 256), Image.LANCZOS)       # .ico skips sizes above the source
        img.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def _windows(run=subprocess.run) -> Path:
    target, args = launch_target()
    icon = f"{target},0" if getattr(sys, "frozen", False) else str(icon_file())
    env = dict(os.environ, HC_NAME=NAME, HC_TARGET=target,
               HC_ARGS=subprocess.list2cmdline(args), HC_DIR=str(Path.home()),
               HC_ICON=icon, HC_COMMENT=COMMENT)
    out = run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-Command", _PS_SCRIPT], env=env, capture_output=True, text=True,
              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if out.returncode != 0:
        raise OSError((out.stderr or out.stdout or "PowerShell failed").strip())
    return Path(out.stdout.strip().splitlines()[-1])


def desktop_entry(target: str, args: list[str], icon: Path) -> str:
    exec_line = " ".join(f'"{a}"' if " " in a else a for a in [target, *args])
    return ("[Desktop Entry]\nType=Application\n"
            f"Name={NAME}\nComment={COMMENT}\nExec={exec_line}\nIcon={icon}\n"
            "Terminal=false\nCategories=Utility;\n")


def _linux(desktop: Path | None = None) -> Path:
    folder = desktop or Path(os.environ.get("XDG_DESKTOP_DIR", Path.home() / "Desktop"))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "hermes-companion.desktop"
    target, args = launch_target()
    path.write_text(desktop_entry(target, args, icon_file()), encoding="utf-8")
    path.chmod(0o755)
    return path


def create(desktop: Path | None = None) -> Path:
    """Put the icon on the desktop and return where it went."""
    if sys.platform == "win32":
        return _windows()
    if sys.platform.startswith("linux"):
        return _linux(desktop)
    raise OSError("desktop icons are made on Windows and Linux; on macOS run "
                  "`hermes-companion` from Terminal or add it to the Dock")
