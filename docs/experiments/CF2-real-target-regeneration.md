# CF2 — corrected real-target disassembly and diff regeneration

- Date: 2026-08-11
- Scope: PR #4, post-`page_off @ +0x80` regeneration
- Evidence: **real-target static** against all four CF1 hash-pinned executables
- Disassembler: GNU objdump 2.44, `-D -b binary -m i386 -M intel --adjust-vma=<object-base>`
- Analysis model: current PR `le_image.py` reconstruction semantics + current `le_disasm.py` / `le_diff.py` algorithms

## Purpose

The first CF2 target measurements were produced from object bytes reconstructed with the wrong LE enumerated-page base (`impmod_off @ +0x70`). After the parser was corrected to Open Watcom's absolute `page_off @ +0x80`, every disassembly- and signature-derived target number had to be regenerated from scratch.

This experiment does that regeneration using the four exact CF1 targets supplied directly to the analysis environment. No old instruction count, function count, signature, diff bucket or byte-coverage value is carried forward by arithmetic adjustment.

The execution sandbox did not have a Git checkout of the PR branch and shell DNS could not resolve `github.com`. Rather than switch to a different disassembler or comparison algorithm, the current branch source for `le_image.py`, `le_disasm.py`, and `le_diff.py` was read through the GitHub connector and the relevant reconstruction/disassembly/diff logic was reproduced for the local target run. The GNU `objdump` command, listing parser, candidate construction, normalization, and two-pass matching semantics match the branch implementation. The reconstructed-object hashes below are an additional input-level regression anchor. A future checkout-capable run should reproduce the same values with the repository CLIs directly.

The container-layout evidence and why `+0x80` is authoritative are recorded separately in [`CF2-wdump-layout-correction.md`](./CF2-wdump-layout-correction.md).

## Inputs

| Target | Size | SHA-256 |
| --- | ---: | --- |
| `ANTAG_EN.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `ANTAG_INTL.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `PATCH_EN.EXE` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `PATCH_INTL.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

All four hashes match `tools/free-target-sources.json` / the CF1 manifest.

## Reconstructed object fingerprints

These hashes are over the exact flat object byte streams handed to analysis. They are useful regression anchors for the container layer without committing target bytes.

| Target | Object | Base | Virtual size | Pages | SHA-256 of reconstructed object |
| --- | ---: | ---: | ---: | ---: | --- |
| `ANTAG_EN` | code 1 | `0x10000` | 468790 | 115 | `7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8` |
| `ANTAG_EN` | data 2 | `0x90000` | 688672 | 11 | `3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797` |
| `ANTAG_INTL` | code 1 | `0x10000` | 468966 | 115 | `f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15` |
| `ANTAG_INTL` | data 2 | `0x90000` | 688752 | 11 | `6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe` |
| `PATCH_EN` | code 1 | `0x10000` | 449350 | 110 | `9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2` |
| `PATCH_EN` | data 2 | `0x80000` | 685808 | 11 | `5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a` |
| `PATCH_INTL` | code 1 | `0x10000` | 449526 | 110 | `be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6` |
| `PATCH_INTL` | data 2 | `0x80000` | 685888 | 11 | `4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96` |

The code-object size delta remains 19,440 bytes for both locale pairs. This is a measured layout fact, not evidence that all 19,440 bytes implement Antagonizer behavior.

## Regenerated disassembly inventories

`le_disasm` linearly sweeps the whole executable object. Candidate starts are direct-call targets plus the image entry seed. These are analysis candidates, not proven function boundaries.

| Target | Instructions decoded | Candidate functions | Direct in-object call sites | Distinct branch targets | Call-graph edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 144696 | 1326 | 7472 | 11059 | 4259 |
| `ANTAG_INTL` | 144691 | 1326 | 7477 | 11018 | 4260 |
| `PATCH_EN` | 139093 | 1297 | 7251 | 10433 | 4162 |
| `PATCH_INTL` | 139129 | 1296 | 7255 | 10448 | 4162 |

The old headline values `144684 instructions / 1242 candidates / 7252 calls / 4089 edges` for `ANTAG_EN` were therefore products of the shifted object stream and must not be reused.

## Regenerated Antagonizer ↔ bug-patch differential

The current diff is two-pass:

1. strict signature: mask only operands that fall inside an image object range;
2. shape signature: on strict leftovers, mask every hexadecimal constant.

The resulting three classes are strict matches, same-shape/different-constant candidates, and structurally different candidates.

### English pair

`ANTAG_EN` (`8d91e89e…`) vs `PATCH_EN` (`7c944866…`):

| Metric | Value |
| --- | ---: |
| Antagonizer candidate functions | 1326 |
| Patch candidate functions | 1297 |
| Strict matches | 685 |
| Strict matches relocated | 588 |
| Strict matches at same address | 97 |
| Constant-only differences | 525 |
| Structurally different only in Antagonizer | 116 |
| Structurally different only in patch | 87 |
| Antagonizer attributed bytes | 468774 |
| Antagonizer structurally-unmatched bytes | 110108 |
| Antagonizer matched-byte fraction (structural bucket only) | 0.765115 |
| Patch attributed bytes | 449334 |
| Patch structurally-unmatched bytes | 90660 |
| Patch matched-byte fraction (structural bucket only) | 0.798235 |
| Antagonizer structural candidates > 2000 bytes | 11 |
| Patch structural candidates > 2000 bytes | 9 |

Bucket arithmetic closes exactly: `685 + 525 + 116 = 1326` on the Antagonizer side and `685 + 525 + 87 = 1297` on the patch side.

The ten largest Antagonizer-only structural candidates are:

| Address | Bytes | Decoded instructions | Direct callers |
| ---: | ---: | ---: | ---: |
| `0x41268` | 7964 | 1865 | 1 |
| `0x72148` | 7612 | 2309 | 1 |
| `0x62da5` | 6983 | 2110 | 4 |
| `0x50140` | 5428 | 1431 | 3 |
| `0x7d9e4` | 5382 | 1328 | 4 |
| `0x39de0` | 4928 | 1459 | 1 |
| `0x27bf8` | 4220 | 1108 | 1 |
| `0x4b944` | 3768 | 914 | 1 |
| `0x3cce4` | 3084 | 759 | 2 |
| `0x406c4` | 2979 | 768 | 2 |

### International pair

`ANTAG_INTL` (`9d44b1ca…`) vs `PATCH_INTL` (`16fa81fc…`):

| Metric | Value |
| --- | ---: |
| Antagonizer candidate functions | 1326 |
| Patch candidate functions | 1296 |
| Strict matches | 683 |
| Strict matches relocated | 586 |
| Strict matches at same address | 97 |
| Constant-only differences | 520 |
| Structurally different only in Antagonizer | 123 |
| Structurally different only in patch | 93 |
| Antagonizer attributed bytes | 468950 |
| Antagonizer structurally-unmatched bytes | 112939 |
| Antagonizer matched-byte fraction (structural bucket only) | 0.759166 |
| Patch attributed bytes | 449510 |
| Patch structurally-unmatched bytes | 93491 |
| Patch matched-byte fraction (structural bucket only) | 0.792016 |
| Antagonizer structural candidates > 2000 bytes | 12 |
| Patch structural candidates > 2000 bytes | 10 |

Bucket arithmetic again closes: `683 + 520 + 123 = 1326`, and `683 + 520 + 93 = 1296`.

The ten largest Antagonizer-only structural candidates are:

| Address | Bytes | Decoded instructions | Direct callers |
| ---: | ---: | ---: | ---: |
| `0x412a8` | 7964 | 1865 | 1 |
| `0x721f8` | 7612 | 2305 | 1 |
| `0x62e55` | 6983 | 2110 | 4 |
| `0x501e0` | 5428 | 1429 | 3 |
| `0x7da94` | 5382 | 1307 | 4 |
| `0x39e20` | 4928 | 1460 | 1 |
| `0x27c38` | 4220 | 1106 | 1 |
| `0x4b9e4` | 3768 | 914 | 1 |
| `0x3cd24` | 3086 | 760 | 2 |
| `0x40704` | 2978 | 767 | 2 |

## Cross-locale sanity check

This is not the product differential, but it is useful for checking that the regenerated inventories behave coherently across the two localization builds.

| Pair | Strict matches | Relocated strict | Constant-only | Structural left/right | Left matched-byte fraction | Right matched-byte fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` vs `ANTAG_INTL` | 1221 | 1025 | 46 | 59 / 59 | 0.838974 | 0.838684 |
| `PATCH_EN` vs `PATCH_INTL` | 1190 | 1000 | 56 | 51 / 50 | 0.855931 | 0.855623 |

The locale-pair results are much closer to each other than the Antagonizer-vs-patch results, as expected for related localized builds. This is a consistency observation, not proof of source-lineage equivalence.

## Important corrections to previous CF2 statements

The following old numbers/statements are superseded:

- `ANTAG_EN` was not `144684 instructions / 1242 candidates / 7252 calls / 4089 edges`; corrected values are `144696 / 1326 / 7472 / 4259`.
- The English diff is not `620 strict / 507 constant-only / 115 / 87 structural`; corrected values are `685 / 525 / 116 / 87`.
- Not every strict English match is relocated: `588 / 685` relocate and `97` stay at the same address.
- The Antagonizer structural matched-byte fraction is `0.765115` for EN and `0.759166` for INTL. As before, this metric deliberately ignores the constant-only bucket and therefore must not be read as a percentage of semantically unchanged code.
- Large merged spans remain a real limitation: `11` EN and `12` INTL Antagonizer-only structural candidates exceed 2000 bytes.

## Interpretation limits

These regenerated numbers fix the container-input error; they do not make the higher-level analysis more certain than the algorithms allow.

- Linear sweep still decodes embedded data as instructions.
- Candidate boundaries still come from direct-call targets and can merge unrelated code spans.
- Indirect calls remain unresolved.
- `constant_only_differences` intentionally mixes DS-relative relocation noise with any genuine constant/threshold changes.
- Whole-image Antagonizer-vs-patch differences may still include source-snapshot, compiler-layout or bug-fix differences unrelated to self-management. T1 must establish or constrain lineage before RE1 treats this pair as a behavioral differential.

## Reproduction commands

With the four pinned targets under `binaries/`:

```sh
python3 tools/fetch_free_targets.py --verify

python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/ANTAG_INTL.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_INTL.EXE --summary

python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```

For a future independent container-regression check, extract/reconstruct both objects and compare their SHA-256 values against the object fingerprint table above before trusting downstream disassembly counts.