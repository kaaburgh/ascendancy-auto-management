# CF2 correction — Open Watcom LE `page_off` layout

- Date: 2026-08-11
- Scope: PR #4, CF2 static-analysis container layer
- Evidence: **primary-source static** for LE semantics, **real-target static** for all four pinned executables, **synthetic** for corrected parser tests
- Status: **container correction and downstream real-target regeneration complete**

## Decision

The original CF2 parser was wrong to use LE-header `+0x70` as the enumerated-page file base. The correct field for these four executables is Open Watcom's absolute `page_off` at `+0x80`.

The correction is supported by Open Watcom's writer/reader/structure agreement and by independent invariants in all four exact target binaries. The earlier attempt to defend `+0x70` mixed raw observations with virtual addresses already derived through the disputed mapping, creating circular evidence.

## Primary-source layout

Open Watcom agrees in three places:

1. `bld/watcom/h/exeflat.h` defines packed `os2_flat_header` with `impmod_off @ +0x70`, `impproc_off @ +0x78`, enumerated-data-page `page_off @ +0x80`, `autodata_obj @ +0x94`, and `debug_off/debug_len @ +0x98/+0x9c`.
2. `bld/exedump/c/os2exe.c` computes an LE page file offset as `(page_number - 1) * page_size + page_off`.
3. `bld/wl/c/loadflat.c` assigns `exe_head.page_off` from the actual output-file position immediately before `WriteDataPages`.

`wdump` treats loader/fixup offsets such as `impmod_off` as LE-header-relative — for example it compares against `Os2_386_head.impmod_off + New_exe_off`. `page_off` is different: it is already an absolute file offset and is used without adding `New_exe_off`.

## Real-target verification

The four supplied executables match the CF1 pinned hashes exactly:

| Target | Size | SHA-256 |
| --- | ---: | --- |
| `ANTAG_EN.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `ANTAG_INTL.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `PATCH_EN.EXE` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `PATCH_INTL.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

All four have `e_lfanew = 0x2a50`, sequential LE page maps, and only legal page flag `0x00`.

| Target | `impmod_off +0x70` | `impproc_off +0x78` | `page_off +0x80` | `autodata +0x94` | debug `+0x98/+0x9c` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x153d5` | `0x153d5` | `0x18000` | `2` | `0 / 0` |
| `ANTAG_INTL` | `0x153be` | `0x153be` | `0x18000` | `2` | `0 / 0` |
| `PATCH_EN` | `0x14a76` | `0x14a76` | `0x17600` | `2` | `0 / 0` |
| `PATCH_INTL` | `0x14a44` | `0x14a44` | `0x17600` | `2` | `0 / 0` |

`num_impmods == 0` in all four. Therefore `+0x70 == +0x78` means only that the two empty import tables share one **header-relative loader position**. It does not alias either field to page data.

Using `page_off @ +0x80`, enumerated page data ends exactly at EOF in all four files. Treating the numeric `impmod_off` as an absolute page base leaves 11,307 / 11,330 / 11,146 / 11,196 bytes supposedly trailing. Those old trailing regions are exactly artifacts of the wrong base.

## Re-check of the previous content arguments

### Copyright raw offset

The raw location was real; the old VA was not independent. For `ANTAG_EN`, `Ascendancy\nCopyright...` is at file `0x8b895`. VA `0x934c0` was produced by applying the disputed `+0x70` mapping and therefore cannot prove that mapping.

With `page_off = 0x18000`, the same bytes are data-object offset `0x895`, VA `0x90895`. The patch pair maps the same banner to VA `0x80895`.

### Watcom runtime banner and entry point

For `ANTAG_EN`, `WATCOM C/C++32 Run-Time` starts at file `0x803b6`, corrected VA `0x783b6`, exactly two bytes after declared entry VA `0x783b4`.

The same relationship holds in all four files. At the declared entry under `+0x80`, every binary begins:

```text
eb 76 57 41 54 43 4f 4d ...
```

`EB 76` is `jmp short +0x76`; it jumps over the embedded Watcom banner and metadata tail into coherent startup code. The previous statement that `+0x80` placed the entry “on a copyright string” was therefore a decoding error.

Under the old absolute-`+0x70` interpretation, the four declared entry points instead map to unrelated byte sequences. This is the strongest target-byte discriminator between the two interpretations.

### `push 0x34c0` versus `0x895`

The correctly reconstructed `ANTAG_EN` code does contain one `push 0x34c0` and no literal immediate `0x895`, but this does not support the old mapping.

Under the correct data-object layout, `data+0x34c0` is a real formatting block beginning `%s %d\0%s %d...`, and the surrounding code pushes adjacent offsets such as `0x34c0` and `0x34c6` into the same formatting sequence. The immediate therefore has a coherent use unrelated to the copyright string.

A direct immediate `0x895` is not required for the copyright string to exist at that data offset; it may be referenced indirectly, through a table/computed pointer, or not by the swept path at all.

## Corrected basic target facts

The correction confirms:

- `page_off @ +0x80` closes page data exactly at EOF;
- `autodata_obj = 2`;
- `debug_off = debug_len = 0`;
- there is no extra ~11 KB post-page-data region;
- the two-object table and page counts are structurally consistent;
- Watcom C/C++32 and Rational DOS/4G identifiers remain present at corrected VAs.

Corrected raw-string VAs:

| Target | Watcom banner | Copyright banner | `RATIONAL DOS/4G` |
| --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x783b6` | `0x90895` | `0x9563c` |
| `ANTAG_INTL` | `0x78466` | `0x90895` | `0x9563c` |
| `PATCH_EN` | `0x737c6` | `0x80895` | `0x854bc` |
| `PATCH_INTL` | `0x73876` | `0x80895` | `0x854bc` |

## Parser correction

PR #4 now:

- reads absolute `page_off` from `+0x80`;
- reads `autodata_obj` from `+0x94` and debug fields from `+0x98/+0x9c`;
- requires enough header bytes for fields it consumes;
- rejects zero/implausibly early page data rather than guessing another header slot;
- treats `verify --anchor` only as an optional content cross-check;
- uses `+0x80` in synthetic fixtures and has a regression proving a legacy `+0x70` fixture fails closed.

The focused corrected parser suite passed 53 synthetic tests in the correction environment.

## Downstream regeneration completed

The corrected object streams have now been regenerated and passed through the current branch reconstruction/disassembly/diff semantics. Exact reconstructed code/data SHA-256 fingerprints, all replacement counts, and the execution-method note are recorded in [`CF2-real-target-regeneration.md`](./CF2-real-target-regeneration.md).

Headline replacements:

- `ANTAG_EN`: `144696` decoded instructions, `1326` candidate functions, `7472` direct call sites, `4259` call-graph edges;
- English diff: `685` strict matches, `525` constant-only differences, `116 / 87` structurally different candidates;
- international diff: `683` strict, `520` constant-only, `123 / 93` structural;
- only `588 / 685` English strict matches and `586 / 683` international strict matches relocate; 97 in each comparison remain at the same address.

Therefore the old `620 / 507 / 115 / 87` buckets and the old `ANTAG_EN` inventory numbers are superseded rather than merely offset-corrected.

## Decision on `wdump`

`wdump` changes the **validation model**, not the desired deployment dependency. Open Watcom source/`wdump` is an authoritative independent oracle for LE semantics and should be used as a cross-check. The project can still keep a small dependency-light parser for normal cloud runs as long as it follows those semantics, fails closed, and downstream target facts are tied to reproducible object fingerprints.
