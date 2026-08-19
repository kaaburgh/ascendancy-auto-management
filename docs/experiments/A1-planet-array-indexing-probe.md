# A1 — bounded planet-array indexing probe

Date: 2026-08-19  
Roadmap item: **A1 — Design the M1 per-planet profile state representation**  
Issue: **#26**  
Evidence class in this slice: **synthetic/tooling until the exact-target workflow runs**  
Blind-RE provenance: **clean**

## Question

A1 selected a two-layer representation but cannot finish the sidecar contract until it has a reuse-safe logical planet identity/lifetime rule. Current supported evidence establishes the `0x7b` planet-record stride and two independently useful planet loops, but it does not establish an array base/count or a slot index that may safely key the sidecar.

Can a bounded static probe of the already-established turn and owned-planet loops produce independent leads for the array/indexing relationship without promoting literal overlap into an identity claim?

## Prepared probe

[`../../scripts/probe_a1_planet_array_indexing.py`](../../scripts/probe_a1_planet_array_indexing.py) operates only on canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`. It reconstructs LE object 1 with the existing parser and disassembles only two code windows already supported by RE3 evidence:

- `0x20c94..0x20e30` — the turn-level planet loop;
- `0x3bf80..0x3c130` — the owned-planet loop containing the player automation gate.

The probe records only:

- instructions in each bounded window whose operands contain the established `0x7b` stride;
- absolute operands that fall inside LE object 2;
- the intersection of those data-object operands across both windows.

The output deliberately leaves `array_base`, `array_count`, and `slot_indexing` as `null` and status `unestablished`. A shared literal can identify a high-value follow-up location, but it does not prove that the location is a planet-array base/count, that an index is stable, or that a record address cannot be reused.

This is intentionally different from A2's capacity/literal work: the question is A1 logical identity/indexing, and no candidate mapped-capacity conclusion is consumed or produced.

## Why this is useful

A1 currently risks two bad shortcuts: treating a valid pointer as a stable identity, or inferring a slot from the known stride without establishing the base/count relationship. The probe narrows the next investigation to concrete operands used by both known planet loops while preserving ambiguity if there is no unique shared lead.

A useful exact-target result can therefore do one of three things:

1. identify a small shared operand set that deserves independent semantic/runtime validation;
2. show that the two loops do not share a simple absolute operand, eliminating the easiest static-base model;
3. fail closed because the expected `0x7b` loop evidence no longer appears in one of the supported windows, signalling drift in the project model/tooling.

None of these outcomes completes A1 by itself.

## Exact-target execution

The canonical executable is freely redistributed and already has a fail-closed acquisition path, so the probe has a manual GitHub Actions workflow at [`.github/workflows/a1-planet-array-indexing.yml`](../../.github/workflows/a1-planet-array-indexing.yml).

The evidence-producing commands are:

```sh
python tools/fetch_free_targets.py antagonizer-en
python scripts/probe_a1_planet_array_indexing.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a1-planet-array-indexing.json
```

The workflow records the checkout SHA and SHA-256 values of every material repository input, then uploads only the derived JSON. No proprietary retail data are required and no target executable is uploaded as evidence.

The workflow remains `workflow_dispatch` rather than ordinary PR correctness CI because remote exact-target acquisition is evidence production, not a dependency of every PR's correctness gate.

## Synthetic validation

[`../../tests/test_probe_a1_planet_array_indexing.py`](../../tests/test_probe_a1_planet_array_indexing.py) covers bounded disassembly parsing, stride recognition, data-object operand collection, shared-lead intersection, and the rule that even a unique shared operand must not populate `array_base`, `array_count`, or `slot_indexing` automatically.

These tests validate the probe's fail-closed interpretation boundary only. They do not establish a target-specific indexing relationship.

## Status impact

A1 remains **Investigation first**. The two-layer sidecar representation remains selected, but the reuse-safe key/epoch and lossless Manual-transition invalidation boundary remain open. This slice prepares an independent static lead generator for the first half of that remaining work; it does not change the roadmap state or authorize UI2/A2 to assume a slot index.
