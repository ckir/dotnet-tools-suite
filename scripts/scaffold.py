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

def app_restore_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet restore src/apps/{a}/{a}.csproj" for a in cfg.apps)

def app_build_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet build src/apps/{a}/{a}.csproj --configuration Release --no-restore" for a in cfg.apps)

def app_release_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet build src/apps/{a}/{a}.csproj --configuration Release" for a in cfg.apps)

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
        "app_restore_lines": app_restore_lines(cfg),
        "app_build_lines": app_build_lines(cfg),
        "app_release_lines": app_release_lines(cfg),
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
    ".github/workflows/build.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Build\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Restore\n        run: |\n{{app_restore_lines}}\n\n      - name: Build\n        run: |\n{{app_build_lines}}\n",
    ".github/workflows/license-check.yml": "name: License Header Enforcement\n\non:\n  push:\n    branches: [ main ]\n  pull_request:\n    branches: [ main ]\n\njobs:\n  license-check:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up Python\n        uses: actions/setup-python@v7\n        with:\n          python-version: \"3.x\"\n\n      - name: Run PolyForm header check\n        run: |\n          python scripts/polyform_injector.py --check\n        continue-on-error: true\n        id: check\n\n      - name: Show diff of missing headers\n        if: steps.check.outcome == 'failure'\n        run: |\n          git --no-pager diff\n\n      - name: Fail if headers missing\n        if: steps.check.outcome == 'failure'\n        run: |\n          echo \"\u274c Missing PolyForm license headers detected.\"\n          exit 1\n\n      - name: Success\n        if: steps.check.outcome == 'success'\n        run: |\n          echo \"\u2714 All files contain PolyForm Noncommercial License 1.0.0 headers.\"\n\n",
    ".github/workflows/release.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Release\n\non:\n  push:\n    tags: [ \"v*\" ]\n  workflow_dispatch:\n\njobs:\n  release:\n    runs-on: ubuntu-latest\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Build Release\n        run: |\n{{app_release_lines}}\n\n      - name: Placeholder\n        run: echo \"Release packaging not yet implemented.\"\n",
    ".github/workflows/docs.yml": "# Copyright (c) {{year}} {{holder}}\n# Licensed under the PolyForm Noncommercial License 1.0.0\n\nname: Docs\n\non:\n  push:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  pull_request:\n    branches: [main]\n    paths:\n      - \"docs/**\"\n      - \"src/**\"\n      - \".github/workflows/docs.yml\"\n  workflow_dispatch:\n\npermissions:\n  contents: read\n  pages: write\n  id-token: write\n\nconcurrency:\n  group: pages\n  cancel-in-progress: false\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v7\n\n      - name: Set up .NET\n        uses: actions/setup-dotnet@v6\n        with:\n          dotnet-version: \"{{dotnet}}\"\n\n      - name: Restore\n        run: |\n{{app_restore_lines}}\n\n      - name: Install DocFX\n        run: dotnet tool update -g docfx\n\n      - name: Build docs\n        # NOTE: requires repo Settings -> Pages -> Source = \"GitHub Actions\" (one-time manual step).\n        # PRs build strictly; main pushes build normally then deploy.\n        run: |\n          if [ \"${{ github.event_name }}\" = \"pull_request\" ]; then\n            docfx docs/docfx.json --warningsAsErrors\n          else\n            docfx docs/docfx.json\n          fi\n\n      - name: Add .nojekyll\n        run: cp docs/.nojekyll docs/_site/.nojekyll\n\n      - name: Upload Pages artifact\n        uses: actions/upload-pages-artifact@v3\n        with:\n          path: docs/_site\n\n  deploy:\n    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'\n    needs: build\n    runs-on: ubuntu-latest\n    environment:\n      name: github-pages\n      url: ${{ steps.deployment.outputs.page_url }}\n    steps:\n      - name: Deploy to GitHub Pages\n        id: deployment\n        uses: actions/deploy-pages@v4\n",
    "README.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# {{repo}}\n\n[![Docs](https://github.com/{{owner}}/{{repo}}/actions/workflows/docs.yml/badge.svg)](https://{{owner}}.github.io/{{repo}}/)\n\nA suite of .NET 10 command-line tools and shared libraries.\n\n## Apps (`src/apps`)\n\n| App | Description |\n|-----|-------------|\n| `tooling-cli` | General tooling entry point |\n| `datasync-cli` | Data synchronization tool |\n| `reporting-cli` | Reporting tool |\n\n## Libraries (`src/libs`)\n\n| Library | Description |\n|---------|-------------|\n| `shared-kernel` | Shared domain primitives |\n| `logging` | Logging abstractions |\n| `cli-runtime` | CLI hosting runtime |\n\n## Prerequisites\n\nPinned in `perster.json`: .NET SDK `{{dotnet_sdk_pin}}`, PowerShell modules\n(`Pester`, `PlatyPS`, `PSDepend`), and tools (`just`, `lefthook`,\n`gitleaks`).\n\n## Usage\n\n```sh\njust --list        # show available recipes\njust license-check # verify PolyForm license headers\njust license-inject # add missing PolyForm license headers\n```\n\n## License\n\nPolyForm Noncommercial License 1.0.0 \u2014 see [LICENSE](LICENSE) and\n[NOTICE.md](NOTICE.md).\n",
    "TODO.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# TODO\n\n## Build\n\n- [ ]\n\n## Docs\n\n- [x] DocFX site live on GitHub Pages\n\n## Apps\n\n- [ ]\n\n## Libraries\n\n- [ ]\n\n## CI / Release\n\n- [ ]\n",
    "CONTRIBUTING.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Contributing\n\n## Commits\n\nUse [Conventional Commits](https://www.conventionalcommits.org/)\n(e.g. `feat(tooling-cli): ...`). Commit messages are validated by\n`build/scripts/validate-commit.ps1`.\n\n## License headers\n\nEvery source file must carry the PolyForm Noncommercial License 1.0.0\nheader. Before pushing, run:\n\n```sh\njust license-inject   # add any missing headers\njust license-check    # verify; must exit 0\n```\n\nCI enforces this via `.github/workflows/license-check.yml`.\n\n## Pull requests\n\nKeep PRs focused, ensure `just license-check` passes, and update the\nrelevant per-app `CHANGELOG.md`.\n",
    "SECURITY.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Security Policy\n\n## Reporting a vulnerability\n\nPlease report vulnerabilities via a private\n[GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories)\nfor this repository. Do not open a public issue for security reports.\n\n## Scope\n\nSupported: the latest `main` branch of `src/apps/*` and `src/libs/*`.\n",
    "NOTICE.md": "<!--\nCopyright (c) {{year}} {{holder}}\nLicensed under the PolyForm Noncommercial License 1.0.0\n\n-->\n\n# Notices\n\nCopyright (c) 2026 {{holder}}.\n\nThis project is licensed under the PolyForm Noncommercial License\n1.0.0. See [LICENSE](LICENSE) for the full license text.\n\nYou may use this software for non-commercial purposes only.\n",
    "LICENSE": "# PolyForm Noncommercial License 1.0.0\n\nhttps://polyformproject.org/licenses/noncommercial/1.0.0\n\n## Acceptance\n\nIn order to get any license under these terms, you must agree\nto them as both your obligations and as conditions that your\npermissions can't be used without.\n\n## Copyright License\n\nLicensor grants you a copyright license for the\nsoftware, defined as the source code files that the\nlicensor makes available under these terms.\n\nYou may use the software for non-commercial purposes.\n\n## Non-Commercial Use\n\n\"Non-commercial\" means use that is not primarily intended\nfor or directed toward commercial advantage or monetary\ncompensation. For purposes of this license, \"commercial\"\nincludes any use of the software in connection with any\nbusiness, consulting, or revenue-generating activity.\n\n## Patent License\n\nLicensor grants you a patent license for the software,\nto the extent that any patent claims are necessarily\ninfringed by making, using, or selling the software.\n\n## Fair Use\n\nThe licensor reserves all rights not expressly granted\nin these terms. Fair use, first sale, and other\nlimitations of copyright law remain applicable.\n\n## No Other Rights\n\nThese terms do not grant any rights other than those\nexpressly stated. No trademark rights are granted.\n\n## Distribution\n\nYou may distribute the software under these terms,\nprovided that you include a copy of these terms and\na clear indication that the software is subject to\nthe PolyForm Noncommercial License 1.0.0.\n\n## Modified Software\n\nYou may create modified versions of the software and\ndistribute them under these terms.\n\n## Termination\n\nIf you violate any term of this license, your rights\nterminate automatically.\n\n## No Warranty\n\nThe software is provided \"as is\" without warranty of\nany kind.\n\n## Limitation of Liability\n\nThe licensor shall not be liable for any damages\narising from the use of the software.\n",
    "Justfile": "python := \"python3\"\n\ndefault:\n    @just --list\n\nlicense-inject:\n    {{python}} scripts/polyform_injector.py\n\nlicense-check:\n    {{python}} scripts/polyform_injector.py --check\n\npre-commit: license-inject\n\ndocs-install:\n    dotnet tool update -g docfx\n\ndocs-build:\n    docfx docs/docfx.json\n\ndocs-serve:\n    docfx docs/docfx.json --serve\n\n",
})

# --- Per-app templates (rendered once per app via collect_files) ---
_APP_TEMPLATES: dict[str, str] = {
    "src/apps/{{app}}/{{app}}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n'
        '  <PropertyGroup>\n'
        '    <OutputType>Exe</OutputType>\n'
        '    <TargetFramework>{{dotnet_tfm}}</TargetFramework>\n'
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
