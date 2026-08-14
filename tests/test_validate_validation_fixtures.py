from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_validation_fixtures as fixtures  # noqa: E402

DECLARATION = json.loads(fixtures.DEFAULT_DECLARATION.read_text(encoding="utf-8"))


def multi_planet_fixture(**overrides):
    payload = b"multi-planet save payload"
    entry = {
        "id": "resume-multi-planet",
        "filename": "resume-multi.gam",
        "role": "m1-multi-planet",
        "storage": "operator-supplied",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "produced_by_target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
        "runtime_properties": {
            "evidence": "runtime",
            "source": "docs/re/validation-fixtures.md",
            "player_race_id": 0,
            "player_owned_planet_count": 3,
            "player_planet_names": ["Alpha I", "Beta II", "Gamma III"],
            "planets_with_empty_current_action_at_load": ["Beta II"],
        },
    }
    entry.update(overrides)
    return entry, payload


def document_with(entry) -> dict:
    document = copy.deepcopy(DECLARATION)
    document["fixtures"] = [entry]
    return document


class ValidationFixtureDeclarationTests(unittest.TestCase):
    def test_committed_declaration_is_valid(self):
        declared = fixtures.check_declaration(copy.deepcopy(DECLARATION))
        self.assertTrue(declared)

    def test_committed_declaration_records_the_single_planet_limitation(self):
        entry = next(
            item for item in DECLARATION["fixtures"] if item["filename"] == "resume.gam"
        )
        self.assertEqual(entry["runtime_properties"]["player_owned_planet_count"], 1)
        self.assertEqual(entry["role"], "single-planet-causal")
        self.assertTrue(entry["limitations"])

    def test_multi_planet_role_is_accepted_when_requirements_are_met(self):
        entry, _ = multi_planet_fixture()
        self.assertTrue(fixtures.check_declaration(document_with(entry)))

    def test_unverified_fixture_is_declarable_but_not_usable(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "unverified"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("unverified", status["reason"])

    def test_static_evidence_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "static"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("runtime", status["reason"])

    def test_runtime_evidence_without_a_source_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"].pop("source")
        declared = fixtures.check_declaration(document_with(entry))
        self.assertFalse(declared[0]["_role_status"]["satisfied"])

    def test_save_from_a_non_canonical_target_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["produced_by_target_sha256"] = (
            "7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b"
        )
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("canonical", status["reason"])

    def test_source_naming_a_missing_record_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = "docs/experiments/does-not-exist.md"
        declared = fixtures.check_declaration(document_with(entry))
        status = declared[0]["_role_status"]
        self.assertFalse(status["satisfied"])
        self.assertIn("does not resolve", status["reason"])

    def test_source_escaping_the_repository_does_not_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["source"] = "../../etc/passwd"
        declared = fixtures.check_declaration(document_with(entry))
        self.assertFalse(declared[0]["_role_status"]["satisfied"])

    def test_verified_properties_contradicting_the_role_fail_closed(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "runtime"
        entry["runtime_properties"]["player_owned_planet_count"] = 1
        entry["runtime_properties"]["player_planet_names"] = ["Alpha I"]
        entry["runtime_properties"]["planets_with_empty_current_action_at_load"] = ["Alpha I"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_require_role_rejects_a_declaration_with_only_unverified_candidates(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "unverified"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "declaration.json"
            path.write_text(json.dumps(document_with(entry)), encoding="utf-8")
            self.assertEqual(
                fixtures.main(["--declaration", str(path), "--require-role", "m1-multi-planet"]), 1
            )
            self.assertEqual(fixtures.main(["--declaration", str(path)]), 0)

    def test_planet_count_must_match_the_named_planets(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["player_owned_planet_count"] = 4
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_duplicate_planet_names_are_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["player_planet_names"] = ["Alpha I", "Alpha I", "Gamma III"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_empty_action_planet_must_be_player_owned(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["planets_with_empty_current_action_at_load"] = ["Delta IV"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_absent_payload_is_reported_but_not_fatal(self):
        entry, _ = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            results = fixtures.check_payloads([entry], Path(directory), require_present=False)
        self.assertEqual(results[0]["payload"], "absent")

    def test_absent_payload_fails_closed_when_required(self):
        entry, _ = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(fixtures.FixtureDeclarationError):
                fixtures.check_payloads([entry], Path(directory), require_present=True)

    def test_present_payload_identity_is_verified(self):
        entry, payload = multi_planet_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / entry["filename"]
            path.write_bytes(payload)
            results = fixtures.check_payloads([entry], Path(directory), require_present=True)
            self.assertEqual(results[0]["payload"], "verified")

            path.write_bytes(payload + b"drift")
            with self.assertRaises(fixtures.FixtureDeclarationError):
                fixtures.check_payloads([entry], Path(directory), require_present=True)

    def test_unknown_storage_is_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "somewhere-else"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_repository_storage_requires_a_repository_path(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_repository_path_may_not_escape_the_repository(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        entry["repository_path"] = "../outside/resume-multi.gam"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_committed_payload_must_exist_even_without_require_present(self):
        entry, _ = multi_planet_fixture()
        entry["storage"] = "repository"
        entry["repository_path"] = "tests/fixtures/definitely-absent.gam"
        fixtures.check_declaration(document_with(entry))
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_payloads([entry], None, require_present=False)

    def test_unknown_role_is_rejected(self):
        entry, _ = multi_planet_fixture()
        entry["role"] = "not-a-declared-role"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_unsupported_schema_is_rejected(self):
        document = copy.deepcopy(DECLARATION)
        document["schema"] = 99
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document)


if __name__ == "__main__":
    unittest.main()
