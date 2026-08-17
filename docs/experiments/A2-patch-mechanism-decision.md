# A2 — patch mechanism decision experiment

Date: 2026-08-17  
Roadmap item: A2  
Issue: #30  
Blind-RE provenance: **clean**  
Evidence classes used here: existing `static`, `runtime`, and `synthetic` evidence only; this note adds no new target-runtime claim.

## Question

What is the smallest experiment that can turn A2 from an architecture preference into an evidence-backed choice of one M1 patch/integration mechanism?

A2 is still `Investigation first`. This slice deliberately does **not** select a mechanism yet. The current repository proves enough about the target and cloud runtime to reject several assumption-driven shortcuts, but it does not yet establish the code/data capacity and loader behavior needed to choose safely between an out-of-place transformed executable and a runtime-side integration mechanism.

## Target and evidence boundary

Canonical M1 target:

- `ANTAG_EN.EXE`
- SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`
- 610863 bytes
- DOS `MZ` stub wrapping a 32-bit 80386 Linear Executable (`LE`) image under a bound DOS/4G-family runtime.

The load-layout facts used below come from [`../re/targets.md`](../re/targets.md) and the CF2/T2 handoff. The cloud execution/debugging capability comes from [`CF3-cloud-runtime-debugging.md`](./CF3-cloud-runtime-debugging.md). The M1 automation seam and preservation boundary come from [`../re/auto-management-ui-state.md`](../re/auto-management-ui-state.md) and [`../re/auto-management-turn-path.md`](../re/auto-management-turn-path.md).

No external target-specific recovered knowledge, unsupported repository history, abandoned branches, or closed PRs were inspected for this decision.

## Established constraints that A2 must preserve

1. **Exact-target fail-closed gating is practical.** The canonical executable already has a stable published SHA-256 and reproducible acquisition/verification path.
2. **The production image is LE, not PE.** A Win32 DLL-injection or PE-section mental model is not an acceptable default.
3. **Current static layout has exactly two mapped objects.** Object 1 is code and object 2 is data. Their current layout is established, but the repository does not yet establish that either object contains enough semantically safe spare capacity for M1 additions.
4. **Current enumerated page data reaches EOF.** Therefore there is no already-established trailing payload region that may simply be treated as free mod storage.
5. **Runtime execution in cloud is available.** The exact target runs under the verified retail fixture in DOSBox, and `dosbox-debug` has an independently demonstrated scripted breakpoint + guest-memory observation capability.
6. **The later M1 patch must preserve the existing automation gate/policy layering.** A2 chooses integration mechanics; it does not redefine the RE4/RE5 behavior model.
7. **A1 and A2 stay independent.** A2 must not bake in a profile-state key/lifecycle contract that A1 has not completed.

## Mechanism families still worth evaluating

### A. Derived executable, patching only already-mapped bytes/pages

This has attractive operational properties: deterministic output, straightforward input-hash gating, easy byte-level expected-value checks, and simple uninstall by retaining/restoring the untouched executable. It also avoids adding a separate resident loader at runtime.

The unresolved question is capacity. Current evidence identifies target seams and mapped objects but does not establish a sufficiently large, semantically disposable code/data region. Choosing this mechanism now would silently assume a code cave or reusable storage that has not been proven.

### B. Derived executable with LE layout growth

This could provide explicit new code/data capacity while keeping installation as one transformed executable. It would require a writer that updates all LE metadata affected by any new/extended pages or objects and then proves that the bound DOS/4G runtime accepts the transformed image.

The repository has a reader/reconstruction model and independent `wdump` agreement for the existing layout, but it has not yet demonstrated a correct LE **writer** or that this exact bound runtime accepts the required growth pattern. Selecting this family before that proof would move loader-format risk into P1 by assumption.

### C. Runtime-side loader / TSR / equivalent external resident mechanism

This avoids rewriting LE layout for added payload capacity, but it introduces a different unproven boundary: how an external DOS/DOS4G-side component safely gains access to the protected-mode target, installs/removes modifications, preserves lifecycle, and remains compatible with the target's extender behavior.

CF3 proves debugger control and observation, not a production resident-integration API. Therefore a runtime-side mechanism is not currently lower-risk merely because it leaves the executable bytes untouched.

## Rejected shortcuts

- **Modern Win32 DLL injection/hooking:** wrong execution model for the established target and unsupported by evidence.
- **Assume a code cave from file growth or zero bytes:** neither the Antagonizer-vs-baseline size delta nor padding alone proves semantically unused executable capacity.
- **Append raw bytes after EOF and branch to them:** current evidence does not show that appended bytes would be mapped/executable by the LE loader.
- **Use the debugger as the shipping mechanism:** CF3 establishes research capability, not an end-user integration path.
- **Patch target bytes without a full input identity + expected-byte/structural check:** violates the repository fail-closed patching contract.

## Decision experiment

Before choosing A, B, or C, run **one bounded capacity-and-loader experiment** with two stages. The experiment is still A2 architecture work; it must not implement profile behavior.

### Stage 1 — static capacity inventory on the exact target

Add a repository tool that consumes only the verified canonical executable and existing LE parser model and emits a machine-readable inventory of candidate patch capacity:

- mapped code/data page ranges and permissions/flags;
- contiguous padding/zero regions, but labeled only as *candidate capacity*, never safe caves;
- direct control-flow references into candidate code ranges using the existing disassembly inventory;
- known durable target seams that later code must reach;
- every candidate's file offset, LE object-relative address, size, and provenance.

The tool must fail closed on the wrong target hash and keep ambiguity explicit. It must not classify a region as reusable merely because no direct reference was found.

### Stage 2 — target-neutral loader-growth control

On a redistributable/synthetic LE fixture, implement the smallest transformation needed to add or extend mapped payload capacity, then independently inspect the output with the existing parser plus `wdump` (or another independent generic LE implementation) and execute the transformed fixture in the cloud runtime.

The control must prove:

- the transformed image is structurally accepted by two independent readers;
- the added payload is actually mapped/executed or mapped/read as declared by the experiment oracle;
- a deliberately malformed header/page mapping fails closed;
- deterministic regeneration produces byte-identical output.

This stage is **synthetic capability evidence only**. It must not be reported as proof that the canonical Antagonizer accepts the same growth until the exact-target experiment exists.

## Decision rule after the experiment

1. If Stage 1 establishes enough independently defensible existing mapped capacity for the bounded M1 payload, prefer **A** because it minimizes loader-format and runtime-resident complexity.
2. Otherwise, if Stage 2 establishes a deterministic and independently validated LE-growth path, carry **B** into one exact-target no-feature proof before A2 is completed.
3. If neither is established, only then promote **C** for a similarly bounded DOS/DOS4G integration feasibility experiment; do not choose it by elimination without proving its protected-mode lifecycle boundary.

A2 is complete only when one family has a concrete install/remove model, exact-target gate, patch-location validation, zero/ambiguous/unexpected-byte failure behavior, capacity model, cloud build/test path, and later UI/policy integration boundary with no unresolved mechanism decision left for P1.

## Validation for this slice

This is a documentation-only investigation slice. Meaningful validation is therefore:

- all relative links in this note resolve;
- every target-specific statement is traceable to current supported repository evidence;
- no proprietary payload, private path, target-specific external recovered material, or unsupported architecture fact is introduced;
- A2 remains `Investigation first`; no P1/P2 implementation or target modification is claimed.

## Roadmap reconciliation

No A2 status, dependency, execution classification, acceptance criterion, or selected mechanism changes in this slice. The roadmap already requires A2 to evaluate exact-target gating, patch-location validation, rollback, capacity, cloud testability, and downstream integration. This note narrows those existing requirements to the next evidence-producing experiment without claiming that the experiment has run or that its result is established.