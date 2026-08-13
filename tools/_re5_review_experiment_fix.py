from pathlib import Path

p = Path('docs/experiments/RE5-runtime-turn-path.md')
s = p.read_text(encoding='utf-8')

def r(old: str, new: str) -> None:
    global s
    if s.count(old) != 1:
        raise SystemExit(f'experiment anchor count {s.count(old)} for {old[:80]!r}')
    s = s.replace(old, new, 1)

r('The experiment is deliberately causal rather than a whole-turn trace. It compares the same pinned saved planet in Manual and Managed modes and then temporarily removes two whole-instruction boundaries from the **live DOSBox process only**:\n\n1. the RE3 gate-to-policy call `0x3c118 -> 0x3d8f0`;\n2. the downstream action-byte commit `0x34df2: mov [planet+0x54], al` inside the `0x34b0c` mutation candidate.\n',
  'The experiment is deliberately causal rather than a whole-turn trace. It compares the same pinned saved planet in Manual and Managed modes, directly probes reachability of the RE3 gate-to-policy call site, and temporarily removes two whole-instruction boundaries from the **live DOSBox process only**:\n\n1. reachability probe at `0x3c118`: replace the five-byte call with `mov byte [edx+0x54], 0x7e; nop`;\n2. suppress the RE3 gate-to-policy call `0x3c118 -> 0x3d8f0`;\n3. suppress the downstream action-byte commit `0x34df2: mov [planet+0x54], al` inside the `0x34b0c` mutation candidate.\n')
r('| suppress gate → policy | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | five NOPs |\n| suppress action commit | `0x34df2` | `88 46 54` (`mov [esi+0x54], al`) | three NOPs |\n',
  '| probe gate → policy reachability | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | `c6 42 54 7e 90` (`mov byte [edx+0x54],0x7e; nop`) |\n| suppress gate → policy | `0x3c118` | `e8 d3 17 00 00` (`call 0x3d8f0`) | five NOPs |\n| suppress action commit | `0x34df2` | `88 46 54` (`mov [esi+0x54], al`) | three NOPs |\n')
r('The final runner stops DOSBox with `SIGSTOP` for each small `0x12`-byte sample, performs one bounded read, resumes with `SIGCONT`, and samples at 25 ms intervals. This produces coherent bounded observations and prevents an unbounded memory read. The observed millisecond values below therefore describe the diagnostic sampling window; they are **not** instruction-level or gameplay-performance measurements.\n',
  'The final runner stops DOSBox with `SIGSTOP` for each small `0x12`-byte sample, waits until `/proc/<pid>/status` reports an actual stopped-state code (`T` or `t`) **after** the `State:` colon, performs one bounded read, resumes with `SIGCONT`, and samples at 25 ms intervals. A review found that the first implementation searched for the letters `T`/`t` anywhere in the whole `State:` line; lowercase `t` in the label itself made that check vacuous. The parser now extracts the state code explicitly, focused tests cover `R`, `S`, `T`, and `t`, and all six exact-target scenarios below were rerun after the correction.\n\nThis produces coherent bounded observations and prevents an unbounded memory read. The observed millisecond values below therefore describe the diagnostic sampling window; they are **not** instruction-level or gameplay-performance measurements.\n')
r('The four final sub-scenarios were executed individually because the surrounding container tool imposes a shorter single-command wall-time than the four fresh DOSBox startups combined. Each focused invocation is the same code path selected by `--scenario`; `--scenario all` remains the one-command operator path where the host permits the combined runtime.\n',
  'The six final sub-scenarios were executed individually because the surrounding container tool imposes a shorter single-command wall-time than six fresh DOSBox startups combined. Each focused invocation is the same code path selected by `--scenario`; `--scenario all` remains the one-command operator path where the host permits the combined runtime.\n')
start = s.index('## Final observations')
end = s.index('## Exploratory negative result retained')
observations = '''## Final observations

### 1. Manual control: no automatic selection or commit

Pinned start/armed state:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = 00000000
```

Observed for `7014.826 ms` with corrected stopped-state sampling:

- no `+0x52` change;
- no `+0x54` change;
- `+0x5a` remained zero;
- DOSBox remained alive.

Result: **PASS**.

### 2. Manual gate-reachability probe: `0x3c118` is not reached

After exact-byte validation, the runner replaced the complete `0x3c118` call (`e8 d3 17 00 00`) with `c6 42 54 7e 90`, which writes marker byte `0x7e` to `[EDX+0x54]` and does not invoke the policy. RE3 independently established that `EDX` is the current planet pointer at this call site.

With `+0x5a == 0`, observed for `7018.474 ms`:

- `+0x52` remained `ffff`;
- `+0x54` remained `ff` — marker `7e` never appeared;
- `+0x5a` remained `00000000`;
- original call bytes were restored and byte-verified.

Result: **PASS**.

### 3. Managed gate-reachability probe: the same `0x3c118` site is reached

The exact same marker replacement was applied in a fresh process after ordinary **M** produced `+0x5a == 0xffffffff`.

The first corrected coherent sample at `26.099 ms` observed:

```text
+0x52 = ffff
+0x54: ff -> 7e
+0x5a = ffffffff
```

No policy call was executed because the call instruction itself had been replaced by the marker write. Original call bytes were restored and byte-verified.

Result: **PASS**.

**Runtime conclusion:** for the same player-owned planet and empty-action preconditions, Manual does not reach `0x3c118` while Managed does. Static RE3 control flow permits Manual to reach this site only when the separate override is nonzero, so the paired probe establishes that the override bypass is **inactive in this pinned Manual scenario** without requiring an unverified DOS/4G data-address mapping.

### 4. Managed control: automatic selection reaches action commit

After ordinary **M**:

```text
+0x52 = ffff
+0x54 = ff
+0x5a = ffffffff
```

Observed at the first corrected mutation sample (`4511.810 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> 00
+0x5a: ffffffff (unchanged)
```

`0x0034` and `0x00` are recorded values only; RE5 does not assign gameplay semantics to those codes.

Result: **PASS**.

### 5. Managed + gate-to-policy call suppressed: no selection or commit

The runner verified `e8 d3 17 00 00` at static `0x3c118`, replaced the complete five-byte call with NOPs in the live process, then armed the same Managed state.

Observed for `7023.444 ms` with corrected stopped-state sampling:

- `+0x52` remained `ffff`;
- `+0x54` remained `ff`;
- `+0x5a` remained `ffffffff`;
- original call bytes were restored and byte-verified;
- DOSBox remained alive.

Result: **PASS**.

**Runtime conclusion:** the RE3 `0x3c118 -> 0x3d8f0` boundary is necessary for the tested automatic selection/action path.

### 6. Managed + final action-byte write suppressed: selection survives, commit does not

The runner verified `88 46 54` at static `0x34df2` and replaced that complete three-byte instruction with NOPs in the live process.

The policy path still produced a selected slot at the first observed selection sample (`5174.806 ms`):

```text
+0x52: ffff -> 3400
+0x54: ff   -> ff
+0x5a: ffffffff (unchanged)
```

During the full `7005.001 ms` bounded window, `+0x54` never left `ff`. The original `88 46 54` bytes were restored and byte-verified; DOSBox remained alive.

Result: **PASS**.

**Runtime conclusion:** selection/decision output exists upstream of the `+0x54` write, while `0x34df2` is a concrete action-commit seam in the tested `0x34b0c` mutation path.

'''
s = s[:start] + observations + s[end:]
r('1. On the same exact saved planet with the same empty-action starting state, legacy Manual remains idle in the bounded turn window while legacy Managed selects and commits an automatic action.\n2. The exact RE3 gate-to-policy call `0x3c118 -> 0x3d8f0` is necessary for that Managed automatic action in the tested scenario.\n3. Policy/selection output is observable as `+0x52` changing before/currently with action assignment.\n4. The exact `0x34df2` write to `[planet+0x54]` is a necessary current-action commit seam; suppressing it does not suppress the upstream `+0x52` selection.\n5. The safest M1 integration model is therefore to preserve the game\'s existing legacy automation gate and downstream policy/mutation machinery rather than hook or reimplement the AI.\n',
  '1. With the same player-owned planet and empty-action preconditions, the `0x3c118` marker probe is not reached in Manual (`+0x5a == 0`) and is reached in Managed (`+0x5a == 0xffffffff`).\n2. Because RE3 statically shows that the only Manual bypass around zero `+0x5a` is the separate override branch, the paired probe establishes that override bypass inactive in the pinned Manual scenario.\n3. Legacy Manual remains idle in the bounded turn window while legacy Managed selects and commits an automatic action.\n4. The exact RE3 gate-to-policy call `0x3c118 -> 0x3d8f0` is necessary for that Managed automatic action in the tested scenario.\n5. Policy/selection output is observable as `+0x52` changing before/currently with action assignment.\n6. The exact `0x34df2` write to `[planet+0x54]` is a necessary current-action commit seam; suppressing it does not suppress the upstream `+0x52` selection.\n7. The safest M1 integration model is therefore to preserve the game\'s existing legacy automation gate and downstream policy/mutation machinery rather than hook or reimplement the AI.\n')
r('- The separate global override in the RE3 gate is still semantically unknown. RE5 intentionally does **not** publish a runtime value/address for it because a trustworthy DOS/4G guest-linear mapping was not independently established. The causal Manual/Managed control and policy-call intervention answer the M1 seam question without inventing that mapping.\n',
  '- The separate global override in the RE3 gate is still semantically unknown, and RE5 intentionally does **not** publish a guessed runtime address/value for it. The paired `0x3c118` marker probe establishes the fact needed by M1 instead: the override bypass is inactive for the pinned Manual scenario, while Managed reaches the same call site.\n')
r('--scenario manual-control\n--scenario managed-control\n--scenario managed-policy-suppressed\n--scenario managed-action-write-suppressed\n',
  '--scenario manual-control\n--scenario manual-gate-probe\n--scenario managed-gate-probe\n--scenario managed-control\n--scenario managed-policy-suppressed\n--scenario managed-action-write-suppressed\n')
r('**RE5 acceptance is met for the canonical M1 target.** Runtime evidence now connects the RE4-confirmed per-planet Managed state to the RE3 policy boundary and separates automatic selection from action commit. M1 architecture can map both automated profile identities back to the existing legacy automated semantics before `0x3c118` while leaving `0x3d8f0` and downstream action mutation untouched.\n',
  '**RE5 acceptance is met for the canonical M1 target.** Corrected coherent-sampling runtime evidence now shows direct gate-site reachability discrimination: Manual `+0x5a == 0` does not reach `0x3c118`, Managed `+0x5a == 0xffffffff` does, and the RE3 override bypass is therefore inactive in the pinned Manual scenario. The same rerun confirms the policy-call necessity and separates automatic selection from action commit. M1 architecture can map both automated profile identities back to the existing legacy automated semantics before `0x3c118` while leaving `0x3d8f0` and downstream action mutation untouched.\n')
p.write_text(s, encoding='utf-8')
