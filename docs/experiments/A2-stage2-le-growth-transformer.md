# A2 Stage 2 — synthetic LE growth transformer preparation

Date: 2026-08-18  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence class in this slice: **synthetic/tooling** only.

## Question

A2 Stage 1 has not established any existing mapped target bytes as reusable. The previously defined fallback is a target-neutral LE-growth control before mechanism B can be considered. What is the smallest fail-closed transformation primitive worth validating before adding independent-reader and DOS runtime oracles?

## Bounded implementation

[`../../scripts/extend_synthetic_le_capacity.py`](../../scripts/extend_synthetic_le_capacity.py) implements one intentionally narrow operation for synthetic/control LE images:

1. parse the input with the repository LE reader;
2. require sequential physical page numbering, a full final page, page data ending exactly at EOF, zero page-map slack, and no loader/fixup/auxiliary structures that this control does not know how to relocate;
3. insert one logical page-map entry immediately after a selected mapped object;
4. append one new physical page at EOF;
5. grow the selected object's page count and virtual size and shift later objects' logical first-page indices;
6. reparse the result and internally verify that the payload is mapped where expected and all pre-existing object bytes are preserved.

The canonical Ascendancy target SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` is explicitly rejected. This helper is not a production patcher and is not evidence that the target's bound DOS/4G runtime accepts layout growth.

## Why the subset is intentionally narrow

A generic LE writer would have to account for loader/fixup tables, nonresident/debug data, short final physical pages, non-sequential physical maps and possibly other structures not yet covered by an independent writer oracle. Stage 2 is an information-gain experiment, so the first primitive fails closed instead of silently moving or rewriting structures whose semantics are not yet independently validated.

The page-map insertion uses existing zero slack before enumerated page data rather than moving the data-page base. The new logical entry may point to a newly appended physical page while later logical entries retain their original physical-page numbers. This allows the control to grow a non-final logical object while preserving the bytes of later objects.

## Synthetic validation in this slice

[`../../tests/test_extend_synthetic_le_capacity.py`](../../tests/test_extend_synthetic_le_capacity.py) covers:

- growing a non-final executable object while preserving a later data object;
- growing the final data object;
- deterministic byte-identical regeneration;
- empty/oversized payload rejection;
- short-final-page rejection;
- trailing-structure rejection;
- nonzero page-map-slack rejection;
- explicit canonical-target identity refusal;
- CLI input/output alias and overwrite refusal.

These checks use the existing repository parser as an **internal structural consistency** oracle only. They do not satisfy Stage 2's required independent-reader evidence.

## Evidence boundary and remaining Stage 2 work

This preparation slice does **not** complete Stage 2. In particular it has not established either of the two required independent capability claims:

- an independent generic LE reader such as Open Watcom `wdump` agrees that the transformed layout is structurally valid;
- a redistributable/runnable LE control executes under the cloud DOS runtime and directly observes the appended mapped payload through a predeclared semantic oracle.

A deliberately malformed transformed image also still needs an independent-reader/runtime failure oracle rather than merely rejection by the same parser used during construction.

No target-specific facts are added by this slice. It must not be cited as evidence that canonical `ANTAG_EN.EXE` accepts an added page or that mechanism B is selected.

## Status impact

A2 remains `Investigation first`. Mechanism A remains unselected because Stage 1 capacity is not independently proven reusable. Mechanism B remains unselected because this slice prepares only the target-neutral transformation primitive; independent `wdump` inspection and cloud runtime execution are still required before Stage 2 can support the decision rule in [`A2-patch-mechanism-decision.md`](./A2-patch-mechanism-decision.md).

The next bounded Stage 2 action is to pair this transformer with a runnable redistributable/synthetic LE control, inspect the transformed image with an independent generic LE implementation, and run it under the existing cloud DOS runtime with an oracle that directly distinguishes access/execution of the appended page.
