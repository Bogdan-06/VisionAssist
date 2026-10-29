# One-time, isolated WSL2 environment for the existing TensorFlow training pipeline.
[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9._-]+$')][string]$Distro = 'Ubuntu-24.04')
$ErrorActionPreference = 'Stop'
function Invoke-TrainingWsl([string[]]$CommandArguments) {
    & wsl.exe -d $Distro -u root --exec @CommandArguments
    if ($LASTEXITCODE -ne 0) { throw "WSL setup command failed: $($CommandArguments -join ' ')" }
}
$installed = ((& wsl.exe --list --quiet) -join "`n") -replace [string][char]0, ''
if (($installed -split "`r?`n").Trim() -notcontains $Distro) {
    & wsl.exe --install -d $Distro --no-launch
    if ($LASTEXITCODE -ne 0) { throw 'WSL installation failed. Resolve the Windows message, then rerun this script.' }
}
Invoke-TrainingWsl -CommandArguments @('/usr/lib/wsl/lib/nvidia-smi')
Invoke-TrainingWsl -CommandArguments @('apt-get', 'update')
Invoke-TrainingWsl -CommandArguments @('apt-get', 'install', '-y', 'python3-venv')
Invoke-TrainingWsl -CommandArguments @('python3', '-m', 'venv', '/opt/visionassist/venv')
$projectLinux = (& wsl.exe -d $Distro -u root --exec wslpath -a -u $PSScriptRoot) -join ''
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the project path inside WSL.' }
$projectLinux = $projectLinux.Trim()
$gpuPython = '/opt/visionassist/venv/bin/python'
Invoke-TrainingWsl -CommandArguments @($gpuPython, '-m', 'pip', 'install', '--disable-pip-version-check',
    '-r', "$projectLinux/tools/ground/requirements-training-gpu.txt")
Invoke-TrainingWsl -CommandArguments @($gpuPython, "$projectLinux/tools/ground/check_training_gpu.py")
$configuration = @{ distro = $Distro; python = $gpuPython; verifiedUtc = [DateTime]::UtcNow.ToString('o') }
$configuration | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'training-gpu.local.json') -Encoding UTF8
Write-Host 'GPU setup verified. Train-GroundModel.ps1 will now use it automatically.'
