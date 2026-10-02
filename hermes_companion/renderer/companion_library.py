"""Local-only saved companion library. Does not start or bind Hermes agents."""
from __future__ import annotations

import os
from pathlib import Path


def default_database_path() -> Path:
    """Keep saved identities across window/process restarts, outside the repo."""
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return base / 'hermes' / 'companion' / 'library.sqlite3'


import sqlite3
import tkinter as tk
from tkinter import ttk
from uuid import uuid4


class CompanionLibrary:
    """Tk view over the real local store; no network or live-pet control."""

    def __init__(self, root, store, database_path):
        self.root, self.store = root, store
        self.selected_id = None
        self.profiles = {}
        root.title('Companion Library — saved identities')
        root.geometry('1040x790')
        root.minsize(960, 730)
        self.status_var = tk.StringVar(value='Create a profile or reopen an existing identity.')
        self.identity_var = tk.StringVar(value='No profile open — not a running agent')
        self.name_var, self.role_var = tk.StringVar(), tk.StringVar()
        self.show_archived = tk.BooleanVar(value=False)
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Companion Library', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Saved profiles are not running agents. Reopening does not start Hermes or change your live pet.').pack(anchor='w', pady=(4, 12))
        ttk.Label(outer, text=f'Local plaintext database: {database_path}', wraplength=960).pack(anchor='w')
        create = ttk.LabelFrame(outer, text='Create a lasting identity', padding=10)
        create.pack(fill='x', pady=10)
        ttk.Label(create, text='Name').grid(row=0, column=0, sticky='w')
        ttk.Entry(create, textvariable=self.name_var, width=26).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(create, text='Role (optional)').grid(row=0, column=2)
        ttk.Entry(create, textvariable=self.role_var, width=30).grid(row=0, column=3, padx=6)
        self.create_button = ttk.Button(create, text='Create profile', command=lambda: self.run(self.create_profile))
        self.create_button.grid(row=0, column=4, padx=8)
        listing = ttk.Frame(outer)
        listing.pack(fill='x')
        ttk.Checkbutton(listing, text='Include archived profiles', variable=self.show_archived, command=lambda: self.run(self.refresh_profiles)).pack(side='left')
        self.refresh_button = ttk.Button(listing, text='Refresh', command=lambda: self.run(self.refresh_profiles))
        self.refresh_button.pack(side='right')
        self.profile_tree = ttk.Treeview(outer, columns=('name', 'role', 'state', 'id'), show='headings', height=3, selectmode='browse')
        for key, label, width in [('name', 'Name', 160), ('role', 'Role', 220), ('state', 'Saved state', 110), ('id', 'Stable identity', 330)]:
            self.profile_tree.heading(key, text=label)
            self.profile_tree.column(key, width=width)
        self.profile_tree.pack(fill='x', pady=6)
        self.profile_tree.bind('<Double-1>', lambda event: self.run(self.open_profile))
        actions = ttk.Frame(outer)
        actions.pack(fill='x')
        self.open_button = ttk.Button(actions, text='Reopen selected', command=lambda: self.run(self.open_profile))
        self.open_button.pack(side='left')
        self.archive_button = ttk.Button(actions, text='Archive open profile', command=lambda: self.run(lambda: self.set_archived(True)))
        self.archive_button.pack(side='left', padx=6)
        self.restore_button = ttk.Button(actions, text='Restore open profile', command=lambda: self.run(lambda: self.set_archived(False)))
        self.restore_button.pack(side='left')
        ttk.Label(outer, textvariable=self.identity_var, wraplength=980, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=12)
        self.detail_frame = ttk.Frame(outer)
        self.detail_frame.pack(fill='both', expand=True)
        self.build_memory_ui()
        ttk.Label(outer, textvariable=self.status_var, wraplength=920).pack(side='bottom', fill='x', pady=(8, 0), before=self.detail_frame)
        self.refresh_profiles()

    def run(self, action):
        try:
            action()
        except (ValueError, KeyError, PermissionError, sqlite3.Error) as exc:
            self.status_var.set(f'Not saved: {exc}')

    def refresh_profiles(self):
        profiles = self.store.list_companions(include_archived=True)
        self.profiles = {p['companion_id']: p for p in profiles}
        self.profile_tree.delete(*self.profile_tree.get_children())
        for p in profiles:
            if not p['archived'] or self.show_archived.get():
                self.profile_tree.insert('', 'end', iid=p['companion_id'], values=(p['name'], p['role'], 'Archived' if p['archived'] else 'Saved', p['companion_id']))
        if self.selected_id in self.profiles:
            self.show_identity()
            self.refresh_memories()

    def create_profile(self):
        cid = 'companion-' + uuid4().hex
        self.store.create_companion(cid, self.name_var.get(), self.role_var.get())
        self.selected_id = cid
        self.refresh_profiles()
        self.profile_tree.selection_set(cid)
        self.name_var.set('')
        self.role_var.set('')
        self.status_var.set('Profile saved locally. No agent was started.')

    def open_profile(self):
        selection = self.profile_tree.selection()
        if not selection:
            raise ValueError('select a profile to reopen')
        self.selected_id = selection[0]
        self.refresh_profiles()
        self.status_var.set('Saved identity reopened. Runtime agent status is not connected.')

    def show_identity(self):
        p = self.profiles[self.selected_id]
        self.identity_var.set(f"{p['name']} | {p['companion_id']} | {'Archived' if p['archived'] else 'Saved profile'} — not a running agent")

    def require_profile(self):
        if not self.selected_id:
            raise ValueError('reopen or create a profile first')
        return self.selected_id

    def build_memory_ui(self):
        self.notebook = ttk.Notebook(self.detail_frame)
        self.notebook.pack(fill='both', expand=True)
        memory = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(memory, text='Inspectable memory')
        ttk.Label(memory, text='Private to this identity. Select a row to inspect its complete text and provenance. No automatic collection.').pack(anchor='w')
        rows = ttk.Frame(memory)
        rows.pack(fill='both', expand=True, pady=6)
        self.memory_tree = ttk.Treeview(rows, columns=('content', 'source', 'scope', 'approved'), show='headings', height=3, selectmode='browse')
        for key, label, width in [('content', 'Preference / note', 490), ('source', 'Source', 100), ('scope', 'Scope', 100), ('approved', 'Approved', 75)]:
            self.memory_tree.heading(key, text=label)
            self.memory_tree.column(key, width=width)
        self.memory_tree.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(rows, orient='vertical', command=self.memory_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.memory_tree.configure(yscrollcommand=scrollbar.set)
        self.memory_tree.bind('<<TreeviewSelect>>', lambda event: self.run(self.inspect_memory))
        self.memory_meta_var = tk.StringVar(value='No memory selected.')
        ttk.Label(memory, textvariable=self.memory_meta_var, wraplength=900).pack(anchor='w')
        self.memory_text = tk.Text(memory, height=3, wrap='word', font=('Segoe UI', 10), undo=True)
        self.memory_text.pack(fill='x', pady=6)
        self.approved_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(memory, text='I approve saving this text as memory for this companion only (no secrets or raw captures).', variable=self.approved_var).pack(anchor='w')
        buttons = ttk.Frame(memory)
        buttons.pack(fill='x', pady=6)
        self.add_button = ttk.Button(buttons, text='Add approved memory', command=lambda: self.run(self.add_memory))
        self.add_button.pack(side='left')
        self.correct_button = ttk.Button(buttons, text='Correct selected + approve', command=lambda: self.run(self.correct_memory))
        self.correct_button.pack(side='left', padx=6)
        self.forget_button = ttk.Button(buttons, text='Forget selected permanently', command=lambda: self.run(self.forget_memory))
        self.forget_button.pack(side='left')
        ttk.Label(memory, text='Forget deletes the local record. It cannot recall copies already exported or included in backups.').pack(anchor='w')
        self.memories = {}
        preview = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(preview, text='Execution context preview (no execution)')
        ttk.Label(preview, text='Build an explanatory snapshot for identifiers you enter. This does not connect to or execute a Hermes session.', wraplength=900).pack(anchor='w')
        fields = ttk.Frame(preview)
        fields.pack(fill='x', pady=10)
        self.task_var, self.session_var = tk.StringVar(), tk.StringVar()
        for label, var in [('Task ID', self.task_var), ('Session ID', self.session_var)]:
            ttk.Label(fields, text=label).pack(side='left', padx=6)
            ttk.Entry(fields, textvariable=var, width=28).pack(side='left')
            var.trace_add('write', lambda *args: self.clear_preview())
        self.preview_button = ttk.Button(fields, text='Build preview', command=lambda: self.run(self.build_preview))
        self.preview_button.pack(side='left', padx=10)
        self.preview_text = tk.Text(preview, height=8, wrap='word', state='disabled')
        self.preview_text.pack(fill='both', expand=True)
        ttk.Label(preview, text='Point-in-time preview only; external writes may make it stale. Rebuild before inspection. No action authority.').pack(anchor='w', pady=6)
        self.clear_preview()

    def clear_preview(self):
        self.set_preview('No current preview. Select a saved profile, enter task/session IDs, then Build preview.')

    def set_preview(self, text):
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', text)
        self.preview_text.configure(state='disabled')

    def build_preview(self):
        import json
        self.clear_preview()
        result = self.store.build_execution_context(self.require_profile(), self.task_var.get(), self.session_var.get(), project_id=None)
        self.set_preview(json.dumps(result, indent=2, ensure_ascii=False))
        self.status_var.set('Context preview built from the local store. Nothing executed or sent to Hermes.')

    def refresh_memories(self):
        self.clear_preview()
        self.memories = {m['memory_id']: m for m in self.store.list_memories(self.require_profile())}
        self.memory_tree.delete(*self.memory_tree.get_children())
        for mid, m in self.memories.items():
            self.memory_tree.insert('', 'end', iid=mid, values=(m['content'], m['source'], m['scope'], m['state']))
        self.memory_text.delete('1.0', 'end')
        self.memory_text.edit_reset()
        self.memory_meta_var.set('No memory selected. Type a new preference or select an existing row.')
        self.approved_var.set(False)

    def selected_memory(self):
        selected = self.memory_tree.selection()
        if not selected or selected[0] not in self.memories:
            raise ValueError('select a memory from this open profile')
        return selected[0]

    def inspect_memory(self):
        if not self.memory_tree.selection():
            return
        mid = self.selected_memory()
        m = self.memories[mid]
        self.memory_text.delete('1.0', 'end')
        self.memory_text.insert('1.0', m['content'])
        self.approved_var.set(False)
        self.memory_meta_var.set(f"ID: {mid} | Source: {m['source']} | Scope: {m['scope']} | Approved: {m['state']} | Version: {m['version']} | Updated: {m['updated_at']}")

    def approved_text(self):
        self.require_profile()
        if not self.approved_var.get():
            raise ValueError('check the approval box to approve saving this text')
        text = self.memory_text.get('1.0', 'end-1c')
        if not text.strip():
            raise ValueError('enter a preference or curated note')
        return text

    def add_memory(self):
        text = self.approved_text()
        self.store.add_memory(self.require_profile(), text, source='user', approved=True, scope='companion', project_id=None)
        self.refresh_memories()
        self.status_var.set('Approved memory saved for this companion only.')

    def correct_memory(self):
        text = self.approved_text()
        mid = self.selected_memory()
        if self.memories[mid]['scope'] != 'companion':
            raise ValueError('only companion-private memories can be edited here')
        self.store.correct_memory(mid, text)
        self.store.approve_memory(mid, confirmed=True)
        self.refresh_memories()
        self.status_var.set('Correction saved and explicitly approved. Previous preview is no longer current.')

    def forget_memory(self):
        self.store.delete_memory(self.selected_memory())
        self.refresh_memories()
        self.status_var.set('Memory forgotten from the local store. Existing exports/backups are not recalled.')

    def set_archived(self, archived):
        self.store.archive_companion(self.require_profile(), archived=archived)
        self.refresh_profiles()
        self.status_var.set('Profile archived; memory retained, no live agent stopped.' if archived else 'Profile restored with the same identity.')


def main(argv=None):
    import argparse
    from hermes_companion.core.companion_memory import CompanionMemoryStore
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=default_database_path(), help='Local persistent SQLite database path')
    args = parser.parse_args(argv)
    store = CompanionMemoryStore(args.db)
    root = None
    try:
        root = tk.Tk()
        CompanionLibrary(root, store, args.db)
        root.update_idletasks()
        print(f'COMPANION LIBRARY READY pid={os.getpid()} database={args.db}', flush=True)
        root.mainloop()
    finally:
        store.close()
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass


if __name__ == '__main__':
    main()
