param(
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [Parameter(Mandatory=$true)][string]$RunName,
    [string]$ResumeFrom
)

# A separate process can retain a long CPU training run across tool-session interruptions.
# RunName must be new: the Python scripts refuse to overwrite earlier evidence.
if ($RunName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Use a simple new run name' }
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$workPath = (Resolve-Path -LiteralPath $WorkRoot -ErrorAction Stop).Path
$pythonPath = Join-Path $workPath 'modelmaker-venv\Scripts\python.exe'
$runPath = Join-Path $workPath $RunName
$statusPath = Join-Path $workPath ($RunName + '-status.json')
if ((Test-Path -LiteralPath $runPath) -or (Test-Path -LiteralPath $statusPath)) {
    throw 'Run already exists; inspect it before starting another run'
}
Set-Location -LiteralPath $projectRoot
$status = @{ run=$RunName; pid=$PID; started=(Get-Date).ToString('o'); state='running'; stage='training' }
function Save-RunStatus { $status | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8 }
Save-RunStatus
try {
    $trainingArguments=@('tools\ground\train_modelmaker.py','--data',(Join-Path $workPath 'rdd-coco-v2'),'--checkpoint-archive',(Join-Path $workPath 'mobilenetv2_ssd_i320_ckpt.tar.gz'),'--output',$runPath,'--epochs','20','--batch-size','8')
    if ($ResumeFrom) { $trainingArguments+=@('--resume-from',$ResumeFrom) }
    & $pythonPath @trainingArguments *> (Join-Path $workPath ($RunName + '.log'))
    if ($LASTEXITCODE -ne 0) { throw "Training exited with code $LASTEXITCODE" }
    $status.stage='validation'; Save-RunStatus
    & $pythonPath tools\ground\evaluate_task_detector.py --model (Join-Path $runPath 'model.tflite') --data (Join-Path $workPath 'rdd-coco-v2') --output ($runPath + '-validation') *> ($runPath + '-validation.log')
    if ($LASTEXITCODE -ne 0) { throw "Validation exited with code $LASTEXITCODE" }
    $status.stage='external'; Save-RunStatus
    & $pythonPath tools\ground\evaluate_task_external.py --dataset (Join-Path $workPath 'external-uk\Potholes.zip') --model (Join-Path $runPath 'model.tflite') --conditions tools\ground\uk-reviewed-conditions.json --output ($runPath + '-external') *> ($runPath + '-external.log')
    if ($LASTEXITCODE -ne 0) { throw "External evaluation exited with code $LASTEXITCODE" }
    $status.state='completed'
} catch {
    $status.state='failed'
    $status.error=$_.Exception.Message
} finally {
    $status.finished=(Get-Date).ToString('o'); Save-RunStatus
}
if ($status.state -ne 'completed') { exit 1 }
