# Ascendancy reverse-engineering project index

This directory stores durable facts and well-supported models discovered while analyzing Ascendancy and the chosen modded target.

Do not store proprietary binaries here.

## What belongs here

Examples:

- target hashes and relevant container/LE metadata;
- function/structure hypotheses with confidence labels;
- validated addresses/offsets tied to exact hashes;
- signatures and the invariants used to disambiguate them;
- call sequences and state-transition diagrams;
- annotated disassembly excerpts kept short enough to be legally and practically reviewable;
- save-game format findings;
- patch sites and original bytes;
- compatibility notes between vanilla, official patches, and Antagonizer builds.

Use [`targets.md`](./targets.md) as the canonical supported-binary inventory.

Use [`static-analysis/t2/`](./static-analysis/t2/) for the T2 repo-safe canonical load/candidate handoff and [`../experiments/T2-static-analysis-bundle.md`](../experiments/T2-static-analysis-bundle.md) for its regeneration procedure and independent `wdump` evidence.

Use [`vanilla-antagonizer-diff.md`](./vanilla-antagonizer-diff.md) for the RE1 ranked differential handoff and [`../experiments/RE1-vanilla-antagonizer-differential-map.md`](../experiments/RE1-vanilla-antagonizer-differential-map.md) for the reproducible procedure, evidence boundaries, and negative results.

Use [`auto-management-ui-state.md`](./auto-management-ui-state.md) for the RE2/RE4 static-plus-runtime Managed UI/state model, [`../experiments/RE2-auto-management-ui-state-static.md`](../experiments/RE2-auto-management-ui-state-static.md) for its static recovery, and [`../experiments/RE4-runtime-ui-state.md`](../experiments/RE4-runtime-ui-state.md) for the two-planet runtime ownership/transition confirmation.

Use [`auto-management-turn-path.md`](./auto-management-turn-path.md) for the RE3 static per-turn state-gate/policy/action path and [`../experiments/RE3-static-turn-path.md`](../experiments/RE3-static-turn-path.md) for the reproducible byte-level evidence and bounded RE5 handoff.

Use [`m1-profile-state-representation.md`](./m1-profile-state-representation.md) for the A1 architecture decision boundary: the selected binary `+0x5a` compatibility mirror plus mod-owned profile identity, the exact evidence it relies on, and the still-open reuse-safe identity/lifetime requirement.

## Suggested note format

```markdown
# Topic

## Targets
- `<sha256>` — filename/version label

## Established facts
- `static`: ...
- `runtime`: ...

## Working hypotheses
- H1 ...

## Addresses / signatures
- address ...
- signature ...
- expected match count and invariants ...

## How this was established
- experiment link(s)
- tool/script and relevant command

## Unknowns / next experiment
- ...
```

Avoid invented semantic names. Prefer a neutral candidate label plus a parenthetical hypothesis until evidence justifies a semantic name.
