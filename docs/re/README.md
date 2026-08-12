# Reverse-engineering notes

This directory stores durable facts and well-supported models discovered while analyzing Ascendancy and the chosen modded target.

Do not store proprietary binaries here.

## What belongs here

Examples:

- target hashes and PE metadata;
- function/structure/vtable hypotheses with confidence labels;
- validated RVAs/offsets tied to exact hashes;
- signatures and the invariants used to disambiguate them;
- call sequences and state-transition diagrams;
- annotated disassembly excerpts kept short enough to be legally and practically reviewable;
- save-game format findings;
- patch sites and original bytes;
- compatibility notes between vanilla, official patches, and Antagonizer builds.

Use [`targets.md`](./targets.md) as the canonical supported-binary inventory.

Use [`static-analysis/t2/`](./static-analysis/t2/) for the T2 repo-safe canonical load/candidate handoff and [`../experiments/T2-static-analysis-bundle.md`](../experiments/T2-static-analysis-bundle.md) for its regeneration procedure and independent `wdump` evidence.

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
- RVA ...
- signature ...
- expected match count and invariants ...

## How this was established
- experiment link(s)
- tool/script and relevant command

## Unknowns / next experiment
- ...
```

Avoid invented semantic names. Prefer `sub_401230 (candidate planet update)` until evidence justifies renaming the concept.
