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

## Usage

```sh
just setup          # restore local tools + NuGet packages
just check          # PR validation: format, license, build, test, pack
just build          # build solution (Release)
just test           # run tests with coverage into TestResults/
just pack           # pack libraries into artifacts/packages/
just format         # apply dotnet format
just format-check   # verify formatting without modifying files
just license-check  # verify PolyForm license headers
just license-inject # add missing PolyForm license headers
just docs           # build DocFX site
just docs-serve     # serve DocFX site locally
just version        # show GitVersion
just sbom           # CycloneDX SBOM into artifacts/sbom/ (release only)
```

Run `just check` before opening a PR; CI runs the same command.
Libraries in `src/libs` enable package validation on `pack`.
Releases are cut from `v*` tags; see [CONTRIBUTING](CONTRIBUTING.md).

## License

PolyForm Noncommercial License 1.0.0 — see [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md).
