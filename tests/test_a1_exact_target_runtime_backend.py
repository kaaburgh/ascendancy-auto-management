from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a1_exact_target_runtime_backend import (  # noqa: E402
    A1ExactTargetBackendError,
    A1ExactTargetRuntimeBackend,
)


class ExactTargetRuntimeBackendTests(unittest.TestCase):
    def _backend(self, *, resolver=None, driver=None):
        resolver = resolver or (
            lambda *args: {"record_pointer": 0x2340, "record": b"x" * 0x7B}
        )
        driver = driver or (
            lambda **kwargs: {"completed": True, "lifecycle_signal": None}
        )
        return A1ExactTargetRuntimeBackend(
            pid=7,
            anchor={"map_start": 0x1000, "map_end": 0x9000},
            data_bias=0x20,
            manifest={"schema": "synthetic"},
            replacement_driver=driver,
            selected_record_resolver=resolver,
        )

    def test_qualify_delegates_to_selected_record_resolver(self) -> None:
        calls = []

        def resolver(*args):
            calls.append(args)
            return {"record_pointer": 0x3450, "record": b"r" * 0x7B}

        backend = self._backend(resolver=resolver)
        got = backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)

        self.assertEqual(got["record_pointer"], 0x3450)
        self.assertEqual(got["record"], b"r" * 0x7B)
        self.assertFalse(got["population_replacement"])
        self.assertEqual(calls[0][0], 7)
        self.assertEqual(calls[0][4], "A")

    def test_completed_replacement_marks_only_next_qualification(self) -> None:
        backend = self._backend()
        result = backend.replace(
            step_id="reset", mechanism="new-game-reset", timeout_seconds=3
        )
        self.assertTrue(result["completed"])

        first = backend.qualify(
            step_id="post-reset", logical_label="A", timeout_seconds=2
        )
        second = backend.qualify(
            step_id="later", logical_label="A", timeout_seconds=2
        )
        self.assertTrue(first["population_replacement"])
        self.assertFalse(second["population_replacement"])

    def test_failed_replacement_does_not_mark_population_replacement(self) -> None:
        backend = self._backend(driver=lambda **kwargs: {"completed": False})
        result = backend.replace(
            step_id="load", mechanism="save-load-replacement", timeout_seconds=3
        )
        self.assertFalse(result["completed"])
        got = backend.qualify(step_id="after", logical_label="A", timeout_seconds=2)
        self.assertFalse(got["population_replacement"])

    def test_second_replacement_before_post_qualification_is_rejected(self) -> None:
        backend = self._backend()
        backend.replace(step_id="reset", mechanism="new-game-reset", timeout_seconds=3)
        with self.assertRaisesRegex(
            A1ExactTargetBackendError, "before post-replacement qualification"
        ):
            backend.replace(
                step_id="load", mechanism="save-load-replacement", timeout_seconds=3
            )

    def test_invalid_resolver_record_fails_closed(self) -> None:
        backend = self._backend(
            resolver=lambda *args: {"record_pointer": 1, "record": "not-bytes"}
        )
        with self.assertRaisesRegex(A1ExactTargetBackendError, "invalid record"):
            backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)

    def test_nonpositive_timeout_fails_before_runtime_driver(self) -> None:
        calls = []

        def driver(**kwargs):
            calls.append(kwargs)
            return {"completed": True}

        backend = self._backend(driver=driver)
        with self.assertRaisesRegex(A1ExactTargetBackendError, "timeout_seconds"):
            backend.replace(step_id="reset", mechanism="new-game-reset", timeout_seconds=0)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
