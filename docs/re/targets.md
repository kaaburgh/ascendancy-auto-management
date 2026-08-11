# Target binaries

T1 selected one exact M1 production target and one exact comparison baseline. Later binary-specific work must use these identities unless a later roadmap decision explicitly changes them.

- **Canonical M1 target:** `antagonizer-en` / `ANTAG_EN.EXE`, SHA-256 `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`, 610863 bytes.
- **Canonical comparison baseline:** `bugpatch-en` / `PATCH_EN.EXE`, publisher-documented version 1.6.5, SHA-256 `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`, 587451 bytes.

The reviewed machine-readable T0 captures are in [`target-manifest.json`](./target-manifest.json). Target-selection and build-lineage evidence is in [`../experiments/T1-canonical-target-selection.md`](../experiments/T1-canonical-target-selection.md).

The International Antagonizer and bug-patch binaries remain cross-locale corroboration/future-compatibility candidates; T1 does **not** broaden M1 support to them.

## T0 target-capture policy

Use [`../../tools/inspect_target.py`](../../tools/inspect_target.py) to fingerprint any candidate executable supplied outside git. The tool is deliberately a shallow target-identity inspector, not a disassembler or a general static-analysis pipeline: normalized disassembly, functions, xrefs, strings and binary comparison belong to CF2/T2.

Example:

```sh
python3 tools/inspect_target.py binaries/ANTAG_EN.EXE \
  --id antagonizer-en \
  --label "Antagonizer English canonical M1 target" \
  --output artifacts/antagonizer-en.target.json
```

A capture records:

- SHA-256 and exact file size;
- input filename (basename only) and the caller-supplied label;
- detected container format and architecture when the shallow parser can establish them;
- DOS `MZ` header metadata when present;
- selected Linear Executable (`LE`) header/load metadata when an LE header is present and complete enough to parse;
- positive DOS/4G-family extender-marker evidence when found in the DOS stub;
- inspector name/version and a reproducible command with host directory names removed;
- bounded warnings for partial or malformed headers instead of guessed facts.

For the same bytes and logical invocation, the JSON is deterministic: it contains no timestamp, hostname, absolute input/output path, or environment-specific identifier. Unknown files are still fingerprinted, but their format/architecture remain `unknown`/`null` rather than being inferred from a release name.

When `--output` is used, the inspector refuses to write if the output resolves to the input target, including existing symlink and hardlink aliases. The target file remains read-only input; a metadata capture must never replace the executable it is fingerprinting.

### Stable target IDs and labels

A target `id` is a repository-facing logical identifier supplied with `--id`; it is never inferred from a filename or binary contents. IDs use lowercase letters/digits plus `.`, `_`, and `-` and must match `^[a-z0-9][a-z0-9._-]*$`.

Reuse an established acquisition id when the captured bytes are exactly that candidate. A separately supplied retail executable should receive a new neutral id rather than being called equivalent to a known candidate before evidence establishes that relationship.

A `label` is human context such as a maintainer-reported release or version description. Labels are evidence/provenance annotations, not identity: SHA-256 is the byte identity, and a label must not turn an unverified release claim into a fact.

## Machine-readable manifest

The schema is [`../../tools/target-manifest.schema.json`](../../tools/target-manifest.schema.json). A repository-safe synthetic example is [`target-manifest.example.json`](./target-manifest.example.json), and the reviewed canonical T1 records are [`target-manifest.json`](./target-manifest.json).

The top-level form is:

```json
{
  "schema": 1,
  "targets": [
    {
      "id": "candidate-id",
      "filename": "CANDIDATE.EXE",
      "label": "caller-supplied context",
      "size": 123456,
      "sha256": "...",
      "container": {},
      "capture": {},
      "warnings": []
    }
  ]
}
```

`inspect_target.py` emits a one-target manifest. Reviewed records may be combined into one project manifest without changing their captured identity fields. IDs in such a combined manifest must be unique. Two files with the same SHA-256 are the same byte identity even if filenames differ; do not invent separate compatibility claims from filenames alone.

## Interpretation boundaries

The inspector reports only what its small parser establishes:

- architecture is emitted only for an LE CPU type explicitly recognized by the parser; an unknown CPU type is preserved numerically and leaves architecture `null`;
- LE multi-byte fields are decoded only when the header declares the supported little-endian byte and word ordering (`0/0`). Any other ordering leaves only the LE magic/order bytes recorded, emits a warning, and does not publish CPU/load metadata decoded with the wrong endianness;
- DOS/4G detection is positive-marker evidence from the DOS stub. Absence of a known marker does not establish that no extender is involved. On the canonical pair the T0 manifest has no `extender` field because the shallow stub scan does not find one; CF1 independently established bound DOS/4G-family runtime evidence outside that scan boundary;
- LE offsets/counts are header metadata. T0 does not walk object/page/fixup/import tables and does not claim runtime addresses or selector mappings;
- a filename, label, or matching file size never substitutes for a hash;
- target fingerprints are static evidence about the named bytes, not runtime evidence that the game executes or that any patch behavior works.

The shallow T0 inspector and the deeper CF2 parser intentionally have different scopes. `inspect_target.py` captures stable identity/header metadata for arbitrary inputs; `le_image.py` reconstructs the known LE targets for analysis and is where object/page-layout invariants are enforced.

## Candidate acquisition

CF1 established that all four candidate executables are lawfully fetchable in cloud. Fetch them into the git-ignored `binaries/` with:

```sh
python3 tools/fetch_free_targets.py          # fetch and verify all four
python3 tools/fetch_free_targets.py --list   # show ids, sizes and pinned hashes
python3 tools/fetch_free_targets.py --verify # re-verify without the network
```

| Manifest id | Role | Size | SHA-256 |
| --- | --- | ---: | --- |
| `antagonizer-en` | **Canonical M1 Antagonizer target** | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `bugpatch-en` | **Canonical comparison baseline**, official bug patch 1.6.5 English | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `antagonizer-intl` | International Antagonizer; corroboration/future compatibility | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `bugpatch-intl` | International official bug patch 1.8.5; corroboration/future compatibility | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

Facts that apply to all four, established by CF1/T1 static evidence:

- DOS `MZ` region followed by a Linear Executable (`LE`) image at `e_lfanew = 0x2a50`; **not PE**;
- Intel 80386 LE CPU type under the T0 parser;
- each is a complete standalone game build, not a patcher;
- all four share the same complete bound MZ stub and the same Watcom/DOS runtime fingerprints;
- the English and International families show the same locale-layout delta, and both locale-matched Antagonizer↔bug-patch pairs show the same larger layout/string-anchor transformation. See the T1 experiment for exact values.

Publisher version strings 1.6.5 / 1.8.5 for the bug patches come from CF1's contemporaneous `patch.txt` provenance, not from an embedded LE module version (which is `0` in the T0 captures). The Antagonizer has no publisher-documented version number in the current evidence.

The retail unpatched `ASCEND.EXE` is not freely distributed and is not required as the T1 baseline. It remains an optional historical reference.

## Container facts, corrected and revalidated

The four exact binaries establish:

- DOS `MZ` at file offset 0; Linear Executable (`LE`) header at `e_lfanew = 0x2a50`; not PE.
- Little-endian, LE format level 0, CPU type `0x02` (80386), page size 4096.
- Exactly two objects in each image: object 1 executable code, object 2 writable data; page-map numbers are sequential and every observed page flag is `0x00` (`legal`).
- Open Watcom's enumerated-data-page `page_off` is the 32-bit field at LE-header `+0x80` and is an **absolute file offset**. The old CF2 parser incorrectly treated `impmod_off @ +0x70` as this value.
- `autodata_obj @ +0x94` is `2` in all four files.
- `debug_off @ +0x98` and `debug_len @ +0x9c` are both zero in all four files.
- With the corrected `page_off`, enumerated page data ends **exactly at EOF** in all four files. The earlier `~11 KB trailing unparsed` region was an artifact of using `impmod_off` as an absolute page base.

Per target:

| Target | Code object | Data object base | Pages | Entry VA | `page_off` |
| --- | --- | --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x10000`–`0x82736` | `0x90000` | 126 | `0x783b4` | `0x18000` |
| `ANTAG_INTL` | `0x10000`–`0x827e6` | `0x90000` | 126 | `0x78464` | `0x18000` |
| `PATCH_EN` | `0x10000`–`0x7db46` | `0x80000` | 121 | `0x737c4` | `0x17600` |
| `PATCH_INTL` | `0x10000`–`0x7dbf6` | `0x80000` | 121 | `0x73874` | `0x17600` |

The object-table metadata above is unchanged by the correction and was re-read from the exact target bytes.

### Why `+0x70` was misleading

In all four files `impmod_off @ +0x70` equals `impproc_off @ +0x78`, and `num_impmods == 0`. That observation is real, but it does **not** mean either field aliases page data.

Open Watcom treats the import/fixup table offsets as LE-header-relative; `wdump` adds `New_exe_off` when using them. `page_off` is a separate absolute file offset and is used without that addition. The equal import offsets simply describe empty import tables sharing the same loader-relative position.

The corrected entry mapping is also decisive: all four declared entry points begin with `EB 76`, a short jump over the embedded `WATCOM C/C++32 Run-Time ...` banner into consistent startup code. The old absolute-`+0x70` interpretation mapped the four entries to unrelated byte sequences.

Full evidence, including the re-check of the previous `0x34c0`/`0x895` argument, is in [`../experiments/CF2-wdump-layout-correction.md`](../experiments/CF2-wdump-layout-correction.md).

## Build toolchain identification

Raw-file strings identify **Watcom C/C++32** and **Rational DOS/4G**. With the corrected mapping their virtual addresses are:

| Target | Watcom runtime banner | Ascendancy copyright | `RATIONAL DOS/4G` |
| --- | ---: | ---: | ---: |
| `ANTAG_EN` | `0x783b6` | `0x90895` | `0x9563c` |
| `ANTAG_INTL` | `0x78466` | `0x90895` | `0x9563c` |
| `PATCH_EN` | `0x737c6` | `0x80895` | `0x854bc` |
| `PATCH_INTL` | `0x73876` | `0x80895` | `0x854bc` |

Watcom's default 32-bit convention is register-based (`__watcall`: arguments in EAX/EDX/EBX/ECX), but this project treats that as an **open implication**, not an established calling convention for Ascendancy. RE2/RE3 must make a known-arity call-site check an early explicit step before interpreting arguments; A2/P1 must not design a trampoline around `__watcall` until that evidence exists.

Open Watcom `wdump` is currently a **source-level format oracle** in CF2: its header/linker/dumper source established `page_off` semantics. It has not yet been executed against these four files as an independent target run. T2 owns that concrete cross-check: run `wdump` on all four pinned targets, compare object/page/header values to `le_image.py info --json`, and record any discrepancy before treating the source-level agreement as a tool-output agreement.

## Corrected reconstructed-object fingerprints

| Target | Code object SHA-256 | Data object SHA-256 |
| --- | --- | --- |
| `ANTAG_EN` | `7772d00e6e36d5a2828d43410c59c601ca2149e3dcee33187b53d7a2d278c8e8` | `3bb3ddc418aa5eaceedd2de0cc8d20034b3fa99c3db36181d08de2992e1c4797` |
| `ANTAG_INTL` | `f86803f21c9144f10b02f558ff9b30378812dd497061ef05b31cb1b3e29bde15` | `6397503cf6a093f5a9bb60117e6bc3044395363c46a59c25eb30f1d8167f79fe` |
| `PATCH_EN` | `9a6055067d153af08c40c4d368c339881a2a50f06e3a8c41500a1748737a84a2` | `5eb4889b6c23dff80464e5686fa84a4e1269402b8e3d58070ce3869ec91e3c6a` |
| `PATCH_INTL` | `be79ae2b1e393af4de5b32682432ff4f4664a96531d6f90473a26310b905e4b6` | `4506b1c9c569f0d9c2145e9b49887b1dcce6e42bd962457bcf4856377587fa96` |

Current serialized inventories also embed the reconstructed code-object hash and parser-layout identity, so `le_diff` can reject stale pre-correction JSON rather than trusting only the source EXE hash.

## Regenerated disassembly inventory

| Target | Instructions | Candidate regions | Direct call sites | Branch targets | Call-graph edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ANTAG_EN` | 144696 | 1326 | 7472 | 11059 | 4259 |
| `ANTAG_INTL` | 144691 | 1326 | 7477 | 11018 | 4260 |
| `PATCH_EN` | 139093 | 1297 | 7251 | 10433 | 4162 |
| `PATCH_INTL` | 139129 | 1296 | 7255 | 10448 | 4162 |

These counts are analysis metadata from a linear sweep, not proven function or instruction boundaries. Direct-call-derived starts miss indirect-only callees, which are folded into preceding candidate spans.

## Conservative Antagonizer ↔ patch differential

The current model has four classes and labels only operand-preserving matches identical.

English:

- **72 exact matches** (`50` at different candidate addresses, `22` at the same address);
- **613 reference-only differences** — in-image operands changed; relocation and possible semantic retargets are mixed;
- **525 constant-only differences** — same instruction shape after all hex operands are masked;
- **116 / 87 structural regions** (Antagonizer / patch);
- structural-only matched-byte fraction `0.765115 / 0.798235`;
- 11 Antagonizer-only structural spans exceed 2000 bytes.

International:

- **72 exact matches** (`50` moved, `22` same address);
- **611 reference-only differences**;
- **520 constant-only differences**;
- **123 / 93 structural regions**;
- structural-only matched-byte fraction `0.759166 / 0.792016`;
- 12 Antagonizer-only structural spans exceed 2000 bytes.

The previous post-layout-correction `685 strict` English and `683 strict` international aggregates masked in-image references. They split exactly into `72 exact + 613 reference-only` and `72 exact + 611 reference-only`; constant-only and structural counts are unchanged. The still older `620 / 507 / 115 / 87` English values came from the shifted `+0x70` object stream and are also superseded.

Full metrics, bucket arithmetic, largest regions, locale sanity checks and the clean-checkout regression are in [`../experiments/CF2-real-target-regeneration.md`](../experiments/CF2-real-target-regeneration.md).

## Reading these binaries

The tools preinstalled in the tested cloud image do not lay out the LE container: GNU `objdump` reports `file format not recognized` and `file` only classifies it. The repository keeps a small fail-closed reader and hands reconstructed flat objects to GNU `objdump`:

```sh
python3 tools/le_image.py info binaries/ANTAG_EN.EXE
python3 tools/le_image.py strings binaries/ANTAG_EN.EXE
python3 tools/le_disasm.py binaries/ANTAG_EN.EXE --summary
python3 tools/le_diff.py binaries/ANTAG_EN.EXE binaries/PATCH_EN.EXE --summary
```

`verify --anchor ADDRESS=TEXT` is an optional content check for a **known, independently pinned** VA. It never selects between header layouts. An address learned from this parser's own mapping is circular evidence and must not be used to validate that mapping; see the general rule in [`../agent-playbook.md`](../agent-playbook.md).

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not a CF2 cloud dependency. It is an optional additional reference.

Provenance, source archives and complete hashes are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

## Canonical M1 target — English Antagonizer

- Role: production target for M1 and all target-runtime validation unless superseded by roadmap evidence.
- Manifest id: `antagonizer-en`.
- Filename: `ANTAG_EN.EXE` (acquisition/capture filename; runtime distribution may name it `ANTAG.EXE`).
- SHA-256: `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00`.
- File size: 610863 bytes.
- Detected format: DOS `MZ` + Linear Executable (`LE`), secondary header offset `0x2a50`.
- Architecture: `x86 (Intel 80386)` from LE CPU type 2.
- Extender evidence: CF1 static evidence establishes bound DOS/4G-family runtime strings; the T0 stub-only detector intentionally emits no extender field for this file.
- Capture tool/version: `inspect_target.py` 1.0.0.
- Capture manifest: [`target-manifest.json`](./target-manifest.json).
- Provenance: The Logic Factory's freely distributed English Antagonizer release; CF1 records two independent archive mirrors containing byte-identical executable payloads.
- Relationship to comparison build: directly comparable build lineage is **strongly supported**, not proven to an identical source-control revision. Cross-locale object-layout and unique-string displacement evidence reproduces the same Antagonizer↔bug-patch transformation in both English and International pairs.
- Supported by current patch: no patch exists yet; this is the binary later patch tasks must support first.

## Canonical comparison baseline — English official bug patch 1.6.5

- Role: canonical vanilla-lineage comparison baseline for T2/RE1; not the production mod target.
- Manifest id: `bugpatch-en`.
- Filename: `PATCH_EN.EXE` in the acquisition set / `PATCH.EXE` in the publisher archive.
- SHA-256: `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b`.
- File size: 587451 bytes.
- Detected format: DOS `MZ` + Linear Executable (`LE`), secondary header offset `0x2a50`.
- Architecture: `x86 (Intel 80386)` from LE CPU type 2.
- Extender evidence: same boundary as the canonical target; CF1 supplies the bound DOS/4G-family evidence.
- Capture tool/version: `inspect_target.py` 1.0.0.
- Capture manifest: [`target-manifest.json`](./target-manifest.json).
- Provenance/version: official The Logic Factory English bug-patch standalone executable; publisher documentation identifies it as version 1.6.5.
- Relationship to production target: same-language comparison pair with directly comparable lineage strongly supported by T1's cross-locale structural evidence.
- Supported by current patch: no; comparison reference only.

## RE1 constraint from T1

Comparable lineage is strong enough to justify a normalized whole-image differential as a candidate-ranking tool, but it does **not** prove every difference is Antagonizer AI behavior. RE1 must keep unrelated bug-fix/configuration drift as a confound.

Prefer candidate changes that either:

- reproduce in the International Antagonizer↔bug-patch comparison; or
- have independent semantic evidence from strings, call/data relationships, UI/state proximity, or later runtime validation.

A change present in only one locale needs an explanation before it is promoted as Antagonizer-specific behavior.

Do not commit proprietary executables or copyrighted game assets themselves.
