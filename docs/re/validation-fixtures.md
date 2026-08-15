# Save fixtures for runtime validation

Durable record of which saved games the project relies on, what each one is allowed to be used for, and what a future save must satisfy before an experiment may depend on it.

Declarations live in [`../../tools/validation-fixtures.json`](../../tools/validation-fixtures.json) and are checked by `scripts/validate_validation_fixtures.py`.

## Where save payloads live

A fixture declares `storage`, and both values are legitimate:

- `repository` — the payload is committed under `fixtures/saves/`, and the declaration check then requires it to be present and hash-verified on every run.
- `operator-supplied` — the payload is maintainer-supplied and referenced by hash only. Absence is reported rather than fatal, unless the caller passes `--require-present`.

Nothing in the repository rules forbids committing a save. `AGENTS.md` bars proprietary game binaries, copyrighted assets, private dumps, huge captures, secrets, and private user data; a maintainer's own save of their own game is none of those. The retail manifest's exclusion of "mutable configuration/save files" describes what that manifest pins — immutable runtime files — not a commit ban. `resume.gam` is committed at `fixtures/saves/resume.gam`; it carries only game-generated content — star, planet and technology names from the game's own tables — and no personal data.

For saves specifically, committing is usually the better default. A fixture that exists only on one machine can be lost, and every conclusion pinned to its hash then becomes unreproducible; the declaration makes that loss detectable but cannot undo it. A save is also small — the current one is 81647 bytes — and the repository already commits target-derived material of the same kind, including planet names taken from the game's own tables.

Before committing a save, check three things: that it is the maintainer's own save of a game they are entitled to distribute, that it carries no personal data (the player name is the likely place), and that it has not grown large enough to belong under an ignored path instead.

## Established property of the current fixture

`resume.gam` (SHA-256 `fe7b29f6…`) has **exactly one player-owned planet**, `Xerxes I`.

RE4 established `Xerxes I` as a player-owned planet record in this save, and the RE5 follow-up established that it is the only one while investigating whether a same-race record bracket could be built around it. Both are now in the supported repository state; see [`auto-management-turn-path.md`](./auto-management-turn-path.md). The observations were:

- the immediate `Xerxes ± 0x7b` records are `Stavern IV` and `Xerxes II`, both owner `0xff`;
- `Xerxes I` is the only record with owner `0`;
- the nearest owned records on either side belong to other races.

RE3 established that the per-race pass skips planets whose `+0x57` does not match the race identity, so the player-race pass over this save visits exactly one planet record.

### What that blocks

V1 requires setting `Agricultural` on one player-owned planet and `Industrial` on a different one, then confirming both hold their own mode. **Those steps cannot be performed on `resume.gam` at all**, and no fixture declaring two player-owned planets exists. This is a fixture limitation rather than an implementation gap, and it is independent of how A1/A2 choose to represent the profile.

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

## Adding a fixture

`scripts/add_validation_fixture.py` takes the save plus a description of what it contains, computes size and SHA-256, copies the payload into the repository when it is committed, writes the declaration, and refuses to write anything that would not validate. `--dry-run` shows the computed entry without touching either.

Agents have the same workflow as a skill at [`.claude/skills/add-save-fixture/SKILL.md`](../../.claude/skills/add-save-fixture/SKILL.md).

The declaration must name every player-owned planet individually rather than only counting them. The count is derived from the names, duplicate names are rejected, and the planets that start with no current action are named separately — those are the properties consumers actually branch on.

## Verification status

Runtime properties in the declaration are claims, and each carries an `evidence` level.

A role is satisfied only by `runtime` evidence that names its source and comes from a save produced by the canonical target. Three separate conditions, each of which can fail on its own:

- `evidence` must be `runtime`. `unverified` is a legitimate declaration — that is how a save enters the repository before anyone has run it — and `static` reasoning about a save's bytes is not the same claim as observing what a running game does with it. Neither satisfies a role.
- `source` must name a Markdown experiment record under `docs/experiments/` that declares `Evidence class: **runtime**`, contains both this fixture's full SHA-256 and the full `produced_by_target_sha256`, and carries exactly one `<!-- validation-fixture-observations:v1 -->` fenced JSON block. That block independently pins the fixture/target identities plus `player_race_id`, the player-owned count/names, and the planets observed with an empty current action at load. Promotion fails closed if any declared role-critical property differs from the structured observations; merely mentioning the two hashes is not evidence for arbitrary properties.
- `produced_by_target_sha256` must be the canonical `ANTAG.EXE`. A save written by the bug-patch build or the vanilla release cannot carry evidence about the canonical target.

The structured observation block is the promotion authority for those role-critical properties: prose may explain how the experiment established them, but it cannot override, fill in, or silently widen the machine-readable observations.

A fixture failing any of these is reported as unusable and `--require-role <role>` fails.

Declared-but-wrong properties are treated differently from unverified ones. If a fixture claims verified evidence and its own numbers contradict the role it claims, validation fails closed rather than marking it unusable: an honest "not checked yet" is a state to work through, a verified claim that does not hold is an error.

The declaration check is intentionally split in two: the declaration is always validated, while payload identity is verified when the payload is reachable. A `repository` fixture must always be present and verified; an `operator-supplied` one is verified only when the file is supplied.
