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
from a1_lifetime_observer_core import A1ObserverExecutionError  # noqa: E402
from a1_selected_record_runtime import A1SelectedRecordResolutionError  # noqa: E402


class ExactTargetRuntimeBackendTests(unittest.TestCase):
    def _backend(self, *, resolver=None, selection=None, driver=None):
        resolver = resolver or (
            lambda *args: {"record_pointer": 0x2340, "record": b"x" * 0x7B}
        )
        selection = selection or (
            lambda **kwargs: {"action_completed": True}
        )
        driver = driver or (
            lambda **kwargs: {"completed": True, "lifecycle_signal": None}
        )
        return A1ExactTargetRuntimeBackend(
            pid=7,
            anchor={"map_start": 0x1000, "map_end": 0x9000},
            data_bias=0x20,
            manifest={"schema": "synthetic"},
            selection_driver=selection,
            replacement_driver=driver,
            selected_record_resolver=resolver,
        )

    def test_qualify_runs_requested_input_action_before_witness_resolution(self) -> None:
        calls = []

        def selection(**kwargs):
            calls.append(("selection", kwargs))
            return {"action_completed": True}

        def resolver(*args):
            calls.append(("resolver", args))
            return {"record_pointer": 0x3450, "record": b"r" * 0x7B}

        backend = self._backend(resolver=resolver, selection=selection)
        got = backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)

        self.assertEqual(got["record_pointer"], 0x3450)
        self.assertEqual(got["record"], b"r" * 0x7B)
        self.assertFalse(got["population_replacement"])
        self.assertEqual(calls[0], (
            "selection",
            {"step_id": "control-a", "logical_label": "A", "timeout_seconds": 2.0},
        ))
        self.assertEqual(calls[1][0], "resolver")
        self.assertEqual(calls[1][1][0], 7)
        self.assertEqual(calls[1][1][4], "A")

    def test_uncompleted_selection_action_fails_before_record_resolution(self) -> None:
        resolver_calls = []

        def resolver(*args):
            resolver_calls.append(args)
            return {"record_pointer": 0x3450, "record": b"r" * 0x7B}

        backend = self._backend(
            resolver=resolver,
            selection=lambda **kwargs: {"action_completed": False},
        )
        with self.assertRaisesRegex(A1ExactTargetBackendError, "did not complete"):
            backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)
        self.assertEqual(resolver_calls, [])

    def test_nonobject_selection_result_fails_before_record_resolution(self) -> None:
        resolver_calls = []

        def resolver(*args):
            resolver_calls.append(args)
            return {"record_pointer": 0x3450, "record": b"r" * 0x7B}

        backend = self._backend(resolver=resolver, selection=lambda **kwargs: True)
        with self.assertRaisesRegex(A1ExactTargetBackendError, "selection driver returned"):
            backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)
        self.assertEqual(resolver_calls, [])

    def test_selected_record_resolution_error_is_normalized_for_observer_retry(self) -> None:
        def resolver(*args):
            raise A1SelectedRecordResolutionError("short selected-planet record read")

        backend = self._backend(resolver=resolver)
        with self.assertRaisesRegex(
            A1ExactTargetBackendError, "selected-record qualification failed"
        ) as caught:
            backend.qualify(step_id="control-a", logical_label="A", timeout_seconds=2)

        self.assertIsInstance(caught.exception, A1ObserverExecutionError)
        self.assertIsInstance(caught.exception.__cause__, A1SelectedRecordResolutionError)

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

    def test_nonpositive_timeout_fails_before_runtime_drivers(self) -> None:
        selection_calls = []
        replacement_calls = []

        def selection(**kwargs):
            selection_calls.append(kwargs)
            return {"action_completed": True}

        def driver(**kwargs):
            replacement_calls.append(kwargs)
            return {"completed": True}

        backend = self._backend(selection=selection, driver=driver)
        with self.assertRaisesRegex(A1ExactTargetBackendError, "timeout_seconds"):
            backend.qualify(step_id="a", logical_label="A", timeout_seconds=0)
        with self.assertRaisesRegex(A1ExactTargetBackendError, "timeout_seconds"):
            backend.replace(step_id="reset", mechanism="new-game-reset", timeout_seconds=0)
        self.assertEqual(selection_calls, [])
        self.assertEqual(replacement_calls, [])


if __name__ == "__main__":
    unittest.main()
