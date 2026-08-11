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

Facts that apply to all four (static, this hash set):

- DOS `MZ` stub at offset 0; Linear Executable (`LE`) image at `e_lfanew = 0x2a50`; bound DOS/4G extender. **Not PE** — tooling that assumes PE will not work.
- Each is a **complete standalone game build**, not a patcher. The Antagonizer and the bug patch are alternatives to the retail `ASCEND.EXE`, run in its place from the same installed directory.
- Version strings 1.6.5 / 1.8.5 for the bug patches are the publisher's own documented values (`patch.txt`), not measured from the binaries. The Antagonizer has no publisher-documented version string.
- Little-endian, LE format level 0, CPU type `0x02` (80386), page size 4096, no debug info, and no iterated/zero-filled/range pages — every page-map entry is a plain "legal" page.
- Exactly two objects: object 1 code (flags `0x2045` = readable/executable/preload/32-bit), object 2 data (flags `0x2043` = readable/writable/preload/32-bit).
- Roughly 11 KB at the end of each file is **not described by the LE structures** and remains unparsed.

## Build toolchain (static, CF2)

- **Compiler: Watcom C/C++32.** Runtime banner at code-object VA `0x7afe0` in `ANTAG_EN.EXE`: `WATCOM C/C++32 Run-Time system. (c) Copyright by WATCOM International Corp. 1988-1994. All rights reserved.` The date range points at the Watcom 10.x era; the exact version is not established by this string.
- **Extender: Rational DOS/4G.** String `RATIONAL DOS/4G` at data-object VA `0x98267`.

**Open implication, not established:** Watcom's default 32-bit convention is register-based (`__watcall`: arguments in EAX/EDX/EBX/ECX) rather than stack-based cdecl. If that holds for this build it changes how function signatures are read and how any hook or trampoline must be written. The build could have been configured for stack calling, so confirm against real call sites (RE2/RE3) before depending on it.

## Container layout per target (static, CF2)

| Target | Code object | Data object base | Pages | Entry VA | Trailing unparsed |
| --- | --- | --- | --- | --- | --- |
| `ANTAG_EN` | `0x10000`–`0x82736` | `0x90000` | 126 | `0x783b4` | 11307 |
| `ANTAG_INTL` | `0x10000`–`0x827e6` | `0x90000` | 126 | `0x78464` | 11330 |
| `PATCH_EN` | `0x10000`–`0x7db46` | `0x80000` | 121 | `0x737c4` | 11146 |
| `PATCH_INTL` | `0x10000`–`0x7dbf6` | `0x80000` | 121 | `0x73874` | 11196 |

The Antagonizer's code object is 19440 bytes larger than the English bug patch's, which moves its data object base from `0x80000` to `0x90000`. Whether that growth is the AI changes is **not** established — RE1 must test it.

## Reading these binaries

Nothing in a standard toolchain parses LE: `objdump` reports "file format not recognized". Use the project's tools, which need only the standard library and `objdump`:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE      # container layout
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE   # strings with virtual addresses
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

Capabilities, limits and validation are recorded in [`../experiments/CF2-cloud-static-re.md`](../experiments/CF2-cloud-static-re.md). Read the limits before trusting a candidate function boundary.

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not available in cloud. It is an optional additional reference; if it is ever needed, only its metadata should be handed off, never the file.

Provenance, egress requirements and the full hash table including the source archives are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

## Canonical entries

Pending T1.

For each supported binary, record at least:

```markdown
## <label>

- Filename:
- Architecture:
- SHA-256:
- File size:
- PE timestamp:
- Image base:
- Provenance/version notes:
- Relationship to vanilla/reference build:
- Supported by current patch: yes/no
```

Do not commit the proprietary executable itself.
