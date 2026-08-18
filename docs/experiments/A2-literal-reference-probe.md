# A2 Stage 1 follow-up — literal-reference probe tooling

Date: 2026-08-18  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence class in this slice: **synthetic/tooling** until an exact-target run completes.

## Question

Stage 1 found two large fully file-backed zero ranges in object 2, at VA `0x96c10` / 6206 bytes and `0x988dc` / 3052 bytes. The Stage 1 producer established only zero content plus absence of incoming direct call/branch targets under GNU objdump linear sweep. Can an independent raw-byte probe cheaply expose obvious non-control-flow consumers before any runtime watch experiment or Stage 2 loader-growth work?

## Bounded method

[`../../scripts/probe_a2_literal_references.py`](../../scripts/probe_a2_literal_references.py) scans every mapped LE object byte at every byte offset for little-endian 32-bit values that land inside either candidate under two interpretations:

- the encoded value is a linear virtual address inside the candidate;
- the encoded value is relative to the candidate's target LE-object base.

This deliberately does **not** reuse the Stage 1 zero-run detector or GNU-objdump direct-control-flow model as its oracle. It is a raw literal search over mapped bytes.

The CLI is pinned to canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, exposes no expected-hash override, verifies that both candidate ranges remain inside their declared LE object, and refuses an output path that aliases the immutable target input.

## Evidence boundary

A literal hit is an **investigation lead**, not proof of a semantic reference: arbitrary data can encode the same value accidentally. Conversely, zero literal hits do **not** establish that a range is unused. The probe does not exclude LE relocation/fixup references, narrower encodings, computed or indirect addressing, runtime initialization, scratch use, sentinel semantics, or any other consumer.

For that reason every emitted candidate remains:

```text
reusable: false
reuse_evidence: not established
```

regardless of the scan result.

## Synthetic validation

[`../../tests/test_probe_a2_literal_references.py`](../../tests/test_probe_a2_literal_references.py) covers:

- unaligned literal matches;
- both linear-VA and target-object-relative interpretations;
- boundary values immediately outside a candidate;
- fail-closed missing target-object and out-of-object candidates;
- fail-closed target hash mismatch;
- CLI inability to override the canonical hash;
- output/input alias rejection;
- preservation of `reusable: false` even when the static probe completes.

These tests establish the probe's behavior only. They do not establish anything about the canonical target ranges.

## Exact-target execution path

[`../../.github/workflows/a2-literal-reference-probe.yml`](../../.github/workflows/a2-literal-reference-probe.yml) is the exact-target evidence generator. It supports both manual `workflow_dispatch` and pull-request execution when any material producer/parser/acquisition input changes. The pull-request path exists so an exact PR head can produce reviewable target evidence without relying on an operator-side dispatch capability.

The workflow fetches only the hash-pinned canonical Antagonizer executable, runs the repository probe, binds the detached JSON to the checkout plus all material producer/parser/acquisition inputs, prints only compact counts, and uploads only the derived JSON. It does not upload target bytes.

The evidence command is:

```sh
python tools/fetch_free_targets.py antagonizer-en
python scripts/probe_a2_literal_references.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a2-literal-reference-probe.json
```

The pull-request trigger covers all repository inputs that can materially change the evidence:

- `.github/workflows/a2-literal-reference-probe.yml`;
- `scripts/probe_a2_literal_references.py`;
- `tools/fetch_free_targets.py`;
- `tools/free-target-sources.json`;
- `tools/le_image.py`.

## Status impact

Adding exact-head PR execution changes only the evidence delivery path; it does not itself establish a target result or change A2 planning state. A2 remains `Investigation first`; mechanism A remains unselected and both Stage 1 ranges remain non-reusable until an exact-target artifact is actually produced and interpreted.

When the exact-target scan runs, any hits must be investigated as possible consumers. If it has no useful hits, that negative result still does not establish reusable capacity; the roadmap's bounded runtime observation remains desirable where practical, otherwise A2 should proceed to the already-defined Stage 2 target-neutral LE-growth control rather than promote a cave by absence-of-evidence.
