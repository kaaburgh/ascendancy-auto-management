import hashlib
import unittest

from scripts.a1_selection_control_oracle import A1SelectionControlError, validate_selection_control


def witness(planet: str) -> dict:
    raw = planet.encode("utf-8")
    return {
        "scenario_planet": planet,
        "metadata_basis": "bounded-record-metadata",
        "metadata_hex": raw.hex(),
        "metadata_sha256": hashlib.sha256(raw).hexdigest(),
    }


def point(seq: int, pointer: int, planet: str) -> dict:
    return {
        "seq": seq,
        "record_pointer": pointer,
        "logical_record": planet,
        "qualified_witness": witness(planet),
    }


def manifest() -> dict:
    return {
        "planets": {
            planet: hashlib.sha256(planet.encode("utf-8")).hexdigest()
            for planet in ("Planet A", "Planet B")
        }
    }


def positive_record() -> dict:
    return {
        "outcome": "positive-epoch-pointer",
        "transitions": [
            {
                "label": "selection-control",
                "replacement": False,
                "observations": {
                    "first": point(1, 0x10100, "Planet A"),
                    "second": point(2, 0x10200, "Planet B"),
                    "return": point(3, 0x10100, "Planet A"),
                },
            }
        ],
    }


class A1SelectionControlOracleTests(unittest.TestCase):
    def test_accepts_qualified_a_b_a_control(self):
        validate_selection_control(positive_record(), manifest())

    def test_nonpositive_record_does_not_require_control(self):
        validate_selection_control({"outcome": "incomplete-harness", "transitions": []}, {})

    def test_positive_rejects_missing_observations(self):
        record = positive_record()
        del record["transitions"][0]["observations"]
        with self.assertRaisesRegex(A1SelectionControlError, "bounded observations"):
            validate_selection_control(record, manifest())

    def test_positive_rejects_pointer_collapse_between_planets(self):
        record = positive_record()
        record["transitions"][0]["observations"]["second"]["record_pointer"] = 0x10100
        with self.assertRaisesRegex(A1SelectionControlError, "distinct record pointers"):
            validate_selection_control(record, manifest())

    def test_positive_rejects_return_to_different_pointer(self):
        record = positive_record()
        record["transitions"][0]["observations"]["return"]["record_pointer"] = 0x10300
        with self.assertRaisesRegex(A1SelectionControlError, "reproduce the first record pointer"):
            validate_selection_control(record, manifest())

    def test_positive_rejects_population_replacement(self):
        record = positive_record()
        record["transitions"][0]["replacement"] = True
        with self.assertRaisesRegex(A1SelectionControlError, "replacement=false"):
            validate_selection_control(record, manifest())

    def test_positive_rejects_unqualified_return_witness(self):
        record = positive_record()
        record["transitions"][0]["observations"]["return"]["qualified_witness"] = witness("Planet B")
        with self.assertRaisesRegex(A1SelectionControlError, "scenario_planet must bind"):
            validate_selection_control(record, manifest())


if __name__ == "__main__":
    unittest.main()
