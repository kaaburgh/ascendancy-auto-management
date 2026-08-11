# Claude Code instructions

Read and follow [`AGENTS.md`](./AGENTS.md) before planning or editing. It is the canonical repository instruction file; [`docs/agent-playbook.md`](./docs/agent-playbook.md) contains the detailed autonomous RE workflow.

Key rules:

- treat `ROADMAP.md` as the live status and sequencing source;
- observe and instrument before patching when the cause is unknown;
- tie offsets/patches to exact binary hashes and fail closed on unsupported binaries;
- preserve important RE findings and negative experiments in the repository;
- distinguish static/runtime/synthetic/reported evidence from assumptions;
- never claim target behavior was verified without an actual target-machine observation.
