# Repository instructions for coding agents

These instructions apply to the whole repository. Read this file before planning or changing anything, then read the roadmap item and the task-specific sources it points to.

## Source of truth

When sources disagree, use this order:

1. The current task and explicit maintainer decisions.
2. Evidence from the exact target binary or runtime being investigated.
3. Current source, tools, tests, and generated diagnostic output.
4. [`ROADMAP.md`](./ROADMAP.md), which is the live status and sequencing document.
5. Durable reverse-engineering notes under [`docs/re/`](./docs/re/) and experiment records under [`docs/experiments/`](./docs/experiments/).
6. Historical notes and superseded experiments.

Do not implement a roadmap item merely because an old note suggests it. First check the item's current status, dependencies, evidence, and accepted direction.

For the detailed workflow, repository map, and validation rules, read [`docs/agent-playbook.md`](./docs/agent-playbook.md). For writing or restructuring roadmap items, read [`docs/roadmap-authoring.md`](./docs/roadmap-authoring.md).

## Working model

Prefer this loop:

**observe → hypothesize → instrument → test → update model → patch**

If the cause is unknown, observability comes before a final patch. Prefer an experiment that can eliminate several hypotheses over a narrow experiment that confirms only one guess.

Keep these categories distinct in docs and PRs:

- **static** — established from PE metadata, disassembly, xrefs, strings, data-flow, or binary comparison for a named binary/hash;
- **runtime** — observed by debugger, hook, trace, dump, capture, or memory inspection against a named binary/hash;
- **synthetic** — established by unit/integration tests or fixtures that do not execute the actual game;
- **reported** — observed by the maintainer/user but not captured independently in a repository artifact;
- **assumed** — plausible, but not established.

A hypothesis is not a fact because it has a plausible function name. If a function is only believed to be `ManagePlanet`, label it that way until the call path or state transition establishes the role.

## Roadmap discipline

`ROADMAP.md` is the live backlog and status record, not a one-time plan.

A feature or investigation PR must update the relevant roadmap item in the same PR whenever the change affects:

- status;
- evidence or confidence;
- dependencies or sequencing;
- supported binaries;
- the proposed direction;
- acceptance criteria;
- a decision to drop, split, supersede, or defer work.

Preserve useful negative results. If an experiment disproves an item premise, mark the item `Dropped`, `Superseded`, or rewrite it with the corrected model; do not silently delete the reasoning that prevents the same mistake from being repeated.

Do not opportunistically implement later roadmap items unless they are inseparable from the current one.

## Binary compatibility and patch safety

Addresses and offsets are version-specific unless proven otherwise.

Prefer, in order:

1. exported/public APIs;
2. stable runtime relationships;
3. signatures/pattern scanning with additional invariants;
4. relative references/call relationships;
5. version-specific offsets only when necessary.

For every version-specific patch:

- identify the target executable/DLL by SHA-256 and record relevant PE metadata;
- verify expected bytes or structural invariants before patching;
- validate instruction boundaries and RIP-relative addressing where applicable;
- require an unambiguous match;
- fail closed on an unknown binary, zero matches, multiple ambiguous matches, or unexpected bytes;
- never select an arbitrary pattern match;
- keep installation and removal reversible.

If a file on disk is modified, require a hash check, backup, patch, post-write verification, and automatic restore path. Prefer runtime patching/proxy DLL/injection when it is materially safer and easier to reverse.

## Native Windows and hook rules

Keep `DllMain` minimal and respect loader-lock constraints.

For DLLs, hooks, trampolines, and runtime patches, account for:

- x86/x64 and calling convention;
- register and stack preservation/alignment;
- thread safety and reentrancy;
- recursion through indirect API paths;
- COM lifetime/reference counting when applicable;
- hook installation/removal lifecycle;
- page protection changes and instruction-cache flushes;
- partially applied patch rollback.

A hook must preserve original semantics except for the intended behavioral change.

## Observability and experiments

When the target behavior cannot be reproduced in the current environment, continue autonomously with static analysis, tooling, parsers, signatures, fixtures, and diagnostic builds.

If a target-machine run is genuinely required, prepare one minimal reproducible experiment. Prefer one command/script/DLL that produces a self-contained `artifacts/run-*.zip` containing only safe-to-share metadata, logs, hashes, configuration, and requested dumps/captures.

Diagnostics should be structured, bounded, and cheap enough for their intended mode. Avoid per-frame filesystem I/O, allocations, global locks, expensive formatting, or stack walking in production patch mode.

## Reverse-engineering records

Substantial findings belong in the repository, not only in chat or a PR description.

Use:

- [`docs/re/`](./docs/re/) for durable knowledge such as target hashes, signatures, offsets, structures, call sequences, annotated disassembly, and supported-version notes;
- [`docs/experiments/`](./docs/experiments/) for reproducible experiments, including negative results;
- `tools/` and `scripts/` for reusable analysis, capture, patch, validation, and artifact-generation utilities.

Do not commit proprietary game binaries, copyrighted assets, private dumps, huge captures, secrets, or user data. Local raw artifacts belong under ignored paths such as `artifacts/`, `captures/`, and `binaries/`.

## Testing and claims

Test independent pieces even when the target binary cannot run in CI: pattern scanners, parsers, binary transforms, patch validation, configuration, synthetic PE fixtures, and artifact generation.

Do not claim target behavior was verified when only compilation or synthetic tests ran. State exactly which checks ran, on which binary/hash, and what still requires a target machine.

## Scope and safety

Keep patches small and task-specific. Do not turn a narrow compatibility/mod change into a general framework without a demonstrated need.

This project is for legitimate modification of software the maintainer is entitled to inspect. Do not add DRM/licensing bypasses, anti-cheat bypasses, cheats, credential theft, hidden persistence, or malware-like behavior.

## Pull requests

Use a focused branch and a concise imperative or conventional title.

A PR must be reviewable without chat history and should state:

- the roadmap item and goal;
- what was established experimentally;
- what remains a hypothesis;
- how the implementation or diagnostic works;
- supported binaries/hashes and fail-closed behavior;
- validation actually performed;
- target-machine validation performed, still required, or not applicable;
- install/remove/rollback behavior when relevant;
- roadmap and RE/docs updates;
- risks, unknowns, and deliberately out-of-scope follow-ups.

Use the repository PR template rather than replacing it with a generic summary.
