# CF3 — demo executable and package static preflight

- Date: 2026-08-11
- Scope: static preflight for the maintainer-supplied Ascendancy demo executable and full demo ZIP
- Evidence: **real-file static** for supplied bytes; package provenance as an official demo is **maintainer-reported/self-identifying from README** and has not yet been independently reproduced from a public source
- Runtime follow-up: **demo boot and planet UI now observed successfully**; see [`CF3-cloud-runtime-debugging.md`](./CF3-cloud-runtime-debugging.md)

## Supplied package

The maintainer supplied `ascdemo.zip` after first supplying its `ASCEND.EXE` separately.

- ZIP size: `8978479` bytes
- ZIP SHA-256: `eb18315e744bf53be4dc5d8533f80d317e073661e86acb2ebba3241ae67f9e79`
- ZIP entries: `19`
- inner `ASCEND.EXE`: `582147` bytes, SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`

The inner executable hash is **exactly identical** to the previously supplied standalone demo `ASCEND.EXE`, so all prior container/disassembly measurements apply to the executable in this package.

The archive was inspected with path-traversal checks before extraction. No game/demo binaries or data are committed to the repository.

### Package contents relevant to runtime

The package contains:

- `ASCEND.EXE`
- `DOS4GW.EXE`
- `SETSOUND.EXE`
- `UVCONFIG.EXE`
- `ASCEND00.COB`, `ASCEND01.COB`, `ASCEND02.COB`
- `COB.CFG`
- Miles DIG drivers / `AILDRVR.LST`
- `README`

`COB.CFG` contains:

```text
ascend00.cob
ascend01.cob
ascend02.cob
```

and all three named archives are present.

The README's installed-file section describes 20 installed files and mentions `DIG.INI` and `ASCEND.CFG`, while this downloadable ZIP contains 19 entries, including `ASCEND02.COB` and omitting those two configuration files. The README's downloader instructions explicitly say to run `SETSOUND` after unzipping. A later runtime run deliberately disabled emulated sound and reached the game/planet UI without those generated configuration files; that does not establish the normal sound-setup behavior.

## The demo contains the relevant feature

The demo's own README says:

```text
<M>         toggle research and planet self-management
```

The same package data contains plaintext help/UI material for:

- `Planet Status Screen`
- `Planet Display`
- `Research Display`
- colony/planet project, industry, prosperity and research UI text

The later runtime experiment confirms the broader UI path: the supplied demo boots, creates a new game, reaches the galaxy map, opens the `Planets` list, and opens the starting planet surface. Thus the planet-management screens are not merely dead package strings.

The exact effect of `M` is still not claimed from screenshots: on the tested galaxy and planet screens the framebuffer did not change after the key, so its internal/turn-level effect still needs instrumentation or a behavioral experiment.

## Container/layout result

The demo executable is another DOS `MZ` + Linear Executable (`LE`) image in the same Watcom/DOS4G layout family as the four CF1 targets:

- `e_lfanew = 0x2a50`
- LE format, 4096-byte pages
- 120 enumerated pages
- exactly two objects
- `impmod_off @ +0x70 = 0x146bd`
- `impproc_off @ +0x78 = 0x146bd`
- `num_impmods = 0`
- absolute enumerated-page `page_off @ +0x80 = 0x17200`
- `autodata_obj @ +0x94 = 2`
- `debug_off/debug_len @ +0x98/+0x9c = 0/0`
- sequential page-map numbers and only legal (`0x00`) page flags

Using `page_off @ +0x80`, page data spans `0x17200 .. 0x8e203`, exactly to EOF (`0x8e203`). Thus this independently supplied demo executable is a fifth real-world check that the corrected Open Watcom `page_off @ +0x80` interpretation is coherent outside the original four CF1 binaries.

The two objects are:

| Object | Base/range | Virtual size | Pages | Flags | Reconstructed SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| code 1 | `0x10000 .. 0x7c7e6` | 444390 | 109 | `0x2045` | `9093238fecd3da761b7770438194d1561aa0bc73496bad8eca574311e5e58738` |
| data 2 | `0x80000 .. 0x126ba0` | 682912 | 11 | `0x2043` | `e4a100f6dfd60ff03ddf2d05ca90df4752c83b8831c0341784328d9d6d0ea6e7` |

## Entry/startup cross-check

The declared entry is VA `0x72464`, file offset `0x79664`. Its first bytes are:

```text
eb 76 57 41 54 43 4f 4d 20 43 2f 43 2b 2b 33 32 ...
```

As in all four CF1 targets, `EB 76` jumps over the embedded `WATCOM C/C++32 Run-Time ...` banner into coherent startup code. This is independent additional evidence against treating the numeric `impmod_off @ +0x70` value as an absolute page-data base.

## Demo-identifying strings under corrected mapping

Raw strings include:

- `Ascendancy Demo Version` — raw file `0x84a95`, data-object offset `0x895`, VA `0x80895`
- `Copyright (c) 1995 The Logic Factory, Inc.` immediately after the demo marker
- `RATIONAL DOS/4G` — raw file `0x895f8`, VA `0x853f8`
- `Thank you for playing Ascendancy.` — raw file `0x8a624`, VA `0x86424`

The demo marker at data offset `0x895` is a layout relationship with the patch pair's banner location, not by itself source-lineage proof.

## Corrected static inventory

Using the same GNU objdump 2.44 linear-sweep/candidate semantics as the corrected CF2 regeneration:

- decoded instructions: **137586**
- candidate functions: **1295**
- direct in-object call sites: **7194**
- distinct branch targets: **10359**
- call-graph edges: **4127**

These are analysis metadata, not proven function boundaries.

## Supplemental differential observations

| Comparison | Strict matches | Relocated strict | Same-address strict | Constant-only | Structural demo / other | Demo structural matched-byte fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| demo vs `PATCH_EN` | 690 | 598 | 92 | 531 | 74 / 76 | `0.779004` |
| demo vs `PATCH_INTL` | 690 | 598 | 92 | 530 | 75 / 76 | `0.782352` |
| demo vs `ANTAG_EN` | 669 | 582 | 87 | 520 | 106 / 137 | `0.733931` |
| demo vs `ANTAG_INTL` | 669 | 582 | 87 | 514 | 112 / 143 | `0.724066` |

On this coarse candidate/signature metric the demo is structurally closer to the patch pair than to the Antagonizer pair. This is hypothesis-generating only; compiler/layout effects and demo-specific cuts remain confounders.

## Full-build-versus-demo-data boundary, now established at runtime

The earlier static preflight found no obvious high-level filename-contract mismatch. The runtime experiment has now identified the first concrete mismatch.

Both exact full-build executables tested against the otherwise unchanged demo data — `ANTAG_EN.EXE` and the official `PATCH_EN.EXE` control — successfully open:

```text
COB.CFG
ASCEND00.COB
ASCEND01.COB
ASCEND02.COB
```

and then attempt:

```text
STATIC.TXT   fopen64 mode=rb
```

The demo package has no `STATIC.TXT`, the read fails with `ENOENT`, and both full-build executables return to DOS before reaching their game UI.

This is a stronger result than the old static compatibility hypothesis:

- `ANTAG.EXE + demo data` is **not compatible as supplied**;
- the first observed failure is **not Antagonizer-specific**, because the official patch fails at the same boundary;
- `static.txt` occurs in all four full-build executables and is absent from the demo executable;
- there may be further full-build data dependencies after `STATIC.TXT`, so a complete authorized retail/full-build data handoff is preferable to fabricating or guessing individual files.

The filesystem evidence and exact cloud runtime setup are recorded in [`CF3-cloud-runtime-debugging.md`](./CF3-cloud-runtime-debugging.md). The host-side probe source is [`../../tools/dosbox_fsprobe.c`](../../tools/dosbox_fsprobe.c).

## Current use of the demo

Established now:

1. exact demo ZIP and inner-EXE fingerprints are known;
2. the full demo data package is available to the experiment;
3. documentation explicitly includes planet self-management;
4. the planet-management UI path is observed running under DOSBox/Xvfb;
5. scripted mouse/keyboard input and framebuffer capture work in cloud;
6. the corrected LE/static toolchain works on the demo executable;
7. full-build-on-demo-data fails at the exact `STATIC.TXT` read boundary.

Still unresolved:

- the internal/turn-level state effect of `M`;
- full Antagonizer runtime against authorized full-game data;
- debugger/memory/state instrumentation sufficient for RE4/RE5.

## Safety / repository policy

No executable, ZIP, Debian package, screenshot, COB, or copyrighted game/demo data is committed. Only hashes, layout metadata, aggregate analysis, runtime observations, and non-game diagnostic source are recorded.
