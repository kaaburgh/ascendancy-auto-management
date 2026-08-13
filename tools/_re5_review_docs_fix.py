from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    if s.count(old) != 1:
        raise SystemExit(f'{path}: anchor count {s.count(old)} for {old[:90]!r}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')

p = 'docs/re/auto-management-turn-path.md'
replace_once(p,
'''On the exact canonical target and pinned `resume.gam`, the same player planet `Xerxes I` starts with `+0x52 == 0xffff`, `+0x54 == 0xff` and `+0x5a == 0`. Four fresh-process causal controls establish the runtime layering:\n\n1. **Manual control:** with `+0x5a == 0`, neither `+0x52` nor `+0x54` changes during the bounded fast-forward window.\n2. **Managed control:** ordinary M produces the RE4-confirmed `+0x5a == 0xffffffff`; the existing turn path then selects `+0x52 = 0x0034` and commits `+0x54 = 0x00`.\n3. **Gate→policy intervention:** after exact-byte validation, live-process-only NOPs replace the complete `0x3c118` `call 0x3d8f0` (`e8 d3 17 00 00`). Managed remains set, but neither selection nor action mutation occurs. Original call bytes are restored and re-verified before teardown.\n4. **Action-commit intervention:** after exact-byte validation, live-process-only NOPs replace the complete `0x34df2` `mov [esi+0x54], al` (`88 46 54`). `+0x52` still changes from `ffff` to `3400`, while `+0x54` remains `ff`. Original bytes are restored and re-verified.\n''',
'''On the exact canonical target and pinned `resume.gam`, the same player planet `Xerxes I` starts with `+0x52 == 0xffff`, `+0x54 == 0xff` and `+0x5a == 0`. Six fresh-process causal controls, all rerun after correcting the stopped-state parser, establish the runtime layering:\n\n1. **Manual control:** with `+0x5a == 0`, neither `+0x52` nor `+0x54` changes during the bounded fast-forward window.\n2. **Manual gate probe:** after exact-byte validation, the complete `0x3c118` call is replaced by `c6 42 54 7e 90` (`mov byte [edx+0x54],0x7e; nop`). With `+0x5a == 0`, marker `0x7e` never appears during the 7-second window.\n3. **Managed gate probe:** the same marker replacement with `+0x5a == 0xffffffff` writes `0x7e` to `+0x54` while `+0x52` stays `ffff`, directly proving reachability of `0x3c118` without running the policy.\n4. **Managed control:** ordinary M produces the RE4-confirmed `+0x5a == 0xffffffff`; the existing turn path then selects `+0x52 = 0x0034` and commits `+0x54 = 0x00`.\n5. **Gate→policy intervention:** after exact-byte validation, live-process-only NOPs replace the complete `0x3c118` `call 0x3d8f0` (`e8 d3 17 00 00`). Managed remains set, but neither selection nor action mutation occurs. Original call bytes are restored and re-verified before teardown.\n6. **Action-commit intervention:** after exact-byte validation, live-process-only NOPs replace the complete `0x34df2` `mov [esi+0x54], al` (`88 46 54`). `+0x52` still changes from `ffff` to `3400`, while `+0x54` remains `ff`. Original bytes are restored and re-verified.\n\nThe paired gate probes close RE3 H4 for the pinned M1 scenario: static RE3 control flow allows a Manual `+0x5a == 0` planet to reach `0x3c118` only through the separate nonzero override path. Manual does not reach the marker while Managed does, so that override bypass is inactive in this tested Manual run. Its broader gameplay semantics remain unknown.\n''')
replace_once(p,
'''The separate global override in the RE3 gate remains semantically unknown. RE5 intentionally does not publish a guessed runtime address/value for it because a trustworthy DOS/4G guest-linear mapping was not independently established. No M1 conclusion above depends on inventing that mapping.\n''',
'''The separate global override in the RE3 gate remains semantically unknown, and RE5 intentionally does not publish a guessed runtime address/value for it. The paired call-site marker probe establishes the M1-relevant fact without inventing that mapping: the override bypass is inactive in the pinned Manual scenario.\n''')

p = Path('ROADMAP.md')
roadmap = p.read_text(encoding='utf-8')
start = roadmap.index('## RE5 — Runtime-confirm the per-turn self-management call path')
end = roadmap.index('\n---\n\n# Track A — Architecture decisions', start)
section = roadmap[start:end]
old = '- the same pinned `Xerxes I` resume begins with no selected/current action (`+0x52 == 0xffff`, `+0x54 == 0xff`); in a bounded fast-forward window Manual (`+0x5a == 0`) stays idle while the RE4-confirmed Managed state (`+0x5a == 0xffffffff`) selects `+0x52 = 0x0034` and commits `+0x54 = 0x00`;\n'
new = '- the same pinned `Xerxes I` resume begins with no selected/current action (`+0x52 == 0xffff`, `+0x54 == 0xff`); corrected coherent sampling shows Manual (`+0x5a == 0`) stays idle while the RE4-confirmed Managed state (`+0x5a == 0xffffffff`) selects `+0x52 = 0x0034` and commits `+0x54 = 0x00`;\n- a paired exact-byte gate probe replaces only the whole `0x3c118` call with `mov byte [edx+0x54],0x7e; nop`: Manual never reaches the marker during 7 seconds, while Managed reaches it; with RE3\'s static gate this establishes the separate override bypass inactive in the pinned Manual scenario without guessing a DOS/4G data address;\n'
if section.count(old) != 1: raise SystemExit('roadmap outcome anchor missing')
section = section.replace(old, new, 1)
old = 'The separate RE3 override-global semantics remain unknown. RE5 deliberately does not publish a guessed runtime address/value for it because a trustworthy DOS/4G guest-linear mapping was not independently established; the causal same-save Manual/Managed controls and gate-call intervention answer the M1 preservation question without that assumption.\n'
new = 'The separate RE3 override-global semantics remain unknown. RE5 deliberately does not publish a guessed runtime address/value for it because a trustworthy DOS/4G guest-linear mapping was not independently established; the paired call-site marker probe instead establishes that the override bypass is inactive in the pinned Manual scenario.\n'
if section.count(old) != 1: raise SystemExit('roadmap override anchor missing')
section = section.replace(old, new, 1)
section = section.replace('focused synthetic tests for record uniqueness, runtime-site translation, patch-plan instruction sizes and all four causal oracles.', 'focused synthetic tests for record uniqueness, runtime-site translation, patch-plan instruction sizes, stopped-state parsing and all six causal oracles.')
p.write_text(roadmap[:start] + section + roadmap[end:], encoding='utf-8')
