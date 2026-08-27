import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import a1_sidecar_evidence_bundle as bundle


class A1SelectionControlBundleCallTests(unittest.TestCase):
    def test_validate_bundle_rejects_missing_selection_control_on_its_own_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qualification_path = root / "qualification.json"
            expected_path = root / "expected.json"
            record_path = root / "record.json"

            qualification_path.write_text("{}\n", encoding="utf-8")
            expected_path.write_text("{}\n", encoding="utf-8")
            record_path.write_text(
                json.dumps(
                    {
                        "outcome": "positive-epoch-pointer",
                        "transitions": [],
                    }
                ),
                encoding="utf-8",
            )

            scenario_manifest = {
                "schema": "ascendancy.a1-sidecar-scenario-qualification/v1",
                "planets": {"scenario-planet-a": "0" * 64},
            }
            with (
                patch.object(bundle, "build_manifest", return_value=scenario_manifest),
                patch.object(bundle, "validate_record", return_value={"outcome": "positive-epoch-pointer"}),
            ):
                with self.assertRaisesRegex(
                    bundle.A1SelectionControlError,
                    "positive outcome requires exactly one selection-control transition",
                ):
                    bundle.validate_bundle(qualification_path, expected_path, record_path)


if __name__ == "__main__":
    unittest.main()
