# V1 operator validation-state handoff

Date: 2026-08-14  
Roadmap item: V1  
Evidence classes: `reported` for the visible game state/provenance, `static` for file identity and byte comparison.  
Blind-RE provenance: **clean**.

## Purpose

The maintainer created a small ordinary-game state intended to remove V1's need to play forward from a new game before validating multiple per-planet M1 modes.

The raw save files are **not committed**. They are operator-supplied ephemeral runtime input, following the same model already used for the owned retail installation. Their exact identities are pinned in [`../../tools/v1-validation-state-manifest.json`](../../tools/v1-validation-state-manifest.json).

## Operator-supplied files

| File | Role | Size | SHA-256 |
| --- | --- | ---: | --- |
| `02.SAV` | manual save | 133721 | `c56d4843c171dbed5c977434037690cdfed5039ca99f80c4f0ac6f87bff47066` |
| `resume.gam` | companion resume state | 133721 | `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1` |

A byte comparison performed at handoff time found only 15 differing bytes. Every difference is at or before file offset `0x72`; bytes `0x73..EOF` are identical, with suffix SHA-256 `b04cacb277178aa0eed1b6ed5f7f596b29d3b20b1aa4d95d8c1c0bd855ef2e01`.

This is only an identity/structure observation. No save-header semantics are inferred from the differing bytes.

## Reported visible state

The maintainer supplied a screenshot of the ordinary Planets overview showing:

- player display: `Minions`;
- `3 Planets Occupied, 1 System Controlled`;
- unique visible planet names `Corpuscle I`, `Corpuscle II`, and `Corpuscle III`;
- all three visible rows show `No Project`;
- no blocking modal is visible.

The maintainer reported creating the state through ordinary play on the canonical Antagonizer, without cheats, save editing, or guest-memory modification.

These are **reported** facts until reproduced by a project runtime experiment. In particular, `No Project` must not be silently equated with the internal empty-action field until V1 or a bounded predecessor verifies it on this exact save.

## Why the raw saves are not in git

Inspection of the save bytes shows that they embed substantial game-owned string/data tables (for example technology and race/game vocabulary), not merely maintainer-authored coordinates or a tiny synthetic state description. Repository policy forbids committing copyrighted game assets/raw proprietary target material. The safe handoff is therefore hash-pinned ephemeral input rather than source-controlled raw bytes.

Do not base64-wrap the saves into a text file or otherwise bypass this rule.

## Verification

When the operator attaches the two files to a cloud task, verify their exact identity before use:

```sh
python3 tools/verify_v1_validation_state.py \
  --input-dir /path/to/attached/save-directory
```

The verifier intentionally resolves the reviewed repository manifest at `tools/v1-validation-state-manifest.json` internally. The normal CLI has no manifest/source override; tests may inject a synthetic manifest only through the Python-only test seam.

Expected identity-only result:

```text
V1 operator validation-state identity: PASS (2 files; suffix identical from 0x73)
Runtime game-state verification is still required by V1.
```

Before V1 relies on this state, the runtime harness must still establish at least:

1. the save loads under canonical `ANTAG.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
2. the player/race identity required by the V1 scenario;
3. at least two distinct player-owned planets, with unique names;
4. at least one player-owned planet whose **internal** current-action state is empty;
5. a stable scripted start without a blocking modal;
6. any additional UI2-specific selector/oracle prerequisites needed by the final V1 action file.

If the candidate fails one of those runtime checks, preserve the failure and either choose the companion file or produce a new operator save; do not weaken V1's acceptance criteria.
