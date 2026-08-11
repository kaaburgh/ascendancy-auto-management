# CF2 — Cloud static reverse-engineering workflow

- Roadmap item: CF2
- Date: 2026-08-11
- Targets: `ANTAG_EN.EXE` `8d91e89e…`, `ANTAG_INTL.EXE` `9d44b1ca…`, `PATCH_EN.EXE` `7c944866…`, `PATCH_INTL.EXE` `16fa81fc…`
- Current state: **corrected; clean-checkout real-target regression is the completion gate**
- Evidence: **primary-source static** for LE layout, **real-target static** for container/disassembly/diff measurements, **synthetic** for fixture-driven tests, **runtime** for cloud tool availability

## Question

Can the static analysis this milestone needs run headlessly and reproducibly in Codex or Claude cloud, rather than requiring an interactive local Ghidra session?

## Answer

**Yes.** The cloud path is a small fail-closed LE reader plus GNU `objdump` over reconstructed flat i386 objects. No GUI, JVM, Ghidra installation or Python package dependency is required for the CF2 capability.

Two review findings materially hardened the implementation:

1. the initial parser used LE-header `impmod_off @ +0x70` as the enumerated-page base; Open Watcom establishes absolute `page_off @ +0x80`, so all real-target results were regenerated from corrected object bytes;
2. the first post-correction differential called candidates "strict matches" after masking every in-image operand, which could hide a real changed callee/global/table reference. Exact matches now preserve every operand, and reference-only changes are an explicit unresolved bucket.

The layout correction evidence is in [`CF2-wdump-layout-correction.md`](./CF2-wdump-layout-correction.md). Full object fingerprints, metrics and the current regression contract are in [`CF2-real-target-regeneration.md`](./CF2-real-target-regeneration.md).

## Cloud toolchain

GNU `objdump` does not understand the LE container itself but does disassemble a flat byte range when supplied the architecture and virtual base:

```sh
objdump -D -b binary -m i386 -M intel --adjust-vma=<base> object.bin
```

The repository supplies:

- `tools/le_image.py` — fail-closed LE reader/reconstructor using Open Watcom `os2_flat_header` semantics;
- `tools/le_disasm.py` — reconstructs an executable object, drives `objdump`, and emits versioned candidate/call/signature metadata;
- `tools/le_diff.py` — validates inventory provenance and compares candidates in exact, reference-only, constant-only and structural classes;
- `tools/le_fixture.py` — synthetic LE fixtures, including malformed variants, so the unit suite needs no target bytes;
- `scripts/validate_cf2_real_targets.py` — clean-checkout regression over all four pinned real targets using the repository CLIs.

Open Watcom `wdump` is an independent format oracle/cross-check, not a required dependency for normal cloud analysis. Its source semantics established the corrected field layout; executing `wdump` itself against the four targets is deliberately retained as a T2 independent cross-check.

## Corrected container facts

All four exact CF1 targets match their pinned SHA-256 hashes, have `e_lfanew = 0x2a50`, sequential legal page maps, two objects, `autodata_obj = 2`, and zero debug offset/length.

The authoritative `page_off @ +0x80` is `0x18000` for both Antagonizer files and `0x17600` for both patch files. With that field, enumerated page data ends exactly at EOF for all four binaries. The earlier approximately 11 KB trailing region was an artifact of treating a header-relative import-table offset as an absolute page base.

Corrected raw-string VAs include:

| Target | Watcom runtime banner | Ascendancy copyright | `RATIONAL DOS/4G` |
| --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x783b6` | `0x90895` | `0x9563c` |
| `ANTAG_INTL` | `0x78466` | `0x90895` | `0x9563c` |
| `PATCH_EN` | `0x737c6` | `0x80895` | `0x854bc` |
| `PATCH_INTL` | `0x73876` | `0x80895` | `0x854bc` |

The declared entry provides an independent structural/content check: under `+0x80`, every target starts at `EB 76` immediately before the Watcom banner and jumps over it into coherent startup code. This address comes from the LE entry metadata, not from asking the parser where a discovered string lives. The project playbook now explicitly forbids circular validation where a mapping is "verified" with VAs derived by that same mapping.

## Reconstructed-object regression fingerprints

| Target | Code object SHA-256 | Data object SHA-256 |
| --- | --- | --- |
| `ANTAG_EN` | `7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8` | `3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797` |
| `ANTAG_INTL` | `f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15` | `6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe` |
| `PATCH_EN` | `9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2` | `5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a` |
| `PATCH_INTL` | `be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6` | `4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96` |

The serialized inventory also carries its reconstructed code-object SHA-256 and parser-layout identity. `le_diff` rejects an unversioned/pre-correction JSON artifact even when its source EXE hash is valid.

## Corrected disassembly inventories

| Target | Instructions | Candidate regions | Direct call sites | Branch targets | Call-graph edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 144696 | 1326 | 7472 | 11059 | 4259 |
| `ANTAG_INTL` | 144691 | 1326 | 7477 | 11018 | 4260 |
| `PATCH_EN` | 139093 | 1297 | 7251 | 10433 | 4162 |
| `PATCH_INTL` | 139129 | 1296 | 7255 | 10448 | 4162 |

The old `ANTAG_EN` values `144684 / 1242 / 7252 / 4089` came from the shifted `+0x70` object stream and are superseded.

## Conservative four-class differential

### English: `ANTAG_EN` vs `PATCH_EN`

- **72 exact matches**; 50 are at different candidate addresses and 22 at the same address;
- **613 reference-only differences** — same after masking only in-image operands; relocation noise and behavioral retargets are mixed here;
- **525 constant-only differences** — same after masking all hex operands; DS-relative movement and genuine constant retuning are mixed here;
- **116 / 87 structural regions**;
- structural-only matched-byte fraction `0.765115 / 0.798235`;
- 11 Antagonizer-only structural regions exceed 2000 bytes.

Arithmetic: `72 + 613 + 525 + 116 = 1326`; `72 + 613 + 525 + 87 = 1297`.

The earlier post-layout-correction `685 strict` value was not 685 identical candidates. It splits exactly into `72 exact + 613 reference-only`.

### International: `ANTAG_INTL` vs `PATCH_INTL`

- **72 exact matches**; 50 moved, 22 same candidate address;
- **611 reference-only differences**;
- **520 constant-only differences**;
- **123 / 93 structural regions**;
- structural-only matched-byte fraction `0.759166 / 0.792016`;
- 12 Antagonizer-only structural regions exceed 2000 bytes.

The earlier `683 strict` value splits into `72 exact + 611 reference-only`.

### Cross-locale sanity

| Pair | Exact | Reference-only | Constant-only | Structural left/right |
| --- | ---: | ---: | ---: | ---: |
| `ANTAG_EN` vs `ANTAG_INTL` | 114 | 1107 | 46 | 59 / 59 |
| `PATCH_EN` vs `PATCH_INTL` | 114 | 1076 | 56 | 51 / 50 |

This is a consistency check, not source-lineage proof.

## Limits handed to downstream RE

- The sweep is linear; embedded data can decode as instructions.
- Candidate starts come from direct call targets plus a seed. Indirect-only callees are not given independent starts and can be folded into a preceding region.
- `116` English structural regions is **not** a claim of 116 changed functions. Eleven exceed 2000 bytes and the largest is 7964 bytes.
- The 613 reference-only English candidates may include real callee/global/table retargets and must not be discarded as relocation noise.
- The 525 constant-only English candidates are the largest unresolved semantic bucket. A self-management change implemented mostly by retuned constants could live there rather than in the structural list.
- Parsing LE fixup records is the clean next discriminator if RE1 cannot make those two unresolved buckets tractable.
- The structural matched-byte fraction ignores both middle buckets and is not a semantic similarity percentage.
- Whole-image Antagonizer-vs-patch differences may still include unrelated source-snapshot/compiler/bug-fix changes; T1 owns lineage constraints.
- Watcom's default `__watcall` remains a hypothesis. RE2/RE3 must confirm calling convention at real known-arity call sites before argument interpretation or later hook/trampoline design depends on it.

## Reproduction and completion gate

Network-free synthetic/unit validation remains:

```sh
python -m unittest discover -s tests -v
```

The authoritative checkout-level CF2 gate is:

```sh
python3 scripts/validate_cf2_real_targets.py --fetch
```

That command fetches/verifies the four CF1 targets, checks all reconstructed-object fingerprints, invokes the repository `le_disasm.py` on all four, and invokes the repository `le_diff.py` on product and locale pairs while asserting the metrics above. `.github/workflows/tests.yml` runs it in its own `CF2 real-target regression` job; CF2 must not be described as `Completed and verified` unless that current-head job is green.

## Outcome for the roadmap

The feasibility conclusion remains: **T2, RE1, RE2 and RE3 have a viable headless static-analysis path in cloud** once their normal dependencies are satisfied. The current PR's final completion status is tied to the clean-checkout real-target regression, not to a hand-reproduced algorithm run.

The Antagonizer code object remains exactly 19,440 bytes larger than the corresponding patch code object in both locale pairs. That is a measured size fact only, not “19,440 bytes of AI changes.”
