# M1 per-planet profile state representation

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

## Preserve the separate override condition

`+0x5a` is not an unconditional statement that the target will or will not enter automatic policy. RE3 established the player-side gate as the known relationship:

```text
(+0x5a != 0 OR separate_override != 0)
AND +0x54 == 0xff
-> existing automatic-policy candidate
```

RE5 observed the separate override as zero throughout two bounded, normally progressing Manual windows in the pinned M1 scenario. Its broader semantics remain unknown.

Accordingly, A1 uses `+0x5a` only as the original profile compatibility mirror. `Manual -> 0` means the mod restores the ordinary Manual field value; it does **not** authorize downstream code or validation to claim that automatic policy is impossible in every untested override context. A2/UI2/V1 must preserve or observe the existing override behavior rather than patching it away as an implementation shortcut.

## Why not encode three values directly in `+0x5a`

RE2/RE4 established more than a generic nonzero flag:

- the ordinary M path bitwise-NOTs the entire dword, giving exactly `0 <-> 0xffffffff` in the observed path;
- the existing renderer compares the field exactly with `0xffffffff` before displaying `Self Managed`;
- RE3/RE5 established a nonzero test on the player-side turn gate, while other consumers of the field have not been exhaustively reconstructed.

Using an extra in-band value for Industrial would therefore require patching or proving every exact-value consumer and the original NOT-based toggle semantics. That increases the M1 patch surface solely to carry a distinction that the original game does not need. Keeping the game field binary preserves the strongest compatibility invariant instead.

## Unresolved sidecar identity / lifetime question

The sidecar requires a reuse-safe identity for one live planet record over the intended current-session lifetime. Existing evidence establishes a `0x7b` planet-record population and runtime pointers/selection relationships, but it does **not** establish that a record pointer or slot index can never be reused for a different logical planet without an independently detectable epoch/reset.

Therefore neither a raw record pointer nor a slot index is accepted as the finished A1 key merely because it is aligned, in range, or currently names a valid record. Those structural checks do not exclude this failure mode:

1. planet A occupies a valid slot and receives `Industrial` in the sidecar;
2. the target later reuses the same valid slot for planet B without a detected whole-population reset;
3. pointer/index/range checks still pass;
4. planet B incorrectly inherits planet A's profile.

A1 must close that ambiguity before completion. The next bounded investigation must establish at least one of:

- an evidence-backed epoch/generation boundary that invalidates all sidecar entries before slot reuse is possible;
- an immutable or reuse-detecting per-record identity available in the supported runtime state;
- another equivalent key/lifecycle contract that makes stale-profile transfer fail closed.

If none can be established cheaply, A1 must revisit the sidecar choice rather than delegating an invented key to A2/UI2.

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

Again, these rules resolve **profile identity**, not the separate override condition described above.

## State invariants already fixed by A1

For any future valid sidecar entry:

1. `Manual` implies the compatibility mirror is `0x00000000`.
2. `Agricultural` and `Industrial` both imply the compatibility mirror is `0xffffffff`.
3. A zero compatibility mirror resolves the mod profile as Manual, even if stale sidecar bytes claim an automated profile.
4. A Managed mirror with no valid sidecar entry resolves the mod profile as Agricultural.
5. No lookup may return a profile for a different logical planet because a pointer, index, or presentation name was reused.
6. Profile changes update sidecar identity and the compatibility mirror as one logical transition; observers must not treat a partially updated pair as stable state.
7. The sidecar does not replace, bypass, or reinterpret the established target override condition or downstream automatic policy/action path.

## Lifecycle requirement still to close

The sidecar is intended to exist only for the running game session. M1 deliberately does not require persistence of Agricultural/Industrial identity into the save format.

However, "current session" is not itself an evidence-backed invalidation rule. A1 still needs a concrete observable boundary or immutable/reuse-detecting identity that tells the implementation when entries cease to belong to the same logical planets. Until that is established, A2/UI2 must not invent a convenient reset heuristic and A1 must remain open/investigatory.

A later persistence design may serialize only the mod-owned profile identity while retaining this same binary compatibility mirror, provided it has its own versioning and identity contract.

## Alternatives considered

### Three-value enum in `+0x5a`

Rejected for M1. It is compact, but conflicts with the confirmed exact-`0xffffffff` renderer check and the NOT-based original toggle, and it would require proving or patching unknown consumers.

### Spare bits in another game-owned field

Rejected without further evidence. No collision-free spare field/bit with appropriate lifetime has been established, so using one would convert an architecture choice into an unsupported target assumption.

### Sidecar keyed only by planet name

Rejected. Names are presentation data, not an established immutable lifetime identity, and name reuse must not leak one planet's profile to another.

### Sidecar keyed only by pointer/slot

Not accepted yet. It remains the preferred direction only if the bounded A1 follow-up establishes an epoch or reuse detector that makes stale slot reuse impossible to misclassify.

## Consequences for downstream work

- **A1 follow-up** owns the bounded runtime/static identity-lifetime investigation. It must leave a concrete reuse-safe key/epoch contract or reconsider the sidecar direction.
- **A2** may evaluate mechanisms that can hold bounded session-local sidecar state, but must not treat raw pointer/slot stability as an established A1 fact.
- **UI1** may reason about the three user-visible states, but implementation remains dependent on completed A1 and A2.
- **UI2** will own the tested state-machine/lookup implementation only after A1 supplies the key/lifecycle contract. Its synthetic coverage must include mode mapping, independent planets, invalid sidecar entries, invalid `+0x5a` values, identity reuse/invalidation, session reset, and the override qualification where relevant.
- **P1/P2** do not need to teach the original AI about Agricultural versus Industrial; they must preserve the original Managed path and known override behavior.
- **V1** must verify two different planets retain different profile identities during the intended running-session window, both automated profiles preserve existing self-management behavior, Manual restores the ordinary field value, and the observed scenario remains compatible with the established override assumptions.

## Decision boundary

This A1 slice selects the two-layer representation: original binary compatibility mirror plus mod-owned profile identity. It deliberately does **not** claim A1 completion until the sidecar's reuse-safe identity/lifetime rule is evidenced. It also does not choose the patch/loader mechanism, memory-allocation technique, selector UI, save-persistence format, or differentiated policy logic.
