# Operational OpenHoldem source evidence

Date recorded: 2026-08-16

DeepSix has **two different kinds of OpenHoldem evidence**, and they must not be conflated.

## 1. Build-complete operational repository — authoritative lineage

The operational repository is available directly through GitHub:

- repository: `pmartins87/myoh_private`
- operational/default branch observed: `oh_pre_release_v15`
- pinned head at verification: `3aa8a28944e3759fecc9323fb9f7361d54d4c9af`
- pinned commit message: `envia cards dos opps para a dll.`
- repository contains the real Visual Studio/build structure, including:
  - root `OpenHoldem.sln`;
  - `OpenHoldem/OpenHoldem.sln`;
  - `OpenHoldem/OpenHoldem.vcxproj`;
  - user DLL projects;
  - tablemaps/release assets and the wider project tree.

The pinned commit also contains current local-lineage modifications such as the AOF Tracker v24 exports for opponent cards in `OpenHoldem/CSymbolengineUserDLL.cpp`. This is therefore much stronger evidence of the actually evolved OpenHoldem lineage than the old text-only dump.

### DeepSix isolation branch

A dedicated branch has now been created from that exact operational commit:

- branch: `deepsix_6plus`
- base commit: `3aa8a28944e3759fecc9323fb9f7361d54d4c9af`

All future invasive OH6Plus work must go to this dedicated branch (or a later dedicated repository derived from it), never to the operational `oh_pre_release_v15` branch. No autoplay for DeepSix is enabled by creating this branch.

## 2. Historical text source dump — secondary audit artifact

DeepSix also has a text export of the OpenHoldem source tree used as project evidence:

- source artifact name: `repositorio_completo_openholdem.txt`
- embedded original root: `C:\Users\Caixa\Desktop\personal\myoh_git\OpenHoldem\`
- artifact size: **2,275,222 bytes**
- SHA-256: `8a2809bf32b226775a237c9a51f970e8fd55148e777890f9a275b5fd6bd8521e`
- embedded text files: **393**
  - 196 `.cpp`
  - 197 `.h`

### What the text dump proves

It is a stable, hashable record of the C++/header material supplied earlier to the project and remains useful for reproducible source audits and for comparing assumptions against the live repository.

### What the text dump does not prove

The export contains no `.sln`, `.vcxproj`, `.vcproj`, `.props` or `.filters` files and therefore is **not by itself a build-complete clone**. It may omit resources, generated files, third-party dependencies and other non-C++ assets.

The earlier limitation is now resolved by the directly accessible `pmartins87/myoh_private` repository, but the dump remains preserved as historical evidence rather than silently discarded or re-labelled.

## Relationship to clean upstream

The clean upstream baseline remains separately pinned in `PROVENANCE.md` to `OpenHoldem/openholdembot@5d2bb3afec7922aab1b72aef1b23265ff6ea1b13`.

The operational `myoh_private` lineage is the user's evolved production lineage. It must not be silently equated with pristine upstream. DeepSix therefore keeps three concepts separate:

1. clean upstream baseline;
2. operational evolved OpenHoldem lineage;
3. dedicated `deepsix_6plus` development branch.
