# Vanilla ↔ Antagonizer differential map

## Targets

Canonical M1 comparison:

- `ANTAG_EN.EXE` — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` — 610863 bytes.
- `PATCH_EN.EXE` — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` — 587451 bytes.

Cross-locale corroboration only:

- `ANTAG_INTL.EXE` — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`.
- `PATCH_INTL.EXE` — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

Blind-RE provenance: **clean**. Findings here are `static`; no target-specific external recovered knowledge was used.

## What the map means

`tools/le_disasm.py` candidate starts are linear-sweep/direct-call analysis regions, not verified functions. Addresses below identify exact candidate regions for the named hashes. A structural region without a `le_diff` match is never silently assigned a baseline identity.

RE1 preserves all four conservative comparison classes:

- exact: 72 EN;
- reference-only: 613 EN;
- constant-only: 525 EN;
- structural: 116 Antagonizer-side / 87 patch-side EN.

The International product pair is `72 / 611 / 520 / 123 / 93` and is used only to corroborate repeated changes.

The reproducible procedure, cross-locale accounting, negative results, and short disassembly observations are in [`../experiments/RE1-vanilla-antagonizer-differential-map.md`](../experiments/RE1-vanilla-antagonizer-differential-map.md). `scripts/generate_re1_diff_map.py` regenerates a compact machine-readable candidate map by reusing the exact validated matching passes from `tools/le_diff.py`; the full report stays under ignored `artifacts/` by default.

## Ranked candidate map

### Tier 1 — strongest changed-planet-region leads

**`ANTAG_EN 0x34e70` — structural — 1136 attributed bytes — 12 callers.**  
Cross-locale: corroborated. `planet.cpp` relationship: direct graph neighbor of anchored changed regions. A heuristic local alignment to patch `0x34034` has high instruction-shape similarity and the same caller count. The Antagonizer side contains a contiguous ~42-instruction addition with object-relative accesses and x87 arithmetic. **Confidence:** high that this is materially changed code in the planet compilation neighborhood; low on exact behavior/function identity.

**`ANTAG_EN 0x352e0` — structural — 1372 bytes — 3 callers — two `..\planet.cpp` diagnostic anchors.**  
Cross-locale: corroborated. Heuristic local alignment to patch `0x343f8` preserves a long common field/call sequence but differs materially: a baseline block that conditionally checks globals and may increment `[esi+0x50]` is absent/reworked in Antagonizer before both paths converge on operations involving `[esi+0x44]`, `[esi+0x50]`, `[esi+0x52]`, `[esi+0x54]`, `[esi+0x57]`, and `[esi+0x10]`. **Confidence:** high for a changed object-update routine candidate; self-management semantics unconfirmed.

**`ANTAG_EN 0x3676c → PATCH_EN 0x350a0` — constant-only — 752 bytes — 6 callers — `..\planet.cpp` anchor.**  
Cross-locale: corroborated. A non-address literal and the corresponding data comparison constant change from IEEE-754 `64.0` (`0x42800000`) to `1280.0` (`0x44a00000`) while the surrounding instruction shape remains stable. The context computes an x87 three-component magnitude, adds `-3200.0`, compares it with the changed value, and passes a bounded result onward. **Confidence:** high that this is a genuine numeric retune; low on whether it is policy, geometry, or another planet-related calculation.

### Tier 2 — traversal seams inside the same anchored cluster

**`0x35a70 → 0x34b5c` — constant-only — 148 bytes — 26 callers — three `planet.cpp` anchors.**  
High centrality but inspected operand differences are dominated by relocation/diagnostic movement. Use as a traversal/lookup seam; **do not** infer that it is the changed policy.

**`0x35930` — reference-only — 56 bytes — 36 callers.**  
High-centrality neighbor used by Tier-1 changed candidates. Useful for call-graph expansion in RE2/RE3; semantic confidence low.

**`0x366c8 → 0x34ffc` — constant-only — 164 bytes — 7 callers — `planet.cpp` anchor.**  
Called from `0x3676c` and nearby anchored code. Current changes are mostly relocation/source diagnostics. Useful seam, not a confirmed behavior.

**`0x36cd4 → 0x35604` — constant-only — 876 bytes — 2 callers — three `planet.cpp` anchors.**  
Cross-locale reproduced; no equally distinctive literal/structural delta found in RE1. Secondary candidate.

### Tier 3 — UI-proximity / boundary leads

**`0x373e0 → 0x35d10` — constant-only — 8112 attributed bytes — `..\planwin.cpp`/planet-window resource neighborhood.**  
The size is a warning that indirect-only callees are folded into the candidate; treat it as a region, not an 8 KiB function. Shared resource tags include `PLANETALLOC`, `PLANLIST`, `PLSQUARE`, `PLRES`, `PLIND`, `PLPRO`, `PLPOP`, and `PLBUILD`. This is a bounded RE2 UI lead, not evidence of self-management behavior. In particular, shared baseline tag `PLIND` is **not** evidence for the new M1 Industrial profile.

## Cluster boundaries and call relationships

The strict source-diagnostic shape finds all 28 Antagonizer `..\planet.cpp` data-string occurrences as code xrefs, versus 26 in the patch. In English they fall into Antagonizer candidate regions `0x33af0..0x370b8` and patch regions `0x33210..0x359e8`.

Useful internal relationships in the Antagonizer inventory include:

- `0x33af0` calls `0x33d30` and structural hub `0x34e70`;
- reference-only `0x34b0c` (19 callers) calls `0x34e70` multiple times plus `0x35a70` and `0x366c8`;
- `0x34e70` has 12 incoming callers;
- `0x352e0` calls `0x34e70`, `0x35930`, `0x35a70`, and `0x366c8` among other neighbors;
- `0x35a70` has 26 incoming callers and `0x35930` has 36;
- `0x36a5c` and `0x36cd4` both call back into the same central cluster.

These relationships justify investigating a bounded cluster instead of 1254 unresolved EN candidates independently.

## Cross-locale support

Using only conservative exact/reference/constant locale mappings:

- 609/613 EN reference-only pairs reproduce as reference-only in the International product pair;
- 517/525 EN constant-only pairs reproduce as constant-only;
- 66/116 EN Antagonizer structural regions have a recoverable locale mapping and are structural on the International product side.

The structural denominator is mapping-limited; lack of a locale map is not evidence that a structural change exists only in English.

## Negative findings

- No useful printable `self-management`, `automation`, or `governor` semantic anchor was found. The only `manage*` hit is shared `Could not initialize instrument manager`.
- Most reference-only changes are relocation-heavy even when cross-locale-stable.
- Most inspected constant-only planet candidates are explained by source-diagnostic line/file movement, DS-relative layout shifts, globals, or call/branch relocation. The `64.0→1280.0` retune is a notable exception, not permission to interpret the whole bucket as policy constants.
- Multi-kilobyte structural/constant spans demonstrate candidate-boundary folding and must not be counted as changed functions.
- `planet.cpp`/`planwin.cpp` anchors establish compilation-unit proximity, not C++ symbols, object types, ABI, or behavior.

## Handoff hypotheses

- **H1 (high static priority):** `0x34e70` and `0x352e0` lie on a materially changed planet-state/update path worth using as RE3 traversal seeds. The exact semantic role remains unknown.
- **H2 (medium-high):** `0x3676c` contains an intentional Antagonizer numeric retune relevant to planet-associated behavior; runtime/context tracing must decide whether that behavior is automation, geometry, or something else.
- **H3 (medium):** high-caller seams `0x35a70`, `0x35930`, and `0x366c8` can connect state/UI or turn-path callers to the changed cluster even if the seams themselves are mostly unchanged logic.
- **H4 (medium, RE2-specific):** the folded `0x373e0` planet-window region is a useful static UI neighborhood for finding the existing self-management control, but RE1 has not identified the handler or state field.

No hypothesis above is a confirmed function name or behavior. RE2 must establish calling convention before interpreting arguments, and RE2/RE3 own the UI/state and per-turn semantic tracing respectively.
