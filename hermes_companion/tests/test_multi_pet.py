import importlib
import unittest


class MultiPetTests(unittest.TestCase):
    def test_exact_session_only_and_unbound_never_animates(self):
        mod = importlib.import_module('hermes_companion.renderer.multi_pet')
        fleet = mod.FleetModel([mod.PetBinding('Alpha', 'a'), mod.PetBinding('Beta', 'b'), mod.PetBinding('Free')])
        routed = fleet.accept({'event': 'tool.started', 'session_id': 'a', 'tool': 'terminal'}, now=10)
        self.assertEqual(list(routed), [0])
        self.assertEqual(fleet.pets[0].last_event, 'tool.started')
        self.assertEqual(fleet.pets[1].last_event, '')
        self.assertEqual(fleet.pets[2].status(10, True), 'UNBOUND')
        self.assertEqual(fleet.accept({'event': 'tool.started'}, now=11), {})

    def test_shared_router_rejects_wrong_agent_and_invalid_provenance(self):
        from hermes_companion.renderer.multi_pet import FleetModel, PetBinding
        f = FleetModel([PetBinding('A', 'a')])
        self.assertEqual(f.accept({'session_id':'a', 'agent_id':'other', 'event':'tool.started'}), {})
        self.assertEqual(f.accept({'session_id':'a', 'ts':float('nan'), 'event':'tool.started'}), {})
        self.assertEqual(f.accept({'session_id':'a', 'event':'tool.started', 'target_session_id':'b'}), {})
        self.assertIsNone(f.pets[0].last_seen)
        self.assertEqual(f.registry.companions[0].context_permissions, ())

    def test_model_rejects_ambiguous_duplicate_bindings(self):
        from hermes_companion.renderer.multi_pet import FleetModel, PetBinding
        for pets in [[], [PetBinding('A')]*5, [PetBinding('A'), PetBinding('A')],
                     [PetBinding('A', 'same'), PetBinding('B', 'same')], [PetBinding('bad\nlabel')]]:
            with self.assertRaises(ValueError):
                FleetModel(pets)

    def test_category_and_combos_remain_per_session(self):
        from hermes_companion.renderer.multi_pet import FleetModel, PetBinding
        f = FleetModel([PetBinding('A','a'), PetBinding('B','b')])
        f.accept({'session_id':'a', 'event':'tool.started', 'tool':'terminal'})
        f.accept({'session_id':'a', 'event':'tool.finished', 'tool':'terminal'})
        f.accept({'session_id':'b', 'event':'tool.started', 'tool':'web_search'})
        self.assertEqual(f.pets[0].combo, 2)
        self.assertEqual(f.pets[1].combo, 1)
        self.assertEqual(f.pets[1].category, 'web')
        for record in [None, [], {'session_id': []}, {'session_id':'a', 'event':'unknown'},
                       {'session_id':'a','event':'tool.started','tool':{'secret':'not displayed'}}]:
            self.assertEqual(f.accept(record), {})

    def test_tail_starts_at_end_keeps_partial_lines_and_survives_rotation(self):
        import tempfile
        import json
        from pathlib import Path
        from hermes_companion.renderer import multi_pet as m
        from hermes_companion.core.event_auth import sign_record
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'events.jsonl'
            path.write_text('{"event":"old"}\n')
            key = b'k' * 32
            tail = m.BoundedTail(path, auth_key=key)
            self.assertEqual(tail.poll(), [])
            with path.open('a') as f:
                f.write(json.dumps(sign_record({'event': 'new'}, key))[:-1])
            self.assertEqual(tail.poll(), [])
            with path.open('a') as f:
                f.write('}\n[]\n{"event":"unsigned"}\n')
            self.assertEqual(tail.poll(), [{'event': 'new'}])
            path.write_text(json.dumps(sign_record({}, key)) + '\n')
            self.assertEqual(tail.poll(), [{}])
            path.unlink()
            self.assertEqual(tail.poll(), [])
            self.assertFalse(tail.available)

    def test_ui_cli_validation_and_truthful_states(self):
        from hermes_companion.renderer import multi_pet as m
        self.assertTrue(callable(m.MultiPetDock))
        self.assertEqual(m.parse_binding('Scout=session-a').session_id, 'session-a')
        self.assertEqual(m.parse_binding('Free').session_id, '')
        for text in ['', '=abc', 'A=x=y', 'A=\nsecret']:
            with self.assertRaises(ValueError):
                m.parse_binding(text)
        p = m.PetBinding('A', 's')
        self.assertEqual(p.status(50, False), 'DISCONNECTED')
        self.assertEqual(p.status(50, True), 'AWAITING SESSION EVENT')
        p.last_seen = 0
        self.assertEqual(p.status(50, True), 'STALE / ACTIVITY UNKNOWN')


if __name__ == '__main__':
    unittest.main()
