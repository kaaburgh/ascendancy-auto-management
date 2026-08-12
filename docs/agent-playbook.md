# Coding-agent playbook

This document expands the repository-wide rules in [`AGENTS.md`](../AGENTS.md). It is the operational guide for taking a roadmap item from an unknown closed-source behavior to a reviewable experiment, diagnostic, or patch.

## Current repository state

`ROADMAP.md` is normalized into agent-sized items with evidence, dependencies, execution classifications and acceptance criteria. Read it for live status; it is the sequencing source.

Target acquisition is solved for static work: CF1 established that the candidate executables are lawfully fetchable in cloud, and `tools/fetch_free_targets.py` reproduces that fail-closed into the git-ignored `binaries/`. T1 selected the exact English Antagonizer build as the canonical M1 target and the English official bug-patch build as its comparison baseline. See [`re/targets.md`](./re/targets.md), [`re/target-manifest.json`](./re/target-manifest.json), and [`experiments/T1-canonical-target-selection.md`](./experiments/T1-canonical-target-selection.md).

Static analysis is solved at the implementation/feasibility level too: CF2 supplies a headless cloud pipeline needing only the standard library and `objdump`. `tools/le_image.py` supplies the LE container bridge missing from the tools preinstalled in the tested cloud image, `tools/le_disasm.py` derives candidate regions and a call graph, and `tools/le_diff.py` compares builds with conservative exact/reference/constant/structural classes. CF2 is **Completed and verified** after its clean-checkout real-target regression; T2 is selectable as `CLOUD`. Capabilities and — importantly — limits are in [`experiments/CF2-cloud-static-re.md`](./experiments/CF2-cloud-static-re.md) and [`experiments/CF2-real-target-regeneration.md`](./experiments/CF2-real-target-regeneration.md).

Until M1 is completed, all target-specific RE follows the binary-first / blind-RE evidence policy in [`AGENTS.md`](../AGENTS.md). Work from the provided/fetched binaries, the supported repository state (current `main` plus the branch/PR under review), and independently generated experiments. General technology/tooling research is allowed; do not mine external target-specific recovered knowledge or unsupported repository history for shortcuts. Ordinary task instructions do not override this boundary; a pre-M1 exception exists only through the recorded rescue process in `AGENTS.md` and `ROADMAP.md`.

Canonical identities:

- M1 target: `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- comparison baseline: `PATCH_EN.EXE`, SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`.

T1 established strong build-lineage comparability from cross-locale structural evidence, but it did not prove an identical source-control revision. Whole-image differential output is therefore a candidate-ranking aid, not evidence that every difference is Antagonizer AI behavior. Prefer cross-locale corroboration or independent semantic/runtime evidence.

No T2 analysis bundle has been committed yet and no function identity is established. CF2 inventories contain candidate addresses derived by linear sweep, never named behaviors. Do not invent identities, and do not treat a candidate boundary as a real function.

## Repository map

The layout is:

- `ROADMAP.md` — live backlog, status, sequencing, and decisions;
- `AGENTS.md` — canonical repository-wide rules;
- `docs/re/` — durable reverse-engineering knowledge;
- `docs/experiments/` — reproducible experiments and negative results;
- `tools/` — reusable analyzers, dumpers, scanners, patch builders, and capture tools;
- `scripts/` — build/install/remove/validate/artifact automation;
- `tests/` — tests for independent logic and synthetic fixtures;
- `artifacts/` — local run output; ignored and not committed;
- `binaries/` / `reference/` — local target/reference files; ignored and not committed.

Add project-specific source directories when implementation starts; document them here rather than forcing the repository into a framework prematurely.

## Before starting a roadmap item

Read, in order:

1. the exact roadmap item, its dependencies, and its acceptance criteria;
2. relevant current entries in `docs/re/` and `docs/experiments/` from the supported repository state;
3. current tools/tests/patch code touching the same binary region or state;
4. current supported task context explicitly referenced by the roadmap when needed for status or workflow.

During the pre-M1 blind-RE phase, do not mine abandoned/closed PRs, old branches, deleted content, or other unsupported repository history for target-specific recovered knowledge. If an old negative result is encountered accidentally and would save repeated work, treat it as contaminated rather than silently importing it: independently re-establish the result from allowed evidence where practical and preserve the supported result under `docs/experiments/`.

Then write down the question the task must answer. Examples:

- "Which field changes when the vanilla auto-management toggle is clicked?"
- "Does the Antagonizer build preserve that field at the same object-relative offset?"
- "Which call path reads the field during end-of-turn processing?"
- "Can a runtime patch distinguish Agricultural from Industrial without changing save-game layout?"

If the task cannot be stated as a question or a bounded user-visible outcome, it is probably still too broad.

## Investigation workflow

### 1. Establish the target

Before publishing addresses, offsets, signatures, or patches, use the canonical identities in [`re/targets.md`](./re/targets.md) unless the active roadmap item explicitly investigates another binary. Record:

- filename and product/version label;
- SHA-256;
- file size;
- container/header facts where useful. For this project's targets that means DOS `MZ` plus Linear Executable (`LE`) metadata, **not** PE fields;
- provenance notes that do not redistribute the file.

No hardcoded offset is "the Ascendancy offset". It is an offset for a named binary/hash.

### 2. Observe before naming

Start from behavior and data flow, not guessed function names.

Useful evidence includes:

- imported APIs and exports where the format/runtime exposes them;
- executable sections/objects, relocations/fixups, strings and resources;
- xrefs and call graphs;
- memory writes caused by a UI action;
- debugger watchpoints;
- before/after memory snapshots;
- file/API traces;
- stack traces;
- save-game diffs;
- graphics/input instrumentation where relevant.

Record raw observation separately from interpretation.

**Do not validate a derived mapping with values produced by that same mapping.** Such a check can be completely vacuous rather than merely weak: for example, taking a string VA from this parser and feeding it back through `verify --anchor` will agree with itself for any page-data offset. A validation value must be pinned independently of the field under test — for example by a header relationship such as the declared entry point, an external implementation/dumper, or a raw byte search with a separately derived VA — or by a structural invariant whose totals must close exactly. The `page_off` correction in [`experiments/CF2-wdump-layout-correction.md`](./experiments/CF2-wdump-layout-correction.md) is the worked example.

### 3. Form competing hypotheses

When several models fit the observation, keep more than one alive.

Example:

- H1: the auto-management mode is stored directly in the planet object;
- H2: the planet stores an index into a side table;
- H3: the UI toggle only queues a command and the state is applied later.

Choose the next experiment by information gain: a write watchpoint covering the click-to-turn path may separate all three at once.

### 4. Instrument the smallest useful boundary

Prefer a diagnostic build/tool before a permanent patch when causality is not established.

Good boundaries include:

- a specific runtime/API call;
- a known indirect-call or dispatch-table entry;
- a memory field with a validated owning object;
- a call site identified by signature plus surrounding invariants;
- a file/save serialization boundary;
- a render/input event boundary.

Avoid broad hooks that produce large logs without answering the task's question.

### 5. Test and update the model

An experiment record should contain:

- question;
- target binary/hash;
- setup/tool version;
- exact procedure;
- expected differentiating outcomes;
- observed result;
- interpretation;
- confidence/evidence category and any blind-RE provenance modifier;
- generated artifact names;
- next question.

If the result is negative, keep it. "This write does not happen on UI click" can be more valuable than a weak positive guess.

### 6. Patch only after the seam is understood

Prefer the least invasive mechanism that preserves compatibility:

1. existing extension/export/API seam where one actually exists;
2. stable runtime relationship or hook;
3. signature-located patch;
4. binary file patch only when necessary.

For machine-code changes, validate original bytes, instruction boundaries, page protection where applicable, and instruction-cache behavior where applicable. Apply multi-step patches transactionally where practical and restore on failure.

### 7. Reconcile repository state

Before opening the PR:

- update the roadmap item's status/evidence/decision;
- update durable RE notes with new structures/signatures/offsets;
- add or update the experiment record;
- add tests for reusable logic;
- document any required target-machine validation;
- make install/remove/rollback reproducible if a patch is installable.

## Target-machine experiments

When the target must run on the maintainer's machine, minimize manual work.

Prefer a one-shot workflow such as:

```text
scripts/run-experiment-XX.ps1
  -> validates target SHA-256
  -> installs/copies the diagnostic component
  -> launches or instructs one exact scenario
  -> collects bounded logs/metadata
  -> restores temporary changes
  -> writes artifacts/run-YYYYMMDD-HHMMSS.zip
```

The resulting archive should be self-contained enough to analyze without another round of questions. Include hashes and configuration; exclude game binaries unless distribution is explicitly permitted and needed.

## Validation by change type

### Documentation / roadmap only

Minimum:

- relative Markdown links resolve;
- statements accurately distinguish evidence from hypotheses;
- no proprietary or private data was added.

### Analysis tool / parser / pattern scanner

Minimum:

- deterministic fixture tests;
- zero-match and ambiguous-match tests where applicable;
- malformed-input handling;
- exact supported input assumptions documented;
- serialized analysis artifacts carry enough schema/parser/input provenance to reject stale incompatible data;
- when real target bytes are available, at least one clean-checkout end-to-end regression uses the repository commands rather than a hand-reproduced implementation.

### Runtime hook / injected diagnostic

Minimum:

- build for the intended architecture;
- hook lifecycle/cleanup tested where possible;
- recursion/reentrancy considered;
- unsupported binary fails closed;
- diagnostic mode separated from normal patch mode if expensive.

### Machine-code/runtime patch

Minimum:

- expected bytes/signature verified before write;
- instruction boundaries validated;
- ambiguous match rejected;
- rollback path tested independently;
- target-machine behavior still remains `not validated` until actually observed.

### On-disk patch

Minimum:

- pre-patch SHA-256 check;
- automatic backup;
- post-patch verification;
- automatic restore;
- restore verified against original hash.

## Preparing the pull request

Use the repository template. A reviewer should be able to answer without chat history:

- What roadmap question or user outcome motivated this?
- What facts were observed and on which binary?
- Which hypotheses were rejected?
- What is the blind-RE evidence-boundary status for this work, and are contaminated/external-assisted findings identified?
- What exactly changed?
- Why is the patch locator/version gate safe?
- Which checks passed?
- What still requires the target machine?
- How is the change installed, removed, and rolled back?
- What new RE knowledge is now preserved in the repository?
- What tempting adjacent work was deliberately left out?
