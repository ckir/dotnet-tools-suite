<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# DocFX GitHub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DocFX site (API + conceptual) that auto-deploys to GitHub Pages on pushes to `main`.

**Architecture:** `docs/` folder holds `docfx.json` (csproj metadata source, `_site` output); `Directory.Build.props` enables XML docs centrally; new `docs.yml` workflow builds with the `docfx` .NET tool and deploys via the official `upload-pages-artifact` + `deploy-pages` actions.

**Tech Stack:** DocFX (.NET tool `docfx`), .NET SDK 10.0.x, GitHub Actions, GitHub Pages (Actions source).

**Spec:** `docs/superpowers/specs/2026-09-21-docfx-github-pages-design.md`

## Global Constraints

- .NET SDK `10.0.x` in CI via `actions/setup-dotnet@v6`; checkout via `actions/checkout@v7`.
- Pages deploy only with `actions/upload-pages-artifact@v3` + `actions/deploy-pages@v4`, permissions `contents: read`, `pages: write`, `id-token: write`, environment `github-pages`, concurrency group `pages` with `cancel-in-progress: false`.
- Site serves from project subpath: `globalMetadata._appBasePath` is exactly `/dotnet-tools-suite/`; sitemap `baseUrl` is exactly `https://ckir.github.io/dotnet-tools-suite`.
- PolyForm license headers REQUIRED on every `.md`, `.yml`, `.props` file touched; `.json` files MUST NOT carry headers (JSON has no comments — the injector skips `.json` and a header would invalidate it); `docs/.nojekyll` stays empty with no header.
- One-time manual step (not automatable): repo Settings → Pages → Source → `GitHub Actions`.
- `GenerateDocumentationFile=true` must not break `build.yml`: add `NoWarn 1591`, do not enable `TreatWarningsAsErrors` for `CS1591` in library builds; strict docs warnings apply only inside `docs.yml`.

---

## File Structure

- Modify: `Directory.Build.props` — single place enabling XML doc files for all 6 projects (`GenerateDocumentationFile`, `NoWarn 1591`).
- Modify: `.gitignore` — ignore DocFX output/cache (`docs/_site/`, `docs/obj/`).
- Create: `docs/docfx.json` — metadata (6 csproj via `src: ".."`) + build (content, `_appBasePath`, sitemap). No license header.
- Create: `docs/toc.yml`, `docs/index.md`, `docs/articles/toc.yml`, `docs/articles/intro.md`, `docs/api/index.md` — landing, TOC, first conceptual page, API stub. All with PolyForm `<!-- -->` headers.
- Create: `docs/.nojekyll` — empty file (no header) so Pages skips Jekyll.
- Create: `docs/images/.gitkeep` — empty placeholder so the `images/**` resource glob has a target dir (no header needed for `.gitkeep`; it is not a checked extension).
- Create: `.github/workflows/docs.yml` — build + deploy jobs per constraints. `# `-style PolyForm header.
- Modify: `Justfile` — add `docs-install`, `docs-build`, `docs-serve` recipes.
- Modify: `README.md` — docs badge + link (keep existing PolyForm header).
- Modify: `TODO.md` — tick the Docs checkbox (keep existing header).

---

### Task 1: XML docs foundation + gitignore

**Files:**
- Modify: `Directory.Build.props`
- Modify: `.gitignore`
- Test: shell (`dotnet build`, `git status --porcelain`, `python scripts/polyform_injector.py --check`)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `GenerateDocumentationFile=true` + `NoWarn 1591` for all projects; `docs/_site/` + `docs/obj/` ignored. Later tasks rely on XML files existing at `src/**/bin/Release/*/net10.0/*.xml`.

- [ ] **Step 1: Confirm current props has no doc settings**

Run: `grep -n "GenerateDocumentationFile\|NoWarn" Directory.Build.props || echo "ABSENT"`
Expected: `ABSENT` (proves the edit below is the change that enables XML docs).

- [ ] **Step 2: Enable XML docs centrally**

Edit `Directory.Build.props` from:

```xml
<Project></Project>
```

to:

```xml
<Project>
  <PropertyGroup>
    <GenerateDocumentationFile>true</GenerateDocumentationFile>
    <NoWarn>$(NoWarn);1591</NoWarn>
  </PropertyGroup>
</Project>
```

Keep the existing PolyForm `<!-- -->` header at the top untouched.

- [ ] **Step 3: Verify libraries still build with XML output**

Run: `dotnet build src/libs/shared-kernel/shared-kernel.csproj --configuration Release`
Expected: exit 0, and `ls src/libs/shared-kernel/bin/Release/net10.0/*.xml` lists one XML file.

- [ ] **Step 4: Append DocFX ignores to `.gitignore`**

Append exactly:

```
# DocFX
docs/_site/
docs/obj/
```

- [ ] **Step 5: Verify license headers and git state**

Run: `python scripts/polyform_injector.py --check`
Expected: `All files contain PolyForm headers.`

- [ ] **Step 6: Commit**

```bash
git add Directory.Build.props .gitignore
git commit -m "chore: enable XML docs centrally and ignore DocFX output"
```

---

### Task 2: DocFX content scaffold

**Files:**
- Create: `docs/docfx.json` (no header)
- Create: `docs/toc.yml`, `docs/index.md`, `docs/articles/toc.yml`, `docs/articles/intro.md`, `docs/api/index.md` (all with PolyForm headers)
- Create: `docs/.nojekyll` (empty), `docs/images/.gitkeep` (empty)
- Test: shell (`python scripts/polyform_injector.py --check`, `docfx --version` later in Task 3)

**Interfaces:**
- Consumes: XML docs enabled (Task 1).
- Produces: complete DocFX source tree that Task 3 builds; `docs/docfx.json` path consumed by `Justfile` recipes and `docs.yml` (Tasks 4).

- [ ] **Step 1: Verify docs tree is absent**

Run: `ls docs/docfx.json docs/toc.yml docs/index.md 2>&1 || echo "SCAFFOLD-ABSENT"`
Expected: `SCAFFOLD-ABSENT`.

- [ ] **Step 2: Write `docs/docfx.json` (no header — JSON)**

```json
{
  "metadata": [
    {
      "src": [
        {
          "files": [
            "src/apps/tooling-cli/tooling-cli.csproj",
            "src/apps/datasync-cli/datasync-cli.csproj",
            "src/apps/reporting-cli/reporting-cli.csproj",
            "src/libs/shared-kernel/shared-kernel.csproj",
            "src/libs/logging/logging.csproj",
            "src/libs/cli-runtime/cli-runtime.csproj"
          ],
          "src": ".."
        }
      ],
      "dest": "api",
      "properties": {
        "TargetFramework": "net10.0",
        "Configuration": "Release"
      }
    }
  ],
  "build": {
    "content": [
      {
        "files": ["api/*.yml", "api/index.md"]
      },
      {
        "files": ["articles/*.md", "articles/toc.yml", "toc.yml", "*.md"]
      }
    ],
    "resource": [
      {
        "files": ["images/**"]
      }
    ],
    "dest": "_site",
    "globalMetadata": {
      "_appTitle": "dotnet-tools-suite",
      "_appBasePath": "/dotnet-tools-suite/",
      "_enableSearch": true
    },
    "template": ["default", "modern"],
    "sitemap": {
      "baseUrl": "https://ckir.github.io/dotnet-tools-suite",
      "changefreq": "weekly",
      "priority": 0.5
    }
  }
}
```

Note: `files` globs are relative to `src: ".."` (repo root) because DocFX cannot crawl outside the `docs/` directory otherwise. If the installed DocFX errors with `Template 'modern' not found`, change `"template"` to `["default"]` only.

- [ ] **Step 3: Write `docs/toc.yml`**

```yaml
<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

- name: Home
  href: index.md
- name: Articles
  href: articles/toc.yml
- name: API Reference
  href: api/index.md
```

- [ ] **Step 4: Write `docs/index.md`**

```markdown
<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

---
title: dotnet-tools-suite
description: Documentation for the dotnet-tools-suite .NET 10 CLI tools and libraries.
---

# dotnet-tools-suite

A suite of .NET 10 command-line tools and shared libraries.

- [Articles](articles/intro.md): concepts and guides.
- [API Reference](api/index.md): auto-generated from source and XML doc comments.

## Projects

| Area | Projects |
|------|----------|
| Apps | `tooling-cli`, `datasync-cli`, `reporting-cli` |
| Libraries | `shared-kernel`, `logging`, `cli-runtime` |
```

- [ ] **Step 5: Write `docs/articles/toc.yml`, `docs/articles/intro.md`, `docs/api/index.md`**

`docs/articles/toc.yml`:

```yaml
<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

- name: Introduction
  href: intro.md
```

`docs/articles/intro.md`:

```markdown
<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# Introduction

This site documents `dotnet-tools-suite`: three CLI apps (`tooling-cli`, `datasync-cli`, `reporting-cli`) and three libraries (`shared-kernel`, `logging`, `cli-runtime`).

API pages are generated from the projects under `src/` and their XML documentation comments. Add `///` doc comments to public APIs to improve the reference.
```

`docs/api/index.md`:

```markdown
<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# API Reference

Auto-generated from `src/apps/*` and `src/libs/*`. Select a namespace in the table of contents.
```

- [ ] **Step 6: Create `.nojekyll` and images placeholder**

Run: `mkdir -p docs/images docs/articles docs/api && : > docs/.nojekyll && : > docs/images/.gitkeep`
Expected: both files exist and are zero bytes (`wc -c docs/.nojekyll docs/images/.gitkeep`).

- [ ] **Step 7: Verify headers (json must be skipped by the checker)**

Run: `python scripts/polyform_injector.py --check`
Expected: `All files contain PolyForm headers.` (checker only enforces `.md`/`.yml`; `.json`/`.nojekyll`/`.gitkeep` are not checked).

- [ ] **Step 8: Commit**

```bash
git add docs/docfx.json docs/toc.yml docs/index.md docs/articles/toc.yml docs/articles/intro.md docs/api/index.md docs/.nojekyll docs/images/.gitkeep
git commit -m "docs: scaffold DocFX site sources"
```

---

### Task 3: Local DocFX build verification

**Files:**
- Modify: none (verification only; if `modern` template is missing, edit `docs/docfx.json` template line to `["default"]`).
- Test: shell (`dotnet tool update -g docfx`, `docfx docs/docfx.json`, checks on `docs/_site/`)

**Interfaces:**
- Consumes: `docs/docfx.json` + content (Task 2), XML docs (Task 1).
- Produces: verified local build procedure + confirmed `--warningsAsErrors` flag support (yes/no) consumed by Task 4's workflow strictness step.

- [ ] **Step 1: Install DocFX and show version**

Run: `dotnet tool update -g docfx && docfx --version`
Expected: exit 0 and a version string (e.g. `v2.77+`).

- [ ] **Step 2: Restore projects for metadata stage**

Run: `dotnet restore src/apps/tooling-cli/tooling-cli.csproj && dotnet restore src/apps/datasync-cli/datasync-cli.csproj && dotnet restore src/apps/reporting-cli/reporting-cli.csproj`
Expected: exit 0 for all three (libraries restore transitively).

- [ ] **Step 3: Build the site**

Run: `docfx docs/docfx.json`
Expected: exit 0; `docs/_site/index.html` exists; `ls docs/_site/api | head` shows generated API pages.

- [ ] **Step 4: Confirm base-path rewriting for project subpath**

Run: `grep -o "/dotnet-tools-suite/" docs/_site/index.html | head -1`
Expected: `/dotnet-tools-suite/` (proves `_appBasePath` was applied; without it Pages serves 404 assets).

- [ ] **Step 5: Confirm strict-flag support for the CI workflow**

Run: `docfx build --help | grep -i "warningsAsErrors" || docfx --help | grep -i "warningsAsErrors" || echo "STRICT-FLAG-ABSENT"`
Expected: either a `warningsAsErrors` line (Task 4 uses `docfx docs/docfx.json --warningsAsErrors` on PRs) or `STRICT-FLAG-ABSENT` (Task 4 uses plain `docfx docs/docfx.json` on PRs and relies on non-zero exit). Record the outcome in the commit message body.

- [ ] **Step 6: Commit any template fallback fix (only if Step 3 failed on `modern`)**

If Step 3 failed with `Template 'modern' not found`, edit `docs/docfx.json` line `"template": ["default", "modern"],` to `"template": ["default"],`, re-run Step 3, then:

```bash
git add docs/docfx.json
git commit -m "docs: fall back to default DocFX template"
```

If Step 3 passed, skip this step with no commit.

---

### Task 4: CI workflow + local recipes + README badge

**Files:**
- Create: `.github/workflows/docs.yml`
- Modify: `Justfile`, `README.md`
- Test: shell (`python -c` YAML sanity, `just docs-build`, header check, `git status` ignores `_site`)

**Interfaces:**
- Consumes: `docs/docfx.json` path (Task 2), strict-flag outcome (Task 3).
- Produces: `docs.yml` referenced by the docs badge in `README.md`; `just docs-*` recipes for local use. Task 5 validates the workflow end to end.

- [ ] **Step 1: Verify workflow is absent**

Run: `ls .github/workflows/docs.yml 2>&1 || echo "WORKFLOW-ABSENT"`
Expected: `WORKFLOW-ABSENT`.

- [ ] **Step 2: Write `.github/workflows/docs.yml`**

```yaml
# Copyright (c) 2026 Costas Kirgoussios
# Licensed under the PolyForm Noncommercial License 1.0.0

name: Docs

on:
  push:
    branches: [main]
    paths:
      - "docs/**"
      - "src/**"
      - ".github/workflows/docs.yml"
  pull_request:
    branches: [main]
    paths:
      - "docs/**"
      - "src/**"
      - ".github/workflows/docs.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v7

      - name: Set up .NET
        uses: actions/setup-dotnet@v6
        with:
          dotnet-version: "10.0.x"

      - name: Restore
        run: |
          dotnet restore src/apps/tooling-cli/tooling-cli.csproj
          dotnet restore src/apps/datasync-cli/datasync-cli.csproj
          dotnet restore src/apps/reporting-cli/reporting-cli.csproj

      - name: Install DocFX
        run: dotnet tool update -g docfx

      - name: Build docs
        # NOTE: requires repo Settings -> Pages -> Source = "GitHub Actions" (one-time manual step).
        # PRs build strictly; main pushes build normally then deploy.
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            docfx docs/docfx.json --warningsAsErrors
          else
            docfx docs/docfx.json
          fi

      - name: Add .nojekyll
        run: cp docs/.nojekyll docs/_site/.nojekyll

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: docs/_site

  deploy:
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

If Task 3 Step 5 reported `STRICT-FLAG-ABSENT`, replace the `Build docs` run block with a single line: `run: docfx docs/docfx.json`.

- [ ] **Step 3: Sanity-check workflow YAML parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/docs.yml')); print('YAML-OK')"`
Expected: `YAML-OK`. (If `pyyaml` is missing, run `python3 -c "import sys; open('.github/workflows/docs.yml').read(); print('YAML-READ-OK')"` instead and eyeball indentation.)

- [ ] **Step 4: Add `just` recipes**

Append to `Justfile`:

```make
docs-install:
    dotnet tool update -g docfx

docs-build:
    docfx docs/docfx.json

docs-serve:
    docfx docs/docfx.json --serve
```

Verify with: `just --list | grep docs`
Expected: lists `docs-install`, `docs-build`, `docs-serve`.

- [ ] **Step 5: Add README badge and link**

Edit `README.md`: after the `# dotnet-tools-suite` title block, insert:

```markdown
[![Docs](https://github.com/ckir/dotnet-tools-suite/actions/workflows/docs.yml/badge.svg)](https://ckir.github.io/dotnet-tools-suite/)
```

Keep the existing PolyForm header comment. Verify with: `grep -n "docs.yml/badge" README.md`
Expected: one matching line.

- [ ] **Step 6: Confirm `_site` stays untracked and headers pass**

Run: `git status --porcelain | grep "_site" || echo "SITE-IGNORED"; python scripts/polyform_injector.py --check`
Expected: `SITE-IGNORED` and `All files contain PolyForm headers.`

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/docs.yml Justfile README.md
git commit -m "ci: add DocFX docs workflow with GitHub Pages deploy"
```

---

### Task 5: End-to-end validation and Pages enablement

**Files:**
- Modify: `TODO.md` (tick Docs box)
- Test: shell + browser (local serve smoke, `act` optional, live URL after push)

**Interfaces:**
- Consumes: workflow (Task 4), built `_site` (Task 3).
- Produces: live site at `https://ckir.github.io/dotnet-tools-suite/`; closed Docs TODO.

- [ ] **Step 1: Serve locally and smoke-test**

Run: `docfx docs/docfx.json --serve & sleep 8; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/dotnet-tools-suite/; kill %1`
Expected: `200`. If the root path 404s, retry `curl http://localhost:8080/` and note the serving root — `_appBasePath` only rewrites asset links, and the local serve root may differ from Pages.

- [ ] **Step 2: Check API and search artifacts exist**

Run: `ls docs/_site/api | head -5; ls docs/_site | grep -i "index.html\|sitemap.xml\|search" | head -5`
Expected: API listing is non-empty; `index.html` and `sitemap.xml` exist.

- [ ] **Step 3: Push branch and open PR (workflow validation)**

Run: `git push -u origin HEAD && gh pr create --fill --title "docs: add DocFX with GitHub Pages deploy" --body "Validates docs.yml build on PR."`
Expected: PR checks show the `Docs / build` job green and `deploy` skipped.

- [ ] **Step 4: One-time Pages source switch (manual, in browser)**

Go to `https://github.com/ckir/dotnet-tools-suite/settings/pages` → under Build and deployment → Source → select `GitHub Actions`. Merge the PR, then watch the `Docs` workflow on `main`: `build` green followed by `deploy` green.

- [ ] **Step 5: Verify live site**

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://ckir.github.io/dotnet-tools-suite/`
Expected: `200`. In a browser confirm: landing page renders, one API page per assembly loads, search returns a result.

- [ ] **Step 6: Tick Docs TODO and commit**

Edit `TODO.md` Docs section from `- [ ]` to `- [x] DocFX site live on GitHub Pages`, keep the PolyForm header, then:

```bash
git add TODO.md
git commit -m "docs: mark GitHub Pages site live"
```

---

## Self-Review

- Spec coverage: layout → Tasks 1–2; `docfx.json` config + `_appBasePath` → Task 2 + verified Task 3 Step 4; workflow → Task 4; validation → Tasks 3 + 5; manual Pages step → Task 5 Step 4; README/TODO housekeeping → Tasks 4–5. No gaps.
- Placeholder scan: no `TBD`/`TODO`/vague handling; every code step ships exact file content and exact run commands with expected outputs; `modern` template and `--warningsAsErrors` fallbacks are explicit conditionals, not open ends.
- Type consistency: paths (`docs/docfx.json`, `docs/_site`, `src: ".."`), versions (`checkout@v7`, `setup-dotnet@v6`, `upload-pages-artifact@v3`, `deploy-pages@v4`, `10.0.x`), and URLs (`/dotnet-tools-suite/`, `https://ckir.github.io/dotnet-tools-suite`) are identical across tasks.
