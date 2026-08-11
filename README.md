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

The current direction is:

- treat the **Antagonizer** executable as the primary production target because it already contains improved planetary self-management behavior;
- keep the original/vanilla executable as a comparison baseline where useful;
- identify every supported target by exact cryptographic hash before relying on offsets, signatures, or patch bytes;
- do not assume the exact executable format, layout, state representation, or patch seam until it is established by evidence.

The canonical Antagonizer/patch combination and exact hashes are roadmap work, not assumptions baked into the implementation.

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
