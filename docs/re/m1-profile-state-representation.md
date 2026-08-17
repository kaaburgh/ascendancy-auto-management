# M1 per-planet profile state representation

## Decision

For M1, keep the game's confirmed `planet_record+0x5a` dword in its original two-state domain and store the extra profile identity in mod-owned, current-session sidecar state.

The game field remains a compatibility mirror only:

- `0x00000000` — Manual;
- `0xffffffff` — existing Managed/self-management enabled.

The mod-owned profile state distinguishes:

- `Manual`;
- `Agricultural`;
- `Industrial`.

The mapping to the game is deliberately many-to-one:

```text
Manual       -> +0x5a = 0x00000000
Agricultural -> +0x5a = 0xffffffff
Industrial   -> +0x5a = 0xffffffff
```

Agricultural and Industrial therefore retain separate M1 identities while both continue through the already established existing self-management gate and policy path.

Evidence class: architecture decision based on existing `static + runtime` repository evidence. Blind-RE provenance: **clean**. This note adds no new target-runtime claim.

## Why not encode three values directly in `+0x5a`

RE2/RE4 established more than a generic nonzero flag:

- the ordinary M path bitwise-NOTs the entire dword, giving exactly `0 <-> 0xffffffff` in the observed path;
- the existing renderer compares the field exactly with `0xffffffff` before displaying `Self Managed`;
- RE3/RE5 established that the current-player turn gate treats nonzero as automation-enabled, but other consumers of the field have not been exhaustively reconstructed.

Using an extra in-band value for Industrial would therefore require patching or proving every exact-value consumer and the original NOT-based toggle semantics. That increases the M1 patch surface solely to carry a distinction that the original game does not need. Keeping the game field binary preserves the strongest compatibility invariant instead.

## Sidecar identity and fail-closed lookup

The sidecar is session-local and keyed by a validated runtime planet-record identity. The implementation must derive the key from the same `0x7b` planet-record population used by the established UI/turn-path evidence; it must not use a planet name alone as identity.

A concrete implementation may use a record pointer/slot index, but lookup is valid only while all structural checks used to derive that identity still hold. At minimum, the implementation must reject an unaligned/out-of-range record, reject a record that no longer matches the expected planet population, and prevent a stale entry from being transferred to another record after a reset/reload/reinitialization boundary.

A cached pointer or slot number is therefore not self-authenticating state. If the implementation cannot prove that a lookup still addresses the same live planet record, it must discard that sidecar entry and reconstruct a conservative profile from the original game field rather than returning another planet's profile.

The exact discovery/storage mechanism belongs to A2/UI2 because it depends on the selected integration mechanism; A1 fixes the semantic key contract and fallback, not the patch technology.

## Initialization and compatibility fallback

The original game field is authoritative for whether automation is enabled. A missing, stale, corrupt, or otherwise invalid sidecar entry is reconstructed as:

```text
+0x5a == 0x00000000 -> Manual
+0x5a == 0xffffffff -> Agricultural
anything else       -> invalid/unsupported state; fail closed
```

`Agricultural` is the compatibility default for an already-Managed planet because M1 gives Agricultural and Industrial the same existing game behavior. This preserves the pre-mod behavior without pretending that an old Managed state historically carried either new profile identity.

Once the player explicitly selects Industrial, the sidecar retains that identity while the game field remains `0xffffffff`.

The implementation must not silently coerce an unexpected third value of `+0x5a` into either automated profile. Encountering such a value is evidence that an assumption changed or the state is corrupt; the feature must refuse the profile operation for that record rather than widening the accepted target state.

## State transitions and invariants

For every valid sidecar entry:

1. `Manual` implies the compatibility mirror is `0x00000000`.
2. `Agricultural` and `Industrial` both imply the compatibility mirror is `0xffffffff`.
3. A zero compatibility mirror always resolves as Manual, even if stale sidecar bytes claim an automated profile.
4. A Managed mirror with no valid sidecar entry resolves as Agricultural.
5. No sidecar lookup may return a profile for a different planet merely because a pointer, index, or name was reused.
6. Profile changes update sidecar identity and the compatibility mirror as one logical transition; observers must not treat a partially updated pair as a stable state.
7. The sidecar does not alter the established downstream automatic policy/action path for M1.

These rules preserve a direct escape hatch to original Manual behavior: clearing the original Managed field is sufficient to make the effective profile Manual.

## Lifecycle

The sidecar exists only for the running game session. M1 deliberately does not persist it into the save format.

The implementation must clear/invalidate all sidecar state whenever the runtime planet-record population is reinitialized or when it cannot prove continuity with the population for which the entries were created. New or previously unseen planets initialize from the compatibility mirror using the fallback above.

Because save/load persistence is outside M1, losing the Agricultural/Industrial distinction across a load boundary is expected. A later persistence design may serialize only the mod-owned profile identity while retaining this same binary compatibility mirror.

## Alternatives considered

### Three-value enum in `+0x5a`

Rejected for M1. It is compact, but conflicts with the confirmed exact-`0xffffffff` renderer check and the NOT-based original toggle, and it would require proving or patching unknown consumers.

### Spare bits in another game-owned field

Rejected without further evidence. No collision-free spare field/bit with appropriate lifetime has been established, so using one would convert an architecture choice into an unsupported target assumption.

### Sidecar keyed only by planet name

Rejected. Names are presentation data, not an established unique lifetime identity, and name reuse must not leak one planet's profile to another.

## Consequences for downstream work

- **A2** must choose an integration mechanism that can hold bounded session-local sidecar state and validate planet-record identity without changing save files.
- **UI1** may choose the interaction independently, but every transition must preserve the binary mirror invariant above.
- **UI2** owns the tested state machine/lookup implementation. Its synthetic coverage must include mode mapping, independent planets, invalid sidecar entries, invalid `+0x5a` values, identity reuse/invalidation, and session reset.
- **P1/P2** do not need to teach the original AI about Agricultural versus Industrial; they only need to preserve the existing Managed path while making mod-owned identity available to UI/state code.
- **V1** must verify two different planets retain different sidecar profile identities during the running session while both automated profiles still exercise existing self-management, and that returning one planet to Manual clears the effective automation state.

## Decision boundary

A1 chooses where M1 profile identity lives and how it maps to the confirmed game state. It does **not** choose the patch/loader mechanism, memory-allocation technique, selector UI, save persistence format, or differentiated policy logic.
