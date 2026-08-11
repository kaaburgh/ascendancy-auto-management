# Ascendancy Auto-Management Roadmap

This file is the live backlog, sequencing source, and execution-environment contract for the project.

The roadmap is intentionally written so a capable coding/reverse-engineering agent can select one bounded item, complete it without chat history, and leave enough durable evidence for the next agent. See [`AGENTS.md`](./AGENTS.md) for repository-wide rules and [`docs/agent-playbook.md`](./docs/agent-playbook.md) for the detailed RE workflow.

Canonical roadmap items and durable technical documentation are written in English so symbols, tool output, scripts, PRs, and handoffs use one language.

---

## Product direction

Add specialized automatic management for player-owned planets. A planet should eventually support profiles such as **Agricultural**, **Industrial**, **Scientific**, and other useful strategic modes. Each profile will define priorities for construction, tile development, and resource optimization, and the selected profile will make decisions every turn until the player changes it or returns to manual control.

The project deliberately starts with a smaller integration milestone before implementing differentiated policies.

## Milestone M1 — selectable automation profiles

> For every player-owned planet, the UI can select **Manual / Agricultural / Industrial**, and the selected mode remains correct for the current game session.

For M1:

- `Manual` must preserve normal manual control.
- `Agricultural` and `Industrial` may use the same existing self-management behavior; their policy algorithms do not need to differ yet.
- The mode is per planet, not global.
- Switching between the three modes must be safe and reversible during a running game.
- Save-game persistence of the new profile distinction is **not** required.
- `Scientific` and additional profiles are **not** required.
- Differentiated Agricultural/Industrial build decisions are **not** required.

M1 is complete only after the behavior is observed on the canonical target executable, not merely compiled or validated synthetically.

---

## Execution-environment contract

Cloud-first development is a project requirement. Do not mark a task local-only merely because reverse engineering, DOS execution, debugging, or UI validation traditionally happens on a workstation.

Every active task has one execution classification:

- **CLOUD** — Codex or Claude cloud may take and complete the task.
- **CLOUD RESEARCH** — Codex or Claude cloud may take the task. Its purpose is to determine whether a named gated step can be executed reproducibly in cloud infrastructure.
- **GATED** — no agent should take the task yet. A named CLOUD RESEARCH item must first change it to either `CLOUD` or `LOCAL ONLY` and document how it is executed.
- **LOCAL ONLY** — cloud agents must not take the task. This classification is valid only after a cloud-feasibility investigation records the concrete blocker.

### Required outcome of a CLOUD RESEARCH task

A cloud-feasibility investigation is not complete with a prose opinion such as “probably needs Windows” or “DOSBox should work.” It must modify this roadmap and produce one of these outcomes for every gated task it owns:

1. **Cloud path found**
   - change the gated task to `Execution: CLOUD`;
   - add or reference reproducible setup/scripts/configuration;
   - state what a clean Codex/Claude environment needs to run it;
   - add at least a smoke test for the cloud path where practical.

2. **Cloud path not practical**
   - change the gated task to `Execution: LOCAL ONLY`;
   - document the exact blocker and what was tried;
   - prepare the smallest possible one-shot local procedure/script;
   - define the repo-safe artifact produced by that local run;
   - ensure the next analysis/implementation step consuming that artifact is a `CLOUD` task wherever possible.

A feasibility task must prefer automation over manual instructions and must preserve negative results under `docs/experiments/` when they would prevent repeated work.

### Rules for cloud agents selecting work

A cloud agent may select an item only when:

- `Status` is `Open` or `Investigation first`;
- `Execution` is `CLOUD` or `CLOUD RESEARCH`;
- every dependency is completed with the required evidence;
- no newer roadmap decision invalidates the item.

A cloud agent must **never** select a `GATED` or `LOCAL ONLY` item. It may improve scripts or documentation around a local-only item only if that is itself a separate CLOUD task.

---

## Target strategy and current assumptions

The intended production target is the **Antagonizer** executable because the project wants to extend its existing planetary self-management rather than rebuild vanilla AI behavior. T1 selected the exact English Antagonizer build as the canonical M1 production target and the English official bug-patch build as the canonical differential baseline.

### Established by CF1/T0/T1 (static / reported)

- The Antagonizer is a **standalone complete game executable** (`ANTAG.EXE`), copied beside the retail `ASCEND.EXE` and run instead of it. It is not a patcher, not a data file, and not stacked on top of a base executable.
- The publisher's official bug patch has the same shape: `PATCH.EXE` (version 1.6.5, English) and `F_PATCH.EXE` (version 1.8.5, non-English) are also standalone full builds.
- Both were distributed free of charge by The Logic Factory and are lawfully fetchable in cloud; the retail game **data** files are not.
- Canonical M1 target: `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes.
- Canonical comparison baseline: `PATCH_EN.EXE`, SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`, 587451 bytes; publisher-documented version 1.6.5.
- Container format on the canonical pair: DOS `MZ`, Linear Executable (`LE`) image at `e_lfanew = 0x2a50`, Intel 80386 LE CPU type, bound DOS/4G-family runtime evidence. Not PE.
- T1 strongly supports direct build-lineage comparability between the Antagonizer and bug-patch families: the same locale-layout delta and the same Antagonizer↔bug-patch object/string-anchor transformation repeat in English and International pairs. Exact source-control revision identity is not proven.
- The International pair remains cross-locale corroboration/future compatibility input, not M1 support.

### Established by CF2 (static; final clean-checkout gate pending)

Full detail in [`docs/re/targets.md`](./docs/re/targets.md), [`docs/experiments/CF2-cloud-static-re.md`](./docs/experiments/CF2-cloud-static-re.md), and [`docs/experiments/CF2-real-target-regeneration.md`](./docs/experiments/CF2-real-target-regeneration.md).

- **Load layout.** LE format level 0, little-endian, CPU `0x02` (80386), 4096-byte pages, all page-map entries plain "legal" pages, no debug info. Exactly two objects per image: object 1 code at base `0x10000` (flags `0x2045`), object 2 data (flags `0x2043`) at `0x90000` for the Antagonizer and `0x80000` for the bug patch. Open Watcom's absolute enumerated-page `page_off @ +0x80` is `0x18000` for the Antagonizer pair and `0x17600` for the patch pair; enumerated page data ends exactly at EOF in all four targets. The old ~11 KB trailing-region claim was a parser artifact from treating `impmod_off @ +0x70` as the page base.
- **Build toolchain.** Watcom C/C++32 under the Rational DOS/4G extender. Corrected `ANTAG_EN` VAs are Watcom runtime banner `0x783b6` and `RATIONAL DOS/4G` `0x9563c`.
- **Headless static analysis.** A dependency-light cloud pipeline exists using the standard library plus GNU `objdump`. With corrected reconstructed objects, `ANTAG_EN` yields 144696 decoded instructions, 1326 candidate regions, 7472 direct in-object call sites, and 4259 call-graph edges.
- **Conservative differential.** English Antagonizer ↔ patch: **72 exact / 613 reference-only / 525 constant-only / 116 / 87 structural**. International: **72 / 611 / 520 / 123 / 93**. The earlier post-layout-correction `685 strict` and `683 strict` aggregates were too permissive because they masked changed in-image references; they split exactly into `72 exact + 613 reference-only` and `72 exact + 611 reference-only`. Structural and constant-only counts are unchanged.
- **Artifact provenance.** `le_disasm` inventory JSON is schema-versioned and records the source hash, reconstructed-object hash, parser-layout identity, and signature model. `le_diff` rejects legacy/unversioned/pre-`+0x80` inventories rather than silently comparing them.

### External RE corpus discovered: FoxAhead/IDA-Projects (external static; validation pending T3)

A substantial public reverse-engineering corpus exists at `FoxAhead/IDA-Projects/Ascendancy/`. The roadmap audit pins upstream repository commit `77d43c6c52c1560b7068490dcf315e284914379e`; T3 must pin the exact Ascendancy tree/files it consumes rather than following mutable `main`.

High-value observations that T3 must reproduce and independently validate before later tasks promote them to project facts:

- upstream `Ascendancy/ANTAG.EXE` is byte-identical to the canonical English Antagonizer target: Git blob SHA-1 `504886b8c7a9abd6e7c5add3c3ff3e7b289cfae2`, corresponding to the canonical SHA-256 `8d91e89e…` and CRC32 `0x7A9B321B`;
- upstream `Ascendancy/patch.exe` is byte-identical to the canonical English bug-patch baseline: Git blob SHA-1 `9b9794c9966546e0512663261b56fa808fee9e7c`, corresponding to SHA-256 `7c944866…` and CRC32 `0x8AB98421`;
- the attached/CF1 International pair (`9d44b1ca…`, `16fa81fc…`) remains useful independent cross-locale corroboration; no byte-identical International target was identified in the pinned FoxAhead Ascendancy tree during this roadmap audit;
- `Ascendancy/IDA Plugin/ascendancy/config.yaml` labels the exact English files `ANTAG.EXE` as `v1.6.10` and `PATCH.EXE` as `v1.6.5`, with the same CRC32 values. Treat the Antagonizer version label as external provenance until T3 records how it is supported;
- the corpus includes a large IDA/Hex-Rays body of work rather than only one pseudocode file: dated C decompilations through `ANTAG.EXE20251010.c`, `ANTAG.EXE.h`, ASM/IDC exports, `Functions.xlsx`, an Ascendancy IDA plugin, Watcom type/signature material, library `.LIB/.PAT/.SIG/.lst` artifacts, and analyst notes describing Watcom/IDA setup;
- the latest external decompilation contains direct M1-relevant hypotheses: a `T_Planet` field named `Unknown_5A`; a UI write that toggles `V_Game.pCurPlanet->Unknown_5A`; a nearby `"Self Managed"` display condition; save/read-write references to the same field; and turn-processing logic that checks the field before calling an externally named `Q_Race_ManagePlanetDevelopment_sub_3D8F0` at VA `0x3D8F0` when no construction is active;
- the same corpus names useful lower-level construction anchors including `Q_Planet_StartConstruction_sub_34774` and `Q_Planet_BuildAtOptimalLocation_sub_34AE4`;
- FoxAhead's notes configure IDA for Fastcall and the generated C uses `__fastcall`, but that is analyst/decompiler configuration, not independent proof of the real ABI. RE2/RE3 still require a known-arity call-site check;
- the pinned repository root contains no `LICENSE` or README granting reuse rights. Until licensing/permission is clarified, **do not vendor or bulk-copy** FoxAhead's generated C/ASM/IDC, spreadsheets, signatures, or binary files into this repository. Use pinned upstream references and commit only independently generated facts, crosswalks, small necessary excerpts where legally appropriate, and our own reproducible analysis.

The external corpus is therefore a **high-value hypothesis and symbol source**, not an authority that outranks exact-target evidence. T3 exists specifically to turn useful upstream annotations into independently checked, hash-bound project evidence.

### Still assumptions

These are project directions, not yet binary facts. Do not assume:

- the runtime segment/selector mapping or DOS extender runtime behavior merely from the static LE load layout;
- that the 19440-byte growth of the Antagonizer's code object is explained only by the AI changes;
- that every whole-image difference is Antagonizer AI behavior; despite T1's strong lineage evidence, RE1 must retain unrelated bug-fix/configuration drift as a confound and prefer cross-locale or independent semantic/runtime corroboration;
- **the calling convention.** Watcom defaults plus FoxAhead's Fastcall-configured IDA/decompiler output strongly suggest a register convention, but this is not independent binary proof. RE2/RE3 must confirm it at known-arity real call sites before argument interpretation or hook design depends on it;
- that a candidate boundary from `tools/le_disasm.py` is a real function boundary — starts are derived from direct calls by linear sweep and indirect-only callees can be folded into preceding spans;
- that a particular address or function is stable between the baseline and Antagonizer;
- that FoxAhead's names, types, comments or inferred semantics are original symbols or ground truth. In particular, `T_Planet.Unknown_5A` at the apparent `+0x5A` field and `Q_Race_ManagePlanetDevelopment_sub_3D8F0` are high-value external hypotheses until T3/RE2/RE3 independently validate the corresponding bytes, relationships and meaning;
- that the existing UI toggle directly writes the authoritative runtime state merely because the external decompilation shows a candidate write; RE4 still establishes runtime semantics and ownership;
- that the safest implementation is an on-disk patch, runtime hook, loader, TSR, or any other specific mechanism.

All binary-specific findings must name the exact target hash. External FoxAhead-derived statements must additionally name the pinned upstream commit/file unless the fact has been independently reproduced and promoted into this repository's own evidence.

---

## Dependency overview

The expected M1 critical path is now split so the external corpus can remove unnecessary broad-search dependencies:

- `T1 → T3` validates and indexes the exact-target FoxAhead corpus immediately in cloud;
- `CF2 → T2` finishes our independent reproducible static-analysis bundle;
- `T2 + T3 → RE2 + RE3` validates the focused UI/state and per-turn seams in parallel;
- `RE1` runs in parallel as broader Antagonizer↔bug-patch corroboration and no longer blocks RE2/RE3 if T3's focused anchors validate;
- `CF3 + RE2 → RE4`, then `CF3 + RE3 + RE4 → RE5`;
- `RE4 + RE5 → A1/A2 → P1/P2 → UI1/UI2 → V1 → M1`.

`CF4` may run after `CF3` and gates visual/end-to-end UI validation.

Cloud-feasibility tasks are intentionally near the front so later work is not unnecessarily pushed to a local machine.

**Current front of the path:** CF1, T0 and T1 are complete. CF2's implementation and real-target expected values are complete in PR #4, but its final clean-checkout repository-CLI regression is still the completion gate. Treat CF2 as logically implemented for planning, but do not duplicate its work or mark its dependent completion gates satisfied until #4 is green and merged. **T3 is independently selectable now** because it depends only on completed T1 and public/hash-checkable upstream artifacts. **CF3** also remains independently selectable. T2 becomes selectable once CF2 returns to `Completed and verified`.

The important sequencing change is that a future cloud agent should not begin RE2/RE3 by rediscovering planet/UI/AI candidates from the entire binary. T3 first validates and packages the FoxAhead anchors; RE2/RE3 then independently prove or reject those anchors using our exact-target toolchain. Broad RE1 remains valuable but is no longer a mandatory search gate for M1.

---

# Track CF — Cloud feasibility

## CF1 — Investigate cloud access to exact target executables

- **Status:** **Completed and verified** — see [`docs/experiments/CF1-cloud-target-access.md`](./docs/experiments/CF1-cloud-target-access.md). Evidence: `runtime` for cloud reachability and the end-to-end fetch (observed in a Claude cloud sandbox), `static` for the hashes and container format, `reported` for publisher distribution intent.
- **Execution:** CLOUD RESEARCH
- **Priority:** Critical
- **Category:** Cloud enablement / target acquisition
- **Origin:** High-level steps 1–2
- **Depends on:** None
- **Gates:** T1, T2, RE1 and every later task that requires direct target bytes
- **Question:** Can a clean Codex or Claude cloud environment obtain the exact Antagonizer target and vanilla reference in a lawful, reproducible way without committing proprietary binaries to this repository?

### Outcome

**Yes, for the executables.** The decisive finding is what the Antagonizer *is*: not an in-place patcher but a **complete standalone game executable** (`ANTAG.EXE`) that is copied next to the retail `ASCEND.EXE` and reads the retail data files. The publisher's official bug patch is the same shape (`PATCH.EXE`, version 1.6.5 English / `F_PATCH.EXE`, 1.8.5 non-English). Both were released free of charge by The Logic Factory in 1995 and survive on the Internet Archive.

Established:

- the Antagonizer executable is fetchable in cloud, hash-pinned, from **two independently uploaded mirrors that contain byte-identical payloads** (static: `sha256 8d91e89e…` English, `9d44b1ca…` non-English, 610863 bytes each);
- a **vanilla-lineage reference is also fetchable in cloud**: the official bug-patch executable (`7c944866…` English, `16fa81fc…` non-English, 587451 bytes each);
- all four are DOS `MZ` stubs wrapping a Linear Executable image with a bound DOS/4G extender, carrying the game's own 1995 copyright banner (static);
- `tools/fetch_free_targets.py` + `tools/free-target-sources.json` reproduce this fail-closed into the git-ignored `binaries/`, and were run end to end in cloud;
- a clean environment needs only HTTPS egress to `archive.org` and `*.archive.org` (downloads redirect to per-node hosts) and stdlib Python 3.11+.

Rejected / bounded:

- the **retail game data files are not available as a lawful public dependency**, and the repository must not obtain them from abandonware or full retail distributions. This is a constraint handed to CF3/CF4, not a blocker for static RE. CF1 did **not** investigate the freely distributed official playable demo as a runtime fixture; that is CF3's, and CF1 must not be cited as ruling out a cloud runtime path.
- the **retail unpatched `ASCEND.EXE`** is not freely distributed. It is an optional third reference, not a prerequisite.
- CF1 settled the **packaging** relationship between the bug patch and the Antagonizer (both standalone executables), **not** their **build lineage**. T1 subsequently resolved the baseline decision with stronger cross-locale static lineage evidence; see [`docs/experiments/T1-canonical-target-selection.md`](./docs/experiments/T1-canonical-target-selection.md).
- `web.archive.org` was **blocked by egress policy** in the sandbox where this ran even though `archive.org` was reachable. Do not build tooling on a Wayback fallback without re-probing.
- abandonware full-game sources must never be added to the acquisition manifest, regardless of reachability.

Consequence for the roadmap: target acquisition no longer blocks T1/T2/RE1; T1 is complete, and CF3 starts from "cloud has the executables but not the data".

### Required investigation

Explore concrete mechanisms rather than assuming one:

- public redistributable/official patch archives if legally and technically suitable;
- scripted download from a stable source with checksum verification;
- agent/task attachments or other ephemeral input mechanisms available in the target cloud environment;
- maintainer-generated analysis bundles that avoid giving the cloud raw proprietary binaries;
- other reproducible approaches that preserve repository policy.

Do not commit game executables or copyrighted game assets merely to make the task easier.

### Deliverables

- `docs/experiments/CF1-cloud-target-access.md` describing approaches tested and their limitations.
- If direct cloud acquisition works: a fail-closed fetch/bootstrap script that downloads only permitted artifacts, verifies exact hashes, and stores them under ignored paths.
- If direct access does not work: a minimal local capture/export contract that produces only the artifacts needed by cloud tasks.
- Update every gated task owned by CF1 from `GATED` to either `CLOUD` or `LOCAL ONLY`, adding the execution procedure or handoff artifact.

### Acceptance criteria

- A fresh cloud agent can determine exactly how target bytes or their approved derivatives become available, or exactly why they cannot.
- The roadmap no longer leaves CF1-owned tasks with an undecided execution environment.
- No proprietary target binary is added to git.

---

## CF2 — Investigate cloud static reverse-engineering workflow

- **Status:** **Validation pending** — implementation, synthetic regression and corrected real-target expected values are complete; do not restore `Completed and verified` until `scripts/validate_cf2_real_targets.py --fetch` passes from a clean checkout of the current PR head. See [`docs/experiments/CF2-cloud-static-re.md`](./docs/experiments/CF2-cloud-static-re.md) and [`docs/experiments/CF2-real-target-regeneration.md`](./docs/experiments/CF2-real-target-regeneration.md).
- **Execution:** CLOUD RESEARCH
- **Priority:** Critical
- **Category:** Cloud enablement / static RE
- **Origin:** High-level step 2
- **Depends on:** None. CF1 and T1 are complete, so the exact canonical pair and all four corroboration targets are available in cloud; use real bytes rather than synthetic fixtures when the task asks for real-target evidence.
- **Gates:** T2, RE1, RE2, RE3
- **Question:** Can the static analysis needed for this milestone be run headlessly and reproducibly in Codex or Claude cloud rather than requiring an interactive local Ghidra session?

### Outcome so far

**Yes, with the standard library and GNU binutils.** No GUI, JVM, Ghidra LE loader, or `pip install` is required.

The decisive negative result remains: GNU `objdump` does not read the LE container itself (`file format not recognized`), while it disassembles flat i386 ranges correctly with `-b binary -m i386 --adjust-vma`. The gap was the container reader, not the disassembler.

Built and fail-closed:

- `tools/le_image.py` — LE container parser/reconstructor using Open Watcom's packed `os2_flat_header`; authoritative absolute `page_off @ +0x80`; `info` / `extract` / `strings` / `verify`;
- `tools/le_disasm.py` — drives `objdump`, derives candidate starts/call graph, and writes schema-versioned inventories with exact, reference and shape signatures plus reconstructed-object/parser provenance;
- `tools/le_diff.py` — rejects incompatible/stale inventories and performs exact → reference-only → constant-only matching before structural leftovers;
- `tools/le_fixture.py` — synthetic LE builder, including malformed images;
- `scripts/validate_cf2_real_targets.py` — invokes the repository CLIs against all four pinned real targets and asserts object fingerprints plus headline metrics.

Review of Open Watcom source exposed the original parser's `+0x70` mistake. With `page_off @ +0x80`, all page ranges end exactly at EOF and every declared entry starts with `EB 76` immediately before the Watcom runtime banner. Reconstructed-object hashes in `CF2-real-target-regeneration.md` gate future parser drift.

Corrected real-target inventory:

- `ANTAG_EN`: 144696 decoded instructions, 1326 candidate regions, 7472 direct call sites, 4259 call-graph edges;
- `ANTAG_INTL`: 144691 / 1326 / 7477 / 4260;
- `PATCH_EN`: 139093 / 1297 / 7251 / 4162;
- `PATCH_INTL`: 139129 / 1296 / 7255 / 4162.

Current conservative differential:

- **English:** 72 exact, 613 reference-only, 525 constant-only, 116 / 87 structural. Exact matches: 50 moved / 22 same candidate address. Structural-only matched-byte fraction `0.765115 / 0.798235`; 11 Antagonizer-only structural spans exceed 2000 bytes.
- **International:** 72 exact, 611 reference-only, 520 constant-only, 123 / 93 structural. Exact matches: 50 moved / 22 same. Structural-only fraction `0.759166 / 0.792016`; 12 Antagonizer-only structural spans exceed 2000 bytes.

The post-layout-correction `685 strict` English and `683 strict` international counts are also superseded as claims of identity: they masked changed in-image references and split exactly into `72 exact + 613 reference-only` and `72 exact + 611 reference-only`. The earlier `620 / 507 / 115 / 87` and `144684 / 1242 / 7252 / 4089` values came from the shifted `+0x70` object stream.

Limits that downstream work must retain:

- linear sweep can decode embedded data;
- candidate starts are direct-call-derived regions, not verified functions; indirect-only callees are folded into preceding spans;
- 11 EN / 12 INTL structural Antagonizer-only spans exceed 2000 bytes, so the structural count is not a changed-function count;
- reference-only differences mix benign relocation with possible callee/global/table retargets;
- constant-only differences mix DS-relative layout movement with genuine thresholds/flags and are the largest unresolved English bucket;
- structural matched-byte fraction ignores both unresolved middle buckets;
- despite T1's strong direct-lineage evidence, whole-image differences may still contain unrelated bug-fix/configuration drift and need cross-locale or semantic corroboration.

The Antagonizer code object remains exactly 19440 bytes larger than the corresponding patch code object in both locales. This is a measured layout fact only.

**Calling-convention implication, not established:** Watcom defaults suggest `__watcall`, but RE2/RE3 must confirm argument passing at real known-arity call sites before any interpretation or later trampoline depends on it.

### Clean-checkout completion gate

CF2 returns to `Completed and verified` only after a clean checkout of the current head passes:

```sh
python -m unittest discover -s tests -v
python scripts/validate_cf2_real_targets.py --fetch
```

The second command fetches/verifies all four CF1 binaries, checks all eight reconstructed-object hashes, invokes repository `le_disasm.py` for all four, and invokes repository `le_diff.py` for both product pairs plus locale sanity pairs. `.github/workflows/tests.yml` contains an explicit `CF2 real-target regression` job for the same gate.

### Deliverables

- reproducible scripts/configuration under `tools/` or `scripts/`;
- synthetic fixture coverage plus real-target regression;
- `docs/experiments/CF2-cloud-static-re.md` with tested tool versions and known limitations;
- updates converting CF2-owned gated tasks to `CLOUD` only once the completion gate passes.

### Acceptance criteria

A fresh cloud environment can run the static-analysis pipeline without manual GUI steps **and** the current-head repository CLIs reproduce the pinned object hashes/inventory/diff metrics on all four real targets.

---

## CF3 — Investigate cloud execution and debugging of the target game

- **Status:** Investigation first
- **Execution:** CLOUD RESEARCH
- **Priority:** Critical
- **Category:** Cloud enablement / DOS runtime
- **Origin:** High-level steps 2–5
- **Depends on:** CF1 (complete)
- **Gates:** RE4, RE5, P2, V1
- **Question:** Can the target DOS game, or at minimum the required state-tracing/debugging experiments, execute reproducibly inside Codex or Claude cloud?

> **Starting condition from CF1:** cloud has the game **executables**. Retail game data are **not available as a lawful public dependency**, and the repository must not obtain them from abandonware or full retail distributions.
>
> However — and CF1 did **not** investigate this — a freely distributed official **playable demo** of Ascendancy exists (`reported`, maintainer). It may contain enough game data and functionality for runtime and debugging work, which would make a cloud runtime fixture possible.
>
> **Before classifying any target runtime task as `LOCAL ONLY`, CF3 must evaluate the demo.** A `LOCAL ONLY` decision that has not tested the demo is not a completed investigation, and CF1's findings must not be cited as evidence that no lawful cloud runtime path exists — CF1 established target-executable availability and nothing about the demo.

### Required investigation

**Evaluate the official playable demo as a cloud runtime fixture. Do this first — it decides whether the rest of this item is a cloud or local question:**

- reproducibly acquire it from an authorized/legitimate redistribution source, hash-pinned and fail-closed, in the manner CF1 established for the executables. Abandonware repacks and full retail distributions are not acceptable sources;
- run it headlessly/scriptably;
- verify whether planet management and self-management exist in it at all — a demo with the colony screens cut is a different proposition from one that merely limits turns or star systems;
- test whether the canonical `ANTAG.EXE` can run against the demo's data files;
- if it cannot, determine which runtime RE experiments can still be performed against the demo's own `ASCEND.EXE`, and which genuinely require the retail installation.

Record the outcome even if negative: a demo that lacks the relevant screens is exactly the kind of result that must be preserved so the next agent does not retry it.

Then investigate a non-interactive or scriptable emulator/debugger setup capable of the evidence this project needs. Relevant capabilities include:

- launching a DOS protected-mode application in the cloud environment;
- deterministic mounting/configuration;
- bounded stdout/log/capture artifacts;
- scripted input or another reproducible way to reach a scenario;
- memory snapshots, breakpoints/watchpoints, debugger logging, or equivalent instrumentation;
- clean process termination and artifact collection.

Do not count “the emulator package installs” as success. The result must be relevant to the kinds of runtime evidence later tasks require.

### Deliverables

- `docs/experiments/CF3-cloud-runtime-debugging.md`, including the demo evaluation and its result whether positive or negative;
- reusable environment/config/scripts if cloud execution is viable;
- a fail-closed acquisition path for the demo if it proves usable, following the CF1 pattern;
- a smoke test using a safe fixture, and target-game smoke test if CF1 provides target access;
- updates converting RE4, RE5, P2 and other CF3-owned gated tasks to `CLOUD` or `LOCAL ONLY`.

If runtime work becomes local-only, create/identify a one-shot local experiment workflow that produces a compact artifact archive for cloud analysis.

### Acceptance criteria

The roadmap has an evidence-backed execution decision for runtime/debugging tasks and a reproducible handoff in either direction.

Any `LOCAL ONLY` classification is only valid once the playable demo has actually been evaluated as a cloud runtime fixture and the reason it is insufficient is recorded. "The retail installation is not publicly available" is **not** on its own a sufficient basis for `LOCAL ONLY`.

---

## CF4 — Investigate cloud UI interaction and visual validation

- **Status:** Investigation first
- **Execution:** CLOUD RESEARCH
- **Priority:** High
- **Category:** Cloud enablement / UI validation
- **Origin:** High-level step 7
- **Depends on:** CF3
- **Gates:** V1 and any UI task whose correctness cannot be established statically
- **Question:** Can Codex or Claude cloud reliably drive the planet UI and capture enough visual/state evidence to validate Manual / Agricultural / Industrial selection?

### Required investigation

Try to make validation machine-driven rather than requiring the maintainer to play manually. Evaluate options such as scripted emulator input, deterministic save/scenario setup, frame/screenshot capture, state/log instrumentation, or a combination.

The goal is not general game automation. It is the smallest reproducible harness that can validate the milestone scenario.

### Deliverables

- `docs/experiments/CF4-cloud-ui-validation.md`;
- scripts/configuration for repeatable UI input/capture if viable;
- a definition of the exact M1 validation scenario;
- update V1 to `CLOUD` or `LOCAL ONLY`.

If local validation is unavoidable, prepare a one-command or minimal-step local runner that captures all evidence needed for a later CLOUD analysis task.

### Acceptance criteria

A future agent does not have to rediscover how to validate the UI. The roadmap contains a concrete cloud path or an explicit local-only path with automated artifact capture.

---

# Track T — Target baseline and reproducibility

## T0 — Define target policy and metadata capture tooling

- **Status:** **Completed and verified** — deterministic synthetic fixture coverage establishes the T0 capture contract; no target-runtime claim is made.
- **Execution:** CLOUD
- **Priority:** High
- **Category:** Tooling / compatibility
- **Origin:** High-level step 1
- **Depends on:** None
- **Goal:** Define how the project names, fingerprints, and records candidate vanilla and Antagonizer executables before any offsets or patch decisions are accepted.

### Outcome

T0 now has a stdlib-only target inspector, versioned machine-readable schema, synthetic example, deterministic malformed-input/format tests, and a human policy in [`docs/re/targets.md`](./docs/re/targets.md).

Established (`synthetic` / tooling):

- `tools/inspect_target.py` fingerprints an arbitrary external file by SHA-256/size without editing code and records a caller-supplied stable id/label;
- it detects DOS `MZ` and shallow `LE` container/header metadata when structurally present, reports architecture only for explicitly recognized LE CPU types, and records positive DOS/4G-family stub-marker evidence without treating marker absence as proof;
- malformed/truncated headers are bounded and surfaced as warnings rather than converted into guessed facts;
- capture JSON is deterministic for the same bytes/logical invocation and strips host directory names from the recorded command;
- `tools/target-manifest.schema.json` defines schema v1 and `docs/re/target-manifest.example.json` provides a repository-safe synthetic example;
- `docs/re/targets.md` defines stable-id, manifest, interpretation, canonical-entry and evidence boundaries.

Deliberately not established by T0:

- no canonical Antagonizer target or comparison baseline was selected by T0 — T1 later made that decision from real candidate bytes and lineage evidence;
- no object/page-table walking, disassembly, function discovery, xrefs, strings pipeline or binary-diff workflow was implemented — that remains CF2/T2 scope;
- no game binary was executed and no target runtime behavior was validated.

### Work

Create a small target-inspection tool/script that can run against a file supplied outside git and emit repo-safe metadata, including at least:

- SHA-256;
- file size;
- filename/user-supplied version label;
- detected executable/container format and architecture when determinable;
- useful header/extender/load metadata supported by the chosen parser;
- tool version and command used.

Define the machine-readable target manifest format and the human-readable `docs/re/targets.md` convention.

Do not hard-code unverified release names or hashes.

### Deliverables

- target metadata/capture script;
- deterministic tests using synthetic or redistributable fixtures;
- initial `docs/re/targets.md` documenting the policy and leaving actual canonical hashes explicitly pending if unavailable;
- schema/example for any machine-readable target manifest.

### Acceptance criteria

Another agent or maintainer can point the tool at candidate binaries and produce a deterministic fingerprint record without editing code.

---

## T1 — Establish the canonical Antagonizer target and vanilla reference

- **Status:** **Completed and verified** — see [`docs/experiments/T1-canonical-target-selection.md`](./docs/experiments/T1-canonical-target-selection.md). Static evidence establishes exact candidate identities and strongly supports directly comparable Antagonizer↔bug-patch build lineage; exact source-control revision identity remains unproven and is carried forward as an RE1 constraint.
- **Execution:** **CLOUD** — set by CF1. Candidate bytes are fetchable in cloud with `python3 tools/fetch_free_targets.py`; provenance is recorded in [`docs/experiments/CF1-cloud-target-access.md`](./docs/experiments/CF1-cloud-target-access.md).
- **Priority:** Critical
- **Category:** Target baseline
- **Origin:** High-level step 1
- **Depends on:** T0 (complete), CF1 (complete)
- **Goal:** Replace release-name assumptions with exact target identities and provenance.

### Outcome

Canonical M1 production target:

- `antagonizer-en` / `ANTAG_EN.EXE`;
- SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- 610863 bytes.

Canonical comparison baseline:

- `bugpatch-en` / `PATCH_EN.EXE` (publisher `PATCH.EXE`, documented version 1.6.5);
- SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- 587451 bytes.

The reviewed T0 captures are committed as [`docs/re/target-manifest.json`](./docs/re/target-manifest.json), and canonical entries plus compatibility boundaries are in [`docs/re/targets.md`](./docs/re/targets.md).

Build-lineage result (`static`):

- all four CF1 candidates share a byte-identical complete bound MZ stub and the same Watcom/DOS runtime fingerprints;
- the International-vs-English object-layout delta is exactly the same in the Antagonizer and bug-patch families (`+0xb0` executable virtual size/entry, `+0x50` writable virtual size/stack);
- the Antagonizer-vs-bug-patch layout delta is exactly the same in both locales (`+0x4bf0` executable virtual size/entry, `+0xb30` writable virtual size/stack, `+5` executable pages);
- each locale-matched Antagonizer↔bug-patch comparison has the same 467 common uniquely-occurring ASCII strings, and the complete 15-bucket file-offset displacement histogram is identical between the English and International comparisons.

This evidence is stronger than the zip member timestamps that originally made the English pair look doubtful. The timestamp gap remains weak archive/file provenance, not a demonstrated source-build gap. The English pair is therefore selected because it is same-language and has the strongest publisher documentation while retaining cross-locale structural corroboration.

The International pair remains RE corroboration/future compatibility input. It is **not** added to M1 support.

RE1 constraint: comparable lineage justifies normalized whole-image differential analysis as a candidate-ranking tool, but unrelated bug-fix/configuration drift remains possible. Prefer candidate changes reproduced by the International pair or supported by independent semantic/runtime evidence; do not equate every difference with AI behavior.

### Candidate set (established by CF1)

Four candidates, all cloud-fetchable and hash-pinned in `tools/free-target-sources.json`:

| Manifest id | Role | Size | SHA-256 |
| --- | --- | --- | --- |
| `antagonizer-en` | **Canonical M1 Antagonizer target** | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `antagonizer-intl` | International Antagonizer; corroboration/future compatibility | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `bugpatch-en` | **Canonical comparison baseline**, official bug patch 1.6.5 English | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `bugpatch-intl` | International official bug patch 1.8.5; corroboration/future compatibility | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

### Required evidence

For the chosen Antagonizer production target and vanilla comparison reference, record:

- exact SHA-256 and size;
- filename and meaningful release/patch provenance;
- **build/version lineage relationship between the chosen Antagonizer target and the chosen comparison baseline** — established from evidence, not assumed;
- detected executable format/architecture/extender facts from T0 plus bounded supporting evidence where T0 intentionally does not parse deeper;
- whether the files are directly available to cloud agents or require a handoff.

### Baseline selection and lineage decision

CF1 settled only the **packaging** relationship: the Antagonizer and the bug patch are separate standalone executables, not a patch stacked on a base. T1 supplied the stronger binary evidence needed to make the baseline decision.

Exact same-revision source provenance is still unavailable because the binaries expose no source-control/build identifier. The repeated cross-locale layout and string-anchor transforms are nevertheless strong evidence of a directly comparable build lineage rather than unrelated source snapshots. That is sufficient for RE1 to use the selected pair as a normalized differential baseline with the explicit confound policy above.

The retail unpatched `ASCEND.EXE` is not freely distributed and remains an optional historical reference; it does not block T1 or RE1.

### Deliverables

- [x] completed canonical entries in `docs/re/targets.md` and `docs/re/target-manifest.json`;
- [x] experiment/source record explaining target selection;
- [x] roadmap updates removing now-invalid target-selection/version assumptions and handing RE1 its lineage constraint.

### Acceptance criteria

**Met.** Every later binary-specific task can name one exact Antagonizer hash as the M1 production target and one exact vanilla-lineage hash as its comparison baseline.

---

## T2 — Produce a reproducible static-analysis bundle

- **Status:** Investigation first
- **Execution:** **CLOUD** — set by CF2's feasibility result. T1 is complete; T2 remains dependency-blocked only until CF2 returns to `Completed and verified` after its clean-checkout gate.
- **Priority:** High
- **Category:** Tooling / static RE
- **Origin:** High-level step 2
- **Depends on:** T1 (complete), CF2
- **Goal:** Make target static analysis reproducible enough that later agents do not depend on one person's interactive RE database.

### Work

Using the CF2 toolchain, generate stable analysis outputs for both canonical binaries. Prefer reviewable machine-readable/text artifacts over opaque project databases.

Useful outputs may include:

- segment/section/load maps;
- strings and references where available;
- normalized candidate/start-address inventories;
- imports/runtime/library indicators if applicable;
- call edges or other comparable relationships;
- disassembly/decompiler snippets only where needed and legally appropriate;
- tool versions and exact commands.

**Independent format-oracle check required by CF2 review:** obtain/run Open Watcom `wdump` (or the corresponding official Open Watcom executable dumper) on all four hash-pinned CF1 targets, compare its object/page/header output with `python tools/le_image.py info --json`, and record exact agreements/disagreements. CF2 established the field semantics from Open Watcom source; T2 must turn that into a target-level independent tool-output cross-check rather than citing source agreement as if `wdump` had already been run on the binaries.

If T3 has completed, include its small independently verified FoxAhead crosswalk as an **annotation layer** over the project's own bundle. Do not make T2 reproducibility depend on IDA databases, Hex-Rays, or bulk upstream generated source. T2 and T3 are intentionally parallelizable; each must remain useful if the other upstream/tooling source disappears.

Avoid bulk committing copyrighted disassembly if a smaller derived representation is sufficient.

### Deliverables

- scripts to regenerate the bundle;
- repo-safe derived artifacts under `docs/re/` or another documented location;
- `docs/experiments/T2-static-analysis-bundle.md` including the `wdump` comparison.

### Acceptance criteria

A later CLOUD task can reason about target structure and reproduce the relevant derived outputs without relying on undocumented local GUI state, and the LE load-map facts have an independent target-level `wdump` comparison.

---

## T3 — Validate and index the FoxAhead Ascendancy RE corpus

- **Status:** Investigation first
- **Execution:** **CLOUD**
- **Priority:** Critical
- **Category:** Reverse engineering / external corpus validation
- **Origin:** Discovery of `FoxAhead/IDA-Projects/Ascendancy/`
- **Depends on:** T1 (complete)
- **Gates:** RE2, RE3; supplies focused anchors to RE1 but does not depend on CF2/T2
- **Question:** Which FoxAhead annotations are demonstrably tied to our exact canonical binaries, how do their address/type conventions map to our own toolchain, and which M1-relevant hypotheses can be promoted into independently verified static evidence?

### Starting evidence to reproduce

Use upstream commit `77d43c6c52c1560b7068490dcf315e284914379e` as the audit starting point, then pin the exact relevant file/tree object IDs in the experiment record.

The roadmap audit found:

- `Ascendancy/ANTAG.EXE` ↔ canonical `ANTAG_EN.EXE`: exact file identity (`sha256 8d91e89e…`, Git blob `504886b8…`, CRC32 `0x7A9B321B`);
- `Ascendancy/patch.exe` ↔ canonical `PATCH_EN.EXE`: exact file identity (`sha256 7c944866…`, Git blob `9b9794c9…`, CRC32 `0x8AB98421`);
- FoxAhead's `config.yaml` labels those files `ANTAG.EXE v1.6.10` and `PATCH.EXE v1.6.5`;
- the two CF1 International files have their known hashes but no exact copy was identified in the pinned upstream tree;
- high-value external symbol/type hypotheses include `T_Planet.Unknown_5A`, `V_Game.pCurPlanet`, `Q_Race_ManagePlanetDevelopment_sub_3D8F0`, `Q_Planet_StartConstruction_sub_34774`, `Q_Planet_BuildAtOptimalLocation_sub_34AE4`, and the `"Self Managed"` UI path.

These are **inputs**, not T3 acceptance evidence.

### Work

1. **Pin and inventory the corpus.** Record the upstream commit plus hashes/object IDs for only the files actually used. Classify the large corpus by purpose: target binaries, IDA/decompiler exports, type information, function tables/spreadsheets, IDA automation, compiler/library signatures, and analyst notes. Do not require a future agent to browse the entire directory again.
2. **Prove exact target identity.** Recompute SHA-256/size/CRC32 for the upstream English `ANTAG.EXE` and `patch.exe` and match them to T1. Record that the International pair is independent corroboration unless an exact upstream counterpart is subsequently found.
3. **Establish the coordinate-system crosswalk.** Determine how FoxAhead's reported VAs/function suffixes map to LE object-relative offsets and the CF2 reconstructed-image VA convention. Validate at least three unrelated anchors by raw instruction/byte windows and direct-call relationships. Explicitly reconcile any small apparent discrepancies such as FoxAhead `config.yaml`'s `start: 0x783B4` versus CF2's Watcom runtime-banner VA `0x783B6`; do not paper over them.
4. **Evaluate ABI evidence.** Record what comes from Watcom defaults, FoxAhead's IDA setup notes, decompiler `__fastcall` declarations, and independently observed call sites. The first three are hypothesis/supporting evidence; only the last can establish this binary's actual argument convention for our purposes.
5. **Build a focused M1 crosswalk.** Starting from the external candidates, independently verify the exact instructions/xrefs/data relationships for:
   - candidate `T_Planet + 0x5A` state storage (`Unknown_5A` upstream name);
   - the selected-planet UI toggle and `"Self Managed"` rendering path;
   - save/read-write references that may constrain state lifetime;
   - the per-race/per-planet turn guard using the candidate state;
   - the call into the candidate planet-development manager near `0x3D8F0`;
   - lower-level build/construction entry points that bound later patch/instrumentation experiments.
6. **Separate names from facts.** For every crosswalk entry record: exact target hash, upstream file/commit and upstream name, our independently observed address/bytes/xrefs, evidence category, confidence, and whether the semantic name itself remains unverified.
7. **Keep the repository license-safe and reproducible.** The pinned FoxAhead repository exposes no project-level license grant. Do not commit bulk C/ASM/IDC exports, spreadsheets, IDA databases, library archives, signatures, or copied target binaries. Prefer a small script that fetches hash-pinned upstream inputs into an ignored cache and emits only independently generated metadata/crosswalk facts. If upstream licensing is later clarified, update this rule explicitly rather than assuming permission.

### Deliverables

- `docs/experiments/T3-foxahead-corpus-validation.md` with pinned upstream provenance, identity checks, corpus inventory, address/ABI validation and negative findings;
- `docs/re/foxahead-crosswalk.json` (or an equally reviewable machine-readable format) containing only bounded independently checked facts/pointers, not bulk upstream source;
- a small reproducible cloud script under `tools/` or `scripts/` for fetching/verifying the selected upstream files and regenerating the crosswalk inputs where practical;
- updates to RE1/RE2/RE3 if any advertised anchor fails validation or reveals a better dependency split.

### Acceptance criteria

- a fresh cloud agent can reproduce the exact-target identity and address crosswalk without IDA GUI state;
- at least the UI/state and turn-manager M1 anchors are either independently validated against `ANTAG_EN.EXE` or explicitly rejected with evidence;
- upstream semantic names remain labelled as external hypotheses unless independently established;
- no bulk unlicensed FoxAhead-generated code/data or game binaries are copied into this repository;
- RE2 and RE3 can start from a bounded set of exact-target anchors instead of rediscovering them across the whole executable.

---

# Track RE — Understand existing self-management

## RE1 — Build and reconcile the vanilla ↔ Antagonizer differential map

- **Status:** Investigation first
- **Execution:** **CLOUD** — set by CF2 once its final validation gate passes. Both sides are cloud-fetchable, T1 fixed their exact hashes, and `tools/le_diff.py` performs the comparison. Still dependency-blocked on T2 and T3.
- **Priority:** High
- **Category:** Reverse engineering / differential analysis
- **Origin:** High-level step 3 and the decision to use vanilla as a reference
- **Depends on:** T2, T3
- **Role in M1:** Parallel corroboration and broader context. If T3's focused UI/state/turn anchors validate, RE1 is **not** a prerequisite for RE2/RE3. If T3 rejects those anchors, update the roadmap and restore an appropriate search dependency rather than silently falling back to broad guessing.
- **Question:** Which code/data regions changed between canonical vanilla-lineage baseline and Antagonizer, how do they relate to independently validated FoxAhead anchors, and which changes plausibly explain the documented improvement in planetary self-management?

> **Canonical pair from T1:** target is `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`; baseline is English `PATCH.EXE` / `PATCH_EN.EXE` SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` (publisher-documented 1.6.5). The International pair is corroboration input, not an additional supported M1 target.
>
> **Lineage constraint from T1:** cross-locale object-layout and unique-string displacement evidence strongly supports directly comparable Antagonizer↔bug-patch lineage, but exact same-revision source identity is not proven. A whole-image differential is valid for **candidate ranking**, not for attributing every difference to AI. Prefer changes that reproduce in the International pair or have independent semantic/runtime evidence. Keep unrelated bug-fix/configuration drift as an expected confound.
>
> **External-anchor constraint from T3:** FoxAhead names/types are not source truth. Use only T3 entries that independently validate their exact address/bytes/xrefs; then ask where those anchors land in the baseline and in each CF2 diff class. An upstream name is a search accelerator, not acceptance evidence.
>
> **Do not interpret candidate counts as function counts.** `le_disasm` candidate boundaries come from direct calls plus a seed; indirect-only callees are folded into preceding spans. In the English product diff 11 of 116 Antagonizer-only structural spans exceed 2000 bytes and the largest is ~7964 bytes. `116 structural` therefore means 116 regions/leads, not 116 changed functions.

### Required inputs from CF2

RE1 must inspect **all unresolved classes**, not only structural leftovers:

- `reference_only_differences`: 613 EN / 611 INTL. In-image operands changed. Some will be benign relocation; some may be true callee/global/state/table retargets. A changed reference is not an identical candidate.
- `constant_only_differences`: 525 EN / 520 INTL. This is the largest unresolved English semantic bucket. DS-relative layout movement and genuine thresholds/biases/flags are mixed; an Antagonizer change implemented by retuning constants can live here.
- structural regions: 116 / 87 EN and 123 / 93 INTL, with the large-span caveat above.
- exact matches: only 72 in each product pair under the conservative operand-preserving definition.

If the two unresolved middle buckets remain too noisy, parsing LE fixup records is the clean next discriminator for loader-patched operands. Do not solve this by masking more values and calling the result identical.

### Work

Start by projecting T3's independently validated M1 anchors into the patch baseline and both locale-pair diffs. This can quickly distinguish “same generic game mechanism” from Antagonizer-specific changes and can seed function-boundary correction around known real routines.

Then use normalized/static analysis rather than raw byte diff alone to rank the remaining candidate regions using strings, call relationships, data references, UI proximity, cross-locale consistency, or known self-management behavior. Do not name a candidate `ManagePlanet` merely because FoxAhead did; retain the external name separately from our evidence-backed description until semantics are established.

### Deliverables

- `docs/re/vanilla-antagonizer-diff.md` with a ranked candidate map across reference-only, constant-only and structural evidence, including where T3 anchors land;
- machine-readable diff output or scripts where useful;
- explicit hypotheses and confidence level;
- negative findings that materially narrow the search.

### Acceptance criteria

The project has a reproducible broader explanation of how the focused M1 anchors relate to vanilla/Antagonizer differences and a bounded map for future M2/deeper AI work. No candidate is presented as a confirmed function/behavior solely from an external symbol name or a diff-class match.

---

## RE2 — Identify the existing auto-management UI/state seam statically

- **Status:** Investigation first
- **Execution:** **CLOUD** — the analysis path is resolved by CF2 once its final gate passes; dependency-blocked on T2 and T3, but no longer on broad RE1 if T3's focused anchors validate
- **Priority:** Critical
- **Category:** Reverse engineering / planet state / UI
- **Origin:** High-level steps 3–4
- **Depends on:** T2, T3
- **Question:** Does the exact canonical binary independently support FoxAhead's candidate `T_Planet + 0x5A` self-management state and UI write/read path, and what state representation is actually changed or consulted?

### Work

Use T3's crosswalk as a bounded hypothesis set, not as truth.

**First calling-convention check:** before interpreting argument/register roles from candidate call sites, select at least one real call with independently inferable arity/semantics and establish whether the surrounding code follows the register convention suggested by FoxAhead/Watcom or a stack-based convention. Record the binary evidence; do not inherit either the compiler default or IDA's Fastcall setting as a game fact.

Then independently trace and verify:

- the candidate selected-planet relationship corresponding to external `V_Game.pCurPlanet`;
- the exact instruction that externally decompiles as `V_Game.pCurPlanet->Unknown_5A = ~V_Game.pCurPlanet->Unknown_5A` and whether the apparent field offset is really `+0x5A` in our target coordinate system;
- the `"Self Managed"` rendering/read path and whether it tests the same storage;
- other reads/writes, including the external `Q_Planet_ReadWrite_sub_370B8` hypothesis, that constrain ownership/lifetime;
- any alternative interpretation that fits the bytes equally well;
- candidate code sites suitable for runtime watchpoint/instrumentation in RE4.

Do not infer “boolean persisted self-management state” only from a convenient decompiler field name. Static evidence should establish object relationship, offset and read/write sites; RE4 establishes runtime semantics on multiple planets.

### Deliverables

- `docs/re/auto-management-ui-state.md`;
- calling-convention observation tied to exact target/call sites;
- independently annotated state/UI sites tied to exact target hash and cross-referenced to (but not copied from) T3 upstream annotations;
- a minimal runtime experiment specification for RE4 that maximizes information gain.

### Acceptance criteria

RE4 can be executed as a bounded watchpoint/state-transition experiment rather than an open-ended debugger session; the candidate state offset and UI relationship are independently established or rejected; and static argument interpretation is not resting on an unverified ABI or external decompiler label.

---

## RE3 — Identify the per-turn self-management decision path statically

- **Status:** Investigation first
- **Execution:** **CLOUD** — the analysis path is resolved by CF2 once its final gate passes; dependency-blocked on T2 and T3, but can run in parallel with RE2 and no longer requires broad RE1 if T3's focused anchors validate
- **Priority:** Critical
- **Category:** Reverse engineering / turn processing
- **Origin:** High-level step 3
- **Depends on:** T2, T3
- **Question:** Does the canonical binary independently confirm the external per-race/per-planet guard and call into the candidate `Q_Race_ManagePlanetDevelopment_sub_3D8F0`, and where is the smallest real seam that consumes player-planet self-management state each turn?

### Work

Before assigning meaning to registers/stack slots, independently confirm the calling convention at a relevant known-arity call site. If RE2 has already landed equivalent evidence, reuse it explicitly; otherwise record evidence that RE2 can reference later.

Use T3's bounded anchors to verify the external hypothesis rather than rediscovering the entire AI:

- locate the per-race/per-planet loop and independently decode the guard externally represented as `race != player || candidate_state || V_SelfPlayMode`;
- verify the adjacent `buildingPlanetItemIndex == 0xFF` condition and direct call target near external VA `0x3D8F0`;
- determine whether the candidate manager truly reaches the lower-level planet build/construction routines, using call/xref evidence rather than semantic naming alone;
- separate “is this planet automated?” state checks from policy/decision code and from generic action-execution code;
- determine what is shared with AI-controlled empires versus player self-management;
- if RE2 has already established the state field, reconcile the two analyses; if not, leave exact cross-references so RE2 can do so without repeating the whole trace.

Do not require full reconstruction of the AI algorithm. M1 only needs a safe seam that lets two profile identities continue to invoke existing self-management.

### Deliverables

- `docs/re/auto-management-turn-path.md`;
- calling-convention evidence or an explicit cross-reference to the RE2 evidence used;
- independently verified call graph/data-flow description tied to target hash and external crosswalk IDs;
- a minimal runtime confirmation plan for RE5.

### Acceptance criteria

There is a falsifiable, exact-target hypothesis for where candidate mode state is consumed each turn and how existing self-management reaches planet-development actions. The key guard/call relationship is independently established or rejected, and ABI interpretation is backed by binary evidence rather than FoxAhead naming/configuration.

---

## RE4 — Runtime-confirm the per-planet mode state and UI transition

- **Status:** Investigation first
- **Execution:** GATED — CF3 must change this to `CLOUD` or `LOCAL ONLY`
- **Priority:** Critical
- **Category:** Reverse engineering / runtime state
- **Origin:** High-level steps 3–4
- **Depends on:** RE2, CF3
- **Question:** What exact runtime state transition occurs when the existing self-management control is toggled for a selected planet?

### Experiment requirements

The experiment should distinguish at least these hypotheses where relevant:

- state stored directly in a planet object;
- state stored in a side structure/indexed table;
- UI queues a command and state changes later;
- UI state and simulation state are distinct.

Capture enough context to establish ownership of the field/state, not merely “byte X changed once.” Repeat on at least two different planets if feasible to establish per-planet behavior.

### Deliverables

- reproducible experiment record under `docs/experiments/`;
- durable findings in `docs/re/auto-management-ui-state.md`;
- exact target hash and addresses/offsets/signatures with evidence category;
- update RE2 hypotheses/status.

If `LOCAL ONLY`, the local run must emit a compact artifact that a cloud agent can analyze without another interactive session.

### Acceptance criteria

The project can identify and observe the per-planet auto-management state transition with runtime evidence and can tell manual from automated state for at least two planets.

---

## RE5 — Runtime-confirm the per-turn self-management call path

- **Status:** Investigation first
- **Execution:** GATED — CF3 must change this to `CLOUD` or `LOCAL ONLY`
- **Priority:** Critical
- **Category:** Reverse engineering / runtime turn processing
- **Origin:** High-level step 3
- **Depends on:** RE3, RE4, CF3
- **Question:** Which runtime path consumes the confirmed auto-management state during a turn and reaches the existing planetary management decision/action code?

### Work

Instrument the smallest confirmed boundary from RE3/RE4. Establish causality by comparing manual and automated planets and, where feasible, two automated planets with different current construction/state.

Avoid tracing the whole game loop if a narrow breakpoint/watchpoint/hook can answer the question.

### Deliverables

- runtime experiment record;
- updated `docs/re/auto-management-turn-path.md` with established call/data relationships;
- the smallest safe candidate seam for preserving existing automation under new profile identities.

### Acceptance criteria

The project knows where the new profile representation must map back to “automated” semantics for M1 without requiring a full reconstruction of the AI.

---

# Track A — Architecture decisions

## A1 — Design the M1 per-planet profile state representation

- **Status:** Open
- **Execution:** CLOUD
- **Priority:** Critical
- **Category:** Architecture / state
- **Origin:** High-level step 6
- **Depends on:** RE4, RE5
- **Goal:** Choose the least invasive representation for `Manual`, `Agricultural`, and `Industrial` during the current game session.

### Candidate directions to evaluate

Examples, not prescriptions:

- extend/reuse unused values or bits in an existing confirmed state field;
- keep original manual/automated state untouched and maintain a mod-owned side table keyed by a stable planet identity/index;
- another representation justified by established object lifetime and memory behavior.

Save-game format changes should be avoided for M1 unless evidence shows they are necessary.

### Decision criteria

- per-planet correctness;
- stable lifetime for the current session;
- no collision with confirmed game state;
- minimal patch surface;
- easy fallback to original manual/automated semantics;
- clear path to later save persistence without forcing it now;
- testability outside the target where possible.

### Deliverables

- an ADR/design note under `docs/re/` or `docs/`;
- explicit invariants and lifecycle rules;
- update downstream task assumptions if the chosen design differs from this roadmap.

### Acceptance criteria

The implementation tasks no longer need to invent where profile identity lives or how it maps to the game's original automation boolean/state.

---

## A2 — Select the patch/integration mechanism

- **Status:** Investigation first
- **Execution:** CLOUD
- **Priority:** Critical
- **Category:** Architecture / patching
- **Origin:** High-level step 5
- **Depends on:** T1, T2, RE4, RE5
- **Goal:** Choose the safest practical mechanism for modifying the canonical target and define how it is built, installed, removed, and version-gated.

### Evaluate based on established target facts

Possible mechanisms may include an executable transformation, loader-time/runtime modification, or another DOS-compatible technique. Do not import assumptions from modern Win32 hooking if the confirmed target environment does not support them.

The decision must cover:

- how exact target compatibility is checked;
- how patch locations are found and validated;
- failure behavior for unknown binaries or ambiguous matches;
- rollback/removal;
- how much code/data space the mechanism can add;
- whether the mechanism can be built and tested in cloud;
- how later UI and policy logic will be integrated.

### Deliverables

- architecture decision record;
- concrete patch format/mechanism and safety invariants;
- any required roadmap changes to implementation tasks.

### Acceptance criteria

There is one accepted M1 patch mechanism with no unresolved “we will decide during implementation” dependency.

---

# Track P — Patch tooling and proof of execution

## P1 — Implement the fail-closed patch/build pipeline

- **Status:** Open
- **Execution:** CLOUD
- **Priority:** Critical
- **Category:** Implementation / tooling
- **Origin:** High-level step 5
- **Depends on:** A2
- **Goal:** Build the reusable mechanism that produces and applies the M1 modification safely, before adding profile behavior.

### Requirements

As applicable to A2:

- exact supported target hash/version gate;
- expected-byte/signature/structural validation before modification;
- reject zero or ambiguous matches;
- deterministic output;
- reversible install/remove or deterministic regeneration of an untouched target;
- tests for success, unsupported input, corrupted expected bytes, zero match and ambiguous match where meaningful;
- synthetic fixture coverage so CI/cloud can exercise the patch logic without proprietary binaries.

### Deliverables

- implementation under `tools/`, `scripts/`, or a documented source directory;
- focused tests;
- usage documentation;
- no feature behavior beyond what is needed to prove the patch pipeline itself.

### Acceptance criteria

The patch pipeline is independently testable in cloud and fails closed for unsupported/surprising inputs.

---

## P2 — Validate a minimal proof-of-execution modification on the target

- **Status:** Investigation first
- **Execution:** GATED — CF3 must change this to `CLOUD` or `LOCAL ONLY`
- **Priority:** Critical
- **Category:** Runtime validation / patch mechanism
- **Origin:** High-level step 5
- **Depends on:** P1, CF3
- **Goal:** Prove that the chosen mechanism can alter one harmless, clearly observable behavior in the canonical Antagonizer target and cleanly restore original behavior.

### Constraints

Choose the smallest diagnostic modification that proves code/data control at a relevant seam. Do not implement the profile feature opportunistically in this task.

The test must verify:

- target hash gate;
- patch application;
- observable execution of modified behavior;
- clean removal/rollback;
- original target hash or behavior restored as appropriate.

### Deliverables

- experiment record and bounded runtime artifact;
- any necessary patch-tool fixes;
- durable note describing the proven patch seam/mechanism.

### Acceptance criteria

The project has target-runtime evidence that the selected patch mechanism actually executes and is reversible.

---

# Track UI — Three-state mode and player interaction

## UI1 — Define the minimal M1 selector interaction

- **Status:** Open
- **Execution:** CLOUD
- **Priority:** High
- **Category:** Product / UI design
- **Origin:** High-level step 7
- **Depends on:** RE2, RE4, A1, A2
- **Goal:** Choose the smallest understandable way to select and display `Manual`, `Agricultural`, and `Industrial` using the established planet-screen UI seam.

### Design constraints

- must be discoverable enough for a player to understand the current mode;
- must work per selected planet;
- must preserve a clear path back to Manual;
- should minimize new graphics/assets and patch surface for M1;
- may cycle an existing control, add a small selector, or use another interaction justified by the confirmed UI implementation;
- must not require differentiated profile policy logic yet.

### Deliverables

- concise UI behavior specification;
- state-transition diagram/table in docs or tests;
- exact implementation seam(s) from established RE evidence;
- update UI2 if the chosen interaction changes its scope.

### Acceptance criteria

An implementation agent can build the interaction without inventing labels, transition semantics, or how the current planet's mode is displayed.

---

## UI2 — Implement per-planet Manual / Agricultural / Industrial selection

- **Status:** Open
- **Execution:** CLOUD
- **Priority:** Critical
- **Category:** Feature implementation / state + UI
- **Origin:** High-level steps 6–7
- **Depends on:** A1, A2, P1, P2, UI1
- **Goal:** Implement the M1 state machine and UI integration for three per-planet modes.

### Required behavior

- each player-owned planet can independently hold one of the three M1 modes;
- selecting a planet displays its current mode;
- player input can transition among the modes according to UI1;
- `Manual` maps to the original non-automated behavior;
- both `Agricultural` and `Industrial` map to the original automated/self-management behavior for M1;
- the profile identity remains distinct even though the two automated modes share behavior;
- switching planets must not leak one planet's profile into another;
- state remains valid for the current running session under the lifecycle established in A1.

### Testing

Add all logic that can be tested without the game to synthetic/unit tests, especially:

- mode encoding/decoding;
- per-planet lookup/lifecycle rules;
- transitions;
- mapping `Agricultural|Industrial → existing automated semantics`;
- invalid/corrupt state fallback;
- patch-location/version validation.

Do not claim M1 complete until V1 runs on the target.

### Deliverables

- feature implementation;
- tests and fixtures;
- updated documentation for install/remove and known limitations;
- roadmap status `Implemented, validation incomplete` if target validation has not yet occurred.

### Acceptance criteria

The patch/build output contains the full intended M1 behavior and passes all cloud/synthetic checks, with remaining target-only evidence explicitly delegated to V1.

---

# Track V — Milestone validation

## V1 — Validate M1 end to end on the canonical target

- **Status:** Investigation first
- **Execution:** GATED — CF4 must change this to `CLOUD` or `LOCAL ONLY`
- **Priority:** Critical
- **Category:** End-to-end validation
- **Origin:** Milestone exit criteria
- **Depends on:** UI2, CF4
- **Goal:** Establish runtime evidence that Manual / Agricultural / Industrial selection works correctly for multiple planets in a real running game session.

### Required scenario

Use the exact canonical Antagonizer hash and the reproducible validation harness defined by CF4. At minimum demonstrate:

1. start from an unmodified/supported target and apply the mod;
2. open one player-owned planet and set `Agricultural`;
3. open a different player-owned planet and set `Industrial`;
4. revisit both planets and confirm each displays its own mode;
5. advance at least one turn and confirm the mode identities remain stable;
6. establish that both automated modes still follow the game's existing self-management path for M1;
7. return one planet to `Manual` and confirm normal manual behavior/state is restored;
8. remove/rollback the mod and confirm the target returns to the expected original state.

Add additional checks discovered by RE/implementation if they are necessary to exclude corruption, aliasing, crashes, or lifecycle errors.

### Deliverables

- target hash and exact mod build identifier;
- reproducible validation record under `docs/experiments/`;
- screenshots/logs/state traces or other bounded evidence defined by CF4;
- update UI2 and milestone status based on observed results;
- any failures become new bounded roadmap items rather than being hidden in PR prose.

### Acceptance criteria

All M1 behaviors are observed on the canonical target with no known corruption/crash/regression in the tested scenario, and rollback is verified.

---

# Milestone M1 exit checklist

M1 may be marked **Completed and verified** only when all of the following are true:

- canonical Antagonizer target is identified by exact hash;
- the existing per-planet self-management state and per-turn consumption path are established with sufficient evidence;
- the chosen patch mechanism is version-gated, fail-closed, reproducible and reversible;
- Manual / Agricultural / Industrial are distinct per-planet states in the mod;
- both automated profile states preserve existing self-management behavior for M1;
- the planet UI can select and display all three states;
- two different planets can hold different automation profiles simultaneously;
- profile identity survives turn advancement within the current session;
- returning a planet to Manual works;
- target-runtime validation is recorded against the canonical hash;
- install/remove/rollback behavior is documented and verified;
- all significant RE findings and negative experiments are preserved in the repository.

---

# Explicitly after M1

Do not pull these into M1 unless new evidence proves they are inseparable:

1. **M2 — Differentiated policies**
   - define and implement actual Agricultural and Industrial planning rules;
   - decide whether policy selects one action, a build queue, tile development, or another action model;
   - build deterministic policy tests from synthetic planet states;
   - validate decisions against real game states.

2. **Additional profiles**
   - Scientific is the obvious next candidate;
   - add other profiles only when they represent a useful strategic player intent rather than arbitrary AI complexity.

3. **Save-game persistence**
   - persist profile identity across save/load;
   - prefer backward-compatible or external/mod-owned persistence unless evidence supports a safe save-format extension.

4. **Policy transparency and controls**
   - explain why the governor chose an action;
   - allow constraints or protected buildings only if real play demonstrates the need.

5. **Additional binary versions**
   - support other Antagonizer/vanilla releases only after M1 is stable on one canonical target;
   - every additional target must have its own compatibility evidence and fail-closed validation.

---

## Roadmap maintenance rules

The PR that changes reality must change this roadmap in the same PR.

Examples:

- a feasibility task establishes cloud DOS execution → convert its gated runtime tasks to `CLOUD` and link the harness;
- cloud runtime fails for a concrete, reproduced reason → mark the relevant task `LOCAL ONLY`, preserve the experiment, and provide the one-shot local artifact workflow;
- runtime evidence disproves a state-field hypothesis → update RE2/RE4 and dependent architecture tasks before implementing anything;
- implementation exists but target validation is pending → use `Implemented, validation incomplete`;
- a task premise is invalid → mark it `Superseded` or `Dropped` and preserve why.

Do not silently delete negative results, broaden tasks during execution, or treat a guessed function name/offset as established merely because an implementation appears to work synthetically.
