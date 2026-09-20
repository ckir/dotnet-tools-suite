<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# dotnet-tools-suite

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

Pinned in `perster.json`: .NET SDK `10.0.100`, PowerShell modules
(`Pester`, `PlatyPS`, `PSDepend`), and tools (`just`, `lefthook`,
`gitleaks`).

## Usage

```sh
just --list        # show available recipes
just license-check # verify PolyForm license headers
just license-inject # add missing PolyForm license headers
```

## License

PolyForm Noncommercial License 1.0.0 — see [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md).
