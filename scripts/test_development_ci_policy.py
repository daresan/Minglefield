"""Minglefield Development CI Policy v1.0.0 trigger safety regressions.

No YAML dependency: check only stable source-level invariants. GitHub Actions
remains authoritative for actually parsing and executing the workflow files.
This is unrelated to ComfyUI node-graph workflows.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def events(name):
    text = workflow(name)
    start = re.search(r"^on:\s*$", text, re.MULTILINE)
    if not start:
        raise AssertionError(f"missing GitHub Actions event block: {name}")
    end = re.search(r"^permissions:\s*$", text[start.end():], re.MULTILINE)
    if not end:
        raise AssertionError(f"missing permissions block: {name}")
    return text[start.end():start.end() + end.start()]


class DevelopmentCIPolicyTests(unittest.TestCase):
    def test_no_automatic_portable_packaging(self):
        reusable = events("installer-tauri-packaging.yml")
        self.assertIn("  workflow_call:", reusable)
        self.assertIn("  workflow_dispatch:", reusable)
        self.assertNotRegex(reusable, r"(?m)^  (?:push|pull_request):")
        marker = events("installer-portable-milestone.yml")
        self.assertIn("installer/gui/PORTABLE-TEST-REQUEST.md", marker)
        self.assertIn("  workflow_dispatch:", marker)

    def test_routine_core_checks_do_not_build_every_gui_or_document_edit(self):
        core_events = events("installer-rust.yml")
        self.assertIn('installer/crates/**', core_events)
        self.assertNotIn('"installer/**"', core_events)
        self.assertIn("full_matrix:", core_events)
        self.assertIn("ubuntu-latest", workflow("installer-rust.yml"))
        self.assertNotIn("  tauri-gui:", workflow("installer-rust.yml"))
        self.assertNotIn("tauri -- build", workflow("installer-rust.yml"))

    def test_frontend_and_native_gui_have_separate_triggers(self):
        frontend = events("installer-gui-frontend.yml")
        native = events("installer-gui-native.yml")
        self.assertIn("installer/gui/*.js", frontend)
        self.assertNotIn("installer/gui/src-tauri/**", frontend)
        self.assertIn("installer/gui/src-tauri/**", native)
        self.assertNotIn("installer/gui/PORTABLE-TEST-REQUEST.md", frontend)
        self.assertNotIn("tauri -- build", workflow("installer-gui-native.yml"))
        self.assertIn("full_matrix:", native)

    def test_security_and_game_matrix_are_risk_scoped(self):
        native = events("installer-native-security.yml")
        self.assertIn("migration_destination.rs", native)
        self.assertIn("encrypted_copy_preflight.rs", native)
        self.assertIn("windows-latest", workflow("installer-native-security.yml"))
        self.assertIn("macos-latest", workflow("installer-native-security.yml"))
        self.assertNotRegex(native, r"(?m)^  pull_request:")
        game = events("game-installation-security.yml")
        self.assertRegex(game, r"(?m)^  push:")
        self.assertRegex(game, r"(?m)^  pull_request:")
        self.assertIn("test_game_integration_install*.py", game)
        self.assertNotIn('"installer/**"', game)

    def test_versioned_contract_and_rollback_exist(self):
        policy = (ROOT / "docs" / "ci" /
                  "MINGLEFIELD-DEVELOPMENT-CI-POLICY-v1.0.0.md").read_text(encoding="utf-8")
        self.assertIn("c1bfd5a26f01444de4349836c463eaa5bd4f65be", policy)
        self.assertIn("ComfyUI", policy)
        self.assertIn("M2.15", policy)


if __name__ == "__main__":
    unittest.main()
