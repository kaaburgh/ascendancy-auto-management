# CF3 — cloud runtime and debugging feasibility

Date: 2026-08-12  
Roadmap item: CF3  
Blind-RE provenance: **clean**  
Evidence classes used below: `runtime`, `static`, `synthetic`, and `reported` as marked.

## Question

Can Ascendancy runtime work needed by M1 execute reproducibly in cloud, using the freely distributed playable demo when possible, and can that fixture replace the retail data needed by the canonical Antagonizer target?

## Inputs

Operator-supplied, hash-verified bundles were used only as generic tooling or project-supplied target/runtime bytes:

- DOSBox 0.74-3 Linux x86_64 runtime bundle; its `verify.sh` passed before testing;
- Ascendancy executable/demo bundle generated from an original `ascdemo.zip` plus the four project target executables;
- the generic Linux RE toolkit was verified, but it is static-analysis tooling and does not contain a runtime debugger.

Relevant executable identities:

- official demo `ASCEND.EXE`: SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`, 582147 bytes;
- canonical M1 target bytes, run under their distribution filename `ANTAG.EXE`: SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes.

The source manifest bundled by the operator records the original demo archive as:

- `ascdemo.zip`, 8978479 bytes;
- SHA-256 `eb18315e744bf53be4dc5d8533f80d317e073661e86acb2ebba3241ae67f9e79`.

No retail game data were used or acquired.

## Demo acquisition and provenance

The current DOS Games Archive download entry identifies `ascdemo.zip` as an MS-DOS **Playable demo**, names `ASCEND.EXE`, and reports the matching 8.56 MB download size. Its Ascendancy page identifies The Logic Factory as developer and The Logic Factory / Virgin Interactive Entertainment as publishers. The supplied demo README is itself publisher-authored and describes how to run the demo and contact The Logic Factory.

The reviewed source is recorded in `tools/demo-runtime-manifest.json`. `tools/fetch_demo.py` pins the complete archive by size/SHA-256 and pins every extracted file separately. It rejects a wrong archive, missing/duplicate case-insensitive members, wrong member bytes, and destinations inside tracked repository paths. A local archive may be supplied with `--archive`; it is subject to the same pinned archive hash.

The current cloud sandbox could resolve the source through the browser/tooling layer, but direct Python HTTPS from the execution container failed with `Temporary failure in name resolution`. Therefore the network transfer itself was not re-downloaded inside this container. This is an environment egress limitation, not a claim that the source is unavailable. The operator-supplied extracted demo tree was independently verified against all 19 committed file pins:

```text
verified 19 demo files in .../demo
```

This keeps acquisition fail-closed while avoiding a false `LOCAL ONLY` conclusion from one sandbox's network policy.

## Does the demo contain planet management and self-management?

**Yes.** This is established without target-specific external RE.

`static` / publisher README:

- the demo's explicit “Features NOT included” list removes the introduction, full tutorial, larger galaxies, full research tree, unlimited game days, and other limits, but does not remove colony/planet management;
- the documented special command `<M>` is “toggle research and planet self-management”.

`static` / supplied demo data:

- `ASCEND00.COB` contains the user-facing strings `Self Managed`, `(Self Managed)`, and `Self-Managed`;
- it also contains the `Planet Status Screen` and `Planet Display` user-facing text.

This is sufficient to establish that the demo is relevant to planet-management runtime experiments. CF3 deliberately does not reverse engineer the self-management implementation; that belongs to RE2–RE5.

## Headless/scriptable demo runtime

A first smoke run with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` established that DOSBox can launch the protected-mode demo without requiring an X server or audio device.

Process liveness alone was not accepted as evidence. `tools/cf3_sdl12_probe.c` is a small SDL 1.2 `LD_PRELOAD` diagnostic that:

- records video-mode requests;
- injects only explicitly scheduled keyboard events through `SDL_PollEvent`;
- copies a bounded number of SDL framebuffer snapshots to PPM files;
- does no target memory inspection and contains no target-specific offsets/knowledge.

`scripts/run_cf3_runtime_smoke.py` builds that probe, constructs a temporary mounted tree, forces dummy SDL video/audio, bounds execution with a timeout, and packages metadata/logs/captures into `artifacts/run-CF3-*.zip`. It never places game bytes into git.

Observed `runtime` result against the pinned demo:

1. DOSBox requested its normal 640x400 surface.
2. The demo displayed its “Ascendancy Demo Version” welcome screen and waited for a key.
3. A scripted Space key at 9000 ms advanced the program.
4. The game requested a 640x480 surface.
5. A captured framebuffer showed the Ascendancy main menu (Introduction / Tutorial / New Game / load/save/exit entries).
6. The process remained running until the bounded smoke-test timeout; no crash/error path was observed.

Repository command equivalent to the successful run:

```sh
python scripts/run_cf3_runtime_smoke.py \
  --dosbox /path/to/dosbox-runtime/bin/dosbox \
  --game-dir game/demo \
  --verify-demo \
  --expected-exe-sha256 0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9 \
  --key-events '9000:space' \
  --captures-ms '5000,8000,12000' \
  --timeout 14 \
  --expect-mode 640x480
```

The raw screenshots are runtime artifacts and are intentionally not committed.

## Can canonical `ANTAG.EXE` use demo data?

**No, not as a usable game-runtime fixture.** This is a clean negative `runtime` result and is the decisive CF3 boundary.

The exact canonical Antagonizer bytes were copied under the original runtime name `ANTAG.EXE` into a temporary overlay of the already verified demo tree. The same DOSBox configuration, SDL probe, timing and input were used.

Observed:

- DOSBox entered the initial 640x400 surface;
- the DOS/4G runtime banner executed;
- `ANTAG.EXE` returned to the DOS prompt before entering the game's 640x480 mode;
- no 640x480 request was observed during the 14-second bounded run;
- the fail-closed smoke command therefore returned nonzero with `expected mode 640x480 was not observed`.

Machine-readable artifact metadata recorded only two video-mode requests, `640x400` with bpp 0 and 32, while the demo `ASCEND.EXE` run on the same data produced the additional `640x480` game mode.

This result does **not** establish which demo/retail data difference causes the exit, and CF3 does not attempt to patch around it. It establishes only the fixture compatibility question CF3 owns: the freely distributed demo data cannot substitute for a retail installation when the exact canonical Antagonizer must execute.

## Runtime/debugging capability decision

Two capabilities need to be separated:

### Demo-own runtime: CLOUD

The official demo itself is a viable cloud fixture for emulator setup, protected-mode launch, deterministic mounting, timed keyboard input, framebuffer capture, bounded execution, and experiments that only need the demo's own `ASCEND.EXE` behavior.

This is useful for validating generic runtime tooling and for narrowing later hypotheses, but demo addresses/state must never be presented as canonical Antagonizer runtime facts.

### Canonical Antagonizer runtime: LOCAL ONLY

RE4, RE5 and P2 require runtime evidence on the canonical Antagonizer, not merely analogous demo behavior. Since canonical `ANTAG.EXE` does not initialize the game on demo data and CF1 established that retail game data are not a lawful public cloud dependency, those exact-target runtime tasks require a maintainer-owned retail installation.

The blocker is therefore **data availability plus demonstrated demo incompatibility**, not “DOSBox cannot run in cloud”. This distinction prevents repeating the wrong feasibility investigation.

## Debugger/instrumentation findings

The attached DOSBox 0.74-3 runtime is the normal build, not a debugger-enabled package. The attached RE toolkit is also static-only. That is not interpreted as a project-wide lack of debugging capability.

General DOSBox documentation/build metadata provides a separate debug build with an internal debugger (`--enable-debug` / distribution `dosbox-debug`) and breakpoints, protected-mode breakpoints, stepping and CPU logging. Those are generic emulator capabilities and remain appropriate for the eventual local RE4/RE5 experiment once the static work supplies the exact breakpoint/watchpoint question.

CF3 does not invent RE4/RE5 breakpoints before their dependencies complete. The artifact launcher intentionally accepts the DOSBox launcher path as an argument so a debug-enabled build can replace the normal executable without changing target acquisition or artifact packaging.

## One-shot local handoff for exact-target runtime

Once a later task has a concrete breakpoint/watchpoint or proof-of-execution scenario, the maintainer should need only a retail installation plus the canonical target and a suitable DOSBox build. The shared launcher is:

```sh
python scripts/run_cf3_runtime_smoke.py \
  --dosbox /path/to/dosbox-or-debug-build \
  --game-dir /path/to/owned/retail/ASCEND \
  --exe /path/to/owned/retail/ASCEND/ANTAG.EXE \
  --expected-exe-sha256 8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00 \
  --captures-ms '5000,10000,15000' \
  --timeout 20
```

It creates a self-contained ignored `artifacts/run-CF3-*.zip` with:

- exact executable SHA-256 and size;
- DOSBox command/timeout metadata;
- stdout/stderr (including debugger output when the selected build writes it there);
- bounded framebuffer captures;
- no retail data files and no executable payload.

RE4/RE5 should extend the invocation with the smallest experiment-specific debugger control they establish rather than turning CF3 into a speculative debugger framework.

## Automated validation

`synthetic`:

- `tests/test_cf3_demo_fetch.py` verifies successful pinned extraction, re-verification, tampered-archive rejection, and ambiguous case-insensitive ZIP member rejection;
- `tests/test_cf3_sdl12_probe.py` compiles the probe with warnings-as-errors and uses a tiny synthetic SDL-compatible shared library/program to prove timed key injection and framebuffer capture without any game bytes.

Current focused run:

```text
Ran 5 tests in 1.214s
OK
```

`runtime`:

- all 19 supplied demo files matched the committed pins;
- demo `ASCEND.EXE` smoke: PASS, expected 640x480 game mode observed;
- canonical `ANTAG.EXE` on the same verified demo tree: expected 640x480 mode **not** observed; negative artifact produced as intended.

## Roadmap decision

CF3 is **Completed and verified**.

- RE4 → `LOCAL ONLY` for its canonical-target runtime evidence.
- RE5 → `LOCAL ONLY` for its canonical-target runtime evidence.
- P2 → `LOCAL ONLY` for canonical-target proof of execution/rollback.
- V1 remains gated by CF4; CF3 has not performed CF4's UI/end-to-end validation work.
- CF4 is now selectable as its own `CLOUD RESEARCH` task. It may reuse the demo/runtime harness, but must independently decide how much UI-driving/visual validation can be cloud-driven and how to package the exact-target local remainder.

No RE4, RE5, P2, CF4 or feature implementation was started in this work.
