# RE3 — static automatic-management turn-path experiment

Date: 2026-08-13  
Roadmap item: RE3  
Blind-RE provenance: **clean**  
Evidence class: **static**.

## Question

Which static call/data path consumes the existing player-planet self-management condition during turn processing, reaches the automatic decision logic, and commits the selected next action — without reconstructing the complete AI?

A second requirement was to establish the relevant calling convention from real target call sites before assigning meaning to register values.

## Inputs

Only the supported repository state and hash-pinned target bytes were used. No target-specific external recovered knowledge or unsupported repository history was consulted.

Canonical target:

- `ANTAG_EN.EXE` — 610863 bytes — SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

Corroboration binaries:

- `ANTAG_INTL.EXE` — SHA-256 `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c`;
- `PATCH_EN.EXE` — SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`;
- `PATCH_INTL.EXE` — SHA-256 `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b`.

The canonical target was independently present both in the supplied executable bundle as `ANTAG_EN.EXE` and in the supplied retail tree as `ANTAG.EXE`; both copies had the same canonical SHA-256.

Static tooling supplied for the experiment:

- Rizin `0.9.1` (`linux-x86-64`);
- NDISASM `3.02` (built 2026-06-28).

The supplied toolkit's `verify.sh` completed `toolkit verification: PASS` before analysis.

Repository evidence read before analysis:

- [`../re/vanilla-antagonizer-diff.md`](../re/vanilla-antagonizer-diff.md), especially RE1 H1/H3 and the `planet.cpp` cluster;
- T2's exact load-layout facts and candidate-boundary caveat;
- `AGENTS.md` and [`../agent-playbook.md`](../agent-playbook.md).

RE2 output was deliberately **not** used: RE2 may execute in parallel, and RE3 independently established the turn-path state-consumption hypothesis and ABI evidence without modifying RE2-owned files.

## Procedure

### 1. Verify exact inputs

The four executable hashes were checked before target-specific interpretation:

```sh
sha256sum ANT*EXE PATCH*EXE
```

Observed hashes exactly matched the T1/RE1 pins above.

### 2. Start from the RE1 turn-path leads, not guessed names

Run Rizin analysis on the canonical target and inspect RE1's bounded cluster plus its direct callers:

```sh
rizin -q ANTAG_EN.EXE
[0x00000000]> e scr.color=false
[0x00000000]> aaa
[0x00000000]> s 0x352e0
[0x000352e0]> axt
[0x000352e0]> pdf
```

`0x352e0` had a direct turn-side caller in candidate `0x20c94`. Expanding that caller showed a planet loop calling `0x352e0` with stride `0x7b`, followed by a race loop calling `0x3b220` with stride `0x1ee`.

Continue only along the smallest data-flow chain needed to distinguish state gate, policy, and action mutation:

```text
0x20c94 -> 0x3b220 -> 0x3b5b8 -> 0x3d8f0 -> 0x34b0c
```

Inspect exact callers/callees and object-relative accesses at each boundary rather than assigning source names.

### 3. Independently byte-check the decisive instruction boundaries

Rizin supplies the LE-aware graph/relocation view. To avoid relying on one decoder for the decisive blocks, short raw code slices were decoded independently with NDISASM.

For the exact Antagonizer layout established by T2, object 1 starts at VA `0x10000` and enumerated page data starts at file offset `0x18000`, so for the pinned code object the inspected raw file offset is:

```text
file_offset = 0x18000 + (VA - 0x10000)
```

For the pinned patch pair the corresponding T2 `page_off` is `0x17600`.

The short canonical byte anchors checked in this experiment were:

- `0x20dac`, 22 bytes — SHA-256 `660390360cb824224e0786d789654b7fcaac648075fbe7ba481b3d7797655854` — per-planet call/`0x7b` stride boundary;
- `0x20de6`, 53 bytes — SHA-256 `9bf7a8f97288746f9a5deb337e93d47a6cdeb5dd17108c7bc623e2c1ee59d376` — non-player and explicit current-player calls into `0x3b220`;
- `0x3c0eb`, 50 bytes — SHA-256 `c7378b4c197b8c9f3f8e4904081fc6c5f3ab0a99737938c0be5578b498122ce6` — owner/player/`+0x5a`/`+0x54` gate through call `0x3d8f0`;
- `0x3d8f0`, 45 bytes — SHA-256 `158aacb2dd2646a3968cc8668bfcf6ecdb0dd2065d56e5bad2a931558b739ae7` — policy-entry prologue consuming incoming `EAX` and `EDX`;
- `0x3df70`, 29 bytes — SHA-256 `da28be8c2bbd4e49082f8a5f1bfcb80236c70f79f7ff8470166dd1a3d8f40066` — four-register call preparation into `0x34b0c`;
- `0x34db2`, 69 bytes — SHA-256 `811abe7ee39b96bd91805eaf52cf6965331569ddc165331612543085103a4cdb` — selected-slot/action writes including `+0x52` and `+0x54`.

NDISASM agreed with the relevant Rizin instruction boundaries and register/object-relative operations. Raw absolute data operands differ from Rizin's relocated VAs as expected for an LE image; no semantic conclusion was based on treating the unrelocated raw immediate as a final linear data address.

### 4. Establish the ABI from real calls

At `0x3c118`, `EDX` is already the current `planet_base + index*0x7b` pointer and `EAX` is loaded from the current race pointer immediately before `call 0x3d8f0`. There are no argument pushes.

At `0x3d8f0`, the callee immediately:

```text
stores incoming EAX
copies incoming EDX to ESI
```

It then allocates `0x10c` bytes of local stack. A full NDISASM pass over the candidate through its return found no `[esp+...]` access above `+0x108`; therefore the candidate does not consume hidden caller-stack arguments above that local frame.

At `0x3df88 -> 0x34b0c`, the caller prepares `ECX=1`, `EBX=0x15`, `EAX=planet`, `EDX=selected-index`; `0x34b0c` consumes those register values.

This is observed internal register calling consistent with Watcom `__watcall` order `EAX, EDX, EBX, ECX`. The conclusion is deliberately scoped to these game-internal calls rather than applied to every library/runtime call in the image.

### 5. Corroborate the gate across product and locale pairs

Search the three corroboration binaries for the same owner/player/action gate and follow its direct policy call.

Observed boundaries:

| Build | Gate start used for comparison | Policy target |
| --- | ---: | ---: |
| `ANTAG_EN` | `0x3c0eb` | `0x3d8f0` |
| `ANTAG_INTL` | `0x3c12b` | `0x3d930` |
| `PATCH_EN` | `0x39f28` | `0x3a5a0` |
| `PATCH_INTL` | `0x39f68` | `0x3a5e0` |

Both International mappings are exactly `+0x40` from their English product counterpart at these boundaries.

All four gates compare the same planet-relative owner field `+0x57`, preserve the current-player-only `dword +0x5a` test, require `byte +0x54 == 0xff`, and then call the product's downstream policy candidate.

The first 45 bytes at `ANTAG_EN 0x3d8f0` and `ANTAG_INTL 0x3d930` are identical. The first 45 bytes at `PATCH_EN 0x3a5a0` and `PATCH_INTL 0x3a5e0` are also identical. The Antagonizer and patch policy entries differ materially from each other immediately after the shared register-saving shape, so this is not a claim of exact policy identity across products.

This establishes a stronger relationship than fuzzy address similarity: the same behavioral gate calls each product's policy candidate, and the relationship repeats independently in both locales.

## Observations

### A. General planet update happens before the automation decision

`0x20c94` walks every planet at stride `0x7b` and calls RE1 lead `0x352e0`. The candidate resolves existing current actions/progress and updates planet-relative state. It is therefore on turn processing but is not conditional on the player automation gate.

This narrows RE1 H1: `0x352e0` is an update/progression anchor, not the best policy-entry hook.

### B. Race processing is shared with the current player

The same `0x3b220` path runs for non-player races and, by an explicit second call, the current player race. `0x3b220` calls `0x3b5b8` at `0x3b31b`.

This supports a shared generic-AI implementation with a player-specific gate rather than two independent planet-management engines.

### C. The discriminating player gate is object-relative `+0x5a`

The final planet loop in `0x3b5b8` compares `[planet+0x57]` with the current race id. When the race is not the player, it proceeds directly. When it is the player, it tests `dword [planet+0x5a]` and skips the planet when the value is zero **unless** a separate global override is nonzero.

It then requires `[planet+0x54] == 0xff` before calling the downstream policy candidate.

This is the highest-information static candidate for the existing per-planet self-management state consumption. It does **not** establish that the UI toggle writes `+0x5a`.

### D. Policy and mutation are separate layers

`0x3d8f0` performs a large decision/scoring sequence and reaches `0x34b0c` with selected values. `0x34b0c` modifies slot state and explicitly writes the planet's `+0x52/+0x54` current-selection fields.

Therefore RE3 can distinguish:

- state gate: `0x3c0fc` within `0x3b5b8`;
- policy: `0x3d8f0`;
- action/queue mutation: `0x34b0c`;
- generic turn update/recalculation: `0x352e0` / `0x34e70`.

## Interpretation and confidence

- **High static confidence:** the current-player-only `+0x5a` predicate gates entry into the same generic management policy used for non-player owned planets.
- **High static confidence:** `0x3d8f0` is an automatic next-action policy candidate because it is called after the owner/player/empty-action gate and feeds concrete selection values to a mutation routine.
- **High static confidence:** `0x34b0c` is a downstream action/queue mutation seam because it writes the current slot/action fields.
- **Medium semantic confidence:** `+0x5a` is specifically the UI-visible “self management” state. The control-flow role is strong and cross-product-stable, but the UI writer must be established independently by RE2/RE4.
- **Unknown:** semantics of the separate global override that can bypass a zero `+0x5a` value for the player.

## Rejected / narrowed hypotheses

- **Rejected as the primary policy seam:** RE1 lead `0x352e0`. It is called for every planet before the race/player automation discrimination.
- **Narrowed:** `0x34e70` is important changed planet-cluster code, but on this path it is downstream recalculation/state refresh rather than the self-management entry gate.
- **Not established:** a distinct player-only policy implementation. Static flow instead shows player and non-player planets converging on the same policy candidate after different gate conditions.
- **Not attempted:** full reconstruction of the Antagonizer AI/scoring algorithm. M1 does not require it.

## Minimal RE5 experiment derived from this result

RE5 should wait for RE4 to provide runtime-confirmed manual/automated planets, then instrument only the static boundary established here.

One turn should capture:

1. gate hits around `0x3c0fc` with planet pointer, owner/id `+0x57`, candidate automation value `+0x5a`, current action `+0x54`, and the separate override global;
2. whether the same planet reaches `0x3c118/0x3d8f0`;
3. at least one `0x3df88 -> 0x34b0c` policy-to-mutation call;
4. before/after `+0x52/+0x54` for the selected planet.

Compare an RE4-confirmed manual player planet and automated player planet, both with `+0x54 == 0xff`, and observe a non-player owned planet from the same turn where practical. A second automated player planet with different state is useful but not required for the first falsification.

The experiment should select a run/hit where the separate override global is zero. If it is never zero in the relevant scenario, that becomes a new observation rather than silently treating `+0x5a` as the only gate.

Expected discriminator if the static model is correct:

- manual player planet with `+0x5a == 0` does not enter `0x3d8f0`;
- automated player planet has `+0x5a != 0` and does enter when its current action is empty;
- a non-player owned planet can enter the same `0x3d8f0` path without the player-only `+0x5a` requirement;
- policy output reaches `0x34b0c` and changes the current slot/action state.

This is intentionally a bounded experiment, not a whole-turn trace.

## Result

RE3's acceptance criterion is met statically: there is a falsifiable, cross-product/cross-locale-supported hypothesis for where per-planet player automation state is consumed each turn and how the existing shared management policy reaches action/queue mutation. The register interpretation is backed by direct ABI observations at real call sites.

No runtime behavior is claimed. RE5 owns causal runtime confirmation, and RE4/parallel RE2 own the UI-to-state transition.
