# CF3 — cloud runtime/debugging investigation

- Date: 2026-08-11
- Status: **Investigation incomplete — demo package validated statically; runtime blocked by missing emulator in this sandbox**
- Execution classification: remains `CLOUD RESEARCH`
- Evidence categories: real-file static + package documentation + cloud-environment runtime/tool availability

## Question

Can the Ascendancy demo, and ideally the canonical Antagonizer executable against the demo data set, run reproducibly in cloud infrastructure with enough observability for RE4/RE5?

## Demo input now available

The maintainer supplied the complete downloadable demo package:

- `ascdemo.zip`
- size `8978479`
- SHA-256 `eb18315e744bf53be4dc5d8533f80d317e073661e86acb2ebba3241ae67f9e79`
- 19 ZIP members

Its internal `ASCEND.EXE` is `582147` bytes with SHA-256 `0183b75cb44ce52b52ba57baf2b9521e21a7611e487a1ebb5b768067441960a9`, exactly matching the demo executable previously supplied separately.

Detailed package/container/static-analysis evidence is in [`CF3-demo-executable-static-preflight.md`](./CF3-demo-executable-static-preflight.md).

## Feature suitability

The package itself materially improves the CF3 outlook.

The README explicitly documents:

```text
<M>         toggle research and planet self-management
```

and the supplied resources contain Planet Status/Planet Display/Research UI help text. Thus the demo is not merely a title-screen or combat-only build: the package documentation says the exact self-management behavior relevant to M1 exists.

This satisfies the roadmap requirement to **evaluate whether the demo has the relevant feature at all** at the package/static level. Runtime confirmation is still required before later RE tasks depend on it.

## Package completeness preflight

`COB.CFG` names:

```text
ascend00.cob
ascend01.cob
ascend02.cob
```

and all three archives are present. The package also contains `DOS4GW.EXE`, `SETSOUND.EXE`, `UVCONFIG.EXE`, Miles DIG drivers and the driver list.

The README says to run `SETSOUND` after unzipping and describes `DIG.INI` / `ASCEND.CFG` among installed files; those two files are not present in the supplied ZIP. This is treated as setup/runtime configuration, not as proof the package is incomplete, because the downloader instructions explicitly include a configuration step. That behavior has not yet been run under DOS.

## Static `ANTAG.EXE` compatibility preflight

The demo executable and the four full-build executables share the same top-level external runtime/configuration filenames (`cob.cfg`, `ascend.cfg`, DIG/MDI configuration, DOS4GW, VESA/UniVBE handling).

Nothing at that top-level file-contract layer rules out trying `ANTAG.EXE` in the demo directory. Conversely, no static result proves that all resources/data indices required by Antagonizer exist in the cut-down demo archives. Runtime remains the decisive experiment.

## Cloud environment probe

The current sandbox was checked directly for:

- `dosbox`
- `dosbox-x`
- `dosbox-staging`
- `dosemu` / `dosemu2`
- `qemu-system-i386` / `qemu-i386`
- Wine

None is installed.

Relevant available pieces:

- Debian 13 (`trixie`)
- `Xvfb`
- SDL2 runtime

The apt sources are configured for normal Debian trixie repositories, but `apt-get update` fails because the sandbox cannot resolve `deb.debian.org`. Therefore an emulator could not be installed through the normal package-manager path in this run.

This is a **specific cloud-image/network limitation**, not a demonstrated architectural blocker. Do not mark RE4/RE5/P2/V1 `LOCAL ONLY` from this experiment.

## Minimal next cloud experiment

A cloud image with DOSBox (or another scriptable DOS protected-mode emulator) already installed, or with working Debian-package egress, should run the supplied exact demo package first.

The minimum information-gain sequence is:

1. mount the exact extracted demo directory read/write;
2. configure or disable sound non-interactively enough to pass startup;
3. launch the demo with a virtual X display / deterministic video configuration;
4. establish that it reaches the main game rather than returning an immediate VESA/data/config error;
5. navigate to a planet and exercise the documented `M` self-management toggle;
6. capture a bounded screenshot/log/state artifact;
7. replace only `ASCEND.EXE` with hash-pinned `ANTAG_EN.EXE` while leaving the demo data unchanged and repeat startup;
8. if Antagonizer fails, capture the exact error and file/resource access context rather than concluding generally that the demo is incompatible.

One successful run should produce a self-contained artifact containing emulator/version, exact executable/data hashes, configuration, stdout/stderr, screenshots or frame capture, and any diagnostic trace used.

## Current decision

CF3 remains **Investigation first / CLOUD RESEARCH**.

Positive evidence:

- exact full demo package is now available;
- package documentation explicitly includes planet self-management;
- required planet-management UI material is present;
- executable/data top-level contract is coherent;
- the demo executable belongs to the same LE/Watcom/DOS4G family as the CF1 targets.

Unresolved only because this sandbox lacks a runnable DOS emulator and cannot install one through its blocked apt DNS path:

- actual demo boot;
- actual self-management interaction;
- `ANTAG.EXE + demo data` runtime compatibility;
- debugger/instrumentation capability.

This is substantially narrower than the original CF3 unknown: the remaining question is now emulator/runtime execution, not demo availability or feature presence.
