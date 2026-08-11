# CF2 correction — Open Watcom LE `page_off` layout

- Date: 2026-08-11
- Scope: PR #4, CF2 static-analysis container layer
- Evidence: **primary-source static** for the LE layout; **synthetic** for the corrected parser tests; **real-target revalidation pending**

## Why this correction exists

The first CF2 implementation reconstructed enumerated LE pages from the 32-bit value at LE-header offset `+0x70`. Review pointed out that Open Watcom ships both the LE structure definition and an executable dumper (`wdump` / `exedump`) whose layout disagrees with that choice.

This was not a documentation-only issue. `le_image.py` feeds every later string address, disassembly, function inventory and differential result, so a wrong page-data base invalidates all measurements derived from reconstructed target bytes.

## What Open Watcom establishes

Three independent parts of the Open Watcom source tree agree:

1. `bld/watcom/h/exeflat.h` defines packed `os2_flat_header` with:
   - `impmod_off` at `+0x70`;
   - `impproc_off` at `+0x78`;
   - enumerated-data-page `page_off` at `+0x80`;
   - `autodata_obj` at `+0x94`;
   - `debug_off` / `debug_len` at `+0x98` / `+0x9c`.
2. `bld/exedump/c/os2exe.c` computes an LE page's file offset as
   `(page_number - 1) * page_size + Os2_386_head.page_off`.
3. `bld/wl/c/loadflat.c` assigns `exe_head.page_off = curr_loc` immediately before `WriteDataPages(curr_loc)`. At that point `curr_loc` has just been reset by `NullAlign(4)`, and `NullAlign` obtains its base from the real `PosLoad()`, so `page_off` is an **absolute file offset**.

This writer/reader agreement is stronger evidence than a secondary format table.

## Why the earlier content argument was misleading

The earlier PR revision tried to preserve `+0x70` because several content observations appeared to support it. The decisive one was interpreted incorrectly.

For `ANTAG_EN.EXE`, the declared entry point under `page_off @ +0x80` maps to file offset `0x803b4`, whose bytes begin:

```text
eb 76 57 41 54 43 4f 4d 20 43 2f 43 2b 2b 33 32 ...
```

The previous write-up treated this as “the entry point lands on the WATCOM copyright string.” It does not: `eb 76` is a valid `jmp short +0x76`, followed by the `WATCOM C/C++32 Run-Time ...` banner. Jumping over an embedded runtime banner is a perfectly plausible startup sequence and removes the strongest alleged contradiction to `+0x80`.

There is a second strong consistency check. The old `+0x70` mapping for `ANTAG_EN.EXE` started enumerated pages at `0x153d5` and reported 11,307 (`0x2c2b`) trailing bytes. The format-defined `+0x80` field says page data starts at `0x18000`; the displacement is exactly `0x2c2b`. In other words, the old parser shifted the whole fixed-size page window left by exactly the amount it later reported as “unparsed trailing data.” Under `+0x80`, the observed page range ends exactly at EOF. The same exact-EOF behavior was already observed for `PATCH_EN.EXE` during review.

The old DS-relative `0x34c0` versus `0x895` argument is also not usable as independent evidence: the disassembly used to search for those immediates came from the same wrongly shifted reconstructed code object. It was circular.

## Consequence for previous CF2 results

### Still supported

These findings do not depend on the disputed page-data mapping, or are supported by raw-file evidence:

- the targets are MZ containers with an LE header at the recorded `e_lfanew`;
- object-table metadata before the disputed header region (object bases, sizes, flags, page counts) remains structurally meaningful and must be rechecked but is not automatically invalidated;
- the raw binaries contain Watcom C/C++32 and Rational DOS/4G identification strings, so the compiler/extender identification remains strongly supported, although their **virtual addresses must be regenerated**;
- the cloud architecture remains viable: a small LE reader can reconstruct objects and GNU `objdump` can disassemble the resulting flat ranges;
- `le_disasm.py` / `le_diff.py` algorithms and their synthetic tests remain useful independently of which target bytes are supplied.

### Invalidated pending regeneration

Do **not** use the previous real-target values from PR #4 until the corrected parser has been run on all four pinned hashes:

- virtual addresses assigned to strings;
- reconstructed code/data object bytes;
- instruction, call-site, call-graph and candidate-function counts;
- normalized/shape signatures;
- the `620 / 507 / 115 / 87` English diff buckets and the corresponding non-English figures;
- any statement based on those candidate sets, including large-span counts and matched-byte percentages;
- the old `~11 KB trailing unparsed` claim;
- the previous `debug info = none` conclusion, because the first parser also read debug fields from the wrong header offsets.

Compiler/extender *identity* survives as raw-string evidence; their old VAs do not.

## Parser correction

PR #4 now:

- reads `page_off` from `+0x80` and treats it as an absolute file offset;
- reads `autodata_obj` from `+0x94` and debug fields from `+0x98/+0x9c`;
- requires enough header bytes for the fields it actually reads;
- rejects a zero or implausibly early page-data offset rather than guessing another header slot;
- keeps `verify --anchor` only as an optional content cross-check; anchors can no longer select a competing layout;
- makes the synthetic fixture use `+0x80` by default and has an explicit regression proving a legacy `+0x70` fixture fails closed.

The focused synthetic `test_le_image` suite passes (53 tests) against the corrected implementation in the environment used for this correction.

## Required real-target revalidation

A cloud environment with the CF1 `archive.org` egress must fetch the four pinned target hashes and rerun, at minimum:

```sh
python3 tools/fetch_free_targets.py
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py info binaries/ANTAG_INTL.EXE
python3 tools/le_image.py info binaries/PATCH_EN.EXE
python3 tools/le_image.py info binaries/PATCH_INTL.EXE
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

Before CF2 is again marked “Completed and verified,” regenerate `docs/re/targets.md`, the CF2 experiment measurements, and the PR summary from those corrected outputs. Do not carry old numbers forward by arithmetic adjustment: the old object byte streams were shifted, so disassembly boundaries and signatures must be recomputed from scratch.

## Decision on `wdump`

`wdump` changes the **validation model**, not the desired deployment dependency. Its source is an authoritative independent oracle for the LE layout and is valuable for cross-checking. The project does not need to require a full Open Watcom installation in every clean cloud run merely to replace a small, tested parser. Keeping the parser lightweight remains reasonable as long as it follows the format-defined fields and fails closed.
