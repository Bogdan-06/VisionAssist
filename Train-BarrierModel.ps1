# Separate stairs/curb/step experiment. Existing pothole training is unchanged.
[CmdletBinding()]
param(
    [ValidateRange(1,1000)][int]$Epochs = 20,
    [ValidateRange(1,64)][int]$Threads = 8,
    [ValidateRange(1,128)][int]$BatchSize = 8,
    [ValidateSet('Gpu','Cpu')][string]$Device = 'Gpu',
    [string]$DataRoot = (Join-Path $env:USERPROFILE 'Documents\Codex\2026-10-09\new-chat\work\ground'),
    [string]$OutputRoot = '',
    [string]$WslDistro = 'Ubuntu-24.04',
    [string]$ResumeFrom = '',
    [string]$EvaluationPython = '',
    [switch]$Smoke,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if (-not $OutputRoot) { $OutputRoot = Join-Path $PSScriptRoot 'barrier-training-runs' }
$runner = Join-Path $PSScriptRoot 'tools\ground\run_barrier_training.py'
function Convert-BarrierWslPath([string]$Path) {
    $absolute = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $converted = & wsl.exe -d $WslDistro -u root --exec wslpath -a -u $absolute
    if ($LASTEXITCODE -ne 0) { throw "Cannot convert path for WSL: $absolute" }
    return ($converted -join '').Trim()
}
if ($Device -eq 'Gpu') {
    if (-not $EvaluationPython) { $EvaluationPython = '/opt/visionassist/barrier-runtime-venv/bin/python' }
    if (-not $EvaluationPython.StartsWith('/')) { throw 'GPU evaluation Python must be a Linux path inside WSL.' }
    $runner = Convert-BarrierWslPath $runner
    $DataRoot = Convert-BarrierWslPath $DataRoot
    $OutputRoot = Convert-BarrierWslPath $OutputRoot
    if ($ResumeFrom) { $ResumeFrom = Convert-BarrierWslPath $ResumeFrom }
} elseif (-not $EvaluationPython) {
    $EvaluationPython = Join-Path $DataRoot 'barrier-runtime-venv\Scripts\python.exe'
}
$arguments = @('-u',$runner,'--data-root',$DataRoot,'--output-root',$OutputRoot,
    '--device',$Device.ToLowerInvariant(),'--epochs',"$Epochs",'--threads',"$Threads",'--batch-size',"$BatchSize")
if ($Smoke) { $arguments += '--smoke' }
if ($CheckOnly) { $arguments += '--check-only' }
if ($ResumeFrom) { $arguments += @('--resume-from',$ResumeFrom) }
$arguments += @('--evaluation-python',$EvaluationPython)
if ($Device -eq 'Gpu') {
    & wsl.exe -d $WslDistro -u root --exec /opt/visionassist/modelmaker-venv/bin/python @arguments
} else {
    $python = Join-Path $DataRoot 'modelmaker-venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw "Detector Python is missing: $python" }
    & $python @arguments
}
exit $LASTEXITCODE
