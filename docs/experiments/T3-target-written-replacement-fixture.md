# T3 — target-written replacement fixture experiment

- Roadmap item: **T3 — Supply a multi-planet save fixture for M1 validation**
- Tracking issue: **#34 — T3: prepare target-written replacement fixture experiment**
- Evidence state: **experiment contract only; not yet run**
- Intended evidence class after execution: **runtime**
- Blind-RE provenance: **clean**
- Canonical target: `ANTAG.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes

## Question

The current operator multi-planet fixture has passed current-state runtime qualification, but its exact-byte producer provenance remains only reported. The first ordinary-save producer probe was negative: canonical `ANTAG.EXE` loaded the operator state and wrote a new save, but those bytes did not match either operator file.

Can T3 instead create a **new, stable fixture whose exact bytes are demonstrably written by canonical `ANTAG.EXE` through ordinary play**, then independently re-run the existing current-state qualifier against those same exact bytes?

This follows the second completion path already allowed by `ROADMAP.md`; it does not reinterpret the negative producer probe as positive evidence.

## Evidence boundary

The experiment must use the verified retail runtime and exact canonical target. Operator/source inputs are immutable evidence: any run that can write saves executes only in an isolated verified working copy. No proprietary executable or save payload is committed to git.

A successful producer result and a successful current-state result are separate evidence axes:

1. **Producer axis:** canonical `ANTAG.EXE` writes a save through an ordinary in-game save path. The exact resulting bytes are hash-pinned under a new fixture id, and the detached producer record binds those bytes to the canonical target and the committed harness/configuration identities.
2. **Current-state axis:** those exact target-written bytes are passed unchanged to `scripts/run_t3_multi_planet_fixture.py`, which independently establishes the role-critical current runtime properties.

The role remains unusable if either axis is missing, malformed, stale, refers to different bytes, or fails its semantic oracle.

## Bounded method

1. Verify the canonical target and retail runtime manifest before launching the game.
2. Create an isolated writable copy of the verified runtime tree; remove unrelated mutable save outputs from that copy so output selection is unambiguous.
3. Start canonical `ANTAG.EXE` through the existing DOSBox/Xvfb + XTEST runtime path and reach a known multi-planet campaign state using only ordinary UI actions and already-qualified input state.
4. Invoke the ordinary **Save Game** path to an explicitly empty slot. The save action must be bounded by timeout/termination rules and must identify exactly one newly written candidate payload.
5. After the target is stopped, hash the target-written payload and preserve only safe metadata in the detached producer record. Do not copy the proprietary payload into the repository.
6. Assign a **new fixture id** to that exact hash. Do not reuse `resume-en-operator-multi-planet-2026-08-14`, because its bytes and provenance history are different.
7. Run `scripts/run_t3_multi_planet_fixture.py` against the exact target-written payload. The qualifier must receive the new bytes as immutable candidate input and must still execute against a fresh isolated copy of the verified runtime tree.
8. Promote the new fixture to role `m1-multi-planet` only if both the producer artifact and the independent current-state artifact bind the same fixture SHA-256 and canonical target SHA-256 and both validators pass.

## Producer success oracle

Positive producer evidence requires all of the following:

- the executable identity is exactly canonical `ANTAG.EXE`;
- the source retail tree passed its existing manifest verification before copying;
- the game wrote exactly one intended save payload through ordinary UI, without guest code/data patching;
- the output payload exists after the bounded run and its SHA-256/size are recorded;
- the detached record contains `validation-fixture-production:v1` semantics with `target_written_exact_bytes: true` only for that exact output hash;
- the detached record identifies the scenario/configuration and the complete material harness/tool source closure needed to audit the run;
- source/operator inputs remain unchanged.

Failure to establish any condition is a negative/inconclusive producer result, not partial positive provenance.

## Current-state success oracle

The second phase uses the existing T3 qualifier rather than a producer-specific shortcut. The exact target-written bytes must load successfully on canonical `ANTAG.EXE` and independently satisfy the qualifier's existing M1 role contract, including at least two current-player-owned planets and at least one player-owned planet with an empty current action at load. The candidate bytes must remain unchanged by the qualification run.

A producer PASS without this current-state PASS creates a correctly proven target-written save that is **not** a valid `m1-multi-planet` fixture. A current-state PASS on bytes other than the producer-bound hash does not satisfy producer provenance.

## Detached evidence requirements

The producer artifact should be machine-readable, bounded, and safe to commit when it contains no proprietary payload bytes. It must include at least:

- explicit schema/version;
- canonical target SHA-256 and verified retail-fixture identity;
- exact produced fixture SHA-256 and size;
- ordinary-save method/scenario identity;
- producer harness/configuration identities or hashes for all material inputs;
- DOSBox/runtime environment identity material to the claim;
- termination result and bounded timing outcome;
- `target_written_exact_bytes` result;
- source-input unchanged checks;
- names/digests of any bounded auxiliary artifacts, without embedding the save itself.

The current-state artifact remains the independently generated output of `scripts/run_t3_multi_planet_fixture.py` and must bind the same fixture hash.

## Failure and ambiguity handling

Fail closed when no save is written, multiple candidate save outputs are created, the intended output cannot be distinguished without guessing, the target/retail identity is wrong, source evidence changes, the run exceeds its bound, or the producer and qualifier bind different fixture hashes. Preserve useful negative metadata where safe instead of selecting a convenient candidate.

Do not claim that `resume.gam` is automatically materialized unless a bounded run directly observes that behavior. The previous producer probe explicitly did not observe it.

## Acceptance for the preparation slice

This document only defines the next reproducible experiment and its evidence boundary. It does **not** claim that a new target-written fixture exists, that T3 is complete, or that V1 is unblocked.

The implementation/execution slice that follows should automate the producer path as far as practical, emit the detached producer artifact, then feed the exact resulting bytes into the already-established current-state qualifier without weakening either validator.
