# Ascendancy Auto-Management

Experimental modding and reverse-engineering project for the 1995 DOS strategy game [Ascendancy](https://en.wikipedia.org/wiki/Ascendancy_(video_game)).

The project aims to reduce late-game planetary micromanagement by extending the game's existing planet self-management with explicit strategic profiles such as **Agricultural**, **Industrial**, and later **Scientific** or other useful specializations.

## Product idea

A player-owned planet may be placed under a selected auto-management profile. On each turn, the planet should make construction and development decisions according to that profile until the player changes the profile or returns the planet to manual control.

The intended behavior is deliberately policy-driven rather than a general-purpose AI governor: a profile should be predictable enough that a player can use it as a strategic tool.

Examples of eventual profiles:

- **Agricultural** — prioritize population/prosperity capacity and the infrastructure needed to sustain growth.
- **Industrial** — prioritize production capacity and infrastructure that accelerates construction.
- **Scientific** — prioritize research output while maintaining enough growth and production to remain functional.

The exact policy rules are intentionally out of scope for the first milestone.

## First milestone

The first milestone proves that the game can represent and expose multiple per-planet automation modes:

> For every player-owned planet, the UI can select **Manual / Agricultural / Industrial**, and the selected mode remains correct for the current game session.

At this milestone Agricultural and Industrial may still execute identical behavior. Differentiated build policies, per-turn policy execution, and save-game persistence are later work.

See [`ROADMAP.md`](./ROADMAP.md) for the executable task plan.

## Target strategy

T1 selected an exact English Antagonizer build as the M1 production target and the same-language official bug-patch build as the canonical differential baseline:

- **M1 target:** `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes.
- **Comparison baseline:** `PATCH_EN.EXE` / publisher `PATCH.EXE` version 1.6.5, SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`, 587451 bytes.

The International pair remains a future-compatibility/cross-locale corroboration set; M1 support is not silently broadened to it.

T1's static lineage experiment found the same Antagonizer↔bug-patch object-layout and unique-string displacement transformation in both English and International pairs. That strongly supports a directly comparable build lineage and makes the English publisher bug patch a useful RE1 baseline, while still requiring RE1 to treat unrelated bug-fix/configuration drift as a possible confound rather than calling every difference AI behavior.

Every later offset, signature or patch byte must still be tied to an exact cryptographic hash. Do not assume state representation, runtime layout, or a patch seam until established by evidence.

Details: [`docs/re/targets.md`](./docs/re/targets.md), [`docs/re/target-manifest.json`](./docs/re/target-manifest.json), and [`docs/experiments/T1-canonical-target-selection.md`](./docs/experiments/T1-canonical-target-selection.md).

### Obtaining the candidate executables

The Antagonizer is a **standalone complete game executable** that runs in place of the retail `ASCEND.EXE`, and The Logic Factory released it — and the official bug patch — free of charge in 1995. Those executables are therefore fetchable directly, which means static reverse engineering needs no handoff of proprietary files:

```sh
python3 tools/fetch_free_targets.py          # fetch and verify every candidate
python3 tools/fetch_free_targets.py --list   # ids, sizes and pinned hashes
python3 tools/fetch_free_targets.py --verify # re-verify offline
```

Files land in the git-ignored `binaries/`. The tool only ever downloads artifacts pinned in `tools/free-target-sources.json`, verifies the archive and the extracted executable against exact sizes and SHA-256 hashes, and writes nothing when any check fails. It requires only stdlib Python and HTTPS egress to `archive.org` and `*.archive.org`.

The retail game **data** files are a different matter: a retail installation requires the maintainer's own copy, since the game is not sold on any current storefront. But that does not mean cloud cannot run the game at all — an officially distributed **playable demo** exists and is a lawfully redistributable candidate for a cloud runtime fixture. It must be investigated before runtime work is declared local-only. That evaluation is [`ROADMAP.md`](./ROADMAP.md)'s CF3.

Only freely distributed artifacts may be added to the acquisition manifest — never full-game images, retail distributions, or abandonware repacks.

Acquisition provenance: [`docs/experiments/CF1-cloud-target-access.md`](./docs/experiments/CF1-cloud-target-access.md).

### Analysing them

The targets are DOS Linear Executable (`LE`) images with a bound Rational DOS/4G extender, built with Watcom C/C++32. None of the tools preinstalled in the tested cloud image lays that container out — `objdump` rejects it outright and `file` only classifies it — so the repository carries its own parser. LE-aware dumpers do exist in the wider ecosystem, notably Open Watcom's `wdump`; Open Watcom's structure/linker/dumper sources are used as an independent layout oracle rather than making the whole compiler suite a required dependency.

> **CF2 correction note:** review found that the first parser revision used LE header `+0x70` (`impmod_off`) as the enumerated-page base. Open Watcom establishes absolute `page_off @ +0x80`. The parser, fixtures and tests were corrected, all four pinned real targets were re-analysed with the current branch semantics, and the old disassembly/diff numbers were replaced rather than offset-adjusted. The execution-method note and exact reconstructed-object regression hashes are in [`docs/experiments/CF2-real-target-regeneration.md`](./docs/experiments/CF2-real-target-regeneration.md); layout evidence is in [`docs/experiments/CF2-wdump-layout-correction.md`](./docs/experiments/CF2-wdump-layout-correction.md). Do not copy the pre-correction CF2 numbers from git history or review comments.

The intended pipeline needs only the Python standard library and `objdump`; no GUI, no JVM, no `pip install`:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE       # container and load map
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE    # strings with virtual addresses
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary # candidate functions, call graph
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

`le_disasm` now emits a versioned inventory with the target SHA-256, reconstructed-object SHA-256, parser-layout identity, and three signature levels. `le_diff` fails closed on stale or incompatible JSON and uses a conservative four-class comparison: exact matches preserve every operand; `reference_only_differences` differ only in in-image references after masking and may contain either relocation noise or real callee/global/table retargets; `constant_only_differences` have the same instruction shape but different remaining constants and may contain either DS-relative movement or genuine threshold/flag changes; only the remainder is structural.

On the corrected English pair the current classes are **72 exact matches / 613 reference-only / 525 constant-only / 116 / 87 structural** (Antagonizer / patch). The international pair is **72 / 611 / 520 / 123 / 93**. The earlier post-layout-correction headline of `685 strict` English and `683 strict` international was itself too aggressive: those aggregates masked changed in-image references and split exactly into `72 exact + 613 reference-only` and `72 exact + 611 reference-only`. Structural and constant-only counts are unchanged. These are analysis leads, not verified behavioral differences.

Read the limits in [`docs/experiments/CF2-cloud-static-re.md`](./docs/experiments/CF2-cloud-static-re.md) before trusting any candidate function boundary: the inventory comes from a linear sweep with boundaries inferred from direct call targets, so it produces regions/leads, not verified functions; functions reached only indirectly may be folded into a preceding candidate span.

## Cloud-first development

This repository is intentionally organized so that as much work as possible can be performed by coding agents in **Codex cloud** or **Claude cloud**.

Closed-source game modification creates three likely friction points: access to proprietary target files, running/debugging the DOS game, and visually validating UI behavior. The roadmap therefore does **not** mark those steps local-only by default. It first creates explicit cloud-feasibility investigations.

Every active roadmap item has an execution classification:

- **CLOUD** — a cloud coding agent may take and complete the item.
- **CLOUD RESEARCH** — a cloud agent investigates whether a gated target step can be made cloud-executable. The investigation must update the roadmap with the result.
- **GATED** — do not take this task yet; its execution environment is decided by a named cloud-feasibility task.
- **LOCAL ONLY** — a cloud agent must not take the task. This label should appear only after a feasibility investigation documents why cloud execution is not practical.

If a step truly requires a local machine, the preferred pattern is still cloud-first: the cloud agent prepares the smallest possible one-shot local experiment, the maintainer runs it, and a subsequent CLOUD task consumes the resulting safe artifacts.

## Development model

The game is closed-source, so the project uses an evidence-first reverse-engineering loop:

**observe → hypothesize → instrument → test → update model → patch**

Important rules are documented in [`AGENTS.md`](./AGENTS.md):

- distinguish established evidence from assumptions;
- tie binary-specific facts to exact target hashes;
- prefer reversible and fail-closed patch mechanisms;
- keep negative RE results because they prevent repeated dead ends;
- never claim target-game validation when only synthetic or static checks ran;
- keep proprietary binaries and raw target-machine artifacts out of the repository.

For the detailed agent workflow see [`docs/agent-playbook.md`](./docs/agent-playbook.md).

## Repository layout

- [`ROADMAP.md`](./ROADMAP.md) — live backlog, dependencies, execution environment and milestone state.
- [`AGENTS.md`](./AGENTS.md) — canonical repository-wide rules for coding agents.
- [`CLAUDE.md`](./CLAUDE.md) — Claude-specific entry point that delegates to `AGENTS.md`.
- [`docs/agent-playbook.md`](./docs/agent-playbook.md) — operational reverse-engineering workflow.
- [`docs/roadmap-authoring.md`](./docs/roadmap-authoring.md) — rules for keeping roadmap items agent-sized and evidence-driven.
- `docs/re/` — durable reverse-engineering findings.
- `docs/experiments/` — reproducible experiments, including negative results.
- `tools/` — reusable analysis, diffing, patching and diagnostic tooling.
- `scripts/` — automation for builds, validation, target capture and local handoff experiments.
- `tests/` — tests and synthetic fixtures for logic that can be validated without the game.
- `binaries/`, `reference/`, `artifacts/`, `captures/` — local/ephemeral material; ignored and not committed.

## For coding agents

Before taking work:

1. Read [`AGENTS.md`](./AGENTS.md).
2. Read the current milestone and task-selection rules in [`ROADMAP.md`](./ROADMAP.md).
3. Choose only a task whose dependencies are satisfied and whose execution classification allows your environment.
4. Read the linked RE notes and experiments.
5. Keep the task bounded. If new evidence changes the plan, update the roadmap in the same PR instead of silently continuing under invalid assumptions.

A cloud agent must never pick a **GATED** or **LOCAL ONLY** item.

## Scope and non-goals

The project currently focuses on player-facing planetary automation. It is not an attempt to rewrite Ascendancy, replace the entire game AI, rebalance the game, or build a generic mod framework unless later evidence shows that one of those is necessary for the feature.

The repository must not redistribute proprietary game executables or copyrighted game assets. Reverse-engineering outputs should contain only the minimal information needed to reproduce and review the work.
