"""Local durable continuity, NOT model training or execution authority.

UI API (all records are plain dict/list values):
    CompanionMemoryStore(path)  # explicit local SQLite path; close() when done
    create_companion(companion_id, name, role='') -> dict (stable ID)
    list_companions(include_archived=False) -> list[dict]
    archive_companion(companion_id, archived=True) -> dict
    add_memory(companion_id, content, source='user', approved=True,
               scope='companion', project_id=None, *, task_id=None,
               confirmed=False) -> dict
    list_memories(companion_id) -> list[dict]  # owner's inspection, not inheritance
    correct_memory(memory_id, content) -> dict  # resets approval and sharing
    approve_memory(memory_id, *, confirmed=False) -> dict
    revoke_memory(memory_id) -> dict
    delete_memory(memory_id) -> bool  # hard delete, no content tombstone
    grant_shared(companion_id, memory_id, *, confirmed=False) -> None
    revoke_shared(companion_id, memory_id) -> None
    grant_project(companion_id, project_id, *, confirmed=False) -> None
    revoke_project(companion_id, project_id) -> None
    build_execution_context(companion_id, task_id, session_id, project_id=None,
                            *, memory_ids=None) -> dict
    validate_execution_context(snapshot, *, companion_id, task_id, session_id,
                               project_id=None) -> bool

Only trusted local consent/UI code should hold the store. 'approved=True' on
source='user' means a deliberate user save, NOT silent extraction. Other sources
must be tentative unless confirmed=True. Confirmation flags assert a consent
ceremony, not authentication. Never expose these methods as unrestricted model
or remote tools. Persist only curated text preferences/summaries, never raw
camera/screen/audio/document capture. Only user, outcome_summary and
curated_note source labels are accepted; they are attribution, not verification.

New identities inherit nothing. Shared records require approved content AND an
explicit per-record recipient grant. Project records stay owner-isolated and
require an exact project grant; a project ID alone grants nothing. Optional
memory_ids narrows selection; optional task_id on a record restricts relevance.
Build on every dispatch with actual registry companion ID and actual task/session
IDs, never sprite names or cached bindings. Snapshots are explanatory data only:
no snapshot, even fresh, authorizes actions. Validate with the independently
known execution tuple immediately before consumption, then apply Hermes intent
policy/confirmation separately. Any write invalidates old snapshots, including
across connections/restarts. Returned copies cannot be recalled from callers.

No PermissionedContext observations/grants are imported or persisted. Registry
CompanionConfig.companion_id is the identity key; display_name maps to name.
Archive is a memory-library operation; caller separately removes live registry
bindings. This module never starts/stops agents, captures data or calls APIs.
SQLite file is local plaintext, not an encrypted vault; protect its directory.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from .companion_registry import bounded_text


class CompanionMemoryStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys=ON')
        self._db.execute('PRAGMA secure_delete=ON')
        with self._db:
            self._db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    store_id TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS companions (
                    companion_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    role TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    companion_id TEXT NOT NULL REFERENCES companions(companion_id),
                    content TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL,
                    scope TEXT NOT NULL, project_id TEXT, task_id TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
                CREATE TABLE IF NOT EXISTS shared_grants (
                    companion_id TEXT NOT NULL REFERENCES companions(companion_id),
                    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                    PRIMARY KEY(companion_id,memory_id));
                CREATE TABLE IF NOT EXISTS project_grants (
                    companion_id TEXT NOT NULL REFERENCES companions(companion_id),
                    project_id TEXT NOT NULL, PRIMARY KEY(companion_id,project_id));
            ''')
            self._db.execute('INSERT OR IGNORE INTO metadata VALUES (1, ?, 0)', (uuid4().hex,))

    def close(self):
        self._db.close()

    def _bump(self):
        self._db.execute('UPDATE metadata SET revision=revision+1 WHERE singleton=1')

    def _companion(self, companion_id, *, active=True):
        row = self._db.execute('SELECT * FROM companions WHERE companion_id=?', (companion_id,)).fetchone()
        if row is None:
            raise KeyError('unknown companion')
        if active and row['archived']:
            raise PermissionError('companion archived')
        return dict(row)

    def create_companion(self, companion_id, name, role=''):
        bounded_text(companion_id, 'companion_id', 64)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', companion_id):
            raise ValueError('invalid companion_id')
        bounded_text(name, 'name', 80)
        bounded_text(role, 'role', 80, empty=True)
        with self._db:
            self._db.execute('INSERT INTO companions VALUES (?, ?, ?, 0)', (companion_id, name, role))
            self._bump()
        return self._companion(companion_id)

    def archive_companion(self, companion_id, archived=True):
        if type(archived) is not bool:
            raise ValueError('archived must be boolean')
        with self._db:
            self._bump()
            self._companion(companion_id, active=False)
            self._db.execute('UPDATE companions SET archived=? WHERE companion_id=?', (archived, companion_id))
            if archived:
                self._db.execute('DELETE FROM project_grants WHERE companion_id=?', (companion_id,))
                self._db.execute('''DELETE FROM shared_grants WHERE companion_id=? OR memory_id IN
                    (SELECT memory_id FROM memories WHERE companion_id=?)''', (companion_id, companion_id))
        return self._companion(companion_id, active=False)

    def list_companions(self, include_archived=False):
        return [dict(row) for row in self._db.execute(
            'SELECT * FROM companions WHERE (? OR archived=0) ORDER BY companion_id',
            (bool(include_archived),))]

    def _memory(self, memory_id):
        row = self._db.execute('SELECT * FROM memories WHERE memory_id=?', (memory_id,)).fetchone()
        if row is None:
            raise KeyError('unknown memory')
        return dict(row)

    @staticmethod
    def _content(content):
        if not isinstance(content, str) or not content.strip() or len(content) > 8192 or '\x00' in content:
            raise ValueError('bounded curated text required')

    def add_memory(self, companion_id, content, source='user', approved=True,
                   scope='companion', project_id=None, *, task_id=None, confirmed=False):
        self._companion(companion_id)
        self._content(content)
        if source not in ('user', 'outcome_summary', 'curated_note'):
            raise ValueError('curated source required; raw sensing prohibited')
        if type(approved) is not bool:
            raise ValueError('approved must be boolean')
        if approved and source != 'user' and confirmed is not True:
            raise PermissionError('explicit approval required for derived memory')
        if scope not in ('companion', 'shared', 'project'):
            raise ValueError('invalid memory scope')
        if scope == 'project':
            bounded_text(project_id, 'project_id')
        elif project_id is not None:
            raise ValueError('project_id requires project scope')
        if task_id is not None:
            bounded_text(task_id, 'task_id')
        memory_id = uuid4().hex
        with self._db:
            self._db.execute('''INSERT INTO memories
                (memory_id,companion_id,content,source,state,scope,project_id,task_id)
                VALUES (?,?,?,?,?,?,?,?)''',
                (memory_id, companion_id, content, source, 'approved' if approved else 'tentative',
                 scope, project_id, task_id))
            self._bump()
        return self._memory(memory_id)

    def list_memories(self, companion_id):
        self._companion(companion_id, active=False)
        return [dict(row) for row in self._db.execute(
            'SELECT * FROM memories WHERE companion_id=? ORDER BY rowid', (companion_id,))]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def grant_project(self, companion_id, project_id, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError('explicit project permission required')
        bounded_text(project_id, 'project_id')
        with self._db:
            self._bump()
            self._companion(companion_id)
            self._db.execute('INSERT OR IGNORE INTO project_grants VALUES (?,?)', (companion_id, project_id))

    def revoke_project(self, companion_id, project_id):
        with self._db:
            self._db.execute('DELETE FROM project_grants WHERE companion_id=? AND project_id=?', (companion_id, project_id))
            self._bump()

    def grant_shared(self, companion_id, memory_id, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError('explicit per-record inheritance approval required')
        with self._db:
            # Acquire write lock before checking state to prevent a concurrent revoke race.
            self._bump()
            self._companion(companion_id)
            rec = self._memory(memory_id)
            self._companion(rec['companion_id'])
            if rec['scope'] != 'shared' or rec['state'] != 'approved':
                raise PermissionError('only approved shared memory can be inherited')
            self._db.execute('INSERT OR IGNORE INTO shared_grants VALUES (?,?)', (companion_id, memory_id))

    def revoke_shared(self, companion_id, memory_id):
        with self._db:
            self._db.execute('DELETE FROM shared_grants WHERE companion_id=? AND memory_id=?', (companion_id, memory_id))
            self._bump()

    def correct_memory(self, memory_id, content):
        self._content(content)
        self._memory(memory_id)
        with self._db:
            self._db.execute('''UPDATE memories SET content=?, state='tentative',
                version=version+1, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE memory_id=?''', (content, memory_id))
            self._db.execute('DELETE FROM shared_grants WHERE memory_id=?', (memory_id,))
            self._bump()
        return self._memory(memory_id)

    def _set_state(self, memory_id, state):
        self._memory(memory_id)
        with self._db:
            self._db.execute('''UPDATE memories SET state=?,version=version+1,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE memory_id=?''', (state, memory_id))
            if state != 'approved':
                self._db.execute('DELETE FROM shared_grants WHERE memory_id=?', (memory_id,))
            self._bump()
        return self._memory(memory_id)

    def approve_memory(self, memory_id, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError('explicit local approval required')
        return self._set_state(memory_id, 'approved')

    def revoke_memory(self, memory_id):
        return self._set_state(memory_id, 'revoked')

    def delete_memory(self, memory_id):
        with self._db:
            deleted = self._db.execute('DELETE FROM memories WHERE memory_id=?', (memory_id,)).rowcount > 0
            if deleted:
                self._bump()
        return deleted

    def validate_execution_context(self, snapshot, *, companion_id, task_id, session_id, project_id=None):
        """Freshness/integrity check only, never an action permission check."""
        if not isinstance(snapshot, dict):
            return False
        try:
            return snapshot == self.build_execution_context(
                companion_id, task_id, session_id, project_id,
                memory_ids=snapshot.get('memory_ids'))
        except (KeyError, ValueError, TypeError, PermissionError):
            return False

    def build_execution_context(self, companion_id, task_id, session_id, project_id=None, *, memory_ids=None):
        if memory_ids is not None:
            if not isinstance(memory_ids, (list, tuple)):
                raise ValueError('memory_ids must be an explicit list or tuple')
            for mid in memory_ids:
                bounded_text(mid, 'memory_id', 64)
            memory_ids = sorted(set(memory_ids))
        # One consistent read transaction; revision and permissions cannot be torn.
        with self._db:
            self._db.execute('BEGIN')
            return self._build_context(companion_id, task_id, session_id, project_id, memory_ids)

    def _build_context(self, companion_id, task_id, session_id, project_id, memory_ids):
        self._companion(companion_id)
        bounded_text(task_id, 'task_id')
        bounded_text(session_id, 'session_id')
        if project_id is not None:
            bounded_text(project_id, 'project_id')
        meta = self._db.execute('SELECT * FROM metadata').fetchone()
        records = [dict(r) for r in self._db.execute('''
            SELECT m.* FROM memories m JOIN companions c ON c.companion_id=m.companion_id
            WHERE c.archived=0 AND m.state='approved' AND (m.task_id IS NULL OR m.task_id=?)
              AND ((m.scope='companion' AND m.companion_id=?) OR
                   (m.scope='shared' AND EXISTS (SELECT 1 FROM shared_grants g
                    WHERE g.memory_id=m.memory_id AND g.companion_id=?)) OR
                   (m.scope='project' AND m.companion_id=? AND m.project_id=?
                    AND EXISTS (SELECT 1 FROM project_grants p
                    WHERE p.companion_id=m.companion_id AND p.project_id=m.project_id)))
            ORDER BY m.rowid''', (task_id, companion_id, companion_id, companion_id, project_id))
            if memory_ids is None or r['memory_id'] in memory_ids]
        return dict(store_id=meta['store_id'], revision=meta['revision'],
                    companion_id=companion_id, task_id=task_id, session_id=session_id,
                    project_id=project_id, memory_ids=memory_ids,
                    memories=records, authorizes_actions=False)
