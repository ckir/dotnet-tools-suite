python := "python3"

default:
    @just --list

license-inject:
    {{python}} scripts/polyform_injector.py

license-check:
    {{python}} scripts/polyform_injector.py --check

pre-commit: license-inject

docs-install:
    dotnet tool update -g docfx

docs-build:
    docfx docs/docfx.json

docs-serve:
    docfx docs/docfx.json --serve

