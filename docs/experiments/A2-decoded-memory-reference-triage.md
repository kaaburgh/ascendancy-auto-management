# A2 Stage 1 follow-up — decoded absolute-memory reference triage

Date: 2026-08-19  
Roadmap item: A2 / issue #30  
Blind-RE provenance: **clean**  
Evidence class in this slice: **synthetic/tooling** until an exact-target run completes.

## Question

Stage 1 found two large fully file-backed zero ranges in object 2, at VA `0x96c10` / 6206 bytes and `0x988dc` / 3052 bytes. The independent all-byte literal probe later found 1983 raw u32 matches on a historical exact head (1162 and 821 respectively), but raw bytes can encode those values coincidentally.

Can a decoded-instruction pass cheaply rank that noisy result by retaining only numeric values that GNU objdump renders as absolute memory operands in code object 1?

## Bounded method

[`../../scripts/probe_a2_decoded_memory_references.py`](../../scripts/probe_a2_decoded_memory_references.py) reconstructs canonical LE object 1, runs GNU objdump in i386 Intel syntax, and records only decoded absolute-memory operands whose literal falls inside either candidate under one of the already-used address interpretations:

- linear virtual address;
- object-2-relative offset.

Immediates that are not memory operands are excluded. The probe is pinned to canonical `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, verifies the candidate/object relationship, and refuses an output path that aliases the immutable target. Because GNU objdump decoder/rendering semantics are material to the derived result, the machine-readable artifact also records the first line of `objdump --version` as `method.decoder_tool_identity`; failure to obtain that identity fails closed before evidence is emitted.

## Evidence boundary

This pass is **triage, not independent validation** of GNU objdump. It uses the same decoder family already present in the project, although it asks a different question from Stage 1's incoming direct-control-flow check.

A decoded absolute-memory hit is an investigation lead. Linear sweep can decode embedded data, and a rendered displacement still needs semantic corroboration. Conversely, zero decoded hits would not establish inactivity: computed/indirect access, runtime initialization, scratch use, sentinel semantics, differently represented relocations, or other consumers remain possible.

Every candidate therefore remains:

```text
reusable: false
reuse_evidence: not established
```

regardless of the result.

## Synthetic validation

[`../../tests/test_probe_a2_decoded_memory_references.py`](../../tests/test_probe_a2_decoded_memory_references.py) covers segment-qualified absolute memory operands, exclusion of ordinary immediates and register-relative small displacements, both candidate address interpretations, candidate boundaries, output/input alias rejection, and capture of a stable machine-readable GNU objdump identity.

These tests establish parser/classifier and provenance-contract behavior only.

## Exact-target evidence path

[`../../.github/workflows/a2-decoded-memory-references.yml`](../../.github/workflows/a2-decoded-memory-references.yml) supports manual `workflow_dispatch` and a dedicated evidence-branch `create` trigger under `evidence/a2-decoded-memory-references/`. Normal feature branches and PRs do not fetch the remote canonical target.

The evidence commands are:

```sh
python tools/fetch_free_targets.py antagonizer-en
python scripts/probe_a2_decoded_memory_references.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a2-decoded-memory-references.json
```

The workflow checks out and verifies the exact event SHA, records hashes for the workflow, probe, target fetcher, acquisition manifest and LE parser, and uploads only derived JSON. The derived JSON itself records the GNU objdump tool identity so artifacts produced from the same checkout/target but materially different binutils versions remain distinguishable.

## Status impact

This preparation slice does not change `ROADMAP.md`. A2 remains `Investigation first`; mechanism A is unselected. An eventual exact-target result can rank concrete instruction sites for review, but it cannot by itself establish reusable capacity. The bounded runtime observation remains the stronger next discriminator when the verified retail fixture is available.
