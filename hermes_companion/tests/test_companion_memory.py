"""Disk-backed continuity contract; no sensors, models or services."""
import tempfile
import unittest
from pathlib import Path

from hermes_companion.core import companion_memory as memory


class CompanionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'memory.sqlite3'
        self.store = memory.CompanionMemoryStore(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_identity_survives_disk_reopen_and_empty_default(self):
        expected = self.store.create_companion('alpha', 'Alpha', role='Reviewer')
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(self.store.list_companions(), [expected])
        ctx = self.store.build_execution_context('alpha', 'task', 'session')
        self.assertEqual(ctx['memories'], [])
        self.assertEqual((ctx['companion_id'], ctx['task_id'], ctx['session_id']),
                         ('alpha', 'task', 'session'))
        self.assertFalse(ctx['authorizes_actions'])

    def test_approved_curated_memory_persists_isolated_and_task_bound(self):
        self.store.create_companion('alpha', 'Alpha')
        self.store.create_companion('beta', 'Beta')
        saved = self.store.add_memory('alpha', 'Prefer concise reports')
        self.store.add_memory('alpha', 'Maybe likes tables', approved=False)
        targeted = self.store.add_memory('alpha', 'Use inventory scope', task_id='inventory')
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(len(self.store.list_memories('alpha')), 3)
        ctx = self.store.build_execution_context('alpha', 'other', 's')
        self.assertEqual(ctx['memories'], [saved])
        self.assertEqual(self.store.build_execution_context('beta', 'other', 's')['memories'], [])
        self.assertEqual(self.store.build_execution_context('alpha', 'inventory', 's', memory_ids=[targeted['memory_id']])['memories'], [targeted])
        self.assertEqual(saved['source'], 'user')
        self.assertEqual(saved['state'], 'approved')
        for source in ('camera', 'screen', 'microphone', 'selected_document'):
            with self.assertRaises(ValueError):
                self.store.add_memory('alpha', 'raw capture', source=source)
        with self.assertRaises(PermissionError):
            self.store.add_memory('alpha', 'inferred', source='outcome_summary')
        with self.assertRaises(ValueError):
            self.store.build_execution_context('alpha', '', 's')

    def test_correction_revocation_deletion_and_stale_binding(self):
        self.store.create_companion('a', 'A')
        rec = self.store.add_memory('a', 'old')
        mid = rec['memory_id']
        def build():
            return self.store.build_execution_context('a', 't', 's')
        def valid(ctx, **kw):
            return self.store.validate_execution_context(ctx, companion_id='a',
                task_id=kw.get('task_id', 't'), session_id=kw.get('session_id', 's'))
        before = build()
        self.assertTrue(valid(before))
        self.assertFalse(valid(before, task_id='other'))
        self.assertFalse(valid(before, session_id='other'))
        with memory.CompanionMemoryStore(self.path) as second:
            changed = second.correct_memory(mid, 'corrected')
        self.assertEqual(changed['state'], 'tentative')
        self.assertEqual(changed['source'], 'user')
        self.assertEqual(changed['version'], 2)
        self.assertFalse(valid(before))
        self.assertEqual(build()['memories'], [])
        with self.assertRaises(PermissionError):
            self.store.approve_memory(mid)
        self.store.approve_memory(mid, confirmed=True)
        self.assertEqual(build()['memories'][0]['content'], 'corrected')
        self.store.revoke_memory(mid)
        self.assertEqual(build()['memories'], [])
        self.assertEqual(self.store.list_memories('a')[0]['state'], 'revoked')
        self.assertTrue(self.store.delete_memory(mid))
        self.assertFalse(self.store.delete_memory(mid))
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(self.store.list_memories('a'), [])
        self.assertFalse(valid(before))
        altered = build()
        altered['authorizes_actions'] = True
        self.assertFalse(valid(altered))

    def test_shared_inheritance_requires_selected_approval_and_revokes(self):
        self.store.create_companion('a', 'A')
        self.store.create_companion('b', 'B')
        m = self.store.add_memory('a', 'Shared preference', scope='shared')['memory_id']
        def build():
            return self.store.build_execution_context('b', 't', 's')
        self.assertEqual(build()['memories'], [])
        with self.assertRaises(PermissionError):
            self.store.grant_shared('b', m)
        self.store.grant_shared('b', m, confirmed=True)
        self.assertEqual(build()['memories'][0]['companion_id'], 'a')
        self.assertEqual(self.store.list_memories('b'), [])
        before = build()
        self.store.revoke_shared('b', m)
        self.assertEqual(build()['memories'], [])
        self.assertFalse(self.store.validate_execution_context(before, companion_id='b', task_id='t', session_id='s'))
        self.store.grant_shared('b', m, confirmed=True)
        self.store.correct_memory(m, 'Changed preference')
        self.store.approve_memory(m, confirmed=True)
        self.assertEqual(build()['memories'], [])  # prior recipient consent is not recycled
        self.store.grant_shared('b', m, confirmed=True)
        self.store.revoke_memory(m)
        self.store.approve_memory(m, confirmed=True)
        self.assertEqual(build()['memories'], [])
        tentative = self.store.add_memory('a', 'Maybe', scope='shared', approved=False)
        with self.assertRaises(PermissionError):
            self.store.grant_shared('b', tentative['memory_id'], confirmed=True)
        private = self.store.add_memory('a', 'Private')
        with self.assertRaises(PermissionError):
            self.store.grant_shared('b', private['memory_id'], confirmed=True)
        self.store.grant_shared('b', m, confirmed=True)
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(len(build()['memories']), 1)
        self.store.delete_memory(m)
        self.assertEqual(build()['memories'], [])

    def test_project_permission_is_exact_and_owner_isolated(self):
        for cid in ('a', 'b'):
            self.store.create_companion(cid, cid)
            self.store.add_memory(cid, 'Project ' + cid, scope='project', project_id='p')
        def build(project='p'):
            return self.store.build_execution_context('a', 't', 's', project)
        self.assertEqual(build()['memories'], [])
        with self.assertRaises(PermissionError):
            self.store.grant_project('a', 'p')
        self.store.grant_project('a', 'p', confirmed=True)
        self.assertEqual([r['content'] for r in build()['memories']], ['Project a'])
        self.assertEqual(build('q')['memories'], [])
        self.assertEqual(build(None)['memories'], [])
        before = build()
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(build(), before)
        self.store.revoke_project('a', 'p')
        self.assertEqual(build()['memories'], [])
        self.assertFalse(self.store.validate_execution_context(before, companion_id='a', task_id='t', session_id='s', project_id='p'))

    def test_archive_persists_and_reopen_does_not_restore_grants(self):
        for cid in ('a', 'b'):
            self.store.create_companion(cid, cid)
        rec = self.store.add_memory('a', 'Share', scope='shared')
        self.store.grant_shared('b', rec['memory_id'], confirmed=True)
        before = self.store.build_execution_context('b', 't', 's')
        self.store.archive_companion('a')
        self.assertEqual([r['companion_id'] for r in self.store.list_companions()], ['b'])
        self.assertEqual(len(self.store.list_companions(include_archived=True)), 2)
        self.assertEqual(self.store.build_execution_context('b', 't', 's')['memories'], [])
        self.assertFalse(self.store.validate_execution_context(before, companion_id='b', task_id='t', session_id='s'))
        with self.assertRaises(PermissionError):
            self.store.build_execution_context('a', 't', 's')
        with self.assertRaises(PermissionError):
            self.store.add_memory('a', 'No')
        self.store.close()
        self.store = memory.CompanionMemoryStore(self.path)
        self.assertEqual(len(self.store.list_companions()), 1)
        self.store.archive_companion('a', archived=False)
        self.assertEqual(self.store.list_memories('a'), [rec])
        self.assertEqual(self.store.build_execution_context('b', 't', 's')['memories'], [])
        with self.assertRaises(ValueError):
            self.store.archive_companion('a', archived='false')

    def test_selected_snapshot_validates_without_broadening_and_rejects_bad_input(self):
        self.store.create_companion('a', 'A')
        a = self.store.add_memory('a', 'first')
        self.store.add_memory('a', 'second')
        ctx = self.store.build_execution_context('a', 't', 's', memory_ids=[a['memory_id']])
        self.assertTrue(self.store.validate_execution_context(ctx, companion_id='a', task_id='t', session_id='s'))
        self.assertEqual(ctx['memory_ids'], [a['memory_id']])
        self.assertEqual(self.store.build_execution_context('a', 't', 's', memory_ids=[])['memories'], [])
        for bad in (a['memory_id'], 1, [None], [''], {'x': 1}):
            with self.assertRaises(ValueError):
                self.store.build_execution_context('a', 't', 's', memory_ids=bad)
        ctx['memories'][0]['content'] = 'forged'
        self.assertFalse(self.store.validate_execution_context(ctx, companion_id='a', task_id='t', session_id='s'))
        self.assertEqual(self.store.list_memories('a')[0]['content'], 'first')
        for cid in ('bad id', '../path', '', ' a'):
            with self.assertRaises(ValueError):
                self.store.create_companion(cid, 'invalid')
        with self.assertRaises(KeyError):
            self.store.build_execution_context('missing', 't', 's')


if __name__ == '__main__':
    unittest.main()
