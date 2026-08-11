## Roadmap item and goal

<!-- Link/name the roadmap item. State the bounded question or user-visible outcome. -->

## What changed

<!-- Describe the focused implementation, diagnostic, experiment, or documentation change. -->

## Evidence and reasoning

### Established

<!-- Facts only. Label static/runtime/synthetic/reported evidence and name the target hash when applicable. -->

### Still hypotheses / unknowns

<!-- Keep unverified interpretations explicit. -->

## Validation

<!-- List only checks actually run and their result. -->

- [ ] Documentation links/checks
- [ ] Focused unit/fixture tests
- [ ] Build for intended architecture
- [ ] Pattern/patch validation tests
- [ ] Install/remove/rollback test
- [ ] Other:

## Target-machine validation

<!-- Choose one and describe the exact scenario, binary SHA-256, and result or remaining request. -->

- [ ] Performed on the target game build
- [ ] Still required
- [ ] Not applicable

## Binary compatibility and safety

<!-- Record exact supported hash(es), signature/match invariants, expected bytes, fail-closed behavior, and rollback where relevant. -->

- [ ] Unsupported/unknown binaries fail closed
- [ ] Expected bytes/signature/invariants are verified before patching
- [ ] Ambiguous pattern matches are rejected
- [ ] On-disk changes have backup and automatic restore, or no on-disk patch is used

## Roadmap / RE / docs

- [ ] `ROADMAP.md` updated if status, evidence, sequencing, supported binaries, or decisions changed
- [ ] Durable RE findings saved under `docs/re/`
- [ ] Reproducible experiments/negative results saved under `docs/experiments/`
- [ ] No proprietary binaries, huge captures, secrets, or private user data committed

## Deliberately out of scope

<!-- Name tempting adjacent work and follow-ups intentionally not included. -->
