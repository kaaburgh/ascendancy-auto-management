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

V1 requires setting `Agricultural` on one player-owned planet and `Industrial` on a different one, then confirming both hold their own mode. **Those steps cannot be performed on the historical single-planet `resume.gam` at all.** T3 supplies a separate operator-supplied multi-planet fixture; the historical save remains the fixture of record for completed RE4/RE5 evidence rather than being replaced.

## T3 multi-planet fixture

`resume-en-operator-multi-planet-2026-08-14` is an operator-supplied `resume.gam`, 133721 bytes, SHA-256 `d2b8df5d57ac3151d0ba09533f5f0644785bb0911a25470b7ef7e541d6bbeac1`. Its current role properties are `runtime` evidence from [`../experiments/T3-multi-planet-save-fixture.md`](../experiments/T3-multi-planet-save-fixture.md):

- current player/race id `0`;
- exactly three player-owned planets: `Corpuscle I`, `Corpuscle II`, `Corpuscle III`;
- all three load with no current action (`+0x52 == 0xffff`, `+0x54 == 0xff`);
- the independently discovered 305-record runtime planet sequence has unique names.

The payload remains `operator-supplied`, not committed. T3 independently establishes exact-target load compatibility and the role-critical **current-state** runtime properties. Historical producer provenance remains the maintainer report preserved by the V1 handoff: the declaration keeps `producer_provenance.evidence: reported` rather than upgrading that claim to runtime evidence. Under the 2026-08-18 T3 acceptance decision recorded in `ROADMAP.md` and issue #38, `m1-multi-planet` does **not** require byte-for-byte reproduction of the historical save write. Exact payload identity plus the detached canonical-target current-state runtime qualification are the load-bearing evidence axes for this role, so the fixture is role-usable while the producer report remains metadata.

The negative canonical-save probe remains useful evidence: a later `Load -> Save Game` operation produced a different target-written payload. That proves the save operation is not byte-stable for this replay; it does not establish that the historical operator files were produced by another executable or edited externally. See [`../experiments/T3-producer-provenance-probe.md`](../experiments/T3-producer-provenance-probe.md).

The declaration keeps the same stable fixture id and exact bytes that were introduced as `unverified`; current-state runtime qualification does not rebind that id to a derived save and does not silently promote a maintainer provenance statement into runtime producer evidence.

The RE4/RE5 selection entry points accept an explicit save hash and planet name while retaining the historical `Xerxes I` defaults. RE4 additionally accepts a bounded visible planet-list row. Exact-target row-1 validation on `Corpuscle I` established two distinct UI geometries: click centers use a 145-pixel stride, while the `Self-Managed` renderer-oracle regions use a measured 141-pixel stride. RE5 focused-artifact aggregation rejects mixed planet identities.

## Requirements for an M1 multi-planet fixture

Required — an experiment may not claim role `m1-multi-planet` without these:

1. **At least two player-owned planets.** Three or more is preferable: it leaves margin if one planet turns out to be unusable, and it is the minimum for a same-race two-sided record bracket should one ever be wanted.
2. **At least one player-owned planet with no current action at load** (`+0x52 == 0xffff`, `+0x54 == 0xff`). Every existing runner asserts this precondition; a save whose planets all carry actions breaks them.
3. **Unique planet names.** Runtime record lookup requires exactly one match for the planet name, and fails closed otherwise.
4. **Canonical-target provenance.** `produced_by_target_sha256` must name canonical `ANTAG.EXE` (`8d91e89e…`). For the current operator fixture, the maintainer's ordinary-play provenance report is accepted for this historical-authorship fact; the role does not require a later save operation to reproduce the historical payload byte-for-byte. A save known to come from the vanilla/bug-patch build or known to be externally edited is not acceptable.
5. **Independent current-state runtime qualification on the canonical target.** The role requires the detached T3 runtime observation artifact for the exact fixture bytes; a maintainer report alone cannot establish player ownership/count/action state.

Strongly preferred:

6. **Same player race id as the current fixture** (`0`). A different race is not wrong, but several runners assume owner `0`, so a different race turns a fixture change into a code change.
7. **Saved at the start of the player's turn, with no modal dialog or event popup pending at load.** The UI automation drives a fixed click sequence; anything that opens over the planet view desynchronises it.
8. **A moderate rather than maximal empire.** Late game is what makes the fixture useful for differentiated policies later, but every extra planet and surviving race adds per-turn work, and the bounded observation windows are tuned against the current save's turn rate. If turn processing slows materially, window and progress thresholds must be re-derived rather than reused.
9. **Planets with visibly different characteristics** — terrain, population, resources — so that later differentiated policy work has something to differentiate.

Neutral but worth recording: whatever player name the save carries becomes part of a repository-visible fixture description, so prefer a neutral one.

## Adding a fixture

`scripts/add_validation_fixture.py` takes the save plus a description of what it contains, computes size and SHA-256, copies the payload into the repository when it is committed, writes the declaration, and refuses to write anything that would not validate. `--dry-run` shows the computed entry without touching either.

Agents have the same workflow as a skill at [`.claude/skills/add-save-fixture/SKILL.md`](../../.claude/skills/add-save-fixture/SKILL.md).

The declaration must name every player-owned planet individually rather than only counting them. The count is derived from the names, duplicate names are rejected, and the planets that start with no current action are named separately — those are the properties consumers actually branch on.

## Verification status

Runtime properties in the declaration are claims, and each carries an `evidence` level.

A role is evaluated against independent evidence axes rather than treating one target hash as proof of everything:

- **Current-state runtime properties.** `runtime_properties.evidence` must be `runtime`, and `runtime_properties.source` must name a Markdown experiment under `docs/experiments/` that declares `Evidence class: **runtime**`, names this fixture's full SHA-256 and the canonical runtime target, and carries exactly one `<!-- validation-fixture-observations:v1 -->` fenced JSON block. The block pins the fixture/target identities plus `player_race_id`, player-owned count/names, and empty-current-action planets. For roles with `requires_detached_runtime_observation_artifact: true`, it must also pin a detached JSON run artifact by repository path and SHA-256. The validator requires that artifact to be the passed `ascendancy.t3-multi-planet-fixture/v2` / `t3/operator-save-runtime-verify/v2` record for the same fixture/role, canonical target, clean read-only runtime execution, pinned DOSBox configuration, content-addressed runner-source and harness-dependency identities whose exact executed bytes are materialized by the T3 runner and preserved under `docs/experiments/`, coherent stopped-process mapping, unchanged source bytes, and matching current-state observation oracle. Editing the Markdown block alone cannot promote the role.
- **Producer provenance when the role requires it.** `produced_by_target_sha256` identifies the **claimed** producer target; equality with the canonical SHA is necessary but is never runtime evidence by itself. A role with `requires_runtime_canonical_target_production: true` additionally requires `producer_provenance.evidence: runtime` and a Markdown runtime source under `docs/experiments/` containing exactly one `<!-- validation-fixture-production:v1 -->` fenced JSON block. That block is only an index: it binds the exact fixture SHA, canonical target SHA, ordinary-game method, and `target_written_exact_bytes: true`, **and** pins a detached JSON run artifact by repository path plus SHA-256. The run artifact must be a passed `ascendancy.validation-fixture-producer/v1` record that independently carries exact target/fixture identities, DOSBox identity and material configuration, a repository `scripts/*.py` harness identity plus source SHA and a preserved exact executed source snapshot under `docs/experiments/`, completed ordinary-save termination, no diagnostic guest writes or source-input mutation, and a passed exact-byte output oracle. A hand-authored Markdown assertion, successful load, or different derived re-save cannot satisfy a role that explicitly opts into this requirement.

Reported or unverified producer provenance is a legitimate declaration state. It keeps a role unusable **only when that role explicitly requires runtime canonical-target production**. The current `m1-multi-planet` role does not: it preserves the maintainer provenance report as metadata while independently requiring exact payload identity and detached canonical-target current-state evidence. The generic exact-byte producer machinery remains available for future roles or experiments that opt into it.

The Markdown observation and production blocks are machine-readable indices, not self-authenticating evidence. When a role requires a detached current-state artifact, the observation block binds its claims to that hash-verified runtime record; when a role requires a detached production artifact, the production block binds producer provenance to its separate hash-verified run artifact. The validator checks the corresponding identities, harness/runtime configuration, completion state, and oracle before a required axis can satisfy the role. Prose may explain either experiment, but cannot override, fill in, or silently widen the machine-readable evidence.

A fixture failing any required axis is reported as unusable and `--require-role <role>` fails.

Declared-but-wrong properties are treated differently from unverified ones. If a fixture claims verified evidence and its own numbers contradict the role it claims, validation fails closed rather than marking it unusable: an honest "not checked yet" is a state to work through, a verified claim that does not hold is an error.

The declaration check is intentionally split in two: the declaration is always validated, while payload identity is verified when the payload is reachable. A `repository` fixture must always be present and verified; an `operator-supplied` one is verified only when the file is supplied.
