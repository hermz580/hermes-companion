"""Launcher contract: no secrets on the command line, and every argument a
launcher passes must actually be accepted by the real CLI parser.

Drift here is silent and dangerous in both directions:
  * a launcher passing an argument the parser dropped makes the companion
    fail to start (exit 2), and
  * a launcher passing a token on the command line leaks it to anyone who
    can read the process list.

Flags are read only from the lines that actually invoke ``hermes_companion``,
so launcher-local switches (``--no-bind``, ``--no-relay``) are not mistaken for
CLI arguments.
"""
import argparse
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAUNCH = REPO / 'launch'
PRIMARY = ('companion-pet.cmd', 'companion-relay.cmd', 'companion-astro.cmd',
           'companion-astro-local.cmd', 'companion-choose.cmd',
           'companion-start.cmd')
TOKEN_EXPORTERS = ('companion-pet.cmd', 'companion-relay.cmd',
                   'companion-astro.cmd', 'companion-choose.cmd',
                   'companion-start.cmd')

INVOKE_RE = re.compile(r'-m\s+hermes_companion\s+([a-z]+)([^\r\n]*)')
FLAG_RE = re.compile(r'(--[a-z][a-z-]*)')


def _parser():
    from hermes_companion.cli import emit
    return emit.build_parser()


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError('no subcommands in the real parser')


def _text(name):
    return (LAUNCH / name).read_text(encoding='utf-8', errors='replace')


def _invocations(text):
    """Yield (subcommand, raw_args) for each real CLI invocation in a launcher."""
    for match in INVOKE_RE.finditer(text):
        yield match.group(1), match.group(2)


class LauncherContractTests(unittest.TestCase):
    def test_every_primary_launcher_exists(self):
        for name in PRIMARY:
            with self.subTest(launcher=name):
                self.assertTrue((LAUNCH / name).is_file(), f'{name} missing')

    def test_no_launcher_passes_the_relay_token_on_the_command_line(self):
        for name in PRIMARY:
            text = _text(name)
            with self.subTest(launcher=name):
                self.assertNotIn('--token', text,
                                 f'{name} passes --token on the command line')

    def test_relay_launchers_export_the_token_via_the_environment(self):
        for name in TOKEN_EXPORTERS:
            text = _text(name)
            with self.subTest(launcher=name):
                self.assertIn('HERMES_COMPANION_TOKEN', text)

    def test_launcher_arguments_are_accepted_by_the_real_parsers(self):
        choices = _subparsers(_parser())
        for name in PRIMARY:
            text = _text(name)
            invocations = list(_invocations(text))
            with self.subTest(launcher=name):
                self.assertTrue(invocations, f'{name} never invokes the CLI')
            for command, raw in invocations:
                with self.subTest(launcher=name, command=command):
                    self.assertIn(command, choices,
                                  f'{name} calls {command}, which does not exist')
                accepted = {a.dest for a in choices[command]._actions}
                for flag in FLAG_RE.findall(raw):
                    stem = flag.lstrip('-').replace('-', '_')
                    with self.subTest(launcher=name, flag=flag, command=command):
                        self.assertIn(stem, accepted,
                                      f'{name} passes {flag} to {command}, which rejects it')

    def test_standalone_launcher_initializes_its_declared_defaults(self):
        text = _text('companion-astro-local.cmd')
        self.assertIn('COMPANION=%DEFAULT_COMPANION%', text)
        self.assertIn('SCALE=%DEFAULT_SCALE%', text)
        self.assertIn('%COMPANION%', text)

    def test_start_launcher_binds_before_starting_the_overlay(self):
        text = _text('companion-start.cmd')
        self.assertIn('-m hermes_companion bind', text)
        self.assertIn('-m hermes_companion live', text)
        self.assertLess(text.index('hermes_companion bind'),
                        text.index('hermes_companion live'),
                        'the overlay must be bound before it starts')

    def test_default_token_reads_only_the_environment(self):
        import os
        from hermes_companion.renderer.relay import default_token
        original = os.environ.pop('HERMES_COMPANION_TOKEN', None)
        try:
            self.assertEqual(default_token(), '')
            os.environ['HERMES_COMPANION_TOKEN'] = 'abc123'
            self.assertEqual(default_token(), 'abc123')
        finally:
            if original is None:
                os.environ.pop('HERMES_COMPANION_TOKEN', None)
            else:
                os.environ['HERMES_COMPANION_TOKEN'] = original


if __name__ == '__main__':
    unittest.main()
