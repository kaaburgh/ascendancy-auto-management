# RE5 — runtime automatic-management turn-path experiment

Date: 2026-08-13  
Roadmap item: RE5  
Blind-RE provenance: **clean**  
Evidence class: **runtime**, with RE3 static addresses used only as experiment boundaries.

## Question

Does the RE4-confirmed per-planet Managed state actually control the RE3 automatic-management path during turn processing, and where is the smallest established seam that M1 must preserve to keep the original automation behavior?

The experiment is deliberately causal rather than a whole-turn trace. It compares the same pinned saved planet in Manual and Managed modes and then temporarily removes two whole-instruction boundaries from the **live DOSBox process only**:

1. the RE3 gate-to-policy call `0x3c118 -> 0x3d8f0`;
2. the downstream action-byte commit `0x34df2: mov [planet+0x54], al` inside the `0x34b0c` mutation candidate.

## Inputs

Canonical target:

- `ANTAG.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Runtime fixture:

- exact committed `tools/retail-runtime-manifest.json` — SHA-256 `814c37ea8683e9c32ce494bcb9568d08a33d3ef8e6d91b99ac07f37958269852`;
- immutable manifest entries: 17, all size/SHA-256 verified before execution;
- mutable input used by the scenario: `resume.gam`, SHA-256 `fe7b29f63b685df3b098c0bd109a44e95c9a36a2116617b6c0363eb289a813d3`.

Runtime/tooling:

- supplied DOSBox 0.74-3 Linux x86-64 runtime bundle; its `verify.sh` passed before the experiment;
- DOSBox CPU core forced to `normal` so live guest-code diagnostic writes are immediately observed and reversible;
- Xvfb + XTEST for bounded input;
- `/proc/<pid>/mem` for bounded guest-backing-memory reads/writes in the DOSBox process;
- `scripts/run_re5_runtime_turn_path.py` for the final fail-closed experiment.

The selected player planet is `Xerxes I`, independently established by RE4 as a structured `0x7b` runtime record with its name at `+0x24`. The pinned resume begins with:

- owner candidate `+0x57 = 0x00`;
- current selected slot `+0x52 = 0xffff`;
- current action `+0x54 = 0xff` (empty);
- Managed state `+0x5a = 0x00000000` (Manual).

No external target-specific recovered knowledge, unsupported repository history, cheat table, source reconstruction, or third-party mod internals were used.

## Instrumentation safety

The runner reuses RE4's exact fixture verification, unique relocation-tolerant runtime toggle signature, UI driver and bounded process-memory primitives.

It does **not** assume a DOS/4G selector/base mapping. RE2's uniquely matched runtime toggle sequence is used only as a mapping-local code anchor corresponding to static `0x37915`; RE5 resolves another static code site by the already established code-relative delta inside that same runtime mapping.

Before either live diagnostic patch, the runner requires the exact canonical instruction bytes:

| Purpose | Static VA | Expected whole instruction | Diagnostic bytes |
| --- | ---: | --- | --- |
| suppress gate → policy | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | five NOPs |
| suppress action commit | `0x34df2` | `88 46 54` (`mov [esi+0x54], al`) | three NOPs |

A zero/ambiguous runtime anchor, unexpected bytes, short process read/write, missing structured `Xerxes I` record, non-empty initial `+0x52/+0x54`, unexpected state transition, or failed patch restore fails closed. Each patched scenario runs in a fresh process and temporary copy of the retail tree. Original bytes are restored and byte-verified before process teardown; the repository or supplied retail tree is never modified.

Raw memory snapshots and host addresses are not written to artifacts. `run.json` retains only hashes, mapping size/relative anchor offset, object-relative state values, static patch sites/bytes, bounded timing observations and pass/fail oracles.

### Stable sampling under fast-forward

An early clean-run attempt exposed an instrumentation problem: concurrent `/proc/<pid>/mem` polling can stall while DOSBox is executing the `normal` core at fast-forward. This was treated as a diagnostic-tool failure rather than target evidence.

The final runner stops DOSBox with `SIGSTOP` for each small `0x12`-byte sample, performs one bounded read, resumes with `SIGCONT`, and samples at 25 ms intervals. This produces coherent bounded observations and prevents an unbounded memory read. The observed millisecond values below therefore describe the diagnostic sampling window; they are **not** instruction-level or gameplay-performance measurements.

## Procedure

For every sub-scenario the runner starts from a fresh copy of the same pinned fixture and save:

1. start canonical `ANTAG.EXE` under DOSBox `core=normal`;
2. resume the pinned save and open `Xerxes I`;
3. require a unique RE4 runtime anchor and unique player-owned `Xerxes I` record;
4. require `+0x52 == 0xffff` and `+0x54 == 0xff`;
5. leave the planet Manual or toggle ordinary **M** to the RE4-confirmed `+0x5a == 0xffffffff` Managed state;
6. apply the scenario's optional live-process diagnostic patch after exact-byte validation;
7. return to the main screen, enable fast-forward, and sample `+0x52/+0x54/+0x5a` for a bounded 7-second window;
8. stop fast-forward, validate the scenario oracle, restore/verify any diagnostic instruction bytes, and terminate the temporary process.

The four final sub-scenarios were executed individually because the surrounding container tool imposes a shorter single-command wall-time than the four fresh DOSBox startups combined. Each focused invocation is the same code path selected by `--scenario`; `--scenario all` remains the one-command operator path where the host permits the combined runtime.

## Final observations

### 1. Manual control: no automatic selection or commit

Pinned start/armed state:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = 00000000
```

Observed for `7016.879 ms` of the bounded window:

- no `+0x52` change;
- no `+0x54` change;
- `+0x5a` remained zero;
- DOSBox remained alive.

Result: **PASS**.

### 2. Managed control: automatic selection reaches action commit

After ordinary **M**:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = ffffffff
```

Observed at the first mutation sample (`4501.775 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> 00
+0x5a: ffffffff (unchanged)
```

`0x0034` and `0x00` are recorded values only; RE5 does not assign gameplay semantics to those codes.

Result: **PASS**.

### 3. Managed + gate-to-policy call suppressed: no selection or commit

The runner verified `e8 d3 17 00 00` at static `0x3c118`, replaced the complete five-byte call with NOPs in the live process, then armed the same Managed state.

Observed for `7013.522 ms`:

- `+0x52` remained `ffff`;
- `+0x54` remained `ff`;
- `+0x5a` remained `ffffffff`;
- original call bytes were restored and byte-verified;
- DOSBox remained alive.

Result: **PASS**.

**Runtime conclusion:** the RE3 `0x3c118 -> 0x3d8f0` boundary is necessary for the tested automatic selection/action path. This is stronger than a breakpoint hit: removing only that call removes the downstream observable selection while preserving the Managed state and process execution.

### 4. Managed + final action-byte write suppressed: selection survives, commit does not

The runner verified `88 46 54` at static `0x34df2` and replaced that complete three-byte instruction with NOPs in the live process.

The policy path still produced a selected slot at the first observed selection sample (`6021.757 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> ff
+0x5a: ffffffff (unchanged)
```

During the full `7006.122 ms` bounded window, `+0x54` never left `ff`. The original `88 46 54` bytes were restored and byte-verified; DOSBox remained alive.

Result: **PASS**.

**Runtime conclusion:** selection/decision output exists upstream of the `+0x54` write, while `0x34df2` is a concrete action-commit seam in the tested `0x34b0c` mutation path. This experimentally separates policy output (`+0x52`) from current-action commit (`+0x54`).

## Exploratory negative result retained

Before settling on the commit-write intervention, a clean exploratory run suppressed the RE3-highlighted internal call site `0x3df88 -> 0x34b0c` (`e8 7f 6b ff ff`) alone. The Managed planet still received an automatic action in that run (about 4.3 seconds after fast-forward began), and the original bytes were restored.

Therefore `0x3df88` is **not** established as the unique runtime policy-to-mutation call for the pinned `Xerxes I` scenario. RE3 already identified several static calls from the policy candidate into `0x34b0c`; RE5 deliberately does not guess which individual caller supplied this particular selected action. The downstream `0x34df2` write is the stronger runtime boundary because suppressing it preserved upstream selection while preventing commit.

## Interpretation

### Established, runtime, clean

1. On the same exact saved planet with the same empty-action starting state, legacy Manual remains idle in the bounded turn window while legacy Managed selects and commits an automatic action.
2. The exact RE3 gate-to-policy call `0x3c118 -> 0x3d8f0` is necessary for that Managed automatic action in the tested scenario.
3. Policy/selection output is observable as `+0x52` changing before/currently with action assignment.
4. The exact `0x34df2` write to `[planet+0x54]` is a necessary current-action commit seam; suppressing it does not suppress the upstream `+0x52` selection.
5. The safest M1 integration model is therefore to preserve the game's existing legacy automation gate and downstream policy/mutation machinery rather than hook or reimplement the AI.

### M1 handoff

The smallest established semantic seam is **before `0x3c118`**:

```text
Manual profile                -> legacy planet+0x5a == 0
Agricultural / Industrial M1  -> legacy automated/nonzero +0x5a semantics
                                      |
                                      v
                              existing 0x3c118 -> 0x3d8f0
                                      |
                                      v
                              existing selection/mutation
```

This is a semantic requirement for A1/A2, not a decision about where the new profile identity itself must live. RE5 does **not** require encoding three values directly in `+0x5a`; A1 still owns that architecture decision.

### Remaining unknowns

- The separate global override in the RE3 gate is still semantically unknown. RE5 intentionally does **not** publish a runtime value/address for it because a trustworthy DOS/4G guest-linear mapping was not independently established. The causal Manual/Managed control and policy-call intervention answer the M1 seam question without inventing that mapping.
- RE5 does not identify which one of the multiple policy-internal `0x34b0c` call sites handles every action class.
- The exact gameplay meanings of selected slot `0x0034` and action byte `0x00` are not reconstructed.
- Non-player convergence remains high-confidence RE3 static evidence; it was not required to establish the player M1 preservation seam and was not broadened into this runtime experiment.
- Save persistence, new profile representation, patch mechanism and UI design remain A/UI/P work.

## Reproduction

Focused helper tests:

```sh
python -m unittest tests.test_run_re5_runtime_turn_path -v
```

Complete target experiment on a host with the maintainer-supplied pinned retail tree:

```sh
python scripts/run_re5_runtime_turn_path.py \
  --game-dir /path/to/pinned/retail-tree \
  --dosbox /path/to/dosbox \
  --fixture-manifest tools/retail-runtime-manifest.json \
  --artifacts artifacts/re5-runtime-turn-path \
  --scenario all
```

Focused retry/diagnosis uses one of:

```text
--scenario manual-control
--scenario managed-control
--scenario managed-policy-suppressed
--scenario managed-action-write-suppressed
```

`run.json` is repo-safe by construction and contains no target binary, save payload, raw memory snapshot, host pointer, proprietary asset, secret, or user data.

## Result

**RE5 acceptance is met for the canonical M1 target.** Runtime evidence now connects the RE4-confirmed per-planet Managed state to the RE3 policy boundary and separates automatic selection from action commit. M1 architecture can map both automated profile identities back to the existing legacy automated semantics before `0x3c118` while leaving `0x3d8f0` and downstream action mutation untouched.
