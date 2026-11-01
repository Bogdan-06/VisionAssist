# Safe launcher contracts: no training or dataset reads, even if a lock regresses.
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$tokens = $null
$parseErrors = $null
foreach ($name in @('Train-VisionAssist.ps1','Train-BarrierModel.ps1','Train-GroundModel.ps1')) {
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $project $name),[ref]$tokens,[ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}
. (Join-Path $PSScriptRoot 'Acquire-TrainingLock.ps1')
$lock = Get-VisionAssistTrainingLock
try {
    foreach ($name in @('Train-VisionAssist.ps1','Train-BarrierModel.ps1','Train-GroundModel.ps1')) {
        $argsForChild = @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $project $name),'-Device','Cpu',
            '-DataRoot',(Join-Path $env:TEMP 'visionassist-intentionally-missing-data'))
        if ($name -eq 'Train-VisionAssist.ps1') { $argsForChild += @('-Task','barrier','-Action','evaluate') }
        # PowerShell 5.1 promotes redirected native stderr to NativeCommandError.
        # Expected rejection must be inspected, rather than terminating the test.
        $ErrorActionPreference = 'Continue'
        try {
            $output = (& powershell.exe @argsForChild 2>&1 | Out-String)
            $childExit = $LASTEXITCODE
        } finally { $ErrorActionPreference = 'Stop' }
        if ($childExit -eq 0 -or $output -notmatch 'Another VisionAssist job is active') {
            throw "Shared lock rejection failed for $name : $output"
        }
        Write-Output "PASS shared host lock: $name"
    }
} finally { $lock.Dispose() }
Write-Output 'PASS PowerShell syntax: all three launchers'
