import tempfile
import unittest
from pathlib import Path

from scripts.run_a1_lifetime_observer import A1RuntimeObserverError, run_observer


class A1LifetimeObserverArgumentBindingTests(unittest.TestCase):
    def test_rejects_immutable_input_that_differs_from_observer_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observer = root / "observer.py"
            observer.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            observer.chmod(0o755)
            declared = root / "declared-actions.json"
            actual = root / "actual-actions.json"
            declared.write_text('{"steps":["declared"]}\n', encoding="utf-8")
            actual.write_text('{"steps":["actual"]}\n', encoding="utf-8")

            with self.assertRaisesRegex(
                A1RuntimeObserverError,
                "immutable input 'action-script' does not match observer argument --action-script",
            ):
                run_observer(
                    root / "qualification.json",
                    root / "expected.json",
                    observer,
                    ["--action-script", str(actual)],
                    5.0,
                    root / "record.json",
                    immutable_inputs={"action-script": declared},
                )


if __name__ == "__main__":
    unittest.main()
