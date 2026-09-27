<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# Contributing

## Setup

```sh
just setup  # dotnet tool restore + dotnet restore + lefthook install
```

Requires .NET SDK 10.0.x (see `global.json`), `just`, `lefthook`,
Python 3.x, and `pwsh`. `just setup` fails loudly if `lefthook` is
missing; install it, then re-run. CI uses `just restore` instead
(tools and packages only — hooks are a developer-machine concern).

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/)
(e.g. `feat(tooling-cli): ...`). Commit messages are validated by
`build/scripts/validate-commit.ps1` (also wired as the `commit-msg` hook).

## Checks

Run before pushing:

```sh
just check  # format-check + license-check + build + test
```

- `just format` applies formatting (`dotnet format`, ships with the SDK);
  `just format-check` verifies without modifying files (used by CI/pre-commit).
- `just test` runs `dotnet test` with XPlat coverage into `TestResults/`;
  use `just coverage-report` (ReportGenerator) for HTML output.
  New test projects should reference `coverlet.collector` so coverage
  collection works out of the box.
- `just pack` packs only `src/libs/*` (`IsPackable=true` with
  `EnablePackageValidation`); apps set `IsPackable=false`. Kept out of
  `just check` so pre-push stays fast — CI and release run it explicitly.
- `just version` shows the GitVersion (ContinuousDelivery).
- `just sbom` generates CycloneDX JSON (release only, not part of `check`).

## License headers

Every source file must carry the PolyForm Noncommercial License 1.0.0
header. Before pushing, run:

```sh
just license-inject   # add any missing headers
just license-check    # verify; must exit 0
```

CI enforces this via `.github/workflows/license-check.yml`.
Generated output (`bin/`, `obj/`, `artifacts/`, `TestResults/`,
`docs/_site/`, `docs/api/*.yml`) is excluded from the check.

## Pull requests

Keep PRs focused, ensure `just check` passes, and update the
relevant per-app `CHANGELOG.md`.

CI (`build.yml`) runs `just check`, then `just pack`, plus raw and
HTML (ReportGenerator) coverage artifacts.
Docs deploy from `main` via `docs.yml`. Releases are cut from `v*`
tags (or manual dispatch): version, build, test, pack, SBOM,
artifacts, then a GitHub Release with generated notes. Built
packages are attached as release assets; nothing is published to
NuGet.org (no push step, no credentials) — PR/push CI never publishes.
Dependabot (weekly, grouped) covers NuGet, GitHub Actions, and the
.NET SDK pin in `global.json`, and its PRs auto-merge (squash) once
`just check` passes.
