#!/usr/bin/env python3
# Copyright (c) 2026 Costas Kirgoussios
# Licensed under the PolyForm Noncommercial License 1.0.0

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
