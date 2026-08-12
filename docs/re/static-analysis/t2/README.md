# T2 static-analysis bundle

This directory is the repo-safe handoff produced by `scripts/generate_t2_static_bundle.py` for roadmap item T2.

Start with [`manifest.json`](./manifest.json). The two `*.summary.json` files cover the canonical English Antagonizer target and English bug-patch baseline. [`wdump-comparison.json`](./wdump-comparison.json) records the independent Open Watcom header/object/page-map cross-check across all four pinned CF1 targets.

The generator deliberately keeps full target strings and full `le_disasm` v2 inventories under ignored `artifacts/t2-static-analysis/`; they are reproducible but not useful to bulk-commit. The committed summaries preserve exact target/object provenance, complete candidate-start lists, headline counts, and stable digests of the omitted full records/call edges/string order.

Regenerate from a checkout containing the four exact pinned files under `binaries/`:

```sh
python3 scripts/generate_t2_static_bundle.py --wdump /path/to/wdump
```

`wdump` is required rather than silently skipped. The script fails closed on a missing target, hash/size mismatch, malformed `wdump` output, or any disagreement in the compared LE fields.

See [`../../../experiments/T2-static-analysis-bundle.md`](../../../experiments/T2-static-analysis-bundle.md) for the exact tool build used for the recorded comparison, results, evidence classification, and interpretation limits.
