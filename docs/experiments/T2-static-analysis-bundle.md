# T2 — reproducible static-analysis bundle

- Date: 2026-08-12
- Roadmap item: T2
- Evidence: **static**, generated from the four exact CF1/T1 hash-pinned executables
- Blind-RE provenance: **clean**
- Environment: Linux x86_64, Python 3, GNU objdump 2.44
- Independent format oracle: Open Watcom `wdump` 2.0 beta, build timestamp `Aug 1 2026 04:24:55`, 64-bit

## Question

Can later cloud agents reproduce the canonical Antagonizer/baseline static structure without an interactive RE database, and does an independent Open Watcom dumper agree with the repository LE parser on the target-level header/object/page mapping?

## Inputs

| Id | Filename | Size | SHA-256 | Role |
| --- | --- | ---: | --- | --- |
| `antag-en` | `ANTAG_EN.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` | canonical M1 target |
| `patch-en` | `PATCH_EN.EXE` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` | canonical comparison baseline |
| `antag-intl` | `ANTAG_INTL.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` | cross-locale format-oracle check only |
| `patch-intl` | `PATCH_INTL.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` | cross-locale format-oracle check only |

The executables came from the operator-supplied executable bundle and re-hashed to the established CF1/T1 values before analysis. No target binary is committed.

The operator-supplied RE-toolkit archive had SHA-256 `388ac94389d360d234d11e302eca26019abcd128f19e2fc5cf1ad61426823f03`; its `wdump` binary had SHA-256 `74282d0b263015636b9eb00172c5007e593155aaf829e788a80b4e3e0ccb815a`. The toolkit provenance identifies Open Watcom release `2026-08-01-Build`, source commit `88195868c8824dabaf960c6f1cc7833ede140b12`. The supplied tool contains no target-specific recovered knowledge.

## Procedure

The reusable entry point is:

```sh
python3 scripts/generate_t2_static_bundle.py \
  --binaries binaries \
  --wdump /path/to/wdump
```

The script fails closed unless all four filenames, sizes, and SHA-256 values match the pinned target set. It then:

1. runs `tools/le_image.py info --json` on all four targets;
2. for the canonical English pair, runs `tools/le_image.py strings --json --min-length 4` and `tools/le_disasm.py`;
3. stores the full canonical layouts, string inventories, and `le_disasm` v2 inventories only under ignored `artifacts/t2-static-analysis/`;
4. stages the compact repo-safe summaries in a sibling temporary directory rather than modifying `docs/re/static-analysis/t2/` in place;
5. runs `wdump -q -p` on all four pinned targets;
6. requires exact object/page index coverage from `wdump` (no duplicates, missing rows, or out-of-range row indices), requires `le_image` to report the pinned target page maps as sequential before using identity page mapping, and then compares every object record/page-map row plus every LE header field also exposed by `le_image.py info --json`;
7. fails if any coverage invariant or compared field differs;
8. publishes the staged tracked bundle only after both canonical analyses and all four `wdump` comparisons pass. A failed rerun leaves the previously committed repo-safe bundle unchanged.

The raw `wdump` text is not committed. Its SHA-256 is recorded per target in `wdump-comparison.json`, so a rerun with the same `wdump` build can be compared exactly without adding another bulky dump.

## Canonical static bundle

The committed repo-safe bundle is under [`../re/static-analysis/t2/`](../re/static-analysis/t2/).

### `ANTAG_EN.EXE` — `8d91e89e…`

- LE header: `0x2a50`; 80386 LE; 4096-byte pages; 126 pages; enumerated data at file offset `0x18000`.
- Object 1: code, base `0x10000`, virtual size `0x72736` (468790), pages 1–115.
- Object 2: data, base `0x90000`, virtual size `0xa8220` (688672), pages 116–126.
- Entry: object 1 + `0x683b4` = VA `0x783b4`.
- `le_disasm`: 144696 decoded instructions, 1326 candidate starts, 7472 direct in-object call sites, 11059 distinct branch targets, 4259 call-graph edges.
- Printable runs of at least four characters: 3849 total (2395 in object 1, 1454 in object 2); the full ordered string index is represented by SHA-256 `dfdc88533bafddee3b69ceeb122dc0741313cf1a276fd253b308a5c95032c622` rather than committed verbatim.

### `PATCH_EN.EXE` — `7c944866…`

- LE header: `0x2a50`; 80386 LE; 4096-byte pages; 121 pages; enumerated data at file offset `0x17600`.
- Object 1: code, base `0x10000`, virtual size `0x6db46` (449350), pages 1–110.
- Object 2: data, base `0x80000`, virtual size `0xa76f0` (685808), pages 111–121.
- Entry: object 1 + `0x637c4` = VA `0x737c4`.
- `le_disasm`: 139093 decoded instructions, 1297 candidate starts, 7251 direct in-object call sites, 10433 distinct branch targets, 4162 call-graph edges.
- Printable runs of at least four characters: 3734 total (2308 in object 1, 1426 in object 2); ordered string-index SHA-256 `6347cf98d6507c70428dae3d4d0afcd7c5732f696f383429df467025c7bcacd5`.

These `le_disasm` numbers reproduce CF2's corrected real-target measurements. Candidate starts remain direct-call-derived linear-sweep regions, **not verified function boundaries**. No semantic function names are established by T2.

## Independent `wdump` cross-check

Result: **PASS on all four pinned targets with zero disagreements**.

For each target, the script compared 24 LE header values exposed by both tools, both object records, and every `wdump -p` page-map row:

| Target | Header fields | Objects | Page entries | Disagreements |
| --- | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 24 | 2 | 126 | 0 |
| `ANTAG_INTL` | 24 | 2 | 126 | 0 |
| `PATCH_EN` | 24 | 2 | 121 | 0 |
| `PATCH_INTL` | 24 | 2 | 121 | 0 |

The hardened comparison also checks that those rows cover exactly object indices `{1,2}` and page indices `1..N` once each. A duplicate row can no longer hide a missing row merely because the total count still matches. Because `le_image.py info --json` currently exposes only the boolean `numbers_are_sequential` rather than the individual page-number vector, the row-by-row identity comparison is now explicitly gated on that boolean; if a pinned target is ever parsed as non-sequential, the T2 check fails closed instead of silently assuming identity mapping.

In particular, Open Watcom independently reports `page_off = 0x18000` for both Antagonizer builds and `0x17600` for both bug-patch builds, the same object bases/sizes/page ranges, and the same sequential page-to-file-offset mapping as `le_image.py`. This is the target-level independent tool-output check CF2 review required; it is distinct from the earlier source-code reasoning that established the parser field semantics.

`wdump` also labels the LE header OS type as `1` for all four images. T2 records this only as a static header-field agreement; it does not infer runtime OS/extender semantics from that field.

## Repo-safe artifact contract

[`../re/static-analysis/t2/manifest.json`](../re/static-analysis/t2/manifest.json) is the entry point. Each canonical summary contains:

- the exact source SHA-256 and reconstructed code-object SHA-256;
- complete `le_image` layout output;
- `le_disasm` schema/tool/provenance metadata and headline counts;
- candidate-start samples plus SHA-256 of the complete sorted candidate-start list;
- SHA-256 digests of the full candidate records, call-edge list, and regenerated full inventory file;
- string counts, object distribution, ordered full-index digest, longest-run metadata without text, and hashed runtime/toolchain indicators.

This deliberately avoids committing target executables, raw disassembly, or bulk target strings. Later work that needs the full `le_disasm` function records/call edges or full strings regenerates them into ignored `artifacts/` with the single script above.

Tracked output is transactional: the generator copies the existing repo-safe directory into a same-filesystem staging directory, overwrites generated files there, and requests publication only after all required checks pass. Publication swaps the staged directory into place and keeps/restores the previous directory if the replacement itself fails. An exception before publication discards staging and leaves the existing repo output untouched.

## Evidence boundary and limits

- **Static, clean:** all target facts in this record were produced from the supplied exact binaries with current repository tooling or the generic Open Watcom dumper.
- No external target-specific decompilation, address map, source port, cheat table, or third-party mod internals were consulted.
- `wdump` agreement validates the LE header/object/page interpretation for these exact binaries. It does not validate higher-level candidate boundaries or semantics.
- Linear sweep can decode embedded data; direct-call-derived candidate starts can fold indirect-only callees into larger spans.
- T2 does not rank Antagonizer-vs-patch changes, identify self-management code, infer calling convention, or perform runtime validation. Those remain downstream roadmap work.

## Validation performed

- all four supplied executable SHA-256 values matched the pinned target set;
- focused T2 unit tests: **10 tests, all passed**, covering the normal `wdump` comparison, page-offset mismatch, duplicate/missing page indices, duplicate/missing object indices, out-of-range page indices, non-sequential `le_image` page-map refusal, string-summary redaction, transactional failure/no-publication, transactional success/preservation of unmanaged files, and fail-closed missing-target handling;
- the supplied real `wdump` output on all four exact targets has object indices `[1,2]`, exact page-index coverage (`1..126`, `1..126`, `1..121`, `1..121`), identity map-page values, and zero page flags, so the new stricter coverage gates accept the same independently observed target output;
- full T2 generator completed successfully against all four real targets before the hardening; the hardening does not change successful-target summary/comparison data, only acceptance of malformed/regressed inputs and when tracked output is published;
- canonical `le_disasm` headline counts matched the corrected CF2 measurements;
- independent `wdump` comparison passed with zero disagreements across 24 shared header fields, two objects, and every page row for all four targets;
- no target-machine/runtime behavior was claimed or required.
