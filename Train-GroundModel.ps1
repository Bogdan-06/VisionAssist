# Run from any folder. Each invocation creates a separate local research run.
[CmdletBinding()]
param(
    [ValidateRange(1, 1000)][int]$Epochs = 12,
    [ValidateRange(1, 64)][int]$Threads = 8,
    [ValidateSet('Auto', 'Cpu', 'Gpu')][string]$Device = 'Auto',
    [ValidateRange(1, 128)][int]$BatchSize = 16,
    [ValidateRange(1, 128)][int]$CacheBatchSize = 32,
    [string]$DataRoot = (Join-Path $env:USERPROFILE 'Documents\Codex\2026-10-09\new-chat\work\ground'),
    [string]$Python = '',
    [string]$Backbone = (Join-Path $env:USERPROFILE '.keras\models\mobilenet_v2_weights_tf_dim_ordering_tf_kernels_0.5_224_no_top.h5'),
    [string]$OutputRoot = '',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if (-not $OutputRoot) { $OutputRoot = Join-Path $PSScriptRoot 'training-runs' }
$runner = Join-Path $PSScriptRoot 'tools\ground\run_training.py'
$gpuConfigPath = Join-Path $PSScriptRoot 'training-gpu.local.json'
$useWsl = $Device -eq 'Gpu' -or ($Device -eq 'Auto' -and -not $Python -and (Test-Path -LiteralPath $gpuConfigPath))
if ($useWsl) {
    if (-not (Test-Path -LiteralPath $gpuConfigPath)) {
        throw 'GPU setup is missing. Run Setup-GpuTraining.ps1 once, or use -Device Cpu.'
    }
    $gpuConfig = Get-Content -LiteralPath $gpuConfigPath -Raw | ConvertFrom-Json
    function Convert-ToWslPath([string]$WindowsPath) {
        $absolute = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WindowsPath)
        $converted = & wsl.exe -d $gpuConfig.distro -u root --exec wslpath -a -u $absolute
        if ($LASTEXITCODE -ne 0) { throw "Cannot convert path for WSL: $absolute" }
        return ($converted -join '').Trim()
    }
    $gpuArguments = @('-u', (Convert-ToWslPath $runner), '--data-root', (Convert-ToWslPath $DataRoot),
        '--backbone', (Convert-ToWslPath $Backbone), '--output-root', (Convert-ToWslPath $OutputRoot),
        '--epochs', "$Epochs", '--threads', "$Threads", '--device', 'gpu',
        '--batch-size', "$BatchSize", '--cache-batch-size', "$CacheBatchSize")
    if ($CheckOnly) { $gpuArguments += '--check-only' }
    Write-Host "Using NVIDIA GPU through WSL2 ($($gpuConfig.distro))."
    & wsl.exe -d $gpuConfig.distro -u root --exec $gpuConfig.python @gpuArguments
    exit $LASTEXITCODE
}
if (-not $Python) { $Python = Join-Path $DataRoot 'venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python was not found at $Python. Keep the prepared work\ground folder, or pass -DataRoot or -Python."
}
$runnerArguments = @('-u', $runner, '--data-root', $DataRoot, '--backbone', $Backbone,
    '--output-root', $OutputRoot, '--epochs', "$Epochs", '--threads', "$Threads", '--device', $Device.ToLowerInvariant(),
    '--batch-size', "$BatchSize", '--cache-batch-size', "$CacheBatchSize")
if ($CheckOnly) { $runnerArguments += '--check-only' }
& $Python @runnerArguments
exit $LASTEXITCODE
