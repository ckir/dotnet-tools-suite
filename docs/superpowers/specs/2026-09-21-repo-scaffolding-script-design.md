<!--
Copyright (c) 2026 Costas Kirgoussios
Licensed under the PolyForm Noncommercial License 1.0.0

-->

# Repo Scaffolding Script — Design

Date: 2026-09-21
Status: Approved (approach A — self-contained generator, embedded templates)
Repo: `ckir/dotnet-tools-suite` (branch `main`)

## 1. Goal

A single-file, stdlib-only Python script (`scripts/scaffold.py`) that
reproduces this repo's monorepo scaffold for other users: full replica
of root config, workflows, scripts, `src/` layout, and DocFX tree, fully
parameterized, creating the GitHub repo and pushing via `gh`, then
guiding the user through the un-scriptable manual steps with
`gh`-backed verification.

## 2. Decisions

- Scope: full replica of the current setup.
- Distribution: one self-contained `scripts/scaffold.py`, stdlib only.
- Parameters: repo, owner, holder, app/lib names and counts, .NET
  version, DocFX on/off.
- Manual steps: printed checklist + `gh api` verification loop.
- Repo creation: script runs `gh repo create` and pushes (assumes `gh`
  installed and authenticated).

## 3. CLI (Section 1 — approved)

`argparse`, non-interactive when fully flagged; prompts only for a
missing `--repo`:

- `--repo` (required): new repository name; also used for the DocFX
  `_appBasePath` (`/<repo>/`) and sitemap `baseUrl`.
- `--owner`: GitHub owner, default from `gh api user --jq .login`.
- `--holder`: copyright holder, defaults to `--owner`.
- `--apps` / `--libs`: repeatable; defaults `tooling-cli,datasync-cli,
  reporting-cli` and `shared-kernel,logging,cli-runtime`.
- `--dotnet`: SDK/workflow version, default `10.0.x` (pinned SDK value
  in `perster.json` derived from the same input).
- `--no-docs`: omits the DocFX tree, `docs.yml`, and the README badge.
- `--private` / `--public`: passed to `gh repo create` (default
  `--public` to match this repo's Pages-friendly posture).
- `--target-dir`: default `./<repo>`, must not exist or must be empty.
- `--skip-create`: stop after the local commit; print the `gh` commands
  instead of running them.
- `--skip-verify`: bypass the manual-steps verification loop.
- `--self-test`: render defaults to a temp dir and diff key files
  against this repo to catch template drift; exit 0/1.

## 4. Template catalog (Section 2 — approved)

One string constant per scaffold file (~25 files):

- Root: `.gitignore`, `Directory.Build.props`,
  `Directory.Packages.props`, `GitVersion.yml`, `Justfile`,
  `lefthook.yml`, `perster.json`, `README.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, `TODO.md`, `LICENSE`, `NOTICE.md`.
- Workflows: `build.yml`, `license-check.yml`, `release.yml`,
  `docs.yml` (skipped under `--no-docs`).
- `scripts/polyform_injector.py` (copied verbatim, no placeholders).
- `src/apps/<app>/<app>.csproj` + `Program.cs` stub per app;
  `src/libs/<lib>/<lib>.csproj` + `Class1.cs` stub per lib.
- DocFX tree (skipped under `--no-docs`): `docs/docfx.json`,
  `docs/index.md`, `docs/toc.yml`, `docs/articles/toc.yml`,
  `docs/articles/intro.md`, `docs/api/index.md`, `docs/.nojekyll`,
  `docs/images/.gitkeep`.

Placeholder scheme: doubled braces (`{{repo}}`, `{{owner}}`,
`{{holder}}`, `{{dotnet}}`, plus generated blocks `{{app_list}}`,
`{{lib_list}}`, `{{metadata_files}}`, `{{workflow_restores}}`,
`{{workflow_builds}}`, `{{readme_table}}`) rendered by a single
`render()` so single braces in C#/JSON/YAML pass through untouched.

Per-file rules carried over from this repo's lessons: `.json` files
never take license headers; `toc.yml` files use `#`-style headers
(DocFX rejects HTML comments in TOC YAML); generated DocFX metadata
(`docs/api/*.yml`, `docs/api/toc.yml`, `docs/api/.manifest`) is
git-ignored, not scaffolded.

## 5. Generation + create flow (Section 3 — approved)

1. Validate tools: `python3`, `git`, `gh auth status` (fatal if
   missing/unauthenticated); `dotnet` optional (warn-only, needed only
   for local builds, not scaffolding).
2. Render the tree into `--target-dir`; refuse non-empty dirs.
3. `git init -b main`, `git add -A`, initial commit
   `feat: initial commit from scaffold`.
4. `gh repo create <owner>/<repo> [--private|--public] --source=. --push`
   (equivalent explicit push `git push -u origin main` if created
   separately).
5. Fail fast: any failing command aborts with the exact command,
   exit code, and tail of output printed.

## 6. Manual steps verify loop (Section 4 — approved)

After a successful push (skipped with `--skip-create`/`--skip-verify`),
print the checklist of actions no script can perform, then verify in a
loop (`[Enter]` re-checks, `s` skips the rest):

1. Settings → Pages → Source → **GitHub Actions** — verified with
   `gh api repos/<owner>/<repo>/pages --jq .build_type` expecting
   `workflow` (this exact check caught the missing flip during this
   repo's own rollout).
2. First `Docs` workflow run green — `gh run list
   --workflow=docs.yml --limit 1` conclusion `success`.
3. Live site responds — `https://<owner>.github.io/<repo>/` HTTP 200.

## 7. Out of scope

Branch protection rulesets, environment protection rules, custom
domains/CNAME, versioned docs, secret management, non-GitHub forges,
updating existing repos (greenfield scaffolding only).

## 8. Risks

- Template drift: scaffold silently diverges from this repo. Mitigation:
  `--self-test` diffs key rendered files against the live repo.
- `gh` version differences in `repo create` flags. Mitigation: use only
  long-stable flags; print the manual equivalent on failure.
- Placeholder collision with C# string interpolation (`$"{...}"`) or
  `{{ }}` in workflow expressions (`${{ ... }}`). Mitigation:
  doubled-brace scheme plus self-test rendering real C# and workflow
  files.
