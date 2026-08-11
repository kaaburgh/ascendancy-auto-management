# CF2 — Cloud static reverse-engineering workflow

- Roadmap item: CF2
- Date: 2026-08-11
- Targets: `ANTAG_EN.EXE` `8d91e89e…`, `ANTAG_INTL.EXE` `9d44b1ca…`, `PATCH_EN.EXE` `7c944866…`, `PATCH_INTL.EXE` `16fa81fc…`
- Current state: **corrected and revalidated on all four real targets**
- Evidence: **primary-source static** for LE layout, **real-target static** for container/disassembly/diff measurements, **synthetic** for fixture-driven parser/disassembly/diff tests, **runtime** for the observed cloud tool availability

## Question

Can the static analysis this milestone needs run headlessly and reproducibly in Codex or Claude cloud, rather than requiring an interactive local Ghidra session?

## Answer

**Yes.** The useful cloud path remains a small fail-closed LE reader plus preinstalled GNU `objdump` over reconstructed flat i386 objects. No GUI, JVM, Ghidra install or Python package dependency is required for the current CF2 capability.

A review-discovered container bug temporarily invalidated the first real-target measurements: the initial parser used LE-header `impmod_off @ +0x70` as the enumerated-page base. Open Watcom's packed header, linker and `wdump`/exedump all establish that the absolute enumerated-data-page `page_off` is at `+0x80`. The parser was corrected and the four exact targets were then rerun from scratch.

The layout correction evidence is preserved in [`CF2-wdump-layout-correction.md`](./CF2-wdump-layout-correction.md). The complete regenerated disassembly/diff evidence is in [`CF2-real-target-regeneration.md`](./CF2-real-target-regeneration.md).

## Cloud toolchain

The tested environment has GNU binutils; GNU `objdump` does not understand the LE container itself but does disassemble a flat byte range when supplied the architecture and virtual base:

```sh
objdump -D -b binary -m i386 -M intel --adjust-vma=<base> object.bin
```

The repository therefore supplies:

- `tools/le_image.py` — fail-closed LE reader/reconstructor using Open Watcom's `os2_flat_header` semantics;
- `tools/le_disasm.py` — reconstructs an executable object, drives `objdump`, and emits derived candidate-function/call/signature metadata rather than bulk disassembly;
- `tools/le_diff.py` — compares candidate inventories with strict and shape signatures;
- `tools/le_fixture.py` — synthetic LE fixtures, including malformed variants, so CI does not need target bytes.

Open Watcom `wdump` is an independent format oracle/cross-check, not a required runtime dependency for normal cloud analysis.

## Corrected container facts

All four exact CF1 targets match their pinned SHA-256 hashes, have `e_lfanew = 0x2a50`, sequential legal page maps, two objects, `autodata_obj = 2`, and zero debug offset/length.

The authoritative `page_off @ +0x80` is `0x18000` for both Antagonizer files and `0x17600` for both bug-patch files. With that field, enumerated page data ends exactly at EOF for all four binaries. The old approximately 11 KB trailing region was solely an artifact of treating the header-relative import-table offset as an absolute page base.

Corrected raw-string VAs include:

| Target | Watcom runtime banner | Ascendancy copyright | `RATIONAL DOS/4G` |
| --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x783b6` | `0x90895` | `0x9563c` |
| `ANTAG_INTL` | `0x78466` | `0x90895` | `0x9563c` |
| `PATCH_EN` | `0x737c6` | `0x80895` | `0x854bc` |
| `PATCH_INTL` | `0x73876` | `0x80895` | `0x854bc` |

The entry point provides a strong independent check: with `+0x80`, every target begins at `EB 76` immediately before the Watcom banner; the short jump skips the embedded banner and lands on coherent startup code. The old absolute-`+0x70` interpretation maps the four entries to unrelated bytes.

## Reconstructed-object regression fingerprints

Before trusting downstream counts after a future parser change, the flat object streams can be checked against these SHA-256 values:

| Target | Code object SHA-256 | Data object SHA-256 |
| --- | --- | --- |
| `ANTAG_EN` | `7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8` | `3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797` |
| `ANTAG_INTL` | `f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15` | `6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe` |
| `PATCH_EN` | `9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2` | `5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a` |
| `PATCH_INTL` | `be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6` | `4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96` |

These are hashes of reconstructed flat objects, not hashes of extra committed game files.

## Corrected disassembly inventories

The current `le_disasm` algorithm linearly sweeps the whole executable object. Candidate starts are the image seed plus direct in-object call targets. GNU objdump 2.44 produced:

| Target | Instructions | Candidate functions | Direct call sites | Branch targets | Call-graph edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 144696 | 1326 | 7472 | 11059 | 4259 |
| `ANTAG_INTL` | 144691 | 1326 | 7477 | 11018 | 4260 |
| `PATCH_EN` | 139093 | 1297 | 7251 | 10433 | 4162 |
| `PATCH_INTL` | 139129 | 1296 | 7255 | 10448 | 4162 |

The old `ANTAG_EN` values `144684 / 1242 / 7252 / 4089` were derived from the shifted page stream and are superseded.

## Corrected differential

`le_diff` performs two multiset match passes:

1. **strict signature** — in-image address operands are normalized while other constants are preserved;
2. **shape signature** — strict leftovers are compared with all hexadecimal constants masked.

This produces three explicit buckets instead of pretending DS-relative relocations and semantic constant changes can already be distinguished.

### English

`ANTAG_EN` vs `PATCH_EN`:

- 685 strict matches;
- 588 strict matches relocated, 97 at the same address;
- 525 constant-only differences;
- 116 Antagonizer-only and 87 patch-only structurally different candidates;
- structural-only matched-byte fraction `0.765115` / `0.798235`;
- 11 Antagonizer-only structural candidates exceed 2000 bytes.

The bucket arithmetic closes: `685 + 525 + 116 = 1326`, `685 + 525 + 87 = 1297`.

### International

`ANTAG_INTL` vs `PATCH_INTL`:

- 683 strict matches;
- 586 strict matches relocated, 97 at the same address;
- 520 constant-only differences;
- 123 Antagonizer-only and 93 patch-only structurally different candidates;
- structural-only matched-byte fraction `0.759166` / `0.792016`;
- 12 Antagonizer-only structural candidates exceed 2000 bytes.

The bucket arithmetic again closes: `683 + 520 + 123 = 1326`, `683 + 520 + 93 = 1296`.

The old English headline `620 / 507 / 115 / 87` is superseded. The old statement that every strict match relocated is also false: 97 strict matches remain at the same address in each locale comparison.

## Cross-locale consistency check

As a non-product sanity check, comparing each family across locale gives substantially more strict matches than Antagonizer-vs-patch:

| Pair | Strict | Relocated strict | Constant-only | Structural left/right |
| --- | ---: | ---: | ---: | ---: |
| `ANTAG_EN` vs `ANTAG_INTL` | 1221 | 1025 | 46 | 59 / 59 |
| `PATCH_EN` vs `PATCH_INTL` | 1190 | 1000 | 56 | 51 / 50 |

This is consistent with the two localization variants being closer to each other than the Antagonizer/patch pair. It is not proof that the Antagonizer and patch were compiled from comparable source snapshots; T1 still owns that lineage question.

## Limits that downstream RE must retain

The corrected container input removes one foundational error but does not turn the derived inventory into ground truth:

- linear sweep decodes embedded data as instructions and makes instruction counts upper-bound-like analysis metadata;
- candidate boundaries are inferred from direct calls and may merge large spans; 11 EN and 12 INTL Antagonizer-only structural candidates exceed 2000 bytes;
- indirect calls are unresolved;
- the constant-only bucket intentionally mixes DS-relative layout changes with any real threshold/flag changes;
- the matched-byte fraction counts only the structural bucket and must not be read as a semantic similarity percentage;
- whole-image Antagonizer-vs-patch differences can include unrelated build/bug-fix changes if T1 cannot establish comparable lineage.

If the constant-only bucket becomes a practical blocker for RE1, parsing LE fixup records is the clean next improvement because it can identify loader-patched operands rather than relying on value heuristics.

## Reproduction

```sh
python3 tools/fetch_free_targets.py
python3 tools/fetch_free_targets.py --verify

for f in binaries/ANTAG_EN.EXE binaries/ANTAG_INTL.EXE \
         binaries/PATCH_EN.EXE binaries/PATCH_INTL.EXE; do
  python3 tools/le_image.py info "$f"
  python3 tools/le_disasm.py "$f" --summary
done

python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

For container-regression work, also compare reconstructed code/data SHA-256 values with the fingerprints above before comparing downstream counts.

## Outcome for the roadmap

CF2's original feasibility decision remains valid and is now backed by corrected real-target evidence: **T2, RE1, RE2 and RE3 can use the headless static-analysis path in cloud** once their normal dependencies are satisfied.

The Antagonizer code object remains exactly 19,440 bytes larger than the corresponding patch code object in both locale pairs. That is a measured size fact only. It must not be equated with “19,440 bytes of AI changes.”

Watcom's default `__watcall` convention remains an implication to test against real call sites, not an established Ascendancy calling convention.