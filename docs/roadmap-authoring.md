# Roadmap authoring for autonomous work

`ROADMAP.md` is the live state of the project. It should let a coding/reverse-engineering agent choose one item, understand why it exists, execute it without rediscovering prior work, and leave the repository more informative even when the hypothesis is wrong.

The existing roadmap is intentionally still an initial sketch. When it is rewritten, prefer English for canonical roadmap items and durable technical documentation so tool output, symbol names, upstream references, and PRs share one language. Maintainer discussion may remain in any language.

## Status vocabulary

Use one of these statuses unless a task has a compelling reason to introduce another:

- **Open** — bounded work is ready to start.
- **Investigation first** — the next step is to answer a question, not implement a feature.
- **Blocked on target evidence** — the repository cannot settle the item without running the game on the target machine.
- **Partially implemented** — some scope shipped; the remainder is named explicitly.
- **Implemented, validation incomplete** — code exists but required target evidence is missing.
- **Completed and verified** — acceptance criteria are met with the required evidence.
- **Superseded** — replaced by another item; preserve the reason and link.
- **Dropped** — no longer worth doing or based on a disproved premise; preserve the reason.

## Priority model

Priority should describe consequence and sequencing, not enthusiasm.

A simple starting model is:

- **Critical** — game corruption/crash/data loss or the project cannot safely proceed.
- **High** — blocks the current milestone or a central investigation.
- **Medium** — meaningful correctness, robustness, tooling, or maintainability work.
- **Low** — cleanup or value not yet established.

Dependencies matter more than nominal priority. An investigation that unlocks three High items may be the correct next task even if it is Medium itself.

## Evidence vocabulary

Use the same vocabulary as `AGENTS.md`:

- `static`
- `runtime`
- `synthetic`
- `reported`
- `assumed`

Confidence should describe the premise, not the author's confidence in prose.

## Recommended item schema

Each active item should contain enough of the following fields to be actionable:

```markdown
### R1 — Identify the planet object and auto-management state

- **Status:** Investigation first
- **Priority:** High
- **Category:** Reverse engineering / planet state
- **Origin:** Initial milestone item 3
- **Depends on:** R0 target binary baseline
- **Problem / question:** What state changes when auto-management is toggled, and where is it stored?
- **Known evidence:**
  - `reported`: the game exposes an on/off auto-management control per owned planet.
- **Hypotheses:**
  - H1: a field in the planet object stores the mode directly.
  - H2: the UI queues a command and state changes later.
- **Next experiment:** Toggle the control while tracing writes to the selected planet candidate and compare before/after snapshots.
- **Expected information gain:** Distinguishes direct storage from deferred command handling and yields candidate write sites.
- **Proposed direction after evidence:** Not decided.
- **Compatibility / safety:** Read-only instrumentation first; no patching.
- **Validation / acceptance:** Record the owning object relationship, write site(s), exact target hash, and a reproducible way to observe the state transition.
- **Artifacts / docs:** `docs/re/planet-state.md`, `docs/experiments/R1-*.md`
- **Estimated scope:** Small/Medium
```

Not every item needs every field, but an agent should never have to invent the problem statement, evidence level, or completion condition.

## Investigation items vs implementation items

An investigation item should end with knowledge or a decision, not necessarily code. Its acceptance criteria should name what becomes known.

An implementation item should depend on established seams and state exactly which user-visible behavior changes, which binaries are supported, and what target validation is required.

Do not combine "find the state representation" and "ship a three-state patch" into one item. The first can invalidate the design assumptions of the second.

## Updating items from PRs

The PR that changes reality changes the roadmap.

Examples:

- an experiment confirms an offset only for one hash → record the hash and change confidence to `runtime`;
- a signature scanner makes the offset version-independent → update compatibility notes;
- a target run shows the premise is wrong → mark `Dropped` or rewrite the item;
- implementation lands but has not run in the game → `Implemented, validation incomplete`;
- a target-machine experiment verifies the acceptance criteria → `Completed and verified`.

Do not use checkboxes alone as status. Keep the evidence and reasoning that explain why the status is true.

## Milestones

A milestone should be an observable capability, not a collection of tasks.

For example, the current milestone can remain:

> For each player-owned planet, the UI can select Manual / Agricultural / Industrial and the chosen state remains correct for the current game session.

Its roadmap items should separately establish target compatibility, state representation, UI path, patch mechanism, storage, and validation.
