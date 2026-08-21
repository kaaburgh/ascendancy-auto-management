# A2 — raw literal reference probe for Stage 1 capacity leads

Date: 2026-08-21  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence class in this PR: **synthetic/tooling only** until the exact target producer is run.

## Question

Can the two largest fully file-backed Stage 1 data-object zero ranges be shown to have obvious file-backed address literals elsewhere in the mapped image, using a structural check that is independent of the Stage 1 zero-run/direct-control-flow derivation?

The ranges under test are the existing Stage 1 leads:

- object 2 VA `0x96c10`, 6206 bytes;
- object 2 VA `0x988dc`, 3052 bytes.

This probe deliberately does not consume the Stage 1 inventory artifact. The ranges are pinned here from the reviewed durable result in [`A2-stage1-capacity-inventory.md`](./A2-stage1-capacity-inventory.md), while the producer independently scans mapped file-backed bytes through the existing LE parser.

## Producer

[`../../scripts/generate_a2_raw_literal_reference_probe.py`](../../scripts/generate_a2_raw_literal_reference_probe.py) is pinned to canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` with no CLI hash override.

It scans every overlapping little-endian 32-bit word whose four source bytes are contiguous and file-backed in a mapped LE object. Values landing inside either candidate range are emitted with source VA/object/file offset and candidate-relative offset.

A hit is only a **raw literal lead**. It does not prove that an instruction or data consumer reads that value. Conversely, no hit does not prove reuse safety: computed addresses, narrower encodings, indirect tables, selector-relative calculations, initialization, runtime mutation, or other consumers remain possible.

The output is therefore intentionally incapable of setting `reusable: true` or selecting mechanism A.

## Synthetic validation

`tests/test_generate_a2_raw_literal_reference_probe.py` checks overlapping/unaligned dword scanning, range-boundary handling, negative matching, and the absence of a target-hash override.

## Exact-target command

After this tooling PR is reviewed, run against a separately acquired verified canonical target:

```sh
python tools/fetch_free_targets.py antagonizer-en
python scripts/generate_a2_raw_literal_reference_probe.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a2-raw-literal-reference-probe.json
```

The detached result must be bound to the exact repository revision and material producer/parser inputs before it is promoted to durable target evidence.

The manual [`../../.github/workflows/a2-real-target.yml`](../../.github/workflows/a2-real-target.yml) evidence workflow now runs this producer beside the Stage 1 inventory after one verified target acquisition. It records the exact checkout SHA plus SHA-256 values for the workflow, acquisition inputs, LE parser and raw-literal producer, prints a compact hit summary, and uploads `a2-raw-literal-reference-probe.json` as a separate short-lived artifact. This remains an explicit evidence-generation dispatch, not a PR correctness gate.

## Decision impact

This slice does not change A2 status. If exact-target literal hits exist, inspect those source sites before any reuse claim. If no literal hits exist, that is only one independent negative structural observation; the roadmap still requires stronger structural/runtime evidence before capacity is reusable. If the bounded investigation cannot establish reusable capacity, proceed to the already-defined Stage 2 target-neutral LE-growth control rather than forcing a code-cave conclusion.
