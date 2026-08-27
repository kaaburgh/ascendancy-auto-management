#!/usr/bin/env python3
"""Public A1 lifetime oracle backed by the import-order-independent core."""
from __future__ import annotations

try:
    from scripts import _a1_sidecar_lifetime_oracle_core as _core
except ImportError:
    import _a1_sidecar_lifetime_oracle_core as _core


for _name in dir(_core):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_core, _name)


if __name__ == "__main__":
    raise SystemExit(_core.main())
