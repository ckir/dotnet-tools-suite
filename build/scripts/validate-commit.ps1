# Copyright (c) 2026 Costas Kirgoussios
# Licensed under the PolyForm Noncommercial License 1.0.0

<#
.SYNOPSIS
  Validates a commit message against Conventional Commits.

.DESCRIPTION
  Accepts a commit-msg file path (as passed by Lefthook) or a raw message
  string. Allows Conventional Commit subjects like `feat(scope): ...` and
  Git-generated `Merge ...` messages. Exits 0 when valid, 1 otherwise.
#>
param(
    [Parameter(Position = 0)]
    [string]$CommitMsgOrFile
)

$pattern = '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^\)]+\))?(!)?: .+'

function Get-Subject {
    param([string]$InputArg)
    if ([string]::IsNullOrWhiteSpace($InputArg)) {
        $msgFile = Join-Path (git rev-parse --git-dir 2>$null) 'COMMIT_EDITMSG'
        if ($msgFile -and (Test-Path $msgFile)) {
            $InputArg = $msgFile
        }
    }
    if ((Test-Path $InputArg -ErrorAction SilentlyContinue)) {
        # @( ... ) forces an array: a single-line file would otherwise
        # come back as a scalar string and $lines[0] would be one char.
        $lines = @(Get-Content $InputArg | Where-Object { $_ -notmatch '^\s*#' } | Where-Object { $_.Trim() -ne '' })
        if ($lines.Count -eq 0) { return '' }
        return $lines[0].Trim()
    }
    $firstLine = ($InputArg -split "`r?`n") | Where-Object { $_.Trim() -ne '' } | Select-Object -First 1
    return $firstLine.Trim()
}

$subject = Get-Subject $CommitMsgOrFile

if ([string]::IsNullOrWhiteSpace($subject)) {
    Write-Error 'Empty commit message.'
    exit 1
}
if ($subject -match '^Merge ') {
    exit 0
}
if ($subject -match '^Revert ".*"$' -or $subject -match "^Revert '.*'$") {
    exit 0
}
if ($subject -match $pattern) {
    exit 0
}

Write-Error @"
Invalid commit message: '$subject'
Expected Conventional Commits, e.g. 'feat(tooling-cli): add command'.
Types: feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert
"@
exit 1
