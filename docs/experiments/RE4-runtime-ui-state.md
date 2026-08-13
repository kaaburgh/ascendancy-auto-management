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
- immutable runtime definition is exactly the committed `tools/retail-runtime-manifest.json`, SHA-256 `814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852`;
- that manifest contains exactly 17 pinned immutable files and the runner rejects any different/custom manifest content;
- the runtime tree is additionally rejected if two filenames collide case-insensitively, preventing a hashed path from differing from the path DOSBox may open;
- the resumed-game scenario separately pins mutable/operator-supplied `resume.gam`: 81647 bytes, SHA-256 `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`.

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

1. requires the supplied fixture manifest bytes to match the committed retail manifest SHA-256 above and validates its expected id/schema/17-file count;
2. rejects case-insensitive filename collisions in the runtime tree, then verifies every pinned immutable file by exact size/SHA-256 and independently re-checks canonical `ANTAG.EXE` identity;
3. for `resume`, separately requires the exact `resume.gam` SHA-256 above;
4. copies the supplied game tree to a temporary mount, so guest writes do not touch the operator fixture;
5. starts Xvfb and DOSBox, reaches the 640x480 game UI, and drives only the small scenario-specific path to Planets → Planetary Display;
6. searches readable/writable DOSBox mappings for exactly one relocation-tolerant copy of the canonical RE2 toggle sequence beginning at `0x37915`:

   ```text
   8b 52 5a a1 ?? ?? ?? ?? f7 d2 89 50 5a e9 32 01 00 00 83 3d
   ```

   Zero or multiple matches fail closed.
7. takes three in-memory snapshots of only the containing host mapping around `M`, requiring a `0 -> ffffffff -> 0` dword transition at record-relative `+0x5a`;
8. requires that the containing `0x7b` record has a printable NUL-terminated planet name at `+0x24`; the resumed scenario additionally requires `Xerxes I` exactly;
9. after identifying the field, polls only that four-byte host location and records input-to-transition latency for both directions;
10. captures the same Planets-list RGB region in Manual state, Managed state, and after restoring Manual. PASS requires all three invariants simultaneously:
    - Managed region equals pinned `Self-Managed` RGB SHA-256 `66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`;
    - Manual region differs from Managed;
    - restored-Manual region exactly returns to the original Manual region hash;
11. terminates the temporary runtime and writes only compact `run.json` plus three screenshots. Raw process-memory snapshots are held in memory and never written to the artifact directory.

Synthetic tests now cover the two review-discovered failure modes in addition to the original state/signature checks: arbitrary/custom fixture manifests fail closed, case-insensitive runtime filename collisions fail closed, and the renderer oracle rejects both a non-differential Manual/Managed frame and a failure to return to the Manual region after restore.

### Commands used for the hardened final runs

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

## Final hardened runtime observations

Both post-review runs passed the strengthened fixture and differential-renderer contract against the exact canonical target.

### Planet A — resumed game / `Xerxes I`

`runtime`, clean.

- runtime toggle anchor bytes: `8b525aa164a62400f7d289505ae932010000833dfc7c2100000f8425010000a1`;
- host mapping size: `0x1439000` bytes;
- anchor offset inside that ephemeral host mapping: `0x5f3925`;
- selected planet record offset inside the same snapshot mapping: `0x66aebc`;
- record name at `record+0x24`: `Xerxes I`;
- state field at `record+0x5a` / mapping offset `0x66af16`;
- observed values: `00000000 -> ffffffff -> 00000000`;
- input-to-Managed observation: `19.219 ms`;
- reverse Managed-to-Manual poll: `31.509 ms`;
- no turn was advanced between input and either state observation;
- Manual RGB region `(280,73,100,8)`: `6ca137daa8b4d9eb974728aac338c817859d0eb0a1c3ba43cde244cfd7a248ec`;
- Managed RGB region: `66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`;
- restored-Manual RGB region: `6ca137daa8b4d9eb974728aac338c817859d0eb0a1c3ba43cde244cfd7a248ec`.

### Planet B — independent new Snovemdomas game / `Paragon III`

`runtime`, clean.

- the same runtime toggle anchor bytes were found uniquely;
- host mapping size: `0x1001000` bytes;
- anchor offset inside that separate ephemeral host mapping: `0x1bb925`;
- selected planet record offset: `0x232616`;
- record name at `record+0x24`: `Paragon III`;
- state field at `record+0x5a` / mapping offset `0x232670`;
- observed values: `00000000 -> ffffffff -> 00000000`;
- input-to-Managed observation: `37.829 ms`;
- reverse Managed-to-Manual poll: `31.582 ms`;
- no turn was advanced;
- Manual RGB region: `6ca137daa8b4d9eb974728aac338c817859d0eb0a1c3ba43cde244cfd7a248ec`;
- Managed RGB region: `66df0c5f9a6774156363abc9cd878ec683b64aabd54c4d781387236cd1fff160`;
- restored-Manual RGB region: `6ca137daa8b4d9eb974728aac338c817859d0eb0a1c3ba43cde244cfd7a248ec`.

The host mapping addresses and offsets above are **run-local DOSBox implementation observations**, not stable game addresses and not patch locations. The stable target-specific facts remain the exact executable hash, canonical code sites, the record-relative offsets, the pinned fixture contract, and the relocation-tolerant instruction relationship.

The new-game homeworld differed from the earlier exploratory run (`Flammifer I`), which is expected and strengthens the intended invariant: RE4 depends on the record relationship, not on one generated planet name.

## Hypothesis update

### H1 — state is stored directly in the planet object/record

**Established for the tested canonical runtime.**

The changing dword is not merely near a plausible allocation. In both hardened runs it is exactly `+0x5a` inside a `0x7b` record whose `+0x24` printable name is the player-visible selected planet (`Xerxes I` and `Paragon III`). That record size independently matches RE3's planet traversal stride.

A side-table-only model does not fit these observations.

### H2 — the UI only queues a command and the state changes later

**Rejected as a deferred/turn-time model; bounded event-loop latency remains.**

The field changes within normal input/event servicing (about 19–38 ms in the hardened repetitions) while still on the Planetary Display and without any turn advancement or other game command. This does not claim an instruction-level timestamp for `0x3791f`; it establishes that the state transition is not deferred until turn processing.

### H3 — UI display state is separate from the toggled state

**Rejected for the existing Managed UI by a differential runtime oracle.**

For both independent runs, the same Planets-list region changed from Manual hash `6ca137...48ec` to the pinned Managed hash `66df0c...160` while `record+0x5a == 0xffffffff`, then returned exactly to `6ca137...48ec` after restoring the same record field to zero. This closes the earlier vacuous-oracle possibility where static pixels could have satisfied a Managed-only check.

### H4 — UI and simulation automation state may still be distinct

**Runtime RE4 does not overclaim this final step.**

RE2/RE3 statically converge on the same object-relative `+0x5a` field for UI and per-turn consultation, which makes a separate simulation-state model unlikely. RE5 still owns runtime proof that this confirmed field gates the per-turn automatic-management path. RE4 does not execute that downstream roadmap item here.

## Review hardening result

Two review findings materially improved the experiment contract and are now covered by tests and repeated runtime evidence:

1. fixture identity is no longer caller-defined: a different schema-1 manifest cannot produce `clean/PASS`, and ambiguous case-insensitive filenames are rejected before the tree is copied;
2. the `Self-Managed` visual oracle is now explicitly differential and reversible rather than Managed-only.

These changes do not broaden RE4 into RE5; they strengthen only the evidence gates needed for RE4's existing acceptance claim.

## Result

RE4 acceptance is met on the canonical target:

- the existing Managed state is a per-planet dword at planet-record `+0x5a`;
- `0x00000000` is Manual and `0xffffffff` is Managed for the tested UI path;
- plain M reversibly changes that field before any turn processing;
- the state is tied to two distinct runtime planet records by their embedded names and the independently known `0x7b` record size;
- the existing renderer changes to the pinned `Self-Managed` presentation when the field is set and returns to the exact Manual presentation region after the field is cleared;
- the experiment is repeatable and fail-closed on committed fixture identity, case-insensitive path ambiguity, target identity, runtime signature multiplicity, state transition, record structure, and the reversible renderer oracle.

Still intentionally outside RE4: runtime per-turn consumption/causality (RE5), profile-state architecture (A1), patch mechanism (A2/P1/P2), and new profile UI/behavior.
