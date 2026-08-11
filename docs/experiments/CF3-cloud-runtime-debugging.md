# CF3 — cloud runtime/debugging investigation

- Date: 2026-08-11
- Status: **Investigation incomplete — demo runtime/UI path demonstrated in cloud; full-build-on-demo-data fails on a concrete missing retail-data file; debugger/state tracing still open**
- Execution classification: remains `CLOUD RESEARCH`
- Evidence categories: real-file runtime + host filesystem instrumentation + real-file static + package documentation

## Question

Can the Ascendancy demo, and ideally the canonical Antagonizer executable, run reproducibly in cloud infrastructure with enough observability for RE4/RE5?

## Exact demo input

The maintainer supplied the complete downloadable demo package:

- `ascdemo.zip`
- size `8978479`
- SHA-256 `eb18315e744bf53be4dc5d8533f80d317e073661e86acb2ebba3241ae67f9e79`
- 19 ZIP members
- inner `ASCEND.EXE`: `582147` bytes, SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`

The inner executable exactly matches the standalone demo executable supplied earlier. Detailed package/container/static-analysis evidence is in [`CF3-demo-executable-static-preflight.md`](./CF3-demo-executable-static-preflight.md).

## Cloud runtime environment

The base Debian 13 (`trixie`) sandbox had `Xvfb`, SDL2, `scrot` 1.12.1, Python with Xlib/XTEST bindings, and GCC 14.2.0, but no DOS emulator. Network/DNS to `deb.debian.org` was unavailable, so the maintainer supplied the required Debian packages as task attachments.

They were **extracted locally with `dpkg-deb -x`; nothing was installed into the system**:

| Package | Version | SHA-256 |
| --- | --- | --- |
| `dosbox` | `0.74-3-5+b1` amd64 | `d9c17b9280bdd3ffb611467673b011800cd4a1ddf5294baa7b1c60b0025e1ef2` |
| `libsdl1.2debian` | `1.2.68-3` amd64 | `64622c268b2bd343caa50cf8541629a624838b40d91ab99e7d97853424648d7d` |
| `libsdl-sound1.2` | `1.0.3-9+b5` amd64 | `71004f35c8852e0d98d96ef8df07f00804b4726512f06b8d545325dc7f914b8e` |
| `libsdl-net1.2` | `1.2.8-6+b2` amd64 | `931fd22d0554c2160e9f3914c7de0f035ba1f168fc173f9c793221898642191d` |
| `libmikmod3` | `3.3.13-1` amd64 | `6d991a9a8d915af9ae5b4f2ac763a0755b6d987b7d1a4679c01eb2b5b88288ae` |

With the extracted library directories in `LD_LIBRARY_PATH`, `ldd` on the supplied DOSBox binary had no unresolved dependencies and `dosbox -version` reported `DOSBox version 0.74-3`.

Runtime configuration deliberately removed audio as a confounder:

```ini
[dosbox]
machine=svga_s3
memsize=16

[sdl]
fullscreen=false
output=surface

[mixer]
nosound=true

[midi]
mpu401=none
mididevice=none

[sblaster]
sbtype=none
```

The run used `SDL_AUDIODRIVER=dummy`, an `Xvfb :99` 1024x768x24 display, and mounted the extracted demo directory read/write as DOS drive C. No `SETSOUND` step, `DIG.INI`, or `ASCEND.CFG` was required to reach the tested screens with emulated sound disabled.

## Demo runtime result — positive

The demo is now **observed running**, not merely documented as suitable.

A deterministic input/capture sequence reached all of the following:

1. DOS/4GW protected-mode startup and the `Ascendancy Demo Version` console banner;
2. the demo's `Press a key to continue...` screen;
3. the graphical Ascendancy main menu;
4. `New Game` setup;
5. the Minions species-introduction screen;
6. the live galaxy map;
7. the `Planets` list showing the starting occupied planet and project status;
8. the planet surface/status screen for that colony.

Input was driven through XTEST and captures were taken from Xvfb with `scrot`. Mouse input selected `New Game`, `Begin New Game`, closed the species-introduction screen, selected `Planets`, and opened the starting planet. Keyboard injection was independently verified in graphics mode: `Escape` from the planet surface returned to the planet list.

This is direct runtime evidence that the demo contains and can execute the planet-management path needed for later experiments. It also demonstrates that a cloud process can drive this DOS UI and capture bounded framebuffer evidence.

## `M` self-management toggle observation

The demo README documents:

```text
<M>         toggle research and planet self-management
```

`M` was sent through the same XTEST path on both the galaxy map and planet-surface screen. A screenshot before the key, after the first `M`, and after a second `M` was compared pixel-for-pixel. On both tested screens the framebuffer was identical (`0` changed pixels).

This **does not mean the key is ignored**. `Escape` proves keyboard injection works in graphics mode, and the documented `M` behavior may change internal management/research state without drawing an acknowledgement on those screens. Therefore the `M` behavior still needs a state/turn-effect experiment rather than a screenshot-only assertion.

## `ANTAG_EN.EXE + demo data` runtime result — negative, with exact first failure

The exact English Antagonizer target was tested against an otherwise unchanged copy of the demo data:

- `ANTAG_EN.EXE` SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`
- launched as `ANTAG.EXE` from the demo directory
- same `COB.CFG`, `ASCEND00.COB`, `ASCEND01.COB`, `ASCEND02.COB`, `DOS4GW.EXE`, and other demo files

Observed behavior: DOS/4GW starts, then the executable returns silently to the DOS prompt before reaching an Ascendancy UI/banner.

To avoid guessing, a small host-side `LD_PRELOAD` filesystem probe was built around DOSBox. The reusable source is [`../../tools/dosbox_fsprobe.c`](../../tools/dosbox_fsprobe.c). It records DOSBox host filesystem calls for the mounted directory without modifying guest state.

The Antagonizer trace reaches:

```text
COB.CFG              opened
ASCEND00.COB         opened
ASCEND01.COB         opened
ASCEND02.COB         opened
STATIC.TXT           fopen64 mode=rb -> ENOENT
```

The demo package contains no `STATIC.TXT`.

Static strings independently agree with the runtime result: `static.txt` is present in `ANTAG_EN.EXE`, `ANTAG_INTL.EXE`, `PATCH_EN.EXE`, and `PATCH_INTL.EXE`, but is absent from the demo `ASCEND.EXE`.

## Control experiment — official patch fails at the same boundary

`PATCH_EN.EXE` SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` was run against the same demo data as a control.

It follows the same host-file sequence and also fails on:

```text
STATIC.TXT           fopen64 mode=rb -> ENOENT
```

before returning to DOS.

Therefore the first observed incompatibility is **not Antagonizer-specific**. It is a full-build-versus-demo-data boundary shared by the official patch and Antagonizer. This materially updates the earlier static preflight: the demo data set is sufficient for the demo executable, but not sufficient as-is for these full-build executables.

No empty/synthetic `STATIC.TXT` was created. Doing so would turn a concrete missing-input result into an uncontrolled parser/content experiment and could hide the next real dependency.

## What file input is now needed

To continue the full-build runtime experiment, the preferred input is an authorized copy of the **complete installed retail/full-build data directory** (or an archive of it), excluding nothing merely because it appears unrelated. That avoids a one-file-at-a-time chain if `STATIC.TXT` is only the first demo/full-data difference.

If that is not available, the minimum next input is the original `STATIC.TXT` from the matching installed game data. The next run should leave all other inputs unchanged, re-run the filesystem probe, and either reach the UI or identify the next exact missing/read failure.

Do **not** substitute a fabricated `STATIC.TXT`, abandonware/full-retail download, or inferred contents.

## Current cloud-feasibility decision

CF3 remains **Investigation first / CLOUD RESEARCH**, but the reason is now much narrower.

Established:

- DOS protected-mode Ascendancy runs in this cloud sandbox when DOSBox is supplied as local packages;
- the official demo boots with its exact supplied data;
- Xvfb + scripted XTEST input can reach the actual galaxy, planet list, and planet surface;
- framebuffer captures are reproducible enough for bounded visual evidence;
- host-side file-access instrumentation can identify guest resource/file failures;
- `ANTAG_EN` and `PATCH_EN` cannot use the demo data set as-is because both first fail reading missing `STATIC.TXT`.

Still open:

- observe the actual state/turn effect of the documented `M` self-management toggle;
- boot the canonical full-build/Antagonizer against authorized full game data;
- establish memory/state tracing, breakpoints/watchpoints, or an equivalent debugger/instrumentation path for RE4/RE5;
- only then convert CF3-owned gated tasks to `CLOUD` or `LOCAL ONLY`.

This result is already sufficient to reject two stale conclusions: cloud DOS execution is **not** blocked by the base image, and `ANTAG.EXE + demo data` is **not** an untested compatibility hypothesis anymore. The demo is a viable cloud runtime/UI fixture for its own executable; the remaining target-runtime dependency is full-build data plus deeper state instrumentation.

## Safety / repository policy

No executable, Debian package, ZIP, COB, screenshot, or other copyrighted game/demo asset is committed. The repository stores only hashes, aggregate observations, experiment procedure, and non-game diagnostic source.
