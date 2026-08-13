# Existing auto-management UI/state seam

## Targets and evidence boundary

Canonical M1 target:

- `ANTAG_EN.EXE` / runtime filename `ANTAG.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Static corroboration only:

- `PATCH_EN.EXE` — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- `ANTAG_INTL.EXE` — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`;
- `PATCH_INTL.EXE` — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

Blind-RE provenance: **clean**. Findings below are labeled `static` or `runtime`. No external target-specific recovered knowledge was used. Code addresses are code-object virtual addresses for the named binaries. Data globals such as `DS:0x43664` remain **DS-relative offsets**; RE4 did not need to promote a guessed DOS/4G selector base into a fact.

Reproducible records:

- RE2 static scanner/procedure: `scripts/generate_re2_ui_state_map.py` and [`../experiments/RE2-auto-management-ui-state-static.md`](../experiments/RE2-auto-management-ui-state-static.md);
- RE4 runtime runner/procedure: `scripts/run_re4_runtime_state.py` and [`../experiments/RE4-runtime-ui-state.md`](../experiments/RE4-runtime-ui-state.md).

## Established UI/state seam on `ANTAG_EN`

### Planet-window handler candidate: `0x37568`

`static`, clean.

`0x37568` is anchored to the planet display rather than named from guesswork:

- its setup resolves the `PLANLIST` and `PLSQUARE` data strings;
- nearby setup consumes the planet-window resource family already bounded by RE1;
- the same instruction shape exists in the English patch at `0x35e98` and shifts by the expected locale delta in both International builds.

The entry immediately saves live incoming `EAX`, `DX`, `EBX`, and `ECX`. The branch for `DX == 7` eventually dispatches original `ECX` as PC/AT set-1 keyboard scan codes. At `0x37a28` it compares against `0x32`, **M**, and the branch at `0x37a2b` reaches the state-toggle block at `0x378e6`.

The exact numeric event-enum name represented by `DX == 7` remains unknown.

### Shift discriminator: `DS:0x48608`

`static`, clean.

At `0x26364` the program executes BIOS keyboard-status request `INT 16h` with `AH=02h`, tests bits 0 and 1 of the returned shift-state byte, and stores either `0xffffffff` or zero to `DS:0x48608`.

At `0x378e6` the M-key path compares this global with zero and takes a short `JE` directly to the self-management toggle. Consequently:

- **plain M (`Shift == 0`)** reaches the self-management toggle;
- **Shift+M** skips that write and enters a separate gated branch whose purpose remains unnamed.

### Selected planet relationship: `DS:0x43664`

`static`, clean.

`DS:0x43664` is the selected planet-object pointer used by the planet-window input/render seam.

At `0x16a13..0x16a36`, one independent assignment path:

1. reads a container/list object from `DS:0x43660`;
2. validates an index;
3. loads an element pointer from `[container + index*4 + 0x42]`;
4. stores it to `DS:0x43664` at `0x16a36`.

A second selection path stores an element pointer to the same global at `0x16ef7`.

### Managed flag: planet record `+0x5a`

`static + runtime`, clean.

RE2 statically established a 32-bit field at selected object `+0x5a`:

1. a supporting initializer-shaped routine at `0x22400` writes zero at `+0x5a` (`0x22421`);
2. the plain-M path reads `[selected+0x5a]` at `0x37915`, bitwise-NOTs it, and writes it at `0x3791f`;
3. the renderer checks `[selected+0x5a] == 0xffffffff` at `0x3afca` before requesting resource ID 98, which the exact CF3-pinned retail data identify as `Self Managed`;
4. state-consultation sites `0x35473` and `0x356cc` also test object-relative `+0x5a`; their downstream runtime meaning is not assigned by RE2/RE4.

RE4 now establishes the missing runtime ownership and transition facts on the exact canonical target.

Two independent ordinary-game runs observed two distinct player-owned planet records:

| Scenario | Runtime planet | Record size | Name location | Managed field | Observed transition |
| --- | --- | ---: | ---: | ---: | --- |
| pinned resumed game | `Xerxes I` | `0x7b` | `record+0x24` | `record+0x5a` | `0x00000000 -> 0xffffffff -> 0x00000000` |
| new Snovemdomas game | `Flammifer I` in the recorded final run | `0x7b` | `record+0x24` | `record+0x5a` | `0x00000000 -> 0xffffffff -> 0x00000000` |

The second scenario's generated homeworld name is not assumed stable; the runner discovers it from the runtime record and requires exactly one planet-like record with the reversible transition.

The record relationship is decisive for ownership: in each run the changing dword is exactly `+0x5a` inside a `0x7b` record whose `+0x24` NUL-terminated printable name is the selected player-visible planet. The `0x7b` size independently agrees with RE3's planet traversal stride. A side-table-only model no longer fits the evidence.

### Immediate input transition

`runtime`, clean.

After identifying the exact field, RE4 polls only its four-byte location while injecting plain M. Final recorded runs observed:

- `Xerxes I`: Manual -> Managed in `19.959 ms`; reverse observation in `30.943 ms`;
- `Flammifer I`: Manual -> Managed in `23.078 ms`; reverse observation in `28.682 ms`.

No turn was advanced and no other game command was issued between M and the state observation. This rejects a model where the UI merely queues a state change for later turn processing. The measurement is an event-loop bound, not a claim that RE4 timestamped the exact CPU instruction at `0x3791f`.

### Existing renderer observes Managed state

`runtime + static`, clean.

For each runtime planet, RE4 left `record+0x5a == 0xffffffff`, returned to the ordinary Planets list, and captured the existing `Self-Managed` presentation. An independently inspected 100x8 decoded-RGB region at `(280,73)` had the same SHA-256 in both unrelated runs:

`66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`.

This runtime result agrees with RE2's static `0x3afca` check and rejects a separate UI-display-only state for the existing Managed control.

RE4 deliberately does **not** claim runtime per-turn consumption from this observation. RE3 statically converges on the same `+0x5a` object-relative state, and RE5 owns the runtime proof that it gates the automatic-management decision path.

## Runtime signature and artifact boundary

`runtime`, clean.

The RE4 runner searches DOSBox's readable/writable mappings for exactly one relocation-tolerant copy of the canonical M-toggle read/NOT/write sequence beginning at RE2 site `0x37915`:

```text
8b 52 5a a1 ?? ?? ?? ?? f7 d2 89 50 5a e9 32 01 00 00 83 3d
```

Zero or multiple matches fail closed. The final two runs both observed the same concrete relocated prefix:

```text
8b525aa164a62400f7d289505ae932010000833dfc7c2100000f8425010000a1
```

Host mapping bases/offsets are explicitly run-local DOSBox implementation details and are not patch addresses. Raw process-memory snapshots are held only in memory and are not written to the artifact directory. The emitted artifact contains target/fixture identities, the bounded structural/state result, timings, and screenshots/hashes only.

## Negative runtime result: tutorial interception

`runtime`, clean.

CF4 Tutorial #5 was initially attractive because it reaches the Planetary Display quickly. It is **not** a valid RE4 state fixture: plain M caused the tutorial's Planetary Display instructional overlay to reappear/intercept the action instead of providing an uncontaminated normal-game Managed toggle.

No state conclusion was taken from that run. The final RE4 evidence comes from ordinary non-tutorial resumed/new games.

## Cross-build static corroboration

The same static UI/state seam exists in both product families and both locales:

| Build | Handler | M dispatch | Toggle write | Selected-object DS offset | Shift DS offset | Render check | State checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x37568` | `0x37a08` | `0x3791f` | `0x43664` | `0x48608` | `0x3afca` | `0x35473`, `0x356cc` |
| `ANTAG_INTL` | `0x375a8` | `0x37a48` | `0x3795f` | `0x436b4` | `0x48658` | `0x3b00a` | `0x354b3`, `0x3570c` |
| `PATCH_EN` | `0x35e98` | `0x36338` | `0x3624f` | `0x434f0` | `0x48494` | `0x398fa` | `0x345ab`, `0x347f9` |
| `PATCH_INTL` | `0x35ed8` | `0x36378` | `0x3628f` | `0x43540` | `0x484e4` | `0x3993a` | `0x345eb`, `0x34839` |

All four static scans agree on object-relative state offset `0x5a`, scan code `0x32`, render resource ID 98, and reversible NOT-based state encoding. The International builds remain corroboration only; M1 runtime support is still the canonical English Antagonizer hash.

## Calling-convention observation

`static`, clean.

RE2 did not promote compiler defaults into game facts. The binary shows a mixed boundary:

- at `ANTAG_EN 0x37346`, setup for `data\\planal%02d.shp`, three pushes, stack reads in the callee, and `add esp,0x0c` establish a cdecl-style caller-cleaned three-argument stack call for this variadic formatting boundary;
- `0x37568` itself immediately consumes live `EAX`, `DX`, `EBX`, and `ECX` inputs.

Later patch/hook work must confirm the ABI at each relevant seam rather than applying one blanket convention.

## Confidence and remaining unknowns

**Established, high confidence (`static + runtime`, clean):**

- plain **M** reaches the existing Managed toggle in ordinary game state;
- `DS:0x48608` is the Shift discriminator used by that path;
- `DS:0x43664` is the selected-object relationship used by the UI seam;
- the selected planet is represented by a `0x7b` runtime record containing its name at `+0x24` in the two tested states;
- record `+0x5a` is the 32-bit Managed/self-management state;
- `0x00000000` is Manual and `0xffffffff` is Managed on the tested UI path;
- M changes the field reversibly within normal input/event servicing, before any turn advancement;
- the ordinary Planets renderer displays `Self-Managed` when that field is set;
- a side-table-only or deferred-until-turn UI model is rejected for the existing Managed state.

**Still unknown / intentionally deferred:**

- a symbol-level C++ type/name for the planet record;
- the formal event-enum name for `DX == 7`;
- exact runtime selector/base mapping for the static DS-relative globals, which RE4 did not need to guess;
- runtime per-turn consumption and causal path into existing automation — **RE5**;
- save-game persistence/serialization details of the state;
- any patch/integration mechanism or new profile representation.
