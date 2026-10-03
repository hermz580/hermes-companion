"""Render the app icon (Nyamekra's head and halo) to packaging/icon.ico."""
from pathlib import Path

from hermes_companion.renderer.smooth import FrameRenderer

img = FrameRenderer("nyamekra").frame("idle_bob", 0.2).crop((40, 2, 160, 122))
out = Path(__file__).with_name("icon.ico")
img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
