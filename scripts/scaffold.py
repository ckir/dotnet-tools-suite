#!/usr/bin/env python3
# Copyright (c) 2026 Costas Kirgoussios
# Licensed under the PolyForm Noncommercial License 1.0.0

"""Scaffold a dotnet-tools-suite-style monorepo. Stdlib only; requires git + gh."""
import argparse
import difflib
import os
import sys
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

def app_restore_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet restore src/apps/{a}/{a}.csproj" for a in cfg.apps)

def app_build_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet build src/apps/{a}/{a}.csproj --configuration Release --no-restore" for a in cfg.apps)

def metadata_files(cfg: Config) -> str:
    entries = [f'            "src/apps/{a}/{a}.csproj",' for a in cfg.apps]
    entries += [f'            "src/libs/{l}/{l}.csproj",' for l in cfg.libs]
    entries[-1] = entries[-1].rstrip(",")
    return "\n".join(entries)

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
        "app_restore_lines": app_restore_lines(cfg),
        "app_build_lines": app_build_lines(cfg),
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
    "lefthook.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\n# placeholder Lefthook config\n",
    "perster.json": "{\n  \"dotnet\": \"{{dotnet_sdk_pin}}\",\n  \"pwsh-modules\": [\n    \"Pester\",\n    \"PlatyPS\",\n    \"PSDepend\"\n  ],\n  \"tools\": [\n    \"gitleaks\",\n    \"lefthook\",\n    \"just\"\n  ]\n}\n",
    ".github/workflows/build.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Build\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"10.0.x\"\n\n      - name: Restore\n        run: |\n{{app_restore_lines}}\n\n      - name: Build\n        run: |\n{{app_build_lines}}\n",
    ".github/workflows/license-check.yml": "name: License Header Enforcement\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  license-check:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up Python\n        uses: actions/setup-python@v7\n        with:\n          python-version: \"3.x\"\n\n      - name: Run PolyForm header check\n        run: |\n          python scripts/polyform_injector.py --check\n        continue-on-error: true\n        id: check\n\n      - name: Show diff of missing headers\n        if: steps.check.outcome == 'failure'\n        run: |\n          git --no-pager diff\n\n      - name: Fail if headers missing\n        if: steps.check.outcome == 'failure'\n        run: |\n          echo \"\u274c Missing PolyForm license headers detected.\"\n          exit 1\n\n      - name: Success\n        if: steps.check.outcome == 'success'\n        run: |\n          echo \"\u2714 All files contain PolyForm Noncommercial License 1.0.0 headers.\"\n\n",
    ".github/workflows/release.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Release\n\non:\n  push:\n    tags: [ \"v*\" ]\n  workflow_dispatch:\n\njobs:\n  release:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"10.0.x\"\n\n      - name: Build Release\n        run: |\n          dotnet build src/apps/tooling-cli/tooling-cli.csproj --configuration Release\n          dotnet build src/apps/datasync-cli/datasync-cli.csproj --configuration Release\n          dotnet build src/apps/reporting-cli/reporting-cli.csproj --configuration Release\n\n      - name: Placeholder\n        run: echo \"Release packaging not yet implemented.\"\n",
    ".github/workflows/docs.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Docs\n\non:\n  push:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  pull_request:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  workflow_dispatch:\n\npermissions:\n  contents: read\n  pages: write\n  id-token: write\n\nconcurrency:\n  group: pages\n  cancel-in-progress: false\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Restore\n        run: |\n{{app_restore_lines}}\n\n      - name: Install DocFX\n        run: dotnet tool update -g docfx\n\n      - name: Build docs\n        # NOTE: requires repo Settings -> Pages -> Source = \"GitHub Actions\" (one-time manual step).\n        # PRs build strictly; main pushes build normally then deploy.\n        run: |\n          if [ \"${{ github.event_name }}\" = \"pull_request\" ]; then\n            docfx docs/docfx.json --warningsAsErrors\n          else\n            docfx docs/docfx.json\n          fi\n\n      - name: Add .nojekyll\n        run: cp docs/.nojekyll docs/_site/.nojekyll\n\n      - name: Upload Pages artifact\n        uses: actions/upload-pages-artifact@v3\n        with:\n          path: docs/_site\n\n  deploy:\n    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'\n    needs: build\n    runs-on: ubuntu-latest\n    environment:\n      name: github-pages\n      url: ${{ steps.deployment.outputs.page_url }}\n    steps:\n      - name: Deploy to GitHub Pages\n        id: deployment\n        uses: actions/deploy-pages@v4\n",
    "README.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# {{repo}}\n\n[![Docs](https://github.com/{{owner}}/{{repo}}/actions/workflows/docs.yml/badge.svg)](https://{{owner}}.github.io/{{repo}}/)\n\nA suite of .NET 10 command-line tools and shared libraries.\n\n## Apps (`src/apps`)\n\n| App | Description |\n|-----|-------------|\n| `tooling-cli` | General tooling entry point |\n| `datasync-cli` | Data synchronization tool |\n| `reporting-cli` | Reporting tool |\n\n## Libraries (`src/libs`)\n\n| Library | Description |\n|---------|-------------|\n| `shared-kernel` | Shared domain primitives |\n| `logging` | Logging abstractions |\n| `cli-runtime` | CLI hosting runtime |\n\n## Prerequisites\n\nPinned in `perster.json`: .NET SDK `{{dotnet_sdk_pin}}`, PowerShell modules\n(`Pester`, `PlatyPS`, `PSDepend`), and tools (`just`, `lefthook`,\n`gitleaks`).\n\n## Usage\n\n```sh\njust --list        # show available recipes\njust license-check # verify PolyForm license headers\njust license-inject # add missing PolyForm license headers\n```\n\n## License\n\nPolyForm Noncommercial License 1.0.0 \u2014 see [LICENSE](LICENSE) and\n[NOTICE.md](NOTICE.md).\n",
    "TODO.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# TODO\n\n## Build\n\n- [ ]\n\n## Docs\n\n- [x] DocFX site live on GitHub Pages\n\n## Apps\n\n- [ ]\n\n## Libraries\n\n- [ ]\n\n## CI / Release\n\n- [ ]\n",
    "CONTRIBUTING.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Contributing\n\n## Commits\n\nUse [Conventional Commits](https://www.conventionalcommits.org/)\n(e.g. `feat(tooling-cli): ...`). Commit messages are validated by\n`build/scripts/validate-commit.ps1`.\n\n## License headers\n\nEvery source file must carry the PolyForm Noncommercial License 1.0.0\nheader. Before pushing, run:\n\n```sh\njust license-inject   # add any missing headers\njust license-check    # verify; must exit 0\n```\n\nCI enforces this via `.github/workflows/license-check.yml`.\n\n## Pull requests\n\nKeep PRs focused, ensure `just license-check` passes, and update the\nrelevant per-app `CHANGELOG.md`.\n",
    "SECURITY.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Security Policy\n\n## Reporting a vulnerability\n\nPlease report vulnerabilities via a private\n[GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)\nfor this repository. Do not open a public issue for security reports.\n\n## Scope\n\nSupported: the latest `main` branch of `src/apps/*` and `src/libs/*`.\n",
    "NOTICE.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Notices\n\nCopyright (c) 2026 Costas Kirgoussios.\n\nThis project is licensed under the PolyForm Noncommercial License\n1.0.0. See [LICENSE](LICENSE) for the full license text.\n\nYou may use this software for non-commercial purposes only.\n",
    "LICENSE": "# PolyForm Noncommercial License 1.0.0\n\nhttps://polyformproject.org/licenses/noncommercial/1.0.0\n\n## Acceptance\n\nIn order to get any license under these terms, you must agree\nto them as both your obligations and as conditions that your\npermissions can't be used without.\n\n## Copyright License\n\nLicensor grants you a copyright license for the\nsoftware, defined as the source code files that the\nlicensor makes available under these terms.\n\nYou may use the software for non-commercial purposes.\n\n## Non-Commercial Use\n\n\"Non-commercial\" means use that is not primarily intended\nfor or directed toward commercial advantage or monetary\ncompensation. For purposes of this license, \"commercial\"\nincludes any use of the software in connection with any\nbusiness, consulting, or revenue-generating activity.\n\n## Patent License\n\nLicensor grants you a patent license for the software,\nto the extent that any patent claims are necessarily\ninfringed by making, using, or selling the software.\n\n## Fair Use\n\nThe licensor reserves all rights not expressly granted\nin these terms. Fair use, first sale, and other\nlimitations of copyright law remain applicable.\n\n## No Other Rights\n\nThese terms do not grant any rights other than those\nexpressly stated. No trademark rights are granted.\n\n## Distribution\n\nYou may distribute the software under these terms,\nprovided that you include a copy of these terms and\na clear indication that the software is subject to\nthe PolyForm Noncommercial License 1.0.0.\n\n## Modified Software\n\nYou may create modified versions of the software and\ndistribute them under these terms.\n\n## Termination\n\nIf you violate any term of this license, your rights\nterminate automatically.\n\n## No Warranty\n\nThe software is provided \"as is\" without warranty of\nany kind.\n\n## Limitation of Liability\n\nThe licensor shall not be liable for any damages\narising from the use of the software.\n",
    "Justfile": "python := \"python3\"\n\ndefault:\n    @just --list\n\nlicense-inject:\n    {{python}} scripts/polyform_injector.py\n\nlicense-check:\n    {{python}} scripts/polyform_injector.py --check\n\npre-commit: license-inject\n\ndocs-install:\n    dotnet tool update -g docfx\n\ndocs-build:\n    docfx docs/docfx.json\n\ndocs-serve:\n    docfx docs/docfx.json --serve\n\n",
})

def collect_files(cfg: Config) -> dict[str, str]:
    ctx = build_context(cfg)
    # Files copied byte-for-byte (no placeholder substitution).
    # Justfile uses {{python}} which is Just syntax, not our template syntax.
    verbatim = {"Justfile", "LICENSE"}
    files = {}
    for rel, tpl in TEMPLATES.items():
        if rel in verbatim:
            files[rel] = tpl
        elif rel == ".github/workflows/docs.yml":
            # docs.yml has GitHub Actions ${{...}} expressions that render() would
            # flag as unresolved. Substitute known keys manually, leave ${{ }} alone.
            out = tpl
            for key in sorted(ctx, key=len, reverse=True):
                out = out.replace("{{" + key + "}}", ctx[key])
            files[rel] = out
        else:
            files[rel] = render(tpl, ctx)
    if cfg.no_docs:
        files.pop(".github/workflows/docs.yml", None)
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
        "lefthook.yml",
        "perster.json",
        ".github/workflows/build.yml",
        ".github/workflows/license-check.yml",
        ".github/workflows/release.yml",
        ".github/workflows/docs.yml",
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
    if any_diff:
        print("SELFTEST-FAIL: differences found")
        return 1
    print("SELFTEST-PASS")
    return 0

def main() -> int:
    cfg = parse_args()
    if "--self-test" in sys.argv:
        return self_test()
    print(f"scaffolding {cfg.repo} (templates: {len(TEMPLATES)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
