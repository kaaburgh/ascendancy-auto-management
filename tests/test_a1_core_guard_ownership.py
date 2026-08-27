import copy
import hashlib
import unittest

from scripts import _a1_sidecar_lifetime_oracle_core as core


TARGET_SHA256 = "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00"
QUALIFICATION_SHA256 = "4" * 64
RETAIL_MANIFEST_IDENTITY = "tools/retail-runtime-manifest.json#canonical-retail-fixture"
SCENARIO_IDENTITY = "a1-synthetic-two-planet-scenario-v1"


def metadata_bytes(planet: str) -> bytes:
    return planet.encode("utf-8")


def metadata_digest(planet: str) -> str:
    return hashlib.sha256(metadata_bytes(planet)).hexdigest()


def expected_source() -> dict:
    return {
        "schema": core.EXPECTED_SOURCE_SCHEMA,
        "target_sha256": TARGET_SHA256,
        "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
        "scenario_identity": SCENARIO_IDENTITY,
        "qualification_source_sha256": QUALIFICATION_SHA256,
    }


def scenario_manifest() -> dict:
    return {
        "schema": core.SCENARIO_SCHEMA,
        "source": {
            "target_sha256": TARGET_SHA256,
            "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
            "scenario_identity": SCENARIO_IDENTITY,
            "qualification_source_sha256": QUALIFICATION_SHA256,
        },
        "planets": {
            "scenario-planet-a": metadata_digest("scenario-planet-a"),
            "scenario-planet-b": metadata_digest("scenario-planet-b"),
        },
    }


def witness(planet: str) -> dict:
    raw = metadata_bytes(planet)
    return {
        "scenario_planet": planet,
        "metadata_basis": "bounded-record-metadata",
        "metadata_hex": raw.hex(),
        "metadata_sha256": hashlib.sha256(raw).hexdigest(),
    }


def selection_control_step() -> dict:
    return {
        "label": "selection-control",
        "replacement": False,
        "observations": {
            "first": {
                "seq": 1,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-a",
                "qualified_witness": witness("scenario-planet-a"),
            },
            "second": {
                "seq": 2,
                "record_pointer": 0x10200,
                "logical_record": "scenario-planet-b",
                "qualified_witness": witness("scenario-planet-b"),
            },
            "return": {
                "seq": 3,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-a",
                "qualified_witness": witness("scenario-planet-a"),
            },
        },
    }


def replacement_step(label: str) -> dict:
    return {
        "label": label,
        "replacement": True,
        "invalidation_basis": "epoch",
        "observations": {
            "pre": {
                "seq": 10,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-a",
                "qualified_witness": witness("scenario-planet-a"),
                "array_base": 0x10000,
                "array_count": 8,
                "index": 1,
            },
            "post": {
                "seq": 30,
                "record_pointer": 0x10100,
                "logical_record": "scenario-planet-b",
                "qualified_witness": witness("scenario-planet-b"),
                "array_base": 0x10000,
                "array_count": 8,
                "index": 1,
            },
            "reuse_event": {
                "seq": 25,
                "kind": "index-reassignment",
                "before_logical_record": "scenario-planet-a",
                "after_logical_record": "scenario-planet-b",
                "before_metadata_sha256": metadata_digest("scenario-planet-a"),
                "after_metadata_sha256": metadata_digest("scenario-planet-b"),
                "array_base": 0x10000,
                "index": 1,
            },
            "epoch_signal": {"before": 7, "after": 8, "seq": 20},
        },
    }


def positive_record() -> dict:
    return {
        "schema": core.SCHEMA,
        "outcome": "positive-epoch-index",
        "inputs": {
            "target_sha256": TARGET_SHA256,
            "retail_manifest_identity": RETAIL_MANIFEST_IDENTITY,
            "scenario_identity": SCENARIO_IDENTITY,
            "qualification_source_sha256": QUALIFICATION_SHA256,
        },
        "claims": {
            "array_base_established": True,
            "array_count_established": True,
            "stable_index_established": True,
            "reuse_detector_established": False,
            "epoch_boundary_established": True,
            "manual_transition_invalidation_established": False,
        },
        "control": {"passed": True},
        "transitions": [
            selection_control_step(),
            replacement_step("new-game-reset"),
            replacement_step("save-load-replacement"),
        ],
    }


def v2_manifest() -> dict:
    manifest = scenario_manifest()
    manifest["schema"] = core.SCENARIO_SCHEMA_V2
    manifest["witness_ranges"] = {
        "scenario-planet-a": {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 0x10,
            "length": len(metadata_bytes("scenario-planet-a")),
            "sha256": metadata_digest("scenario-planet-a"),
            "rationale": "synthetic direct-core guard test",
        },
        "scenario-planet-b": {
            "metadata_basis": "bounded-record-metadata",
            "record_offset": 0x60,
            "length": len(metadata_bytes("scenario-planet-b")),
            "sha256": metadata_digest("scenario-planet-b"),
            "rationale": "synthetic direct-core guard test",
        },
    }
    return manifest


def convert_record_to_v2(record: dict) -> None:
    offsets = {"scenario-planet-a": 0x10, "scenario-planet-b": 0x60}

    def visit(value):
        if isinstance(value, dict):
            qualified = value.get("qualified_witness")
            if isinstance(qualified, dict):
                planet = qualified["scenario_planet"]
                raw = bytes.fromhex(qualified.pop("metadata_hex"))
                qualified["record_offset"] = offsets[planet]
                qualified["length"] = len(raw)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(record)


class A1CoreGuardOwnershipTests(unittest.TestCase):
    def test_core_directly_accepts_complete_legacy_positive_contract(self):
        result = core.validate_record(positive_record(), scenario_manifest(), expected_source())
        self.assertTrue(result["positive_contract_accepted"])

    def test_core_directly_enforces_selection_control_guard(self):
        record = positive_record()
        record["transitions"][0] = {"label": "selection-control", "replacement": False}
        with self.assertRaisesRegex(core.A1LifetimeError, "bounded observations for selection-control"):
            core.validate_record(record, scenario_manifest(), expected_source())

    def test_core_directly_accepts_complete_v2_contract(self):
        record = positive_record()
        convert_record_to_v2(record)
        result = core.validate_record(record, v2_manifest(), expected_source())
        self.assertTrue(result["positive_contract_accepted"])

    def test_core_directly_requires_v2_witness_ranges(self):
        record = positive_record()
        convert_record_to_v2(record)
        manifest = v2_manifest()
        del manifest["witness_ranges"]
        with self.assertRaisesRegex(core.A1LifetimeError, "v2 manifest requires witness_ranges"):
            core.validate_record(record, manifest, expected_source())

    def test_core_directly_enforces_v2_witness_geometry(self):
        record = positive_record()
        convert_record_to_v2(record)
        mutated = copy.deepcopy(record)
        witness_value = mutated["transitions"][1]["observations"]["pre"]["qualified_witness"]
        witness_value["record_offset"] += 1
        with self.assertRaisesRegex(core.A1LifetimeError, "record_offset must match"):
            core.validate_record(mutated, v2_manifest(), expected_source())


if __name__ == "__main__":
    unittest.main()
