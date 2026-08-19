# A1 exact-target static evidence bundle

Roadmap item: **A1 — Design the M1 per-planet profile state representation**  
Tracking issue: **#26**  
Process-enablement issue: **#51**  
Evidence class after execution: **static**  
Blind-RE provenance: **clean**

## Purpose

A1 currently has two independent exact-target static probes prepared on `main`:

- `scripts/probe_a1_planet_array_indexing.py` investigates the still-unestablished array/indexing relationship needed before a slot-based sidecar key can be considered;
- `scripts/probe_a1_managed_field_writers.py` inventories direct decoded `planet_record+0x5a` references as bounded leads for the still-unestablished lossless Manual-transition invalidation boundary.

Both probes are intentionally conservative and both remain useful independently. This bundle adds **orchestration only**: one exact-target run fetches the canonical free target once, executes both repository probes on the same checkout/target identity, and uploads their derived JSON together with one hash-bound bundle manifest.

It does not change either probe's analysis model, claim boundary, or roadmap sequencing.

## Execution

Use `.github/workflows/a1-static-evidence-bundle.yml` through either supported evidence-only trigger:

1. **Manual GitHub Actions dispatch.** Run the `workflow_dispatch` action on the exact repository revision to investigate.
2. **Dedicated evidence branch.** Create a new branch whose name starts with `evidence/a1-static-evidence-bundle/` at the exact commit to investigate. The GitHub `create` event starts the bundle only for that branch namespace. Use a fresh suffix for each run rather than moving an old evidence branch.

The evidence-branch path exists so unattended environments that can create Git refs but cannot call `workflow_dispatch` can still run the already-defined cloud experiment. It is **not** ordinary PR correctness CI: creating or updating a normal feature/PR branch does not run the exact-target acquisition job.

For either trigger, the workflow checks out `${{ github.sha }}` and independently verifies `git rev-parse HEAD` equals that SHA before target acquisition. It then verifies GNU `objdump` availability, fetches canonical `antagonizer-en` through the existing fail-closed acquisition path, and runs:

```sh
python scripts/probe_a1_planet_array_indexing.py \
  binaries/ANTAG_EN.EXE \
  --output artifacts/a1-planet-array-indexing.json

python scripts/probe_a1_managed_field_writers.py \
  binaries/ANTAG_EN.EXE \
  --checkout-sha "$GITHUB_SHA" \
  --output artifacts/a1-managed-field-writer-inventory.json
```

The workflow then binds both derived records to the same checkout SHA and hashes all material repository inputs used by the bundle. It emits:

- `artifacts/a1-planet-array-indexing.json`;
- `artifacts/a1-managed-field-writer-inventory.json`;
- `artifacts/a1-static-evidence-bundle.json`.

Only these derived JSON records are uploaded. The target executable is never uploaded as evidence.

## Evidence boundary

A successful bundle run establishes only that both already-defined static probes executed successfully against the exact canonical target on one pinned repository revision.

It does **not** establish any of the following merely because the workflow is green:

- a planet-array base or count;
- stable slot indexing;
- pointer lifetime or reuse safety;
- exhaustive `planet_record+0x5a` writer coverage;
- a lossless Manual-transition invalidation boundary;
- A1 completion.

The bundle manifest records those claims as `false`. The individual probes keep their existing `unestablished` / `incomplete-model` semantics. Any shared operand, new potential writer, or absence of additional direct writers remains an investigation result to interpret under the corresponding durable probe record; bundling cannot upgrade it.

## Why bundle the runs

The two probes consume the same public canonical target and are both current A1 evidence-producing steps. Running them from one exact checkout removes duplicated target acquisition and reduces the chance that later interpretation accidentally compares artifacts from different repository heads while preserving separate machine-readable outputs and separate analysis semantics.

The original per-probe manual workflows remain valid. This bundle is a convenience/evidence-coherence path, not a replacement claim and not a new source of target knowledge.
