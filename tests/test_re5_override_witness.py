import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_re5_override_witness.py"
SPEC = importlib.util.spec_from_file_location("run_re5_override_witness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
witness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(witness)


class _FakeObject:
    def __init__(self, index, base_address, first_page=1):
        self.index = index
        self.base_address = base_address
        self.first_page = first_page


class _FakeImage:
    lfanew = 0x40
    page_size = 0x1000

    def __init__(self, gate_file_offset=0x800):
        self.gate_file_offset = gate_file_offset
        self.objects = [_FakeObject(1, 0x10000, 1), _FakeObject(2, 0x90000, 116)]

    def object_containing(self, address):
        if 0x10000 <= address < 0x82736:
            return self.objects[0]
        if 0x90000 <= address < 0x138220:
            return self.objects[1]
        return None

    def va_to_file_offset(self, address):
        if witness.GATE_OVERRIDE_COMPARE_VA <= address < witness.GATE_OVERRIDE_COMPARE_VA + 7:
            return self.gate_file_offset + (address - witness.GATE_OVERRIDE_COMPARE_VA)
        return None


def _synthetic_gate_target(target_offset=0x10D00, target_object=2):
    image = _FakeImage()
    data = bytearray(0x2000)
    struct.pack_into("<I", data, image.lfanew + witness.LE_H_FIXUP_PAGE_TABLE, 0x200)
    struct.pack_into("<I", data, image.lfanew + witness.LE_H_FIXUP_RECORD_TABLE, 0x500)
    source_relative = witness.GATE_OVERRIDE_COMPARE_VA + 2 - image.objects[0].base_address
    page_index = source_relative // image.page_size
    source_offset = source_relative % image.page_size
    page_table = image.lfanew + 0x200
    for index in range(page_index + 2):
        struct.pack_into("<I", data, page_table + index * 4, 0)
    record = (
        bytes([0x07, 0x10])
        + struct.pack("<H", source_offset)
        + bytes([target_object])
        + struct.pack("<I", target_offset)
    )
    struct.pack_into("<I", data, page_table + page_index * 4, 0)
    struct.pack_into("<I", data, page_table + (page_index + 1) * 4, len(record))
    record_table = image.lfanew + 0x500
    data[record_table:record_table + len(record)] = record
    gate = b"\x83\x3d" + struct.pack("<I", target_offset) + b"\x00"
    data[image.gate_file_offset:image.gate_file_offset + len(gate)] = gate
    return image, bytes(data)


class RE5OverrideWitnessTests(unittest.TestCase):
    def test_scenario_identity_records_nondefault_planet(self):
        self.assertEqual(
            witness.scenario_identity("Corpuscle II"),
            {"selected_planet_name": "Corpuscle II"},
        )
        with self.assertRaisesRegex(witness.OverrideWitnessError, "non-empty"):
            witness.scenario_identity("")

    def test_uniform_bias_is_derived_from_all_signatures(self):
        anchor_offset = 100
        observations = [
            (
                0x90895,
                [anchor_offset + (0x90895 - witness.ANCHOR_VA) - 0xD000],
            ),
            (
                0x998BA,
                [anchor_offset + (0x998BA - witness.ANCHOR_VA) - 0xD000],
            ),
        ]
        self.assertEqual(witness.infer_uniform_bias(anchor_offset, observations), -0xD000)

    def test_bias_rejects_missing_signature(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [])])

    def test_bias_rejects_ambiguous_signature(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [1, 2])])

    def test_bias_rejects_inconsistent_signatures(self):
        with self.assertRaises(witness.OverrideWitnessError):
            witness.infer_uniform_bias(0, [(0x90895, [10]), (0x90EB8, [20])])

    def test_gate_relationship_derives_override_from_le_relocation(self):
        image, data = _synthetic_gate_target()
        override_va, evidence = witness.validate_gate_override_relationship(image, data)
        self.assertEqual(override_va, witness.EXPECTED_OVERRIDE_VA)
        self.assertEqual(evidence["relocation_target_object"], 2)
        self.assertEqual(evidence["relocation_target_offset"], "0x10d00")

    def test_gate_relationship_rejects_wrong_relocation_target(self):
        image, data = _synthetic_gate_target(target_offset=0x10D04)
        with self.assertRaisesRegex(witness.OverrideWitnessError, "derives"):
            witness.validate_gate_override_relationship(image, data)

    def test_fixup_parser_fails_closed_on_unknown_form(self):
        with self.assertRaisesRegex(witness.OverrideWitnessError, "unsupported LE fixup"):
            witness._parse_simple_le_fixup_records(
                b"\x06\x10\x00\x00\x02\x00\x00\x00\x00"
            )

    def test_stardate_resolves_through_bias_path_and_rejects_wrong_bias(self):
        anchor = {
            "map_start": 0x10000000,
            "map_end": 0x10200000,
            "anchor_offset": 0x20000,
        }
        expected = witness.re5.anchor_delta_host(
            anchor, witness.re5.STARDATE_ANCHOR_DELTA, 4
        )
        self.assertEqual(witness.resolve_stardate_host(anchor, -0xD000), expected)
        with self.assertRaisesRegex(witness.OverrideWitnessError, "stardate"):
            witness.resolve_stardate_host(anchor, -0xC000)

    def test_flash_pop_guard_is_recursive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nested = root / "nested"
            nested.mkdir()
            (nested / "FLASH.POP").write_bytes(b"x")
            self.assertTrue(witness.fixture_contains_name(root, "flash.pop"))

    @staticmethod
    def trace(sample_count=220, override=0, stardate=10, gap_ms=25.0):
        base = {
            "owner_0x57": 0,
            "slot_0x52": "ffff",
            "action_0x54": "ff",
            "managed_0x5a": "00000000",
            "override_0xa0d00": override,
            "current_player_id_0x104bea": 0,
            "stardate": stardate,
        }
        samples = []
        for index in range(sample_count):
            current = base.copy()
            current["stardate"] = stardate + index // 10
            current["t_ms"] = index * gap_ms
            samples.append(current)
        after = base.copy()
        after["stardate"] = stardate + 25
        return base, samples, after

    def test_evaluate_accepts_progressing_manual_zero_override_trace(self):
        before, samples, after = self.trace()
        self.assertEqual(witness.evaluate(before, samples, after)["status"], "passed")

    def test_evaluate_rejects_nonzero_override_sample(self):
        before, samples, after = self.trace()
        samples[50]["override_0xa0d00"] = 0xFFFFFFFF
        self.assertEqual(witness.evaluate(before, samples, after)["status"], "failed")

    def test_evaluate_rejects_insufficient_progress(self):
        before, samples, after = self.trace()
        after["stardate"] = before["stardate"] + witness.MIN_STARDATE_DELTA - 1
        result = witness.evaluate(before, samples, after)
        self.assertFalse(result["checks"]["stardate_progress_target_met"])

    def test_evaluate_rejects_sampling_gap_over_bound(self):
        before, samples, after = self.trace(gap_ms=witness.MAX_SAMPLE_GAP_MS + 1.0)
        result = witness.evaluate(before, samples, after)
        self.assertFalse(result["checks"]["max_sample_gap_within_bound"])


if __name__ == "__main__":
    unittest.main()
