# Ascendancy project-local agent policy

## Blind-research gate and experiment accounting

The binary-first / blind-research gate remains active until milestone **M1** is `Completed and verified` in `ROADMAP.md`.

For blind-experiment accounting, the supported repository evidence present on `main` at commit `0a2ea78bef5a2b521dffdbed9c904b1192c23368` is the accepted adoption baseline. This is an administrative evidence baseline, not a claim that every pre-baseline interaction can be retrospectively audited. If later supported evidence shows that a pre-baseline conclusion was influenced by prohibited target-specific recovered knowledge, mark the affected conclusion `contaminated` or `external-assisted` as appropriate and exclude it from blind-RE success accounting.

While M1 is active, the supported repository state is current `main` plus the branch/PR under review. Do not mine closed/abandoned PRs, deleted material, old experimental branches, or unsupported history for target-specific recovered knowledge. An ordinary task or chat instruction does not waive the gate.

A pre-M1 external rescue is valid only after both of these are durable:

1. a concrete blocker or negative result under `docs/experiments/`; and
2. a dated maintainer decision in the relevant `ROADMAP.md` item naming the bounded question and allowed source class and stating that the exception does not generalize.

Findings that depend on such a rescue remain `external-assisted`. A generic operator-provided tool/artifact that contains no target-specific recovered knowledge is a normal capability handoff; material that embeds target-specific recovered knowledge is subject to the rescue gate instead.

Repository-facing policy and roadmap text should describe prohibited external source classes rather than turning the project into a catalog of target-specific external RE projects, authors, symbols, addresses, or layouts.

## Ascendancy roadmap conventions

Use English for canonical roadmap items and durable technical documentation so tool output, symbol names, upstream references, and PRs share one language. Maintainer discussion may use any language.

Priority describes consequence and sequencing, not enthusiasm:

- `Critical` — corruption/crash/data loss or the project cannot safely proceed;
- `High` — blocks the current milestone or a central investigation;
- `Medium` — meaningful correctness, robustness, tooling, or maintainability work;
- `Low` — cleanup or value not yet established.

Dependencies outrank nominal priority. A lower-priority investigation that unlocks several higher-priority items can be the correct next task. Milestones should describe an observable capability rather than merely a collection of tasks.

Blind-RE provenance (`clean`, `contaminated`, `external-assisted`) is separate from evidence class (`static`, `runtime`, `synthetic`, `reported`, `assumed`).

## Scope and safety boundary

This project is for legitimate modification of software the maintainer is entitled to inspect. Do not add DRM/licensing bypasses, anti-cheat bypasses, cheats, credential theft, hidden persistence, or malware-like functionality. Diagnostic investigation of compatibility mechanisms is acceptable only when it does not create a bypass.
