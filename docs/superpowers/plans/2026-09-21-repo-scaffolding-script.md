<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# Repo Scaffolding Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/scaffold.py`, a single-file stdlib-only generator that reproduces this repo's scaffold parameterized by repo/owner/holder/apps/libs/dotnet, creates the GitHub repo via `gh`, and verifies manual steps.

**Architecture:** One Python file: `argparse` CLI → `Config` dataclass → `render()` (doubled-brace placeholders) over an embedded `TEMPLATES` catalog (static strings plus small builder functions for repeated blocks) → `write_tree()` → `git`/`gh` subprocess flow → manual-steps verify loop. A built-in `--self-test` renders defaults to a temp dir and diffs against the live repo.

**Tech Stack:** Python 3 stdlib only (`argparse`, `subprocess`, `pathlib`, `tempfile`, `difflib`, `shutil`, `sys`, `os`). External tools invoked, never imported: `git`, `gh`.

**Spec:** `docs/superpowers/specs/2026-09-21-repo-scaffolding-script-design.md`

## Global Constraints

- Single file `scripts/scaffold.py`, stdlib only — no third-party imports.
- Placeholders use doubled braces (`{{repo}}`); single braces in C#/JSON/YAML pass through untouched.
- `.json` files MUST NOT carry license headers; `toc.yml` files use `#`-style headers (DocFX rejects HTML comments in TOC YAML); every other `.md`/`.yml`/`.props`/`.cs`/`.ps1` file carries the PolyForm header with the user's `{{holder}}`.
- Generated DocFX metadata (`docs/api/*.yml`, `docs/api/toc.yml`, `docs/api/.manifest`) is git-ignored, never scaffolded.
- `gh` is assumed installed and authenticated; `gh auth status` failure is fatal (except `--self-test`/pure-local paths that never call `gh`).
- Any failing subprocess aborts with the exact command, exit code, and last 20 lines of output printed.
- Initial commit message is exactly `feat: initial commit from scaffold`.
- TDD applies: every task writes its check first (failing), then implements (passing). Checks are runnable shell/Python commands with exact expected outputs (this repo has no pytest harness; `py_compile`, `--self-test`, `diff`, and the rendered tree's own `polyform_injector.py --check` are the test suite).

---

## File Structure

- Create: `scripts/scaffold.py` — the only production file. Internal sections in order: (1) `TEMPLATES` catalog (static strings), (2) builder functions for repeated blocks, (3) `render()`, (4) `Config` + `parse_args()`, (5) `write_tree()`, (6) `run()` subprocess helper + `gh` helpers, (7) create/push flow, (8) manual-steps verify loop, (9) `--self-test`, (10) `main()`.
- Test: temp directories only (never committed); the rendered tree's `scripts/polyform_injector.py --check` run with cwd inside the rendered tree is the header test.
- No other repo files change (the script reads live repo files only during `--self-test` diffing).

### Canonical decisions (bind all tasks)

- All apps are generated from ONE canonical app template (the current `datasync-cli` shape: `OutputType Exe`, lib ProjectReferences to every scaffolded lib, `System.CommandLine` + `Microsoft.Extensions.*` packages), with `{{app}}` substituted. The current `tooling-cli` minimal csproj (no ProjectReferences) is NOT replicated; `--self-test` allowlists exactly that one diff (`src/apps/tooling-cli/tooling-cli.csproj`).
- C# namespace for a lib/app derives from its name by deleting `-` (e.g. `shared-kernel` → `sharedkernel`, `datasync-cli` → `datasynccli`). `Program.cs` uses the raw app name in `RootCommand("{{app}}")` and the running message.
- `--dotnet` value (default `10.0.x`) flows to: workflow `dotnet-version`, csproj `TargetFramework` (`net` + major, e.g. `10.0.x` → `net10.0`), docfx metadata `TargetFramework`, `perster.json` `dotnet` (pinned SDK default `10.0.100` unless `--dotnet` names an exact SDK — if `--dotnet` matches `^\d+\.\d+\.x$`, pin `perster.json` to `<major>.<minor>.100`).
- Package versions (`System.CommandLine 2.0.12`, `Microsoft.Extensions.* 10.0.12`) are copied verbatim, not parameterized.

---

### Task 1: CLI skeleton, render engine, write path, self-test harness

**Files:**
- Create: `scripts/scaffold.py` (sections 3–5, 9–10 skeleton; `TEMPLATES = {}` empty; builders return `""`)
- Test: shell (`py_compile`, `--help`, `--self-test` red/green)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `parse_args() -> Config`, `render(template: str, ctx: dict[str, str]) -> str`, `write_tree(root: Path, files: dict[str, str]) -> None`, `Config` fields consumed by Tasks 2–4; `--self-test` framework consumed by Tasks 2–3.

- [ ] **Step 1: Write the failing checks**

Create `/tmp/scaffold_checks_task1.sh` (scratch, never committed):

```bash
#!/bin/sh
set -u
python3 -m py_compile scripts/scaffold.py || exit 1
python3 scripts/scaffold.py --help | grep -q -- "--repo" || exit 1
python3 scripts/scaffold.py --help | grep -q -- "--no-docs" || exit 1
python3 scripts/scaffold.py --help | grep -q -- "--self-test" || exit 1
python3 scripts/scaffold.py --self-test && exit 1 || echo "RED-OK"
```

- [ ] **Step 2: Run checks to verify they fail**

Run: `sh /tmp/scaffold_checks_task1.sh`
Expected: FAIL (`scripts/scaffold.py` does not exist → `py_compile` errors).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/scaffold.py` with exactly this structure (stdlib only):

```python
#!/usr/bin/env python3
"""Scaffold a dotnet-tools-suite-style monorepo. Stdlib only; requires git + gh."""
import argparse
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
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
        raise ValueError(f"unresolved placeholder in rendered output: {out[out.index('{{'):out.index('{{')+30]}")
    return out

def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")

def build_context(cfg: Config) -> dict[str, str]:
    return {"repo": cfg.repo, "owner": cfg.owner, "holder": cfg.holder, "dotnet": cfg.dotnet}

def collect_files(cfg: Config) -> dict[str, str]:
    ctx = build_context(cfg)
    return {rel: render(tpl, ctx) for rel, tpl in TEMPLATES.items()}

def self_test() -> int:
    if not TEMPLATES:
        print("SELFTEST-FAIL: no templates registered")
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
```

PolyForm header: `scripts/scaffold.py` is `.py` — the injector has no
`.py` style, so `check_only()` ignores it; still prepend the `#`-style
header (same text as `.yml`) for consistency.

- [ ] **Step 4: Run checks to verify green-except-red**

Run: `sh /tmp/scaffold_checks_task1.sh`
Expected: `py_compile` passes, all three `grep`s pass, `--self-test` exits 1 printing `SELFTEST-FAIL: no templates registered`, script prints `RED-OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/scaffold.py
git commit -m "feat: add scaffold CLI skeleton with render engine"
```

---

### Task 2: Root + workflow templates and repeated-block builders

**Files:**
- Modify: `scripts/scaffold.py` (sections 1–2: `TEMPLATES` entries below + builder functions)
- Test: shell (`--self-test` diffs rendered defaults against live repo files)

**Interfaces:**
- Consumes: `render()`, `Config`, `collect_files()` (Task 1).
- Produces: `TEMPLATES` root/workflow entries + `app_block_*()` builders consumed by Task 3's full-tree test and Task 4's e2e run.

Placeholder table (only these keys exist; anything else left as `{{...}}` fails the build per `render()`):

| Key | Value source |
|---|---|
| `repo`, `owner`, `holder`, `dotnet` | `Config` fields verbatim |
| `dotnet_tfm` | `net{major}.{minor}` parsed from `--dotnet` (`10.0.x` → `net10.0`) |
| `dotnet_sdk_pin` | exact SDK if given else `<major>.<minor>.100` |
| `app_restore_lines`, `app_build_lines` | one `dotnet restore …` / `dotnet build …` line per app (see builder) |
| `metadata_files` | one quoted csproj path per app+lib for docfx.json (see builder) |
| `readme_apps_row`, `readme_libs_row` | backtick lists for README tables |
| `readme_title`, `year` | repo name; copyright year `2026` (copy verbatim, not parameterized) |

Builder functions (exact code to add):

```python
def app_restore_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet restore src/apps/{a}/{a}.csproj" for a in cfg.apps)

def app_build_lines(cfg: Config) -> str:
    return "\n".join(f"          dotnet build src/apps/{a}/{a}.csproj --configuration Release --no-restore" for a in cfg.apps)

def metadata_files(cfg: Config) -> str:
    entries = [f'            "src/apps/{a}/{a}.csproj",' for a in cfg.apps]
    entries += [f'            "src/libs/{l}/{l}.csproj",' for l in cfg.libs]
    entries[-1] = entries[-1].rstrip(",")
    return "\n".join(entries)
```

`TEMPLATES` entries this task (key = target relpath; static text with
`{{holder}}` in license headers and the keys above where needed;
`build.yml` Restore/Build bodies use `{{app_restore_lines}}` /
`{{app_build_lines}}`; `docs.yml` additionally uses them plus
`{{dotnet}}`; README uses `{{repo}}`, `{{owner}}`, `{{readme_apps_row}}`,
`{{readme_libs_row}}` and badge line
`[![Docs](https://github.com/{{owner}}/{{repo}}/actions/workflows/docs.yml/badge.svg)](https://{{owner}}.github.io/{{repo}}/)`
omitted under `--no-docs`):

- `.gitignore` — copy of live `.gitignore` verbatim (drop the
  `docs/api/*.yml`, `docs/api/toc.yml`, `docs/api/.manifest` lines when
  `no_docs`; implement as post-render filter in `collect_files()`: skip
  any rendered line starting with `docs/api/` if `cfg.no_docs` and the
  file is `.gitignore`).
- `Directory.Build.props` — copy verbatim with `{{holder}}` header.
- `Directory.Packages.props` — copy verbatim with `{{holder}}` header.
- `GitVersion.yml`, `lefthook.yml` — copy verbatim with `{{holder}}`.
- `perster.json` — copy verbatim with `{{dotnet_sdk_pin}}` in place of `10.0.100`.
- `.github/workflows/build.yml`, `license-check.yml`, `release.yml` —
  copy verbatim with `{{holder}}` header and `{{app_restore_lines}}` /
  `{{app_build_lines}}` bodies.
- `.github/workflows/docs.yml` — copy verbatim with `{{holder}}`,
  `{{dotnet}}`, `{{app_restore_lines}}`; skipped entirely under
  `--no-docs` (filter in `collect_files()`).
- `README.md`, `TODO.md`, `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE.md`,
  `LICENSE` — copy verbatim with `{{holder}}` / `{{repo}}` swaps
  (`LICENSE` has no placeholders: copy byte-identical; `NOTICE.md`
  swaps holder + year lines keep `2026`).
- `Justfile` — copy verbatim; drop the `docs-install`/`docs-build`/
  `docs-serve` stanzas under `--no-docs` (same post-render filter
  mechanism: skip from the `docs-install:` line to end of
  `docs-serve` stanza).

Extend `build_context()` to add all builder keys; extend
`collect_files()` with the two skip rules (`docs.yml` + docs-only
`.gitignore`/`Justfile` filtering under `no_docs`).

Extend `self_test()` for this task (exact logic): render defaults
(`Config(repo="dotnet-tools-suite", owner="ckir",
holder="Costas Kirgoussios")`), write to temp dir, then `diff` these
rendered files against the live repo and REQUIRE zero differences:
`.gitignore`, `Directory.Build.props`, `GitVersion.yml`, `lefthook.yml`,
`perster.json`, all four workflows, `Justfile`, `README.md`. Print
`SELFTEST-PASS` on success, unified diff + exit 1 otherwise.

- [ ] **Step 1: Write the failing check**

Run: `python3 scripts/scaffold.py --self-test`
Expected: FAIL — prints `SELFTEST-FAIL: no templates registered` (exit 1), proving the new `self_test()` body is absent.

- [ ] **Step 2: Implement templates + builders + filters + self-test**

Add the `TEMPLATES` entries, builder functions, `build_context()`
keys, `collect_files()` skip rules, and the diffing `self_test()`
exactly as specified above.

- [ ] **Step 3: Run the check green**

Run: `python3 scripts/scaffold.py --self-test`
Expected: exit 0, `SELFTEST-PASS` (every listed file byte-identical to the live repo).

- [ ] **Step 4: Commit**

```bash
git add scripts/scaffold.py
git commit -m "feat: add scaffold root and workflow templates with self-test"
```

---

### Task 3: src + DocFX + scripts templates, skip rules, header test

**Files:**
- Modify: `scripts/scaffold.py` (`TEMPLATES` src/docs entries)
- Test: shell (`--self-test` full-tree diff + rendered-tree header check)

**Interfaces:**
- Consumes: `TEMPLATES`, `collect_files()`, `self_test()` (Tasks 1–2).
- Produces: complete file catalog consumed by Task 4's create/push/verify run.

`TEMPLATES` entries this task (namespace rule: `{{namespace}}` =
name with `-` deleted):

- `scripts/polyform_injector.py` — copy of the live file byte-identical
  (no placeholders; never rendered with a context that could touch it —
  it contains no `{{...}}` sequences; `self_test()` asserts that).
- Per app `src/apps/{{app}}/{{app}}.csproj` — canonical template
  (datasync-cli shape), exact text with `{{lib_refs}}` builder emitting
  one `    <ProjectReference Include="..\..\libs\{{lib}}\{{lib}}.csproj" />`
  line per lib, and `{{dotnet_tfm}}`:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>{{dotnet_tfm}}</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
{{lib_refs}}
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="System.CommandLine" Version="2.0.12" />
    <PackageReference Include="Microsoft.Extensions.DependencyInjection" Version="10.0.12" />
    <PackageReference Include="Microsoft.Extensions.Logging" Version="10.0.12" />
    <PackageReference Include="Microsoft.Extensions.Logging.Console" Version="10.0.12" />
  </ItemGroup>
</Project>
```

- Per app `src/apps/{{app}}/Program.cs` — exact text:

```csharp
// Copyright (c) 2026 {{holder}}
// Licensed under the PolyForm Noncommercial License 1.0.0

using System;
using System.CommandLine;
using Microsoft.Extensions.Logging;

var root = new RootCommand("{{app}}");

root.SetAction(_ =>
{
    Console.WriteLine("{{app}} is running.");
});

return await root.Parse(args).InvokeAsync();
```

- Per lib `src/libs/{{lib}}/{{lib}}.csproj` — exact text with `{{dotnet_tfm}}`:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>{{dotnet_tfm}}</TargetFramework>
  </PropertyGroup>
</Project>
```

- Per lib `src/libs/{{lib}}/Class1.cs` — exact text:

```csharp
// Copyright (c) 2026 {{holder}}
// Licensed under the PolyForm Noncommercial License 1.0.0

namespace {{namespace}};

public class Class1
{
}
```

- DocFX tree (all skipped under `--no-docs` via `collect_files()`
  skipping any relpath starting with `docs/`): `docs/docfx.json`
  (live copy with `{{metadata_files}}`, `{{repo}}` in `_appBasePath`
  `/{{repo}}/` and sitemap `https://{{owner}}.github.io/{{repo}}`,
  `{{dotnet_tfm}}` without the `net` prefix stripped — metadata
  `TargetFramework` uses the full `{{dotnet_tfm}}`, e.g. `net10.0`),
  `docs/index.md`, `docs/toc.yml` (`#`-style header), `docs/api/index.md`,
  `docs/articles/toc.yml` (`#`-style header),
  `docs/articles/intro.md`, `docs/.nojekyll` (empty string),
  `docs/images/.gitkeep` (empty string). App/lib tables in
  `docs/index.md` use `{{readme_apps_row}}` / `{{readme_libs_row}}`.

Because relpaths themselves contain placeholders (`{{app}}`,
`{{lib}}`), `collect_files()` must render KEYS as well as values:
`{render(rel, ctx_full): render(tpl, ctx_full)}` where `ctx_full`
includes per-app/per-lib entries — implement by expanding app/lib
templates in a loop over `cfg.apps`/`cfg.libs` with `ctx | {"app": a,
"namespace": a.replace("-", "")}` (same for libs).

Extend `self_test()`: after the Task 2 file diffs, additionally require
zero diff for `src/libs/*` files, `scripts/polyform_injector.py`, and
all `docs/` files EXCEPT the allowlisted
`src/apps/tooling-cli/tooling-cli.csproj` (canonical template differs
from the live minimal file by design — assert the diff EXISTS and
contains `ProjectReference`, proving canonicalization rather than a
copy error). Then run the rendered tree's header check: execute
`python3 <tmp>/scripts/polyform_injector.py --check` with cwd inside
the temp tree and require exit 0 printing `All files contain PolyForm
headers.`

- [ ] **Step 1: Write the failing check**

Run: `python3 scripts/scaffold.py --self-test && python3 -c "print('HAS-SRC-DIFF-STEP')"`
Expected: FAIL — current `--self-test` passes without checking any
`src/` file (prove by: `python3 scripts/scaffold.py --self-test; echo "no-src-coverage"` prints no src coverage; the new asserts are absent).

- [ ] **Step 2: Implement src/docs/scripts templates + key rendering + extended self-test**

Add entries, key-rendering loop, namespace derivation, `--no-docs`
`docs/` skip, and the extended `self_test()` exactly as specified.

- [ ] **Step 3: Run green**

Run: `python3 scripts/scaffold.py --self-test`
Expected: exit 0, `SELFTEST-PASS`; header check inside temp tree passes.

- [ ] **Step 4: Commit**

```bash
git add scripts/scaffold.py
git commit -m "feat: add scaffold src and docs templates with header check"
```

---

### Task 4: git/gh create flow, verify loop, end-to-end dry run

**Files:**
- Modify: `scripts/scaffold.py` (sections 6–8: `run()`, create/push, verify loop, `main()` wiring)
- Test: shell (local `--skip-create` scaffold of a scratch repo + diff + header check; `gh` paths exercised with `--help`-level stubbing only — no real repo is created by tests)

**Interfaces:**
- Consumes: full `TEMPLATES` catalog + `collect_files()` (Tasks 2–3).
- Produces: finished script; nothing downstream.

Exact helpers to add:

```python
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
```

Create/push flow (exact order): refuse non-empty `--target-dir`
(`TARGET-NOT-EMPTY` + exit 2); `write_tree()`; `git init -b main`;
`git add -A`; `git commit -m "feat: initial commit from scaffold"`;
unless `--skip-create`: `gh repo create <owner>/<repo>
--public|--private --source <target> --push`. With `--skip-create`,
print the exact `gh` command instead of running it.

Verify loop (skipped with `--skip-verify` or `--skip-create`): print the
three manual steps with the user's values interpolated, then for each
check print prompt and wait: `[Enter]` re-checks, `s` skips the rest.
Exact checks:

1. Pages source: `gh api repos/{owner}/{repo}/pages --jq .build_type` → expect `workflow`.
2. Docs run green: `gh run list --workflow=docs.yml --limit 1 --json conclusion --jq .[0].conclusion` → expect `success` (empty = rerun prompt, not failure).
3. Live site: `urllib.request.urlopen(f"https://{owner}.github.io/{repo}/", timeout=30).status` → expect `200`, using stdlib `urllib` (no curl dependency).

`main()` wiring order: `--self-test` → validate tools → render/write →
git commit → create/push → verify loop. `--owner` empty at runtime
resolves via `gh api user --jq .login` (strip quotes/newlines); `--holder`
empty defaults to resolved owner.

- [ ] **Step 1: Write the failing check (local dry run)**

Run:

```bash
rm -rf /tmp/scaffold-e2e && python3 scripts/scaffold.py --repo e2e-probe --owner someowner --holder "Some Holder" --target-dir /tmp/scaffold-e2e --skip-create && test -f /tmp/scaffold-e2e/docs/docfx.json && echo "E2E-OK"
```

Expected: FAIL — `main()` has no create flow yet (prints the Task 1
stub line, creates nothing, `test -f` fails).

- [ ] **Step 2: Implement create/push flow + verify loop + main wiring**

Add helpers, flow, loop, and wiring exactly as specified. `--self-test`
and `--help` behavior from Tasks 1–2 must keep working unchanged.

- [ ] **Step 3: Run green — dry run, diff, headers, self-test**

Run:

```bash
rm -rf /tmp/scaffold-e2e && python3 scripts/scaffold.py --repo e2e-probe --owner someowner --holder "Some Holder" --target-dir /tmp/scaffold-e2e --skip-create --skip-verify && echo "---" && grep -c "someowner" /tmp/scaffold-e2e/docs/docfx.json && cd /tmp/scaffold-e2e && python3 scripts/polyform_injector.py --check; cd - >/dev/null; python3 scripts/scaffold.py --self-test
```

Expected: scaffold exits 0; `grep -c` prints a count ≥ 2 (owner in
sitemap + edit links); header check prints `All files contain PolyForm
headers.`; `--self-test` prints `SELFTEST-PASS`. Clean up
`/tmp/scaffold-e2e` afterwards (`rm -rf /tmp/scaffold-e2e`,
`/tmp/scaffold_checks_task1.sh`).

- [ ] **Step 4: Commit**

```bash
git add scripts/scaffold.py
git commit -m "feat: add scaffold create flow with manual-steps verification"
```

---

## Self-Review

- Spec coverage: CLI §3 → Task 1 (+ Task 4 wiring); catalog §4 → Tasks 2–3 (all ~25 files listed with exact transforms; placeholder table complete; header/gitignore rules encoded; drift guard = extended `--self-test`); flow §5 → Task 4 (tool validation, render, commit message verbatim, `gh repo create` flags, fail-fast format); verify loop §6 → Task 4 (three checks with exact commands, Enter/s interaction, `--skip-verify`); out-of-scope items have no tasks by design.
- Placeholder scan: no TBD/TODO/later; every code step ships exact code/commands/expected outputs; template contents are specified as live-file copies plus explicit substitution lists and full canonical texts where structure is generated.
- Type consistency: `Config` fields, `render()/write_tree()/run()/collect_files()/build_context()/self_test()` signatures identical across tasks; `{{...}}` key names match the placeholder table everywhere; commit messages verbatim.
