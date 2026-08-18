# A2 Stage 1 — mapped-capacity inventory tooling

Date: 2026-08-17  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence classes: **synthetic/tooling** for producer behavior; **static** for the exact-target inventory result below.

## Scope

This slice implements and executes the Stage 1 inventory producer defined by [`A2-patch-mechanism-decision.md`](./A2-patch-mechanism-decision.md). It does **not** claim that Stage 1 has established reusable capacity on the canonical target and it does not select patch family A, B, or C.

The producer is [`../../scripts/generate_a2_capacity_inventory.py`](../../scripts/generate_a2_capacity_inventory.py). It consumes an LE executable through the existing `le_image` parser and uses the existing `le_disasm` linear-sweep model for direct control-flow observations.

## Evidence boundary

The CLI is pinned to canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` and exposes no command-line override for that identity. It refuses any other input before target-specific inventory generation. The reusable internal `build_inventory()` API still accepts an expected hash so synthetic fixtures can exercise the producer without weakening the operator-facing gate.

When `--output` is used, the producer resolves both paths and fails closed if the destination aliases the immutable target executable. Inventory output must remain a separate derived artifact rather than replacing the operator-supplied evidence input.

For each mapped LE object the JSON output records object range, flags, page mapping metadata, and every contiguous zero run at or above the configured threshold. Each zero run is labeled `candidate-zero-capacity-only`, with `reusable: false` and `reuse_evidence: not established` regardless of whether the linear sweep finds an incoming direct branch/call.

The producer also records:

- file-backed spans without assuming that LE virtual pages are physically contiguous;
- whether the complete candidate range is file-backed;
- incoming direct `call`/branch targets from GNU `objdump` linear sweep for executable objects;
- the durable M1 UI/automation seams already established in `docs/re/auto-management-ui-state.md` and `docs/re/auto-management-turn-path.md`;
- target, producer, parser-layout and disassembler provenance.

Absence of a direct reference is explicitly **not** evidence that a candidate is semantically unused. Indirect references, embedded data, runtime-computed control flow and unobserved consumers remain possible. This tool is therefore a capacity *inventory*, not a code-cave classifier.

## Synthetic validation

`tests/test_generate_a2_capacity_inventory.py` covers:

- thresholded and trailing zero-run detection;
- direct call/branch extraction without treating ordinary immediates as control flow;
- fail-closed target SHA mismatch before disassembly;
- the absence of a CLI override for canonical target identity;
- fail-closed rejection when `--output` aliases the immutable target input;
- fail-closed durable-seam mapping for a noncanonical synthetic fixture;
- the distinction between file-backed bytes and virtual zero-filled object tail.

These tests establish producer behavior only. They do not establish canonical-target capacity.

## Exact-target Stage 1 result

GitHub Actions run `32088624243` executed the repository producer on PR #33 after acquiring only manifest id `antagonizer-en` through `tools/fetch_free_targets.py`. The acquisition step verified canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`; GNU objdump was version 2.42.

The exact-target inventory reported:

- 43 zero/padding candidate regions at the default 16-byte threshold;
- 42 candidates fully backed by file bytes;
- 0 candidates with an incoming **direct** call/branch target under the producer's GNU-objdump linear-sweep model;
- 23,477 direct control-flow references observed overall;
- the largest fully file-backed candidate is object 2 at VA `0x96c10`, size 6,206 bytes;
- the next largest fully file-backed candidates are object 2 at `0x988dc` (3,052 bytes), `0x99dae` (1,023), `0x9845f` (821), and `0x994d6` (813).

Every candidate remains `reusable: false`. In particular, the 6,206-byte and 3,052-byte data-object zero runs are **capacity leads only**. The lack of incoming direct control-flow references does not exclude data references, indirect/runtime-computed access, initialization semantics, sentinels, scratch storage, or other consumers. This run therefore establishes that sizeable mapped/file-backed zero regions exist on the canonical image; it does **not** establish that any byte is safe to repurpose.

The workflow uploaded only the 2.5 KiB derived inventory JSON as the short-lived `a2-stage1-capacity-inventory` artifact. No target bytes were uploaded or committed.

## Reproducible exact-target path

[`../../.github/workflows/a2-real-target.yml`](../../.github/workflows/a2-real-target.yml) binds the evidence job to the workflow itself plus every material repository input to this result: the Stage 1 producer, acquisition tool/manifest, LE parser, and disassembler. It performs:

```sh
objdump --version
python tools/fetch_free_targets.py antagonizer-en
python scripts/generate_a2_capacity_inventory.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a2-stage1-capacity-inventory.json
```

The workflow prints a compact candidate summary and uploads only the derived JSON.

## Next experiment

Independently investigate the apparently useful fully file-backed ranges, starting with `0x96c10` / 6,206 bytes and `0x988dc` / 3,052 bytes, for non-control-flow consumers and runtime mutation/reads before declaring even one byte reusable. Prefer structural evidence independent of this zero-run producer plus a bounded runtime watch/probe where practical.

If that investigation cannot establish sufficiently defensible existing mapped capacity, proceed to A2 Stage 2's target-neutral LE-growth control. Do not select the existing-mapped-byte mechanism merely because the inventory contains large zero runs.

## Status impact

A2 remains `Investigation first`. P1 remains blocked on A2. Stage 1 has now produced exact-target candidate inventory, but mechanism A is not accepted until independent evidence establishes reusable capacity; otherwise A2 proceeds to Stage 2.
