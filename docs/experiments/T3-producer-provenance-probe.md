# T3 — canonical producer-provenance probe for the operator save

- Roadmap item: **T3 — Supply a multi-planet save fixture for M1 validation**
- Evidence class: **runtime**
- Blind-RE provenance: **clean**
- Date: 2026-08-15
- Target: canonical `ANTAG.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes
- Operator manual save: `02.SAV`, SHA-256 `c56d4843c171dbed5c977434037690cdfed5039ca99f80c4f0ac6f87bff47066`, 133721 bytes
- Operator resume companion: `resume.gam`, SHA-256 `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1`, 133721 bytes
- Detached runtime record: [`T3-producer-provenance-probe.json`](./T3-producer-provenance-probe.json), SHA-256 `93b6b357867ce920121ec6d4ffd69bace0f7adf5c8198a9b9ee4cd4fd11fdaee`

## Question

T3 proves that the exact operator `resume.gam` loads on the canonical target and has the required current player/planet properties. That does **not** prove the historical claim that canonical `ANTAG.EXE` wrote those exact bytes. Can an independent ordinary-game save path reproduce the operator bytes closely enough to establish exact-byte producer provenance?

## Method

The bounded probe used the pinned retail runtime and canonical target in an isolated copy, with the same DOSBox/Xvfb + XTEST input mechanism as supported runtime work. No guest code or guest data was patched. The isolated tree contained the exact operator `02.SAV` but no `resume.gam` or other numbered save. The detached JSON record preserves the target and DOSBox identities, material DOSBox/display/input configuration, semantic replay contract, termination facts, input/output hashes, and byte-difference oracle. The original one-shot XTEST source script was **not** retained; that limitation is explicit in the artifact, and this negative record is therefore evidence for the negative result only, never acceptable positive producer provenance.

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

Thus the target can load the operator state and write a derived save from it, but this experiment does **not** establish that exact `d2b8df5d…` bytes were target-written. No `validation-fixture-production:v1` block is emitted: that marker is reserved for positive exact-byte producer evidence backed by a passed, hash-bound run artifact whose committed harness identity is independently checkable.

## Next experiment

Either identify and exercise the ordinary canonical-target path that writes the exact resume-companion representation and require byte identity with `d2b8df5d…`, or create a new stable fixture whose exact bytes are demonstrably written by canonical `ANTAG.EXE`, give it a new fixture id, and re-run the existing T3 current-state qualification on that payload.
