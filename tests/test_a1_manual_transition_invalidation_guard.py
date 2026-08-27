import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "_a1_sidecar_lifetime_oracle_cases.py"
SPEC = importlib.util.spec_from_file_location("a1_sidecar_lifetime_oracle_cases", CASES)
_cases = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(_cases)


class A1ManualTransitionInvalidationGuardTests(unittest.TestCase):
    def test_public_oracle_rejects_manual_transition_invalidation_claim(self):
        record = _cases.base_record()
        record["claims"]["manual_transition_invalidation_established"] = True

        with self.assertRaisesRegex(
            _cases.mod.A1LifetimeError,
            "must not establish Manual-transition invalidation",
        ):
            _cases.mod.validate_record(record)


if __name__ == "__main__":
    unittest.main()
