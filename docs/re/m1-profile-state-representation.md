# M1 per-planet profile state representation

## Targets

- `ANTAG_EN.EXE` — canonical M1 Antagonizer target, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.

The target-specific state facts below are inherited only from the supported evidence for this exact binary: [`auto-management-ui-state.md`](./auto-management-ui-state.md) for the `+0x5a` toggle/renderer seam and [`auto-management-turn-path.md`](./auto-management-turn-path.md) for the owner gate, `0x7b` record stride, override witness, and per-turn path.

## Decision status

A1 has one architecture direction selected but is **not complete yet**.

For M1, keep the game's confirmed `planet_record+0x5a` dword in its original two-state domain and store the extra profile identity in mod-owned, current-session sidecar state. This settles the representation split, but current repository evidence does not yet establish a reuse-safe runtime key/epoch for the sidecar. A1 therefore remains investigatory until that identity/lifetime question is closed with supported evidence.

The game field remains a profile compatibility mirror:

- `0x00000000` — Manual profile intent;
- `0xffffffff` — existing Managed/self-management profile intent.

The mod-owned profile state distinguishes:

- `Manual`;
- `Agricultural`;
- `Industrial`.

The mapping to the game field is deliberately many-to-one:

```text
Manual       -> +0x5a = 0x00000000
Agricultural -> +0x5a = 0xffffffff
Industrial   -> +0x5a = 0xffffffff
```

Agricultural and Industrial therefore retain separate M1 identities while preserving the established Managed-side compatibility condition.

Evidence class: architecture decision based on existing `static + runtime` repository evidence. Blind-RE provenance: **clean**. This note adds no new target-runtime claim.

## Preserve the owner and separate-override gates

`+0x5a` is not an unconditional statement that the target will or will not enter automatic policy. [`auto-management-turn-path.md`](./auto-management-turn-path.md) establishes two owner-dependent paths:

```text
owner == current player race
AND (+0x5a != 0 OR separate_override != 0)
AND +0x54 == 0xff
-> existing automatic-policy candidate

owner == other race
AND +0x54 == 0xff
-> existing automatic-policy candidate (+0x5a not consulted on this gate)
```

M1 writes profiles only for player-owned planets, so its compatibility mapping concerns the first path. RE5 observed the separate override as zero in every coherent sample across two bounded, normally progressing Manual windows in the pinned M1 scenario. Sampling does not prove the dword stayed zero at every instant between samples, and an unknown indirect writer is not excluded; broader override semantics remain unknown.

Accordingly, A1 uses `+0x5a` only as the original profile compatibility mirror. `Manual -> 0` means the mod restores the ordinary Manual field value; it does **not** authorize downstream code or validation to claim that automatic policy is impossible in every untested override context. A2/UI2/V1 must preserve or observe the existing owner/override behavior rather than patching it away as an implementation shortcut.

## Why not encode three values directly in `+0x5a`

[`auto-management-ui-state.md`](./auto-management-ui-state.md) and the RE4 evidence establish more than a generic nonzero flag:

- the ordinary M path bitwise-NOTs the entire dword, giving exactly `0 <-> 0xffffffff` in the observed path;
- the existing renderer compares the field exactly with `0xffffffff` before displaying `Self Managed`;
- RE3/RE5 establish a nonzero test on the current-player turn gate, while other consumers of the field have not been exhaustively reconstructed.

Using an extra in-band value for Industrial would therefore require patching or proving every exact-value consumer and the original NOT-based toggle semantics. That increases the M1 patch surface solely to carry a distinction that the original game does not need. Keeping the game field binary preserves the strongest compatibility invariant instead.

## Unresolved sidecar identity / lifetime question

The sidecar requires a reuse-safe identity for one live planet record over the intended current-session lifetime. Existing evidence establishes a `0x7b` **record stride** and runtime pointer/selection relationships, but explicitly does **not** establish an array base/count. A slot index is therefore not currently derivable from supported evidence. The evidence also does not establish that a live record pointer can never be reused for a different logical planet without an independently detectable epoch/reset.

Consequently neither a raw record pointer nor a hypothetical slot index is accepted as the finished A1 key merely because it is aligned, in range, or currently names a valid record. Pointer-only structural checks do not exclude this failure mode:

1. planet A occupies a valid record and receives `Industrial` in the sidecar;
2. the target later reuses the same valid address for planet B without a detected population epoch/reset;
3. alignment/range/current-record checks still pass;
4. planet B incorrectly inherits planet A's profile.

A1 must close that ambiguity before completion. Its remaining bounded investigation has two concrete identity questions:

- establish an evidence-backed epoch/generation boundary or immutable/reuse-detecting record identity that invalidates stale entries before pointer reuse can transfer a profile; and
- if a slot-based key remains desirable, first establish an array base/count (or an equivalent independently validated indexing relationship) rather than assuming a slot index from the known stride.

Another equivalent key/lifecycle contract is acceptable if it makes stale-profile transfer fail closed. If none can be established cheaply, A1 must revisit the sidecar choice rather than delegating an invented key to A2/UI2.

Planet name alone is not an acceptable substitute: current evidence establishes it as useful presentation/lookup data, not as an immutable lifetime identity.

## Initialization and compatibility fallback

Once a reuse-safe sidecar key has been established, a missing or invalid sidecar entry derives only the **profile identity** from the original game field:

```text
+0x5a == 0x00000000 -> Manual
+0x5a == 0xffffffff -> Agricultural
anything else       -> invalid/unsupported profile state; fail closed
```

`Agricultural` is the compatibility default for an already-Managed planet because M1 gives Agricultural and Industrial the same existing game behavior. This preserves the pre-mod Managed intent without pretending that an old Managed state historically carried either new profile identity.

Once the player explicitly selects Industrial, valid sidecar state retains that identity while the game field remains `0xffffffff`.

The implementation must not silently coerce an unexpected third value of `+0x5a` into either automated profile. Encountering such a value is evidence that an assumption changed or the state is corrupt; the feature must refuse the profile operation for that record rather than widening the accepted target state.

Again, these rules resolve **profile identity**, not the owner/override conditions described above.

## State invariants already fixed by A1

For any future valid sidecar entry:

1. `Manual` implies the compatibility mirror is `0x00000000`.
2. `Agricultural` and `Industrial` both imply the compatibility mirror is `0xffffffff`.
3. Observing a zero compatibility mirror resolves the mod profile as Manual **and invalidates any automated sidecar identity for that logical record**. This covers an original/unmediated M-path transition that the mod did not perform.
4. After such invalidation, a later observed `0xffffffff` mirror with no new valid sidecar selection resolves as Agricultural; an old Industrial identity must not resurrect merely because the original game toggled the mirror back to Managed.
5. A Managed mirror with no valid sidecar entry resolves as Agricultural.
6. No lookup may return a profile for a different logical planet because a pointer, hypothetical index, or presentation name was reused.
7. Mod-mediated profile changes update sidecar identity and the compatibility mirror as one logical transition; observers must not treat a partially updated pair as stable state.
8. The sidecar does not replace, bypass, or reinterpret the established target owner/override conditions or downstream automatic policy/action path.

These rules deliberately do not require A2 to intercept every original `+0x5a` write merely to keep sidecar state coherent: observing Manual is sufficient to invalidate stale automated identity and fail back to the compatibility default on a later unmanaged-to-Managed round trip.

## Lifecycle requirement still to close

The sidecar is intended to exist only for the running game session. M1 deliberately does not require persistence of Agricultural/Industrial identity into the save format.

However, "current session" is not itself an evidence-backed invalidation rule. **A1 itself** still owns the concrete observable boundary or immutable/reuse-detecting identity that tells the implementation when entries cease to belong to the same logical planets. Until that is established, A2/UI2 must not invent a convenient reset heuristic and A1 must remain open/investigatory.

A later persistence design may serialize only the mod-owned profile identity while retaining this same binary compatibility mirror, provided it has its own versioning and identity contract.

## Alternatives considered

### Three-value enum in `+0x5a`

Rejected for M1. It is compact, but conflicts with the confirmed exact-`0xffffffff` renderer check and the NOT-based original toggle, and it would require proving or patching unknown consumers.

### Spare bits in another game-owned field

Rejected without further evidence. No collision-free spare field/bit with appropriate lifetime has been established, so using one would convert an architecture choice into an unsupported target assumption.

### Sidecar keyed only by planet name

Rejected. Names are presentation data, not an established immutable lifetime identity, and name reuse must not leak one planet's profile to another.

### Sidecar keyed only by pointer/slot

Not accepted yet. A raw pointer remains only a candidate until A1 establishes an epoch or reuse detector. A slot index is a still weaker candidate at present because the supported evidence establishes the `0x7b` stride but not an array base/count from which such an index could be derived.

## Consequences for downstream work

- **A1** owns the remaining bounded runtime/static identity-lifetime investigation. It must leave a concrete reuse-safe key/epoch contract (and any required indexing evidence) or reconsider the sidecar direction before A1 can complete.
- **A2** may evaluate mechanisms that can hold bounded session-local sidecar state, but must not treat raw pointer stability, a slot index, or an inferred array base/count as established A1 facts.
- **UI1** may reason about the three user-visible states, but implementation remains dependent on completed A1 and A2.
- **UI2** will own the tested state-machine/lookup implementation only after A1 supplies the key/lifecycle contract. Its synthetic coverage must include mode mapping, independent planets, invalid sidecar entries, invalid `+0x5a` values, original/unmediated Manual↔Managed mirror transitions, identity reuse/invalidation, session reset, and the owner/override qualification where relevant.
- **P1/P2** do not need to teach the original AI about Agricultural versus Industrial; they must preserve the original Managed path and known owner/override behavior.
- **V1** must verify two different player-owned planets retain different profile identities during the intended running-session window, both automated profiles preserve existing self-management behavior, Manual restores the ordinary field value and invalidates stale automated identity, and the observed scenario remains compatible with the established override assumptions.

## Decision boundary

This A1 slice selects the two-layer representation: original binary compatibility mirror plus mod-owned profile identity. It deliberately does **not** claim A1 completion until the sidecar's reuse-safe identity/lifetime rule is evidenced. It also does not choose the patch/loader mechanism, memory-allocation technique, selector UI, save-persistence format, or differentiated policy logic.
