# Ascendancy Auto-Management

Experimental modding and reverse-engineering project for the 1995 DOS strategy game Ascendancy.

The project aims to reduce late-game planetary micromanagement by extending the game's existing planet self-management with explicit strategic profiles such as **Agricultural**, **Industrial**, and later other useful specializations.

## First milestone

The first milestone proves that the game can represent and expose multiple per-planet automation modes:

> For every player-owned planet, the UI can select **Manual / Agricultural / Industrial**, and the selected mode remains correct for the current game session.

At this milestone Agricultural and Industrial may still execute identical behavior. Differentiated build policies, per-turn policy execution, and save-game persistence are later work.

`README.md` is an overview, not an operator-facing projection or a source of current planning/evidence state. See [`ROADMAP.md`](./ROADMAP.md) for live project state and [`docs/re/`](./docs/re/) plus [`docs/experiments/`](./docs/experiments/) for current evidence.

## Repository workflow

Freely distributed candidate executables can be fetched and verified through the repository's pinned acquisition tool:

```sh
python3 tools/fetch_free_targets.py
python3 tools/fetch_free_targets.py --list
python3 tools/fetch_free_targets.py --verify
```

The static-analysis entry points are:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

Exact target identities, parser/layout corrections, comparison counts, and other mutable findings intentionally live in the canonical evidence records rather than being duplicated here.

## Development model

The project uses an evidence-first reverse-engineering loop:

**observe → hypothesize → instrument → test → update model → patch**

Before taking work, read [`AGENTS.md`](./AGENTS.md), the live [`ROADMAP.md`](./ROADMAP.md), and the relevant durable evidence. For the detailed workflow see [`docs/agent-playbook.md`](./docs/agent-playbook.md).

The repository is cloud-first: active roadmap items declare whether they are cloud-executable, cloud-feasibility research, gated, or local-only. A missing capability in one runner is not by itself evidence that the project requires local execution.

## Repository layout

- [`ROADMAP.md`](./ROADMAP.md) — live backlog, dependencies, execution environment and milestone state.
- [`AGENTS.md`](./AGENTS.md) — canonical repository-wide rules for coding agents.
- [`docs/agent-playbook.md`](./docs/agent-playbook.md) — operational workflow.
- [`docs/roadmap-authoring.md`](./docs/roadmap-authoring.md) — roadmap-maintenance rules.
- `docs/re/` — durable reverse-engineering findings.
- `docs/experiments/` — reproducible experiments and negative results.
- `tools/` — reusable analysis and diagnostic tooling.
- `scripts/` — automation for validation and evidence handling.
- `tests/` — synthetic and repository-level regression tests.
- `binaries/`, `reference/`, `artifacts/`, `captures/` — local or ephemeral material; ignored and not committed.

## Scope

The project focuses on player-facing planetary automation. It is not an attempt to rewrite the whole game, replace all game AI, rebalance the game, or build a generic mod framework unless later evidence makes that necessary.

The repository does not redistribute proprietary game executables or copyrighted game assets. Reverse-engineering outputs should contain only the minimal information needed to reproduce and review the work.
