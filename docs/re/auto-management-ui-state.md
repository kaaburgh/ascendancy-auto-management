# Existing auto-management UI/state seam

## Targets and evidence boundary

Canonical M1 target:

- `ANTAG_EN.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Static corroboration only:

- `PATCH_EN.EXE` — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- `ANTAG_INTL.EXE` — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`;
- `PATCH_INTL.EXE` — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

Blind-RE provenance: **clean**. Findings in this note are **static** unless explicitly marked otherwise. No external target-specific recovered knowledge was used. Addresses are code-object virtual addresses for the named binaries. Data globals such as `DS:0x43664` are **DS-relative offsets**; the DOS/4G runtime selector/base mapping is not established by RE2.

The reproducible static scan is `scripts/generate_re2_ui_state_map.py`; procedure and negative/corrective findings are recorded in [`../experiments/RE2-auto-management-ui-state-static.md`](../experiments/RE2-auto-management-ui-state-static.md).

## Established UI/state seam on `ANTAG_EN`

### Planet-window handler candidate: `0x37568`

`0x37568` is statically anchored to the planet display rather than named from guesswork:

- its setup resolves the `PLANLIST` and `PLSQUARE` data strings;
- nearby setup consumes the planet-window resource family already bounded by RE1;
- the same instruction shape exists in the English patch at `0x35e98` and shifts by the expected locale delta in both International builds.

The entry immediately saves live incoming `EAX`, `DX`, `EBX`, and `ECX` into locals. Therefore RE2 may reason about these four register inputs at this handler without assuming a compiler default calling convention.

The branch for `DX == 7` eventually dispatches the original `ECX` value as PC/AT set-1 keyboard scan codes. At `0x37a28` it compares against `0x32`, the scan code for **M**, and the branch at `0x37a2b` reaches the state-toggle block at `0x378e6`.

This matches the project-supported user-facing behavior recorded by CF3: the game documents **M** as the Managed/self-management toggle for colonies. The exact numeric event-enum name represented by `DX == 7` remains unknown; RE2 does not invent one.

### Shift discriminator: `DS:0x48608`

The modifier used by the M branch is independently identified rather than inferred from the toggle alone. At `0x26364` the program executes BIOS keyboard-status request `INT 16h` with `AH=02h`, tests bits 0 and 1 of the returned shift-state byte, and stores either `0xffffffff` or zero to `DS:0x48608`.

At `0x378e6` the M-key path compares `DS:0x48608` with zero and takes a short `JE` directly to the self-management toggle. Consequently:

- **plain M (`Shift == 0`)** reaches the self-management toggle;
- **Shift+M** skips that write and enters a separate gated diagnostic/alternate branch.

The alternate Shift+M branch is not needed by RE2 and its purpose is left unnamed.

### Selected planet/object relationship: `DS:0x43664`

`DS:0x43664` is the high-confidence selected planet-object pointer for the current planet-window seam.

One independently useful assignment path at `0x16a13..0x16a36`:

1. reads a container/list object from `DS:0x43660`;
2. validates an index;
3. loads an element pointer from `[container + index*4 + 0x42]`;
4. stores that pointer to `DS:0x43664` at `0x16a36`.

A second selection path stores an element pointer to the same global at `0x16ef7`. The planet-window handler and planet-display rendering code then repeatedly dereference `DS:0x43664` at a consistent field family. Runtime ownership/lifetime still belongs to RE4; the static relationship is strong enough to make RE4 bounded.

### Self-management flag: selected object `+0x5a`

The existing self-management state is statically established as a 32-bit field at **`selected_object + 0x5a`** for the canonical target.

Evidence converges from independent paths:

1. **Supportive initializer candidate.** A compact initializer-shaped routine at `0x22400` writes zero to several fields including a dword at `+0x5a` (`0x22421`). Static RE2 does not independently prove that this initializer owns the same planet allocation, so this observation is supporting evidence only.
2. **Input write.** The plain-M path loads the selected pointer from `DS:0x43664`, reads `[selected+0x5a]` at `0x37915`, bitwise-NOTs it, and writes it back at `0x3791f`. The renderer below recognizes `0xffffffff` as the Managed state, and bitwise NOT gives the reversible `0 ↔ 0xffffffff` encoding.
3. **Planet-display rendering.** At `0x3afba` the renderer loads the same selected pointer, checks `[selected+0x5a] == 0xffffffff` at `0x3afca`, and on that branch requests resource ID **98**. The exact attached retail `ASCEND00.COB` hash pinned by CF3 maps resource 98 to the user-facing text `Self Managed`.
4. **User-facing semantics.** The same pinned retail data state that pressing **M** toggles the Managed feature and that its status is visible in the population area/Planets screen. This independently connects the scan-code branch to the display label rather than deriving semantics from the field write alone.
5. **Non-UI consultation.** The RE1 planet-update region checks `[ESI+0x5a] == 0` at `0x35473` and `0x356cc`; when the field is nonzero, the immediately following call boundaries are bypassed. RE2 records these only as state-consultation sites suitable for later instrumentation. The exact callees' semantics and the per-turn policy path are deliberately left to RE3/RE5.

Together these observations are stronger than a “likely flag” hypothesis: for the exact canonical binary, `+0x5a` is the existing **self-management/Managed flag** used by the planet UI. What RE2 does **not** establish is the runtime identity/lifetime of the owning allocation across two planets; RE4 must still prove per-planet ownership dynamically.

## Cross-build corroboration

The same UI/state seam exists in both product families and both locales. This is useful evidence that the control/state representation predates Antagonizer-specific downstream logic.

| Build | Handler | M dispatch | Toggle write | Selected-object DS offset | Shift DS offset | Render check | State checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x37568` | `0x37a08` | `0x3791f` | `0x43664` | `0x48608` | `0x3afca` | `0x35473`, `0x356cc` |
| `ANTAG_INTL` | `0x375a8` | `0x37a48` | `0x3795f` | `0x436b4` | `0x48658` | `0x3b00a` | `0x354b3`, `0x3570c` |
| `PATCH_EN` | `0x35e98` | `0x36338` | `0x3624f` | `0x434f0` | `0x48494` | `0x398fa` | `0x345ab`, `0x347f9` |
| `PATCH_INTL` | `0x35ed8` | `0x36378` | `0x3628f` | `0x43540` | `0x484e4` | `0x3993a` | `0x345eb`, `0x34839` |

All four scans independently require exactly one match for the handler, M dispatch, toggle sequence, BIOS shift probe, selected-list assignment, zero-initializer candidate, Managed renderer, two state checks, and known-arity formatting call. All four agree on object-relative state offset `0x5a`, scan code `0x32`, render resource ID 98, and `0 ↔ 0xffffffff` toggle semantics.

The International builds remain corroboration only; M1 support is still the canonical English Antagonizer hash.

## Calling-convention observation

RE2 does **not** promote “Watcom defaults to `__watcall`” into a game fact. The binary shows a mixed calling boundary.

### Independently inferable stack call

At `ANTAG_EN 0x37346`, setup for the format string `data\\planal%02d.shp` is unambiguous: the format has exactly one conversion. The caller pushes:

1. the integer value (`EBX`);
2. the format-string pointer;
3. the destination-buffer pointer;

then calls `0x76d09` and performs `add esp, 0x0c` afterwards. The callee reads its inputs from stack locations before forwarding them internally. This establishes a **cdecl-style, caller-cleaned three-argument stack call** for this variadic formatting boundary.

### Register-passed internal handler inputs

Conversely, `0x37568` immediately saves incoming `EAX`, `DX`, `EBX`, and `ECX`; no stack-only interpretation is needed to establish those live inputs. The formatting helper itself also converts its stack-facing interface into register values for an internal call.

**RE2 conclusion:** the executable uses a mixed ABI boundary consistent with Watcom code: stack passing is proven for the variadic runtime-style call, while this internal UI handler consumes register-passed inputs. Later work must confirm each relevant seam rather than applying one blanket convention to the whole binary.

## Minimal RE4 runtime experiment

RE4 should confirm ownership and transition causality, not rediscover the static seam.

Use the exact canonical `ANTAG.EXE` hash plus the CF3-verified retail fixture and scriptable `dosbox-debug` path. The bounded experiment should stop after these observations:

1. Reach the Planet Display for player-owned planet **A** with no Shift modifier.
2. Break immediately before/at the write `0x3791f`. Record the runtime code mapping, `DS`, the value loaded from `DS:0x43664`, `EAX`, `EDX`, and the dword at `[EAX+0x5a]` before and after one **M** press.
3. Press **M** again on the same planet and require the same owning pointer with the reverse `0xffffffff → 0` transition.
4. Select a different player-owned planet **B**, press **M**, and require a different selected-object pointer whose `+0x5a` changes independently while planet A's value remains unchanged.
5. On at least one planet, hit the render check `0x3afca` after opening the population/status presentation and show that it observes the same object's `+0x5a` value used by the M-key write.

This single experiment distinguishes the roadmap hypotheses:

- **direct planet field** — supported if the write address is exactly the selected object's `+0x5a` for two distinct planet objects;
- **side table** — supported instead if the observed write is not owned by the selected object relationship;
- **queued command** — supported instead if M does not cause the write synchronously at the identified handler seam;
- **UI/simulation split** — remains possible only if the rendered state is not the same field/value later observed at established state-consultation sites.

The artifact should contain only target/fixture hashes, runtime selector/base mapping needed to interpret the static addresses, breakpoint hit records, register values, selected-object addresses, bounded before/after dwords, and optional screenshots/logs. Do not include retail game files or broad memory dumps.

## Confidence and remaining unknowns

**Established, high confidence (`static`, clean):**

- plain **M** reaches the planet-window Managed toggle;
- `DS:0x48608` is the Shift-state boolean used to distinguish plain M from Shift+M;
- `DS:0x43664` is the selected object used by the planet-window seam;
- selected object `+0x5a` is the 32-bit Managed/self-management flag and is toggled by bitwise NOT between the UI's observed `0`/`0xffffffff` states;
- the planet-display renderer treats `0xffffffff` as Managed and selects resource ID 98 (`Self Managed`);
- the same field/control shape repeats in both product families/locales;
- stack-only calling is false as a blanket model for the handler; a mixed stack/register boundary is directly observed.

**Still unknown / intentionally deferred:**

- runtime selector/base mapping and allocation lifetime;
- a symbol-level C++ type/name for the selected object;
- the formal event-enum name for `DX == 7`;
- exact semantics of the calls bypassed by the two `+0x5a` checks;
- the per-turn decision/policy/action path — **RE3**, not RE2;
- save-game persistence and serialization of this state;
- any patch/injection mechanism.
