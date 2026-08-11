# T1 — Canonical target and comparison-baseline selection

- Roadmap item: T1
- Date: 2026-08-11
- Evidence category: **static** for all binary observations below; **reported** only where this record cites publisher/archive provenance already established by CF1
- Inputs: the four CF1 hash-pinned candidate executables supplied out of tree
- Tooling: `tools/inspect_target.py` 1.0.0 contract from T0 plus a bounded one-off Python probe for LE object-table fields and unique ASCII-string offsets

## Question

Which exact Antagonizer binary should be the M1 production target, which exact publisher bug-patch binary should be its comparison baseline, and is their build lineage comparable enough for RE1 to use a normalized whole-image differential without silently treating unrelated build drift as Antagonizer behavior?

This experiment does **not** implement the CF2 static-RE pipeline. It does not disassemble functions, produce xrefs/call graphs, reconstruct page streams, or create a general binary-diff framework. The additional parsing below is intentionally limited to T1 lineage evidence.

## Inputs and identity check

The supplied candidate bytes match the CF1 manifest exactly:

| Candidate | Size | SHA-256 |
| --- | ---: | --- |
| `ANTAG_EN.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `ANTAG_INTL.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `PATCH_EN.EXE` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `PATCH_INTL.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

CF1 already records publisher/archive provenance and the weak zip-member timestamp evidence. No candidate download or release-name assumption is used as binary identity here; the SHA-256 values above are the identities.

## T0 capture facts

Running the T0 metadata contract over the chosen English pair establishes:

- both are DOS `MZ` + Linear Executable (`LE`), little-endian, CPU type 2 (`Intel 80386`), OS type 1, module flags `0x00000200`, and 4096-byte LE pages;
- both have the secondary LE header at `e_lfanew = 0x2a50` and two LE objects;
- `ANTAG_EN.EXE` has 126 module pages, entry `object 1 + 0x683b4`, stack `object 2 + 0xa8220`, and data-pages offset `0x18000`;
- `PATCH_EN.EXE` has 121 module pages, entry `object 1 + 0x637c4`, stack `object 2 + 0xa76f0`, and data-pages offset `0x17600`;
- T0's bounded extender detector does not find a DOS/4G marker *inside the MZ stub*. This is not evidence that no extender is present. CF1 independently established a bound DOS/4G-family runtime from strings outside the shallow T0 scan boundary.

The reviewed machine-readable captures for the canonical pair are committed as [`../re/target-manifest.json`](../re/target-manifest.json).

## Build-lineage evidence

### 1. Identical bound MZ stub across all four candidates

The first `0x2a50` bytes (the complete MZ region before the LE header) are byte-identical in all four candidates.

SHA-256 of that region:

`b852ae395b9ad04503fc907ad03fa28ea6a17bf5f6c2be045bf96f7177592699`

This establishes a common bound-loader/stub input across both Antagonizer and bug-patch families. It is toolchain/build-family evidence, not proof of a source revision.

### 2. Same compiler/runtime fingerprints

All four images contain the same Watcom and runtime fingerprints, including:

- `WATCOM C Run-Time system ... 1988-1993`;
- `WATCOM C/C++32 Run-Time system ... 1988-1994`;
- the Ascendancy 1995 copyright banner;
- the same `May 02 1995` third-party library date string;
- `RATIONAL DOS/4G`.

No candidate contains a distinct embedded game build date or source-revision identifier that would directly settle source-snapshot identity.

### 3. Locale delta is preserved exactly in both build families

A bounded parse of the two 24-byte LE object-table entries shows this geometry:

| Candidate | Executable object virtual size | Executable pages | Writable object virtual size | Writable pages | Entry offset | Stack offset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | `0x72736` | 115 | `0xa8220` | 11 | `0x683b4` | `0xa8220` |
| `ANTAG_INTL` | `0x727e6` | 115 | `0xa8270` | 11 | `0x68464` | `0xa8270` |
| `PATCH_EN` | `0x6db46` | 110 | `0xa76f0` | 11 | `0x637c4` | `0xa76f0` |
| `PATCH_INTL` | `0x6dbf6` | 110 | `0xa7740` | 11 | `0x63874` | `0xa7740` |

For **both** Antagonizer and bug-patch families, International minus English is exactly:

- executable virtual size: `+0xb0`;
- writable virtual size: `+0x50`;
- entry offset: `+0xb0`;
- stack offset: `+0x50`.

That repeated locale transform is difficult to reconcile with two unrelated codebases that merely happen to share a compiler. It strongly supports the interpretation that each locale pair was built from the same underlying program layout with a small, consistent locale-dependent delta.

### 4. Antagonizer delta is also identical across locales

For **both** locale-matched `ANTAG - PATCH` comparisons, the object-layout delta is exactly:

- executable virtual size: `+0x4bf0` (19440 bytes);
- writable virtual size: `+0xb30` (2864 bytes);
- entry offset: `+0x4bf0`;
- stack offset: `+0xb30`;
- executable pages: `+5`;
- writable pages: unchanged at 11.

The fact that the same Antagonizer-vs-patch transform appears independently in the English and International build pairs is stronger lineage evidence than the archive member timestamps.

### 5. Unique-string displacement fingerprint is identical across locales

For each file, the probe extracts printable ASCII runs of length 8 or more and retains only strings that occur exactly once in that file. It then intersects a locale-matched Antagonizer/patch pair by exact string bytes and counts `ANTAG file offset - PATCH file offset`.

Results:

- English `ANTAG_EN ↔ PATCH_EN`: 467 common unique strings;
- International `ANTAG_INTL ↔ PATCH_INTL`: 467 common unique strings;
- the common-string sets are identical;
- the **complete 15-bucket displacement histogram is identical** in the two locale comparisons.

The histogram is:

```text
0:21
2560:3
4828:2
4832:2
8400:1
22000:10
23040:43
23160:6
23174:4
23176:64
23184:1
23220:6
23396:9
23412:3
23424:292
```

Canonical JSON encoding of that histogram (`sort_keys=True`, compact separators) has SHA-256:

`a02f981d15796c5e46f72c59096fe87b2d39aed3e9f5f43189209b2d9cbf83ed`

This does not identify which changed regions implement AI behavior. It does show that the large-scale layout transformation from bug patch to Antagonizer is reproduced with the same string-anchor displacement structure in both locales.

## Interpretation

### Established

- The four supplied candidates are exactly the CF1 hash-pinned bytes.
- All four share the same complete bound MZ stub and the same Watcom/DOS runtime fingerprints.
- The English↔International structural delta is exactly repeated in both the Antagonizer family and the bug-patch family.
- The Antagonizer↔bug-patch object-size/entry/stack delta is exactly repeated in both locales.
- The entire 467-anchor unique-string displacement fingerprint is identical for the English and International Antagonizer↔bug-patch comparisons.

### Strongly supported inference

The Antagonizer and official bug-patch binaries are from a directly comparable build lineage, not merely unrelated builds of the same game. In particular, the English pair is not disqualified by the approximately two-month zip member timestamp gap recorded by CF1: the binary structure shows the same transformation as the same-day International pair. The archive timestamps therefore remain weak packaging/file metadata and are not treated as source-build timestamps.

This evidence is sufficient to select the publisher bug patch as RE1's comparison baseline. It does **not** prove that every source file came from an identical source-control revision, because no embedded revision/build id is present.

### Remaining uncertainty handed to RE1

A normalized whole-image differential is justified as a **candidate-ranking tool**, but RE1 must not interpret every difference as Antagonizer AI behavior. Unrelated bug-fix/configuration drift remains possible even within a comparable lineage.

RE1 should therefore prefer changes that are corroborated by the International pair or by independent semantic evidence (strings, call/data relationships, UI/state proximity, later runtime confirmation). A change seen only in one locale requires an explanation before it is promoted as an Antagonizer-specific candidate.

## Decision

### Canonical M1 production target

`antagonizer-en` / `ANTAG_EN.EXE`

- SHA-256: `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`
- Size: 610863 bytes
- Reason: publisher-documented English Antagonizer release, cloud-available and independently mirrored per CF1, with build-lineage comparability to the English publisher bug patch strongly supported by the cross-locale structural evidence above.

### Canonical comparison baseline

`bugpatch-en` / `PATCH_EN.EXE` (publisher-documented version 1.6.5)

- SHA-256: `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`
- Size: 587451 bytes
- Reason: official publisher standalone bug-patch build, directly cloud-fetchable, same language as the canonical target, and structurally corroborated by the International pair.

### Future compatibility / corroboration candidates

`antagonizer-intl` and `bugpatch-intl` are **not** added to M1 support by this decision. They remain valuable cross-locale differential corroboration and future compatibility candidates. Supporting them as mod targets is later work.

The retail unpatched `ASCEND.EXE` remains an optional historical reference and is not required for T1 or RE1.

## Reproduction notes

Hash verification:

```sh
sha256sum ANTAG_EN.EXE ANTAG_INTL.EXE PATCH_EN.EXE PATCH_INTL.EXE
```

T0 captures:

```sh
python3 tools/inspect_target.py ANTAG_EN.EXE \
  --id antagonizer-en \
  --label "Antagonizer English canonical M1 target" \
  --output antagonizer-en.target.json

python3 tools/inspect_target.py PATCH_EN.EXE \
  --id bugpatch-en \
  --label "Official bug patch 1.6.5 English comparison baseline" \
  --output bugpatch-en.target.json
```

The additional lineage probe used only Python stdlib (`hashlib`, `re`, `struct`, `collections`) to read the LE object-table entries named by the existing header metadata and compare exact unique ASCII-string offsets. It was intentionally kept one-off rather than added as a general static-analysis tool, because CF2 owns reusable LE reconstruction/disassembly/diff infrastructure.

## Deliberately out of scope

- no CF2/T2 general static-RE pipeline;
- no function discovery, disassembly, xrefs, call graph, or candidate AI-region ranking;
- no runtime execution or demo evaluation (CF3 owns the demo/runtime question);
- no patch mechanism or target modification;
- no claim that the International binaries are supported M1 patch targets.
