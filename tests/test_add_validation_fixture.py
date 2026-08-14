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
        self.runtime_source_relative = "docs/experiments/_synthetic_add_fixture_record.md"
        self.runtime_source = Path(validator.ROOT) / self.runtime_source_relative
        self.runtime_source.write_text(
            "\n".join(
                [
                    "# synthetic fixture runtime record",
                    "",
                    validator.RUNTIME_EVIDENCE_MARKER,
                    f"Target SHA-256 `{validator.CANONICAL_TARGET_SHA256}`.",
                    f"Pinned save SHA-256 `{validator.sha256_file(self.save)}`.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.addCleanup(self.runtime_source.unlink, missing_ok=True)
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

    def test_runtime_evidence_requires_a_valid_verifying_record(self):
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
            1,
        )
        self.assertEqual(
            self.run_adder(
                "--storage",
                "operator-supplied",
                "--evidence",
                "runtime",
                "--verified-by",
                self.runtime_source_relative,
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

    def test_repository_path_escaping_the_repo_copies_nothing(self):
        outside = self.directory / "outside.gam"
        self.assertEqual(
            self.run_adder(
                "--storage", "repository", "--repository-path", f"../{outside.name}"
            ),
            1,
        )
        self.assertFalse(outside.exists())
        self.assertNotIn(
            "resume-en-multi-planet", [item["id"] for item in self.declared()]
        )

    def test_existing_repository_destination_is_never_overwritten(self):
        root = Path(adder.ROOT)
        readme = root / "README.md"
        before = readme.read_bytes()
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", "README.md"), 1
        )
        self.assertEqual(readme.read_bytes(), before)

    def test_committed_payload_is_placed_and_declared_together(self):
        relative = "fixtures/saves/test-add-fixture-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), self.save.read_bytes())
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["repository_path"], relative)

    def test_promotion_of_a_committed_fixture_reuses_its_own_destination(self):
        relative = "fixtures/saves/test-promote-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        # The promotion run supplies the same save from its original path, so the
        # destination already exists and must not be treated as a foreign file.
        self.assertEqual(
            self.run_adder(
                "--replace",
                "--storage",
                "repository",
                "--repository-path",
                relative,
                "--evidence",
                "runtime",
                "--verified-by",
                self.runtime_source_relative,
            ),
            0,
        )
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["runtime_properties"]["evidence"], "runtime")

    def test_replacing_a_committed_fixture_with_different_bytes_is_refused(self):
        relative = "fixtures/saves/test-swap-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        original = destination.read_bytes()
        self.save.write_bytes(b"a different save entirely")
        self.assertEqual(
            self.run_adder("--replace", "--storage", "repository", "--repository-path", relative),
            1,
        )
        self.assertEqual(destination.read_bytes(), original)

    def test_rebinding_an_id_to_different_bytes_is_refused_at_a_new_path(self):
        """A fresh repository_path must not become a way around the identity guard."""
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        original_sha = validator.sha256_file(self.save)
        self.save.write_bytes(b"a different save entirely")
        self.assertEqual(
            self.run_adder(
                "--replace", "--storage", "repository", "--repository-path",
                "fixtures/saves/test-rebind-tmp.gam",
            ),
            1,
        )
        self.assertFalse((Path(adder.ROOT) / "fixtures/saves/test-rebind-tmp.gam").exists())
        entry = next(item for item in self.declared() if item["id"] == "resume-en-multi-planet")
        self.assertEqual(entry["sha256"], original_sha)

    def test_rebinding_an_id_is_refused_when_the_committed_payload_is_the_source(self):
        relative = "fixtures/saves/test-selfsource-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        # Someone edits the committed payload in place and re-runs with it as --save,
        # so destination == save and the destination-based guard never fires.
        destination.write_bytes(b"tampered payload")
        self.assertEqual(
            adder.main(
                [
                    "--save", str(destination), "--id", "resume-en-multi-planet",
                    "--role", "m1-multi-planet", "--declaration", str(self.declaration),
                    "--player-planet", "Alpha I", "--player-planet", "Beta II",
                    "--empty-action-planet", "Beta II", "--replace",
                    "--storage", "repository", "--repository-path", relative,
                ]
            ),
            1,
        )

    def test_a_failed_write_does_not_delete_a_pre_existing_payload(self):
        relative = "fixtures/saves/test-rollback-tmp.gam"
        destination = Path(adder.ROOT) / relative

        def cleanup() -> None:
            destination.unlink(missing_ok=True)
            for parent in (destination.parent, destination.parent.parent):
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()

        self.addCleanup(cleanup)
        self.assertEqual(
            self.run_adder("--storage", "repository", "--repository-path", relative), 0
        )
        original = destination.read_bytes()

        def explode(*args, **kwargs):
            raise validator.FixtureDeclarationError("simulated failure after placement")

        real_check = validator.check_payloads
        validator.check_payloads = explode
        self.addCleanup(setattr, validator, "check_payloads", real_check)
        self.assertEqual(
            self.run_adder("--replace", "--storage", "repository", "--repository-path", relative),
            1,
        )
        self.assertTrue(destination.is_file(), "pre-existing payload was deleted by rollback")
        self.assertEqual(destination.read_bytes(), original)

    def test_declaration_stays_valid_after_the_write(self):
        self.assertEqual(self.run_adder("--storage", "operator-supplied"), 0)
        document = json.loads(self.declaration.read_text(encoding="utf-8"))
        self.assertTrue(validator.check_declaration(document))


if __name__ == "__main__":
    unittest.main()
