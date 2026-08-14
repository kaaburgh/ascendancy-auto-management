from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import add_validation_fixture as adder  # noqa: E402
import validate_validation_fixtures as validator  # noqa: E402


class AddValidationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.save = self.directory / "resume-multi.gam"
        self.save.write_bytes(b"pretend save payload")
        self.declaration = self.directory / "validation-fixtures.json"
        shutil.copy2(validator.DEFAULT_DECLARATION, self.declaration)
        self.addCleanup(self.temp.cleanup)

    def run_adder(self, *extra: str) -> int:
        return adder.main(
            [
                "--save",
                str(self.save),
                "--id",
                "resume-en-multi-planet",
                "--role",
                "m1-multi-planet",
                "--declaration",
                str(self.declaration),
                "--player-planet",
                "Alpha I",
                "--player-planet",
                "Beta II",
                "--empty-action-planet",
                "Beta II",
                *extra,
            ]
        )

    def declared(self) -> list[dict]:
        return json.loads(self.declaration.read_text(encoding="utf-8"))["fixtures"]

    def test_operator_supplied_fixture_is_appended_with_computed_identity(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["size"], self.save.stat().st_size)
        self.assertEqual(entry["sha256"], validator.sha256_file(self.save))
        self.assertEqual(entry["runtime_properties"]["player_owned_planet_count"], 2)
        self.assertEqual(entry["runtime_properties"]["evidence"], "unverified")
        self.assertNotIn("repository_path", entry)

    def test_dry_run_writes_nothing(self):
        before = self.declaration.read_text(encoding="utf-8")
        self.assertEqual(self.run_adder("--storage", "operator-supplied", "--dry-run"), 0)
        self.assertEqual(self.declaration.read_text(encoding="utf-8"), before)

    def test_committed_storage_requires_a_repository_path(self):
        self.assertEqual(self.run_adder("--storage", "repository"), 1)

    def test_runtime_evidence_requires_a_verifying_document(self):
        self.assertEqual(
            self.run_adder("--storage", "operator-supplied", "--evidence", "runtime"), 1
        )
        self.assertEqual(
            self.run_adder(
                "--storage",
                "operator-supplied",
                "--evidence",
                "runtime",
                "--verified-by",
                "docs/experiments/X-fixture.md",
            ),
            0,
        )

    def test_existing_id_is_not_silently_overwritten(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 1)
        self.assertEqual(self.run_adder("--storage", "operator-supplied", "--replace"), 0)
        matches = [item for item in self.declared() if item["id"] == "resume-en-multi-planet"]
        self.assertEqual(len(matches), 1)

    def test_a_save_without_named_planets_is_refused(self):
        self.assertEqual(
            adder.main(
                [
                    "--save",
                    str(self.save),
                    "--id",
                    "nameless",
                    "--role",
                    "m1-multi-planet",
                    "--storage",
                    "operator-supplied",
                    "--declaration",
                    str(self.declaration),
                ]
            ),
            1,
        )

    def test_missing_save_is_refused(self):
        self.assertEqual(
            adder.main(
                [
                    "--save",
                    str(self.directory / "absent.gam"),
                    "--id",
                    "absent",
                    "--role",
                    "m1-multi-planet",
                    "--storage",
                    "operator-supplied",
                    "--player-planet",
                    "Alpha I",
                    "--declaration",
                    str(self.declaration),
                ]
            ),
            1,
        )

    def test_declaration_stays_valid_after_the_write(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        document = json.loads(self.declaration.read_text(encoding="utf-8"))
        self.assertTrue(validator.check_declaration(document))


if __name__ == "__main__":
    unittest.main()
