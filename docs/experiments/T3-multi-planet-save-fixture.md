# T3 — runtime qualification of the operator multi-planet save

- Roadmap item: **T3 — Supply a multi-planet save fixture for M1 validation**
- Evidence class: **runtime**
- Blind-RE provenance: **clean**
- Date: 2026-08-15
- Acceptance decision reconciled: 2026-08-18 (issue #38)
- Supported target: `ANTAG.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes
- Fixture id: `resume-en-operator-multi-planet-2026-08-14`
- Fixture: operator-supplied `resume.gam`, SHA-256 `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1`, 133721 bytes
- Published runtime-qualifier source: exact execution bytes preserved under [`T3-multi-planet-harness/`](./T3-multi-planet-harness/)
- Qualifier source SHA-256: `b811ba2b90db4664e2464a74b69a7e86d45c3c515ade54612b31c6625777030d`
- Detached artifact: [`T3-multi-planet-save-fixture.json`](./T3-multi-planet-save-fixture.json), SHA-256 `4a6f9eca8b75e5a5201a0453bebc7775e22517340609fc1d52046effba2e9e5f`
- Artifact schema: `ascendancy.t3-multi-planet-fixture/v2`
- Scenario contract: `t3/operator-save-runtime-verify/v2`

## Question and boundary

The repository pins this exact operator-supplied `resume.gam` as T3's `m1-multi-planet` candidate. The bounded runtime question is: can the exact canonical target load these exact bytes, and does a coherent runtime observation establish enough player-owned planets plus an empty current-action state for V1 steps 2–4?

The maintainer-reported campaign provenance is preserved separately in [`V1-validation-state-handoff.md`](./V1-validation-state-handoff.md). This experiment does **not** reconstruct the save's historical authoring timeline. It establishes canonical-target load compatibility and the role-critical current runtime properties below. The declaration's `produced_by_target_sha256` identifies the reported producer target, while `producer_provenance.evidence` remains `reported`; this runtime observation is not historical producer evidence for the exact save bytes.

The 2026-08-18 maintainer decision recorded in `ROADMAP.md` / issue #38 makes that distinction non-blocking for this specific role: T3 requires exact payload identity plus independent canonical-target current-state qualification, but does not require a later save operation to reproduce the historical payload byte-for-byte.

## Method

`scripts/run_t3_multi_planet_fixture.py` is read-only with respect to the source inputs. It fail-closes on the retail runtime manifest and canonical `ANTAG.EXE`, checks the candidate hash, copies the retail tree to an isolated temporary directory, replaces mutable save slots only in that copy, and launches the exact target with the candidate installed as `resume.gam`.

The runner then:

1. reaches `Return to Current Game` through the established CF4/RE4 XTEST path;
2. finds the unique relocation-tolerant RE4 runtime anchor;
3. derives the LE data-object runtime bias from the five disjoint initialized-data signatures used by the RE5 read-only witness;
4. reads the current-player id through that validated mapping;
5. stops the process for one coherent memory snapshot;
6. discovers exactly one contiguous 305-record sequence with the established `0x7b` planet-record stride, without using the declaration's ownership claim to locate it;
7. reads name `+0x24`, current slot `+0x52`, action `+0x54`, owner `+0x57`, and Managed state `+0x5a` from those runtime records;
8. requires unique names, at least two current-player-owned planets, and at least one player-owned planet with `+0x52 == 0xffff` and `+0x54 == 0xff`;
9. verifies the source candidate bytes are still byte-identical after the run.

No guest code or guest data is patched. The artifact output is preflighted before target launch: it may not alias the candidate, the fixture manifest, or any path inside the source game tree, and JSON replacement is atomic within the destination directory.

## Runtime/environment identity

The detached v2 artifact records the invoked DOSBox wrapper, not merely a human version label:

- filename `dosbox`, 176 bytes;
- SHA-256 `48ca305e0fc428de991c4bf0651ef127e9ad6a0d2eac40e228ee767ea4b1957a`;
- version output begins `DOSBox version 0.74-3`;
- host: Linux `6.18.35`, `x86_64`, Python `3.13.5`;
- DOSBox/Xvfb material configuration: `core=normal`, `cycles=max`, fullscreen false, `SDL_AUDIODRIVER=dummy`, Xvfb `1024x768x24`.

It also pins the exact imported harness SHA-256 values:

- `run_re4_runtime_state.py`: `6b2ab340ac17d822049c61e0495a809224810b56f032899b0c238882e92399ee`;
- `run_re5_runtime_turn_path.py`: `2f44d13c24540c38e8594d696b321be77cdefc1455194bdff5cd950ab023798a`;
- `run_re5_override_witness.py`: `9002537c85ae1aab6c729981acb9b42ff2e512f34a307e9fb814eaad8e670040`.

## Result

**PASS.** The exact operator fixture loaded on the canonical target and remained byte-identical. Runtime mapping derived one consistent data-object bias (`-0xd000`), the stopped snapshot contained exactly one 305-record planet sequence, and all 305 names were unique.

The current player id was `0`. Exactly three records were owned by that player:

| Planet | owner `+0x57` | slot `+0x52` | action `+0x54` | Managed `+0x5a` |
| --- | ---: | --- | --- | --- |
| `Corpuscle I` | `0` | `ffff` | `ff` | `00000000` |
| `Corpuscle II` | `0` | `ffff` | `ff` | `00000000` |
| `Corpuscle III` | `0` | `ffff` | `ff` | `00000000` |

Thus all three player-owned planets satisfy the existing empty-current-action precondition at load. The planet-name-sequence digest was `92e8f0a56ff190c717d2ed8eea8964b38691cba385ec7635029f7ee332512fc0`; stardate at the coherent observation was `390`.

<!-- validation-fixture-observations:v1 -->
```json
{
  "schema": 1,
  "fixture_sha256": "d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1",
  "target_sha256": "8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00",
  "runtime_properties": {
    "player_race_id": 0,
    "player_owned_planet_count": 3,
    "player_planet_names": [
      "Corpuscle I",
      "Corpuscle II",
      "Corpuscle III"
    ],
    "planets_with_empty_current_action_at_load": [
      "Corpuscle I",
      "Corpuscle II",
      "Corpuscle III"
    ]
  },
  "artifact": "docs/experiments/T3-multi-planet-save-fixture.json",
  "artifact_sha256": "4a6f9eca8b75e5a5201a0453bebc7775e22517340609fc1d52046effba2e9e5f"
}
```

## Parameterized-runner confirmation

T3 also had to remove the historical `Xerxes I` assumption from the reusable runtime runners without retargeting their completed evidence. On the **same exact `d2b8df5d…` fixture**:

- RE4 selected `Corpuscle I` in visible planet-list row 1 and passed the complete `Manual -> Managed -> Manual` transition, including restoration of the same row and the existing `Self-Managed` renderer oracle;
- the renderer oracle for row 1 used region `(280, 214, 100, 8)` and reproduced the pinned Managed RGB SHA-256 `66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`;
- RE5 `manual-control` selected the same `Corpuscle I`, passed over a 7-second window, preserved `slot=ffff/action=ff/Managed=0`, and observed stardate `390 -> 395` (`delta +5`).

The RE4 review experiment preserved one useful negative result: using the 145-pixel **click-center** stride for the renderer oracle sampled the wrong row. Exact-target measurement established separate geometries: click centers are `y=125 + row*145`, while the `Self-Managed` text regions are `y=73 + row*141`. The final harness models these independently. Focused RE5 artifact aggregation also rejects mixed planet identities instead of composing six individually valid scenarios from different planets.

## Superseded branch experiments

Before rebasing onto the current maintainer handoff, an earlier branch revision treated companion `02.SAV` as the T3 input and exercised a fresh target-written-save path. Current supported state intentionally qualifies the already declared operator `resume.gam` with SHA-256 `d2b8df5d…`. Those earlier derived-save runs do not replace or rebind the fixture declaration. They remain useful review history only.

## Producer-provenance follow-up and interpretation

Review correctly separated two claims that this first runtime qualifier had conflated: observing the exact operator bytes on canonical `ANTAG.EXE` is not proof that canonical `ANTAG.EXE` originally wrote those bytes. A follow-up ordinary-save probe is recorded in [`T3-producer-provenance-probe.md`](./T3-producer-provenance-probe.md). The canonical target loaded the companion `02.SAV` and wrote a derived `01.SAV`, but the result was not byte-identical to either operator file and no exact `resume.gam` representation was reproduced. Producer provenance therefore remains reported, not runtime.

That negative result is now interpreted narrowly. It establishes that a later ordinary re-save did not reproduce the historical payload; it does **not** establish that the operator files came from a different executable or were edited. Exact-byte historical reproduction is no longer a T3/V1 fixture acceptance gate. The generic producer-evidence machinery remains available for experiments that actually need that stronger claim.

## Conclusion

The declaration `resume-en-operator-multi-planet-2026-08-14` satisfies role `m1-multi-planet` under the reconciled T3 contract without changing its fixture id, bytes, or evidence labels. T3 directly observed player id `0`, the three player-owned `Corpuscle` planets, and their empty current-action state on the exact canonical target; the detached runtime artifact binds those observations to exact `resume.gam` `d2b8df5d…`. Historical authorship remains an explicit maintainer report rather than being relabeled as runtime evidence.

T3 is therefore complete. V1 may use this fixture once its independent implementation dependencies are ready; this result does not itself validate Manual/Agricultural/Industrial feature behavior.
