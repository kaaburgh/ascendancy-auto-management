# CF2 — Cloud static reverse-engineering workflow

- Roadmap item: CF2
- Date: 2026-08-11
- Targets: `ANTAG_EN.EXE` `8d91e89e…`, `ANTAG_INTL.EXE` `9d44b1ca…`, `PATCH_EN.EXE` `7c944866…`, `PATCH_INTL.EXE` `16fa81fc…` (acquired per CF1)
- Current state: **implementation corrected after Open Watcom layout review; real-target measurements require regeneration before CF2 can again be called verified**
- Evidence category in this revision: **primary-source static** for LE layout, **synthetic** for corrected parser behavior, **runtime** only for the already observed cloud tool availability; corrected real-target run pending

## Question

Can the static analysis this milestone needs run headlessly and reproducibly in Codex or Claude cloud, rather than requiring an interactive local Ghidra session?

## Current answer

**The architecture is still viable, but the first real-target result set is invalidated.**

The tested cloud image had GNU binutils and `file`, but no preinstalled tool that laid out an LE image. `objdump` rejected the container while still being able to disassemble a flat i386 byte range at a supplied virtual base. That means a small container reader plus `objdump -b binary -m i386 --adjust-vma=...` remains a reasonable cloud-first design.

Open Watcom's `wdump`/exedump changes how that reader is validated. It is an authoritative independent format oracle; it does **not** have to become a required runtime dependency for every analysis run.

## The important correction

The first CF2 parser read header offset `+0x70` as the enumerated-data-page base. Review of Open Watcom source establishes that this is wrong.

Open Watcom's packed `os2_flat_header` (`bld/watcom/h/exeflat.h`) places:

- `impmod_off` at `+0x70`;
- `impproc_off` at `+0x78`;
- `page_off` at `+0x80`;
- `autodata_obj` at `+0x94`;
- `debug_off` / `debug_len` at `+0x98` / `+0x9c`.

The same source tree gives writer/reader agreement for `page_off`:

- `bld/wl/c/loadflat.c` assigns `exe_head.page_off` immediately before `WriteDataPages`; immediately beforehand `NullAlign(4)` returns the real current file position from `PosLoad()`, so this value is an **absolute file offset**;
- `bld/exedump/c/os2exe.c` computes an LE page file offset as `(page_number - 1) * page_size + page_off`.

The detailed evidence, including why the earlier content argument was misleading, is preserved in [`CF2-wdump-layout-correction.md`](./CF2-wdump-layout-correction.md).

### Why the previous `+0x70` defence failed

The earlier write-up observed that the declared `ANTAG_EN` entry point maps under `+0x80` to bytes beginning `EB 76 WATCOM...` and interpreted this as an entry point landing on a copyright string.

That interpretation is wrong: `EB 76` is a valid `jmp short +0x76`, followed by the Watcom runtime banner. A startup entry that jumps over embedded identification text is plausible, so this observation supports rather than contradicts the Open Watcom layout.

There is also a strong size consistency check. The old mapping started `ANTAG_EN` enumerated pages at `0x153d5` and reported 11,307 (`0x2c2b`) bytes after page data. The `page_off @ +0x80` value is `0x18000`; the difference is exactly `0x2c2b`. The old parser therefore shifted its fixed-size page window left by exactly the amount it later called a trailing region. The `+0x80` range ends at EOF. The same exact-EOF behavior had already been observed for `PATCH_EN` during review.

The previous DS-relative `0x34c0` versus `0x895` argument cannot rescue `+0x70`: the disassembly used to search for those immediates was itself produced from the wrongly reconstructed object bytes, so it was circular evidence.

## Corrected container tool

`tools/le_image.py` now:

- follows the Open Watcom header layout for every field it consumes;
- uses absolute `page_off @ +0x80`;
- reads autodata/debug fields at `+0x94/+0x98/+0x9c`;
- requires enough header bytes for the fields it reads;
- rejects zero or implausibly early page-data offsets instead of guessing another slot;
- refuses unvalidated page-map flag types;
- requires object page counts and entry-point relationships to be internally consistent;
- exposes `va_to_file_offset()` and optional `verify --anchor` checks.

`verify --anchor` is now deliberately subordinate to the format. It checks whether known content is where a known binary says it should be; it never selects between competing header fields.

`tools/le_fixture.py` uses `page_off @ +0x80` by default and can deliberately place it at `+0x70` only to create a malformed regression fixture. The corrected focused parser suite has **53 passing synthetic tests**, including an explicit assertion that the legacy `+0x70` fixture fails closed and that debug fields are read from `+0x98/+0x9c`.

## Static-analysis pipeline that remains useful

### `tools/le_disasm.py`

The tool still has a sound independent purpose: rebuild a selected executable object, ask GNU `objdump` to linearly decode it, and emit small derived metadata instead of bulk disassembly.

Its limitations remain explicit:

- linear sweep can decode embedded data as instructions;
- candidate functions are seeded from direct-call targets plus an in-object seed and are not proven function boundaries;
- indirect calls are unresolved;
- instruction counts are therefore analysis metadata, not a ground-truth function database.

The review fix for objdump's wrapped byte column also remains valid: instruction lengths are derived from address deltas, not from the printed byte column, because long instructions wrap onto continuation lines.

### `tools/le_diff.py`

The dual-signature design also remains useful independent of the target mapping:

- a strict normalized signature preserves out-of-range constants while masking in-image addresses;
- a shape signature masks all hexadecimal immediates;
- comparison can therefore distinguish strict matches, same-shape/different-constant candidates, and structurally different candidates without pretending it knows whether every small immediate is a relocation or a semantic constant.

What is invalidated is the **previous target population of those buckets**, not the comparison mechanism itself.

Parsing LE fixup records remains the clean way to identify loader-patched operands later if the constant-only bucket is too broad.

## Findings that survive versus findings that do not

### Survive / remain strongly supported

- the four CF1 target hashes and acquisition path;
- MZ + LE container identification and recorded `e_lfanew`;
- raw-file evidence for Watcom C/C++32 and Rational DOS/4G identity;
- the viability of a lightweight cloud pipeline built around a fail-closed LE reader and GNU `objdump`;
- synthetic behavior of the disassembly/diff algorithms and the review fixes made to them.

The Watcom identity still implies that `__watcall` is worth testing, but the calling convention remains a hypothesis until real call sites establish it.

### Invalidated pending a corrected target run

Do not use the previous PR values for:

- virtual addresses of target strings;
- reconstructed code/data bytes;
- target instruction/candidate/call-graph counts;
- target strict/shape signatures;
- English or international diff bucket counts, including the old `620 / 507 / 115 / 87` numbers;
- large-span statistics or matched-byte percentages based on those candidates;
- DS-relative examples found in that reconstructed disassembly;
- the old `~11 KB trailing unparsed` region;
- the prior `debug info = none` statement, because debug fields were also read from the wrong offsets.

Object table fields are earlier in the header and are not automatically invalidated, but they must still be rechecked in the fresh run rather than copied forward as verified facts.

## Required real-target revalidation

In a cloud environment where the CF1 `archive.org` acquisition path is reachable:

```sh
python3 tools/fetch_free_targets.py
python3 tools/fetch_free_targets.py --verify

for f in binaries/ANTAG_EN.EXE binaries/ANTAG_INTL.EXE \
         binaries/PATCH_EN.EXE binaries/PATCH_INTL.EXE; do
  python3 tools/le_image.py info "$f"
done

python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

Regenerate target documentation and measurements **from scratch**. Do not try to repair old disassembly counts or signatures by adding/subtracting the page-base delta; the input byte streams themselves were shifted.

Before CF2 returns to `Completed and verified`:

1. run the full repository test suite on the corrected branch;
2. run the corrected pipeline on all four pinned hashes;
3. restore only the target facts directly observed from those corrected outputs to `docs/re/targets.md`;
4. update the CF2 roadmap outcome and downstream gate state based on that evidence;
5. update the PR summary with the regenerated numbers.

## Decision on `wdump`

Do **not** discard the purpose-built cloud tools solely because `wdump` exists. The useful change is methodological:

- use Open Watcom source/`wdump` as an external oracle for LE semantics;
- keep the repository parser small, testable and dependency-light;
- where a target result matters, prefer an independent cross-check over self-consistent fixtures;
- if a future parser extension disagrees with Open Watcom, treat that as a hypothesis requiring target evidence, not as license to pick whichever field makes current content look plausible.

That preserves the cloud-first objective while removing the self-consistency failure that review exposed.
