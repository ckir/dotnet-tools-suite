<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# DocFX + GitHub Pages — Design

Date: 2026-09-21
Status: Approved (approach A — DocFX .NET tool + official Pages Actions)
Repo: `ckir/dotnet-tools-suite` (branch `main`, .NET 10.0.100)

## 1. Goal

Publish a DocFX documentation site to GitHub Pages at
`https://ckir.github.io/dotnet-tools-suite/`, containing
auto-generated API reference for all 6 projects plus hand-written
conceptual pages. Auto-deploy on every push to `main`; PRs validate
the docs build without deploying.

## 2. Decisions

- Scope: API + conceptual (first version).
- Deploy trigger: push to `main` (paths `docs/**`, `src/**`, workflow
  itself) + `pull_request` build-only + `workflow_dispatch`.
- URL: project subpath (no custom domain). DocFX must set
  `_appBasePath: /dotnet-tools-suite/`.
- Approach A: `dotnet tool` DocFX + `actions/upload-pages-artifact` +
  `actions/deploy-pages`. Rejected B (third-party `gh-pages` branch
  action) and C (folding into `build.yml`).

## 3. Layout (Section 1 — approved)

- `docs/docfx.json` — DocFX configuration.
- `docs/index.md` — landing page.
- `docs/toc.yml` — top-level TOC (Home, Articles, API).
- `docs/articles/intro.md` (+ future conceptual pages).
- `docs/.nojekyll` — empty file, copied to `_site` output to disable
  Jekyll on Pages (protects `_`-prefixed asset paths).
- Generated output `docs/_site/` — gitignored. DocFX cache
  (`docs/obj/`, `.docfx/`) — gitignored.
- `Directory.Build.props` — enable `GenerateDocumentationFile=true`
  centrally so all 6 projects emit XML docs for DocFX metadata.
  Keep `TreatWarningsAsErrors` off for `CS1591` (missing XML comment)
  so docs enablement does not break `build.yml`; docs strictness
  applies only inside the docs workflow via `--warningsAsErrors`.
- `Justfile` — add `docs-serve` recipe for local preview
  (`docfx docs/docfx.json --serve` or `docfx build + serve`).

## 4. DocFX config (Section 2 — approved)

`docs/docfx.json` sketch:

- `metadata`: one `src` entry per project:
  `src/apps/tooling-cli/*.csproj`, `src/apps/datasync-cli/*.csproj`,
  `src/apps/reporting-cli/*.csproj`, `src/libs/shared-kernel/*.csproj`,
  `src/libs/logging/*.csproj`, `src/libs/cli-runtime/*.csproj`,
  `dest: api`, `disableGitFeatures: false`, `disableDefaultFilter: false`.
- `build`: `content` = `api/*.yml`, `api/index.md`, `articles/**`,
  `*.md`, `toc.yml`; `resource` = images if added; `dest: _site`;
  `template: ["default", "modern"]` (fall back to `["default"]` if the
  installed DocFX version ships a single template);
  `globalMetadata: { _appTitle: dotnet-tools-suite,
  _appBasePath: /dotnet-tools-suite/, _enableSearch: true }`;
  `sitemap`, `xref`, GitHub `edit` links to
  `https://github.com/ckir/dotnet-tools-suite/blob/main/docs/`.
- Landing `docs/index.md` + `docs/api/index.md` stubs so API and
  conceptual sections both resolve.

## 5. CI workflow (Section 3 — approved)

New file `.github/workflows/docs.yml` (license header per repo convention):

- `on`: `push.branches: [main]`, `paths: [docs/**, src/**,
  .github/workflows/docs.yml]`; `pull_request.branches: [main]` (same
  paths); `workflow_dispatch`.
- `permissions`: `contents: read`, `pages: write`, `id-token: write`.
- `concurrency`: group `pages`, `cancel-in-progress: false`.
- Job `build` (ubuntu-latest): checkout, `setup-dotnet@v6`
  (`dotnet-version: 10.0.x`), install DocFX
  (`dotnet tool update -g docfx` or local manifest), run
  `docfx docs/docfx.json` (PRs add strict flag), copy `docs/.nojekyll`
  into `docs/_site/`, `actions/upload-pages-artifact@v3`
  (`path: docs/_site`).
- Job `deploy` (`needs: build`, `if: github.event_name != 'pull_request'
  && github.ref == 'refs/heads/main'`, `environment: github-pages`):
  `actions/deploy-pages@v4`.
- One-time manual step (documented in spec + workflow comment):
  repo Settings → Pages → Source → **GitHub Actions**.

## 6. Validation (Section 4 — approved)

- PR check fails the docs build on warnings (`--warningsAsErrors` or
  equivalent log parser) without affecting `build.yml` strictness.
- Local: `just docs-serve` renders without broken links/images.
- Post-deploy: home page, one API page per assembly, and search load
  under the `/dotnet-tools-suite/` base path.
- Housekeeping: `README.md` Pages badge/link, `TODO.md` docs item
  ticked, `.gitignore` covers `_site`/`obj`.

## 7. Out of scope

Custom domain/CNAME, versioned docs per tag, PDF/eBook export,
PlatyPS/PowerShell-help site integration, localized docs.

## 8. Risks

- Pages source still set to branch deploy → deploy job succeeds but
  site never updates. Mitigation: explicit manual step + link check.
- Missing `_appBasePath` → assets 404 under subpath. Covered by config
  + post-deploy check.
- DocFX template name drift across versions → fallback to `default`.
- `CS1591` noise from newly enabled XML docs → keep warnings non-fatal
  in library builds; strict only in docs workflow.
