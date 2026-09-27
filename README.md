<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# dotnet-tools-suite

[![Build](https://github.com/ckir/dotnet-tools-suite/actions/workflows/build.yml/badge.svg)](https://github.com/ckir/dotnet-tools-suite/actions/workflows/build.yml)
[![Docs](https://github.com/ckir/dotnet-tools-suite/actions/workflows/docs.yml/badge.svg)](https://ckir.github.io/dotnet-tools-suite/)
[![License Header Enforcement](https://github.com/ckir/dotnet-tools-suite/actions/workflows/license-check.yml/badge.svg)](https://github.com/ckir/dotnet-tools-suite/actions/workflows/license-check.yml)
[![Release](https://github.com/ckir/dotnet-tools-suite/actions/workflows/release.yml/badge.svg)](https://github.com/ckir/dotnet-tools-suite/actions/workflows/release.yml)

A suite of .NET 10 command-line tools and shared libraries.

## Apps (`src/apps`)

| App | Description |
|-----|-------------|
| `tooling-cli` | General tooling entry point |
| `datasync-cli` | Data synchronization tool |
| `reporting-cli` | Reporting tool |

## Libraries (`src/libs`)

| Library | Description |
|---------|-------------|
| `shared-kernel` | Shared domain primitives |
| `logging` | Logging abstractions |
| `cli-runtime` | CLI hosting runtime |

## Prerequisites

- .NET SDK `10.0.100` or newer 10.0.x (pinned in `global.json`
  with `rollForward: latestFeature`; also listed in `perster.json`)
- `just`, `lefthook`, Python 3.x, PowerShell (`pwsh`) for hooks
- PowerShell modules (`Pester`, `PlatyPS`, `PSDepend`) and tools
  (`just`, `lefthook`, `gitleaks`) listed in `perster.json`
- Local .NET tools restore automatically via `just setup`
  (`docfx`, `GitVersion.Tool`, `CycloneDX`, `ReportGenerator`
  in `.config/dotnet-tools.json`; `dotnet format` ships with the SDK)

## Quick start

```sh
git clone ... && cd dotnet-tools-suite
just setup   # restore local tools + NuGet packages, install git hooks
just check   # format, license, build, test — run before pushing
```

`just setup` restores the local .NET tools (`.config/dotnet-tools.json`),
restores NuGet packages, and installs the Lefthook git hooks, so a fresh
clone is ready for development. It requires `lefthook` on `PATH` (see
Prerequisites) and fails loudly if it is missing.

Common commands (all exist — see `just --list`):

```sh
just build      # build solution (Release)
just test       # run tests with coverage into TestResults/
just pack       # pack libraries into artifacts/packages/ (CI/release only)
just docs-serve # serve the DocFX site locally
```

CI runs `just check` plus `just pack` and a ReportGenerator coverage
report. Releases are cut from `v*` tags: packages are generated and
attached as GitHub Release assets (libraries are not published to
NuGet.org). See [CONTRIBUTING](CONTRIBUTING.md) for details.

## License

PolyForm Noncommercial License 1.0.0 — see [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md).
