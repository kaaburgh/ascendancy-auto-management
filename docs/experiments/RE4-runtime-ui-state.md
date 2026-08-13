# RE4 — runtime Managed-state ownership and UI transition

Date: 2026-08-13  
Roadmap item: RE4  
Blind-RE provenance: **clean**  
Evidence classes used below: `runtime`, `static`, and `synthetic` as marked.

## Question

What exact runtime state transition occurs when the existing per-planet Managed/self-management control is toggled, and is that state owned by the selected planet record rather than a side table or a deferred command?

RE4 deliberately does **not** trace the per-turn decision/policy/action path. That remains RE5.

## Inputs and evidence boundary

Canonical target:

- `ANTAG.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Owned retail fixture:

- maintainer-supplied `Ascendancy_DOS_EN.zip` — 42648482 bytes — SHA-256 `e9f1159c15fd50b9455f817470e13cbc6b17e70551793774b4a7b074859ce987`;
- all 17 immutable runtime files were re-verified against `tools/retail-runtime-manifest.json` before the final runs;
- the resumed-game scenario additionally pins the mutable/operator-supplied `resume.gam` separately: 81647 bytes, SHA-256 `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`.

Generic runtime tooling:

- operator-supplied DOSBox 0.74-3 Linux x86_64 bundle; its `verify.sh` reported `DOSBox runtime verification: PASS`;
- Xvfb/X11 XTEST for bounded input;
- `ffmpeg`/`x11grab` for 640x480 frame capture;
- Linux `/proc/<dosbox-pid>/maps` and `/proc/<dosbox-pid>/mem` for bounded host-side observation of DOSBox's emulated guest-memory mapping.

No external target-specific recovered knowledge, unsupported repository history, source reconstruction, cheat table, or rescue unlock was used. The starting target-specific anchors are the supported RE2/RE3 findings already on `main`.

## Static handoff being tested

RE2 established for the exact canonical hash:

- selected-object global: `DS:0x43664`;
- plain-M Managed path reads `[selected+0x5a]` at `0x37915`, bitwise-NOTs it, and writes it at `0x3791f`;
- the renderer checks `[selected+0x5a] == 0xffffffff` at `0x3afca` before requesting resource ID 98 (`Self Managed`).

RE3 independently established a `0x7b` planet-record stride and a per-turn player gate that consults the same object-relative `+0x5a` field. RE4 uses the `0x7b` relationship only as a structural invariant; it does not execute or claim RE5's per-turn causality.

## Reproducible runner

`scripts/run_re4_runtime_state.py` performs one bounded scenario per invocation. Two separate invocations are intentional: DOSBox/Xlib teardown between target runs is treated as part of the isolation boundary instead of keeping two game sessions in one host process.

The runner:

1. verifies the exact canonical target and every immutable file in `tools/retail-runtime-manifest.json`;
2. for `resume`, separately requires the exact `resume.gam` SHA-256 above;
3. copies the supplied game tree to a temporary mount, so guest writes do not touch the operator fixture;
4. starts Xvfb and DOSBox, reaches the 640x480 game UI, and drives only the small scenario-specific path to Planets → Planetary Display;
5. searches readable/writable DOSBox mappings for exactly one relocation-tolerant copy of the canonical RE2 toggle sequence beginning at `0x37915`:

   ```text
   8b 52 5a a1 ?? ?? ?? ?? f7 d2 89 50 5a e9 32 01 00 00 83 3d
   ```

   Zero or multiple matches fail closed.
6. takes three in-memory snapshots of only the containing host mapping around `M`, requiring a `0 -> ffffffff -> 0` dword transition at record-relative `+0x5a`;
7. requires that the containing `0x7b` record has a printable NUL-terminated planet name at `+0x24`; the resumed scenario additionally requires `Xerxes I` exactly;
8. after identifying the field, polls only that four-byte host location and records input-to-transition latency for both directions;
9. leaves the field Managed, returns to the Planets list, captures the frame, and requires an independently inspected RGB-region oracle for the existing `Self-Managed` line;
10. re-enters the planet, returns the field to Manual, terminates the temporary runtime, and writes only compact `run.json` plus the two screenshots. Raw process-memory snapshots are held in memory and never written to the artifact directory.

Synthetic tests cover relocation wildcards, multiple anchor matches, unrelated toggles, wrong restore values, and zero/ambiguous structured transition candidates.

### Commands used for the final runs

Resumed-game planet:

```sh
python scripts/run_re4_runtime_state.py \
  --game-dir <owned-retail-tree> \
  --dosbox <dosbox-0.74-3> \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --scenario resume \
  --resume-sha256 fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3 \
  --artifacts artifacts/re4-resume
```

Independent new-game planet:

```sh
python scripts/run_re4_runtime_state.py \
  --game-dir <owned-retail-tree> \
  --dosbox <dosbox-0.74-3> \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --scenario new-snovemdomas \
  --artifacts artifacts/re4-new
```

The new-game scenario deliberately does not pin a planet name because the generated homeworld name varies. It discovers and records the selected planet name from the runtime record and fails closed unless exactly one planet-like record exhibits the required reversible `+0x5a` transition.

## Negative result: Tutorial #5 is not a valid RE4 toggle fixture

`runtime`, clean.

The first bounded attempt reused CF4's Tutorial #5 (`Managing Planets and Research`) navigation because it reaches the same Planetary Display quickly. That path is unsuitable for RE4: pressing **M** in the tutorial caused the tutorial's Planetary Display instructional overlay to reappear/intercept the action rather than providing an uncontaminated normal-game Managed toggle.

No state conclusion was taken from that run. RE4 switched to two ordinary non-tutorial states: the pinned resumed game and an independently created new Snovemdomas game. This negative result is preserved so later runtime work does not accidentally validate the tutorial controller instead of the real UI behavior.

## Final runtime observations

Both final runs passed against the exact canonical target.

### Planet A — resumed game / `Xerxes I`

`runtime`, clean.

- runtime toggle anchor bytes: `8b525aa164a62400f7d289505ae932010000833dfc7c2100000f8425010000a1`;
- host mapping size: `0x1403000` bytes;
- anchor offset inside that ephemeral host mapping: `0x5bd925`;
- selected planet record offset inside the same snapshot mapping: `0x634ebc`;
- record name at `record+0x24`: `Xerxes I`;
- state field at `record+0x5a` / mapping offset `0x634f16`;
- observed values: `00000000 -> ffffffff -> 00000000`;
- input-to-Managed observation: `19.959 ms`;
- reverse Managed-to-Manual poll: `30.943 ms`;
- no turn was advanced between input and either state observation;
- managed Planets-list screenshot SHA-256: `9d87e575d442e1c63a01184a617a4ecf1175523a132f7af1d786a05d4f748b71`;
- the inspected `Self-Managed` text region `(280,73,100,8)` has decoded-RGB SHA-256 `66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`.

### Planet B — independent new Snovemdomas game / `Flammifer I`

`runtime`, clean.

- the same runtime toggle anchor bytes were found uniquely;
- host mapping size: `0x1731000` bytes;
- anchor offset inside that separate ephemeral host mapping: `0x8eb925`;
- selected planet record offset: `0x9646c2`;
- record name at `record+0x24`: `Flammifer I`;
- state field at `record+0x5a` / mapping offset `0x96471c`;
- observed values: `00000000 -> ffffffff -> 00000000`;
- input-to-Managed observation: `23.078 ms`;
- reverse Managed-to-Manual poll: `28.682 ms`;
- no turn was advanced;
- managed Planets-list screenshot SHA-256: `729b79d30670213ec421e8027bcde8f9081696a1ecb9c3156d8147325e6b117e`;
- the same `Self-Managed` RGB-region oracle matched exactly.

The host mapping addresses and offsets above are **run-local DOSBox implementation observations**, not stable game addresses and not patch locations. The stable target-specific facts remain the exact executable hash, canonical code sites, the record-relative offsets, and the relocation-tolerant instruction relationship.

## Hypothesis update

### H1 — state is stored directly in the planet object/record

**Established for the tested canonical runtime.**

The changing dword is not merely near a plausible allocation. In both independent runs it is exactly `+0x5a` inside a `0x7b` record whose `+0x24` printable name is the player-visible selected planet (`Xerxes I` and `Flammifer I`). That record size independently matches RE3's planet traversal stride.

A side-table-only model does not fit these observations.

### H2 — the UI only queues a command and the state changes later

**Rejected as a deferred/turn-time model; bounded event-loop latency remains.**

The field changes within about 20–31 ms of the injected M event, while still on the Planetary Display and without any turn advancement or other game command. This does not claim an instruction-level timestamp for `0x3791f`; it establishes that the state transition is part of normal immediate input/event servicing, not something deferred until turn processing.

### H3 — UI display state is separate from the toggled state

**Rejected for the existing Managed UI.**

After the same `+0x5a` field reaches `0xffffffff`, the ordinary Planets list renders the existing `Self-Managed` line. The exact same stable RGB region matched in both unrelated planet runs. Returning the field to zero removes the Managed state on the next normal presentation.

### H4 — UI and simulation automation state may still be distinct

**Runtime RE4 does not overclaim this final step.**

RE2/RE3 statically converge on the same object-relative `+0x5a` field for UI and per-turn consultation, which makes a separate simulation-state model unlikely. RE5 still owns runtime proof that this confirmed field gates the per-turn automatic-management path. RE4 does not execute that downstream roadmap item here.

## Result

RE4 acceptance is met on the canonical target:

- the existing Managed state is a per-planet dword at planet-record `+0x5a`;
- `0x00000000` is Manual and `0xffffffff` is Managed for the tested UI path;
- plain M reversibly changes that field before any turn processing;
- the state is tied to two distinct runtime planet records by their embedded names and the independently known `0x7b` record size;
- the existing renderer displays `Self-Managed` when the field is set;
- the experiment is repeatable and fail-closed on target identity, runtime signature multiplicity, state transition, record structure, and render oracle.

Still intentionally outside RE4: runtime per-turn consumption/causality (RE5), profile-state architecture (A1), patch mechanism (A2/P1/P2), and new profile UI/behavior.
