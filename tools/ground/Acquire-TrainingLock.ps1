function Get-VisionAssistTrainingLock {
    $directory = Join-Path $env:LOCALAPPDATA 'VisionAssist'
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    try { return [System.IO.File]::Open((Join-Path $directory 'training.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Another VisionAssist job is active. Do not delete its lock file.' }
}
