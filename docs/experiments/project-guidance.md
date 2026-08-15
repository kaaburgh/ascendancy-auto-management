# Ascendancy experiment guidance

This directory stores reproducible reverse-engineering and target-machine experiments, including negative results.

An experiment should answer one concrete question and make it possible for another agent to understand exactly what was tested.

## File naming

Prefer a roadmap/item prefix and date when useful, for example:

- `R1-planet-toggle-write-trace.md`
- `R3-ui-call-path.md`
- `R5-minimal-runtime-patch.md`

## Template

```markdown
# <Experiment title>

- Roadmap item:
- Date:
- Target SHA-256:
- Evidence category expected: static/runtime/synthetic
- Tool/build:

## Question

What single question is this experiment meant to answer?

## Competing hypotheses

- H1:
- H2:

## Procedure

1. ...
2. ...

## Expected differentiating outcomes

- If H1, expect ...
- If H2, expect ...

## Result

Record observations first.

## Interpretation

State what the observations support or rule out.

## Artifacts

List local artifact filenames/hashes when relevant. Do not commit proprietary or private captures by default.

## Updated model / next experiment

What changed in the project model, and what is now the highest-information next step?
```

A failed experiment is not a failed task if it removes a plausible hypothesis and that result is preserved here and in the roadmap.
