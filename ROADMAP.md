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

The intended production target is the **Antagonizer** executable because the project wants to extend its existing planetary self-management rather than rebuild vanilla AI behavior. The original/vanilla executable is useful as a reference for differential analysis.

### Established by CF1 (static / reported)

- The Antagonizer is a **standalone complete game executable** (`ANTAG.EXE`), copied beside the retail `ASCEND.EXE` and run instead of it. It is not a patcher, not a data file, and not stacked on top of a base executable.
- The publisher's official bug patch has the same shape: `PATCH.EXE` (version 1.6.5, English) and `F_PATCH.EXE` (version 1.8.5, non-English) are also standalone full builds.
- Both were distributed free of charge by The Logic Factory and are lawfully fetchable in cloud; the retail game **data** files are not.
- Container format: DOS `MZ` stub at offset 0, Linear Executable (`LE`) image at `e_lfanew = 0x2a50`, bound DOS/4G extender. Not PE.

### Still assumptions

These are project directions, not yet binary facts. Until the remaining target-baseline tasks complete, do not assume:

- which of the four CF1 candidates is the canonical M1 target and baseline (T1 decides);
- the load layout, segment/selector mapping, architecture details beyond the LE container, or DOS extender runtime behavior;
- that the size difference between the Antagonizer and bug-patch images is explained by the AI changes;
- that a particular address or function is stable between the baseline and Antagonizer;
- that the auto-management state is a field in the planet object;
- that the existing UI toggle directly writes the persistent state;
- that the safest implementation is an on-disk patch, runtime hook, loader, TSR, or any other specific mechanism.

All binary-specific findings must name the exact target hash.

---

## Dependency overview

The expected critical path is:

`CF1/CF2/CF3 → T1/T2 → RE1 → RE2 + RE3 → RE4 + RE5 → A1/A2 → P1/P2 → UI1/UI2 → V1 → M1`

`CF4` may run after `CF3` and gates visual/end-to-end UI validation.

Cloud-feasibility tasks are intentionally near the front so later work is not unnecessarily pushed to a local machine.

**Current front of the path:** CF1 is complete. The immediately available items are **CF2** (highest information — it is the only remaining gate on `T2 → RE1 → RE2/RE3`), **CF3**, and **T0**.

T1 is now classified `CLOUD` but is **not yet selectable**: it depends on T0, which is still `Open`. It becomes available as soon as T0 completes.

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

- the **retail game data files are not obtainable in cloud** and the repository must not try. This is a constraint handed to CF3/CF4, not a blocker for static RE.
- the **retail unpatched `ASCEND.EXE`** is not freely distributed. It is an optional third reference, not a prerequisite.
- CF1 settled the **packaging** relationship between the bug patch and the Antagonizer (both standalone executables), **not** their **build lineage**. Whether the pair is build-comparable is still open and is required evidence for T1 before a baseline is named.
- `web.archive.org` was **blocked by egress policy** in the sandbox where this ran even though `archive.org` was reachable. Do not build tooling on a Wayback fallback without re-probing.
- abandonware full-game sources must never be added to the manifest, regardless of reachability.

Consequence for the roadmap: T1 becomes `CLOUD`; T2 and RE1 stay gated on **CF2 only**; CF3 starts from "cloud has the executables but not the data".

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

- **Status:** Investigation first
- **Execution:** CLOUD RESEARCH
- **Priority:** Critical
- **Category:** Cloud enablement / static RE
- **Origin:** High-level step 2
- **Depends on:** None. CF1 is complete, so **real target bytes are available in cloud** — use them rather than the synthetic fixtures this item originally allowed for. Fetch with `python3 tools/fetch_free_targets.py`.
- **Gates:** T2, RE1, RE2, RE3
- **Question:** Can the static analysis needed for this milestone be run headlessly and reproducibly in Codex or Claude cloud rather than requiring an interactive local Ghidra session?

> **Input from CF1:** the targets are DOS `MZ` stubs wrapping a Linear Executable (`LE`) image with a bound DOS/4G extender, not PE files. The toolchain must handle LE/DOS-extender images; a PE-only pipeline will not do. This is the highest-information next task on the critical path.

### Required investigation

Establish the minimum viable toolchain for:

- identifying the executable/container format and architecture;
- producing normalized disassembly/function metadata;
- extracting strings and cross-reference-like relationships where supported;
- comparing vanilla and Antagonizer at function/region level;
- exporting results to stable text/JSON artifacts suitable for review and later cloud tasks.

Ghidra headless is an obvious candidate but is not mandated. A smaller toolchain is preferable if it produces sufficient evidence. Interactive GUI-only workflows do not satisfy this task.

### Deliverables

- reproducible scripts/configuration under `tools/` or `scripts/`;
- a synthetic or redistributable smoke-test fixture and CI-compatible test where practical;
- `docs/experiments/CF2-cloud-static-re.md` with tested tool versions and known limitations;
- updates converting CF2-owned gated tasks to `CLOUD` or `LOCAL ONLY`.

### Acceptance criteria

A fresh cloud environment can run the static-analysis pipeline without manual GUI steps, or the investigation demonstrates a concrete blocker and supplies a minimal local export workflow whose output is consumable by CLOUD tasks.

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

> **Starting condition from CF1:** cloud has the game **executables** but not the **retail data files**, and the game is not sold on any current storefront, so there is no lawful cloud route to a runnable installation. CF3 must therefore answer a narrower question than "can the emulator run the game in cloud": can the *instrumentation* be built and smoke-tested in cloud against a safe fixture, with only the scenario run needing the maintainer's installation? Do not spend effort re-testing whether the data files can be downloaded — CF1 settled that they cannot.

### Required investigation

Investigate a non-interactive or scriptable emulator/debugger setup capable of the evidence this project needs. Relevant capabilities include:

- launching a DOS protected-mode application in the cloud environment;
- deterministic mounting/configuration;
- bounded stdout/log/capture artifacts;
- scripted input or another reproducible way to reach a scenario;
- memory snapshots, breakpoints/watchpoints, debugger logging, or equivalent instrumentation;
- clean process termination and artifact collection.

Do not count “the emulator package installs” as success. The result must be relevant to the kinds of runtime evidence later tasks require.

### Deliverables

- `docs/experiments/CF3-cloud-runtime-debugging.md`;
- reusable environment/config/scripts if cloud execution is viable;
- a smoke test using a safe fixture, and target-game smoke test if CF1 provides target access;
- updates converting RE4, RE5, P2 and other CF3-owned gated tasks to `CLOUD` or `LOCAL ONLY`.

If runtime work becomes local-only, create/identify a one-shot local experiment workflow that produces a compact artifact archive for cloud analysis.

### Acceptance criteria

The roadmap has an evidence-backed execution decision for runtime/debugging tasks and a reproducible handoff in either direction.

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

- **Status:** Open
- **Execution:** CLOUD
- **Priority:** High
- **Category:** Tooling / compatibility
- **Origin:** High-level step 1
- **Depends on:** None
- **Goal:** Define how the project names, fingerprints, and records candidate vanilla and Antagonizer executables before any offsets or patch decisions are accepted.

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

- **Status:** Open
- **Execution:** **CLOUD** — set by CF1. Candidate bytes are fetchable in cloud with `python3 tools/fetch_free_targets.py`; provenance is recorded in [`docs/experiments/CF1-cloud-target-access.md`](./docs/experiments/CF1-cloud-target-access.md).
- **Priority:** Critical
- **Category:** Target baseline
- **Origin:** High-level step 1
- **Depends on:** T0 (**still `Open`** — T1 is not selectable until it completes), CF1 (complete)
- **Goal:** Replace release-name assumptions with exact target identities and provenance.

### Candidate set (established by CF1)

Four candidates, all cloud-fetchable and hash-pinned in `tools/free-target-sources.json`:

| Manifest id | Role | Size | SHA-256 |
| --- | --- | --- | --- |
| `antagonizer-en` | Antagonizer, English | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `antagonizer-intl` | Antagonizer, non-English | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `bugpatch-en` | Official bug patch 1.6.5, English | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `bugpatch-intl` | Official bug patch 1.8.5, non-English | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

### Required evidence

For the chosen Antagonizer production target and vanilla comparison reference, record:

- exact SHA-256 and size;
- filename and meaningful release/patch provenance;
- **build/version lineage relationship between the chosen Antagonizer target and the chosen comparison baseline** — established from evidence, not assumed. This is a required output, not an optional note (see below);
- detected executable format/architecture/extender facts from T0;
- whether the files are directly available to cloud agents or require a handoff.

### Baseline selection requires lineage evidence

CF1 settled only the **packaging** relationship: the Antagonizer and the bug patch are separate standalone executables, not a patch stacked on a base. It did **not** settle the **build-lineage** relationship — whether the two were compiled from comparable source snapshots.

That distinction decides whether RE1 is meaningful. If the chosen pair comes from different snapshots, a whole-image differential will surface unrelated bug fixes mixed in with the AI changes, and a ranked "candidate self-management regions" map built on it could be substantially wrong while looking plausible.

So T1 must not select a baseline on availability alone. Before naming the pair it must either establish comparable lineage or record explicitly that comparability is unproven and constrain RE1 accordingly.

Candidates, with their standing:

- the official bug-patch executable is cloud-available and is the **leading candidate**, but it is *not* a default to be adopted without lineage evidence;
- the retail unpatched `ASCEND.EXE` is **not** freely distributed and would require a maintainer handoff of metadata only. Treat it as optional; do not block T1 on it.

Evidence available so far, weak and not sufficient on its own: zip member timestamps pair the non-English bug patch (1995-11-20 17:09:06) and non-English Antagonizer (1995-11-20 17:56:42) 47 minutes apart, while the English pair sits ~2 months apart (1995-11-20 vs 1996-01-25). That gap is a live reason to doubt English-pair comparability, not a footnote. Against it, the English release is the one the publisher documents most fully. Container timestamps are weak build provenance; look for stronger signals with T0/T2 — embedded version or build strings, extender/toolchain fingerprints, section layout, and the size delta (610863 vs 587451) — and record the reasoning either way.

If lineage cannot be established, say so and hand RE1 the constraint rather than an unqualified baseline.

If more than one commonly relevant Antagonizer binary exists, choose one canonical M1 target and list others as future compatibility candidates rather than silently broadening M1.

### Deliverables

- completed canonical entries in `docs/re/targets.md` and target manifest;
- an experiment/source record explaining target selection;
- roadmap updates removing any now-invalid format/version assumptions.

### Acceptance criteria

Every later binary-specific task can name one exact Antagonizer hash as the M1 production target and one exact vanilla hash as its comparison baseline.

---

## T2 — Produce a reproducible static-analysis bundle

- **Status:** Investigation first
- **Execution:** GATED — **CF2 only**. CF1 is resolved: target bytes are cloud-fetchable via `tools/fetch_free_targets.py`, so the remaining question is purely the headless toolchain.
- **Priority:** High
- **Category:** Tooling / static RE
- **Origin:** High-level step 2
- **Depends on:** T1, CF2
- **Goal:** Make target static analysis reproducible enough that later agents do not depend on one person's interactive RE database.

### Work

Using the CF2 toolchain, generate stable analysis outputs for both canonical binaries. Prefer reviewable machine-readable/text artifacts over opaque project databases.

Useful outputs may include:

- segment/section/load maps;
- strings and references where available;
- normalized function/start-address inventories;
- imports/runtime/library indicators if applicable;
- call edges or other comparable relationships;
- disassembly/decompiler snippets only where needed and legally appropriate;
- tool versions and exact commands.

Avoid bulk committing copyrighted disassembly if a smaller derived representation is sufficient.

### Deliverables

- scripts to regenerate the bundle;
- repo-safe derived artifacts under `docs/re/` or another documented location;
- `docs/experiments/T2-static-analysis-bundle.md`.

### Acceptance criteria

A later CLOUD task can reason about target structure and reproduce the relevant derived outputs without relying on undocumented local GUI state.

---

# Track RE — Understand existing self-management

## RE1 — Build a vanilla ↔ Antagonizer differential map

- **Status:** Investigation first
- **Execution:** GATED — **CF2 only**. CF1 is resolved: both sides of the diff are cloud-fetchable.
- **Priority:** High
- **Category:** Reverse engineering / differential analysis
- **Origin:** High-level step 3 and the decision to use vanilla as a reference
- **Depends on:** T2
- **Question:** Which code/data regions changed between canonical vanilla and Antagonizer, and which changes are plausible candidates for the documented improvement in planetary self-management?

> **Refinement from CF1:** "vanilla" here means the baseline T1 selects — most likely the publisher's official bug-patch executable rather than the retail `ASCEND.EXE`, which is not freely distributed. Both are standalone full builds of the same game and are close in size (610863 vs 587451 bytes), which is what makes a whole-image differential tractable.
>
> **Two things this item must not assume.** First, that the pair is build-comparable: T1 owes lineage evidence, and if it reports comparability as unproven, RE1 must treat unrelated bug fixes as an expected confound and weight candidates accordingly instead of reading every difference as AI-related. Second, that the size delta is explained by the AI changes — the Antagonizer image is the *larger* of the two, which is consistent with added behavior but also with an unrelated build difference. Test it; do not assume it.

### Work

Use normalized/static analysis rather than raw byte diff alone. Rank candidate changed functions/regions using evidence such as strings, call relationships, data references, UI proximity, or known self-management behavior. Do not name a candidate `ManagePlanet` merely because it looks plausible.

### Deliverables

- `docs/re/vanilla-antagonizer-diff.md` with a ranked candidate map;
- machine-readable diff output or scripts where useful;
- explicit hypotheses and confidence level;
- negative findings that materially narrow the search.

### Acceptance criteria

The next RE tasks have a bounded set of candidate regions and a reproducible explanation of why they are candidates. No candidate is presented as confirmed behavior without supporting evidence.

---

## RE2 — Identify the existing auto-management UI/state seam statically

- **Status:** Investigation first
- **Execution:** GATED — CF2/T2 must resolve the analysis path
- **Priority:** Critical
- **Category:** Reverse engineering / planet state / UI
- **Origin:** High-level steps 3–4
- **Depends on:** T2, RE1
- **Question:** What code path handles the existing per-planet self-management control, and what state representation is most likely changed or consulted?

### Work

Trace the control from whatever static anchors are available: rendering/input handlers, strings/resources, candidate call sites, selected-planet references, and state reads/writes. Keep competing hypotheses alive if static evidence cannot distinguish them.

At minimum attempt to identify:

- candidate UI input handler(s);
- candidate selected-planet/object relationship;
- candidate auto-management read/write location(s);
- candidate code sites suitable for runtime instrumentation in RE4.

### Deliverables

- `docs/re/auto-management-ui-state.md`;
- annotated candidate sites tied to exact target hash;
- a minimal runtime experiment specification for RE4 that maximizes information gain.

### Acceptance criteria

RE4 can be executed as a bounded experiment rather than an open-ended debugger session.

---

## RE3 — Identify the per-turn self-management decision path statically

- **Status:** Investigation first
- **Execution:** GATED — CF2/T2 must resolve the analysis path
- **Priority:** Critical
- **Category:** Reverse engineering / turn processing
- **Origin:** High-level step 3
- **Depends on:** T2, RE1
- **Question:** Which call path reads planet self-management state and decides/builds the next automatic planet action during turn processing?

### Work

Use the differential map and state candidates from RE2 to find reads/callers that occur in turn-processing or colony-management paths. Distinguish:

- “is this planet automated?” state checks;
- decision/policy code;
- action execution/build-queue code;
- generic AI code shared with non-player empires, if evidence supports such sharing.

Do not require full reconstruction of the AI algorithm. M1 only needs a safe seam that lets two profile identities continue to invoke existing self-management.

### Deliverables

- `docs/re/auto-management-turn-path.md`;
- candidate call graph/data-flow description tied to target hash;
- a minimal runtime confirmation plan for RE5.

### Acceptance criteria

There is a falsifiable hypothesis for where mode state is consumed each turn and how existing self-management is reached.

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
