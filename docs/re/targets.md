# Target binaries

No canonical target binary has been **selected** yet. That selection is roadmap item T1.

This is an intentional project constraint, not missing documentation: T0 defines how target identities are captured; T1 uses that contract to select the exact Antagonizer production target and comparison baseline.

Do not publish or apply version-specific offsets or machine-code patches until this file records the exact target.

## T0 target-capture policy

Use [`../../tools/inspect_target.py`](../../tools/inspect_target.py) to fingerprint any candidate executable supplied outside git. The tool is deliberately a shallow target-identity inspector, not a disassembler or a general static-analysis pipeline: normalized disassembly, functions, xrefs, strings and binary comparison belong to CF2/T2.

Example:

```sh
python3 tools/inspect_target.py binaries/ANTAG_EN.EXE \
  --id antagonizer-en \
  --label "Antagonizer English candidate" \
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

Reuse an established acquisition id when the captured bytes are exactly that candidate, for example the CF1 ids below. A separately supplied retail executable should receive a new neutral id rather than being called equivalent to a known candidate before evidence establishes that relationship.

A `label` is human context such as a maintainer-reported release or version description. Labels are evidence/provenance annotations, not identity: SHA-256 is the byte identity, and a label must not turn an unverified release claim into a fact.

## Machine-readable manifest

The schema is [`../../tools/target-manifest.schema.json`](../../tools/target-manifest.schema.json). A repository-safe synthetic example is [`target-manifest.example.json`](./target-manifest.example.json).

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

`inspect_target.py` emits a one-target manifest. A later task may combine reviewed target records into one project manifest without changing their captured identity fields. IDs in such a combined manifest must be unique. Two files with the same SHA-256 are the same byte identity even if filenames differ; do not invent separate compatibility claims from filenames alone.

T1 owns creation/population of the canonical target manifest and canonical entries below. T0 intentionally does not select a production target or comparison baseline.

## Interpretation boundaries

The inspector reports only what its small parser establishes:

- architecture is emitted only for an LE CPU type explicitly recognized by the parser; an unknown CPU type is preserved numerically and leaves architecture `null`;
- LE multi-byte fields are decoded only when the header declares the supported little-endian byte and word ordering (`0/0`). Any other ordering leaves only the LE magic/order bytes recorded, emits a warning, and does not publish CPU/load metadata decoded with the wrong endianness;
- DOS/4G detection is positive-marker evidence from the DOS stub. Absence of a known marker does not establish that no extender is involved;
- LE offsets/counts are header metadata. The tool does not walk object/page/fixup/import tables and does not claim runtime addresses or selector mappings;
- a filename, label, or matching file size never substitutes for a hash;
- target fingerprints are static evidence about the named bytes, not runtime evidence that the game executes or that any patch behavior works.

## Candidates available to cloud agents

CF1 established that the candidate executables are lawfully fetchable in cloud, so an agent does **not** need to wait for a maintainer handoff to fingerprint them or perform later static analysis. Fetch them into the git-ignored `binaries/` with:

```sh
python3 tools/fetch_free_targets.py          # fetch and verify all four
python3 tools/fetch_free_targets.py --list   # show ids, sizes and pinned hashes
python3 tools/fetch_free_targets.py --verify # re-verify without the network
```

| Manifest id | Role | Size | SHA-256 |
| --- | --- | --- | --- |
| `antagonizer-en` | Antagonizer AI module, English | 610863 | `8d91e89e978a4e39970f30b790c9c55adde59079c6108a34cdd286882e117b00` |
| `antagonizer-intl` | Antagonizer AI module, non-English | 610863 | `9d44b1cafe9181b3bb526afb6daa2cc0cbb7c5c30fce5172f9a8a9e0b54dce0c` |
| `bugpatch-en` | Official bug patch, version 1.6.5, English | 587451 | `7c944866875e0eb9030d9de1b2ac54a240981a51b892015fd0d2009ab0b62b1b` |
| `bugpatch-intl` | Official bug patch, version 1.8.5, non-English | 587451 | `16fa81fc68414dfbe92434e2ad92ca41ec1e02346cbe874b7e53aa8fb6b4455b` |

Facts that apply to all four (static, this hash set, established by CF1):

- DOS `MZ` stub at offset 0; Linear Executable (`LE`) image at `e_lfanew = 0x2a50`; bound DOS/4G extender. **Not PE** — tooling that assumes PE will not work.
- Each is a **complete standalone game build**, not a patcher. The Antagonizer and the bug patch are alternatives to the retail `ASCEND.EXE`, run in its place from the same installed directory.
- Version strings 1.6.5 / 1.8.5 for the bug patches are the publisher's own documented values (`patch.txt`), not measured from the binaries. The Antagonizer has no publisher-documented version string.

These are candidate identities, not a T1 canonical-target decision.

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not available in cloud. It is an optional additional reference; if it is ever needed, only its metadata should be handed off, never the file.

Provenance, egress requirements and the full hash table including the source archives are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

## Canonical entries

Pending T1.

For each canonical/supported binary, record at least:

```markdown
## <label>

- Role:
- Filename:
- SHA-256:
- File size:
- Detected format:
- Architecture:
- Extender evidence:
- Capture tool/version:
- Capture manifest/artifact:
- Provenance/version evidence:
- Relationship to comparison build:
- Supported by current patch: yes/no
```

Do not commit proprietary executables or copyrighted game assets themselves.
