# A2 Stage 1 follow-up — bounded runtime capacity observation

Date: 2026-08-19  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence class in this slice: **synthetic/tooling** until an exact-target run completes.

## Question

Stage 1 found large fully file-backed zero ranges at object-2 VAs `0x96c10` / 6206 bytes and `0x988dc` / 3052 bytes. The independent raw-literal probe subsequently found many byte patterns that numerically land inside both ranges, but those hits are investigation leads rather than semantic-reference proof.

Can a bounded **read-only runtime observation** establish whether either nominally-zero range is materialized non-zero or mutated while the canonical game makes normal progress, without changing guest code or data?

A positive mutation/materialization observation would directly disqualify the simple "unused zero cave" model for the observed bytes. A negative observation is deliberately weaker: it means only that this one scenario did not observe a write. It does not observe reads and must not promote the range to reusable capacity.

## Prepared harness

[`../../scripts/run_a2_capacity_runtime_observation.py`](../../scripts/run_a2_capacity_runtime_observation.py) reuses the already-supported RE4/RE5 cloud runtime path rather than inventing a new DOS execution model.

The harness:

1. verifies the complete pinned retail runtime fixture and canonical `ANTAG.EXE` identity through the existing RE4/RE5 verification path;
2. copies the supplied retail tree to an isolated writable work directory before launch;
3. parses exact `ANTAG.EXE` and fail-closes unless both candidate ranges still belong to object 2 and are still all-zero in the file-backed image;
4. launches canonical `ANTAG.EXE` through the established DOSBox/Xvfb path and loads the canonical `resume.gam` scenario;
5. finds the unique runtime RE2 toggle anchor whose static VA is `0x37915`, then translates candidate VAs by the already-established anchor-relative relationship used by RE5;
6. independently checks the translation at each candidate boundary by requiring the live bytes immediately before and after the zero range to match the exact file-backed boundary bytes;
7. takes coherent candidate snapshots while DOSBox is stopped for each sample, with no guest writes;
8. returns to normal game flow, enables the existing fast-forward UI action, and samples for a bounded window while also checking the established stardate witness advances;
9. emits only derived metadata: hashes, counts, bounded changed offsets, mapping/fixture/harness provenance, and scenario facts. Raw process-memory bytes and the proprietary target are not written to the artifact.

The default observation window is 7 seconds at a 50 ms requested sample interval. The CLI rejects windows above 20 seconds and sample intervals outside 25–250 ms.

## Runtime mapping boundary

The harness does not assume a DOS/4G selector/base model. RE5 already uses the unique runtime code anchor at static `0x37915` to express exact-target relationships inside the same runtime mapping. This observer reuses that established relationship for candidate VAs.

Because the candidates are data-object ranges rather than code near the anchor, the observer adds a second fail-closed check: the non-zero file-backed guard bytes immediately before and after each candidate must match the translated live memory. If either guard differs, the run aborts rather than selecting a convenient mapping.

This guard comparison uses the project's LE parser to obtain the exact file-backed boundary bytes, so it is a structural target/mapping cross-check, not an independent second LE implementation. It is sufficient to prevent a silent anchor-arithmetic misaddress in this harness; it does not upgrade the broader LE parser evidence beyond its existing validation.

## Observation oracle

For each candidate, the detached record reports:

- exact VA, size and object;
- hash of the static all-zero candidate bytes;
- hashes and live-match status for both boundary guards;
- initial/final snapshot hashes;
- initial and maximum non-zero-byte counts;
- whether any sampled byte differed from the initial runtime snapshot;
- number of offsets that differed and the first 64 changed offsets;
- up to 16 distinct snapshot hashes;
- explicit `reusable: false` / `reuse_evidence: not established` regardless of result.

The run fails if the stardate witness does not advance. A stationary/hung target is therefore not accepted as meaningful negative mutation evidence.

Interpretation is intentionally asymmetric:

- **initial runtime non-zero bytes or observed mutation:** evidence against treating the affected bytes as an unused zero cave in the observed scenario;
- **all samples remain zero/unchanged:** only a bounded negative mutation result. Reads, writes outside the window, mode-specific use, other scenarios, initialization before observation, and indirect consumers remain unresolved.

## Reproducible target-machine command

This exact-target runtime experiment needs the pinned retail runtime fixture, so ordinary public CI cannot produce the target result. Run it in a cloud/task environment where the verified retail tree is supplied as input:

```sh
python scripts/run_a2_capacity_runtime_observation.py \
  --game-dir /path/to/verified-retail-tree \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --dosbox dosbox \
  --output artifacts/a2-capacity-runtime-observation.json
```

The output path must be outside the immutable retail evidence tree.

Required host capabilities are the same established runtime stack used by RE4/RE5: Python, DOSBox, Xvfb, X11/XTEST libraries, and access to `/proc/<dosbox-pid>/mem` for read-only observation plus stop/resume control.

## Serialized evidence provenance

The detached result uses schema `ascendancy.a2-capacity-runtime-observation/v1` and records hashes for the material repository inputs that affect execution or interpretation:

- `scripts/run_a2_capacity_runtime_observation.py`;
- `scripts/run_re4_runtime_state.py`;
- `scripts/run_re5_runtime_turn_path.py`;
- `tools/le_image.py`;
- `tools/retail-runtime-manifest.json`.

It also records the canonical target and retail-fixture identities, runtime anchor relationship, bounded scenario timing, stardate progress, and explicit no-guest-write facts.

## Synthetic validation in this slice

[`../../tests/test_run_a2_capacity_runtime_observation.py`](../../tests/test_run_a2_capacity_runtime_observation.py) covers:

- all-zero candidate and non-zero boundary-guard requirements;
- rejection of a candidate that changed from the Stage-1 zero premise;
- rejection of wrong-object declarations;
- unchanged-snapshot reporting without accidental reuse promotion;
- mutation/non-zero reporting and bounded changed-offset capture;
- snapshot-size mismatch rejection;
- anchor-relative candidate translation and mapping-bound failure.

These tests establish harness logic only. They do not claim an exact-target runtime result.

## Status impact

A2 remains `Investigation first`. This preparation slice does not select mechanism A, does not mark either candidate reusable or unusable, and does not advance to Stage 2. It supplies the bounded runtime observation requested by the existing Stage-1 plan.

After an exact-target run, reconcile the result into durable A2 evidence. If the ranges show runtime materialization/mutation, mechanism A loses support for those bytes. If they remain unchanged, further evidence is still required before any reuse claim; if sufficiently defensible existing mapped capacity still cannot be established, proceed to the already-prepared Stage-2 loader-growth control.
