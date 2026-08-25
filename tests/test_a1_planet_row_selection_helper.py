from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a1_planet_row_selection_helper import (
    A1PlanetRowSelectionError,
    WindowGeometry,
    handle_request,
    parse_label_rows,
)


def request(label="A"):
    return {
        "schema": "ascendancy.a1-selection-action-request/v1",
        "step_id": "control-a",
        "logical_label": label,
        "timeout_seconds": 3.0,
    }


class Backend:
    def __init__(self, width=640, height=480):
        self._geometry = WindowGeometry(width, height)
        self.clicks = []

    def geometry(self):
        return self._geometry

    def click(self, x, y):
        self.clicks.append((x, y))


class PlanetRowSelectionHelperTests(unittest.TestCase):
    def test_completes_input_action_for_configured_visible_row(self):
        backend = Backend()
        result = handle_request(request("B"), {"A": 0, "B": 1}, backend)
        self.assertEqual(backend.clicks, [(205, 270)])
        self.assertEqual(
            result,
            {
                "action_completed": True,
                "logical_label": "B",
                "step_id": "control-a",
                "visible_row": 1,
            },
        )
        self.assertNotIn("selected", result)

    def test_label_matching_is_exact(self):
        backend = Backend()
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "not configured"):
            handle_request(request("a"), {"A": 0}, backend)
        self.assertEqual(backend.clicks, [])

    def test_rejects_wrong_schema_before_input(self):
        backend = Backend()
        value = request()
        value["schema"] = "wrong"
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "schema"):
            handle_request(value, {"A": 0}, backend)
        self.assertEqual(backend.clicks, [])

    def test_rejects_unexpected_window_geometry(self):
        backend = Backend(width=800, height=600)
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "640x480"):
            handle_request(request(), {"A": 0}, backend)
        self.assertEqual(backend.clicks, [])

    def test_parse_label_rows_rejects_duplicate_labels(self):
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "duplicate logical label"):
            parse_label_rows(["A=0", "A=1"])

    def test_parse_label_rows_rejects_duplicate_rows(self):
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "duplicate visible row"):
            parse_label_rows(["A=0", "B=0"])

    def test_parse_label_rows_rejects_out_of_range_row(self):
        with self.assertRaisesRegex(A1PlanetRowSelectionError, r"\[0, 2\]"):
            parse_label_rows(["A=3"])

    def test_parse_label_rows_requires_mapping(self):
        with self.assertRaisesRegex(A1PlanetRowSelectionError, "at least one"):
            parse_label_rows([])


if __name__ == "__main__":
    unittest.main()
