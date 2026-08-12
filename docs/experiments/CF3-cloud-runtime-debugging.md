# CF3 — cloud runtime and debugging feasibility

Date: 2026-08-12  
Roadmap item: CF3  
Blind-RE provenance: **clean**  
Evidence classes used below: `runtime`, `static`, `synthetic`, and `reported` as marked.

## Question

Can the DOS runtime work needed by M1 execute reproducibly in cloud, including the exact canonical Antagonizer when the maintainer supplies the owned retail installation as task input? Which parts can use the freely distributed demo, and what input contract is required for exact-target work?

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

A clean GitHub Actions runner exercised the public acquisition path end to end in run `31611654248`, job `CF3 demo acquisition`: the committed fetcher downloaded the pinned archive and re-verified the extracted tree.

The demo contains the feature class relevant to M1. Publisher/user-facing documentation names `<M>` as toggling research and planet self-management, and the supplied demo data contain the user-facing `Self Managed` / planet-screen text. This establishes fixture relevance without inferring implementation details.

## Demo-own headless runtime

`tools/cf3_sdl12_probe.c` and `scripts/run_cf3_runtime_smoke.py` provide a bounded cloud smoke harness. The probe records SDL video-mode transitions, injects only explicitly scheduled keyboard events, and captures selected framebuffers. The runner uses dummy SDL video/audio, a temporary mounted copy, an execution timeout, exact executable hash checks when requested, and a sanitized `artifacts/run-CF3-*.zip` containing metadata/logs/captures but no game payload.

Observed `runtime` result against the pinned demo:

1. DOSBox entered its 640x400 surface.
2. The demo showed its welcome screen.
3. A scheduled Space key advanced it.
4. The game requested 640x480.
5. A captured framebuffer showed the Ascendancy main menu.
6. The process remained alive until the bounded timeout.

The demo therefore proves that protected-mode execution, deterministic mounting, scripted input, bounded framebuffer capture and artifact collection work in this cloud environment.

## Negative result: canonical Antagonizer on demo data

The exact canonical `ANTAG.EXE` was overlaid onto the fully verified demo tree and run with the same DOSBox/runtime probe.

Observed `runtime` result:

- the DOS/4G runtime started;
- only the initial 640x400 DOSBox modes appeared;
- `ANTAG.EXE` returned to the DOS prompt before requesting the game's 640x480 mode;
- the fail-closed `--expect-mode 640x480` check returned nonzero and preserved a bounded negative artifact.

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

Equivalent repository command:

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
  --expect-mode 640x480
```

Observed `runtime` result:

1. `--verify-retail` accepted the supplied fixture against the committed pins.
2. DOSBox entered 640x400 (bpp 0, then 32).
3. The exact canonical `ANTAG.EXE` remained alive rather than returning to the DOS prompt.
4. A scheduled Space key at about 5 seconds advanced the program.
5. The canonical target requested 640x480 bpp 32 at about 6 seconds.
6. The 8-second framebuffer capture was 640x480 and showed the Ascendancy main menu.
7. The bounded run ended by timeout rather than target crash/exit.
8. Artifact metadata recorded `game_dir_retail_verified: true`, exact target hash/size, the three observed video modes, `expected_mode_observed: true`, and two captures, without embedding retail files or host source paths.

This establishes the missing CF3 fact: **the exact canonical Antagonizer runtime is viable in cloud when the maintainer supplies the owned retail installation as ephemeral task input**. The prior `LOCAL ONLY` conclusion was an input-availability conclusion, not a DOSBox/runtime limitation, and is superseded by this supplied-fixture experiment.

## Harness safety corrections from review

Two review findings were fixed before treating the retail handoff as safe.

### Source-tree isolation

The original temporary mount attempted a hardlink before falling back to copying. That was unsafe because a guest write to an existing mounted file could mutate the same inode in the maintainer-owned source tree.

The runner now always copies input files into an independent temporary overlay. A synthetic DOSBox stand-in deliberately overwrites `MUTABLE.CFG` in the mounted tree; the test verifies that the source file remains byte-identical and that neither it nor the executable enters the artifact ZIP.

### Framebuffer lifetime

The original capture worker read `current_surface` concurrently with `SDL_SetVideoMode`, creating a race when SDL replaced/freed the old surface during a mode transition.

The worker thread was removed. Due captures now occur synchronously on the same SDL thread from `SDL_PollEvent` and immediately after `SDL_SetVideoMode`. A synthetic SDL fixture frees the old surface during a mode change and verifies that a post-transition capture comes from the new surface. The revised probe was also exercised on the real canonical 640x400 → 640x480 retail run without a capture crash.

## Debugging/instrumentation boundary

The supplied minimized Debian DOSBox runtime is sufficient for canonical protected-mode execution, scripted input and capture, but its runtime linkage does not provide the ncurses debugger build. CF3 therefore does **not** claim that this particular packaged executable supplies guest breakpoints/watchpoints.

That does not force the downstream tasks to `LOCAL ONLY`. General DOSBox 0.74-3 supports a separately compiled debug configuration (`--enable-debug` / `C_DEBUG`) and its debugger supports breakpoint-oriented workflows; alternatively, RE4/RE5 may use the smallest task-specific guest/runtime instrumentation established by their static dependencies. The key CF3 gate is now resolved: the exact target and its required data can execute in the same cloud environment. A missing optional debugger binary in one supplied runtime bundle is a generic tool-acquisition issue, not evidence that canonical runtime must happen on the maintainer's workstation.

RE4/RE5 should still avoid an open-ended debugger session. Their static predecessors must first define the exact write/read/call-site question, after which the cloud run should use the narrowest debugger or instrumentation mechanism that answers it and package repo-safe evidence.

## Reproducible cloud input contract

For exact-target runtime work, a cloud agent needs:

1. this repository checkout;
2. a generic Linux DOSBox runtime compatible with the tested environment (the supplied 0.74-3 bundle is sufficient for execution/capture);
3. a maintainer-supplied/attached English retail installation kept outside git;
4. the exact canonical `ANTAG.EXE` and immutable fixture files matching `tools/retail-runtime-manifest.json`;
5. `scripts/run_cf3_runtime_smoke.py --verify-retail` before accepting target-runtime evidence.

If the retail attachment is absent in a future cloud task, that is an operator-input handoff, not grounds for reclassifying the task `LOCAL ONLY`. The repository must never fetch the retail installation from abandonware/full-game redistribution sites or commit it for convenience.

## Automated and runtime validation

Synthetic/focused validation covers:

- fail-closed demo extraction and case-insensitive member ambiguity;
- probe compilation with warnings-as-errors;
- timed key injection and framebuffer capture;
- surface replacement/free during a scheduled capture;
- copy-only overlay isolation against a deliberate guest write;
- sanitized artifact contents/metadata;
- case-insensitive retail fixture verification and duplicate-name rejection.

Real/runtime validation covers:

- live public demo acquisition and re-verification in GitHub Actions;
- demo-own headless 640x480/menu smoke;
- preserved negative canonical-ANTAG-on-demo smoke;
- positive exact canonical-ANTAG-on-retail smoke with pinned full-version data and 640x480/menu capture.

The retail screenshot and raw runtime ZIP remain local ignored artifacts and are intentionally not committed.

## Roadmap decision

CF3 is **Completed and verified** with the retail follow-up incorporated.

- RE4 → `CLOUD` once its existing RE2 dependency is complete. Canonical runtime input is a verified maintainer-supplied retail attachment.
- RE5 → `CLOUD` once RE3/RE4 are complete, using the same exact-target fixture/input contract.
- P2 → `CLOUD` once P1 is complete; the canonical proof-of-execution can run against the attached verified retail fixture in cloud.
- V1 remains gated by CF4. CF3 does not take over UI-driving/end-to-end visual validation.
- CF4 remains a separate `CLOUD RESEARCH` item and may reuse this canonical runtime fixture/harness when deciding the V1 path.

No RE4, RE5, P2, CF4 or feature implementation is performed by CF3 itself.
