"""Regression: two companion plugins must never shadow each other's bundle.

Both ``hermes-companion`` and ``hermes-companion-context`` ship a TOP-LEVEL
``hermes_companion`` package and each puts its own directory on ``sys.path``.
Whichever directory lands first owns that name process-wide, so a *partial*
bundle (the context plugin previously shipped only ``core/``) silently wins and
``hermes_companion.behavior`` stops resolving — the companion plugin's hook then
raises ``ModuleNotFoundError``, which its own fail-open handler swallows, and
every event is dropped with no visible error.

The contract these tests pin: a bundled copy of the shared package is COMPLETE,
and a process whose path starts at either plugin directory can still import the
behavior engine.

Run:  python -m hermes_companion.tests.test_plugin_bundle_shadowing
"""
import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The subpackages the companion plugin's live path actually imports.
REQUIRED_SUBPACKAGES = ("core", "behavior")


def _load_installer(dotted: str):
    """Import a build script from the repo (kept as a plain module path)."""
    return importlib.import_module(dotted)


class BundleCompletenessTest(unittest.TestCase):
    def test_context_bundle_is_complete(self):
        """install.py must ship the whole package, not just core/."""
        install = _load_installer("hermes_companion.plugin_context.install")
        with tempfile.TemporaryDirectory() as tmp:
            install.build(tmp)
            pkg = Path(tmp) / "plugins" / "hermes-companion-context" / "hermes_companion"
            self.assertTrue(pkg.is_dir(), "context plugin bundled no package")
            for name in REQUIRED_SUBPACKAGES:
                self.assertTrue(
                    (pkg / name / "__init__.py").is_file(),
                    f"context bundle is missing {name}/ — a partial copy can shadow the "
                    f"companion plugin's complete one",
                )

    def test_companion_bundle_is_complete(self):
        install = _load_installer("hermes_companion.plugin.install")
        with tempfile.TemporaryDirectory() as tmp:
            install.build(tmp)
            pkg = Path(tmp) / "plugins" / "hermes-companion" / "hermes_companion"
            self.assertTrue(pkg.is_dir(), "companion plugin bundled no package")
            for name in REQUIRED_SUBPACKAGES:
                self.assertTrue(
                    (pkg / name / "__init__.py").is_file(),
                    f"companion bundle is missing {name}/",
                )


class PathPriorityTest(unittest.TestCase):
    """Whichever plugin directory is first on sys.path, the engine must import."""

    def _assert_engine_imports(self, first_dir: Path):
        code = (
            "import sys; sys.path.insert(0, r'%s');"
            "from hermes_companion.behavior.behavior_engine import BehaviorEngine;"
            "print('ENGINE_OK')" % str(first_dir)
        )
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(
            proc.returncode, 0,
            f"behavior engine unreachable with {first_dir} first on sys.path:\n"
            f"{proc.stdout}\n{proc.stderr}",
        )
        self.assertIn("ENGINE_OK", proc.stdout)

    def test_context_dir_first_still_resolves_engine(self):
        """The exact failure mode: context plugin's dir occupies sys.path[0]."""
        ctx_install = _load_installer("hermes_companion.plugin_context.install")
        with tempfile.TemporaryDirectory() as tmp:
            ctx_install.build(tmp)  # sibling companion plugin absent
            ctx_dir = Path(tmp) / "plugins" / "hermes-companion-context"
            self._assert_engine_imports(ctx_dir)

    def test_both_plugins_installed_context_first(self):
        """With both installed, the shared name must resolve to a complete copy."""
        ctx_install = _load_installer("hermes_companion.plugin_context.install")
        comp_install = _load_installer("hermes_companion.plugin.install")
        with tempfile.TemporaryDirectory() as tmp:
            ctx_install.build(tmp)
            comp_install.build(tmp)
            ctx_dir = Path(tmp) / "plugins" / "hermes-companion-context"
            self._assert_engine_imports(ctx_dir)


class BundleFreshnessTest(unittest.TestCase):
    """An assembled bundle must carry every module the repo package ships.

    The completeness tests above only prove the bundle has ``core/`` and
    ``behavior/`` at all. They do NOT notice a bundle that is simply OUT OF DATE
    — e.g. a module added to the repo after the plugin was last installed. That
    is a live-path break, not a cosmetic one: ``renderer/live.py`` importing a
    new module makes the installed observer plugin raise on every event, and its
    fail-open handler swallows the error so the companion silently goes deaf.
    """

    # The subpackages the live rendering and hook paths actually import from.
    # "movement" was missing here once, so a bundle without movement/paths.py
    # could not fail even though renderer/live.py imports it.
    INSTALLED_SUBPACKAGES = ("core", "behavior", "renderer", "movement")

    def _repo_modules(self) -> set[str]:
        skip = {"tests", "__pycache__"}
        return {
            p.relative_to(REPO_ROOT).as_posix()
            for p in REPO_ROOT.rglob("*.py")
            if "__pycache__" not in p.parts and not (set(p.relative_to(REPO_ROOT).parts) & skip)
        }

    def _assert_bundle_matches_repo(self, pkg_dir: Path, label: str) -> None:
        """Byte-for-byte match against the repo, and nothing missing."""
        # Nothing in the bundle may diverge from the repo it was built from.
        stale = []
        for path in pkg_dir.rglob("*.py"):
            rel = path.relative_to(pkg_dir)
            if "__pycache__" in rel.parts:
                continue
            source = REPO_ROOT / rel
            if not source.is_file() or source.read_bytes() != path.read_bytes():
                stale.append(rel.as_posix())
        self.assertEqual([], sorted(stale), f"{label} does not match the repo")

        # Every module the live path imports is present.
        missing = [
            rel for rel in sorted(self._repo_modules())
            if rel.split("/")[0] in self.INSTALLED_SUBPACKAGES
            and not (pkg_dir / rel).is_file()
        ]
        self.assertEqual(
            [], missing,
            f"{label} is missing modules the live path imports; "
            f"re-run the installer after adding a module",
        )

    def _assert_bundle_current(self, install, bundle_name: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            install.build(tmp)
            built = Path(tmp) / "plugins" / bundle_name / "hermes_companion"
            self.assertTrue(built.is_dir(), f"{bundle_name} bundled no package")
            self._assert_bundle_matches_repo(built, f"{bundle_name} fresh build")

    def test_companion_bundle_is_current(self):
        self._assert_bundle_current(
            _load_installer("hermes_companion.plugin.install"), "hermes-companion")

    def test_context_bundle_is_current(self):
        self._assert_bundle_current(
            _load_installer("hermes_companion.plugin_context.install"),
            "hermes-companion-context")

    def test_the_actually_installed_bundle_is_current(self):
        """The installed bundle, not just a fresh build, must match the repo.

        The builds above prove the installer is faithful, but they never look
        at what is really installed under %LOCALAPPDATA%\\hermes\\plugins. A
        bundle that predates a new module would silently go deaf; that is the
        exact failure this test exists to stop, so it checks the real install.
        """
        root = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "plugins"
        checked = 0
        for bundle_name in ("hermes-companion", "hermes-companion-context"):
            pkg_dir = root / bundle_name / "hermes_companion"
            if not pkg_dir.is_dir():
                self.skipTest(f"{bundle_name} is not installed here")
            checked += 1
            self._assert_bundle_matches_repo(pkg_dir, f"installed {bundle_name}")
        self.assertGreater(checked, 0, "no plugin bundles installed to check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
