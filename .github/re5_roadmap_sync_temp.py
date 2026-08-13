from pathlib import Path

path = Path("ROADMAP.md")
text = path.read_text(encoding="utf-8")
start_marker = "## RE5 — Runtime-confirm the per-turn self-management call path"
end_marker = "\n---\n\n# Track A — Architecture decisions"
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = '''## RE5 — Runtime-confirm the per-turn self-management call path

- **Status:** **Completed and verified** — clean exact-target runtime causality established; see [`docs/re/auto-management-turn-path.md`](./docs/re/auto-management-turn-path.md) and [`docs/experiments/RE5-runtime-turn-path.md`](./docs/experiments/RE5-runtime-turn-path.md).
- **Execution:** **CLOUD** — completed on the exact canonical Antagonizer with the pinned maintainer-supplied retail fixture, RE4 runtime harness, and `scripts/run_re5_runtime_turn_path.py`.
- **Priority:** Critical
- **Category:** Reverse engineering / runtime turn processing
- **Origin:** High-level step 3
- **Depends on:** RE3 (complete), RE4 (complete), CF3 (complete)
- **Question:** Which runtime path consumes the confirmed auto-management state during a turn and reaches the existing planetary management decision/action code?

### Outcome

`runtime`, clean blind-RE evidence on canonical `ANTAG.EXE` (`8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`):

- the same pinned `Xerxes I` resume begins with no selected/current action (`+0x52 == 0xffff`, `+0x54 == 0xff`); in a bounded fast-forward window Manual (`+0x5a == 0`) stays idle while the RE4-confirmed Managed state (`+0x5a == 0xffffffff`) selects `+0x52 = 0x0034` and commits `+0x54 = 0x00`;
- temporarily replacing the whole exact `0x3c118` `call 0x3d8f0` instruction (`e8 d3 17 00 00`) with five NOPs in the **live DOSBox process only** leaves the Managed state intact but prevents both selection and action mutation; original bytes are restored and re-verified before teardown;
- temporarily replacing the whole `0x34df2` `mov [esi+0x54], al` instruction (`88 46 54`) with three NOPs still permits policy/selection output (`+0x52: ffff -> 3400`) while keeping `+0x54 == 0xff`; this separates upstream decision output from the current-action commit seam;
- an exploratory suppression of RE3's highlighted internal `0x3df88 -> 0x34b0c` call did **not** prevent the tested action, so that individual call site is not promoted to the unique runtime mutation path; the downstream `0x34df2` write is the stronger established boundary;
- the smallest M1 semantic preservation seam is therefore **before `0x3c118`**: `Manual` must map to the legacy zero/non-automated condition and both M1 automated profile identities must map back to the legacy nonzero/Managed semantics, while `0x3d8f0` and downstream selection/mutation stay untouched;
- RE5 does not decide where the three-value profile identity lives. A1 still owns that representation decision, and it need not encode three values directly in `+0x5a`.

The separate RE3 override-global semantics remain unknown. RE5 deliberately does not publish a guessed runtime address/value for it because a trustworthy DOS/4G guest-linear mapping was not independently established; the causal same-save Manual/Managed controls and gate-call intervention answer the M1 preservation question without that assumption.

### Deliverables

- [x] reproducible runtime experiment record at [`docs/experiments/RE5-runtime-turn-path.md`](./docs/experiments/RE5-runtime-turn-path.md);
- [x] durable runtime findings merged into [`docs/re/auto-management-turn-path.md`](./docs/re/auto-management-turn-path.md);
- [x] fail-closed runner `scripts/run_re5_runtime_turn_path.py` with exact fixture/resume identity, unique runtime anchor, whole-instruction expected-byte validation, process-memory-only diagnostic patches and verified rollback;
- [x] focused synthetic tests for record uniqueness, runtime-site translation, patch-plan instruction sizes and all four causal oracles.

### Acceptance criteria

**Met.** The project now knows the M1 preservation boundary: legacy automated/nonzero planet state must still pass the existing gate into `0x3c118 -> 0x3d8f0`; the original policy then produces selection state and the existing `0x34b0c` path commits the current action. New Agricultural/Industrial identity can therefore remain an A1 concern while both automated identities map back to the game's established automation semantics without reconstructing or replacing the AI.
'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
