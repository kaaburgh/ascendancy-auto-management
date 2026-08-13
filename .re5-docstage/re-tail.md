## RE5 runtime confirmation and reopened Manual-gate question

Evidence class: **runtime**. Blind-RE provenance: **clean**. Full procedure, historical observations, and the 2026-08-13 perturbation follow-up are in [`../experiments/RE5-runtime-turn-path.md`](../experiments/RE5-runtime-turn-path.md).

### Runtime relationships that remain established

On the exact canonical target and pinned `resume.gam`, the same player planet `Xerxes I` starts with owner `+0x57 == 0`, empty selected/current action (`+0x52 == 0xffff`, `+0x54 == 0xff`), and RE4-confirmed Manual/Managed state in dword `+0x5a`. The follow-up preserves these causal relationships:

- **Managed reaches the RE3 gate-to-policy call site.** With `+0x5a == 0xffffffff`, the exact whole-call replacement at static `0x3c118` records the marker on `Xerxes I`; the fresh fixed-window run first observed it at `25.946 ms`.
- **`0x3c118 -> 0x3d8f0` remains necessary for the tested Managed automatic action.** Replacing the complete call (`e8 d3 17 00 00`) with five NOPs leaves Managed set while selection/action remain empty; the fresh independent stardate witness advances `0 -> 233` over `7009.080 ms`.
- **Managed control still selects and commits.** A fresh run reaches `+0x52 = 0x0034`, `+0x54 = 0x00` at the first mutation sample (`3850.656 ms`) while `+0x5a` stays `0xffffffff`.
- **`0x34df2` remains a current-action commit seam.** Suppressing the complete `88 46 54` write preserves upstream selection (`+0x52 = 0x003b` in the fresh run) while `+0x54` remains `ff`; stardate advances by `208` in `7020.877 ms`; the selection was first observed at `4031.758 ms`. The varying selected-slot values are opaque observations, not reconstructed semantics.
- Diagnostic instruction apply/verify and restore/re-verify occur only while DOSBox is confirmed stopped; all fresh patched scenarios restored and re-verified original bytes.

The original exploratory result also remains valid: suppressing only `0x3df88 -> 0x34b0c` did not prevent the tested action, so that single call site is not promoted to the unique policy-to-mutation edge.

### Stardate witness and marker perturbation

The runtime-only dword at RE2-anchor-relative `+0x5e657` remains an exact-target progress witness; it is not published as a guessed DOS/4G guest/static address. Fresh controls now show:

- `manual-control`: `0 -> 232` in `7015.295 ms`;
- `managed-policy-suppressed`: `0 -> 233` in `7009.080 ms`;
- `managed-action-write-suppressed`: `0 -> 208` in `7020.877 ms`;
- `managed-gate-probe`: `0 -> 1` in `7002.031 ms`;
- `manual-gate-probe`: `0 -> 1` in `30017.889 ms`.

The cleanest isolating pair is Managed↔Managed at the same `0x3c118` site: five NOPs produce `+233` stardate progress, while replacing the same call with the process-wide `mov [edx+0x54],0x7e` marker produces only `+1` over essentially the same seven-second window. This strongly establishes **instrumentation-induced progression suppression**. It must not be reported as a game-performance defect.

### Why the Manual/override conclusion is reopened

RE3 statically shows that a current-player Manual planet can bypass zero `+0x5a` only through the separate override branch. The earlier RE5 marker run saw no marker on Manual `Xerxes I` while stardate advanced one unit and therefore treated the override as inactive in that pinned run. The precommitted follow-up deliberately demanded stronger evidence because the marker perturbation was suspicious.

Before the follow-up, the pinned save was checked structurally around the unique Xerxes record:

- immediate `Xerxes ± 0x7b` records are `Stavern IV` and `Xerxes II`, both owner `0xff` (unowned), so they cannot serve as owner-gated `0x3c118` witnesses;
- `Xerxes I` is the only owner-`0` planet in the pinned save, so no two-sided same-player bracket is available;
- nearest structurally validated owned records on opposite sides are `Stavern I` (`-4 * 0x7b`, owner `1`) and `Hurble I` (`+8 * 0x7b`, owner `5`). Both were marked during the fresh Manual and Managed probe runs, but they belong to other race loops and are **supplemental cross-race telemetry only**. No array base/count is inferred.

The agreed fallback for Manual therefore required four stardate increments if Xerxes remained unmarked. The fresh Manual probe ran to its `30 s` hard ceiling, kept Xerxes `+0x52/+0x54` empty and never observed the marker, but reached only `delta = 1`; both cross-race telemetry records were marked. This outcome is **inconclusive by the precommitted oracle**: it shows the shared site is active elsewhere, but it does not establish that the player-race loop traversed the Xerxes position under a sufficiently strong non-perturbed control.

Consequently the stronger former statement “the override bypass is runtime-confirmed inactive in the pinned Manual scenario” is withdrawn. The override's broader semantics and trustworthy runtime value/address remain unknown.

### Evidence/artifact contract

The follow-up separates:

- `artifact_schema` — JSON structure;
- `runner_revision` — exact git SHA provenance, not an automatic compatibility discriminator;
- per-scenario `scenario_contract` — observation/oracle semantics.

Gate probes use explicit policies: Managed is a fixed seven-second window; Manual uses target `4` or timeout `30 s`. Marker reachability is represented as `marker_seen`/`first_marker_ms` rather than inferred from the final byte. Cross-race marker telemetry is accumulated as an ever-seen union so transient marker writes are not lost.

All six fresh focused JSON files exist, but the Manual gate artifact is `inconclusive`. The schema-3 aggregator therefore fails closed and does not emit a causal `run-aggregate.json`; no historical artifact is reconstructed from documentation.

### Current preservation-seam status

The runtime-established Managed decision/commit layering still makes **before `0x3c118`** the strongest candidate M1 compatibility seam: leave `0x3d8f0` and downstream selection/action mutation intact rather than reimplementing the existing AI. However this is no longer an unlocked architecture contract. The Manual/override reachability discriminator is still open, so RE5 requires another, less perturbing witness before dependent A1/A2 work may rely on the completed-gate claim.

A useful next experiment should maximize information gain without process-wide action-state stamping: either directly establish the override condition with a trustworthy runtime relationship or observe player-loop reachability using instrumentation that preserves normal `+0x54` semantics. Do not strengthen the current claim by merely extending the mutating marker window.
