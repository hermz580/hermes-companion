"""Pure, deterministic fixtures only: no real sensors or observations."""
import unittest
from datetime import datetime, timedelta, timezone
from hermes_companion.core.permissioned_context import ContextScope, PermissionedContext


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.context = PermissionedContext(clock=lambda: self.now)

    def test_default_off_and_exact_independent_grants(self):
        camera = ContextScope.CAMERA
        document = ContextScope.SELECTED_DOCUMENT
        window = ContextScope.SELECTED_WINDOW
        self.assertIsNone(self.context.permission(camera, "camera-1"))
        self.assertEqual(self.context.snapshot(), ())
        with self.assertRaises(PermissionError):
            self.context.grant(camera, "camera-1", confirmed=False)
        grant = self.context.grant(camera, "camera-1", confirmed=True)
        self.assertEqual(self.context.permission(camera, "camera-1"), grant)
        self.assertIsNone(self.context.permission(camera, "camera-2"))
        self.assertIsNone(self.context.permission(document, "camera-1"))
        self.assertIsNone(self.context.permission(window, "camera-1"))
        doc = self.context.grant(document, "document-1", confirmed=True)
        self.assertEqual(self.context.permission(document, "document-1"), doc)
        self.assertIsNone(self.context.permission(window, "document-1"))

    def test_revocation_expiry_and_regrant(self):
        scope = ContextScope.CAMERA
        old = self.context.grant(scope, "camera-1", confirmed=True, ttl_seconds=10)
        self.assertTrue(self.context.revoke(old.grant_id))
        self.assertFalse(self.context.revoke(old.grant_id))
        self.assertIsNone(self.context.permission(scope, "camera-1"))
        new = self.context.grant(scope, "camera-1", confirmed=True, ttl_seconds=10)
        self.assertNotEqual(new.grant_id, old.grant_id)
        self.now += timedelta(seconds=10)
        self.assertIsNone(self.context.permission(scope, "camera-1"))
        self.now -= timedelta(seconds=5)
        self.assertIsNone(self.context.permission(scope, "camera-1"))
        self.context.grant(scope, "camera-1", confirmed=True)
        self.context.revoke_all()
        self.assertIsNone(self.context.permission(scope, "camera-1"))

    def test_grants_reject_invalid_scope_source_consent_and_ttl(self):
        for scope, source, ttl in [
            ("camera", "camera-1", 30),
            (ContextScope.CAMERA, "C:/private/file", 30),
            (ContextScope.CAMERA, "*", 30),
            (ContextScope.CAMERA, "", 30),
            (ContextScope.CAMERA, "a" * 65, 30),
            (ContextScope.CAMERA, "camera-1", 0),
            (ContextScope.CAMERA, "camera-1", float("nan")),
            (ContextScope.CAMERA, "camera-1", float("inf")),
            (ContextScope.CAMERA, "camera-1", True),
            (ContextScope.CAMERA, "camera-1", 3601),
        ]:
            with self.subTest(scope=scope, source=source, ttl=ttl):
                with self.assertRaises(ValueError):
                    self.context.grant(scope, source, confirmed=True, ttl_seconds=ttl)
        with self.assertRaises(PermissionError):
            self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=1)

    def _observe(self, grant, **changes):
        args = dict(grant_id=grant.grant_id, scope=grant.scope,
                    source_id=grant.source_id, signal="presence_present",
                    observed_at=self.now, max_age_seconds=5)
        args.update(changes)
        return self.context.observe(**args)

    def test_observation_provenance_freshness_and_minimal_record(self):
        from dataclasses import asdict, FrozenInstanceError
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        observed_at = self.now
        self.now += timedelta(seconds=1)
        observation = self._observe(grant, observed_at=observed_at)
        self.assertEqual(observation.observed_at, observed_at)
        self.assertEqual(observation.received_at, self.now)
        self.assertEqual(observation.stale_at, observed_at + timedelta(seconds=5))
        self.assertEqual(observation.grant_id, grant.grant_id)
        self.assertEqual(self.context.snapshot(), (observation,))
        self.assertEqual(set(asdict(observation)), {
            "grant_id", "scope", "source_id", "signal", "observed_at", "received_at", "stale_at"})
        with self.assertRaises(FrozenInstanceError):
            observation.signal = "private text"
        self.now = observed_at + timedelta(seconds=5)
        self.assertTrue(observation.is_stale(self.now))
        self.assertEqual(self.context.snapshot(), ())

    def test_observations_fail_closed_for_missing_revoked_or_wrong_grant(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        for changes in [dict(grant_id="missing"), dict(source_id="camera-2"),
                        dict(scope=ContextScope.SELECTED_WINDOW)]:
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                self._observe(grant, **changes)
        self._observe(grant)
        self.context.revoke(grant.grant_id)
        self.assertEqual(self.context.snapshot(), ())
        with self.assertRaises(PermissionError):
            self._observe(grant)
        self.context.grant(grant.scope, grant.source_id, confirmed=True)
        with self.assertRaises(PermissionError):
            self._observe(grant)
        self.assertEqual(self.context.snapshot(), ())

    def test_no_payload_unknown_signals_or_invalid_source_times(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        self.now += timedelta(seconds=10)
        for changes in [dict(signal="raw private text"), dict(signal="selection_ready"),
                        dict(observed_at=self.now + timedelta(seconds=1)),
                        dict(observed_at=grant.granted_at - timedelta(seconds=1)),
                        dict(observed_at=self.now - timedelta(seconds=5)),
                        dict(observed_at=datetime(2026, 1, 1)),
                        dict(observed_at="2026-01-01"),
                        dict(max_age_seconds=0), dict(max_age_seconds=61),
                        dict(max_age_seconds=float("nan"))]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self._observe(grant, **changes)
        with self.assertRaises(TypeError):
            self._observe(grant, raw_text="private text")
        self.assertEqual(self.context.snapshot(), ())

    def test_selected_sources_are_separate_and_latest_only(self):
        for scope in (ContextScope.SELECTED_DOCUMENT, ContextScope.SELECTED_WINDOW):
            grant = self.context.grant(scope, "selected-1", confirmed=True)
            self._observe(grant, signal="selection_ready")
            self.now += timedelta(seconds=1)
            self._observe(grant, signal="selection_ready")
            with self.assertRaises(ValueError):
                self._observe(grant, signal="presence_present")
        self.assertEqual(len(self.context.snapshot()), 2)
        self.context.revoke_all()
        self.assertEqual(self.context.snapshot(), ())

    def test_replacement_grant_removes_observations(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        self._observe(grant)
        self.context.grant(grant.scope, grant.source_id, confirmed=True)
        self.assertEqual(self.context.snapshot(), ())

    def test_clock_rollback_clears_permissions_and_observations(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        self.now += timedelta(seconds=10)
        self._observe(grant)
        self.now -= timedelta(seconds=1)
        self.assertEqual(self.context.snapshot(), ())
        self.assertIsNone(self.context.permission(grant.scope, grant.source_id))

    def test_out_of_order_observation_cannot_replace_newer_context(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        self.now += timedelta(seconds=2)
        latest = self._observe(grant)
        with self.assertRaises(ValueError):
            self._observe(grant, observed_at=self.now - timedelta(seconds=1),
                          signal="presence_absent")
        self.assertEqual(self.context.snapshot(), (latest,))
        with self.assertRaises(ValueError):
            self._observe(grant)  # Duplicate source timestamp cannot renew TTL.

    def test_grant_expiry_caps_observation_and_forbids_ingestion(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True, ttl_seconds=2)
        observation = self._observe(grant, max_age_seconds=60)
        self.assertEqual(observation.stale_at, grant.expires_at)
        self.now += timedelta(seconds=2)
        with self.assertRaises(PermissionError):
            self._observe(grant)
        self.assertEqual(self.context.snapshot(), ())

    def test_invalid_clock_rejects_grant(self):
        self.now = datetime(2026, 1, 1)
        with self.assertRaises(ValueError):
            self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)

    def test_capacity_is_bounded(self):
        for index in range(32):
            self.context.grant(ContextScope.SELECTED_DOCUMENT, f"document-{index}", confirmed=True)
        with self.assertRaises(ValueError):
            self.context.grant(ContextScope.SELECTED_DOCUMENT, "document-overflow", confirmed=True)
        self.context.grant(ContextScope.SELECTED_DOCUMENT, "document-0", confirmed=True)

    def test_stale_sample_cannot_be_replayed_with_a_longer_lifetime(self):
        grant = self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        sample_time = self.now
        self._observe(grant)
        self.now += timedelta(seconds=5)
        self.assertEqual(self.context.snapshot(), ())
        with self.assertRaises(ValueError):
            self._observe(grant, observed_at=sample_time, max_age_seconds=60)

    def test_default_off_rejects_observation_and_new_instance_has_no_consent(self):
        with self.assertRaises(PermissionError):
            self.context.observe(grant_id="untrusted", scope=ContextScope.CAMERA,
                                 source_id="camera-1", signal="presence_present",
                                 observed_at=self.now)
        self.context.grant(ContextScope.CAMERA, "camera-1", confirmed=True)
        fresh = PermissionedContext(clock=lambda: self.now)
        self.assertIsNone(fresh.permission(ContextScope.CAMERA, "camera-1"))
        self.assertEqual(fresh.snapshot(), ())


if __name__ == "__main__":
    unittest.main()
