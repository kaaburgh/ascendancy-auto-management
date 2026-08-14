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

    def test_single_planet_save_cannot_claim_the_m1_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["player_owned_planet_count"] = 1
        entry["runtime_properties"]["player_planet_names"] = ["Alpha I"]
        entry["runtime_properties"]["planets_with_empty_current_action_at_load"] = ["Alpha I"]
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

    def test_unverified_properties_cannot_satisfy_a_role(self):
        entry, _ = multi_planet_fixture()
        entry["runtime_properties"]["evidence"] = "unverified"
        with self.assertRaises(fixtures.FixtureDeclarationError):
            fixtures.check_declaration(document_with(entry))

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
