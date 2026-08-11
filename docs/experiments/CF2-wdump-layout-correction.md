# CF2 correction — Open Watcom LE `page_off` layout

- Date: 2026-08-11
- Scope: PR #4, CF2 static-analysis container layer
- Evidence: **primary-source static** for the LE layout; **real-target raw-byte static** for all four pinned CF1 executables; **synthetic** for corrected parser tests

## Decision

The original CF2 parser was wrong to use LE-header `+0x70` as the enumerated-page file base. The correct field for these four executables is Open Watcom's `page_off` at `+0x80`.

This is no longer based only on a format table. Open Watcom's writer and reader agree on the field semantics, and the four exact target binaries independently exhibit the startup/layout invariants expected from that interpretation.

The earlier attempt to defend `+0x70` mixed raw observations with virtual addresses already derived through the disputed mapping. That made the strongest alleged content anchors circular.

## Primary-source layout

Three independent parts of Open Watcom agree:

1. `bld/watcom/h/exeflat.h` defines packed `os2_flat_header` with:
   - `impmod_off` at `+0x70`;
   - `impproc_off` at `+0x78`;
   - enumerated-data-page `page_off` at `+0x80`;
   - `autodata_obj` at `+0x94`;
   - `debug_off` / `debug_len` at `+0x98` / `+0x9c`.
2. `bld/exedump/c/os2exe.c` computes an LE page's file offset as
   `(page_number - 1) * page_size + Os2_386_head.page_off`.
3. `bld/wl/c/loadflat.c` writes `exe_head.page_off` from the actual output-file position immediately before `WriteDataPages`.

`wdump` also treats loader/fixup offsets such as `impmod_off` as LE-header-relative. For example, its fixup reader compares the current file position against `Os2_386_head.impmod_off + New_exe_off`. `page_off` is different: it is already an absolute file offset and is used without adding `New_exe_off`.

## Real-target verification

The four attached executables match the CF1 pinned hashes exactly:

| Target | Size | SHA-256 |
| --- | ---: | --- |
| `ANTAG_EN.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `ANTAG_INTL.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `PATCH_EN.EXE` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `PATCH_INTL.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

All four have `e_lfanew = 0x2a50`, sequential LE page maps, and only page flag `0x00`.

The disputed fields are:

| Target | `impmod_off +0x70` | `impproc_off +0x78` | `page_off +0x80` | `autodata +0x94` | debug `+0x98/+0x9c` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x153d5` | `0x153d5` | `0x18000` | `2` | `0 / 0` |
| `ANTAG_INTL` | `0x153be` | `0x153be` | `0x18000` | `2` | `0 / 0` |
| `PATCH_EN` | `0x14a76` | `0x14a76` | `0x17600` | `2` | `0 / 0` |
| `PATCH_INTL` | `0x14a44` | `0x14a44` | `0x17600` | `2` | `0 / 0` |

`num_impmods` is zero in all four. Thus the observation that `+0x70 == +0x78` is real, but the previous interpretation was not: the equality means the two empty import tables occupy the same **header-relative loader position**. It does not make either field the absolute enumerated-page base.

Adding `e_lfanew` to `impmod_off` points into the zero-filled end of the loader/fixup area (`0x17e25`, `0x17e0e`, `0x174c6`, `0x17494` respectively), while the distinct absolute `page_off` fields are `0x18000` / `0x17600`.

### Page range closes exactly at EOF

Using `page_off @ +0x80` and the header's page count/page size/last-page size, enumerated page data ends exactly at EOF in **all four** files:

- `ANTAG_EN`: `0x18000 .. 0x9522f`, EOF `0x9522f`;
- `ANTAG_INTL`: `0x18000 .. 0x9522f`, EOF `0x9522f`;
- `PATCH_EN`: `0x17600 .. 0x8f6bb`, EOF `0x8f6bb`;
- `PATCH_INTL`: `0x17600 .. 0x8f6bb`, EOF `0x8f6bb`.

Using the numeric `impmod_off` value as though it were an absolute page base instead leaves 11,307 / 11,330 / 11,146 / 11,196 bytes supposedly unexplained. That old “trailing region” is an artifact of the wrong base.

## Re-check of the four earlier arguments for `+0x70`

### 1. `Ascendancy\nCopyright ...` raw offset

The raw-file observation was correct but the claimed VA was not independent.

For `ANTAG_EN`, the bytes occur at file offset `0x8b895`. The old VA `0x934c0` was obtained by subtracting the disputed `0x153d5` page base and adding the data-object base — so it cannot be used to prove that same page base.

With the format-defined `page_off = 0x18000`, page-map/object metadata maps the same raw bytes to data-object offset `0x895`, VA `0x90895`. The Antagonizer international build has the same raw offset and corrected VA. The patch pair contains the same banner at file `0x85e95`, data offset `0x895`, VA `0x80895`.

### 2. `WATCOM C/C++32 Run-Time` raw offset

Again, the raw offset is real; the old VA was derived from the old mapping.

For `ANTAG_EN`, `WATCOM C/C++32 Run-Time` starts at file `0x803b6`. Under `page_off = 0x18000`, this is code VA `0x783b6` — exactly **two bytes after the declared entry VA `0x783b4`**.

The same invariant holds in all four binaries: the banner starts two bytes after the declared entry under `+0x80`.

### 3. Declared entry point

This is the strongest real-byte discriminator.

Under `page_off @ +0x80`, the declared entry bytes are:

```text
ANTAG_EN    file 0x803b4: eb 76 57 41 54 43 4f 4d ...
ANTAG_INTL  file 0x80464: eb 76 57 41 54 43 4f 4d ...
PATCH_EN    file 0x7adc4: eb 76 57 41 54 43 4f 4d ...
PATCH_INTL  file 0x7ae74: eb 76 57 41 54 43 4f 4d ...
```

`eb 76` is `jmp short +0x76`. It skips exactly 118 bytes containing the Watcom runtime banner plus a small metadata tail and lands on startup code. For `ANTAG_EN` the destination begins:

```text
fb                    sti
83 e4 fc              and esp, 0xfffffffc
89 e3                 mov ebx, esp
89 1d 38 99 00 00     mov [0x9938], ebx
89 1d 24 99 00 00     mov [0x9924], ebx
...
cd 21                 int 0x21
```

The corresponding destination prefix is the same in both Antagonizer locales, and the patch pair has the same startup sequence with only expected data offsets changed.

Under the old absolute-`+0x70` interpretation the four declared entries instead map to four unrelated byte sequences:

```text
ANTAG_EN    8e c0 8b 1d 20 32 0a 00 ...
ANTAG_INTL  02 66 b8 03 00 5b 07 1f ...
PATCH_EN    10 66 8b ca 26 89 08 07 ...
PATCH_INTL  8b 06 66 26 89 47 2a 66 ...
```

So the previous claim “`+0x80` puts the entry on a copyright string” is false. `+0x80` produces a consistent Watcom startup trampoline in all four binaries; `+0x70` does not.

### 4. `push 0x34c0` versus `0x895`

The original inference was also wrong, but for a more informative reason than simple circularity.

In the correctly reconstructed `ANTAG_EN` code there is indeed one `push 0x34c0` and no immediate `0x895`. However, under the correct data-object mapping `data+0x34c0` contains:

```text
%s %d\0%s %d\0%s %d\0...
```

and the code around the push is:

```text
push eax
push eax
push 0x34c0
push esi
call ...
...
push eax
push eax
push 0x34c6
push esi
call ...
```

So `0x34c0` has a direct, coherent role as a format-string offset in the correctly mapped data object. It is not evidence that the copyright banner lives at DS offset `0x34c0`.

The absence of a literal `0x895` reference also does not contradict the correct mapping: a string need not have a direct immediate xref; it may be reached through a table, pointer, computed address, or not referenced by the swept code path at all.

## Corrected target facts restored by this check

The real-target raw/header check now confirms for all four pinned files:

- `page_off` is `+0x80` and closes page data exactly at EOF;
- `autodata_obj = 2`;
- `debug_off = debug_len = 0`;
- there is no extra ~11 KB region after enumerated page data;
- the two-object table and page counts remain structurally consistent;
- the Watcom runtime and Rational DOS/4G strings remain present; their VAs must use the corrected mapping.

Corrected raw-string VAs include:

- `ANTAG_EN`: Watcom banner `0x783b6`, copyright banner `0x90895`, `RATIONAL DOS/4G` `0x9563c`;
- `ANTAG_INTL`: Watcom banner `0x78466`, copyright banner `0x90895`, `RATIONAL DOS/4G` `0x9563c`;
- `PATCH_EN`: Watcom banner `0x737c6`, copyright banner `0x80895`, `RATIONAL DOS/4G` `0x854bc`;
- `PATCH_INTL`: Watcom banner `0x73876`, copyright banner `0x80895`, `RATIONAL DOS/4G` `0x854bc`.

## Parser correction

PR #4 now:

- reads `page_off` from `+0x80` and treats it as an absolute file offset;
- reads `autodata_obj` from `+0x94` and debug fields from `+0x98/+0x9c`;
- requires enough header bytes for the fields it actually reads;
- rejects a zero or implausibly early page-data offset rather than guessing another header slot;
- keeps `verify --anchor` only as an optional content cross-check; anchors can no longer select a competing layout;
- makes the synthetic fixture use `+0x80` by default and has an explicit regression proving a legacy `+0x70` fixture fails closed.

The focused synthetic `test_le_image` suite passes (53 tests) against the corrected implementation in the correction environment.

## Remaining regeneration

This pass establishes the container mapping and restores the basic target facts above from the four exact binaries. It does **not** make the old disassembly/diff measurements valid again.

Before CF2 is again marked “Completed and verified,” rerun the corrected repository tools on all four files and regenerate:

```sh
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

The old `620 / 507 / 115 / 87` buckets and every statistic derived from the old shifted object bytes remain invalid until that run.

## Decision on `wdump`

`wdump` changes the **validation model**, not the desired deployment dependency. Its source is an authoritative independent oracle for the LE layout and is valuable for cross-checking. The project does not need to require a full Open Watcom installation in every clean cloud run merely to replace a small, tested parser. Keeping the parser lightweight remains reasonable as long as it follows the format-defined fields and fails closed.
