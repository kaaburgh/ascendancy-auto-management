# T2 static-analysis bundle

This directory is the repo-safe handoff produced by `scripts/generate_t2_static_bundle.py` for roadmap item T2.

Start with [`manifest.json`](./manifest.json). The two `*.summary.json` files cover the canonical English Antagonizer target and English bug-patch baseline. [`wdump-comparison.json`](./wdump-comparison.json) records the independent Open Watcom header/object/page-map cross-check across all four pinned CF1 targets.

The generator deliberately keeps full target strings and full `le_disasm` v2 inventories under ignored `artifacts/t2-static-analysis/`; they are reproducible but not useful to bulk-commit. The committed summaries preserve exact target/object provenance, candidate-start samples plus a digest of the complete start list, headline counts, and stable digests of the omitted full candidate records/call edges/string order.

Regenerate from a checkout containing the four exact pinned files under `binaries/`:

```sh
python3 scripts/generate_t2_static_bundle.py --wdump /path/to/wdump
```

`wdump` is required rather than silently skipped. The script fails closed on a missing target, hash/size mismatch, malformed `wdump` output, duplicate/missing/out-of-range object or page rows, a non-sequential `le_image` page map that cannot be compared row-by-row through the current `info --json` schema, or any disagreement in the compared LE fields.

Tracked output is transactional. Generated summaries, `wdump-comparison.json`, and `manifest.json` are written into a sibling staging directory and the existing directory is replaced only after both canonical analyses and all four `wdump` comparisons pass. A failed rerun leaves the previous repo-safe bundle unchanged; unmanaged files such as this README are preserved across a successful replacement.

See [`../../../experiments/T2-static-analysis-bundle.md`](../../../experiments/T2-static-analysis-bundle.md) for the exact tool build used for the recorded comparison, results, evidence classification, and interpretation limits.