# RE1 — vanilla ↔ Antagonizer differential-map experiment

Date: 2026-08-13  
Roadmap item: RE1  
Blind-RE provenance: **clean**  
Evidence class: **static** unless stated otherwise.

## Question

Which unresolved code regions in the canonical English Antagonizer ↔ bug-patch differential deserve priority for RE2/RE3, after preserving reference-only and constant-only changes instead of masking them away, and which leads repeat in the International pair?

## Inputs

The experiment used only project/operator-supplied, hash-pinned executables and the supported repository toolchain. No external target-specific recovered knowledge, unsupported repository history, or rescue unlock was used.

- `ANTAG_EN.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.
- `PATCH_EN.EXE` — 587451 bytes — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`.
- `ANTAG_INTL.EXE` — 610863 bytes — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`.
- `PATCH_INTL.EXE` — 587451 bytes — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

The exploratory run used GNU `objdump` 2.44 for flat i386 disassembly. Clean-checkout validation below used GNU `objdump` 2.42 from the hosted Ubuntu runner. The supplied Open Watcom toolkit had already passed its own `verify.sh`; RE1 does not depend on `wdump` beyond T2's completed load-map cross-check.

## Procedure

1. Verify all four target filenames, sizes, and SHA-256 values.
2. Regenerate `le_disasm` v2 code inventories for all four binaries.
3. Compare EN Antagonizer↔patch, INTL Antagonizer↔patch, and both EN↔INTL locale pairs with the same conservative order as `tools/le_diff.py`: exact → reference-only → constant-only → structural.
4. The generator imports `tools/le_diff.py` and reuses its current `validate_inventory()` plus `match_pass()` sequence directly. This keeps the machine map on the same conservative model rather than creating an independent, looser similarity matcher.
5. Separately, reconstruct code/data objects with `tools/le_image.py`. Scan the data object for embedded `..\planet.cpp`, `..\planwin.cpp`, and `..\psqwin.cpp` substrings, then count only code references having the observed source-diagnostic shape `mov edx,<data-object-relative source offset>` followed within four decoded instructions by a call. This avoids treating an unrelated immediate equal to a string offset as an xref.
6. For every English unresolved Antagonizer candidate, record class, size, incoming caller count, and cross-locale same-class corroboration only when the candidate-level address correspondence is unambiguous. Aggregate `le_diff` matching remains a multiset operation; for address identity, RE1 additionally requires the signature used at that exact/reference-only/constant-only stage to occur exactly once on both sides among candidates still eligible at that stage. Duplicate signatures remain unmapped instead of inheriting list-order `zip` pairings.
7. Source-diagnostic proximity and direct graph adjacency are separate static observations documented below; they are not synthesized into the machine map as facts.
8. Inspect the highest-information structural and literal-retune leads manually. Structural baseline counterparts below are **heuristic alignments**, not identities: they were selected by high instruction-shape similarity plus matching local context, and remain hypotheses because `le_diff` intentionally does not invent fuzzy matches.

Repository command after this PR:

```sh
python3 scripts/generate_re1_diff_map.py \
  --binaries binaries \
  --repo-output artifacts/re1-diff-map/candidate-map.json
```

Full inventories and the machine-readable candidate map remain under ignored `artifacts/re1-diff-map/` by default. The durable ranked interpretation is this experiment record plus `docs/re/vanilla-antagonizer-diff.md`; no bulk target disassembly or strings are committed.

## Reproduced baseline

The regenerated inventory/differential counts exactly reproduce CF2/T2:

- EN product: `72 exact / 613 reference-only / 525 constant-only / 116 Antagonizer structural / 87 patch structural`.
- INTL product: `72 / 611 / 520 / 123 / 93`.
- Antagonizer EN↔INTL: `114 / 1107 / 46 / 59 / 59`.
- Patch EN↔INTL: `114 / 1076 / 56 / 51 / 50`.

The four regenerated headline inventories also reproduce T2: EN Antagonizer `144696` decoded instructions / `1326` candidate starts / `7472` direct in-object call sites / `4259` call edges, and EN patch `139093 / 1297 / 7251 / 4162`.

## Clean-checkout validation

GitHub Actions run `31662170747` validated PR head `4c1e09d7c9ed37306c59e67af09f907ef9edb607` through merge ref `4be68271663e73e5c01b94351bd308ec793a870c` before this documentation-only correction was committed:

- the network-free unit job ran **233 tests** and finished `OK`;
- the dedicated `RE1 real-target differential map` job fetched and verified all four pinned executable hashes, regenerated the four inventories, enforced the four expected conservative diff-count tuples, and completed `RE1 differential map: PASS (1254 EN unresolved candidates)`;
- the real-target job reported `564/613` reference-only, `450/525` constant-only, and `66/116` structural EN candidates as cross-locale corroborated under the unambiguous address-mapping rule;
- the existing CF2 real-target, CF3 demo-acquisition, and CF3 debugger jobs also remained green;
- Documentation run `31662170856` succeeded on the same implementation head.

This is target-byte **static** validation only. RE1 does not claim that the game executed or that any candidate's runtime semantics were confirmed.

## Established observations

### A dense `planet.cpp`-anchored change cluster exists

The exact source-path byte substring `..\planet.cpp` occurs 28 times in the Antagonizer data object and 26 times in the patch data object in both locales. The stricter source-diagnostic xref shape resolves all 28 Antagonizer occurrences and all 26 patch occurrences.

In English, all 28 Antagonizer `planet.cpp` diagnostic xrefs fall into candidate regions between `0x33af0` and `0x370b8`; the corresponding patch anchors fall between `0x33210` and `0x359e8`. This establishes a bounded compilation-unit-proximity cluster. It does **not** establish that every region in the interval is one C++ function or that every change is self-management behavior.

The Antagonizer cluster includes all three unresolved classes. Examples:

- constant-only: `0x33af0→0x33210`, `0x33d30→0x33450`, `0x35a70→0x34b5c`, `0x35b04→0x34bf0`, `0x366c8→0x34ffc`, `0x3676c→0x350a0`, `0x36cd4→0x35604`, `0x370b8→0x359e8`;
- structural: `0x352e0`, `0x363b0`, `0x364b4`, `0x36a5c`;
- nearby reference-only/call-graph hubs include `0x34b0c→0x33cd8`-class relocation mapping and `0x35930` (36 incoming callers in the Antagonizer inventory).

The structural addresses above also repeat as Antagonizer-side structural changes in the International product comparison when their locale mapping is available.

### Structural lead `0x34e70` has a material inserted block

Antagonizer candidate `0x34e70` is structural, 1136 attributed bytes, with 12 incoming direct-call sites. It has no direct `planet.cpp` source-path xref, but it is directly connected to several anchored candidates. A high-similarity local alignment with patch structural candidate `0x34034` has the same caller count and an instruction-shape similarity of about 0.82.

The alignment contains a contiguous Antagonizer-only block of roughly 42 decoded instructions near the end of the candidate. The added block reads/writes fields from the same EAX/EBX-relative object family already used by the surrounding shared code and performs x87 arithmetic before returning to the common tail. This is a material structural delta, not a moved branch target. Exact object-field semantics remain unknown.

### Structural lead `0x352e0` removes/reworks baseline logic

Antagonizer candidate `0x352e0` is structural, 1372 attributed bytes, with 3 incoming callers and two `planet.cpp` diagnostic anchors. A high-similarity local alignment with patch structural candidate `0x343f8` is about 0.81 by instruction shape and preserves a long sequence of common object-relative accesses and corresponding calls.

One concrete delta is a patch-only block immediately after a shared diagnostic region. The patch reads a relocated global byte, compares it with byte `[esi+0x57]`, checks another global, conditionally tests a small count, and may increment word `[esi+0x50]`. The Antagonizer omits that block and proceeds directly into the following arithmetic on `[esi+0x44]`, `[esi+0x50]`, and `[esi+0x52]`. Later code in both candidates continues to touch `[esi+0x54]`, `[esi+0x57]`, `[esi+0x10]`, and neighboring fields.

This establishes changed logic over a consistent object-relative field family. Calling convention, object identity, and whether the block is self-management are not established by RE1.

### Constant-only lead `0x3676c→0x350a0` contains a real numeric retune

This same-shape candidate is 752 attributed bytes, has 6 incoming callers, a `planet.cpp` diagnostic anchor, and repeats in the International pair. Most operands move as expected with code/data layout, but one literal is not an address relocation:

- patch `0x350a0` path: `0x42800000` = IEEE-754 `64.0`;
- Antagonizer `0x3676c` path: `0x44a00000` = IEEE-754 `1280.0`.

The same candidate first computes an x87 distance-like magnitude from three floating components, adds a data constant `-3200.0`, compares against a data constant that also changes `64.0→1280.0`, and uses the same changed value as a fallback before a later call. The International pair reproduces both values exactly.

The arithmetic context makes this a high-value *numeric-policy/geometry* lead, but RE1 does not decide which. Calling it an AI threshold would exceed the evidence.

### Some high-ranked regions are likely infrastructure/lookup seams rather than the changed policy itself

`0x35a70→0x34b5c` is only 148 attributed bytes but has 26 incoming callers and a `planet.cpp` anchor; `0x35930` has 36 incoming callers. Their high centrality makes them useful traversal points for RE2/RE3, but their changed operands are dominated by relocation/source-diagnostic movement rather than obvious new logic. They should be used as graph seams, not automatically treated as Antagonizer-specific behavior.

### UI-proximate code is visible but remains secondary for RE1

The data object contains shared `..\planwin.cpp` / `PLANETALLOC` / `PLANLIST` / `PLSQUARE` / `PLRES` / `PLIND` / `PLPRO` / `PLPOP` / `PLBUILD` anchors in both products. A very large constant-only candidate begins at Antagonizer `0x373e0` (patch `0x35d10`, 8112 attributed bytes). Because candidate starts are direct-call-derived, this size is strong evidence of boundary folding rather than an 8 KiB verified function. It is a useful RE2 UI-proximity lead, not a confirmed UI handler.

`PLIND` is shared baseline text and must not be interpreted as the new M1 “Industrial” profile.

## Cross-locale narrowing

The generated triage pass traverses all English unresolved Antagonizer candidates before ranking. Candidate-level address correspondence is deliberately stricter than `le_diff`'s aggregate multiset matching: a locale/product address pair is accepted only when its current-stage signature is unique on both sides. Duplicate-signature pairs remain unmapped.

Under that rule:

- 564/613 reference-only English pairs reproduce as the same reference-only product pair in the International build;
- 450/525 constant-only English pairs reproduce as the same constant-only product pair;
- 66/116 Antagonizer-side English structural candidates have a recoverable unambiguous EN→INTL Antagonizer mapping whose International candidate is also structural.

The machine report records why mappings were withheld: Antagonizer EN↔INTL has 45 ambiguous reference-only pair instances; patch EN↔INTL has 45; INTL Antagonizer↔patch has 45 ambiguous reference-only and 67 ambiguous constant-only pair instances at the address-mapping layer.

**Correction of an earlier RE1 draft result:** the first pass reported `609/613` reference-only and `517/525` constant-only because it consumed the deterministic `zip` pairing produced by multiset matching as if list order established address identity. That pairing is valid for aggregate bucket counts but is not evidence for a particular candidate correspondence. Those two candidate-level counts are superseded by `564/613` and `450/525`. The four aggregate differential tuples, the `planet.cpp` cluster, and all ranked Tier-1 leads are unchanged; the Tier-1 leads remain corroborated under the stricter mapping.

The lower structural corroboration count is partly a mapping limitation: a region that is structural in both locale comparisons may have no exact/reference/constant locale pair from which to derive an address correspondence. More generally, an omitted ambiguous mapping means **not corroborated by this method**, not “locale-specific.”

## Negative results

- String search does not expose a useful `self-management`, `automation`, `governor`, or equivalent semantic anchor. The only `manage*` hit in the printable indexes is `Could not initialize instrument manager`, present in both products and unrelated to planet management.
- Reference-only is still mostly relocation-heavy. Cross-locale reproduction confirms build-transform stability, not behavioral relevance.
- Most inspected constant-only `planet.cpp` candidates differ primarily in source-diagnostic line/file operands, data offsets, code targets, or relocated globals. The `64.0→1280.0` case is notable precisely because it survives those explanations.
- Large structural candidates are not function counts. `0x373e0` and other multi-kilobyte spans demonstrate direct-call-boundary folding.
- Source-path diagnostics establish compilation-unit proximity only. They do not reveal C++ symbol names, object types, calling convention, or self-management semantics.
- Duplicate normalized signatures are not sufficient evidence for cross-locale address identity; RE1 now preserves them as unmapped rather than selecting an arbitrary counterpart.

These negative results are preserved so RE2/RE3 do not restart from broad string search, treat every middle-bucket change as AI behavior, or reuse ambiguous signature pair order as an address map.

## Interpretation and handoff

The strongest RE1 static leads for subsequent bounded tracing are:

1. `0x34e70` structural hub — substantial inserted logic, 12 callers, graph-connected to `planet.cpp` anchored regions; likely patch counterpart `0x34034` remains a heuristic alignment.
2. `0x352e0` structural anchored region — material removal/rework over a stable object-relative field family; likely patch counterpart `0x343f8` remains a heuristic alignment.
3. `0x3676c→0x350a0` constant-only anchored region — reproducible `64.0→1280.0` non-address numeric retune in x87 context.
4. `0x35a70→0x34b5c`, `0x35930`, and `0x366c8→0x34ffc` — central call/data seams useful for following the candidate cluster without claiming they implement policy.
5. `0x373e0→0x35d10` — UI-proximate `planwin.cpp` folded span for RE2 only; lower semantic confidence.

RE1 deliberately stops here. Establishing the UI/state seam, calling convention, per-turn decision path, or runtime semantics belongs to RE2/RE3 and later tasks.
