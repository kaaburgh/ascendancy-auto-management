# Save fixtures for runtime validation

Durable record of which saved games the project relies on, what each one is allowed to be used for, and what a future save must satisfy before an experiment may depend on it.

Declarations live in [`../../tools/validation-fixtures.json`](../../tools/validation-fixtures.json) and are checked by `scripts/validate_validation_fixtures.py`.

## Why save payloads are not committed

`tools/retail-runtime-manifest.json` pins the immutable retail payload by size and SHA-256 and states that the proprietary payload is never committed; mutable configuration and save files are deliberately excluded from it. `AGENTS.md` places proprietary game material and local raw artifacts under ignored paths.

Save fixtures follow the same model: the payload is maintainer-supplied and referenced by hash, and only the declaration is committed. A save is game-generated rather than a shipped asset, so this is a convention rather than a settled legal boundary — see the open question at the end of this document.

The cost of that choice is real and should be stated plainly: a fixture that exists only on one machine can be lost, and every conclusion pinned to its hash becomes unreproducible. The declaration exists so that the loss is at least detectable rather than silent.

## Established property of the current fixture

`resume.gam` (SHA-256 `fe7b29f6…`) has **exactly one player-owned planet**, `Xerxes I`.

This was established by the RE5 follow-up in PR #18, while investigating whether a same-race record bracket could be built around `Xerxes I`. The full derivation lands in [`auto-management-turn-path.md`](./auto-management-turn-path.md) with that PR; the observations are:

- the immediate `Xerxes ± 0x7b` records are `Stavern IV` and `Xerxes II`, both owner `0xff`;
- `Xerxes I` is the only record with owner `0`;
- the nearest owned records on either side belong to other races.

RE3 established that the per-race pass skips planets whose `+0x57` does not match the race identity, so the player-race pass over this save visits exactly one planet record.

### What that blocks

V1 requires setting `Agricultural` on one player-owned planet and `Industrial` on a different one, then confirming both hold their own mode. **Those steps cannot be performed on `resume.gam` at all.** This is a fixture limitation, not an implementation gap, and it is independent of how A1/A2 choose to represent the profile.

## Requirements for an M1 multi-planet fixture

Required — an experiment may not claim role `m1-multi-planet` without these:

1. **At least two player-owned planets.** Three or more is preferable: it leaves margin if one planet turns out to be unusable, and it is the minimum for a same-race two-sided record bracket should one ever be wanted.
2. **At least one player-owned planet with no current action at load** (`+0x52 == 0xffff`, `+0x54 == 0xff`). Every existing runner asserts this precondition; a save whose planets all carry actions breaks them.
3. **Unique planet names.** Runtime record lookup requires exactly one match for the planet name, and fails closed otherwise.
4. **Produced by the canonical target** (`ANTAG.EXE`, SHA-256 `8d91e89e…`) through ordinary play. A save written by the vanilla or bug-patch build, or edited by hand, is not evidence about the canonical target's behavior.

Strongly preferred:

5. **Same player race id as the current fixture** (`0`). A different race is not wrong, but several runners assume owner `0`, so a different race turns a fixture change into a code change.
6. **Saved at the start of the player's turn, with no modal dialog or event popup pending at load.** The UI automation drives a fixed click sequence; anything that opens over the planet view desynchronises it.
7. **A moderate rather than maximal empire.** Late game is what makes the fixture useful for differentiated policies later, but every extra planet and surviving race adds per-turn work, and the bounded observation windows are tuned against the current save's turn rate. If turn processing slows materially, window and progress thresholds must be re-derived rather than reused.
8. **Planets with visibly different characteristics** — terrain, population, resources — so that later differentiated policy work has something to differentiate.

Neutral but worth recording: whatever player name the save carries becomes part of a repository-visible fixture description, so prefer a neutral one.

## Verification status

Runtime properties in the declaration are claims, and each carries an `evidence` level. A fixture whose properties are `unverified` may be declared, but `scripts/validate_validation_fixtures.py` refuses to let it satisfy a role requirement. Promoting a fixture to `runtime` requires a named experiment that observed the properties on the exact target, in the same way the current fixture's single-planet property was established.

The declaration check is intentionally split in two: the declaration is always validated, while the payload is verified by size and SHA-256 only when it is actually present, since the payload is not part of the repository.

## Open question for the maintainer

Whether save payloads should be committed rather than referenced is a maintainer decision, not a technical one. Committing removes the loss risk described above; referencing keeps consistency with the retail manifest and with `AGENTS.md`.

This document assumes the referencing convention because that is what the repository does today. If the decision changes, it should change explicitly — by amending the rule in `AGENTS.md` and the note in the retail manifest — rather than by adding a silent exception for one file.
