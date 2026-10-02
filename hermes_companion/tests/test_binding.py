"""Explicit binding: one companion, one real session, fail closed otherwise."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hermes_companion.core import binding as bind_mod
from hermes_companion.renderer.live import bound_session_for_companion


class BindTests(unittest.TestCase):
    def test_bind_creates_a_single_readable_row(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            bind_mod.bind('the-alpha-and', 'session-a', path=path)
            rows = bind_mod.describe(path=path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['companion_id'], 'the-alpha-and')
            self.assertEqual(rows[0]['session_id'], 'session-a')
            self.assertEqual(bound_session_for_companion('the-alpha-and', path), 'session-a')

    def test_rebinding_replaces_rather_than_duplicating(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            bind_mod.bind('the-alpha-and', 'session-a', path=path)
            bind_mod.bind('the-alpha-and', 'session-b', path=path)
            rows = bind_mod.describe(path=path)
            self.assertEqual(len(rows), 1, 'duplicate rows would make the reader refuse')
            self.assertEqual(bound_session_for_companion('the-alpha-and', path), 'session-b')

    def test_companions_bind_independently(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            bind_mod.bind('alpha', 'session-a', path=path)
            bind_mod.bind('beta', 'session-b', path=path)
            self.assertEqual(bound_session_for_companion('alpha', path), 'session-a')
            self.assertEqual(bound_session_for_companion('beta', path), 'session-b')

    def test_unbind_removes_only_that_companion(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            bind_mod.bind('alpha', 'session-a', path=path)
            bind_mod.bind('beta', 'session-b', path=path)
            self.assertTrue(bind_mod.unbind('alpha', path=path))
            self.assertIsNone(bound_session_for_companion('alpha', path))
            self.assertEqual(bound_session_for_companion('beta', path), 'session-b')
            self.assertFalse(bind_mod.unbind('alpha', path=path))

    def test_invalid_ids_are_rejected(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            for companion in ['', '  ', 'bad id', 'bad\nlabel', 'x' * 65]:
                with self.subTest(companion=companion):
                    with self.assertRaises(ValueError):
                        bind_mod.bind(companion, 'session-a', path=path)
            for session in ['', '   ', 'has space ', 'x' * 300]:
                with self.subTest(session=session):
                    with self.assertRaises(ValueError):
                        bind_mod.bind('alpha', session, path=path)
            self.assertEqual(bind_mod.describe(path=path), [])

    def test_missing_or_corrupt_file_reads_as_empty_not_guessed(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'bindings.json'
            self.assertEqual(bind_mod.describe(path=path), [])
            path.write_text('{not json', encoding='utf-8')
            self.assertEqual(bind_mod.describe(path=path), [])
            self.assertIsNone(bound_session_for_companion('alpha', path))

    def test_current_session_comes_from_the_newest_log_entry(self):
        with TemporaryDirectory() as d:
            home = Path(d)
            (home / 'logs').mkdir()
            (home / 'logs' / 'agent.log').write_text(
                'run 1 agent_session_id=20260101_010101_aaaa\n'
                'run 2 agent_session_id=20260202_020202_bbbb\n',
                encoding='utf-8')
            self.assertEqual(bind_mod.resolve_current_session(home), '20260202_020202_bbbb')

    def test_current_session_falls_back_to_newest_sessions_entry(self):
        with TemporaryDirectory() as d:
            home = Path(d)
            (home / 'sessions').mkdir()
            (home / 'sessions' / 'sessions.json').write_text(json.dumps({
                'k1': {'session_id': '20260101_010101_aaaa', 'updated_at': '2026-01-01T00:00:00'},
                'k2': {'session_id': '20260303_030303_cccc', 'updated_at': '2026-03-03T00:00:00'},
            }), encoding='utf-8')
            self.assertEqual(bind_mod.resolve_current_session(home), '20260303_030303_cccc')

    def test_current_session_is_none_when_unknown(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(bind_mod.resolve_current_session(Path(d)))


if __name__ == '__main__':
    unittest.main()
