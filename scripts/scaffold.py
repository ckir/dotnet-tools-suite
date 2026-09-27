#!/usr/bin/env python3
# Copyright (c) 2026 Costas Kirgoussios
# Licensed under the PolyForm Noncommercial License 1.0.0

"""Scaffold a dotnet-tools-suite-style monorepo. Stdlib only; requires git + gh."""
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATES: dict[str, str] = {}

@dataclass
class Config:
    repo: str
    owner: str
    holder: str
    apps: list[str] = field(default_factory=lambda: ["tooling-cli", "datasync-cli", "reporting-cli"])
    libs: list[str] = field(default_factory=lambda: ["shared-kernel", "logging", "cli-runtime"])
    dotnet: str = "10.0.x"
    no_docs: bool = False
    public: bool = True
    target_dir: str = ""
    skip_create: bool = False
    skip_verify: bool = False

def parse_args(argv=None) -> Config:
    p = argparse.ArgumentParser(description="Scaffold a dotnet monorepo from embedded templates.")
    p.add_argument("--repo", required=False, default="")
    p.add_argument("--owner", default="")
    p.add_argument("--holder", default="")
    p.add_argument("--apps", action="append", default=[])
    p.add_argument("--libs", action="append", default=[])
    p.add_argument("--dotnet", default="10.0.x")
    p.add_argument("--no-docs", action="store_true")
    p.add_argument("--private", dest="public", action="store_false")
    p.add_argument("--public", dest="public", action="store_true")
    p.add_argument("--target-dir", default="")
    p.add_argument("--skip-create", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args(argv)
    if not a.repo and not a.self_test:
        a.repo = input("Repository name: ").strip()
    cfg = Config(repo=a.repo or "selftest", owner=a.owner, holder=a.holder or a.owner,
                 apps=a.apps or list(Config.__dataclass_fields__["apps"].default_factory()),
                 libs=a.libs or list(Config.__dataclass_fields__["libs"].default_factory()),
                 dotnet=a.dotnet, no_docs=a.no_docs, public=a.public,
                 target_dir=a.target_dir or os.path.join(".", a.repo or "selftest"),
                 skip_create=a.skip_create, skip_verify=a.skip_verify)
    return cfg

def render(template: str, ctx: dict[str, str]) -> str:
    out = template
    for key in sorted(ctx, key=len, reverse=True):
        out = out.replace("{{" + key + "}}", ctx[key])
    if "{{" in out:
        raise ValueError(f"unresolved placeholder in rendered output: {out[out.index('{{'):out.index('{{')+30:]}")
    return out

def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")

def metadata_files(cfg: Config) -> str:
    entries = [f'            "src/apps/{a}/{a}.csproj",' for a in cfg.apps]
    entries += [f'            "src/libs/{l}/{l}.csproj",' for l in cfg.libs]
    entries[-1] = entries[-1].rstrip(",")
    return "\n".join(entries)

def lib_refs(cfg: Config) -> str:
    return "\n".join(
        f'    <ProjectReference Include="..\\..\\libs\\{l}\\{l}.csproj" />'
        for l in cfg.libs
    )

def _dotnet_sdk_pin(dotnet: str) -> str:
    parts = dotnet.split(".")
    if len(parts) >= 3 and parts[2] != "x":
        return dotnet
    return f"{parts[0]}.{parts[1]}.100"

def _dotnet_tfm(dotnet: str) -> str:
    parts = dotnet.split(".")
    return f"net{parts[0]}.{parts[1]}"

def build_context(cfg: Config) -> dict[str, str]:
    return {
        "repo": cfg.repo,
        "owner": cfg.owner,
        "holder": cfg.holder,
        "dotnet": cfg.dotnet,
        "dotnet_sdk_pin": _dotnet_sdk_pin(cfg.dotnet),
        "dotnet_tfm": _dotnet_tfm(cfg.dotnet),
        "metadata_files": metadata_files(cfg),
        "readme_apps_row": ", ".join(f"`{a}`" for a in cfg.apps),
        "readme_libs_row": ", ".join(f"`{l}`" for l in cfg.libs),
        "readme_title": cfg.repo,
        "year": "2026",
    }

TEMPLATES.update({
    ".gitignore": "# .NET build outputs\n"
        "[Bb]in/\n[Oo]bj/\n[Oo]ut/\n[Pp]ublish/\nTestResults/\n[Bb]uild[Ll]og/\n*.user\n*.suo\n*.userosscache\n*.sln.docstates\n"
        "\n# .NET tooling / NuGet\n.nuget/\n*.nupkg\n*.snupkg\nproject.lock.json\nproject.fragment.lock.json\nartifacts/\n"
        "\n# MSBuild / Roslyn\n*.binlog\n"
        "\n# Test coverage\n*.coverage\n*.coveragexml\ncoverage*/\nlcov.info\n"
        "\n# Visual Studio / Rider / VS Code\n.vs/\n.vscode/\n.idea/\n*.rsuser\n"
        "\n# Python (scripts/polyform_injector.py)\n__pycache__/\n*.py[cod]\n*$py.class\n.venv/\nvenv/\n.env/\n.pytest_cache/\n.ruff_cache/\n.mypy_cache/\n"
        "\n# PowerShell / Pester\nPesterResults*.xml\n*.trx\n"
        "\n# GitVersion cache\n.gitversion_cache\nGitVersionConfig.json.bak\n"
        "\n# OS\n.DS_Store\nThumbs.db\ndesktop.ini\n*~\n"
        "\n# Temp / local\n*.tmp\n*.bak\n*.log\n"
        "\n# DocFX\ndocs/_site/\ndocs/obj/\ndocs/api/*.yml\ndocs/api/toc.yml\ndocs/api/.manifest\n",
    "Directory.Build.props": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n<Project>\n  <PropertyGroup>\n    <GenerateDocumentationFile>true</GenerateDocumentationFile>\n    <NoWarn>$(NoWarn);1591</NoWarn>\n  </PropertyGroup>\n</Project>\n",
    "Directory.Packages.props": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n<Project></Project>\n",
    "GitVersion.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nmode: ContinuousDelivery\n",
    ".gitattributes": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\n# Normalize line endings to LF in the repository; check out native\n# endings on developer machines.\n* text=auto\n",
    "lefthook.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\npre-commit:\n  parallel: true\n  commands:\n    format-check:\n      run: just format-check\n    license-check:\n      run: just license-check\n\ncommit-msg:\n  commands:\n    conventional:\n      run: pwsh -NoProfile -NonInteractive -File build/scripts/validate-commit.ps1 {1}\n\npre-push:\n  commands:\n    check:\n      run: just check\n",
    "perster.json": "{\n  \"dotnet\": \"{{dotnet_sdk_pin}}\",\n  \"pwsh-modules\": [\n    \"Pester\",\n    \"PlatyPS\",\n    \"PSDepend\"\n  ],\n  \"tools\": [\n    \"gitleaks\",\n    \"lefthook\",\n    \"just\"\n  ]\n}\n",
    ".github/workflows/build.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Build\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Set up Python\n        uses: actions/setup-python@v7\n        with:\n          python-version: \"3.x\"\n\n      - name: Set up just\n        uses: extractions/setup-just@v4\n\n      - name: Check (format, license, build, test, pack)\n        run: just check\n\n      - name: Upload coverage artifact\n        if: always()\n        uses: actions/upload-artifact@v7\n        with:\n          name: coverage\n          path: TestResults/**\n          if-no-files-found: warn\n",
    ".github/workflows/license-check.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: License Header Enforcement\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  license-check:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up Python\n        uses: actions/setup-python@v7\n        with:\n          python-version: \"3.x\"\n\n      - name: Set up just\n        uses: extractions/setup-just@v4\n\n      - name: Run PolyForm header check\n        run: just license-check\n",
    ".github/workflows/dependabot-automerge.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Dependabot auto-merge\n\non:\n  pull_request_target:\n    types: [opened, synchronize, reopened]\n\npermissions:\n  contents: write\n  pull-requests: write\n\njobs:\n  auto-merge:\n    if: github.actor == 'dependabot[bot]'\n    runs-on: ubuntu-latest\n    steps:\n      # No checkout here: with pull_request_target the job runs in the base\n      # context, so PR code is never executed. --auto queues a squash merge\n      # that GitHub performs only after all checks (just check) pass.\n      - name: Enable auto-merge (squash) once checks pass\n        env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n          PR_URL: ${{ github.event.pull_request.html_url }}\n        run: gh pr merge --auto --squash \"$PR_URL\"\n",
    ".github/workflows/release.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Release\n\non:\n  push:\n    tags: [ \"v*\" ]\n  workflow_dispatch:\n\npermissions:\n  contents: write\n\njobs:\n  release:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n        with:\n          fetch-depth: 0\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Set up just\n        uses: extractions/setup-just@v4\n\n      - name: Restore tools and packages\n        run: just setup\n\n      - name: Determine version\n        run: just version\n\n      - name: Build\n        run: just build\n\n      - name: Test\n        run: just test\n\n      - name: Pack libraries\n        run: just pack\n\n      - name: Generate SBOM (CycloneDX JSON)\n        run: just sbom\n\n      - name: Upload packages artifact\n        uses: actions/upload-artifact@v7\n        with:\n          name: packages\n          path: artifacts/packages/*\n\n      - name: Upload coverage artifact\n        if: always()\n        uses: actions/upload-artifact@v7\n        with:\n          name: coverage\n          path: TestResults/**\n          if-no-files-found: warn\n\n      - name: Upload SBOM artifact\n        uses: actions/upload-artifact@v7\n        with:\n          name: sbom\n          path: artifacts/sbom/bom.json\n          if-no-files-found: error\n\n      - name: GitHub Release\n        if: startsWith(github.ref, 'refs/tags/')\n        uses: softprops/action-gh-release@v3\n        with:\n          generate_release_notes: true\n          files: |\n            artifacts/packages/*\n            artifacts/sbom/bom.json\n",
    ".github/workflows/docs.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Docs\n\non:\n  push:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  pull_request:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  workflow_dispatch:\n\npermissions:\n  contents: read\n  pages: write\n  id-token: write\n\nconcurrency:\n  group: pages\n  cancel-in-progress: false\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Set up just\n        uses: extractions/setup-just@v4\n\n      - name: Restore tools and packages\n        run: just setup\n\n      - name: Build docs\n        # NOTE: requires repo Settings -> Pages -> Source = \"GitHub Actions\" (one-time manual step).\n        # PRs build strictly; main pushes build normally then deploy.\n        run: |\n          if [ \"${{ github.event_name }}\" = \"pull_request\" ]; then\n            just docs --warningsAsErrors\n          else\n            just docs\n          fi\n\n      - name: Add .nojekyll\n        run: cp docs/.nojekyll docs/_site/.nojekyll\n\n      - name: Upload Pages artifact\n        uses: actions/upload-pages-artifact@v5\n        with:\n          path: docs/_site\n\n  deploy:\n    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'\n    needs: build\n    runs-on: ubuntu-latest\n    environment:\n      name: github-pages\n      url: ${{ steps.deployment.outputs.page_url }}\n    steps:\n      - name: Deploy to GitHub Pages\n        id: deployment\n        uses: actions/deploy-pages@v5\n",
    "README.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# {{repo}}\n\n[![Build](https://github.com/{{owner}}/{{repo}}/actions/workflows/build.yml/badge.svg)](https://github.com/{{owner}}/{{repo}}/actions/workflows/build.yml)\n[![Docs](https://github.com/{{owner}}/{{repo}}/actions/workflows/docs.yml/badge.svg)](https://{{owner}}.github.io/{{repo}}/)\n[![License Header Enforcement](https://github.com/{{owner}}/{{repo}}/actions/workflows/license-check.yml/badge.svg)](https://github.com/{{owner}}/{{repo}}/actions/workflows/license-check.yml)\n[![Release](https://github.com/{{owner}}/{{repo}}/actions/workflows/release.yml/badge.svg)](https://github.com/{{owner}}/{{repo}}/actions/workflows/release.yml)\n\nA suite of .NET 10 command-line tools and shared libraries.\n\n## Apps (`src/apps`)\n\n| App | Description |\n|-----|-------------|\n| `tooling-cli` | General tooling entry point |\n| `datasync-cli` | Data synchronization tool |\n| `reporting-cli` | Reporting tool |\n\n## Libraries (`src/libs`)\n\n| Library | Description |\n|---------|-------------|\n| `shared-kernel` | Shared domain primitives |\n| `logging` | Logging abstractions |\n| `cli-runtime` | CLI hosting runtime |\n\n## Prerequisites\n\n- .NET SDK `{{dotnet_sdk_pin}}` or newer 10.0.x (pinned in `global.json`\n  with `rollForward: latestFeature`; also listed in `perster.json`)\n- `just`, `lefthook`, Python 3.x, PowerShell (`pwsh`) for hooks\n- PowerShell modules (`Pester`, `PlatyPS`, `PSDepend`) and tools\n  (`just`, `lefthook`, `gitleaks`) listed in `perster.json`\n- Local .NET tools restore automatically via `just setup`\n  (`docfx`, `GitVersion.Tool`, `CycloneDX`, `ReportGenerator`\n  in `.config/dotnet-tools.json`; `dotnet format` ships with the SDK)\n\n## Usage\n\n```sh\njust setup          # restore local tools + NuGet packages\njust check          # PR validation: format, license, build, test, pack\njust build          # build solution (Release)\njust test           # run tests with coverage into TestResults/\njust pack           # pack libraries into artifacts/packages/\njust format         # apply dotnet format\njust format-check   # verify formatting without modifying files\njust license-check  # verify PolyForm license headers\njust license-inject # add missing PolyForm license headers\njust docs           # build DocFX site\njust docs-serve     # serve DocFX site locally\njust version        # show GitVersion\njust sbom           # CycloneDX SBOM into artifacts/sbom/ (release only)\n```\n\nRun `just check` before opening a PR; CI runs the same command.\nLibraries in `src/libs` enable package validation on `pack`.\nReleases are cut from `v*` tags; see [CONTRIBUTING](CONTRIBUTING.md).\n\n## License\n\nPolyForm Noncommercial License 1.0.0 — see [LICENSE](LICENSE) and\n[NOTICE.md](NOTICE.md).\n",
    "TODO.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# TODO\n\n## Build\n\n- [ ]\n\n## Docs\n\n- [x] DocFX site live on GitHub Pages\n\n## Apps\n\n- [ ]\n\n## Libraries\n\n- [ ]\n\n## CI / Release\n\n- [ ]\n",
    "CONTRIBUTING.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Contributing\n\n## Setup\n\n```sh\njust setup        # dotnet tool restore + dotnet restore\nlefthook install  # enable pre-commit / commit-msg / pre-push hooks\n```\n\nRequires .NET SDK 10.0.x (see `global.json`), `just`, `lefthook`,\nPython 3.x, and `pwsh`.\n\n## Commits\n\nUse [Conventional Commits](https://www.conventionalcommits.org/)\n(e.g. `feat(tooling-cli): ...`). Commit messages are validated by\n`build/scripts/validate-commit.ps1` (also wired as the `commit-msg` hook).\n\n## Checks\n\nRun before pushing:\n\n```sh\njust check  # format-check + license-check + build + test + pack\n```\n\n- `just format` applies formatting (`dotnet format`, ships with the SDK);\n  `just format-check` verifies without modifying files (used by CI/pre-commit).\n- `just test` runs `dotnet test` with XPlat coverage into `TestResults/`;\n  use `just coverage-report` (ReportGenerator) for HTML output.\n  New test projects should reference `coverlet.collector` so coverage\n  collection works out of the box.\n- `just pack` packs only `src/libs/*` (`IsPackable=true` with\n  `EnablePackageValidation`); apps set `IsPackable=false`.\n- `just version` shows the GitVersion (ContinuousDelivery).\n- `just sbom` generates CycloneDX JSON (release only, not part of `check`).\n\n## License headers\n\nEvery source file must carry the PolyForm Noncommercial License 1.0.0\nheader. Before pushing, run:\n\n```sh\njust license-inject   # add any missing headers\njust license-check    # verify; must exit 0\n```\n\nCI enforces this via `.github/workflows/license-check.yml`.\nGenerated output (`bin/`, `obj/`, `artifacts/`, `TestResults/`,\n`docs/_site/`, `docs/api/*.yml`) is excluded from the check.\n\n## Pull requests\n\nKeep PRs focused, ensure `just check` passes, and update the\nrelevant per-app `CHANGELOG.md`.\n\nCI (`build.yml`) runs `just check` plus a coverage artifact.\nDocs deploy from `main` via `docs.yml`. Releases are cut from `v*`\ntags (or manual dispatch): version, build, test, pack, SBOM,\nartifacts, then a GitHub Release with generated notes.\nDependabot (weekly, grouped) covers NuGet, GitHub Actions, and the\n.NET SDK pin in `global.json`, and its PRs auto-merge (squash) once\n`just check` passes.\n",
    "SECURITY.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Security Policy\n\n## Reporting a vulnerability\n\nPlease report vulnerabilities via a private\n[GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)\nfor this repository. Do not open a public issue for security reports.\n\n## Scope\n\nSupported: the latest `main` branch of `src/apps/*` and `src/libs/*`.\n",
    "NOTICE.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Notices\n\nCopyright (c) 2026 {{holder}}.\n\nThis project is licensed under the PolyForm Noncommercial License\n1.0.0. See [LICENSE](LICENSE) for the full license text.\n\nYou may use this software for non-commercial purposes only.\n",
    "LICENSE": "# PolyForm Noncommercial License 1.0.0\n\nhttps://polyformproject.org/licenses/noncommercial/1.0.0\n\n## Acceptance\n\nIn order to get any license under these terms, you must agree\nto them as both your obligations and as conditions that your\npermissions can't be used without.\n\n## Copyright License\n\nLicensor grants you a copyright license for the\nsoftware, defined as the source code files that the\nlicensor makes available under these terms.\n\nYou may use the software for non-commercial purposes.\n\n## Non-Commercial Use\n\n\"Non-commercial\" means use that is not primarily intended\nfor or directed toward commercial advantage or monetary\ncompensation. For purposes of this license, \"commercial\"\nincludes any use of the software in connection with any\nbusiness, consulting, or revenue-generating activity.\n\n## Patent License\n\nLicensor grants you a patent license for the software,\nto the extent that any patent claims are necessarily\ninfringed by making, using, or selling the software.\n\n## Fair Use\n\nThe licensor reserves all rights not expressly granted\nin these terms. Fair use, first sale, and other\nlimitations of copyright law remain applicable.\n\n## No Other Rights\n\nThese terms do not grant any rights other than those\nexpressly stated. No trademark rights are granted.\n\n## Distribution\n\nYou may distribute the software under these terms,\nprovided that you include a copy of these terms and\na clear indication that the software is subject to\nthe PolyForm Noncommercial License 1.0.0.\n\n## Modified Software\n\nYou may create modified versions of the software and\ndistribute them under these terms.\n\n## Termination\n\nIf you violate any term of this license, your rights\nterminate automatically.\n\n## No Warranty\n\nThe software is provided \"as is\" without warranty of\nany kind.\n\n## Limitation of Liability\n\nThe licensor shall not be liable for any damages\narising from the use of the software.\n",
    "Justfile": "sln := \"{{repo}}.slnx\"\nconfig := \"Release\"\npython := env_var_or_default(\"PYTHON\", \"python3\")\npackages := \"artifacts/packages\"\nsbom_dir := \"artifacts/sbom\"\n\ndefault:\n    @just --list\n\n# Bootstrap a fresh clone: restore local tools and NuGet packages.\nsetup:\n    dotnet tool restore\n    dotnet restore {{sln}}\n    @echo \"Setup complete. Run 'lefthook install' to enable git hooks.\"\n\nrestore:\n    dotnet restore {{sln}}\n\nbuild:\n    dotnet build {{sln}} --configuration {{config}}\n\n# Runs tests if any exist; succeeds when no test projects are present.\n# Collects XPlat code coverage into TestResults/.\ntest:\n    dotnet test {{sln}} --configuration {{config}} --collect:\"XPlat Code Coverage\" --results-directory TestResults\n\n# Pack only packable projects (libs). Apps set IsPackable=false.\npack:\n    dotnet pack {{sln}} --configuration {{config}} --output {{packages}}\n\n# PR validation: formatting, licenses, build, tests, package validation (via pack).\ncheck: format-check license-check build test pack\n\nformat:\n    dotnet format {{sln}}\n\nformat-check:\n    dotnet format {{sln}} --verify-no-changes\n\nlicense-inject:\n    {{python}} scripts/polyform_injector.py\n\nlicense-check:\n    {{python}} scripts/polyform_injector.py --check\n\npre-commit: format-check license-check\n\nversion:\n    dotnet tool run dotnet-gitversion\n\n# Generate HTML coverage report from TestResults (requires test run first).\ncoverage-report:\n    dotnet reportgenerator -reports:\"TestResults/**/coverage.cobertura.xml\" -targetdir:\"artifacts/coverage\" -reporttypes:Html\n\n# Generate CycloneDX SBOM (JSON) for release artifacts. Not part of `check`.\nsbom:\n    dotnet dotnet-CycloneDX {{sln}} --output {{sbom_dir}} --output-format json\n\ndocs-install:\n    dotnet tool restore\n\ndocs-build: docs\n\ndocs *args:\n    dotnet docfx docs/docfx.json {{args}}\n\ndocs-serve *args:\n    dotnet docfx docs/docfx.json --serve {{args}}\n",
    "global.json": "{\n  \"sdk\": {\n    \"version\": \"{{dotnet_sdk_pin}}\",\n    \"rollForward\": \"latestFeature\"\n  }\n}\n",
    ".config/dotnet-tools.json": "{\n  \"version\": 1,\n  \"isRoot\": true,\n  \"tools\": {\n    \"docfx\": {\n      \"version\": \"2.81.0\",\n      \"commands\": [\n        \"docfx\"\n      ]\n    },\n    \"gitversion.tool\": {\n      \"version\": \"6.8.2\",\n      \"commands\": [\n        \"dotnet-gitversion\"\n      ]\n    },\n    \"cyclonedx\": {\n      \"version\": \"6.2.0\",\n      \"commands\": [\n        \"dotnet-CycloneDX\"\n      ]\n    },\n    \"dotnet-reportgenerator-globaltool\": {\n      \"version\": \"5.5.11\",\n      \"commands\": [\n        \"reportgenerator\"\n      ]\n    }\n  }\n}\n",
    ".github/dependabot.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nversion: 2\nupdates:\n  - package-ecosystem: \"nuget\"\n    directory: \"/\"\n    schedule:\n      interval: \"weekly\"\n    groups:\n      nuget:\n        patterns:\n          - \"*\"\n  - package-ecosystem: \"github-actions\"\n    directory: \"/\"\n    schedule:\n      interval: \"weekly\"\n    groups:\n      actions:\n        patterns:\n          - \"*\"\n  - package-ecosystem: \"dotnet-sdk\"\n    directory: \"/\"\n    schedule:\n      interval: \"weekly\"\n",
})

# --- Per-app templates (rendered once per app via collect_files) ---
_APP_TEMPLATES: dict[str, str] = {
    "src/apps/{{app}}/{{app}}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n'
        '  <PropertyGroup>\n'
        '    <OutputType>Exe</OutputType>\n'
        '    <TargetFramework>{{dotnet_tfm}}</TargetFramework>\n'
        '    <IsPackable>false</IsPackable>\n'
        '  </PropertyGroup>\n'
        '  <ItemGroup>\n'
        '{{lib_refs}}\n'
        '  </ItemGroup>\n'
        '  <ItemGroup>\n'
        '    <PackageReference Include="System.CommandLine" Version="2.0.12" />\n'
        '    <PackageReference Include="Microsoft.Extensions.DependencyInjection" Version="10.0.12" />\n'
        '    <PackageReference Include="Microsoft.Extensions.Logging" Version="10.0.12" />\n'
        '    <PackageReference Include="Microsoft.Extensions.Logging.Console" Version="10.0.12" />\n'
        '  </ItemGroup>\n'
        '</Project>\n',
    "src/apps/{{app}}/Program.cs": '// Copyright (c) 2026 {{holder}}\n'
        '// Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        'using System;\n'
        'using System.CommandLine;\n'
        'using Microsoft.Extensions.Logging;\n'
        '\n'
        'var root = new RootCommand("{{app}}");\n'
        '\n'
        'root.SetAction(_ =>\n'
        '{\n'
        '    Console.WriteLine("{{app}} is running.");\n'
        '});\n'
        '\n'
        'return await root.Parse(args).InvokeAsync();\n',
}

# --- Per-lib templates (rendered once per lib via collect_files) ---
_LIB_TEMPLATES: dict[str, str] = {
    "src/libs/{{lib}}/{{lib}}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n'
        '  <PropertyGroup>\n'
        '    <TargetFramework>{{dotnet_tfm}}</TargetFramework>\n'
        '    <IsPackable>true</IsPackable>\n'
        '    <EnablePackageValidation>true</EnablePackageValidation>\n'
        '  </PropertyGroup>\n'
        '</Project>\n',
    "src/libs/{{lib}}/Class1.cs": '// Copyright (c) 2026 {{holder}}\n'
        '// Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        'namespace {{namespace}};\n'
        '\n'
        'public class Class1\n'
        '{\n'
        '}\n',
}

# --- DocFX templates ---
_DOCFX_TEMPLATES: dict[str, str] = {
    "docs/docfx.json": '{\n'
        '  "metadata": [\n'
        '    {\n'
        '      "src": [\n'
        '        {\n'
        '          "files": [\n'
        '{{metadata_files}}\n'
        '          ],\n'
        '          "src": ".."\n'
        '        }\n'
        '      ],\n'
        '      "dest": "api",\n'
        '      "properties": {\n'
        '        "TargetFramework": "{{dotnet_tfm}}",\n'
        '        "Configuration": "Release"\n'
        '      }\n'
        '    }\n'
        '  ],\n'
        '  "build": {\n'
        '    "content": [\n'
        '      {\n'
        '        "files": ["api/*.yml", "api/index.md"]\n'
        '      },\n'
        '      {\n'
        '        "files": ["articles/*.md", "articles/toc.yml", "toc.yml", "*.md"]\n'
        '      }\n'
        '    ],\n'
        '    "resource": [\n'
        '      {\n'
        '        "files": ["images/**"]\n'
        '      }\n'
        '    ],\n'
        '    "dest": "_site",\n'
        '    "globalMetadata": {\n'
        '      "_appTitle": "{{repo}}",\n'
        '      "_appBasePath": "/{{repo}}/",\n'
        '      "_enableSearch": true\n'
        '    },\n'
        '    "template": ["default", "modern"],\n'
        '    "sitemap": {\n'
        '      "baseUrl": "https://{{owner}}.github.io/{{repo}}",\n'
        '      "changefreq": "weekly",\n'
        '      "priority": 0.5\n'
        '    }\n'
        '  }\n'
        '}\n',
    "docs/index.md": '<!--\n'
        'Copyright (c) 2026 {{holder}}\n'
        'Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        '-->\n'
        '\n'
        '---\n'
        'title: {{repo}}\n'
        'description: Documentation for the {{repo}} .NET 10 CLI tools and libraries.\n'
        '---\n'
        '\n'
        '# {{repo}}\n'
        '\n'
        'A suite of .NET 10 command-line tools and shared libraries.\n'
        '\n'
        '- [Articles](articles/intro.md): concepts and guides.\n'
        '- [API Reference](api/index.md): auto-generated from source and XML doc comments.\n'
        '\n'
        '## Projects\n'
        '\n'
        '| Area | Projects |\n'
        '|------|----------|\n'
        '| Apps | {{readme_apps_row}} |\n'
        '| Libraries | {{readme_libs_row}} |\n',
    "docs/toc.yml": '# Copyright (c) 2026 {{holder}}\n'
        '# Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        '- name: Home\n'
        '  href: index.md\n'
        '- name: Articles\n'
        '  href: articles/toc.yml\n'
        '- name: API Reference\n'
        '  href: api/index.md\n',
    "docs/api/index.md": '<!--\n'
        'Copyright (c) 2026 {{holder}}\n'
        'Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        '-->\n'
        '\n'
        '# API Reference\n'
        '\n'
        'Auto-generated from `src/apps/*` and `src/libs/*`. Select a namespace in the table of contents.\n',
    "docs/articles/toc.yml": '# Copyright (c) 2026 {{holder}}\n'
        '# Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        '- name: Introduction\n'
        '  href: intro.md\n',
    "docs/articles/intro.md": '<!--\n'
        'Copyright (c) 2026 {{holder}}\n'
        'Licensed under the PolyForm Noncommercial License 1.0.0\n'
        '\n'
        '-->\n'
        '\n'
        '# Introduction\n'
        '\n'
        'This site documents `{{repo}}`: three CLI apps ({{readme_apps_row}}) and three libraries ({{readme_libs_row}}).\n'
        '\n'
        'API pages are generated from the projects under `src/` and their XML documentation comments. Add `///` doc comments to public APIs to improve the reference.\n',
    "docs/.nojekyll": "",
    "docs/images/.gitkeep": "",
}

# --- Polyform injector (verbatim, no placeholder substitution) ---
_polyform_src = Path(__file__).resolve().parent / "polyform_injector.py"
TEMPLATES["scripts/polyform_injector.py"] = _polyform_src.read_text(encoding="utf-8")

def collect_files(cfg: Config) -> dict[str, str]:
    ctx = build_context(cfg)
    # Files copied byte-for-byte (no placeholder substitution).
    verbatim = {"LICENSE"}
    # Files mixing template placeholders with foreign {{...}} syntax:
    # docs.yml and dependabot-automerge.yml have GitHub Actions ${{...}}
    # expressions, Justfile has Just {{...}} interpolations. Substitute
    # known keys manually, leave the foreign expressions alone.
    manual = {
        ".github/workflows/docs.yml",
        ".github/workflows/dependabot-automerge.yml",
        "Justfile",
    }
    files = {}
    for rel, tpl in TEMPLATES.items():
        if rel in verbatim:
            files[rel] = tpl
        elif rel in manual:
            out = tpl
            for key in sorted(ctx, key=len, reverse=True):
                out = out.replace("{{" + key + "}}", ctx[key])
            files[rel] = out
        else:
            files[rel] = render(tpl, ctx)
    # --- Per-app templates ---
    for a in cfg.apps:
        app_ctx = ctx | {"app": a, "lib_refs": lib_refs(cfg)}
        for rel_tpl, tpl in _APP_TEMPLATES.items():
            rel = render(rel_tpl, app_ctx)
            files[rel] = render(tpl, app_ctx)
    # --- Per-lib templates ---
    for l in cfg.libs:
        lib_ctx = ctx | {"lib": l, "namespace": l.replace("-", "")}
        for rel_tpl, tpl in _LIB_TEMPLATES.items():
            rel = render(rel_tpl, lib_ctx)
            files[rel] = render(tpl, lib_ctx)
    # --- DocFX templates ---
    for rel, tpl in _DOCFX_TEMPLATES.items():
        files[rel] = render(tpl, ctx)
    # --- Solution file (name follows repo; folders mirror `dotnet sln add`) ---
    slnx_lines = ["<Solution>", '  <Folder Name="/src/" />']
    if cfg.apps:
        slnx_lines.append('  <Folder Name="/src/apps/">')
        for a in sorted(cfg.apps):
            slnx_lines.append(f'    <Project Path="src/apps/{a}/{a}.csproj" />')
        slnx_lines.append("  </Folder>")
    if cfg.libs:
        slnx_lines.append('  <Folder Name="/src/libs/">')
        for l in sorted(cfg.libs):
            slnx_lines.append(f'    <Project Path="src/libs/{l}/{l}.csproj" />')
        slnx_lines.append("  </Folder>")
    slnx_lines.append("</Solution>")
    files[f"{cfg.repo}.slnx"] = "\n".join(slnx_lines) + "\n"
    # --- Skip docs/ under --no-docs ---
    if cfg.no_docs:
        files.pop(".github/workflows/docs.yml", None)
        files = {k: v for k, v in files.items() if not k.startswith("docs/")}
        if ".gitignore" in files:
            files[".gitignore"] = "\n".join(
                line for line in files[".gitignore"].split("\n")
                if not line.startswith("docs/api/")
            )
        if "Justfile" in files:
            lines = files["Justfile"].split("\n")
            drop_start = None
            for i, line in enumerate(lines):
                if line.startswith("docs-install:"):
                    drop_start = i
                    break
            if drop_start is not None:
                lines = lines[:drop_start]
            files["Justfile"] = "\n".join(lines)
        if "README.md" in files:
            files["README.md"] = "\n".join(
                line for line in files["README.md"].split("\n")
                if not line.startswith("[![Docs](")
            )
    return files

def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"COMMAND-FAILED: {' '.join(cmd)} (exit {e.returncode})")
        print((e.stdout or "")[-2000:])
        print((e.stderr or "")[-2000:])
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(f"COMMAND-NOT-FOUND: {cmd[0]}")
        sys.exit(127)

def require_tools(need_gh: bool) -> None:
    run(["git", "--version"])
    if shutil.which("dotnet") is None:
        print("WARNING: dotnet not found; local builds will be unavailable (scaffolding continues)")
    if need_gh:
        run(["gh", "auth", "status"])

def self_test() -> int:
    if not TEMPLATES:
        print("SELFTEST-FAIL: no templates registered")
        return 1
    cfg = Config(repo="dotnet-tools-suite", owner="ckir", holder="Costas Kirgoussios")
    rendered = collect_files(cfg)
    live_dir = Path(__file__).resolve().parent.parent
    check_files = [
        ".gitignore",
        "Directory.Build.props",
        "GitVersion.yml",
        ".gitattributes",
        "lefthook.yml",
        "perster.json",
        ".github/workflows/build.yml",
        ".github/workflows/license-check.yml",
        ".github/workflows/dependabot-automerge.yml",
        ".github/workflows/release.yml",
        ".github/workflows/docs.yml",
        ".github/dependabot.yml",
        ".config/dotnet-tools.json",
        "global.json",
        f"{cfg.repo}.slnx",
        "Justfile",
        "README.md",
    ]
    any_diff = False
    for rel in check_files:
        live_text = (live_dir / rel).read_text(encoding="utf-8")
        rendered_text = rendered[rel]
        diff_text = "".join(difflib.unified_diff(
            live_text.splitlines(keepends=True),
            rendered_text.splitlines(keepends=True),
            fromfile=f"live/{rel}",
            tofile=f"rendered/{rel}",
        ))
        if diff_text:
            any_diff = True
            print(f"--- {rel} differs ---")
            try:
                print(diff_text)
            except UnicodeEncodeError:
                pass
    # --- src/libs/*: zero diff against live ---
    for l in cfg.libs:
        for suffix in (".csproj", "/Class1.cs"):
            if suffix == "/Class1.cs":
                rel = f"src/libs/{l}/Class1.cs"
            else:
                rel = f"src/libs/{l}/{l}{suffix}"
            live_text = (live_dir / rel).read_text(encoding="utf-8")
            rendered_text = rendered[rel]
            diff_text = "".join(difflib.unified_diff(
                live_text.splitlines(keepends=True),
                rendered_text.splitlines(keepends=True),
                fromfile=f"live/{rel}",
                tofile=f"rendered/{rel}",
            ))
            if diff_text:
                any_diff = True
                print(f"--- {rel} differs ---")
                try:
                    print(diff_text)
                except UnicodeEncodeError:
                    pass
    # --- scripts/polyform_injector.py: byte-identical, no {{...}} sequences ---
    pf_rel = "scripts/polyform_injector.py"
    pf_rendered = rendered[pf_rel]
    if "{{" in pf_rendered:
        print(f"SELFTEST-FAIL: {pf_rel} contains unresolved placeholders")
        return 1
    pf_live = (live_dir / pf_rel).read_text(encoding="utf-8")
    if pf_rendered != pf_live:
        any_diff = True
        print(f"--- {pf_rel} differs ---")
        diff_text = "".join(difflib.unified_diff(
            pf_live.splitlines(keepends=True),
            pf_rendered.splitlines(keepends=True),
            fromfile=f"live/{pf_rel}",
            tofile=f"rendered/{pf_rel}",
        ))
        try:
            print(diff_text)
        except UnicodeEncodeError:
            pass
    # --- docs/*: zero diff against live ---
    for rel, tpl in _DOCFX_TEMPLATES.items():
        live_path = live_dir / rel
        if not live_path.exists():
            any_diff = True
            print(f"--- {rel} missing in live ---")
            continue
        live_text = live_path.read_text(encoding="utf-8")
        rendered_text = rendered[rel]
        diff_text = "".join(difflib.unified_diff(
            live_text.splitlines(keepends=True),
            rendered_text.splitlines(keepends=True),
            fromfile=f"live/{rel}",
            tofile=f"rendered/{rel}",
        ))
        if diff_text:
            any_diff = True
            print(f"--- {rel} differs ---")
            try:
                print(diff_text)
            except UnicodeEncodeError:
                pass
    # --- tooling-cli.csproj allowlist: canonical differs from live by design ---
    tooling_csproj = "src/apps/tooling-cli/tooling-cli.csproj"
    tooling_rendered = rendered[tooling_csproj]
    tooling_live = (live_dir / tooling_csproj).read_text(encoding="utf-8")
    tooling_diff = "".join(difflib.unified_diff(
        tooling_live.splitlines(keepends=True),
        tooling_rendered.splitlines(keepends=True),
        fromfile=f"live/{tooling_csproj}",
        tofile=f"rendered/{tooling_csproj}",
    ))
    if not tooling_diff:
        print(f"SELFTEST-FAIL: {tooling_csproj} should differ from canonical template")
        return 1
    if "ProjectReference" not in tooling_diff:
        print(f"SELFTEST-FAIL: {tooling_csproj} diff should contain ProjectReference")
        return 1
    if any_diff:
        print("SELFTEST-FAIL: differences found")
        return 1
    # --- Rendered-tree header check ---
    with tempfile.TemporaryDirectory(prefix="scaffold-") as tmp:
        tmp_root = Path(tmp)
        write_tree(tmp_root, rendered)
        polyform_path = tmp_root / "scripts" / "polyform_injector.py"
        result = os.system(f'python3 "{polyform_path}" --check')
        if result != 0:
            print("SELFTEST-FAIL: header check failed in rendered tree")
            return 1
    print("SELFTEST-PASS")
    return 0

def main() -> int:
    cfg = parse_args()
    if "--self-test" in sys.argv:
        return self_test()

    # --- Validate tools ---
    need_gh = not cfg.skip_create
    require_tools(need_gh)

    # --- Resolve --owner empty via gh ---
    if not cfg.owner:
        try:
            r = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, check=True)
            cfg.owner = r.stdout.strip().strip('"').strip("'")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ERROR: --owner is empty and 'gh api user' failed")
            sys.exit(1)
    if not cfg.holder:
        cfg.holder = cfg.owner

    # --- Validate names ---
    name_re = re.compile(r"^[A-Za-z0-9._-]+$")
    if not cfg.repo or not name_re.match(cfg.repo):
        print(f"BAD-NAME: repo '{cfg.repo}' must match ^[A-Za-z0-9._-]+$ (no path separators or '..')")
        sys.exit(2)
    if not cfg.owner or not name_re.match(cfg.owner):
        print(f"BAD-NAME: owner '{cfg.owner}' must match ^[A-Za-z0-9._-]+$ (no path separators or '..')")
        sys.exit(2)

    # --- Refuse non-empty --target-dir ---
    target = Path(cfg.target_dir)
    if target.exists() and any(target.iterdir()):
        print("TARGET-NOT-EMPTY: target directory is not empty")
        sys.exit(2)

    # --- Render and write ---
    files = collect_files(cfg)
    print(f"scaffolding {cfg.repo} (templates: {len(files)})")
    write_tree(target, files)

    # --- Git init and commit ---
    run(["git", "init", "-b", "main"], cwd=target)
    run(["git", "add", "-A"], cwd=target)
    run(["git", "commit", "-m", "feat: initial commit from scaffold"], cwd=target)

    # --- Create/push flow ---
    owner = cfg.owner
    repo = cfg.repo
    if cfg.skip_create:
        visibility = "--public" if cfg.public else "--private"
        print(f"gh repo create {owner}/{repo} {visibility} --source {target} --push")
    else:
        visibility = "--public" if cfg.public else "--private"
        print(f"REMOTE-CREATE: gh repo create {owner}/{repo} {visibility} --source {target} --push")
        run(["gh", "repo", "create", f"{owner}/{repo}", visibility, "--source", str(target), "--push"], cwd=target)

    # --- Verify loop ---
    if not cfg.skip_verify and not cfg.skip_create:
        print("\nManual steps to verify:")
        print(f"  1. Enable GitHub Pages: Settings → Pages → Source = \"GitHub Actions\"")
        print(f"  2. Check docs workflow: gh run list --workflow=docs.yml --limit 1")
        print(f"  3. Visit site: https://{owner}.github.io/{repo}/")

        steps = [
            ("Pages source", ["gh", "api", f"repos/{owner}/{repo}/pages", "--jq", ".build_type"], "workflow"),
            ("Docs run green", ["gh", "run", "list", "--workflow=docs.yml", "--limit", "1", "--json", "conclusion", "--jq", ".[0].conclusion"], "success"),
            ("Live site", f"https://{owner}.github.io/{repo}/", None),
        ]

        for name, cmd, expected in steps:
            while True:
                print(f"\n--- {name} ---")
                choice = input("[Enter] to check, 's' to skip: ").strip().lower()
                if choice == "s":
                    break
                if expected is None:
                    # urllib check for live site
                    try:
                        resp = urllib.request.urlopen(cmd, timeout=30)
                        status = resp.status
                        if status == 200:
                            print(f"OK: {status}")
                            break
                        else:
                            print(f"Unexpected status: {status}")
                    except Exception as e:
                        print(f"FAILED: {e}")
                else:
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        actual = r.stdout.strip().strip('"')
                        if actual == expected:
                            print(f"OK: {actual}")
                            break
                        else:
                            print(f"Expected '{expected}', got '{actual}'")
                    except subprocess.CalledProcessError as e:
                        print(f"FAILED: {e}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
