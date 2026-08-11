# CF3 — demo executable static preflight

- Date: 2026-08-11
- Scope: static preflight for the maintainer-supplied Ascendancy demo executable
- Evidence: **real-file static** for the supplied bytes; provenance as a demo executable is **maintainer-reported** and has not yet been independently reproduced from an original demo archive
- Runtime status: **not tested** — the full demo data/package is not available in this run

## Input

The maintainer supplied a file named `ASCEND.EXE` and identified it as coming from the Ascendancy playable demo.

- File size: `582147` bytes
- SHA-256: `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`
- The executable is **not committed** to the repository.

This fingerprint is useful for future provenance work: once an original demo ZIP/installer is available, extraction should reproduce this exact hash before treating the package as the same demo build.

## Container/layout result

The demo executable is another DOS `MZ` + Linear Executable (`LE`) image with the same overall Watcom/DOS4G layout family as the four CF1 targets:

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

Using `page_off @ +0x80`, page data spans `0x17200 .. 0x8e203`, exactly to EOF (`0x8e203`). Thus this independently supplied demo executable provides a fifth real-world check that the corrected Open Watcom `page_off @ +0x80` interpretation is coherent outside the original four CF1 binaries.

The two objects are:

| Object | Base/range | Virtual size | Pages | Flags | Reconstructed SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| code 1 | `0x10000 .. 0x7c7e6` | 444390 | 109 | `0x2045` | `9093238fecd3da761b7770438194d1561aa0bc73496bad8eca574311e5e58738` |
| data 2 | `0x80000 .. 0x126ba0` | 682912 | 11 | `0x2043` | `e4a100f6dfd60ff03ddf2d05ca90df4752c83b8831c0341784328d9d6d0ea6e7` |

These object hashes are regression anchors only; the object bytes remain external to git.

## Entry/startup cross-check

The declared entry is VA `0x72464`, file offset `0x79664`. Its first bytes are:

```text
eb 76 57 41 54 43 4f 4d 20 43 2f 43 2b 2b 33 32 ...
```

As in all four CF1 targets, `EB 76` is a short jump over the embedded `WATCOM C/C++32 Run-Time ...` banner. The jump destination starts with coherent startup code:

```text
fb 83 e4 fc 89 e3 89 1d 0c 97 00 00 89 1d f8 96 ... cd 21 ...
```

This is independent additional evidence against treating the numeric `impmod_off @ +0x70` value as an absolute page-data base.

## Demo-identifying strings under corrected mapping

Raw strings in the supplied file include:

- `Ascendancy Demo Version` — raw file `0x84a95`, data-object offset `0x895`, VA `0x80895`;
- `Copyright (c) 1995 The Logic Factory, Inc.` immediately after the demo marker;
- `RATIONAL DOS/4G` — raw file `0x895f8`, VA `0x853f8`;
- `Thank you for playing Ascendancy.` — raw file `0x8a624`, VA `0x86424`.

The `Ascendancy Demo Version` string appearing at data offset `0x895` is notable because the patch pair also places its Ascendancy copyright/banner material at data offset `0x895`. This is a layout relationship, not by itself proof of source lineage.

## Corrected static inventory

Using the same GNU objdump 2.44 linear-sweep/candidate semantics as the corrected CF2 regeneration:

- decoded instructions: **137586**
- candidate functions: **1295**
- direct in-object call sites: **7194**
- distinct branch targets: **10359**
- call-graph edges: **4127**

As elsewhere in CF2, these are analysis metadata. Candidate boundaries are derived from direct call targets and the entry seed; they are not proven function boundaries.

## Supplemental differential observations

The demo executable was compared with the already regenerated inventories. This is a static similarity check only; it does not establish build lineage or demo feature availability.

| Comparison | Strict matches | Relocated strict | Same-address strict | Constant-only | Structural demo / other | Demo structural matched-byte fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| demo vs `PATCH_EN` | 690 | 598 | 92 | 531 | 74 / 76 | `0.779004` |
| demo vs `PATCH_INTL` | 690 | 598 | 92 | 530 | 75 / 76 | `0.782352` |
| demo vs `ANTAG_EN` | 669 | 582 | 87 | 520 | 106 / 137 | `0.733931` |
| demo vs `ANTAG_INTL` | 669 | 582 | 87 | 514 | 112 / 143 | `0.724066` |

On this coarse candidate/signature metric the demo is structurally closer to the patch pair than to the Antagonizer pair. That is a useful hypothesis-generating observation, but it is **not sufficient evidence that the demo and patch share the same source snapshot**. Compiler/layout effects and demo-specific feature cuts remain confounders.

The demo code object is 4,960 bytes smaller than `PATCH_EN` and 24,400 bytes smaller than `ANTAG_EN`; its data object virtual size is 2,896 bytes smaller than `PATCH_EN`. These are measured layout facts, not behavioral explanations.

## What this does and does not unblock

This file is useful to CF3 in three ways:

1. it gives the demo executable an exact hash and a reproducible static identity;
2. it shows the current corrected LE parser/toolchain applies cleanly to the demo build family;
3. it provides static comparison anchors for later runtime observations.

It does **not** complete the CF3 demo evaluation. In particular, this run cannot establish:

- whether the supplied executable came from a specific original authorized demo archive;
- whether the demo launches successfully in the target cloud environment;
- whether planet-management and self-management screens/functions are available at runtime;
- whether `ANTAG.EXE` can run against the demo's data files;
- which runtime/debugging experiments can be performed with the demo.

Those questions require the **full original demo package** (preferably its ZIP/installer, or the complete extracted demo directory including data files), not only `ASCEND.EXE`. Per the maintainer's instruction, do not substitute an alternative download path before giving them the opportunity to supply those files.

## Safety / repository policy

No executable or copyrighted demo data is committed. Only hashes, layout metadata and derived aggregate analysis are recorded.