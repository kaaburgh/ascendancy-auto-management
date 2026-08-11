# CF2 — corrected real-target disassembly and diff regeneration

- Date: 2026-08-11
- Scope: PR #4, post-`page_off @ +0x80` regeneration and review hardening
- Evidence: **real-target static** against all four CF1 hash-pinned executables
- Disassembler: GNU objdump, `-D -b binary -m i386 -M intel --adjust-vma=<object-base>`
- Analysis model: current PR `le_image.py` reconstruction semantics + current `le_disasm.py` / `le_diff.py` algorithms

## Purpose

The first CF2 target measurements were produced from object bytes reconstructed with the wrong LE enumerated-page base (`impmod_off @ +0x70`). After the parser was corrected to Open Watcom's absolute `page_off @ +0x80`, every disassembly- and signature-derived target number was regenerated from scratch rather than adjusted arithmetically.

A later review found a second, independent problem in the differential model: the then-called "strict" signature masked every operand whose value landed inside an image object. That preserved relocation tolerance but could also hide a behavioral retarget such as a changed callee, global/state field, or table address. The current model therefore keeps exact operands in the only class called identical and exposes reference-only changes as a separate bucket.

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

These hashes are over the exact flat object byte streams handed to analysis. They are regression anchors for the container layer without committing target bytes.

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

The old headline values `144684 instructions / 1242 candidates / 7252 calls / 4089 edges` for `ANTAG_EN` were products of the shifted object stream and must not be reused.

## Versioned inventory contract

Serialized `le_disasm` JSON is a cross-task handoff and therefore now fails closed rather than being accepted on shape alone.

Current inventories record:

- schema `ascendancy.le-disasm.inventory/v2`;
- source executable SHA-256;
- reconstructed object SHA-256;
- parser-layout identity `open-watcom-os2-flat-header-page-off-0x80/v1`;
- `page_off` header offset and absolute data-page offset;
- all three signature levels required by the current differential model.

`le_diff` rejects legacy/unversioned JSON, the previous `+0x70` parser layout, missing object fingerprints, or missing signature fields. A stale inventory can no longer be accepted merely because it carries the same source EXE hash.

## Current Antagonizer ↔ bug-patch differential

The comparison is deliberately conservative and runs in three matching passes, producing four classes:

1. **exact** — whitespace-normalized instruction text with every operand preserved; this is the only class called identical;
2. **reference-only** — exact pass failed, but the candidates match after masking operands whose values fall inside image object ranges; this mixes benign relocation with possible callee/global/table retargets and is therefore a difference bucket;
3. **constant-only** — the first two passes failed, but the candidates match after masking all hexadecimal operands; this mixes DS-relative layout movement with genuine threshold/flag/size changes;
4. **structural** — still unmatched after all three passes.

The previous post-layout-correction "strict" class masked in-image references and was too permissive. Its counts split exactly into the new exact + reference-only classes; constant-only and structural counts do not change.

### English pair

`ANTAG_EN` (`8d91e89e…`) vs `PATCH_EN` (`7c944866…`):

| Metric | Value |
| --- | ---: |
| Antagonizer candidate regions | 1326 |
| Patch candidate regions | 1297 |
| Exact matches | 72 |
| Exact matches relocated | 50 |
| Exact matches at same address | 22 |
| Reference-only differences | 613 |
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

Bucket arithmetic closes exactly: `72 + 613 + 525 + 116 = 1326` and `72 + 613 + 525 + 87 = 1297`.

The previous `685 strict` figure is now understood as `72 exact + 613 reference-only`; it must not be described as 685 identical candidates.

The ten largest Antagonizer-only structural candidates remain:

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
| Antagonizer candidate regions | 1326 |
| Patch candidate regions | 1296 |
| Exact matches | 72 |
| Exact matches relocated | 50 |
| Exact matches at same address | 22 |
| Reference-only differences | 611 |
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

Bucket arithmetic again closes: `72 + 611 + 520 + 123 = 1326` and `72 + 611 + 520 + 93 = 1296`.

The previous `683 strict` figure is now `72 exact + 611 reference-only`.

The ten largest Antagonizer-only structural candidates remain:

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

This is not the product differential, but it checks that the same classification behaves coherently across localization builds.

| Pair | Exact | Relocated exact | Reference-only | Constant-only | Structural left/right | Left structural fraction | Right structural fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` vs `ANTAG_INTL` | 114 | 67 | 1107 | 46 | 59 / 59 | 0.838974 | 0.838684 |
| `PATCH_EN` vs `PATCH_INTL` | 114 | 67 | 1076 | 56 | 51 / 50 | 0.855931 | 0.855623 |

This is a consistency observation, not proof of source-lineage equivalence.

## Interpretation limits handed to RE1

The corrected container and conservative signature model still do not turn candidates into proven functions or behavioral changes.

- Linear sweep can decode embedded data as instructions.
- Candidate starts come only from direct-call targets plus a seed. A function reached only indirectly has no independent candidate start and is folded into the preceding span.
- The English structural set contains 11 spans over 2000 bytes and reaches 7964 bytes; `116` therefore means 116 regions/leads, not 116 changed functions.
- `reference_only_differences` is a live analysis bucket: a changed in-image operand may be relocation noise or a real retarget to another callee/global/state field/table.
- `constant_only_differences` is also live and is the largest unresolved English bucket (525 candidates). If Antagonizer primarily retuned thresholds/biases/flags, meaningful signal may be here rather than in the structural list.
- Parsing LE fixup records is the clean next discriminator for loader-patched operands if RE1 cannot make the two unresolved buckets tractable.
- Whole-image Antagonizer-vs-patch differences may include source-snapshot/compiler/bug-fix differences unrelated to self-management. T1 must establish or constrain lineage before RE1 interprets them behaviorally.

The structural matched-byte fraction deliberately ignores both unresolved middle buckets and must not be read as a percentage of semantically unchanged code.

## Clean-checkout real-target regression

Review correctly identified that the initial corrected regeneration was performed in a sandbox without a Git checkout: current branch source was read through the GitHub connector and the algorithms were faithfully reproduced locally. That was useful evidence, but it was not sufficient to call the current repository pipeline verified end to end.

The repository therefore now contains `scripts/validate_cf2_real_targets.py`. In a clean checkout it:

1. runs `tools/fetch_free_targets.py` and `--verify`;
2. parses all four exact target files with repository `le_image.py`;
3. requires `page_off @ +0x80` and exact EOF closure;
4. checks all eight reconstructed-object SHA-256 fingerprints above;
5. invokes repository `tools/le_disasm.py` for all four targets and checks the inventory counts;
6. invokes repository `tools/le_diff.py` on both product pairs and both locale sanity pairs and checks all four-class metrics above.

GitHub Actions runs this as the separate **CF2 real-target regression** job so the normal unit suite remains network-free. The workflow is the authoritative checkout-level gate; CF2 must not be called `Completed and verified` if this job is not green on the current head.

Local focused regression while implementing the review fix: 77 `le_disasm` / `le_diff` tests passed, including explicit in-image call-retarget visibility and fail-closed stale-inventory cases. The full repository suite and real-target gate are delegated to the clean-checkout workflow above.

## Important superseded statements

Do not reuse any of these from git history or earlier review discussion:

- `ANTAG_EN = 144684 instructions / 1242 candidates / 7252 calls / 4089 edges` — wrong `+0x70` object stream;
- English `620 strict / 507 constant-only / 115 / 87 structural` — wrong `+0x70` object stream;
- English `685 strict / 525 / 116 / 87` interpreted as 685 identical candidates — corrected object stream but over-masked in-image references; final classification is `72 exact / 613 reference-only / 525 constant-only / 116 / 87 structural`;
- international `683 strict / 520 / 123 / 93` interpreted as 683 identical candidates — final classification is `72 exact / 611 reference-only / 520 / 123 / 93`;
- "every strict match relocated" — false in both superseded models.

## Reproduction commands

With the four pinned targets under `binaries/`:

```sh
python3 tools/fetch_free_targets.py --verify
python3 scripts/validate_cf2_real_targets.py
```

For a clean checkout with permitted CF1 network access:

```sh
python3 scripts/validate_cf2_real_targets.py --fetch
```

For manual inspection:

```sh
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_disasm.py binaries/ANTAG_INTL.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_EN.EXE --summary
python3 tools/le_disasm.py binaries/PATCH_INTL.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_INTL.EXE binaries/PATCH_INTL.EXE --summary
```
