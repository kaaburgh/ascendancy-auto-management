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

All four hashes above were rechecked directly during the Open Watcom layout correction in PR #4.

## Container facts, corrected and revalidated

The four exact binaries establish:

- DOS `MZ` at file offset 0; Linear Executable (`LE`) header at `e_lfanew = 0x2a50`; not PE.
- Little-endian, LE format level 0, CPU type `0x02` (80386), page size 4096.
- Exactly two objects in each image: object 1 executable code, object 2 writable data; page-map numbers are sequential and every observed page flag is `0x00` (`legal`).
- Open Watcom's enumerated-data-page `page_off` is the 32-bit field at LE-header `+0x80` and is an **absolute file offset**. The old CF2 parser incorrectly treated `impmod_off @ +0x70` as this value.
- `autodata_obj @ +0x94` is `2` in all four files.
- `debug_off @ +0x98` and `debug_len @ +0x9c` are both zero in all four files.
- With the corrected `page_off`, enumerated page data ends **exactly at EOF** in all four files. The earlier `~11 KB trailing unparsed` region was an artifact of using `impmod_off` as an absolute page base.

Per target:

| Target | Code object | Data object base | Pages | Entry VA | `page_off` |
| --- | --- | --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x10000`–`0x82736` | `0x90000` | 126 | `0x783b4` | `0x18000` |
| `ANTAG_INTL` | `0x10000`–`0x827e6` | `0x90000` | 126 | `0x78464` | `0x18000` |
| `PATCH_EN` | `0x10000`–`0x7db46` | `0x80000` | 121 | `0x737c4` | `0x17600` |
| `PATCH_INTL` | `0x10000`–`0x7dbf6` | `0x80000` | 121 | `0x73874` | `0x17600` |

The object-table metadata above is unchanged by the correction and was re-read from the exact target bytes.

### Why `+0x70` was misleading

In all four files `impmod_off @ +0x70` equals `impproc_off @ +0x78`, and `num_impmods == 0`. That observation is real, but it does **not** mean either field aliases page data.

Open Watcom treats the import/fixup table offsets as LE-header-relative; `wdump` adds `New_exe_off` when using them. `page_off` is a separate absolute file offset and is used without that addition. The equal import offsets simply describe empty import tables sharing the same loader-relative position.

The corrected entry mapping is also decisive: all four declared entry points begin with `EB 76`, a short jump over the embedded `WATCOM C/C++32 Run-Time ...` banner into consistent startup code. The old absolute-`+0x70` interpretation mapped the four entries to unrelated byte sequences.

Full evidence, including the re-check of the previous `0x34c0`/`0x895` argument, is in [`../experiments/CF2-wdump-layout-correction.md`](../experiments/CF2-wdump-layout-correction.md).

## Build toolchain identification

Raw-file strings identify **Watcom C/C++32** and **Rational DOS/4G**. With the corrected mapping their virtual addresses are:

| Target | Watcom runtime banner | Ascendancy copyright | `RATIONAL DOS/4G` |
| --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x783b6` | `0x90895` | `0x9563c` |
| `ANTAG_INTL` | `0x78466` | `0x90895` | `0x9563c` |
| `PATCH_EN` | `0x737c6` | `0x80895` | `0x854bc` |
| `PATCH_INTL` | `0x73876` | `0x80895` | `0x854bc` |

Watcom's default 32-bit convention is register-based (`__watcall`: arguments in EAX/EDX/EBX/ECX), but this project still treats that as an **open implication**, not an established calling convention for Ascendancy. Confirm it against real call sites in RE2/RE3 before any hook/trampoline or signature reading depends on it.

## Corrected reconstructed-object fingerprints

The post-correction regeneration records SHA-256 fingerprints for the exact flat object streams produced by `le_image.py`. These are regression anchors for future container changes; the object bytes themselves remain uncommitted.

| Target | Code object SHA-256 | Data object SHA-256 |
| --- | --- | --- |
| `ANTAG_EN` | `7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8` | `3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797` |
| `ANTAG_INTL` | `f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15` | `6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe` |
| `PATCH_EN` | `9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2` | `5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a` |
| `PATCH_INTL` | `be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6` | `4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96` |

## Regenerated disassembly inventory

The corrected code objects were swept with the current `le_disasm.py` algorithm and GNU objdump 2.44:

| Target | Instructions | Candidate functions | Direct call sites | Branch targets | Call-graph edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 144696 | 1326 | 7472 | 11059 | 4259 |
| `ANTAG_INTL` | 144691 | 1326 | 7477 | 11018 | 4260 |
| `PATCH_EN` | 139093 | 1297 | 7251 | 10433 | 4162 |
| `PATCH_INTL` | 139129 | 1296 | 7255 | 10448 | 4162 |

These counts are analysis metadata from a linear sweep, not proven function or instruction boundaries.

## Regenerated Antagonizer ↔ patch differential

The English pair now has **685 strict matches, 525 constant-only differences, and 116 / 87 structurally different candidates** (Antagonizer / patch). Of the strict matches, 588 are relocated and 97 remain at the same address. The structural-only matched-byte fraction is `0.765115` on the Antagonizer side and `0.798235` on the patch side. Eleven Antagonizer-only structural candidates exceed 2000 bytes.

The international pair has **683 strict matches, 520 constant-only differences, and 123 / 93 structurally different candidates**. Of the strict matches, 586 are relocated and 97 stay at the same address. The structural-only matched-byte fraction is `0.759166` / `0.792016`; twelve Antagonizer-only structural candidates exceed 2000 bytes.

The old `620 / 507 / 115 / 87` English bucket values and the old `ANTAG_EN` inventory counts were produced from the shifted `+0x70` object stream and are superseded.

Full regenerated metrics, object sizes/hashes, bucket arithmetic, largest candidates and a locale-pair sanity check are in [`../experiments/CF2-real-target-regeneration.md`](../experiments/CF2-real-target-regeneration.md).

## Reading these binaries

None of the tools preinstalled in the tested cloud image lays out the LE container: GNU `objdump` reports `file format not recognized` and `file` only classifies it. LE-aware tools exist in the wider ecosystem — Open Watcom's `wdump`/exedump is used as an important **format oracle** — but requiring a full Open Watcom installation is not necessary for the normal cloud path.

The repository keeps a small fail-closed reader and hands reconstructed flat objects to GNU `objdump`:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

`verify --anchor ADDRESS=TEXT` remains available as an optional content cross-check for a **known** binary. An anchor never selects between competing header layouts; the parser follows the Open Watcom header definition and fails closed when it is inconsistent.

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not available in cloud. It is an optional additional reference; if it is ever needed, only its metadata should be handed off, never the file.

Provenance, source archives and complete hashes are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

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
