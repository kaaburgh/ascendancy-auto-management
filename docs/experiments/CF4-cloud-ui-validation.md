# CF4 — cloud UI interaction and visual validation

Date: 2026-08-13  
Roadmap item: CF4  
Blind-RE provenance: **clean**  
Evidence classes used below: `runtime`, `synthetic`, and `reported` as marked.

## Question

Can a cloud agent reliably drive Ascendancy's UI and capture enough bounded visual/state evidence to validate the M1 Manual / Agricultural / Industrial scenario on the exact canonical Antagonizer, without requiring the maintainer to play the scenario manually?

## Inputs and evidence boundary

This investigation used only supported repository state, the project/operator-supplied DOSBox runtime, the official demo fixture, the maintainer-supplied owned English retail installation, and project-generated observations. No external target-specific recovered knowledge, unsupported repository history, or rescue unlock was used.

Exact runtime inputs used for the target-level smoke:

- canonical `ANTAG.EXE`: SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes;
- maintainer-supplied `Ascendancy_DOS_EN.zip`: SHA-256 `e9f1159c15fd50b9455f817470e13cbc6b17e70551793774b4a7b074859ce987`; its immutable runtime files match `tools/retail-runtime-manifest.json`;
- operator-supplied DOSBox 0.74-3 Linux x86_64 runtime bundle: archive SHA-256 `25f8ddae6eb14f01e4b7dd67fa1a3423f5a6f751a906c752bb77250f045f3202`; its bundled `verify.sh` passed before the CF4 runs.

The redistributable control used the official demo `ASCEND.EXE`, SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`, with the CF3-pinned demo file manifest.

## Result

**Cloud path found. V1 is a CLOUD task.**

A bounded X11 harness is enough; no interactive desktop or remote-control session is required. `scripts/run_cf4_ui_validation.py`:

1. verifies every immutable fixture file named by the selected manifest and verifies the exact executable SHA-256;
2. copies the supplied game tree to a temporary mount so UI/save/config writes cannot modify the source fixture;
3. starts its own Xvfb display and DOSBox;
4. waits for the actual 640x480 game window rather than treating DOSBox's initial 640x400 text window as game readiness;
5. drives keyboard chords plus relative mouse motion/buttons through X11 XTEST;
6. captures the exact 640x480 DOSBox window through `ffmpeg`/`x11grab` at named checkpoints;
7. requires at least two captures and rejects a scenario when adjacent captures differ by less than 1% of decoded RGB bytes, which prevents a moved cursor alone from being accepted as a UI transition;
8. writes a bounded `run.json`, sanitized DOSBox logs, and PNG evidence under ignored `artifacts/`.

The action file is deliberately a tiny allow-listed DSL (`wait`, `capture`, `mouse_capture`, relative `mouse_move`, `click`, and `key_chord`). It cannot run arbitrary shell commands. This is enough for V1 while avoiding a general game-automation framework.

## Runtime observations

### Canonical Antagonizer on the pinned retail fixture

`runtime`, clean.

Command shape used in this environment:

```text
python scripts/run_cf4_ui_validation.py \
  --game-dir <owned-retail-tree> \
  --dosbox <dosbox-0.74-3> \
  --exe ANTAG.EXE \
  --expected-exe-sha256 8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00 \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --actions tools/cf4-ui-smoke.json \
  --artifacts artifacts/cf4-retail
```

Observed result: **PASS**. The harness verified all 17 immutable retail-manifest files, observed the 640x480 game window, and drove the exact canonical target from the main menu into the tutorial selector and then into Tutorial #5, *Managing Planets and Research*.

Repo-safe frame metadata from the successful run:

- `01-main-menu.png`: SHA-256 `88175dca98f05fcf7e36c0e2a1595f565c3eb51c882e1d6f97b5fd3142d70fbf`;
- `02-tutorial-list.png`: SHA-256 `4828ae028506d5675740f80ba33a20ec15618d5b88bf7548abb072571f97643c`, decoded-byte change ratio from previous frame `0.797807`;
- `03-tutorial-5-planets.png`: SHA-256 `d5afbb9cacbf31492a53d1761efb5fcc3d5e82c4a5ed49ab3e6f6c79def1e2de`, decoded-byte change ratio `0.785118`.

The final frame visibly contains the Tutorial #5 planets/research scene and its instructional overlay. The screenshots themselves remain local artifacts and are not committed.

### Official demo control

`runtime`, clean.

The demo has one extra pre-video text prompt (`Press a key to continue...`) and only exposes Tutorial #1. `tools/cf4-ui-demo-smoke.json` records that difference as a pre-video `Return` chord and a demo-specific tutorial-selection delta.

Observed result with the supplied pinned demo bytes: **PASS**. The three checkpoints were the main menu, the one-entry tutorial list, and Tutorial #1. Decoded-byte transition ratios were `0.795605` and `0.815082`.

This redistributable path is suitable for a GitHub Actions capability smoke. It proves the cloud image can install/start DOSBox + Xvfb, inject XTEST input, and capture real guest UI transitions without requiring the private retail fixture.

## Negative results and failure modes preserved

`runtime` / `synthetic`, clean.

- Waiting for the first DOSBox X11 window is insufficient: the process initially exposes a 640x400 DOS text window. The harness must wait for a 640x480 transition before declaring the game UI ready.
- The official demo waits at a text-mode `Press a key to continue...` prompt before its 640x480 UI. A cloud smoke that never injects the pre-video key will time out correctly rather than falsely reporting that UI automation is unavailable.
- XTEST absolute pointer motion is not the correct primitive for this DOSBox/game path once the guest owns relative mouse motion. Relative XTEST motion changes the in-game cursor predictably.
- The first mouse button event after focusing the DOSBox window can establish pointer capture rather than activate the intended control. The action model therefore makes `mouse_capture` explicit and separates it from later clicks.
- A frame hash changing is not, by itself, enough evidence of a UI transition because the game cursor is rendered into the guest frame. CF4 therefore requires a minimum decoded-pixel change ratio between adjacent checkpoints.

These details are encoded in the reusable harness/configuration so later agents do not have to rediscover them.

## Exact V1 / M1 validation scenario

V1 must use the exact canonical `ANTAG.EXE` hash above, a source tree that passes `tools/retail-runtime-manifest.json`, and the CF4 harness. The supplied tree is copied before launch; V1 must not mutate the operator's source fixture.

The V1 scenario is fixed as follows:

1. Start from a supported unmodified canonical target and apply the exact mod build under test. Record the mod build identifier and every resulting runtime-patch/binary identity required by the eventual patch mechanism.
2. Enter a pinned validation game state containing **at least two distinct player-owned planets**, identified in the V1 record as `P1` and `P2`. The state may be an operator-supplied save/runtime fixture, but its SHA-256 and provenance must be recorded and it must be supplied as ephemeral input rather than committed if redistribution is not clearly safe.
3. Open `P1`; capture the visible initial `Manual` state.
4. Set `P1` to `Agricultural`; capture the visible selected state.
5. Open `P2`; capture its initial `Manual` state, then set it to `Industrial` and capture the visible selected state.
6. Revisit `P1`; capture that it still displays `Agricultural`.
7. Revisit `P2`; capture that it still displays `Industrial`.
8. Set `P1` back to `Manual`; revisit `P2`; capture that `P2` still displays `Industrial`.
9. Continue/end at least one turn using the normal game path required by the eventual implementation and revisit both planets. Capture `P1 = Manual` and `P2 = Industrial`; if the implementation's mode lifetime intentionally excludes the turn boundary, V1 must fail rather than silently weakening the M1 contract.
10. Remove/disable the mod by its documented rollback path and verify the original canonical target identity is restored when the patch mechanism changes bytes on disk.

The executable input script for these exact UI coordinates/chords cannot be finalized before UI2 determines the actual new controls. UI2 must therefore add a V1 action file using the already-fixed CF4 action schema; it must not invent a different automation mechanism unless CF4's harness proves inadequate. V1 then runs that checked-in action file unchanged and publishes the resulting `run.json` plus named screenshots/log/state traces as its evidence artifact.

For acceptance, screenshots must visibly identify the selected mode at every checkpoint above. If the implementation exposes a cheap structured diagnostic/state trace, V1 should include it and correlate each `P1`/`P2` action with the visual checkpoint; this is additive evidence, not a substitute for the required visible UI state.

## Cloud execution contract for V1

A fresh cloud runner needs:

- Python 3.11+;
- DOSBox 0.74-3 compatible with the CF3 runtime path;
- `Xvfb`, `xwininfo`, `libX11`, `libXtst`/XTEST, and `ffmpeg` with `x11grab`;
- the repository checkout;
- the owned retail tree as ephemeral task input, matching `tools/retail-runtime-manifest.json`;
- the mod build and the V1 validation-state input produced by the later roadmap items.

Missing owned retail/save input is an operator-input handoff, not evidence that the capability is `LOCAL ONLY`. CF3 already established the same rule for exact-target runtime execution.

The checked-in demo smoke provides the public CI capability probe. Exact-target V1 still requires the retail fixture because CF3 established that canonical `ANTAG.EXE` does not run on demo data.

## Validation performed for CF4

- `runtime`: canonical `ANTAG.EXE` + pinned retail fixture + supplied DOSBox 0.74-3 bundle — CF4 tutorial-5 UI smoke **PASS** with three 640x480 captures and two large verified frame transitions.
- `runtime`: pinned official demo `ASCEND.EXE` — demo tutorial-1 UI smoke **PASS** after the required pre-video key, with three 640x480 captures and two large verified frame transitions.
- `synthetic`: focused unit tests cover action-schema allow-listing/bounds, unsafe capture names, minimum capture count, case-insensitive DOS fixture matching, hash mismatch rejection, casefold ambiguity rejection, and PNG dimension parsing.
- `static`: no target-specific addresses, state fields, functions, offsets, calling convention, or patch locations were inferred by CF4.

## Decision

CF4 is **Completed and verified** and V1 changes from `GATED` to **`CLOUD`**.

This decision is limited to UI interaction/evidence capture feasibility. It does not claim that the M1 controls already exist, that profile state is implemented, or that the final V1 action coordinates are known before UI2.
