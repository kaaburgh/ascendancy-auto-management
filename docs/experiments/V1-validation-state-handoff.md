# V1 operator validation-state handoff

Date: 2026-08-14  
Updated against the T3 fixture contract: 2026-08-18  
Roadmap items: T3, V1  
Evidence classes: `reported` for the visible game state/provenance, `static` for file identity and byte comparison.  
Blind-RE provenance: **clean**.

## Purpose

The maintainer created a small ordinary-game state intended to remove V1's need to play forward from a new game before validating multiple per-planet M1 modes.

The supplied pair is kept as **operator-supplied** input for this handoff. That is a supported storage mode under the current T3 fixture contract in [`../re/validation-fixtures.md`](../re/validation-fixtures.md); this document does **not** claim that repository policy generally forbids committing maintainer-owned saves. Their exact identities and pair relationship are pinned in [`../../tools/v1-validation-state-manifest.json`](../../tools/v1-validation-state-manifest.json).

T3 owns whether a save satisfies role `m1-multi-planet`. The `resume.gam` candidate is declared as `resume-en-operator-multi-planet-2026-08-14` in [`../../tools/validation-fixtures.json`](../../tools/validation-fixtures.json). T3 runtime-qualified these exact bytes on the canonical target and promoted the same stable fixture id to `evidence: runtime`; see [`T3-multi-planet-save-fixture.md`](./T3-multi-planet-save-fixture.md). The 2026-08-18 maintainer decision recorded in `ROADMAP.md` / issue #38 accepts the maintainer's ordinary-play canonical-Antagonizer provenance report for this fixture instead of requiring a later save operation to reproduce the historical bytes exactly. This handoff remains the provenance/static-identity record and does not retroactively become runtime producer evidence.

## Operator-supplied files

| File | Role | Size | SHA-256 |
| --- | --- | ---: | --- |
| `02.SAV` | manual save | 133721 | `c56d4843c171dbed5c977434037690cdfed5039ca99f80c4f0ac6f87bff47066` |
| `resume.gam` | companion resume state / T3 candidate | 133721 | `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1` |

A byte comparison performed at handoff time found only 15 differing bytes. Every difference is at or before file offset `0x72`; bytes `0x73..EOF` are identical, with suffix SHA-256 `b04cacb277178aa0eed1b6ed5f7f596b29d3b20b1aa4d95d8c1c0bd855ef2e01`.

This is only an identity/structure observation. No save-header semantics are inferred from the differing bytes.

## Reported visible state and provenance

The maintainer supplied a screenshot of the ordinary Planets overview showing:

- player display: `Minions`;
- `3 Planets Occupied, 1 System Controlled`;
- unique visible planet names `Corpuscle I`, `Corpuscle II`, and `Corpuscle III`;
- all three visible rows show `No Project`;
- no blocking modal is visible.

The maintainer reports creating this state through ordinary play using the canonical Antagonizer (`ANTAG.EXE`), without cheats, save editing, or guest-memory modification. The maintainer further identifies `02.SAV` as the explicit/manual save and `resume.gam` as its companion resume/autosave representation.

These visible/provenance statements remain **reported** facts in this handoff. T3 independently reproduced the role-critical internal state on this exact `resume.gam`: current player id `0`, three player-owned planets with the listed names, and all three with `+0x52 == 0xffff` / `+0x54 == 0xff`. That runtime result is recorded separately in [`T3-multi-planet-save-fixture.md`](./T3-multi-planet-save-fixture.md); this document does not convert the screenshot or historical authorship report itself into runtime evidence.

The later producer probe does not contradict that report. It established that replaying `Load 02.SAV -> Save Game to another slot` produced a different 133721-byte payload. That is evidence that the later save operation was not byte-stable; it is not evidence that the historical operator pair came from another executable or was edited externally. The probe remains preserved in [`T3-producer-provenance-probe.md`](./T3-producer-provenance-probe.md).

## Storage decision for this handoff

The current fixture policy supports both repository and operator-supplied saves. For this candidate pair we keep the raw files operator-supplied because the task already has a reproducible hash-pinned handoff and the pair contains substantial game-generated string/data content. This is a scoped storage decision, not a general prohibition on committed save fixtures.

Do not base64-wrap the files or otherwise disguise them merely to bypass the selected storage mode. If the maintainer later chooses to commit a qualifying save, use the checked-in T3 authoring/validation workflow and its privacy/ownership checks rather than changing this handoff ad hoc.

## Identity verification

When the operator attaches the two files to a cloud task, verify both the exact pair relationship and the generic T3 fixture declaration before use:

```sh
python3 tools/verify_v1_validation_state.py \
  --input-dir /path/to/attached/save-directory
python3 scripts/validate_validation_fixtures.py \
  --fixture-dir /path/to/attached/save-directory \
  --require-role m1-multi-planet
```

The V1 pair verifier intentionally resolves the reviewed repository manifest at `tools/v1-validation-state-manifest.json` internally. The normal CLI has no manifest/source override; tests may inject a synthetic manifest only through the Python-only test seam.

Expected identity-only result from the pair verifier:

```text
V1 operator validation-state identity: PASS (2 files; suffix identical from 0x73)
Runtime game-state verification is still required by V1.
```

That second line describes the pair verifier's boundary: it checks identity/relationship only. The separate generic fixture validator consumes the already-published T3 current-state runtime evidence and should accept role `m1-multi-planet` for exact `resume.gam` `d2b8df5d…`. `producer_provenance.evidence` deliberately remains `reported`; under the current T3 contract that historical-provenance classification is metadata rather than a role blocker.

Payload identity verification is still required whenever the operator supplies the bytes. It does not replace T3's detached canonical-target runtime observation, and neither check replaces V1's later feature-specific end-to-end validation.

## Runtime checks after the T3 handoff

T3 establishes the **current-state** fixture facts on the exact candidate: canonical-target load, current player id, three distinct player-owned planets with unique names, and empty internal current-action state on all three. Its established UI path also reached the ordinary Planets view without a blocking modal during the bounded qualification runs. Together with the hash-pinned operator handoff and accepted maintainer provenance, this satisfies T3's fixture requirement.

V1 still owns the later feature-specific checks once its implementation dependencies are ready: the final UI2 selector/oracles, simultaneous Agricultural/Industrial identities on different planets, turn persistence, restoration to Manual, preserved automated behavior, and mod rollback. T3 completion is not evidence for those not-yet-executed behaviors.
