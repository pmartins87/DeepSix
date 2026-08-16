# Operational OpenHoldem source-dump evidence

Date recorded: 2026-08-16

DeepSix currently has a text export of the OpenHoldem source tree used as project evidence:

- source artifact name: `repositorio_completo_openholdem.txt`
- embedded original root: `C:\Users\Caixa\Desktop\personal\myoh_git\OpenHoldem\`
- artifact size: **2,275,222 bytes**
- SHA-256: `8a2809bf32b226775a237c9a51f970e8fd55148e777890f9a275b5fd6bd8521e`
- embedded text files: **393**
  - 196 `.cpp`
  - 197 `.h`

## What this snapshot proves

It is a stable, hashable record of the C++/header source material supplied to the project and is suitable for source auditing, locating legacy assumptions and reconstructing those embedded text files.

## What this snapshot does **not** prove

The export contains no `.sln`, `.vcxproj`, `.vcproj`, `.props` or `.filters` files and therefore is **not by itself a build-complete clone** of the operational OpenHoldem working directory. It may also omit resources, generated files, third-party dependencies and other non-C++ assets required to reproduce the exact executable.

Accordingly:

- do not call this dump a complete reproducible operational snapshot;
- do not overwrite the clean-upstream provenance record with it;
- use it as the authoritative source evidence available to DeepSix for the 393 embedded C++/header files;
- before the first full Windows build of OpenHoldem6Plus, capture the actual operational working tree/build metadata or an archive of that directory and record its own hash.

## Relationship to clean upstream

The clean upstream baseline remains separately pinned in `PROVENANCE.md` to `OpenHoldem/openholdembot@5d2bb3afec7922aab1b72aef1b23265ff6ea1b13`.

This source dump comes from the user's locally evolved `myoh_git/OpenHoldem` tree and must be treated as a **local lineage**, not silently equated with pristine upstream.
