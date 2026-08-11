# Target binaries

No canonical target binary has been **selected** yet. That selection is roadmap item T1.

This is an intentional project constraint, not missing documentation: the first roadmap phase is to choose the exact vanilla/official-patch/Antagonizer baseline.

Do not publish or apply version-specific offsets or machine-code patches until this file records the exact target.

## Candidates available to cloud agents

CF1 established that the candidate executables are lawfully fetchable in cloud, so an agent does **not** need to wait for a maintainer handoff to do static analysis. Fetch them into the git-ignored `binaries/` with:

```sh
python3 tools/fetch_free_targets.py          # fetch and verify all four
python3 tools/fetch_free_targets.py --list   # show ids, sizes and pinned hashes
python3 tools/fetch_free_targets.py --verify # re-verify without the network
```

| Manifest id | Role | Size | SHA-256 |
| --- | --- | --- | --- |
| `antagonizer-en` | Antagonizer AI module, English | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `antagonizer-intl` | Antagonizer AI module, non-English | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `bugpatch-en` | Official bug patch, version 1.6.5, English | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `bugpatch-intl` | Official bug patch, version 1.8.5, non-English | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

Facts established independently of the corrected page-data mapping:

- DOS `MZ` stub at offset 0; Linear Executable (`LE`) image at `e_lfanew = 0x2a50`; bound DOS/4G-style target. **Not PE** — tooling that assumes PE will not work.
- Each candidate is a **complete standalone game build**, not a patcher. The Antagonizer and the bug patch are alternatives to the retail `ASCEND.EXE`, run in its place from the same installed directory.
- Version strings 1.6.5 / 1.8.5 for the bug patches are the publisher's documented values (`patch.txt`), not measured from the binaries. The Antagonizer has no publisher-documented version string.
- Raw-file strings identify **Watcom C/C++32** and **Rational DOS/4G**. This compiler/extender identification does not depend on assigning those strings virtual addresses.

Provenance, source archives and complete hashes are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

## CF2 layout correction — real-target values must be regenerated

PR #4 initially reconstructed enumerated LE pages from header offset `+0x70`. Open Watcom's own structure definition, linker and executable dumper establish that this was wrong:

- `+0x70` is `impmod_off`;
- the enumerated-data-page `page_off` field is `+0x80` and is an **absolute file offset**;
- `autodata_obj` is `+0x94`;
- `debug_off` / `debug_len` are `+0x98` / `+0x9c`.

The parser and synthetic fixture have been corrected. See [`../experiments/CF2-wdump-layout-correction.md`](../experiments/CF2-wdump-layout-correction.md) for the primary-source evidence and the explanation of why the earlier content argument was circular/misread.

Until the four pinned targets are rerun through the corrected parser, this file deliberately does **not** publish the previous CF2 values for:

- virtual addresses of strings;
- page-data start/end and any supposed trailing region;
- debug-info presence/absence;
- reconstructed object-byte hashes;
- disassembly/function/call-graph counts or differential buckets.

Those values were derived from a shifted byte stream and are invalidated, not merely offset by a constant.

Object-table metadata uses earlier header fields and is therefore not automatically invalidated, but it also must be rechecked rather than copied forward as a confirmed target fact.

### Required revalidation

In a cloud environment with the CF1 `archive.org` egress:

```sh
python3 tools/fetch_free_targets.py

for f in binaries/ANTAG_EN.EXE binaries/ANTAG_INTL.EXE \
         binaries/PATCH_EN.EXE binaries/PATCH_INTL.EXE; do
  python3 tools/le_image.py info "$f"
done

python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

Record the exact output against the four hashes above before restoring any derived target values here.

## Reading these binaries

None of the tools preinstalled in the tested cloud image lays out the LE container: GNU `objdump` reports `file format not recognized` and `file` only classifies it. LE-aware tools exist in the wider ecosystem — Open Watcom's `wdump`/exedump is now used as an important **format oracle** — but requiring a full Open Watcom installation is not necessary for the normal cloud path.

The repository keeps a small fail-closed reader and hands reconstructed flat objects to GNU `objdump`:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

`verify --anchor ADDRESS=TEXT` remains available as an optional content cross-check for a **known** binary. An anchor never selects between competing header layouts; the parser follows the Open Watcom header definition and fails closed when it is inconsistent.

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not available in cloud. It is an optional additional reference; if it is ever needed, only its metadata should be handed off, never the file.

## Build toolchain implication

The raw binaries contain the Watcom C/C++32 runtime banner. Watcom's default 32-bit convention is register-based (`__watcall`: arguments in EAX/EDX/EBX/ECX), but this project still treats that as an **open implication**, not an established calling convention for Ascendancy. Confirm it against real call sites in RE2/RE3 before any hook/trampoline or signature reading depends on it.

## Canonical entries

Pending T1.

For each supported binary, record at least:

```markdown
## <label>

- Filename:
- Architecture:
- SHA-256:
- File size:
- Container/header metadata:
- Provenance/version notes:
- Relationship to vanilla/reference build:
- Supported by current patch: yes/no
```

Do not commit the proprietary executable itself.
