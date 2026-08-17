# RE2 — static auto-management UI/state seam

Date: 2026-08-13  
Roadmap item: RE2  
Blind-RE provenance: **clean**  
Evidence class: **static** unless noted otherwise.

## Question

Which static code path handles the existing planet self-management control, what object/state relationship does it use, and which exact sites let RE4 confirm ownership and transition causality without an open-ended debugger session?

## Inputs

Only the supported repository state, project/operator-supplied exact binaries, project-generated analysis, general PC/BIOS facts, and user-facing data from the maintainer-supplied retail fixture were used. No external target-specific recovered knowledge or unsupported repository history was used.

Exact executables:

- `ANTAG_EN.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- `PATCH_EN.EXE` — 587451 bytes — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- `ANTAG_INTL.EXE` — 610863 bytes — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`;
- `PATCH_INTL.EXE` — 587451 bytes — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

Optional user-facing corroboration used during the exploratory run:

- retail `ASCEND00.COB` — 377589 bytes — SHA-256 `7a17cf776b0128c4f716ff6efb38d130470c5316fd9937c500803a97f85472aa`, already pinned by CF3.

Exploratory disassembly used GNU `objdump` 2.44 on reconstructed flat i386 objects. The committed scanner uses the repository `tools/le_image.py` parser/reconstructor and does not require an interactive RE database.

## Procedure

1. Verify every executable by exact filename, size, and SHA-256.
2. Rebuild code/data objects with `tools/le_image.py`.
3. Locate narrow instruction patterns for the planet-window handler, M-key dispatch, toggle, selected-object assignment, BIOS Shift probe, renderer, two state-consultation sites, a zero-initializer candidate, and a known-arity formatting call.
4. Require exactly one match for every pattern; zero or multiple matches fail closed.
5. Validate independent semantic/structural invariants rather than accepting pattern matches alone: `PLANLIST`/`PLSQUARE` strings, M scan-code branch target, shared selected-object DS global, Shift global written by BIOS `INT 16h/AH=02h`, object-relative state displacement `0x5a`, renderer resource ID 98, known format string, callee stack reads, and caller stack cleanup.
6. Repeat on all four pinned builds and require the state offset, M scan code, and renderer resource ID to agree.
7. When the exact retail COB is supplied explicitly, verify its hash and bounded user-facing markers for resource 98 (`Self Managed`) and the documented M/Managed toggle.

Repository command:

```sh
python scripts/generate_re2_ui_state_map.py --binaries binaries
```

Optional local user-facing corroboration:

```sh
python scripts/generate_re2_ui_state_map.py \
  --binaries binaries \
  --retail-cob /path/to/verified/ASCEND00.COB
```

The machine report is written under ignored `artifacts/re2-ui-state/` by default.

## Calling-convention check first

RE2 deliberately did not assume the Watcom default ABI.

At canonical `ANTAG_EN 0x37346`, the format string `data\\planal%02d.shp` independently establishes one variadic integer conversion. The caller pushes the integer, format pointer, and destination pointer, calls `0x76d09`, then executes `add esp,0x0c`. The callee reads the three incoming values from stack locations. This proves a cdecl-style caller-cleaned three-argument stack boundary at this real call site.

The planet-window candidate at `0x37568`, however, immediately saves live incoming `EAX`, `DX`, `EBX`, and `ECX` into locals. Therefore a blanket stack-only model is false for this internal seam. The established result is a **mixed stack/register ABI boundary**, not a claim that every internal game function follows one convention.

## Canonical observations

### Planet-window input seam

`ANTAG_EN 0x37568` is anchored by `PLANLIST` and `PLSQUARE`. In its `DX == 7` branch, the saved `ECX` value is dispatched as keyboard scan codes. The branch compares `0x32` (PC/AT set-1 M) and jumps to the Managed toggle block.

A polarity correction was made during analysis: the modifier global is checked with a short `JE`, so **plain M**, not Shift+M, reaches the direct toggle. The intermediate opposite interpretation was discarded before repository-facing evidence was written.

### Shift global

`ANTAG_EN DS:0x48608` is independently produced by a BIOS keyboard-status path executing `INT 16h` with `AH=02h` and reducing the returned Shift bits to zero or `0xffffffff`. The M branch reaches the direct toggle when this value is zero. The Shift+M alternate path is intentionally left unnamed.

### Selected object

`ANTAG_EN DS:0x43664` is assigned from a selected element of a list/container at `0x16a13..0x16a36`; another selection path writes the same global. The planet-window input and renderer both dereference this same value. Static evidence therefore supports “selected planet/object pointer for this UI seam”; runtime allocation identity/lifetime remains RE4 work.

### Managed state

The direct M path reads `[selected+0x5a]`, bitwise-NOTs the dword, and writes it back at `0x3791f`. The planet-display renderer reads the same selected object and requires `[selected+0x5a] == 0xffffffff` before requesting resource ID 98. The exact retail user-facing data identify resource 98 as `Self Managed` and describe M as toggling Managed.

This independent input + render + user-facing convergence establishes `selected+0x5a` as the existing planet UI's 32-bit Managed/self-management state field for the canonical target. A separate initializer-shaped routine zeros `+0x5a`, but its owning object is not independently proven and it remains supporting evidence only.

Two RE1 planet-update-region sites (`0x35473`, `0x356cc`) also compare `+0x5a` with zero. RE2 records them as state-consultation instrumentation leads only. Their callees and per-turn meaning are intentionally not traced because that is RE3 scope.

## Cross-build result

The same narrow seam repeats in both product families/locales:

| Build | Handler | M dispatch | Toggle write | Selected DS | Shift DS | Render check | State checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x37568` | `0x37a08` | `0x3791f` | `0x43664` | `0x48608` | `0x3afca` | `0x35473`, `0x356cc` |
| `ANTAG_INTL` | `0x375a8` | `0x37a48` | `0x3795f` | `0x436b4` | `0x48658` | `0x3b00a` | `0x354b3`, `0x3570c` |
| `PATCH_EN` | `0x35e98` | `0x36338` | `0x3624f` | `0x434f0` | `0x48494` | `0x398fa` | `0x345ab`, `0x347f9` |
| `PATCH_INTL` | `0x35ed8` | `0x36378` | `0x3628f` | `0x43540` | `0x484e4` | `0x3993a` | `0x345eb`, `0x34839` |

All four agree on state displacement `0x5a`, M scan code `0x32`, and render resource ID `98`. This strongly supports that the UI/state representation predates the Antagonizer-specific downstream changes rather than being introduced by them.

## Reusable scanner and validation

`scripts/generate_re2_ui_state_map.py` is schema-versioned (`ascendancy.re2-ui-state-map/v1`) and fail-closes on:

- unknown/wrong target hash or size;
- zero/multiple signature matches;
- broken PLANLIST/PLSQUARE anchors;
- M branch no longer reaching the toggle;
- Shift probe/toggle using different globals;
- selected assignment/toggle/renderer using different globals;
- state displacement different from `0x5a`;
- renderer resource ID different from 98;
- known-arity format/callee/cleanup invariant drift;
- cross-build state/key/resource invariant drift;
- optional retail COB hash or bounded semantic-marker drift.

Focused unit tests cover wildcard parsing, zero/ambiguous match rejection, signed rel32 decoding, bounded strings, and user-facing marker validation. `.github/workflows/re2-static.yml` regenerates the map on the four publisher-distributed pinned real targets in a clean GitHub Actions checkout; it is intentionally `workflow_dispatch`-only so `archive.org` availability cannot gate pull requests or pushes.

The exploratory exact-target run reproduced:

`RE2 UI/state map: PASS (ANTAG_EN handler=0x37568 M-toggle-write=0x3791f state=selected+0x5a)`

This remains static target-byte evidence; no runtime semantics are claimed from that pass.

## Blind-RE audit note

After the RE2 findings, durable documents, scanner, and successful PR CI had already been independently produced from the supported RE2 evidence, a final GitHub scope check surfaced the body of a separate parallel RE3 pull request. That body contained target-specific RE3 findings. Investigation of that source stopped immediately and none of its technical content was used to form, rank, alter, or validate any RE2 conclusion or artifact.

The RE2 evidence above had already been preserved before this accidental exposure, so no RE2 conclusion was suggested by the parallel PR and no conclusion is marked `contaminated`. This note records the exposure for auditability; the RE2 provenance remains **clean**.

## Negative findings / limits

- The exact numeric event-enum name for `DX == 7` is not established.
- DS-relative globals are not linear runtime addresses; selector/base mapping is deliberately deferred.
- The initializer candidate does not prove object ownership by itself.
- Static selection flow does not prove two live planets have distinct allocations; RE4 must test that explicitly.
- The two `+0x5a` state checks are not named as policy/decision functions.
- No per-turn decision path, patch mechanism, save persistence, or new profile behavior was investigated.

## RE4 handoff

Use the canonical target/CF3 retail fixture and the scriptable debugger path. Break at the M write `0x3791f` and renderer check `0x3afca`; for planet A toggle twice, then planet B once. Record runtime mapping/DS, selected-object pointer, bounded before/after `+0x5a` dwords, and verify planet A and B are independent owners. This single run distinguishes direct field vs side-table vs queued-command models and checks whether the same field drives UI rendering.

No broad turn-loop trace is required for RE4, and no RE3 result is assumed.
