# RE5/T3 runtime data-object mapping boundary

Target: canonical `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`  
Blind-RE provenance: **clean**  
Evidence classes: **static** identity plus **runtime** mapping observations already recorded by RE5/T3.

This note records a boundary in the already-published RE5/T3 runtime mapping. It does not re-derive any committed artifact and does not add a new target run.

## What is directly corroborated

The RE5 v2 witness derives one runtime data-object bias from five disjoint file-backed initialized-data signatures. The highest signature begins at static VA `0x998ba` and spans 15 bytes, so the initialized-signature evidence itself reaches through `0x998c8` inclusive.

The same witness independently cross-checks the bias at stardate data-model VA `0xa2f6c`: that address must resolve to the same host address as the previously established RE2-anchor-relative stardate witness, and the value then advances during both acceptance runs. This varying stardate read is therefore the furthest runtime-corroborated point on the bias path used by the final RE5 witness.

The RE3 override operand is static VA `0xa0d00`, below `0xa2f6c`. Its identity is independently derived from the canonical gate instruction and LE relocation, and the runtime witness samples it through the bias path inside the range already corroborated by the live stardate cross-check. This mapping-boundary correction therefore does **not** weaken the final M1 claim that the identified override dword was observed zero in the two published Manual windows.

## Current-player read is an extrapolation

The current-player id has a separately established static identity at VA `0x104bea`: two code references and their LE relocations target object 2 offset `0x74bea`, which gives `0x104bea` from object-2 static base `0x90000`.

Runtime placement is a different claim. The RE5/T3 runners apply the same data-object bias to `0x104bea`, but no initialized signature or independently cross-checked live field reaches that far. `0x104bea` is `0x61c7e` bytes (400,510 bytes, about 391 KiB) beyond the furthest independently corroborated bias-path point at `0xa2f6c`. The runtime current-player read is therefore an extrapolation of the observed object-2 bias across that uncorroborated span, not a directly corroborated mapping observation.

The existing value oracle is also weakly discriminating: the acceptance runs require the byte read at the extrapolated address to equal `0`. Zero is common in process memory, so `value == 0` by itself cannot distinguish “the mapped address is the intended current-player field and its value is zero” from “the extrapolated address is not the intended field but happens to contain zero.” The earlier short-read ambiguity was separately fixed by fail-closed process-memory reads; this remaining issue is address identity, not read length.

A stronger current-player runtime oracle would need independent evidence at or beyond this address — for example a target run in which a discriminating relationship or varying value validates the extrapolated mapping. No such evidence is inferred here.

## Consequences for existing records

- **RE5:** the load-bearing override operand `0xa0d00` remains below the live stardate cross-check and retains its existing static relocation plus runtime evidence. The extrapolated current-player byte should be treated as an auxiliary coherence check, not as independent support for the override address.
- **T3:** its player id `0` and the classification of owner-`0` planet records as current-player-owned reuse the same extrapolated `0x104bea` mapping and weak zero oracle. The committed T3 observation remains recorded as published, but that ownership interpretation carries this caveat; the artifact is not re-derived or relabeled by this documentation correction.

The completed RE5 and T3 results are not reopened by this note. It makes the evidence boundary explicit so later consumers do not silently promote an extrapolated runtime address to the same confidence as the initialized signatures, the live stardate cross-check, or the relocation-derived override operand.
