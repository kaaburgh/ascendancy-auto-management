# CF3 — demo executable and package static preflight

- Date: 2026-08-11
- Scope: static preflight for the maintainer-supplied Ascendancy demo executable and full demo ZIP
- Evidence: **real-file static** for supplied bytes; package provenance as an official demo is **maintainer-reported/self-identifying from README** and has not yet been independently reproduced from a public source
- Runtime status: **not completed** — this cloud image lacks a DOS emulator and its apt DNS path is blocked

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

The README's installed-file section describes 20 installed files and mentions `DIG.INI` and `ASCEND.CFG`, while this downloadable ZIP contains 19 entries, including `ASCEND02.COB` and omitting those two configuration files. The README's top-level downloader instructions explicitly say to run `SETSOUND` after unzipping, so the discrepancy is consistent with a downloader package whose runtime configuration is produced during setup, but that generation behavior is not claimed as tested here.

## The demo contains the relevant feature by package documentation

The most important new CF3 fact is in the demo's own README. Its special-key list says:

```text
<M>         toggle research and planet self-management
```

The same package data also contains plaintext help/UI material for:

- `Planet Status Screen`
- `Planet Display`
- `Research Display`
- colony/planet project, industry, prosperity and research UI text

Therefore the demo is **not documented as removing planet self-management or the relevant planet-management screens**. This is strong package-level static/reported evidence and makes the demo materially suitable for a later RE4/RE5 runtime experiment. It is still not a substitute for observing the behavior in a running emulator.

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

## Static `ANTAG.EXE + demo data` compatibility preflight

The demo executable and all four full-build executables expose the same high-level external configuration/runtime filename contract in their strings, including:

- `cob.cfg`
- `ascend.cfg`
- `DIG.INI` / `MDI.INI`
- `dos4gw.exe`
- VESA/UniVBE hooks and Miles DIG driver handling

The supplied demo package contains the three archives named by its `COB.CFG`, so there is no immediate top-level filename-contract mismatch that statically rules out launching a full-build executable against the demo directory.

However, this is **not enough to claim compatibility**. Full-build/Antagonizer executables contain additional resource-name strings not present in the demo executable, and some such names are not observable as plaintext in the supplied COBs. COB compression/indexing and demo feature cuts make plaintext absence insufficient evidence of a missing resource. Only a runtime launch can establish whether `ANTAG.EXE` actually resolves everything it needs and reaches the relevant UI.

## Runtime attempt and current blocker

The current Debian 13 cloud image was checked for:

- DOSBox / DOSBox-X / DOSBox Staging
- DOSEMU
- QEMU i386/system emulation
- Wine

None is installed. `Xvfb` and SDL2 are present.

The system has normal Debian `trixie`, `trixie-updates`, and `trixie-security` apt sources configured, but `apt-get update` fails with `Temporary failure resolving 'deb.debian.org'`. Therefore the missing emulator could not be installed through the sandbox's package manager in this run.

This is an **environment/network blocker, not evidence that cloud DOS execution is impractical**. CF3 remains `Investigation first`; it must not be converted to `LOCAL ONLY` from this result.

## What this does and does not unblock

Established now:

1. exact demo ZIP and inner-EXE fingerprints are known;
2. the full data package is available to the experiment;
3. demo documentation explicitly includes planet self-management;
4. planet-management UI/help material exists in the package;
5. the corrected LE/static toolchain works on the demo executable;
6. there is no obvious top-level file-contract reason that makes an `ANTAG.EXE` launch against demo data impossible.

Still requiring runtime evidence:

- demo boots successfully in a scriptable emulator;
- planet-management/self-management behavior can be reached and observed;
- `ANTAG.EXE` runs against the demo data set;
- if it does not, the exact missing resource/state/runtime failure;
- which RE4/RE5 instrumentation can be automated in cloud.

## Safety / repository policy

No executable, ZIP, or copyrighted demo data is committed. Only hashes, layout metadata, aggregate analysis and package documentation findings are recorded.
