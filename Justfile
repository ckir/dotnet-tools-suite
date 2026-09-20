python := "python3"

default:
    @just --list

license-inject:
    {{python}} scripts/polyform_injector.py

license-check:
    {{python}} scripts/polyform_injector.py --check

pre-commit: license-inject

