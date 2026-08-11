# CF1 — Cloud access to the target executables

- Roadmap item: CF1
- Date: 2026-08-11
- Target SHA-256: n/a at start; hashes established by this experiment are listed below
- Evidence category: **runtime** for cloud-environment reachability and download behavior (observed in this cloud sandbox); **static** for the file-format and hash facts about the acquired executables; **reported** for publisher distribution intent (contemporaneous vendor documentation and Usenet announcement)
- Tool/build: `curl 8.x`, Python 3.11.15, `tools/fetch_free_targets.py` (this PR)

## Question

Can a clean Codex or Claude cloud environment obtain the exact Antagonizer target and a vanilla reference in a lawful, reproducible way without committing proprietary binaries to this repository?

## Competing hypotheses

- **H1** — No cloud path exists; every target byte must come from the maintainer's machine, so T1/T2/RE1 become `LOCAL ONLY`.
- **H2** — Only a maintainer-generated derivative bundle (hashes, disassembly excerpts) can reach the cloud.
- **H3** — Some target bytes are lawfully and directly fetchable in cloud because the publisher distributed them free of charge.
- **H4** — Everything needed, including the retail game data, is fetchable in cloud.

## What the target actually is

This was the decisive discovery, and it changes the shape of the whole track.

The Antagonizer is **not** an in-place patcher and not a data file. Its bundled `README.TXT` says:

> To use the Antagonizer, just copy ANTAG.EXE into the directory in
> which you installed Ascendancy (ASCEND by default).  Type ANTAG to
> run the Antagonizer version.  As always, type ASCEND to run the normal
> version.

The official bug patch works the same way. Its bundled `patch.txt` says:

> If you're playing the English version of Ascendancy, use the file
> PATCH.EXE. Just copy it into the directory you installed Ascendancy to,
> and then type "patch" to run Ascendancy. If it causes problems, make sure
> you have the right version by typing "patch v": the version displayed should
> be 1.6.5.

So both free downloads are **complete standalone game executables** that sit beside the retail `ASCEND.EXE` and read the retail data files. That splits the acquisition problem cleanly in two:

- the **executable** — the only thing static reverse engineering needs — was published free by the rights holder;
- the **retail game data** — needed only to actually *run* the game — was not.

### Structural confirmation (static)

All four acquired executables are DOS `MZ` stubs with a Linear Executable image and a bound DOS/4G extender, carrying the game's own copyright banner. Observed with a header/string probe:

| File | Size | `e_lfanew` | Signature | Banner |
| --- | --- | --- | --- | --- |
| `ANTAG_EN.EXE` | 610863 | `0x2a50` | `LE` | `Ascendancy\nCopyright (c) 1995 The Logic Factory, Inc.` |
| `ANTAG_INTL.EXE` | 610863 | `0x2a50` | `LE` | same |
| `PATCH_EN.EXE` | 587451 | `0x2a50` | `LE` | same |
| `PATCH_INTL.EXE` | 587451 | `0x2a50` | `LE` | same |

`DOS/4G` appears at `0x090645` in the Antagonizer images and `0x08aac5` in the bug-patch images.

This is deliberately shallow. Establishing the load layout, extender behavior, and section map is T0/T1/T2 work, not CF1's.

## Distribution provenance (reported)

The publisher released both downloads free of charge. Todd Templeman of The Logic Factory announced the Antagonizer on `comp.sys.ibm.pc.games.strategic` on 1995-11-21:

> the Antagonizer AI module is completed. Just go to our web site and download it (http://www.logicfactory.com).

The announcement states the module was free to customers, that there are two versions (English and foreign language), and that the bug patch was also available from the same site. The announcement also explicitly invited redistribution help ("try posting it elsewhere on the internet, compuserve etc.").

`logicfactory.com` no longer serves this content — as of this experiment it is a parked domain listed for sale via `spaceship.com`. The surviving copies used here are hosted on the Internet Archive under the `classicpcgames` collection, credited to The Logic Factory.

The DOS game itself is not sold digitally on any current storefront, so a maintainer wanting to *run* the game needs their own retail copy. That is a constraint on CF3/CF4, not on CF1.

## Procedure

1. Probed cloud egress from this sandbox with `curl` against candidate hosts.
2. Fetched `https://archive.org/metadata/<item>` for four items and recorded the publisher-independent per-file `sha1`/`md5` that the Archive publishes.
3. Downloaded all six candidate archives and computed `sha256`/`sha1`/`md5`.
4. Compared each downloaded archive's `sha1` against the Archive's published metadata.
5. Enumerated every zip member with its size, CRC-32, timestamp, and `sha256`.
6. Cross-compared the inner executables across independently uploaded Archive items.
7. Implemented `tools/fetch_free_targets.py` plus the pinned manifest, then ran fetch and verify end to end.

## Result

### Cloud egress (runtime, this sandbox)

| Host | Result |
| --- | --- |
| `archive.org` (metadata + download) | `200` |
| `dn721609.ca.archive.org`, `ia801604.us.archive.org` (redirect targets) | `200` |
| `web.archive.org` | connection reset — **blocked by egress policy** |
| `logicfactory.com` | `200` (parked domain, no content) |

`archive.org/download/...` answers with a cross-host redirect to a per-node
`dn*.*.archive.org` or `ia*.us.archive.org` server, so an environment allowlist
must cover `*.archive.org`, not just the apex. `web.archive.org` being blocked
while `archive.org` is reachable means a Wayback-based fallback is **not**
available here; do not write tooling that depends on it without re-probing.

### Acquired artifacts

Every downloaded archive's SHA-1 matched the Archive's own published metadata. Sizes and SHA-256 as observed:

| Item / archive | Archive SHA-256 | Member | Member size | Member SHA-256 |
| --- | --- | --- | --- | --- |
| `antag/antag.zip` | `c7c15113f8d839b9b73df33f14211967bfe6b1494218ff2f780a7c8108afd076` | `ANTAG.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `ANTAG_ZIP/ANTAG.ZIP` | `ff0c59ab4de584b8f7f599ae26dc35337b923dde507da8568cea2e3c7531e932` | `ANTAG.EXE` | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `antag/f_antag.zip` | `11852930d99739633b1d50e906af901436e3731533b51fc5dafbe3f7d293a2c2` | `F_ANTAG.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `ANTAG_F_ZIP/ANTAG_F.ZIP` | `152bdba3341bcd422a2cf9ea8ae3737d563d80d9bdd61362146668bd7b71add9` | `ANTAG.EXE` | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `f_ascpat/ascpatch.zip` | `bf6a928166952e19a7a87da094f7b680fec19052a0b13ad4e46e34417d917596` | `patch.exe` | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `f_ascpat/f_ascpat.zip` | `56ad8a1b5f7b0620ff8ec36a64cd43fe548daabe480e5b8cbe96e773ca1f2a39` | `F_PATCH.EXE` | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

Two findings worth carrying forward:

1. **Independent corroboration.** Two separately uploaded Archive items (2014 and 2019, different uploaders, different outer zip hashes, and in one case a different member *name*) contain **byte-identical** Antagonizer executables. That is meaningful redundancy: a single tampered or mis-uploaded item cannot silently become the project's target.
2. **Same-day build pairing for the non-English lineage.** Zip member timestamps put `F_PATCH.EXE` at 1995-11-20 17:09:06 and `F_ANTAG.EXE` at 1995-11-20 17:56:42 — 47 minutes apart. The English `ANTAG.EXE` is 1995-11-20 16:51:20 while the English `patch.exe` is 1996-01-25 12:54:10, roughly two months later. If a differential baseline is wanted where non-AI changes are minimised, the non-English pair looks closer, but zip timestamps are weak evidence of build provenance and this must not be treated as established. It is an input to T1's target-selection decision, not a decision.

### Tooling

`tools/fetch_free_targets.py` reads `tools/free-target-sources.json` and, per entry, tries each pinned source until one fully verifies:

- rejects a response longer than the pinned archive size while still streaming;
- requires exact archive size and SHA-256 before opening the zip;
- extracts exactly one unambiguously named member, rejecting case-insensitive collisions instead of picking one;
- requires exact member size and SHA-256;
- writes through a `.part` file and renames only after verification, so a failure leaves no output;
- refuses to overwrite an existing output whose hash differs, unless `--force`;
- refuses a destination inside the repository that is not under a git-ignored root, so target bytes cannot be committed by accident;
- has no URL override: adding a source means a reviewable manifest edit.

Verified in this sandbox:

```text
$ python3 tools/fetch_free_targets.py
fetched antagonizer-en:   binaries/ANTAG_EN.EXE   from https://archive.org/download/antag/antag.zip
fetched antagonizer-intl: binaries/ANTAG_INTL.EXE from https://archive.org/download/antag/f_antag.zip
fetched bugpatch-en:      binaries/PATCH_EN.EXE   from https://archive.org/download/f_ascpat/ascpatch.zip
fetched bugpatch-intl:    binaries/PATCH_INTL.EXE from https://archive.org/download/f_ascpat/f_ascpat.zip
4 of 4 entries verified.

$ python3 tools/fetch_free_targets.py --verify
4 of 4 entries verified.
```

A manifest restricted to each entry's *second* source was also run, and both Antagonizer mirrors produced the same pinned member hash, so the fallback path is exercised against reality and not only against fixtures.

`tests/test_fetch_free_targets.py` covers the logic with 40 stdlib-`unittest`
tests over synthetic zip fixtures served via `file://`, so CI needs no network
and no proprietary bytes: happy path, idempotence, mirror fallback, mirror
repackaging under a different member name, and fail-closed behavior for archive
hash/size mismatch, oversized response, member hash/size mismatch, missing
member, ambiguous member, corrupt archive, unreachable source, tampered or
missing output under `--verify`, existing mismatched output, malformed manifests,
output path traversal, and unsafe destinations.

## Interpretation

**H3 is supported. H1 and H2 are rejected for the executable; H4 is rejected for the game data.**

- The Antagonizer production target **is** directly obtainable in cloud, hash-pinned, from two independent mirrors.
- A vanilla-lineage reference **is** directly obtainable in cloud: the publisher's official bug-patch executable, a complete game binary carrying a publisher-documented version string (1.6.5 English / 1.8.5 non-English).
- The **retail unpatched `ASCEND.EXE`** is not freely distributed and is not in cloud. It is a *nice-to-have* third reference, not a prerequisite: the diff RE1 actually wants is Antagonizer ↔ same-lineage non-Antagonizer build, and the bug-patch executable serves that role.
- The **retail game data files** are not obtainable in cloud, and the repository must not try. Every task needing them is a runtime task already owned by CF3/CF4.

### Deliberately not done

- No proprietary or restricted bytes were added to git. `binaries/` is git-ignored (`git check-ignore` confirms `/binaries/`) and the four executables exist only in the ephemeral sandbox.
- No abandonware full-game source was used, and none may be added to the manifest. `myabandonware.com` was reachable from this sandbox; that is a capability, not a permission.
- No target-metadata capture tool was written: that is T0, and duplicating it here would pre-empt it.
- No canonical target was *selected* and `docs/re/targets.md` was left without canonical entries: choosing the M1 target is T1's decision, and this record supplies the provenance it needs.

## Artifacts

Local only, under the git-ignored `binaries/`: `ANTAG_EN.EXE`, `ANTAG_INTL.EXE`, `PATCH_EN.EXE`, `PATCH_INTL.EXE`. Regenerate with `python3 tools/fetch_free_targets.py`; nothing needs to be preserved between sessions.

## Local handoff contract (only for what cloud cannot get)

Cloud acquisition covers static RE completely, so the handoff surface is small. A maintainer-side export is needed **only** for:

1. **Retail `ASCEND.EXE` fingerprint** — optional. Wanted only if a task must compare against the shipped retail build rather than the official bug-patch build. Deliverable: metadata only (SHA-256, size, filename, version label, header facts), never the file. The tool that produces this record is T0's deliverable; T1 consumes it.
2. **A runnable game installation** — required for RE4, RE5, P2, V1. Deliverable and mechanism are CF3/CF4's to define, because they depend on whether the emulator runs in cloud at all. CF1's contribution is the constraint: the free executables are enough to *analyse*, never enough to *run*.

Constraints that apply to any such export: repo-safe metadata and bounded logs only; no game data files, no copyrighted assets, no full executables committed to git; raw material stays under the ignored `artifacts/`, `captures/`, `binaries/`, `reference/`, `game/` roots.

## Requirements for a clean cloud environment

- HTTPS egress to `archive.org` **and** `*.archive.org` (download redirects to per-node hosts). No other host is required.
- Python 3.11+ with the standard library only. No third-party packages, no `pip install`.
- Roughly 3 MB of writable space for `binaries/`.
- If egress is denied, the tool fails closed with the per-source reason and writes nothing; the fallback is then the local handoff contract above.

## Updated model / next question

CF1's blocking role is discharged: the sequence `T1 → T2 → RE1 → RE2/RE3` no longer needs maintainer-supplied bytes. The remaining gate on that path is CF2 (a headless static-analysis toolchain), which is now the highest-information next task — and it can use real target bytes rather than the synthetic fixtures its description allowed for.

The open question CF1 cannot answer: whether the game can be *executed* in cloud at all, given that the retail data files are unobtainable there. That is CF3, and it should treat "cloud has the executables but not the data" as its starting condition.
