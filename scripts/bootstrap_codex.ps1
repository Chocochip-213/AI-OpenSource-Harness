Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$UseUv = $null -ne (Get-Command uv -ErrorAction SilentlyContinue)

function Run-PythonScript([string]$ScriptPath) {
    if ($UseUv) {
        & uv run python $ScriptPath
    } else {
        & python $ScriptPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: python $ScriptPath"
    }
}

Write-Host "[bootstrap_codex] Repo: $RepoRoot"
Write-Host "[bootstrap_codex] Runner: $(if ($UseUv) { 'uv run python' } else { 'python' })"

Run-PythonScript "scripts/make_context_pack.py"

$ActiveRecipe = "_template"
if (Test-Path ".claude/last_recipe.txt") {
    $ActiveRecipe = (Get-Content ".claude/last_recipe.txt" | Select-Object -First 1).Trim()
}

Write-Host "[bootstrap_codex] Active recipe: $ActiveRecipe"
Write-Host "[bootstrap_codex] Read SSOT docs:"
Write-Host "  recipes/$ActiveRecipe/docs/plan.md"
Write-Host "  recipes/$ActiveRecipe/docs/context.md"
Write-Host "  recipes/$ActiveRecipe/docs/tasks.md"

if ($args -contains "--smoke") {
    Run-PythonScript "scripts/smoke_test.py"
}

Write-Host "[bootstrap_codex] Done."
