#!/usr/bin/env python3
"""Public A1 lifetime oracle with selection-control validation on every positive path."""
from __future__ import annotations

from typing import Any

try:
    from scripts import _a1_sidecar_lifetime_oracle_core as _core
    from scripts.a1_selection_control_oracle import A1SelectionControlError, validate_selection_control
except ImportError:
    import _a1_sidecar_lifetime_oracle_core as _core
    from a1_selection_control_oracle import A1SelectionControlError, validate_selection_control


for _name in dir(_core):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_core, _name)

_RAW_VALIDATE_RECORD = _core.validate_record


def validate_record(
    record: dict[str, Any],
    scenario_manifest: dict[str, Any] | None = None,
    expected_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _RAW_VALIDATE_RECORD(record, scenario_manifest, expected_source)
    if result["positive_contract_accepted"]:
        try:
            validate_selection_control(record, scenario_manifest or {})
        except A1SelectionControlError as exc:
            raise _core.A1LifetimeError(str(exc)) from exc
    return result


# The legacy CLI entry point resolves validate_record through its module globals.
# Bind it to the guarded public validator so direct CLI and imported callers agree.
_core.validate_record = validate_record


if __name__ == "__main__":
    raise SystemExit(_core.main())
