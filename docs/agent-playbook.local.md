# Ascendancy project-local playbook

## Canonical target and evidence anchors

Use `docs/re/targets.md` as the canonical supported-binary inventory unless the active roadmap item explicitly investigates another binary.

The current M1 canonical identities are:

- target: `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`;
- comparison baseline: `PATCH_EN.EXE`, SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`.

These targets are DOS `MZ` plus Linear Executable (`LE`) images. Do not substitute PE terminology or PE-only assumptions when recording container/header evidence.

T1 established strong build-lineage comparability from cross-locale structural evidence, but it did not prove an identical source-control revision. Whole-image differential output is a candidate-ranking aid rather than proof that every difference is Antagonizer AI behavior.

T2 does not establish function identity. Its candidate addresses are linear-sweep/direct-call analysis regions until stronger static/runtime evidence establishes semantics. Do not promote a candidate boundary or convenient symbol name to a fact.

## Repository and tool map

Project-specific navigation and experiment conventions that predate kit ownership remain project-owned:

- `docs/re/project-index.md` — durable Ascendancy RE index and links to canonical findings;
- `docs/experiments/project-guidance.md` — local experiment naming/template guidance;
- `tools/fetch_free_targets.py` and `tools/free-target-sources.json` — fail-closed free-target acquisition;
- `tools/le_image.py` — LE container/parser bridge;
- `tools/le_disasm.py` — static candidate/call inventory;
- `tools/le_diff.py` — conservative build comparison;
- `tools/inspect_target.py` — target metadata inspection;
- `scripts/` — reproducible build/run/validation/artifact automation;
- `artifacts/`, `binaries/`, `reference/`, and captures — local/ignored evidence inputs or outputs unless a roadmap item explicitly defines a safe committed derivative.

Before target-specific work, read the active roadmap item plus the relevant current `docs/re/` and `docs/experiments/` records. Prefer repository entry points and clean-checkout regeneration over hand-reproducing an equivalent analysis.

## Ascendancy validation matrix

Apply these project-specific minimums in addition to the generic profile contract when the change type matches:

- **Documentation / roadmap only:** resolve relative Markdown links, keep evidence/hypothesis language accurate, and confirm no proprietary/private material was added.
- **Analysis tool / parser / scanner:** deterministic fixture tests; malformed-input handling; zero-match/ambiguous-match coverage where applicable; exact input assumptions; schema/parser/input provenance for serialized evidence; and a clean-checkout real-target end-to-end regression when the acceptance claim depends on reproducible target bytes.
- **Runtime hook / injected diagnostic:** build for the intended architecture; exercise lifecycle/cleanup where possible; consider recursion/reentrancy; fail closed on unsupported target identity; separate expensive diagnostic behavior from normal patch mode.
- **Machine-code/runtime patch:** verify expected bytes/signature and instruction boundaries before writing; reject ambiguous matches; test rollback independently; do not call target behavior verified until it is observed on the exact target.
- **On-disk patch:** pre-patch SHA-256 check, automatic backup, post-patch verification, automatic restore, and restored-byte/hash verification.

Diagnostics must remain bounded. In normal patch mode avoid per-frame/draw filesystem I/O, avoidable allocations, global locks, expensive formatting, stack walking, or other observability work that can itself dominate the measured behavior.

## Ascendancy target-machine handoff

When a target-machine run is genuinely required, prepare one bounded scenario with exact target identity and predeclared success/failure oracle. Prefer a one-shot script/tool that validates inputs, performs or guides the scenario, collects bounded safe evidence, restores temporary changes, and writes a self-contained artifact such as `artifacts/run-*.zip`.

The artifact should contain hashes/version identifiers, configuration, detached run metadata, bounded logs and only the requested captures/dumps. Do not package the proprietary game binary or unrelated host/user data.
