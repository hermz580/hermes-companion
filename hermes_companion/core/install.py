"""Put Hermes Companion on this computer like a normal app.

``hermes-companion install`` adds a **Hermes Companion** shortcut, with
Nyamekra's crow icon, to the Desktop and the Start menu (Windows) or the app
menu (Linux). The shortcut opens Companion Home. ``--uninstall`` removes them.

From the one-file ``HermesCompanion.exe`` the exe is first copied to
``%LOCALAPPDATA%\\Programs\\Hermes Companion`` so the shortcuts keep working
after the download is moved or deleted. Running a newer exe's ``install``
replaces that copy, which is how an update lands.

The plan (what goes where) is pure and tested; only ``apply`` touches disk.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP = "Hermes Companion"
EXE = "HermesCompanion.exe"


@dataclass(frozen=True)
class Shortcut:
    folder: str          # "Desktop" or "Programs" (Windows special folders), or a path
    target: str
    args: str
    icon: str
    workdir: str


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "hermes-companion" if base else Path.home() / ".hermes-companion"


def program_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "Programs" / APP if base else data_dir() / "app"


def plan(frozen: bool, executable: str, desktop: bool = True) -> tuple[Path | None, list[Shortcut]]:
    """(where the exe is copied or None, the shortcuts to make). No side effects."""
    folders = (["Desktop"] if desktop else []) + ["Programs"]
    if frozen:
        exe = program_dir() / EXE
        return exe, [Shortcut(f, str(exe), "home", str(exe), str(exe.parent)) for f in folders]
    py = Path(executable)
    gui = py.with_name("pythonw.exe")       # no console window behind Home
    target = gui if gui.exists() else py
    icon = data_dir() / "icon.ico"
    return None, [Shortcut(f, str(target), "-m hermes_companion home", str(icon),
                           str(Path.home())) for f in folders]


def render_icon(out: Path, fmt: str = "ICO") -> Path:
    """Nyamekra's head and halo, the same crop as packaging/make_icon.py."""
    from hermes_companion.renderer.smooth import FrameRenderer
    from PIL import Image
    img = FrameRenderer("nyamekra").frame("idle_bob", 0.2).crop((40, 2, 160, 122))
    img = img.resize((256, 256), Image.LANCZOS)   # ICO drops sizes larger than the source
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "ICO":
        img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    else:
        img.save(out)
    return out


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def powershell_script(shortcuts: list[Shortcut], remove: bool = False) -> str:
    """PowerShell that creates (or removes) the .lnk files. Special folders are
    resolved by Windows itself, so a OneDrive-redirected Desktop just works."""
    lines = ["$ErrorActionPreference = 'Stop'", "$sh = New-Object -ComObject WScript.Shell"]
    for s in shortcuts:
        lines.append(f"$p = Join-Path ([Environment]::GetFolderPath({_ps_quote(s.folder)})) "
                     f"{_ps_quote(APP + '.lnk')}")
        if remove:
            lines.append("if (Test-Path $p) { Remove-Item $p; Write-Output \"removed $p\" }")
            continue
        lines += ["$l = $sh.CreateShortcut($p)",
                  f"$l.TargetPath = {_ps_quote(s.target)}",
                  f"$l.Arguments = {_ps_quote(s.args)}",
                  f"$l.IconLocation = {_ps_quote(s.icon + ',0')}",
                  f"$l.WorkingDirectory = {_ps_quote(s.workdir)}",
                  f"$l.Description = {_ps_quote('Open Companion Home')}",
                  "$l.Save()", "Write-Output \"shortcut $p\""]
    return "\n".join(lines)


def desktop_entry(target: str, args: str, icon: str) -> str:
    """A freedesktop .desktop file for the Linux app menu."""
    return ("[Desktop Entry]\nType=Application\n"
            f"Name={APP}\nComment=Open Companion Home\n"
            f"Exec=\"{target}\" {args}\nIcon={icon}\nTerminal=false\n"
            "Categories=Utility;\n")


def _copy_exe(dest: Path) -> str:
    src = Path(sys.executable).resolve()
    if dest.exists() and dest.resolve() == src:
        return f"already installed at {dest}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dest)
    except OSError as exc:      # the installed copy is running; close it and retry
        raise RuntimeError(f"could not update {dest} ({exc}). Close Hermes Companion "
                           "(tray icon -> Quit) and run install again.") from exc
    return f"installed {dest}"


def apply(desktop: bool = True, remove: bool = False) -> list[str]:
    """Do it. Returns human-readable lines; raises RuntimeError on failure."""
    frozen = bool(getattr(sys, "frozen", False))
    exe, shortcuts = plan(frozen, sys.executable, desktop)
    out: list[str] = []
    if sys.platform == "win32":
        if not remove:
            if exe is not None:
                out.append(_copy_exe(exe))
            else:
                render_icon(Path(shortcuts[0].icon))
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", powershell_script(shortcuts, remove)],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or "PowerShell could not make the shortcuts")
        out += [ln for ln in res.stdout.splitlines() if ln.strip()]
        return out
    if sys.platform.startswith("linux"):
        apps = Path.home() / ".local" / "share" / "applications"
        entry = apps / "hermes-companion.desktop"
        if remove:
            if entry.exists():
                entry.unlink()
                out.append(f"removed {entry}")
            return out
        icon = render_icon(data_dir() / "icon.png", fmt="PNG")
        apps.mkdir(parents=True, exist_ok=True)
        target = sys.executable
        args = "home" if frozen else "-m hermes_companion home"
        entry.write_text(desktop_entry(target, args, str(icon)), encoding="utf-8")
        out.append(f"app menu entry {entry}")
        return out
    raise RuntimeError("install is available on Windows and Linux; on macOS run "
                       "`hermes-companion` from a terminal")


def cmd_install(args) -> int:
    try:
        for line in apply(desktop=not args.no_desktop, remove=args.uninstall):
            print(line)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        return 1
    print("INSTALL OK" if not args.uninstall else "UNINSTALL OK")
    return 0
