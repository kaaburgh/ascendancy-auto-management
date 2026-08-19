# A1 — direct managed-field writer inventory

- Roadmap item: **A1 — Design the M1 per-planet profile state representation**
- Tracking issue: **#26**
- Status: **tooling preparation; exact-target run pending**
- Intended evidence class after exact-target execution: **static**
- Blind-RE provenance: **clean**
- Canonical target: `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`

## Question

A1 requires a **lossless Manual-transition invalidation boundary**. A sidecar entry carrying `Industrial` cannot survive an original-game `Managed -> Manual -> Managed` round trip unless every transition to Manual is intercepted or an independently established equivalent event invalidates the entry.

Supported RE2/RE4 evidence already establishes two writes to `planet_record+0x5a` on the canonical build:

- `0x22421`: initializer-shaped zero write;
- `0x3791f`: ordinary plain-M NOT/write toggle.

It also establishes direct reads/consults at `0x35473`, `0x356cc`, `0x37915`, and `0x3afca`.

This bounded probe asks a narrower question: **which directly decoded object-relative `+0x5a` references and potential writes are visible in a full linear disassembly of canonical code object 1, and do the established RE2 sites still appear under that independent inventory?**

## Method

`scripts/probe_a1_managed_field_writers.py`:

1. fail-closes on the exact canonical target size/SHA-256;
2. reconstructs code object 1 through the existing LE parser;
3. invokes GNU `objdump` over the full flat i386 code object at its LE virtual base;
4. records decoded instructions with a direct `0x5a(%reg)` operand;
5. classifies an instruction as a **potential write** only when that field operand is the decoded destination and the mnemonic is not one of the explicitly read-only comparison/address forms;
6. requires every established RE2 reference site to be rediscovered and requires `0x22421` / `0x3791f` to classify as potential writes;
7. emits a detached JSON record with target identity, checkout SHA, material producer/parser hashes, tool identity, all direct decoded references, potential-write leads, and explicit coverage limitations.

The companion workflow `.github/workflows/a1-managed-field-writers.yml` is manual `workflow_dispatch`. Exact-target acquisition is evidence production, not ordinary PR correctness CI. It uploads only the derived JSON record; no executable bytes are committed or uploaded.

## Evidence boundary

This inventory is intentionally **not an exhaustive writer proof**.

A full linear decode can miss semantically relevant writes reached through computed/indirect addressing, unusual encodings not represented as direct base-plus-`0x5a`, runtime-generated behavior, or code/data ambiguity. Conversely, linear disassembly can decode embedded data as instructions. Therefore even a result containing only the two already-known writes would **not** establish that those are the only possible writers.

The machine-readable result permanently keeps:

- `status: incomplete-model`;
- `complete_writer_inventory_established: false`;
- `lossless_manual_transition_invalidation_boundary: unestablished`.

Its value is to generate concrete interception/investigation leads and to falsify the simplest model if additional direct writers exist. A later A1 completion claim still needs independent evidence that the chosen invalidation boundary cannot miss an original transition to Manual.

## Preparation acceptance

This preparation slice is complete when:

- deterministic synthetic tests cover direct write/read classification and fail-closed established-site checks;
- ordinary repository CI is green for the tooling change;
- the manual exact-target workflow is present and pins the dispatched checkout SHA;
- no target-specific writer-count claim is made before that workflow actually executes.

`ROADMAP.md` is not changed by this preparation slice because A1 planning state does not change. The existing identity/lifetime investigation remains active in parallel, and neither this probe nor the planet-array indexing probe by itself completes A1.
