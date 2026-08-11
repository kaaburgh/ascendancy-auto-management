# CF2 — Cloud static reverse-engineering workflow

- Roadmap item: CF2
- Date: 2026-08-11
- Targets: `ANTAG_EN.EXE` `8d91e89e…`, `ANTAG_INTL.EXE` `9d44b1ca…`, `PATCH_EN.EXE` `7c944866…`, `PATCH_INTL.EXE` `16fa81fc…` (acquired per CF1)
- Evidence category: **static** for every finding about the binaries; **runtime** for what the toolchain does in this cloud sandbox; **synthetic** for the fixture-driven tests
- Tool/build: Python 3.11.15 (standard library only), GNU objdump 2.42 (binutils for Ubuntu), `file` 5.45

## Question

Can the static analysis this milestone needs run headlessly and reproducibly in Codex or Claude cloud, rather than requiring an interactive local Ghidra session?

## Competing hypotheses

- **H1** — An interactive GUI tool is required; static RE is `LOCAL ONLY`.
- **H2** — Ghidra headless is the only viable option, so the pipeline needs a large JVM install and a custom LE loader.
- **H3** — A small purpose-built toolchain over preinstalled utilities is sufficient for the five capabilities this item names.

## What the environment actually offers

Probed in this sandbox:

| Tool | Result |
| --- | --- |
| `objdump`, `readelf`, `nm`, `strings` (binutils 2.42) | present |
| `file` 5.45 | present; identifies the targets as `MS-DOS executable, LE executable` |
| `gcc` 13.3.0 | present |
| `radare2` / `rizin` / `ghidra` / `ndisasm` | **absent** |
| `capstone`, `pefile`, `lief`, `pyelftools` | **absent**; PyPI reachable, `capstone` 5.0.9 installs if wanted |

The decisive negative result: **`objdump` cannot read the LE container at all.**

```text
$ objdump -f binaries/ANTAG_EN.EXE
objdump: binaries/ANTAG_EN.EXE: file format not recognized
```

`file` recognises the format but cannot lay it out, and nothing installed maps LE objects to virtual addresses. That missing container parser — not disassembly — was the real gap.

Conversely, `objdump` *can* disassemble a flat byte range at a chosen virtual address (`-b binary -m i386 --adjust-vma`). So the gap is bridgeable without a disassembler dependency, and **no `pip install` is required**.

## The LE container, established

Field offsets follow the published LE layout. They were not taken on trust; each was confirmed against the targets by checking invariants that would break under a misread:

- object page counts sum exactly to the header page count (126 = 115 + 11 for the Antagonizer; 121 = 110 + 11 for the bug patch);
- page-map numbers form a complete sequence 1..N with no gaps and no non-zero page flags;
- the entry point lands inside an object that is flagged executable;
- `esp` equals the stack object's virtual size exactly, i.e. the stack starts at its top;
- the computed end of page data lies inside the file.

An early draft of this work read `lastpagesize` where `pagesize` belongs; the sum-of-pages and sequence checks caught it immediately. That is why those checks are in the parser and not just in this note.

Common to all four targets (`static`):

| Property | Value |
| --- | --- |
| Container | `MZ` stub, `e_lfanew = 0x2a50`, `LE` image, little-endian, format level 0 |
| CPU | 0x02 (80386) |
| Page size | 4096 |
| Objects | 2 — object 1 code, object 2 data |
| Code object flags | `0x2045` = readable, executable, preload, 32-bit |
| Data object flags | `0x2043` = readable, writable, preload, 32-bit |
| Page flags | all `0x00` (legal); no iterated, zero-filled or range pages |
| Debug info | none (`debuginfo = 0`) |

Per target:

| Target | Code object | Data object base | Pages | Entry | Trailing unparsed |
| --- | --- | --- | --- | --- | --- |
| `ANTAG_EN` | `0x10000`–`0x82736` (0x72736) | `0x90000` | 126 | `0x783b4` | 11307 bytes |
| `ANTAG_INTL` | `0x10000`–`0x827e6` (0x727e6) | `0x90000` | 126 | `0x78464` | 11330 bytes |
| `PATCH_EN` | `0x10000`–`0x7db46` (0x6db46) | `0x80000` | 121 | `0x737c4` | 11146 bytes |
| `PATCH_INTL` | `0x10000`–`0x7dbf6` (0x6dbf6) | `0x80000` | 121 | `0x73874` | 11196 bytes |

Two things worth carrying forward. The Antagonizer's code object is **larger** than the bug patch's (0x72736 vs 0x6db46, a difference of 19440 bytes), which pushes its data object base from `0x80000` to `0x90000`. And roughly 11 KB at the end of every file is **not described by the LE structures**; the parser reports the region and does not guess at it.

### Toolchain identification (static, and consequential)

String extraction with virtual addresses produced two findings that matter well beyond CF2:

```text
0x0007afe0  obj1  WATCOM C/C++32 Run-Time system. (c) Copyright by WATCOM
                  International Corp. 1988-1994. All rights reserved.
0x00098267  obj2  RATIONAL DOS/4G
```

So the game was built with **Watcom C/C++32** and runs under the **Rational DOS/4G** extender. The 1988–1994 copyright range points at the Watcom 10.x era, though the exact version is not established by this string alone.

**Implication that must be verified, not assumed:** Watcom's default 32-bit convention is register-based (`__watcall`, arguments in EAX/EDX/EBX/ECX) rather than stack-based cdecl. If that holds here it changes how every later task reads function signatures and how A2/P1 must build any hook or trampoline. This is an `assumed` implication of the compiler identity — the build could have been configured for stack calling — and RE2/RE3 should confirm it against actual call sites before anything depends on it.

## The toolchain

Three tools, standard library plus `objdump`, each fail-closed:

- **`tools/le_image.py`** — parses the container and rebuilds objects as linear byte ranges with correct virtual addresses. Subcommands `info`, `extract`, `strings`. Refuses, by name rather than by guess: non-MZ input, an `LX` image, big-endian byte/word order, unknown format level or CPU, a non-power-of-two page size, an out-of-range last page size, zero pages or objects, an object flagged invalid, page numbers outside range, **any non-zero page flag** (iterated/zero-filled/range are unvalidated, so they are refused rather than mishandled), page data past end of file, an entry point outside its object, and an entry object that is not executable.
- **`tools/le_disasm.py`** — drives `objdump -b binary -m i386 -M intel --adjust-vma=<base>` over a rebuilt object and derives a **small** inventory: candidate function starts, a call graph, caller counts, a mnemonic histogram, and a normalized signature per candidate function. It refuses to disassemble a data object as code.

  One trap worth knowing if you extend this: **objdump wraps its byte column at 7 bytes per line**, and the continuation lines carry no disassembly text. Counting the printed bytes therefore undercuts every instruction longer than 7 bytes, which quietly deflates any byte total derived from it. Instruction length is taken from the gap to the next decoded address instead, which is exact and has a regression test.
- **`tools/le_diff.py`** — compares two inventories by normalized signature.

`tools/le_fixture.py` builds synthetic LE images, including deliberately defective ones, so all of this is testable without the game.

### Why signatures, not bytes

A raw byte diff of these two images is nearly useless: inserting code shifts everything after it, so almost every byte reads as changed. Signatures hash the normalized instruction text with absolute values masked (`call 0x783b4` → `call IMM`) while keeping registers and operand shapes. Code that merely moved therefore still matches, and what remains is the genuinely different code.

Deliberately *not* emitted: bulk disassembly. The committed artifacts are derived representations — addresses, counts, hashes — which keeps them reviewable and avoids republishing the game's code.

## Result

All five capabilities CF2 names are covered, and the whole pipeline is fast:

| Capability | Outcome |
| --- | --- |
| Identify format and architecture | `le_image info` — LE/386/2-object layout on all four targets |
| Normalized disassembly / function metadata | `le_disasm` — 144,684 instructions and 1242 candidate functions for `ANTAG_EN` in **1.4 s** |
| Strings and reference-like relationships | 1609 strings ≥6 chars with virtual addresses in **0.16 s**; 7252 direct call sites and 4089 call-graph edges |
| Compare the two builds at function/region level | `le_diff` — see below, **2.6 s** end to end |
| Stable text/JSON export | JSON from every tool; byte-identical across repeated runs |

### Differential result, English pair

```text
left  ANTAG_EN.EXE object 1: 1242 candidate functions, 115 unmatched (110322 bytes)
right PATCH_EN.EXE object 1: 1214 candidate functions,  87 unmatched  (91035 bytes)
matched: 1127 (1127 identical but relocated)
```

Every single matched function is at a different address in the two images, which is exactly the shift a byte diff would have drowned in. **1127 of 1242 candidates match, leaving 115 to inspect** — a bounded starting set for RE1 instead of a 470 KB image.

### Honest limits of that number

- The 76% "matched byte fraction" **must not** be read as "24% of the code changed". Unmatched candidates skew large because of boundary merging (below), so the byte figure overstates the delta. The function count is the more meaningful signal.
- Candidate boundaries come from direct call targets, so a region with no incoming direct call merges into its predecessor. 11 of the 115 unmatched candidates exceed 2000 bytes and the largest is 7964 bytes over 1865 instructions — those are almost certainly spans covering data or several real functions, not single functions. Median unmatched size is 414 bytes; 43 of 115 are ≤256 bytes.
- Candidate functions attribute 457,467 of the code object's 468,790 bytes (97.6%); the remainder precedes the first candidate start.
- This is a **linear sweep**. Embedded data disassembles as nonsense and a misaligned start can desynchronise a stretch of output, so instruction counts are upper bounds.
- Indirect calls are not resolved, so the call graph is incomplete — relevant because a Watcom C++ build may dispatch through tables or vtables.

None of this blocks RE1; all of it should shape how RE1 ranks candidates.

### A coarse observation for T1's lineage decision

T1 must establish build lineage before naming a baseline, and the timestamp evidence hinted the non-English pair might be more closely matched (47 minutes apart, versus ~2 months for English). Running the same comparison on both pairs does **not** support that:

| Pair | Matched | Unmatched left | Unmatched right |
| --- | --- | --- | --- |
| `ANTAG_EN` ↔ `PATCH_EN` | 1127 | 115 | 87 |
| `ANTAG_INTL` ↔ `PATCH_INTL` | 1123 | 119 | 89 |

The non-English pair is marginally *worse* on this metric. Treat this as preliminary and coarse — it is one heuristic over inferred boundaries, not a lineage determination — but it does remove the main reason to prefer the non-English lineage, and T1 should not adopt that preference on timestamps alone.

## Interpretation

**H3 is supported; H1 and H2 are rejected.** Static RE for this milestone runs headlessly in cloud with the standard library and preinstalled binutils. No GUI, no JVM, no Ghidra LE loader, and no `pip install` are needed. The only thing that had to be built is the LE container parser, because nothing available reads that format.

CF2's own gate is therefore discharged: **T2 becomes `CLOUD`**, and RE1/RE2/RE3 lose their toolchain gate (they remain blocked on their own dependencies).

## Validation performed

- `python3 -m unittest discover -s tests` — **137 tests pass**, of which 89 are new here: 42 for the parser, 27 for disassembly, 20 for the diff. All run against synthetic fixtures with no network and no proprietary bytes.
- Every fail-closed branch in `le_image` has a test that injects that specific defect.
- Determinism: two consecutive `le_disasm` runs on `ANTAG_EN.EXE` produced byte-identical JSON (`sha256 1732a076…`).
- The full pipeline ran on all four acquired targets, not only the English pair.
- Relocation-tolerance was checked both synthetically (same fixture code at base `0x10000` and `0x40000` matches completely) and on the real targets (all 1127 matches are relocated).
- `python3 scripts/check-docs.py` passes.

Not validated: nothing here executes the game, and no claim in this record depends on running it. Function *identities* are unestablished — the inventory contains candidate addresses, never named behaviors.

## Artifacts

Written under the git-ignored `artifacts/` during this experiment and regenerable in seconds:

```sh
python3 tools/fetch_free_targets.py                       # CF1: get the targets
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE --min-length 6 --json
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE -o artifacts/antag-inv.json
python3 tools/le_disasm.py binaries/PATCH_EN.EXE -o artifacts/patch-inv.json
python3 tools/le_diff.py artifacts/antag-inv.json artifacts/patch-inv.json --summary
```

Nothing needs preserving between sessions. Deciding which derived outputs become committed artifacts is T2's call, not CF2's.

## Requirements for a clean cloud environment

- Python 3.11+, standard library only.
- GNU binutils `objdump` with i386 support — preinstalled on the images used here and on `ubuntu-latest`. `le_disasm` fails closed with an actionable message if it is missing, and `--objdump` accepts an alternative.
- HTTPS egress to `archive.org` and `*.archive.org` for CF1's fetch step. **The analysis itself needs no network.**
- No JVM, no GUI, no `pip install`.

## Updated model / next question

The critical path is now unblocked as far as evidence goes: `T2 → RE1 → RE2/RE3` needs no new tooling decisions.

**T2** is the next task on that path — generate and commit the reviewable derived bundle for the canonical binaries — but note it depends on T1, which depends on T0. **T0** is the nearest unblocked item, and this experiment hands it something concrete: the container facts it must fingerprint are already established, so T0's tool should record LE/DOS-4G metadata rather than PE fields.

The highest-information open question this experiment raises is the Watcom calling convention. If `__watcall` register passing is in use, it shapes RE2/RE3's reading of every function and A2's hook design, and confirming it is cheap — inspect a handful of call sites where a matched function is invoked with known arity. That belongs to RE2/RE3, not here.
