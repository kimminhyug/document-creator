param(
    [ValidateSet('validate', 'build', 'test')][string]$Action = 'build',
    [string]$InputFile = 'examples/demo/content/table-spec.json',
    [string]$Template = 'templates/table_spec.json',
    [string]$Project = 'examples/demo/content/project.json',
    [string]$Theme = 'themes/blue-office.json',
    [string[]]$Formats = @('pdf'),
    [switch]$Release
)
$ErrorActionPreference = 'Stop'
$creatorRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $creatorRoot '.local/runtime.json'
if (-not (Test-Path -LiteralPath $runtimePath)) { throw 'Configure .local/runtime.json first. See README.md.' }
$runtimeConfig = Get-Content -LiteralPath $runtimePath -Raw -Encoding UTF8 | ConvertFrom-Json
Push-Location $creatorRoot
try {
    if ($Action -eq 'test') {
        & $runtimeConfig.python -m unittest discover -s tests -v
    } else {
        $creatorArgs = @('creator.py', $Action, '--input', $InputFile, '--template', $Template, '--project', $Project, '--theme', $Theme, '--runtime', $runtimePath, '--formats') + $Formats
        if ($Release) { $creatorArgs += '--release' }
        & $runtimeConfig.python @creatorArgs
    }
    $resultCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $resultCode
