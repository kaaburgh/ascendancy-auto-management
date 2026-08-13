# CF3 — cloud runtime and debugging feasibility

Date: 2026-08-12  
Roadmap item: CF3  
Blind-RE provenance: **clean**  
Evidence classes used below: `runtime`, `static`, `synthetic`, and `reported` as marked.

## Question

Can the DOS runtime work needed by M1 execute reproducibly in cloud, including the exact canonical Antagonizer when the maintainer supplies the owned retail installation as task input? Which parts can use the freely distributed demo, and can cloud infrastructure provide the breakpoint/state-observation capability later runtime RE tasks require?

## Inputs and evidence boundary

The investigation used only project/operator-supplied binaries, publisher/user-facing demo material, supported repository state, general emulator/tooling information, and project-generated observations. No external target-specific recovered knowledge, unsupported repository history, or rescue unlock was used.

Generic/operator-supplied tooling:

- DOSBox 0.74-3 Linux x86_64 runtime bundle; its `verify.sh` passed before use;
- generic Linux RE toolkit for static tooling only.

Project target/runtime inputs:

- official demo `ASCEND.EXE`: SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`, 582147 bytes;
- canonical M1 target, run under its distribution filename `ANTAG.EXE`: SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes;
- later maintainer-supplied full English installation archive `Ascendancy_DOS_EN.zip`: 42648482 bytes, SHA-256 `e9f1159c15fd50b9455f817470e13cbc6b17e70551793774b4a7b074859ce987`.

The retail archive is task input, not a redistributable project dependency. No retail payload is committed or uploaded by repository automation. `tools/retail-runtime-manifest.json` stores only hashes/sizes for the immutable files required by the canonical runtime fixture so future task attachments can be checked fail-closed.

## Demo acquisition and relevance

The playable demo remains a useful public cloud fixture. `tools/demo-runtime-manifest.json` pins its archive and all extracted files; `tools/fetch_demo.py` rejects wrong archive bytes, missing or case-insensitively ambiguous members, wrong member bytes, and unsafe tracked destinations.

A clean GitHub Actions runner exercised the public acquisition path end to end. The final CF3 Actions run `31631443127`, job `CF3 demo acquisition`, downloaded the pinned archive and re-verified the extracted tree successfully.

The demo contains the feature class relevant to M1. Publisher/user-facing documentation names `<M>` as toggling research and planet self-management, and the supplied demo data contain the user-facing `Self Managed` / planet-screen text. This establishes fixture relevance without inferring implementation details.

## Demo-own headless runtime

`tools/cf3_sdl12_probe.c` and `scripts/run_cf3_runtime_smoke.py` provide a bounded cloud smoke harness. The probe records SDL video-mode transitions, injects only explicitly scheduled keyboard events, and captures selected framebuffers. The runner uses dummy SDL video/audio, a temporary mounted copy, an execution timeout, exact executable hash checks when requested, explicit termination expectations, and a sanitized `artifacts/run-CF3-*.zip` containing metadata/logs/captures but no game payload.

Observed `runtime` result against the pinned demo:

1. DOSBox entered its 640x400 surface.
2. The demo showed its welcome screen.
3. A scheduled Space key advanced it.
4. A **successful** SDL 640x480 mode transition occurred.
5. A captured framebuffer showed the Ascendancy main menu.
6. The process remained alive until the bounded timeout.

The demo therefore proves that protected-mode execution, deterministic mounting, scripted input, bounded framebuffer capture and artifact collection work in this cloud environment.

For a liveness smoke, the equivalent current runner contract includes `--expect-timeout`; `--expect-mode` alone is intentionally insufficient:

```sh
python scripts/run_cf3_runtime_smoke.py \
  --dosbox /path/to/dosbox-runtime/bin/dosbox \
  --game-dir game/demo \
  --verify-demo \
  --expected-exe-sha256 0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9 \
  --key-events '9000:space' \
  --captures-ms '5000,8000,12000' \
  --timeout 14 \
  --expect-mode 640x480 \
  --expect-timeout
```

## Negative result: canonical Antagonizer on demo data

The exact canonical `ANTAG.EXE` was overlaid onto the fully verified demo tree and run with the same DOSBox/runtime probe.

Observed `runtime` result:

- the DOS/4G runtime started;
- only the initial 640x400 DOSBox modes appeared;
- `ANTAG.EXE` returned to the DOS prompt before a successful game 640x480 mode transition;
- the fail-closed 640x480 expectation was not met and a bounded negative artifact was preserved.

This result remains important and must not be erased by the later retail success: **demo data cannot substitute for the retail data when exact canonical Antagonizer runtime evidence is required**. CF3 does not claim which particular data difference causes the early exit.

## Retail follow-up supplied by the maintainer

After the initial CF3 investigation, the maintainer supplied the full English game installation as `Ascendancy_DOS_EN.zip`. The archive contains `ANTAG.EXE` whose SHA-256 exactly matches the canonical T1 target, plus the full-sized retail data files.

The runtime-required immutable fixture is now pinned in `tools/retail-runtime-manifest.json`, including:

- `ANTAG.EXE` — 610863 bytes, `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- `ASCEND00.COB` — 377589 bytes, `7a17cf776b0128c4f716ff6efb38d130470c5316fd9937c500803a97f85472aa`;
- `ASCEND01.COB` — 12385306 bytes, `26ff2e7f6a91a65d878e34d0028872edbf477173a3d236032b77c46f4396e01c`;
- `ASCEND02.COB` — 60787718 bytes, `bd19fe4eb557b0d251a144da0222302735647aa0394e986d4a45ca5f801984f6`;
- the DOS/4G runtime, `COB.CFG`, intro data and required sound drivers, each with exact size/SHA-256 pins.

The manifest intentionally does not make retail data a downloadable dependency and does not commit them. It defines what a maintainer/operator attachment must contain before canonical runtime evidence is accepted.

## Canonical Antagonizer on verified retail data

The full-version-dependent CF3 smoke was repeated with the canonical target and maintainer-supplied retail installation.

Equivalent current repository command:

```sh
python scripts/run_cf3_runtime_smoke.py \
  --dosbox /path/to/dosbox-runtime/bin/dosbox \
  --game-dir /path/to/attached/retail/Ascendancy \
  --exe /path/to/attached/retail/Ascendancy/ANTAG.EXE \
  --verify-retail \
  --expected-exe-sha256 8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00 \
  --key-events '5000:space' \
  --captures-ms '3000,8000' \
  --timeout 11 \
  --expect-mode 640x480 \
  --expect-timeout
```

Observed `runtime` result:

1. `--verify-retail` accepted the supplied fixture against the committed pins.
2. DOSBox entered 640x400 (bpp 0, then 32).
3. The exact canonical `ANTAG.EXE` remained alive rather than returning to the DOS prompt.
4. A scheduled Space key at about 5 seconds advanced the program.
5. The canonical target completed a successful 640x480 bpp 32 `SDL_SetVideoMode` at about 6 seconds.
6. The 8-second framebuffer capture was 640x480 and showed the Ascendancy main menu.
7. The bounded run ended by the expected timeout rather than target crash/exit.
8. Artifact metadata recorded retail verification, exact target identity, successful/failed mode status, the termination expectation/result and captures, without embedding retail files or host source paths.

This establishes the missing CF3 fact: **the exact canonical Antagonizer runtime is viable in cloud when the maintainer supplies the owned retail installation as ephemeral task input**. The prior `LOCAL ONLY` conclusion was an input-availability conclusion, not a DOSBox/runtime limitation, and is superseded by this supplied-fixture experiment.

## Runtime evidence fail-closed corrections from review

A later review identified a second class of false-positive risk in the runtime smoke. Both cases are now explicitly rejected.

### Successful video mode, not merely a request

The SDL probe previously logged the requested dimensions even if `SDL_SetVideoMode` returned `NULL`; the runner could therefore mistake a failed request for an established 640x480 transition.

The probe now records `ok=0|1` from the actual returned surface and `--expect-mode` accepts only a matching `ok=1` transition. A synthetic fake SDL returning `NULL` for 640x480 is required to fail the smoke while preserving that failed request in artifact metadata.

### Explicit process termination semantics

A process could previously reach 640x480 and immediately crash/nonzero-exit yet still satisfy `--expect-mode`. The runner now refuses any `--expect-mode` invocation unless it also states one of:

- `--expect-timeout` — the process must remain alive until the bounded timeout; or
- one or more `--expect-exit-code N` values — the process must terminate normally with an allowed code.

A synthetic mode-then-exit-7 fixture verifies that the successful 640x480 transition is recorded but the overall smoke still fails because the termination contract is violated. Artifacts are still emitted on failure. Metadata schema 2 records mode success, return/timeout state, the declared termination contract, and whether it was met.

## Harness safety corrections from review

Two earlier review findings were also fixed before treating the retail handoff as safe.

### Source-tree isolation

The original temporary mount attempted a hardlink before falling back to copying. That was unsafe because a guest write to an existing mounted file could mutate the same inode in the maintainer-owned source tree.

The runner now always copies input files into an independent temporary overlay. A synthetic DOSBox stand-in deliberately overwrites `MUTABLE.CFG` in the mounted tree; the test verifies that the source file remains byte-identical and that neither it nor the executable enters the artifact ZIP.

### Framebuffer lifetime

The original capture worker read `current_surface` concurrently with `SDL_SetVideoMode`, creating a race when SDL replaced/freed the old surface during a mode transition.

The worker thread was removed. Due captures now occur synchronously on the same SDL thread from `SDL_PollEvent` and immediately after `SDL_SetVideoMode`. A synthetic SDL fixture frees the old surface during a mode change and verifies that a post-transition capture comes from the new surface. The revised probe was also exercised on the real canonical 640x400 → 640x480 retail run without a capture crash.

## Cloud breakpoint and state-observation capability

A later review correctly noted that canonical runtime launch/capture alone was not enough to classify RE4/RE5 as `CLOUD`: those tasks require actual state observation at a bounded runtime boundary. CF3 therefore added and executed a separate **target-free debugger capability smoke**, rather than assuming a debug-enabled package would be usable non-interactively.

The reproducible path is `.github/workflows/tests.yml` job `CF3 debugger capability` plus `scripts/validate_cf3_debugger.py`. On the final CF3 head, GitHub Actions run `31631443127` installed Ubuntu's `dosbox-debug` `0.74-3-5build2` and passed the smoke.

The synthetic guest is six bytes:

```text
B4 2C CD 21 EB FA
```

which repeatedly executes DOS `INT 21h` function `AH=2Ch`. The smoke then:

1. launches `dosbox-debug` under a pseudo-TTY with dummy SDL;
2. injects the standard debugger shortcut as a real mapper chord (`LAlt down → Pause down/up → LAlt up`);
3. drives DOSBox 0.74's debugger command mode through the PTY;
4. installs `BPINT 21 2C *`;
5. resumes with the debugger's F5 binding;
6. requires control to return to the debugger on the next matching interrupt;
7. executes `MEMDUMPBIN CS:100 6` only after that return;
8. requires the host-side dump to match the six guest bytes exactly.

The final job output was:

```text
CF3 debugger smoke: PASS (BPINT hit and byte-exact guest memory observation)
```

This is `synthetic` evidence for a **scriptable cloud breakpoint + guest-memory-observation mechanism**. It does not identify an Antagonizer address, field, calling convention or watchpoint and therefore does not perform RE4/RE5. Those target-specific questions remain owned by their static predecessors and must be tied to the exact canonical hash/retail fixture when executed.

The supplied minimized DOSBox runtime remains sufficient for ordinary target execution/capture. RE4/RE5 may use the proven distro `dosbox-debug` path when a breakpoint-oriented experiment is appropriate, or a narrower task-specific instrumentation path if their established static evidence makes that safer. CF3 now has evidence for both necessary feasibility halves: exact canonical target execution on verified retail data, and non-interactive breakpoint/state observation in cloud infrastructure.

## Reproducible cloud input contract

For exact-target runtime work, a cloud agent needs:

1. this repository checkout;
2. a generic Linux DOSBox runtime compatible with the tested environment for ordinary target execution/capture;
3. `dosbox-debug` 0.74-3 (or another independently demonstrated equivalent) when the bounded experiment requires debugger breakpoint/state observation;
4. a maintainer-supplied/attached English retail installation kept outside git;
5. the exact canonical `ANTAG.EXE` and immutable fixture files matching `tools/retail-runtime-manifest.json`;
6. `scripts/run_cf3_runtime_smoke.py --verify-retail` with explicit mode/termination expectations before accepting target-runtime liveness evidence.

If the retail attachment is absent in a future cloud task, that is an operator-input handoff, not grounds for reclassifying the task `LOCAL ONLY`. The repository must never fetch the retail installation from abandonware/full-game redistribution sites or commit it for convenience.

## Automated and runtime validation

Synthetic/focused validation covers:

- fail-closed demo extraction and case-insensitive member ambiguity;
- probe compilation with warnings-as-errors;
- timed key/chord injection and framebuffer capture;
- surface replacement/free during a scheduled capture;
- copy-only overlay isolation against a deliberate guest write;
- sanitized artifact contents/metadata;
- case-insensitive retail fixture verification and duplicate-name rejection;
- failed `SDL_SetVideoMode` rejection;
- successful-mode-then-crash rejection;
- refusal of `--expect-mode` without explicit termination semantics;
- scripted `dosbox-debug` breakpoint/resume plus byte-exact guest memory observation.

Real/runtime validation covers:

- live public demo acquisition and re-verification in GitHub Actions;
- demo-own headless 640x480/menu smoke;
- preserved negative canonical-ANTAG-on-demo smoke;
- positive exact canonical-ANTAG-on-retail smoke with pinned full-version data and 640x480/menu capture;
- final Actions run `31631443127`: unit tests, CF2 real-target regression, demo acquisition and `CF3 debugger capability` all succeeded.

The retail screenshot and raw runtime ZIP remain local ignored artifacts and are intentionally not committed.

## Roadmap decision

CF3 is **Completed and verified** with the retail and debugger follow-ups incorporated.

- RE4 → `CLOUD` once its existing RE2 dependency is complete. Canonical runtime input is a verified maintainer-supplied retail attachment; a scriptable breakpoint/guest-memory observation path is independently smoke-tested in cloud.
- RE5 → `CLOUD` once RE3/RE4 are complete, using the same exact-target fixture/input contract and the smallest established runtime observation boundary.
- P2 → `CLOUD` once P1 is complete; the canonical proof-of-execution can run against the attached verified retail fixture, and its smoke must use explicit success/termination criteria rather than mode observation alone.
- V1 remains gated by CF4. CF3 does not take over UI-driving/end-to-end visual validation.
- CF4 remains a separate `CLOUD RESEARCH` item and may reuse this canonical runtime fixture/harness when deciding the V1 path.

No RE4, RE5, P2, CF4 or feature implementation is performed by CF3 itself.
