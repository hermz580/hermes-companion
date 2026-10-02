import unittest
from hermes_companion.core.attention import AttentionModel
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.renderer.petdex_overlay import PetdexOverlay, motion_recipe


class AttentionTests(unittest.TestCase):
    def test_approval_survives_background_activity(self):
        model = AttentionModel()
        model.ingest(SemanticEvent(EventKind.APPROVAL_REQUIRED))
        for kind in (EventKind.TOOL_FINISHED, EventKind.AGENT_IDLE, EventKind.TASK_COMPLETE):
            self.assertTrue(model.ingest(SemanticEvent(kind)).needs_user)
        self.assertFalse(model.ingest(SemanticEvent(EventKind.APPROVAL_APPROVED)).needs_user)

    def test_failure_is_not_invented_recovery(self):
        model = AttentionModel()
        model.ingest(SemanticEvent(EventKind.TOOL_FAILED))
        self.assertEqual(model.ingest(SemanticEvent(EventKind.IDLE)).state, 'issue')

    def test_untrusted_category_not_displayed(self):
        model = AttentionModel()
        signal = model.ingest(SemanticEvent(EventKind.TOOL_STARTED, category='SECRET /private/file'))
        self.assertEqual(signal.label, 'Working with general')

    def test_completion_settles_and_attention_keeps_waving(self):
        from collections import deque
        overlay = PetdexOverlay.__new__(PetdexOverlay)
        overlay._queue = deque()
        overlay._beat = None
        overlay._attention_started = 0
        overlay._attention_state = 'complete'
        overlay._start_next(1000)
        self.assertEqual(overlay.row, 'jumping')
        overlay._start_next(3000)
        self.assertEqual(overlay.row, 'idle')
        overlay._attention_state = 'needs-you'
        overlay._start_next(60000)
        self.assertEqual(overlay.row, 'waving')

    def test_authored_action_order_preserved(self):
        for pose in ('jump', 'fall', 'recover', 'run_to_workspace'):
            for ordinal in range(20):
                recipe = motion_recipe(pose, 'development', ordinal)
                self.assertEqual(recipe.direction, 1)
                self.assertFalse(recipe.ping_pong)

if __name__ == '__main__':
    unittest.main()
