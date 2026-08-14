---
name: add-save-fixture
description: Add a saved game to the repository as a declared validation fixture, or promote an existing fixture's runtime properties from unverified to verified. Use when a new .gam save needs to become usable by experiments, when an experiment reports that no fixture satisfies a required role, or when someone asks how saves are pinned in this project.
---

# Adding a save fixture

Saves are declared in `tools/validation-fixtures.json`. A declaration pins the payload by size and SHA-256 and states what the save actually contains, so an experiment can require a fixture by role instead of assuming one.

Read [`docs/re/validation-fixtures.md`](../../../docs/re/validation-fixtures.md) for the requirements a save must meet before it is worth declaring. Do not skip that: a save with one player-owned planet, or with every planet already carrying an action, will be declarable and still useless.

## Add the save

```sh
python scripts/add_validation_fixture.py \
  --save /path/to/resume-multi.gam \
  --id resume-en-multi-planet \
  --role m1-multi-planet \
  --storage repository \
  --repository-path fixtures/saves/resume-multi.gam \
  --player-planet "Alpha I" --player-planet "Beta II" --player-planet "Gamma III" \
  --empty-action-planet "Beta II"
```

Add `--dry-run` first to see the computed entry without copying the payload or writing the declaration.

Choices that matter:

- `--storage repository` commits the payload and requires `--repository-path`; the payload must then be present on every validation run. `--storage operator-supplied` references it by hash only, and it must be provided at run time. Committing is the better default for saves — a fixture living on one machine can be lost while conclusions stay pinned to its hash.
- `--player-planet` must name **every** player-owned planet, once each. The count is derived from these names, and duplicate names are rejected because runtime record lookup requires a unique match.
- `--empty-action-planet` names the planets that start with no current action. Every existing runner asserts that precondition on the planet it observes, so a fixture with none of them cannot be used by those runners.

## Verification is a separate step

A new fixture is written with `evidence: unverified`. It is a legitimate declaration, but no consumer may rely on it: `scripts/validate_validation_fixtures.py` reports the role as **NOT usable**, and `--require-role <role>` fails.

Promoting it is a deliberate second step, after a runtime experiment has observed the declared properties on the exact canonical target and recorded them:

```sh
python scripts/add_validation_fixture.py --replace \
  --save /path/to/resume-multi.gam \
  --id resume-en-multi-planet --role m1-multi-planet \
  --storage repository --repository-path fixtures/saves/resume-multi.gam \
  --player-planet "Alpha I" --player-planet "Beta II" --player-planet "Gamma III" \
  --empty-action-planet "Beta II" \
  --evidence runtime --verified-by docs/experiments/<record>.md
```

Never promote a fixture on its description alone. If the declared numbers contradict the claimed role, validation fails closed rather than reporting the fixture as unusable — a wrong verified claim is an error, an honest unverified one is not.

## Before opening the PR

1. `python scripts/validate_validation_fixtures.py` — declaration is sound, payload identity verified where reachable.
2. `python -m unittest discover -s tests` and `python scripts/check-docs.py`.
3. Check the save itself: it must be the maintainer's own save of a game they may distribute, produced by ordinary play on the canonical `ANTAG.EXE`, carrying no personal data. The player name is the likely place — inspect it with `strings` before committing.
4. Say in the PR body which properties are declared, whether they are verified or still `unverified`, and which experiment will verify them.
