# T3 — canonical producer-provenance probe for the operator save

- Roadmap item: **T3 — Supply a multi-planet save fixture for M1 validation**
- Evidence class: **runtime**
- Blind-RE provenance: **clean**
- Date: 2026-08-15
- T3 acceptance-gate status: **superseded by the 2026-08-18 maintainer decision recorded in `ROADMAP.md` / issue #38; retained as a negative experiment**
- Target: canonical `ANTAG.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes
- Operator manual save: `02.SAV`, SHA-256 `c56d4843c171dbed5c977434037690cdfed5039ca99f80c4f0ac6f87bff47066`, 133721 bytes
- Operator resume companion: `resume.gam`, SHA-256 `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1`, 133721 bytes
- Detached runtime record: [`T3-producer-provenance-probe.json`](./T3-producer-provenance-probe.json), SHA-256 `93b6b357867ce920121ec6d4ffd69bace0f7adf5c8198a9b9ee4cd4fd11fdaee`

## Question

T3 proves that the exact operator `resume.gam` loads on the canonical target and has the required current player/planet properties. That does **not** prove the historical claim that canonical `ANTAG.EXE` wrote those exact bytes. Can an independent ordinary-game save path reproduce the operator bytes closely enough to establish exact-byte producer provenance?

This question was useful for separating current-state evidence from historical producer provenance. After the 2026-08-18 T3 acceptance decision, a positive answer is no longer required for role `m1-multi-planet`; the experiment remains valid evidence about save/re-save behavior.

## Method

The bounded probe used the pinned retail runtime and canonical target in an isolated copy, with the same DOSBox/Xvfb + XTEST input mechanism as supported runtime work. No guest code or guest data was patched. The isolated tree contained the exact operator `02.SAV` but no `resume.gam` or other numbered save. The detached JSON record preserves the target and DOSBox identities, material DOSBox/display/input configuration, semantic replay contract, termination facts, input/output hashes, and byte-difference oracle. The original one-shot XTEST source script was **not** retained; that limitation is explicit in the artifact, and this negative record is evidence for the negative result only, never acceptable positive producer provenance.

1. Start canonical `ANTAG.EXE`, choose **Load Game**, and load exact slot 2.
2. Observe that loading it does not itself materialize `resume.gam`.
3. Return through ordinary UI, choose **Save Game**, and write the state into empty slot 1.
4. Hash the target-written `01.SAV` and compare it byte-for-byte with both operator inputs.

As a control, the original operator pair differs in exactly 15 bytes, all at or before `0x72`, and is byte-identical from `0x73` through EOF.

## Result

**Negative for exact-byte producer provenance.** Canonical `ANTAG.EXE` loaded the exact slot-2 state and wrote a new 133721-byte `01.SAV` through ordinary Save Game UI. The target-written file has SHA-256 `6b2eaaa6fa1198b49d8749d3c5457e5938723527d02f0cc9e63f5e84ff608bee`.

- versus operator `02.SAV`: 942 bytes differ; first offset `0x20`, last offset `0x1ef38`; the suffix from `0x73` is not identical;
- versus operator `resume.gam`: 953 bytes differ; first offset `0x20`, last offset `0x1ef38`; the suffix from `0x73` is not identical;
- no `resume.gam` was automatically generated merely by loading slot 2.

Thus the target can load the operator state and write a derived save from it, but this experiment does **not** establish that exact `d2b8df5d…` bytes were target-written. No `validation-fixture-production:v1` block is emitted: that marker remains reserved for positive exact-byte producer evidence backed by a passed, hash-bound run artifact whose committed harness identity is independently checkable.

The negative result must also not be over-interpreted. It proves that this later `Load -> Save Game` replay did not reproduce the historical operator files byte-for-byte. It does **not** prove that those historical files were produced by another executable, edited externally, or otherwise invalid. The maintainer reports that the pair was produced through ordinary play using canonical `ANTAG.EXE`; T3 preserves that statement as `reported` provenance rather than relabeling it as runtime evidence.

## Status after the T3 acceptance decision

Exact-byte historical producer reproduction is no longer a T3/V1 fixture acceptance requirement. The current fixture is accepted on its pinned identity, canonical-target producer declaration plus maintainer provenance report, and independent detached canonical-target current-state runtime qualification.

A future exact-byte producer experiment may still be useful to understand Ascendancy save/resume serialization or to support another role that explicitly opts into `requires_runtime_canonical_target_production`. It is optional follow-up research rather than the next required T3 step.
