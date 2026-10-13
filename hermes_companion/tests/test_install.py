"""`hermes-companion install`: the shortcut plan and the scripts that make it."""
import sys
import unittest
from pathlib import Path
from unittest import mock

from hermes_companion.core import install


class PlanTests(unittest.TestCase):
    def test_exe_is_copied_to_programs_and_both_icons_open_home(self):
        with mock.patch.dict("os.environ", {"LOCALAPPDATA": r"C:\Users\me\AppData\Local"}):
            exe, cuts = install.plan(True, r"C:\Downloads\HermesCompanion.exe")
        self.assertEqual(exe.name, "HermesCompanion.exe")
        self.assertIn("Programs", exe.parts)
        self.assertEqual([c.folder for c in cuts], ["Desktop", "Programs"])
        for c in cuts:
            self.assertEqual((c.target, c.args, c.icon), (str(exe), "home", str(exe)))

    def test_source_install_uses_python_with_the_rendered_crow_icon(self):
        exe, cuts = install.plan(False, "/venv/bin/python", desktop=False)
        self.assertIsNone(exe)
        self.assertEqual([c.folder for c in cuts], ["Programs"])
        self.assertEqual(cuts[0].args, "-m hermes_companion home")
        self.assertTrue(cuts[0].icon.endswith("icon.ico"))

    def test_powershell_quotes_paths_and_resolves_special_folders(self):
        cut = install.Shortcut("Desktop", r"C:\O'Brien\HermesCompanion.exe", "home",
                               r"C:\O'Brien\HermesCompanion.exe", r"C:\O'Brien")
        ps = install.powershell_script([cut])
        self.assertIn("GetFolderPath('Desktop')", ps)
        self.assertIn(r"'C:\O''Brien\HermesCompanion.exe'", ps)
        self.assertIn(r"'C:\O''Brien\HermesCompanion.exe,0'", ps)
        self.assertIn("'Hermes Companion.lnk'", ps)
        removing = install.powershell_script([cut], remove=True)
        self.assertIn("Remove-Item", removing)
        self.assertNotIn("CreateShortcut", removing)

    def test_linux_desktop_entry_opens_home(self):
        text = install.desktop_entry("/usr/bin/python3", "-m hermes_companion home", "/i.png")
        self.assertIn("Name=Hermes Companion", text)
        self.assertIn('Exec="/usr/bin/python3" -m hermes_companion home', text)
        self.assertIn("Icon=/i.png", text)

    def test_the_cli_accepts_install(self):
        from hermes_companion.cli.emit import build_parser
        a = build_parser().parse_args(["install", "--no-desktop", "--uninstall"])
        self.assertTrue(a.no_desktop and a.uninstall)

    def test_icon_renders_every_windows_size(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            out = install.render_icon(Path(d) / "icon.ico")
            self.assertIn((256, 256), Image.open(out).info["sizes"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux app menu")
    def test_linux_install_and_uninstall_round_trip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.object(Path, "home", return_value=Path(home)), \
                mock.patch.dict("os.environ", {"LOCALAPPDATA": home}):
            install.apply()
            entry = Path(home) / ".local/share/applications/hermes-companion.desktop"
            self.assertTrue(entry.exists())
            self.assertTrue((Path(home) / "hermes-companion" / "icon.png").exists())
            install.apply(remove=True)
            self.assertFalse(entry.exists())


if __name__ == "__main__":
    unittest.main()
