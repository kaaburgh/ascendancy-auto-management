"""Thin runtime backend binding the A1 observer core to selected-record resolution."""
from __future__ import annotations

from typing import Any, Callable, Protocol

try:
    from .a1_lifetime_observer_core import A1ObserverExecutionError
    from .a1_selected_record_runtime import (
        A1SelectedRecordResolutionError,
        resolve_selected_record,
    )
except ImportError:
    from a1_lifetime_observer_core import A1ObserverExecutionError
    from a1_selected_record_runtime import (
        A1SelectedRecordResolutionError,
        resolve_selected_record,
    )


class A1ExactTargetBackendError(A1ObserverExecutionError):
    """Retryable qualification/backend failure understood by the observer core."""


class SelectionDriver(Protocol):
    def __call__(
        self, *, step_id: str, logical_label: str, timeout_seconds: float
    ) -> dict[str, Any]: ...


class ReplacementDriver(Protocol):
    def __call__(
        self, *, step_id: str, mechanism: str, timeout_seconds: float
    ) -> dict[str, Any]: ...


class A1ExactTargetRuntimeBackend:
    """Bind bounded target actions to exact selected-record reads.

    This adapter deliberately does not discover witnesses, lifecycle signals, or
    UI semantics. Every qualification first delegates the requested logical
    selection to a separately bounded driver and only then resolves the selected
    record through the already reviewed fail-closed resolver. Replacement actions
    and any candidate lifecycle signal are likewise supplied by a separately
    bounded target driver.
    """

    def __init__(
        self,
        *,
        pid: int,
        anchor: dict[str, Any],
        data_bias: int,
        manifest: dict[str, Any],
        selection_driver: SelectionDriver,
        replacement_driver: ReplacementDriver,
        selected_record_resolver: Callable[..., dict[str, Any]] = resolve_selected_record,
    ) -> None:
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise A1ExactTargetBackendError("pid must be a positive integer")
        if not isinstance(data_bias, int) or isinstance(data_bias, bool):
            raise A1ExactTargetBackendError("data_bias must be an integer")
        if not isinstance(anchor, dict) or not isinstance(manifest, dict):
            raise A1ExactTargetBackendError("anchor and manifest must be objects")
        if (
            not callable(selection_driver)
            or not callable(replacement_driver)
            or not callable(selected_record_resolver)
        ):
            raise A1ExactTargetBackendError("runtime drivers must be callable")
        self._pid = pid
        self._anchor = anchor
        self._data_bias = data_bias
        self._manifest = manifest
        self._selection_driver = selection_driver
        self._replacement_driver = replacement_driver
        self._resolve = selected_record_resolver
        self._replacement_pending = False

    @staticmethod
    def _timeout(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise A1ExactTargetBackendError("timeout_seconds must be positive")
        return float(value)

    def qualify(
        self, *, step_id: str, logical_label: str, timeout_seconds: float
    ) -> dict[str, Any]:
        timeout = self._timeout(timeout_seconds)
        if not isinstance(step_id, str) or not step_id.strip():
            raise A1ExactTargetBackendError("step_id must be non-empty")
        if not isinstance(logical_label, str) or not logical_label.strip():
            raise A1ExactTargetBackendError("logical_label must be non-empty")

        selection = self._selection_driver(
            step_id=step_id,
            logical_label=logical_label,
            timeout_seconds=timeout,
        )
        if not isinstance(selection, dict):
            raise A1ExactTargetBackendError("selection driver returned non-object")
        if selection.get("selected") is not True:
            raise A1ExactTargetBackendError(
                "selection driver did not confirm requested logical selection"
            )

        try:
            resolved = self._resolve(
                self._pid,
                self._anchor,
                self._data_bias,
                self._manifest,
                logical_label,
            )
        except A1SelectedRecordResolutionError as exc:
            raise A1ExactTargetBackendError(
                f"selected-record qualification failed: {exc}"
            ) from exc
        if not isinstance(resolved, dict):
            raise A1ExactTargetBackendError("selected-record resolver returned non-object")
        pointer = resolved.get("record_pointer")
        record = resolved.get("record")
        if not isinstance(pointer, int) or isinstance(pointer, bool) or pointer < 0:
            raise A1ExactTargetBackendError("selected-record resolver returned invalid pointer")
        if not isinstance(record, bytes):
            raise A1ExactTargetBackendError("selected-record resolver returned invalid record")

        replacement = self._replacement_pending
        self._replacement_pending = False
        return {
            "record_pointer": pointer,
            "record": record,
            "population_replacement": replacement,
        }

    def replace(
        self, *, step_id: str, mechanism: str, timeout_seconds: float
    ) -> dict[str, Any]:
        timeout = self._timeout(timeout_seconds)
        if self._replacement_pending:
            raise A1ExactTargetBackendError(
                "replacement action cannot run before post-replacement qualification"
            )
        if not isinstance(step_id, str) or not step_id.strip():
            raise A1ExactTargetBackendError("step_id must be non-empty")
        if not isinstance(mechanism, str) or not mechanism.strip():
            raise A1ExactTargetBackendError("mechanism must be non-empty")

        result = self._replacement_driver(
            step_id=step_id, mechanism=mechanism, timeout_seconds=timeout
        )
        if not isinstance(result, dict):
            raise A1ExactTargetBackendError("replacement driver returned non-object")
        if result.get("completed") is not True:
            return result
        self._replacement_pending = True
        return result
