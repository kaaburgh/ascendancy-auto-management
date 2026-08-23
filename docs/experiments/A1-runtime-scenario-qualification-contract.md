# A1 runtime scenario qualification contract

Date: 2026-08-23  
Roadmap item: A1 / issue #26  
Blind-RE provenance: **clean**  
Evidence class in this slice: **experiment/tooling contract only**; no new target-runtime claim.

## Purpose

The A1 sidecar lifetime oracle refuses to promote a positive identity/lifetime result unless each logical-record witness is bound to an independently supplied scenario qualification and that qualification is itself bound to independently supplied expected source identity.

The runtime observer must also know *which bounded record bytes* it is expected to observe. A digest alone is insufficient: without a predeclared record-relative range the observer would have to guess or hard-code an unbound byte slice and could not independently reproduce the qualification witness. Scenario qualification v2 therefore binds the witness digest to a record-relative offset, length, metadata basis, and rationale before the target run.

## Inputs that must be pinned independently

Before the A1 lifetime runner starts, the qualification producer receives and verifies:

- canonical target SHA-256;
- retail runtime manifest identity;
- scenario identity;
- qualification-source SHA-256 identifying the exact operator/repository-supplied qualification input;
- a finite set of exact logical planet labels used only for the bounded experiment;
- for every v2 planet witness, a non-empty bounded metadata byte sequence, its record-relative offset, and a rationale for choosing that range.

Logical labels are opaque identifiers. Producer, validator and lifetime consumer must not trim, case-fold, Unicode-normalize, locale-transform or otherwise rewrite them.

The independently supplied expected-source document remains `ascendancy.a1-sidecar-expected-source/v1`; it pins source identity, not witness layout.

## Qualification schemas

### Current observer-capable input: v2

`ascendancy.a1-sidecar-scenario-qualification-input/v2` adds two required fields to each planet entry:

- `record_offset`: non-negative byte offset from the established start of the `0x7b` planet record;
- `metadata_rationale`: non-empty explanation of why this bounded range is suitable for scenario qualification and is not merely presentation-name identity.

The supplied `metadata_hex` plus `record_offset` must fit entirely inside the established `0x7b` record. The existing 512-byte absolute witness bound remains in force.

### Current observer-capable output: v2

The producer emits `ascendancy.a1-sidecar-scenario-qualification/v2`:

```json
{
  "schema": "ascendancy.a1-sidecar-scenario-qualification/v2",
  "source": {
    "target_sha256": "<64 hex>",
    "retail_manifest_identity": "<non-empty stable identity>",
    "scenario_identity": "<non-empty stable identity>",
    "qualification_source_sha256": "<64 hex>"
  },
  "planets": {
    "<logical-label>": "<sha256 of bounded qualified metadata bytes>"
  },
  "witness_ranges": {
    "<logical-label>": {
      "metadata_basis": "bounded-record-metadata",
      "record_offset": 16,
      "length": 8,
      "sha256": "<same digest as planets[logical-label]>",
      "rationale": "<predeclared rationale>"
    }
  }
}
```

The output deliberately contains the digest and location contract but not the qualified proprietary bytes themselves. The future exact-target observer can therefore compute `record_pointer + record_offset`, read exactly `length` bytes, and compare their digest without guessing the witness range.

### Legacy v1 compatibility

The producer continues to accept `ascendancy.a1-sidecar-scenario-qualification-input/v1` and reproduce `ascendancy.a1-sidecar-scenario-qualification/v1` for existing synthetic/oracle compatibility. That path has no witness-location contract and is **not sufficient for the exact-target observer**.

The lifetime oracle's established scenario-input semantics remain v1. `scripts/a1_sidecar_evidence_bundle.py` projects a validated v2 manifest to the unchanged v1 `{source, planets}` view only after v2 qualification has been built from the independently supplied source bytes. This adapter preserves the existing lifetime-oracle decision semantics; it does not discard the v2 manifest passed to the runtime observer or written as detached evidence.

## Bounded witness rule

Each digest covers a deliberately selected, bounded metadata byte range sufficient to distinguish the scenario's known logical records during this experiment. Presentation name may be present as control/presentation evidence but may not be the sole metadata basis.

These bytes are not claimed to be an immutable planet identity. They bind scenario labels to runtime observations so pointer/index reuse can be detected without circularly trusting labels emitted by the observer itself.

## Fail-closed requirements

The producer/validator rejects unsupported schemas; malformed source identities; empty or duplicate exact logical labels; empty or oversized metadata; presentation-name-only qualification; a v2 range outside the established `0x7b` record; missing v2 range rationale; digest/input mismatches; and source identity differing from the independent expected-source document.

No positive A1 identity outcome is valid when qualification is missing or ambiguous. Exact-target observer work must use the v2 location-bearing contract, not the legacy v1 compatibility path.

## Repository-safe boundary

Commit only producer/validator code, synthetic fixtures, range descriptors and compact digests. Do not commit retail save data, target executables, qualified proprietary metadata bytes, broad memory dumps, private paths, usernames, or unrelated process memory.

## Validation slice

Synthetic validation covers deterministic v2 generation, exact source binding, canonical metadata basis, empty/oversized metadata rejection, record-range bounds, required rationale, digest mismatch rejection, exact logical-label behavior, and projection of the resulting digest map to the unchanged lifetime-oracle contract. Existing v1 synthetic callers remain accepted as compatibility-only inputs.

This is tooling evidence. It does not establish a reuse-safe key, pointer/index lifetime, epoch/reset seam, Manual-transition invalidation, or A1 completion.

## Decision boundary

The next executable work remains the exact-target lifetime observer described by `A1-sidecar-runtime-lifetime-experiment.md`: first prove the A→B→A selection control, then execute the bounded new-game/reset and save/load replacement legs. That observer must consume v2 `witness_ranges`; it must not invent or rediscover its own qualification byte range.
