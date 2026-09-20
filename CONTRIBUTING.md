<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# Contributing

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/)
(e.g. `feat(tooling-cli): ...`). Commit messages are validated by
`build/scripts/validate-commit.ps1`.

## License headers

Every source file must carry the PolyForm Noncommercial License 1.0.0
header. Before pushing, run:

```sh
just license-inject   # add any missing headers
just license-check    # verify; must exit 0
```

CI enforces this via `.github/workflows/license-check.yml`.

## Pull requests

Keep PRs focused, ensure `just license-check` passes, and update the
relevant per-app `CHANGELOG.md`.
