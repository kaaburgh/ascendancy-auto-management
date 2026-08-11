# Target binaries

No canonical target binary has been **selected** yet. That selection is roadmap item T1.

This is an intentional project constraint, not missing documentation: the first roadmap phase is to choose the exact vanilla/official-patch/Antagonizer baseline.

Do not publish or apply version-specific offsets or machine-code patches until this file records the exact target.

## Candidates available to cloud agents

CF1 established that the candidate executables are lawfully fetchable in cloud, so an agent does **not** need to wait for a maintainer handoff to do static analysis. Fetch them into the git-ignored `binaries/` with:

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

Facts that apply to all four (static, this hash set):

- DOS `MZ` stub at offset 0; Linear Executable (`LE`) image at `e_lfanew = 0x2a50`; bound DOS/4G extender. **Not PE** — tooling that assumes PE will not work.
- Each is a **complete standalone game build**, not a patcher. The Antagonizer and the bug patch are alternatives to the retail `ASCEND.EXE`, run in its place from the same installed directory.
- Version strings 1.6.5 / 1.8.5 for the bug patches are the publisher's own documented values (`patch.txt`), not measured from the binaries. The Antagonizer has no publisher-documented version string.

The retail unpatched `ASCEND.EXE` is **not** freely distributed and is not available in cloud. It is an optional additional reference; if it is ever needed, only its metadata should be handed off, never the file.

Provenance, egress requirements and the full hash table including the source archives are in [`../experiments/CF1-cloud-target-access.md`](../experiments/CF1-cloud-target-access.md).

## Canonical entries

Pending T1.

For each supported binary, record at least:

```markdown
## <label>

- Filename:
- Architecture:
- SHA-256:
- File size:
- PE timestamp:
- Image base:
- Provenance/version notes:
- Relationship to vanilla/reference build:
- Supported by current patch: yes/no
```

Do not commit the proprietary executable itself.
