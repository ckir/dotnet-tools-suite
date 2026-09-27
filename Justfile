sln := "dotnet-tools-suite.slnx"
config := "Release"
python := env_var_or_default("PYTHON", "python3")
packages := "artifacts/packages"
sbom_dir := "artifacts/sbom"

default:
    @just --list

# Bootstrap a fresh clone: local tools, NuGet packages, and git hooks.
# Requires lefthook on PATH (see README Prerequisites); fails loudly otherwise.
setup:
    just restore
    just hooks

# Restore local tools and NuGet packages (no git hooks; used by CI).
restore:
    dotnet tool restore
    dotnet restore {{sln}}

# Install Lefthook git hooks (requires lefthook: https://github.com/evilmartians/lefthook).
hooks:
    @echo "Installing git hooks with lefthook..."
    lefthook install

build:
    dotnet build {{sln}} --configuration {{config}}

# Runs tests if any exist; succeeds when no test projects are present.
# Collects XPlat code coverage into TestResults/.
test:
    dotnet test {{sln}} --configuration {{config}} --collect:"XPlat Code Coverage" --results-directory TestResults

# Pack only packable projects (libs). Apps set IsPackable=false.
pack:
    dotnet pack {{sln}} --configuration {{config}} --output {{packages}}

# Fast correctness checks for normal development and pre-push.
# Packaging/package validation live in `just pack` (CI and release run both).
check: format-check license-check build test

format:
    dotnet format {{sln}}

format-check:
    dotnet format {{sln}} --verify-no-changes

license-inject:
    {{python}} scripts/polyform_injector.py

license-check:
    {{python}} scripts/polyform_injector.py --check

pre-commit: format-check license-check

version:
    dotnet tool run dotnet-gitversion

# Generate HTML coverage report from TestResults (requires test run first).
coverage-report:
    dotnet reportgenerator -reports:"TestResults/**/coverage.cobertura.xml" -targetdir:"artifacts/coverage" -reporttypes:Html

# Generate CycloneDX SBOM (JSON) for release artifacts. Not part of `check`.
sbom:
    dotnet dotnet-CycloneDX {{sln}} --output {{sbom_dir}} --output-format json

docs-install:
    dotnet tool restore

docs-build: docs

docs *args:
    dotnet docfx docs/docfx.json {{args}}

docs-serve *args:
    dotnet docfx docs/docfx.json --serve {{args}}
