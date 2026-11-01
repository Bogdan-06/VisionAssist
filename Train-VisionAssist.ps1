# Unified local research workflow. Never installs models into the Android app.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('pothole','barrier')][string]$Task,
    [ValidateSet('check','train','evaluate','status','resume','report')][string]$Action = 'check',
    [ValidateSet('Cpu','Gpu')][string]$Device = 'Gpu',
    [ValidateRange(1,1000)][int]$Epochs = 20,
    [ValidateRange(1,128)][int]$BatchSize = 8,
    [ValidateRange(1,128)][int]$CacheBatchSize = 32,
    [ValidateRange(1,64)][int]$Threads = 8,
    [string]$DataRoot = (Join-Path $env:USERPROFILE 'Documents\Codex\2026-10-09\new-chat\work\ground'),
    [string]$OutputDirectory = '',
    [string]$RunDirectory = '',
    [string]$Checkpoint = '',
    [string]$ReportFile = '',
    [ValidateSet('validation','test','all')][string]$Split = 'all',
    [ValidateRange(1,1000000)][int]$MaxImages,
    [switch]$Smoke,
    [string]$Python = '',
    [string]$EvaluationPython = '',
    [string]$WslDistro = 'Ubuntu-24.04',
    [string]$Backbone = (Join-Path $env:USERPROFILE '.keras\models\mobilenet_v2_weights_tf_dim_ordering_tf_kernels_0.5_224_no_top.h5')
)
$ErrorActionPreference = 'Stop'
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot 'visionassist-experiments' }
$runner = Join-Path $PSScriptRoot 'tools\ground\visionassist_training.py'
# A fixed host lock spans tasks, output directories and CPU/WSL runtimes.
$lockDirectory = Join-Path $env:LOCALAPPDATA 'VisionAssist'
$lockPath = Join-Path $lockDirectory 'training.lock'
$hostLock = $null
function Convert-VisionAssistWslPath([string]$Value) {
    $absolute = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Value)
    $result = & wsl.exe -d $WslDistro -u root --exec wslpath -a -u $absolute
    if ($LASTEXITCODE -ne 0) { throw "WSL path conversion failed: $absolute" }
    return ($result -join '').Trim()
}
try {
    if ($Action -in @('train','resume','evaluate')) {
        [System.IO.Directory]::CreateDirectory($lockDirectory) | Out-Null
        try { $hostLock = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None') }
        catch { throw 'Another VisionAssist job is active. Wait for it to finish; do not delete the lock file.' }
        # Detect a WSL controller orphaned by a closed Windows terminal, even
        # when this invocation requests CPU training on Windows.
        if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
            $installed = ((& wsl.exe --list --quiet) -join '').Replace([string][char]0,'')
            if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect WSL distributions for active jobs.' }
            if ($installed -match [regex]::Escape($WslDistro)) {
                $auditRunner = Convert-VisionAssistWslPath $runner
                & wsl.exe -d $WslDistro -u root --exec /usr/bin/python3 -B $auditRunner --audit-processes
                if ($LASTEXITCODE -ne 0) { throw 'A WSL job is active or its process audit failed. Inspect it before starting another job.' }
            }
        }
    }
    $useWsl = $Device -eq 'Gpu'
    # Status/report are dependency-light, but use the same filesystem coordinates
    # as the chosen device so PID checks do not cross operating systems.
    if ($useWsl) {
        $wslVersion = (& wsl.exe --list --verbose 2>&1 | Out-String).Replace([string][char]0,'')
        if ($LASTEXITCODE -ne 0 -or $wslVersion -notmatch ([regex]::Escape($WslDistro) + '\s+\S+\s+2')) {
            throw "WSL2 distribution $WslDistro is unavailable. See Setup-GpuTraining.ps1."
        }
        if (-not $Python) { $Python = if ($Task -eq 'barrier') { '/opt/visionassist/modelmaker-venv/bin/python' } else { '/opt/visionassist/venv/bin/python' } }
        if (-not $EvaluationPython) { $EvaluationPython = '/opt/visionassist/barrier-runtime-venv/bin/python' }
        $runner = Convert-VisionAssistWslPath $runner
        $DataRoot = Convert-VisionAssistWslPath $DataRoot
        $OutputDirectory = Convert-VisionAssistWslPath $OutputDirectory
        $Backbone = Convert-VisionAssistWslPath $Backbone
        if ($RunDirectory) { $RunDirectory = Convert-VisionAssistWslPath $RunDirectory }
        if ($Checkpoint) { $Checkpoint = Convert-VisionAssistWslPath $Checkpoint }
        if ($ReportFile) { $ReportFile = Convert-VisionAssistWslPath $ReportFile }
        $runtimeLock = '/opt/visionassist/unified-training.lock'
    } else {
        if (-not $Python) {
            $environmentName = if ($Task -eq 'barrier') { 'modelmaker-venv' } else { 'venv' }
            $Python = Join-Path $DataRoot "$environmentName\Scripts\python.exe"
        }
        if (-not $EvaluationPython) { $EvaluationPython = Join-Path $DataRoot 'barrier-runtime-venv\Scripts\python.exe' }
        if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python missing: $Python" }
        $runtimeLock = Join-Path $lockDirectory 'runtime.lock'
    }
    $arguments = @('-B','-u',$runner,'--task',$Task,'--action',$Action,'--device',$Device.ToLowerInvariant(),
        '--data-root',$DataRoot,'--output-root',$OutputDirectory,'--backbone',$Backbone,
        '--evaluation-python',$EvaluationPython,'--lock-file',$runtimeLock,'--epochs',"$Epochs",
        '--batch-size',"$BatchSize",'--cache-batch-size',"$CacheBatchSize",'--threads',"$Threads",'--split',$Split)
    if ($RunDirectory) { $arguments += @('--run',$RunDirectory) }
    if ($Checkpoint) { $arguments += @('--checkpoint',$Checkpoint) }
    if ($ReportFile) { $arguments += @('--report-file',$ReportFile) }
    if ($PSBoundParameters.ContainsKey('MaxImages')) { $arguments += @('--max-images',"$MaxImages") }
    if ($Smoke) { $arguments += '--smoke' }
    if ($useWsl) { & wsl.exe -d $WslDistro -u root --exec $Python @arguments }
    else { & $Python @arguments }
    $nativeCode = $LASTEXITCODE
} finally {
    if ($hostLock) { $hostLock.Dispose() }
}
exit $nativeCode
