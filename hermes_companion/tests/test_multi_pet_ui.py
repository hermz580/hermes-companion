"""Invisible dock checks plus opt-in mapped desktop proof.

Routine execution never maps a window.  Set ``MULTI_PET_UI_TEST=1`` only when
the mapped-window screenshot/foreground proof is explicitly wanted.
"""
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class MultiPetHiddenUITests(unittest.TestCase):
    def test_quiet_control_and_exact_event_gate_without_mapping_window(self):
        from hermes_companion.renderer.multi_pet import MultiPetDock, PetBinding
        from hermes_companion.renderer.live import active_pet
        from conftest import shared_tk_root
        with TemporaryDirectory() as d:
            try:
                sheet = active_pet()[1]
            except RuntimeError:
                # No pet installed (e.g. CI): use a blank 8x9 Codex-sized atlas.
                from PIL import Image
                sheet = Path(d) / 'spritesheet.png'
                Image.new('RGBA', (1536, 1872), (0, 0, 0, 0)).save(sheet)
            dock = MultiPetDock(
                [PetBinding('Scout', 'simulation-a'), PetBinding('Guide')],
                [sheet] * 2, Path(d) / 'absent.jsonl', simulation=True,
                visible=False, root=shared_tk_root())
            try:
                dock.root.update_idletasks()
                self.assertFalse(dock.root.winfo_ismapped())
                self.assertFalse(dock.quiet)
                self.assertIn('OFF', dock.canvas.itemcget(dock.quiet_control, 'text'))

                dock.accept({'event': 'tool.started', 'tool': 'terminal'})
                dock.accept({'session_id': 'other', 'event': 'tool.started', 'tool': 'terminal'})
                self.assertEqual(dock.animations, {})

                dock.accept({'session_id': 'simulation-a', 'event': 'tool.started', 'tool': 'terminal'})
                self.assertEqual(list(dock.animations), [0])
                dock.toggle_quiet()
                self.assertTrue(dock.quiet)
                self.assertEqual(dock.animations, {})
                self.assertIn('ON', dock.canvas.itemcget(dock.quiet_control, 'text'))

                # Quiet suppresses motion, not evidence. Unbound remains explicit.
                dock.accept({'session_id': 'simulation-a', 'event': 'tool.finished', 'tool': 'terminal'})
                dock.refresh_status(time.monotonic())
                self.assertEqual(dock.animations, {})
                self.assertEqual(dock.model.pets[0].last_event, 'tool.finished')
                self.assertIn('QUIET', dock.canvas.itemcget(dock.labels[0], 'text'))
                self.assertEqual(dock.canvas.itemcget(dock.labels[1], 'text'), 'UNBOUND')
            finally:
                dock.close()


@unittest.skipUnless(os.environ.get('MULTI_PET_UI_TEST') == '1', 'explicit mapped-window proof opt-in')
class MultiPetMappedProofTests(unittest.TestCase):
    def test_visible_bound_sprites_click_status_motion_and_no_focus_theft(self):
        import ctypes
        from PIL import ImageGrab
        from hermes_companion.renderer.multi_pet import MultiPetDock, PetBinding
        from hermes_companion.renderer.live import active_pet
        user32 = ctypes.windll.user32
        foreground = user32.GetForegroundWindow()
        with TemporaryDirectory() as d:
            try:
                sheet = active_pet()[1]
            except RuntimeError:
                # No pet installed (e.g. CI): use a blank 8x9 Codex-sized atlas.
                from PIL import Image
                sheet = Path(d) / 'spritesheet.png'
                Image.new('RGBA', (1536, 1872), (0, 0, 0, 0)).save(sheet)
            dock = MultiPetDock([PetBinding('Scout', 'simulation-a'), PetBinding('Builder', 'simulation-b'), PetBinding('Guide')], [sheet]*3, Path(d)/'absent.jsonl', simulation=True, visible=True)
            try:
                dock.root.update()
                self.assertEqual(user32.GetForegroundWindow(), foreground, 'launch must not steal foreground')
                self.assertEqual(len(dock.items), 3)
                dock.toggle_quiet()
                self.assertTrue(dock.quiet)
                dock.toggle_quiet()
                self.assertFalse(dock.quiet)
                dock.accept({'session_id':'simulation-a', 'event':'tool.started', 'tool':'terminal'})
                dock.accept({'session_id':'simulation-b', 'event':'tool.started', 'tool':'web_search'})
                positions = []
                for _ in range(20):
                    dock.root.update()
                    positions.append(tuple(dock.canvas.coords(dock.items[0])))
                    time.sleep(.08)
                self.assertGreater(len(set(positions)), 1)
                for x, y in positions:
                    self.assertTrue(90 <= x <= 140 and 132 <= y <= 146)
                dock.canvas.event_generate('<Button-1>', x=345, y=146)
                dock.root.update()
                self.assertEqual(dock.selected, 1)
                self.assertIn('simulation-b', dock.canvas.itemcget(dock.detail, 'text'))
                self.assertEqual(user32.GetForegroundWindow(), foreground, 'status click must not steal foreground')
                self.assertEqual(dock.model.pets[2].last_event, '')
                self.assertIn('UNBOUND', dock.canvas.itemcget(dock.labels[2], 'text'))
                proof = Path(__file__).resolve().parents[1] / 'proof' / 'multi-pet'
                proof.mkdir(parents=True, exist_ok=True)
                x, y = dock.root.winfo_rootx(), dock.root.winfo_rooty()
                ImageGrab.grab((x,y,x+dock.width,y+dock.height)).save(proof/'simulation-dock.png')
                print('UI PROOF:', proof/'simulation-dock.png')
            finally:
                dock.root.destroy()


if __name__ == '__main__':
    unittest.main()
