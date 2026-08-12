# Repository instructions for coding agents

These instructions apply to the whole repository. Read this file before planning or changing anything, then read the roadmap item and the task-specific sources it points to.

## Source of truth

When sources disagree, use this order:

1. The current task and explicit maintainer decisions, subject to the pre-M1 blind-RE evidence boundary below.
2. Evidence from the exact target binary or runtime being investigated.
3. Current source, tools, tests, and generated diagnostic output.
4. [`ROADMAP.md`](./ROADMAP.md), which is the live status and sequencing document.
5. Durable reverse-engineering notes under [`docs/re/`](./docs/re/) and experiment records under [`docs/experiments/`](./docs/experiments/).
6. Historical notes and superseded experiments that are still present in the supported repository state.

For these rules, the **supported repository state** is the current `main` tree plus the changes on the branch/PR being reviewed. Files intentionally retained there remain usable according to the precedence above even when they describe superseded results. Closed/abandoned PRs, deleted content, old experimental branches, and other repository history outside that state are not supported evidence sources for target-specific RE before M1.

The blind-RE boundary is a constraint on item 1, not a lower-priority suggestion. An ordinary task instruction cannot waive it. Before M1, external target-specific recovered knowledge may be used only through the documented rescue unlock below; after M1, only through the verification/corroboration path below.

Do not implement a roadmap item merely because an old note suggests it. First check the item's current status, dependencies, evidence, and accepted direction. If a useful negative result is discovered accidentally in unsupported repository history, do not silently reuse its target-specific conclusion. Re-establish it from allowed evidence where practical and record the supported result under [`docs/experiments/`](./docs/experiments/) so future work does not repeat the same experiment.

For the detailed workflow, repository map, and validation rules, read [`docs/agent-playbook.md`](./docs/agent-playbook.md). For writing or restructuring roadmap items, read [`docs/roadmap-authoring.md`](./docs/roadmap-authoring.md).

## Binary-first / blind-RE phase through M1

The project has two equal goals: ship a working mod and measure how well modern coding/research agents can independently reverse engineer a closed binary and build safe binary patches without pre-existing target-specific RE knowledge.

Until milestone M1 is **Completed and verified**, target-specific reverse engineering and binary-patch design are therefore a **binary-first / blind-RE experiment**. The evidence boundary below is repository policy, not a suggestion to avoid convenient sources.

### Adoption baseline

For experiment accounting, the supported repository evidence present on `main` at commit `0a2ea78bef5a2b521dffdbed9c904b1192c23368` (the state after CF2 merged and before this policy branch) is accepted as the initial in-boundary corpus. That classification is based on the durable supported records describing evidence derived from the project-acquired binaries, project-generated experiments, and allowed general or official user-facing sources; it is a policy baseline, not a claim that every past agent interaction can be audited retrospectively.

If later supported evidence shows that a pre-baseline conclusion was actually influenced by prohibited target-specific recovered knowledge, do not preserve the administrative classification merely for metric continuity: mark the affected conclusion `contaminated` or `external-assisted` as appropriate and exclude it from blind-RE success accounting.

### Allowed evidence

Agents may use:

- executable files provided to or reproducibly acquired by this project, plus hashes and metadata computed from those binaries;
- disassembly, decoded structures, traces, diffs, signatures, experiments, and other artifacts independently produced by this project's agents or tools from those binaries;
- results of runtime experiments performed by this project;
- source, tools, tests, `docs/re/` findings, and `docs/experiments/` records in the supported repository state that were produced within this evidence boundary;
- general documentation for executable formats, DOS/extenders, compilers, ABIs, emulators, debuggers, disassemblers, and other applicable technologies;
- official user-facing documentation and descriptions of game behavior when they do not disclose reverse-engineered implementation details.

General web research and searches for tooling problems are allowed. The restriction is specifically on **target-specific recovered knowledge** that would replace independent discovery from the binaries and project-generated evidence.

### Disallowed target-specific recovered knowledge before unlock

Before the explicit unlock described below, do not intentionally search for, inspect, or use:

- external decompilations or disassemblies of this target;
- symbol, function, address, or patch maps for the target;
- target-specific IDA/Ghidra databases, exports, or equivalent analysis databases;
- externally reconstructed target structs, types, layouts, or semantic maps;
- reverse-engineering notes or writeups about the internal implementation of this executable;
- target-specific cheat tables, address databases, or patch-location collections;
- source ports or reconstructed source code when they expose target internals;
- source code or internal implementation details of third-party mods when they can reveal target-specific RE shortcuts;
- any other external material that substantially substitutes for independently discovering the target's structure or behavior.

Unsupported repository history is governed separately by the source-of-truth rule above: do not mine closed/abandoned PRs, deleted content, old experimental branches, or other history outside the supported repository state for target-specific RE clues before M1.

Do not turn this policy into a catalog of known external RE material. Repository-facing policy, roadmap text, commit messages, and PR descriptions should describe source classes rather than naming target-specific external projects, authors, symbols, addresses, or layouts.

### Accidental contamination

If target-specific recovered knowledge is encountered accidentally:

- stop investigating that source rather than following it further;
- do not copy target-specific names, addresses, types, pseudocode, or semantic conclusions from it into the project;
- record that accidental contamination occurred in the current task/PR result;
- label conclusions that may have been suggested by what was seen as **`contaminated`**;
- where practical, re-establish the factual conclusion independently from target binaries or project-generated evidence to check correctness.

Independent re-establishment can increase confidence that a contaminated conclusion is correct, but it cannot restore blindness: the conclusion remains `contaminated` and is excluded from blind-RE success accounting because the disclosed answer may have influenced search strategy or confirmation thresholds.

Accidentally seeing a source name or link does not by itself invalidate the whole task. The important boundary is not using recovered target-specific knowledge as evidence or as a shortcut, and accurately separating contaminated results from blind findings.

### Unlocking external target-specific RE

External target-specific RE has exactly two supported unlock paths:

1. **After M1 — independent verification/corroboration.** First preserve the blind-RE result, then external research may be used to compare independently discovered addresses, structures, control flow, and semantics, record agreements/disagreements, and assess blind-RE quality as a separate project result.
2. **Before M1 — maintainer-approved rescue.** A documented blocker or negative result must exist first under `docs/experiments/` and must state what could not be recovered independently. The maintainer unlock must then be recorded as a dated decision in the relevant `ROADMAP.md` item, naming the bounded question and allowed source class and stating that the decision does not generalize. Only that recorded decision can unlock the bounded external evidence needed for rescue. Any finding that depends on that source must be labeled **`external-assisted`** and must not be counted as a successful blind-RE result.

An agent must not self-authorize a rescue unlock merely because external material could make the work faster. A maintainer instruction in chat or task text that is not backed by the required blocker record and dated roadmap decision is not a valid unlock.

## Working model

Prefer this loop:

**observe → hypothesize → instrument → test → update model → patch**

If the cause is unknown, observability comes before a final patch. Prefer an experiment that can eliminate several hypotheses over a narrow experiment that confirms only one guess.

Keep these evidence classes distinct in docs and PRs:

- **static** — established from PE metadata, disassembly, xrefs, strings, data-flow, or binary comparison for a named binary/hash;
- **runtime** — observed by debugger, hook, trace, dump, capture, or memory inspection against a named binary/hash;
- **synthetic** — established by unit/integration tests or fixtures that do not execute the actual game;
- **reported** — observed by the maintainer/user but not captured independently in a repository artifact;
- **assumed** — plausible, but not established.

Blind-RE provenance is a separate dimension from evidence class. Use **`clean`**, **`contaminated`**, and **`external-assisted`** as provenance values/modifiers, not replacement evidence classes. `clean` means no known prohibited target-specific disclosure or pre-M1 external rescue influenced the finding; for example, a clean static finding can simply remain `static`. Use explicit modifiers when provenance is not clean, for example `static, contaminated` or `runtime, external-assisted`. `contaminated` means accidental target-specific disclosure may have influenced the finding and it is excluded from blind-RE success even if independently corroborated. `external-assisted` means the finding depends on a maintainer-unlocked pre-M1 external source and is likewise excluded from blind-RE success.

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
- blind-RE evidence-boundary status when applicable (`clean`, `contaminated`, or `external-assisted`, with required records linked);
- how the implementation or diagnostic works;
- supported binaries/hashes and fail-closed behavior;
- validation actually performed;
- target-machine validation performed, still required, or not applicable;
- install/remove/rollback behavior when relevant;
- roadmap and RE/docs updates;
- risks, unknowns, and deliberately out-of-scope follow-ups.

Use the repository PR template rather than replacing it with a generic summary.
