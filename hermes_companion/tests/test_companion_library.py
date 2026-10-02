"""Real Tk + on-disk store coverage."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


# The repo root IS the `hermes_companion` package, so its PARENT must be
# importable. Derive that here rather than depending on an ambient PYTHONPATH:
# pytest's `pythonpath` ini setting fixes this process, not child processes, so
# a subprocess run would otherwise fail wherever the environment was not
# already set up by hand.
PACKAGE_PARENT = Path(__file__).resolve().parents[2]


def _child_env():
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PACKAGE_PARENT) + (os.pathsep + existing if existing else "")
    return env


class LibraryPathTests(unittest.TestCase):
    def test_module_has_user_launch_entrypoint(self):
        result = subprocess.run(
            [sys.executable, '-m', 'hermes_companion.renderer.companion_library', '--help'],
            capture_output=True, text=True, env=_child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--db', result.stdout)

    def test_default_database_is_durable_local_appdata(self):
        from hermes_companion.renderer.companion_library import default_database_path
        expected = Path(os.environ['LOCALAPPDATA']) / 'hermes' / 'companion' / 'library.sqlite3'
        self.assertEqual(default_database_path(), expected)


class LibraryGuiTests(unittest.TestCase):
    # One Tk root for the whole class. Creating and destroying a Tk root per
    # test repeatedly re-initializes the Tcl interpreter, which fails
    # order-dependently on Windows ("Can't find a usable tk.tcl") once other
    # Tk-using tests have run in the same process.
    @classmethod
    def setUpClass(cls):
        # One process-wide interpreter (see tests/conftest.py). Mapped so the
        # geometry/mapping assertions hold, but invisible and off-screen.
        from conftest import shared_tk_root
        cls.root = shared_tk_root()

    @classmethod
    def tearDownClass(cls):
        for child in cls.root.winfo_children():
            child.destroy()

    def setUp(self):
        import tempfile
        from hermes_companion.core.companion_memory import CompanionMemoryStore
        from hermes_companion.renderer.companion_library import CompanionLibrary
        for child in self.root.winfo_children():
            child.destroy()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'library.sqlite3'
        self.store = CompanionMemoryStore(self.path)
        self.app = CompanionLibrary(self.root, self.store, self.path)
        self.root.update()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self, name='Library test'):
        self.app.name_var.set(name)
        self.app.role_var.set('Writing helper')
        self.app.create_button.invoke()
        self.root.update()
        return self.app.selected_id

    def test_memory_requires_consent_corrects_forgets_and_is_isolated(self):
        cid = self.create()
        self.app.memory_text.insert('1.0', 'Prefer concise replies.')
        self.app.add_button.invoke()
        self.assertEqual(self.store.list_memories(cid), [])
        self.assertIn('approve', self.app.status_var.get())
        self.app.approved_var.set(True)
        self.app.add_button.invoke()
        records = self.store.list_memories(cid)
        self.assertEqual(len(records), 1)
        mid = records[0]['memory_id']
        self.assertEqual(records[0]['scope'], 'companion')
        self.assertFalse(self.app.approved_var.get())
        self.app.memory_tree.selection_set(mid)
        self.app.memory_tree.event_generate('<<TreeviewSelect>>')
        self.root.update()
        self.app.memory_text.delete('1.0', 'end')
        self.app.memory_text.insert('1.0', 'Use detailed replies when requested.')
        self.app.approved_var.set(True)
        self.app.correct_button.invoke()
        self.assertEqual(self.store.list_memories(cid)[0]['content'], 'Use detailed replies when requested.')
        self.assertEqual(self.store.list_memories(cid)[0]['state'], 'approved')
        other = self.create('Separate companion')
        self.assertEqual(self.store.list_memories(other), [])
        self.app.profile_tree.selection_set(cid)
        self.app.open_button.invoke()
        self.app.memory_tree.selection_set(mid)
        self.app.forget_button.invoke()
        self.assertEqual(self.store.list_memories(cid), [])
        import tkinter as tk
        with self.assertRaises(tk.TclError):
            self.app.memory_text.edit_undo()

    def test_preview_is_explicit_bound_and_cleared_after_memory_write(self):
        import json
        cid = self.create()
        self.app.task_var.set('task-library-proof')
        self.app.session_var.set('session-library-proof')
        self.app.preview_button.invoke()
        preview = json.loads(self.app.preview_text.get('1.0', 'end'))
        self.assertEqual(preview['companion_id'], cid)
        self.assertEqual(preview['task_id'], 'task-library-proof')
        self.assertFalse(preview['authorizes_actions'])
        self.app.memory_text.insert('1.0', 'Prefer clear summaries.')
        self.app.approved_var.set(True)
        self.app.add_button.invoke()
        self.assertNotIn('task-library-proof', self.app.preview_text.get('1.0', 'end'))
        self.app.preview_button.invoke()
        preview = json.loads(self.app.preview_text.get('1.0', 'end'))
        self.assertEqual(preview['memories'][0]['content'], 'Prefer clear summaries.')

    def test_status_and_controls_fit_minimum_window(self):
        self.root.geometry('960x730')
        self.root.update()
        labels = [w for w in self.app.detail_frame.master.winfo_children() if 'textvariable' in w.keys() and str(w.cget('textvariable')) == str(self.app.status_var)]
        self.assertEqual(len(labels), 1)
        self.assertLessEqual(labels[0].winfo_y() + labels[0].winfo_height(), self.app.detail_frame.master.winfo_height())
        self.assertTrue(labels[0].winfo_ismapped())

    def test_create_reopen_archive_restores_same_identity(self):
        cid = self.create()
        self.assertTrue(cid)
        self.assertIn('not a running agent', self.app.identity_var.get())
        self.app.archive_button.invoke()
        self.root.update()
        self.assertEqual(self.store.list_companions(), [])
        self.app.show_archived.set(True)
        self.app.refresh_button.invoke()
        self.app.profile_tree.selection_set(cid)
        self.app.open_button.invoke()
        self.root.update()
        self.assertEqual(self.app.selected_id, cid)
        self.app.restore_button.invoke()
        self.assertEqual(self.store.list_companions()[0]['companion_id'], cid)
        from hermes_companion.core.companion_memory import CompanionMemoryStore
        other = CompanionMemoryStore(self.path)
        try:
            self.assertEqual(other.list_companions()[0]['companion_id'], cid)
        finally:
            other.close()


if __name__ == '__main__':
    unittest.main()
