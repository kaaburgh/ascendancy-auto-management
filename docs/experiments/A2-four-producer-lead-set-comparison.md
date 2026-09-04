# A2 — four-producer lead-set comparison

- Roadmap item: A2
- Issue: #119
- Date: 2026-09-04
- Target SHA-256: `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`
- Evidence category: static exact-target comparison
- Blind-RE provenance: **clean**
- Checkout: `5e361ff05165c5c91ec8aa7a29160867081c963c`

## Question

Do the four existing A2 producers produce intersecting leads, and do they agree on the ranking of the two Stage 1 candidate ranges, without adding a producer or new instrumentation?

## Inputs and provenance

All four producers were run from the same clean checkout and against the same freshly acquired, hash-verified `ANTAG_EN.EXE`. Their complete outputs were retained during the run under ignored `artifacts/` paths. The durable machine-readable summary, including output digests, is [`A2-four-producer-lead-set-comparison.json`](./A2-four-producer-lead-set-comparison.json).

| Producer output | Schema | Producer SHA-256 | Output SHA-256 | Hit rows | Unique leads |
| --- | --- | --- | --- | ---: | ---: |
| `a2-cycle-generate-raw.json` | `ascendancy.a2-raw-literal-reference-probe/v1` | `ba140f7d03c8fe7eac3c980fad1292b0ff6cfb549f30391dc0707bea9c365eb5` | `bf5ae7c9627e0a2df07019e1f3dfe060439a1ff524e6817eb5cb271d1cc34ee7` | 10 | 10 |
| `a2-cycle-decoded.json` | `ascendancy.a2-decoded-memory-reference-probe/v1` | `0a6c83b0768919f3fe89ce28df6adc9e0eaf050e27f8c6fb7647af5049f85773` | `283d8c9d4e2149235942f143274b29a35f745db3bda3ca12a30dbcebd8fba47d` | 340 | 40 |
| `a2-cycle-literal.json` | `ascendancy.a2-literal-reference-probe/v1` | `650623100dd601e6ca156c8adca779bdfc7d4c55ea9edf4bad44957246bc1afb` | `bf40c3f0e4cfb4c687a62a91669764cd2d9327d95af9bf44bade2610cdecaf78` | 1,983 | 713 |
| `a2-cycle-candidate-raw.json` | `ascendancy.a2-candidate-raw-references/v1` | `b5df3ea84d60dfee55a7b475537a513a9690a073742289617d3b882fbf78215f` | `3e0943821a3f7cdbc45ee009c988a2e58fc46bbbdab5b4de51c9f32296ceebe7` | 2,021 | 738 |

The acquisition and parser inputs were `tools/fetch_free_targets.py` (`3b81d922…`), `tools/free-target-sources.json` (`19088c1a…`), and `tools/le_image.py` (`925cc726…`). The target was acquired through the repository-approved `archive.org` source and verified before all producers ran.

## Method

The comparable lead identity is `(candidate range, candidate-relative offset)`. Producer-specific source locations are not treated as the same lead because the producers expose different source representations and address interpretations. Duplicate hit rows are collapsed for set operations; hit-row counts remain reported for ranking because they are the counts each producer emits.

The four candidate identifiers were normalized only for spelling: `object2-0x96c10` and `object2-96c10` denote the same pinned Stage 1 range, as do the corresponding `0x988dc` identifiers. No target bytes were modified or promoted.

## Result

The all-four normalized lead-set intersection is **empty (`0` leads)**.

The pairwise/triple structure explains that result:

- decoded memory leads: `40` unique leads; all `40` are present in the mapped-literal and full-file raw sets;
- mapped-linear raw leads: `10` unique leads; all `10` are present in the mapped-literal and full-file raw sets;
- mapped-literal leads: `713` unique leads; all `713` are present in the full-file raw set;
- the mapped-linear producer emits only `linear-va` hits, while the decoded producer's `340` hits are all `target-object-relative`; those address-model-specific target offsets have no common lead, so the four-way intersection is not evidence that any producer is wrong;
- the result is an agreement about lead containment only. It does not establish an executed reference, semantic consumer, unused range, or reusable capacity.

Candidate ranking by emitted hit rows is:

| Producer | `object2-0x96c10` | `object2-0x988dc` | First-ranked candidate |
| --- | ---: | ---: | --- |
| mapped-linear raw | 7 | 3 | `0x96c10` |
| decoded memory | 74 | 266 | `0x988dc` |
| mapped literal | 1,162 | 821 | `0x96c10` |
| full-file raw | 1,195 | 826 | `0x96c10` |

The same ordering holds when ranking by unique normalized leads (`7/3`, `10/30`, `413/300`, and `436/302`). Thus the models have **majority ranking agreement (3/4)** but not unanimous agreement; pairwise agreement is `3/6` model pairs. Both candidate ranges occur in every candidate-level set, so candidate-level presence is not discriminating.

## Interpretation and A2 impact

This is a useful bounded result from the four existing producers. The decoded model's unique leads are contained in both broader raw models, while the narrow linear-only model contributes a disjoint address-model view. The ranking split means the outputs do not justify choosing a patch/integration mechanism or promoting either mapped range to reusable capacity.

A2 remains **Investigation first**. The next bounded action remains the already-prepared read-only runtime capacity observation; this result does not authorize a fifth producer, a new instrumentation path, or a canonical-target run beyond the already executed producer comparison.

## Validation and cycle outcome

- Existing producer fixture/safety tests: 25 tests passed.
- Target acquisition: approved source and canonical target hash verified.
- Comparison checks: JSON parsing, schema/count/provenance checks, normalized-set cardinalities, pairwise/triple intersections, and ranking calculations passed.
- Validation execution level: `reconstructed-local` for this cycle's comparison; the target-specific inputs are exact-target static evidence, while CI evidence is separately bound to its own SHAs.
- Target-machine validation: **not applicable**; issue #119 explicitly requires comparison of existing outputs and no new operator session.
- Cycle outcome: **evidence for A2's open question** (not tooling-only and not a target blocker).
- Previous A2 cycle outcome: `unknown`; no provenance-bound durable cycle-outcome record existed at cycle start. This record establishes the outcome for the next independent cycle.

No mapped bytes are promoted to reusable capacity on set intersection alone, and no mechanism is selected.

