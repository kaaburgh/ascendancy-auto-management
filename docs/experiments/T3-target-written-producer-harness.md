# T3 — target-written fixture producer harness

- Roadmap item: **T3 — Supply a multi-planet save fixture for M1 validation**
- Tracking issue: **#36 — T3: implement fail-closed target-written fixture producer harness**
- Evidence state: **tooling only; exact-target producer scenario not yet run**
- Intended evidence class after successful execution: **runtime**
- Blind-RE provenance: **clean**
- Canonical target: `ANTAG.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes

## Purpose

`script/run_t3_target_written_fixture.py` is intentionally not a claim that a replacement fixture exists. It implements the producer-side safety and evidence boundary defined by [`T3-target-written-replacement-fixture.md`](./T3-target-written-replacement-fixture.md): a future bounded run may load a qualified seed state, drive only ordinary XTEST UI input, require one unambiguous numbered save output, preserve the exact target-written bytes at an operator path outside the repository, and emit a detached producer record without embedding the proprietary payload.

The executable path is `scripts/run_t3_target_written_fixture.py`.

## Fail-closed boundaries

The harness requires all of the following before a positive record can be emitted:

- the source retail tree passes the existing canonical retail manifest verifier;
- `ANTAG.EXE` matches the canonical size and SHA-256;
- the seed save matches a caller-supplied SHA-256 and remains unchanged;
- the UI scenario is a committed JSON file under `tools/` or `docs/`, schema `1`, with a bounded runtime and at most 32 actions;
- allowed scenario actions are only pointer movement, click, key input and bounded waits; there is no guest memory/code mutation primitive;
- the isolated working copy begins with numbered saves removed;
- exactly one numbered save is observed after the ordinary UI sequence, and it must be the declared output slot;
- the output becomes stable before the scenario deadline and is non-empty;
- the operator output path is outside both the repository and the immutable source game tree and must not already exist;
- the detached JSON artifact and exact harness source snapshot live under `docs/experiments/`.

The producer artifact uses schema `ascendancy.validation-fixture-producer/v1` and scenario contract `validation-fixture/canonical-target-exact-byte-producer/v1`, matching the existing consumer in `scripts/validate_validation_fixtures.py`. It records canonical target/retail identities, DOSBox identity, material runtime configuration, action-scenario path and SHA-256, exact harness source SHA-256/snapshot, bounded termination, no diagnostic guest writes, unchanged source inputs, and the exact output hash/size.

## Scenario still required

No target-specific action scenario is committed by this slice. The earlier negative producer probe retained the semantic sequence—load the qualified state and use ordinary Save Game—but explicitly did **not** retain its one-shot XTEST source. Reconstructing coordinates or inventing screen oracles from memory would turn an unsupported assumption into executable evidence.

A later bounded slice must independently reacquire and preserve the ordinary Save Game UI action sequence as a committed JSON scenario before an exact-target producer run is attempted. That scenario becomes a material, hash-bound input to any positive artifact.

## Validation scope

Synthetic unit coverage exercises action-schema rejection, runtime bounding, pointer bounds, output ambiguity/wrong-slot handling, operator-path immutability, overwrite rejection, and the producer artifact identity shape. Those tests establish harness behavior only. They do not establish that a target save was written or that any produced bytes satisfy `m1-multi-planet`.

## Remaining T3 gate

After a future producer PASS, the exact operator-held output bytes must independently pass `scripts/run_t3_multi_planet_fixture.py` in a fresh isolated runtime and the resulting fixture declaration must bind the producer and current-state records to the same fixture SHA-256. Until then T3 remains incomplete and V1 cannot consume a replacement fixture.
