"""Render the app icon (Nyamekra's head and halo) to packaging/icon.ico."""
from pathlib import Path

from hermes_companion.core.install import render_icon

print(render_icon(Path(__file__).with_name("icon.ico")))
